"""Reading writes exercised against the frozen M0 schema."""

import uuid
from unittest.mock import Mock

import pytest
from django.core.exceptions import ValidationError
from django.db import OperationalError, connection

from apps.accounts.models import Account, Reader
from apps.library import services
from apps.library.models import Book, ProgressEvent, ShelfEntry

pytestmark = pytest.mark.django_db


@pytest.fixture
def diary():
    account = Account.objects.create_user("reader@demo.local", display_name="Reader")
    reader = Reader.objects.create(account=account, kind=Reader.ADULT)
    book = Book.objects.create(title="Synthetic book", author="Demo", page_count=120,
                               genre="story", cover_color="#123456", cover_emoji="📚")
    entry, _ = services.add_to_shelf(reader, book)
    return reader, book, entry


def test_add_duplicate_and_inactive(diary):
    reader, book, entry = diary
    duplicate, created = services.add_to_shelf(reader, book)
    assert duplicate == entry and not created
    assert ShelfEntry.objects.count() == 1
    assert ProgressEvent.objects.count() == 0
    Book.objects.filter(pk=book.pk).update(is_active=False)
    with pytest.raises(Book.DoesNotExist):
        services.add_to_shelf(reader, book)


@pytest.mark.parametrize("page", [0, 35, 120, "35"])
def test_page_persists_and_calls_club_inside_transaction(diary, monkeypatch, page):
    reader, book, entry = diary
    grant = object()

    def evaluate(actual_reader):
        assert actual_reader == reader and connection.in_atomic_block
        assert ShelfEntry.objects.get(pk=entry.pk).current_page == int(page)
        assert ProgressEvent.objects.get().to_page == int(page)
        return [grant]

    monkeypatch.setattr(services.club_services, "evaluate_achievements", evaluate)
    result = services.record_progress(reader, entry, page, uuid.uuid4())
    entry.refresh_from_db()
    assert entry.current_page == int(page) and result.new_grants == [grant]
    assert not result.replayed
    assert (entry.status == ShelfEntry.FINISHED) == (int(page) == book.page_count)
    assert (entry.finished_at is not None) == (int(page) == book.page_count)


@pytest.mark.parametrize("page", [-1, 121, "not-a-number", "35.5", 35.5, True, None])
def test_invalid_page_has_no_writes(diary, monkeypatch, page):
    reader, _, entry = diary
    spy = Mock()
    monkeypatch.setattr(services.club_services, "evaluate_achievements", spy)
    with pytest.raises(ValidationError):
        services.record_progress(reader, entry, page, uuid.uuid4())
    entry.refresh_from_db()
    assert entry.current_page == 0 and not ProgressEvent.objects.exists()
    spy.assert_not_called()


@pytest.mark.parametrize("request_id", [None, "bad", ""])
def test_invalid_request_id_has_no_writes(diary, request_id):
    reader, _, entry = diary
    with pytest.raises(ValidationError):
        services.record_progress(reader, entry, 35, request_id)
    assert not ProgressEvent.objects.exists()


def test_replay_and_conflicting_payload(diary, monkeypatch):
    reader, _, entry = diary
    key = uuid.uuid4()
    spy = Mock(return_value=[object()])
    monkeypatch.setattr(services.club_services, "evaluate_achievements", spy)
    first = services.record_progress(reader, entry, 35, key)
    replay = services.record_progress(reader, entry, "35", str(key))
    assert first.new_grants and replay.replayed and replay.new_grants == []
    spy.assert_called_once_with(reader)
    with pytest.raises(services.RequestIdConflict):
        services.record_progress(reader, entry, 36, key)
    with pytest.raises(services.RequestIdConflict):
        services.finish_book(reader, entry, key)
    assert ProgressEvent.objects.count() == 1
    entry.refresh_from_db()
    assert entry.current_page == 35


