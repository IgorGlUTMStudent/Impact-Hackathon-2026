"""HTML diary routes using the shared accounts authorization and child middleware.

Adult/child production templates remain an integration gate for deployment.
"""

from functools import wraps
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from apps.accounts import authz
from apps.core.viewmodels import BookVM, GrantVM, MascotLine, ShelfEntryVM, percent
from apps.library import services
from apps.library.models import Book, ShelfEntry
from apps.library.stats import reader_stats


def _htmx(request):
    return request.headers.get("HX-Request", "").lower() == "true"


def _unsaved(status):
    response = HttpResponse(_("Nu s-a salvat — încearcă din nou"), status=status, content_type="text/plain; charset=utf-8")
    if status == 503:
        response["Retry-After"] = "1"
    return response


def _with_reader(*, optional=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            reader = authz.current_reader(request) if request.user.is_authenticated else None
            return view(request, reader, *args, **kwargs)
        return wrapped if optional else authz.login_required(wrapped)
    return decorate


def _mode(request):
    return "child" if authz.is_child_mode(request) else "adult"


def _book_vm(book):
    return BookVM(**{name: getattr(book, name) for name in BookVM.__dataclass_fields__})


def _entry_vm(entry):
    return ShelfEntryVM(
        public_id=entry.public_id, book=_book_vm(entry.book), current_page=entry.current_page,
        page_count=entry.book.page_count, percent=percent(entry.current_page, entry.book.page_count),
        status=entry.status,
    )


def _grant_vm(grant):
    achievement = grant.achievement
    return GrantVM(code=achievement.code, title=achievement.title, icon=achievement.icon,
                   granted_at=grant.granted_at, members_only=achievement.members_only)


def _get_entry(reader, public_id):
    return authz.get_entry_for_reader(reader, public_id)


def _shelf_book_ids(reader):
    if reader is None:
        return set()
    # Public UUIDs match BookVM.public_id; database integer IDs never enter
    # this template contract. Always scope even the public book markers.
    return set(ShelfEntry.objects.filter(reader=reader).values_list("book__public_id", flat=True))


def _catalog_context(reader, books, filters):
    return {"books": [_book_vm(book) for book in books], "filters": filters,
            "shelf_book_ids": _shelf_book_ids(reader)}


@require_GET
@_with_reader(optional=True)
def catalog(request, reader):
    filters = {key: request.GET.get(key, "") for key in ("age_band", "genre")}
    books = Book.objects.filter(is_active=True).order_by("title", "pk")
    for name, value in filters.items():
        if value:
            books = books.filter(**{name: value})
    return render(request, f"{_mode(request)}/catalog.html", _catalog_context(reader, books, filters))


@require_GET
@_with_reader(optional=True)
def book_detail(request, reader, book):
    metadata = get_object_or_404(Book, public_id=book, is_active=True)
    # Context matches the owner-provided adult/child book_detail templates;
    # no additional fields are introduced on the shared BookVM.
    context = {"book": _book_vm(metadata), "shelf_book_ids": _shelf_book_ids(reader)}
    return render(request, f"{_mode(request)}/book_detail.html", context)


@require_GET
@_with_reader()
def my_shelf(request, reader):
    entries = ShelfEntry.objects.filter(reader=reader).select_related("book").order_by("-added_at", "pk")
    context = {"entries": [_entry_vm(entry) for entry in entries], "stats": reader_stats(reader)}
    return render(request, f"{_mode(request)}/shelf.html", context)


def _progress_context(request, entry, *, request_id=None, new_grants=(), errors=(), saved=False):
    context = {
        "entry": _entry_vm(entry), "request_id": uuid4() if request_id is None else request_id,
        "new_grants": [_grant_vm(grant) for grant in new_grants], "errors": list(errors),
    }
    if _mode(request) == "child":
        # Fixed script and MascotLine shape from routes.md. No dependency on
        # an undocumented callable in the other owner's pending mascot module.
        if errors:
            mascot = MascotLine("error", _("Hmm, verifică numărul paginii."), "oops")
        elif saved and context["new_grants"]:
            mascot = MascotLine(
                "achievement", _("Ai deblocat «%(title)s»!") % {"title": context["new_grants"][0].title}, "cheer",
            )
        elif saved and entry.status == ShelfEntry.FINISHED:
            mascot = MascotLine("book_finished", _("Ai terminat cartea! Ce aventură!"), "cheer")
        elif saved:
            mascot = MascotLine("progress_saved", _("Bravo! Ai ajuns la pagina %(page)s.") % {"page": entry.current_page}, "happy")
        else:
            mascot = MascotLine("welcome", _("Salut! Hai să alegem o carte."), "happy")
        context["mascot"] = mascot
    return context


@require_GET
@_with_reader()
def shelf_entry(request, reader, entry):
    current = _get_entry(reader, entry)
    return render(request, f"{_mode(request)}/shelf_entry.html", _progress_context(request, current))


def _saved_response(request, result):
    if not _htmx(request):
        return redirect("shelf_entry", entry=result.entry.public_id)
    context = _progress_context(request, result.entry, new_grants=result.new_grants, saved=True)
    response = render(request, f"{_mode(request)}/_progress.html", context)
    # Called only after the service's transaction has exited successfully.
    response["HX-Trigger"] = "saved"
    return response


@require_POST
@csrf_protect
@_with_reader()
def add_to_shelf(request, reader, book):
    active_book = get_object_or_404(Book, public_id=book, is_active=True)
    try:
        entry, created = services.add_to_shelf(reader, active_book)
    except Book.DoesNotExist:
        raise Http404 from None
    except services.LockTimeout:
        return _unsaved(503)
    target = reverse("shelf_entry", args=[entry.public_id])
    if _htmx(request):
        # HTMX processes HX-Redirect before response swapping, including 204.
        # Navigate the whole page; no add partial or DOM target is required.
        response = HttpResponse(status=204, headers={"HX-Redirect": target})
        if created:
            response["HX-Trigger"] = "saved"
        return response
    return redirect(target)


def _write_progress(request, reader, public_id, *, finish):
    entry = _get_entry(reader, public_id)
    request_id = request.POST.get("request_id", "")
    try:
        if finish:
            result = services.finish_book(reader, entry, request_id)
        else:
            result = services.record_progress(reader, entry, request.POST.get("page"), request_id)
    except ValidationError as error:
        # Re-read after a rejected race with a terminal finish. This is still
        # an error response, never an acknowledgement of this request's save.
        entry = _get_entry(reader, public_id)
        context = _progress_context(request, entry, request_id=request_id, errors=error.messages)
        template = "_progress.html" if _htmx(request) else "shelf_entry.html"
        return render(request, f"{_mode(request)}/{template}", context, status=422)
    except ShelfEntry.DoesNotExist:
        raise Http404 from None
    except services.RequestIdConflict:
        return _unsaved(409)
    except services.LockTimeout:
        return _unsaved(503)
    return _saved_response(request, result)


@require_POST
@csrf_protect
@_with_reader()
def record_progress(request, reader, entry):
    return _write_progress(request, reader, entry, finish=False)


@require_POST
@csrf_protect
@_with_reader()
def finish_book(request, reader, entry):
    return _write_progress(request, reader, entry, finish=True)
