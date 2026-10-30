import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Reader
from apps.core.viewmodels import StatsVM
from apps.library.models import Book, ProgressEvent
from apps.library.services import add_to_shelf, finish_book, record_progress
from apps.library.stats import reader_stats

pytestmark = pytest.mark.django_db


def test_stats_empty_history_positive_deltas_replay_finish_and_isolation(monkeypatch):
    reader = Reader.objects.create(kind="adult", account=Account.objects.create_user("stats@demo.local"))
    other = Reader.objects.create(kind="adult", account=Account.objects.create_user("other@demo.local"))
    assert reader_stats(reader) == StatsVM(0, 0, 0, 0)
    book = Book.objects.create(title="Synthetic", author="Demo", page_count=120, genre="story")
    entry, _ = add_to_shelf(reader, book)
    # Model field defaults retain their original callable when the clock is
    # patched; leave room for those real timestamps below the frozen cutoff.
    now = timezone.now() + timedelta(seconds=1)
    monkeypatch.setattr("apps.library.stats.timezone.now", lambda: now)
    record_progress(reader, entry, 10, uuid.uuid4())
    ProgressEvent.objects.filter(entry=entry).update(created_at=now - timedelta(days=7, seconds=1))
    record_progress(reader, entry, 35, uuid.uuid4())  # +25
    record_progress(reader, entry, 20, uuid.uuid4())  # correction ignored
    key = uuid.uuid4()
    record_progress(reader, entry, 40, key)  # +20
    record_progress(reader, entry, 40, key)  # replay ignored
    assert reader_stats(reader) == StatsVM(1, 0, 40, 45)
    finish_key = uuid.uuid4()
    finish_book(reader, entry, finish_key)  # +80
    finish_book(reader, entry, finish_key)
    assert reader_stats(reader) == StatsVM(1, 1, 120, 125)
    assert reader_stats(other) == StatsVM(0, 0, 0, 0)
    foreign_entry, _ = add_to_shelf(other, book)
    record_progress(other, foreign_entry, 90, uuid.uuid4())
    assert reader_stats(reader) == StatsVM(1, 1, 120, 125)
    assert reader_stats(other) == StatsVM(1, 0, 90, 90)


def test_seven_day_boundary_and_multiple_shelf_entries(monkeypatch):
    reader = Reader.objects.create(kind="adult", account=Account.objects.create_user("boundary@demo.local"))
    now = timezone.now()
    monkeypatch.setattr("apps.library.stats.timezone.now", lambda: now)
    for i in range(2):
        book = Book.objects.create(title=f"Synthetic {i}", author="Demo", page_count=120, genre="story")
        entry, _ = add_to_shelf(reader, book)
        record_progress(reader, entry, 35, uuid.uuid4())
    first, second = ProgressEvent.objects.order_by("pk")
    ProgressEvent.objects.filter(pk=first.pk).update(created_at=now - timedelta(days=7))
    ProgressEvent.objects.filter(pk=second.pk).update(created_at=now + timedelta(seconds=1))
    assert reader_stats(reader) == StatsVM(2, 0, 70, 35)