def test_idempotency_key_covers_all_entries_for_reader(diary):
    reader, book, entry = diary
    other = Book.objects.create(title="Second", author="Demo", page_count=120, genre=book.genre)
    second, _ = services.add_to_shelf(reader, other)
    key = uuid.uuid4()
    services.record_progress(reader, entry, 35, key)
    with pytest.raises(services.RequestIdConflict):
        services.record_progress(reader, second, 35, key)
    assert ProgressEvent.objects.count() == 1


def test_finish_is_terminal_but_original_payload_replays(diary):
    reader, _, entry = diary
    services.record_progress(reader, entry, 35, uuid.uuid4())
    key = uuid.uuid4()
    first = services.finish_book(reader, entry, key)
    assert first.entry.current_page == 120 and first.entry.finished_at
    assert services.finish_book(reader, entry, key).replayed
    with pytest.raises(ValidationError):
        services.finish_book(reader, entry, uuid.uuid4())
    with pytest.raises(ValidationError):
        services.record_progress(reader, entry, 35, uuid.uuid4())
    finish = ProgressEvent.objects.get(kind=ProgressEvent.FINISH)
    assert (finish.from_page, finish.to_page) == (35, 120)


def test_progress_to_last_page_finishes_and_replays(diary):
    reader, _, entry = diary
    key = uuid.uuid4()
    result = services.record_progress(reader, entry, 120, key)
    assert result.entry.status == ShelfEntry.FINISHED
    assert services.record_progress(reader, entry, 120, key).replayed
    with pytest.raises(services.RequestIdConflict):
        services.finish_book(reader, entry, key)


def test_replay_does_not_overwrite_later_progress(diary):
    reader, _, entry = diary
    key = uuid.uuid4()
    services.record_progress(reader, entry, 35, key)
    services.record_progress(reader, entry, 50, uuid.uuid4())
    replay = services.record_progress(reader, entry, 35, key)
    assert replay.replayed and replay.entry.current_page == 50
    assert ProgressEvent.objects.count() == 2


def test_stale_entry_cannot_supply_from_page(diary):
    reader, _, entry = diary
    for page in [35, 20, 40]:
        services.record_progress(reader, entry, page, uuid.uuid4())
    assert list(ProgressEvent.objects.order_by("pk").values_list("from_page", "to_page")) == [(0, 35), (35, 20), (20, 40)]


def test_foreign_reader_cannot_write_or_replay(diary):
    reader, _, entry = diary
    foreign_account = Account.objects.create_user("foreign@demo.local")
    foreign = Reader.objects.create(account=foreign_account, kind=Reader.ADULT)
    key = uuid.uuid4()
    services.record_progress(reader, entry, 35, key)
    with pytest.raises(ShelfEntry.DoesNotExist):
        services.record_progress(foreign, entry, 35, key)
    with pytest.raises(ShelfEntry.DoesNotExist):
        services.finish_book(foreign, entry, uuid.uuid4())
    assert ProgressEvent.objects.count() == 1


def test_achievement_failure_rolls_back_entire_change(diary, monkeypatch):
    reader, _, entry = diary
    monkeypatch.setattr(services.club_services, "evaluate_achievements", Mock(side_effect=RuntimeError("rule failure")))
    with pytest.raises(RuntimeError):
        services.finish_book(reader, entry, uuid.uuid4())
    entry.refresh_from_db()
    assert entry.current_page == 0 and entry.finished_at is None
    assert entry.status == ShelfEntry.READING and not ProgressEvent.objects.exists()


def test_unrelated_operational_errors_are_not_mislabeled_as_lock(diary, monkeypatch):
    reader, _, entry = diary
    monkeypatch.setattr(services.club_services, "evaluate_achievements", Mock(side_effect=OperationalError("disk full")))
    with pytest.raises(OperationalError, match="disk full"):
        services.record_progress(reader, entry, 35, uuid.uuid4())
    assert not ProgressEvent.objects.exists()
