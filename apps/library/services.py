"""Transactional diary writes; callers must obtain the reader through accounts.authz.

View error mapping: ValidationError -> 422, RequestIdConflict -> 409,
LockTimeout -> 503, Book/ShelfEntry.DoesNotExist -> 404. Never retry a write
automatically. Retry the same request_id after an uncertain outcome.

SQLite relies on the foundation's IMMEDIATE transactions and five-second busy
timeout. PostgreSQL locks the reader (serializing reader-wide idempotency keys)
and entry. Replays return the current persisted entry and no new grants.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import Reader
from apps.club import services as club_services
from apps.library.models import Book, ProgressEvent, ShelfEntry


class RequestIdConflict(Exception):
    """The reader has already used this UUID for another payload (HTTP 409)."""


class LockTimeout(Exception):
    """The database could not acquire a write lock; nothing committed (HTTP 503)."""


@dataclass(frozen=True)
class ProgressResult:
    entry: ShelfEntry
    new_grants: list
    replayed: bool


def _is_lock_timeout(error):
    cause = error.__cause__
    sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    message = str(error).lower()
    return sqlstate == "55P03" or "database is locked" in message or "database table is locked" in message


@contextmanager
def _write_transaction():
    try:
        with transaction.atomic():
            yield
    except OperationalError as error:
        if _is_lock_timeout(error):
            raise LockTimeout from error
        raise


def add_to_shelf(reader, book):
    """Return (entry, created); duplicate adds create neither a row nor an event.

    An inactive book is a 404 even if a stale Book instance was passed in.
    The supplied reader is trusted only after the caller's authz check.
    """
    with _write_transaction():
        active_book = Book.objects.get(pk=book.pk, is_active=True)
        return ShelfEntry.objects.get_or_create(reader=reader, book=active_book)


def _request_uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(_("Cerere invalidă. Reîncearcă.")) from None


def _page_number(value):
    # Do not truncate floats, accept booleans, or treat decimal text as a page.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValidationError(_("Introdu un număr întreg de pagini."))
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValidationError(_("Introdu un număr întreg de pagini.")) from None


def _replay(previous, current, kind, to_page):
    if (previous.entry_id, previous.kind, previous.to_page) != (current.pk, kind, to_page):
        raise RequestIdConflict
    return ProgressResult(current, [], replayed=True)


def _record(reader, entry, page, request_id, kind):
    request_id = _request_uuid(request_id)
    requested_page = _page_number(page) if kind == ProgressEvent.PROGRESS else None
    with _write_transaction():
        # The unique key spans every entry for a reader. Locking just the entry
        # would leave a PostgreSQL race when one UUID targets different books.
        Reader.objects.select_for_update().get(pk=reader.pk)
        current = ShelfEntry.objects.select_for_update().get(public_id=entry.public_id, reader=reader)
        book = Book.objects.get(pk=current.book_id)
        to_page = book.page_count if kind == ProgressEvent.FINISH else requested_page
        previous = ProgressEvent.objects.filter(reader=reader, request_id=request_id).first()
        if previous is not None:
            return _replay(previous, current, kind, to_page)
        if not 0 <= to_page <= book.page_count:
            raise ValidationError(
                _("Pagina trebuie să fie între 0 și %(total)s."), params={"total": book.page_count},
            )
        if current.status == ShelfEntry.FINISHED:
            raise ValidationError(_("Cartea este deja terminată."))
        try:
            # Savepoint keeps the enclosing transaction usable if the unique
            # constraint is reached by a writer outside this service's locks.
            with transaction.atomic():
                ProgressEvent.objects.create(
                    reader=reader, entry=current, request_id=request_id,
                    from_page=current.current_page, to_page=to_page, kind=kind,
                )
        except IntegrityError:
            previous = ProgressEvent.objects.filter(reader=reader, request_id=request_id).first()
            if previous is None:
                raise
            current.refresh_from_db()
            return _replay(previous, current, kind, to_page)
        current.current_page = to_page
        if to_page == book.page_count:
            current.status = ShelfEntry.FINISHED
            current.finished_at = timezone.now()
        current.save(update_fields=["current_page", "status", "finished_at"])
        grants = list(club_services.evaluate_achievements(reader))
        result = ProgressResult(current, grants, replayed=False)
    return result


def record_progress(reader, entry, page, request_id):
    """Save an absolute page, automatically finishing at page_count (FR-013).

    The event kind remains 'progress', so its original payload replays exactly.
    """
    return _record(reader, entry, page, request_id, ProgressEvent.PROGRESS)


def finish_book(reader, entry, request_id):
    """Finish once; only an identical request can replay a terminal entry."""
    return _record(reader, entry, None, request_id, ProgressEvent.FINISH)
