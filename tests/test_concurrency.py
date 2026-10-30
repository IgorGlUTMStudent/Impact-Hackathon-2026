"""Real SQLite contention in isolated processes, each with a migrated disk DB.

The parent suite may keep pytest-django's in-memory DB. Each scenario explicitly
uses a temporary file and independent thread-local Django connections, so these
checks cannot accidentally pass against a shared-cache in-memory database.
"""

import inspect
import os
from pathlib import Path
import subprocess
import sys


def run_scenario(tmp_path, scenario):
    database = tmp_path / "concurrency.sqlite3"
    preamble = '''
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import django
django.setup()
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from apps.accounts.models import Account, Reader
from apps.library.models import Book, ProgressEvent, ShelfEntry
from apps.library.services import add_to_shelf, record_progress, finish_book, LockTimeout, RequestIdConflict
from apps.library.stats import reader_stats
assert connection.vendor == "sqlite"
assert str(connection.settings_dict["NAME"]).endswith("concurrency.sqlite3")
assert connection.settings_dict["NAME"] != ":memory:"
call_command("migrate", verbosity=0)
reader = Reader.objects.create(kind="adult", account=Account.objects.create_user("race@demo.local"))
book = Book.objects.create(title="Synthetic", author="Demo", page_count=120, genre="story")
entry, _ = add_to_shelf(reader, book)
def concurrent(actions):
    barrier = threading.Barrier(len(actions))
    def worker(action):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return action()
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(worker, action) for action in actions]
        return [future.result(timeout=10) for future in futures]
'''
    code = preamble + "\n" + inspect.getsource(scenario) + f"\n{scenario.__name__}()\nprint('file-backed SQLite scenario passed')\n"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}", "DJANGO_SETTINGS_MODULE": "config.settings.dev"}
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                            env=env, capture_output=True, text=True, timeout=40, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "file-backed SQLite scenario passed" in result.stdout
    assert database.is_file()


def commit_order():
    results = concurrent([
        lambda: record_progress(reader, entry, 35, uuid.uuid4()),
        lambda: record_progress(reader, entry, 60, uuid.uuid4()),
    ])
    assert all(not result.replayed for result in results)
    events = list(ProgressEvent.objects.order_by("pk"))
    assert len(events) == 2 and events[0].from_page == 0
    assert events[1].from_page == events[0].to_page
    entry.refresh_from_db()
    assert entry.current_page == events[1].to_page
    assert reader_stats(reader).pages_7d == sum(max(0, e.to_page - e.from_page) for e in events)


def same_request():
    key = uuid.uuid4()
    results = concurrent([lambda: record_progress(reader, entry, 35, key)] * 2)
    assert sorted(result.replayed for result in results) == [False, True]
    assert ProgressEvent.objects.count() == 1 and reader_stats(reader).pages_total == 35


def conflicting_request():
    key = uuid.uuid4()
    def write(page):
        try:
            return record_progress(reader, entry, page, key)
        except RequestIdConflict:
            return "conflict"
    results = concurrent([lambda: write(35), lambda: write(60)])
    assert results.count("conflict") == 1 and ProgressEvent.objects.count() == 1


def finish_race():
    def finish():
        try:
            return finish_book(reader, entry, uuid.uuid4())
        except ValidationError:
            return "finished"
    results = concurrent([finish, finish])
    assert results.count("finished") == 1
    assert ProgressEvent.objects.filter(kind="finish").count() == 1
    assert reader_stats(reader).books_finished == 1


def lock_timeout():
    connection.close()
    settings.DATABASES["default"]["OPTIONS"]["timeout"] = 0.15
    key = uuid.uuid4()
    started = threading.Event()
    def attempt():
        close_old_connections()
        try:
            started.set()
            before = time.monotonic()
            try:
                record_progress(reader, entry, 35, key)
            except LockTimeout:
                return time.monotonic() - before
            raise AssertionError("writer unexpectedly acquired held lock")
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            future = pool.submit(attempt)
            assert started.wait(timeout=5)
            elapsed = future.result(timeout=5)
            assert 0.10 <= elapsed < 3
            assert not ProgressEvent.objects.exists()
            assert ShelfEntry.objects.get(pk=entry.pk).current_page == 0
    assert not record_progress(reader, entry, 35, key).replayed
    assert record_progress(reader, entry, 35, key).replayed
    assert ProgressEvent.objects.count() == 1


def test_two_request_ids_same_entry_commit_order(tmp_path):
    run_scenario(tmp_path, commit_order)


def test_replay_same_request_id_returns_prior_result(tmp_path):
    run_scenario(tmp_path, same_request)


def test_reused_request_id_with_other_page_is_conflict(tmp_path):
    run_scenario(tmp_path, conflicting_request)


def test_finish_race_counts_once(tmp_path):
    run_scenario(tmp_path, finish_race)


def test_lock_timeout_stores_nothing_and_retry_succeeds(tmp_path):
    run_scenario(tmp_path, lock_timeout)
