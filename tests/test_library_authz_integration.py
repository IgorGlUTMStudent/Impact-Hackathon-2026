"""Real accounts authz, sessions, CSRF and child middleware on library routes.

Only library rendering uses locmem templates until owner UI PRs land. No authz,
session authorization, middleware or domain service is replaced by a test double.
"""

from datetime import timedelta
from types import SimpleNamespace
import uuid

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import connection, transaction
from django.db.models.signals import post_save
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Account, ChildProfile, Reader
from apps.library.models import Book, ProgressEvent, ShelfEntry

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db
HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def library_rendering(settings):
    assert "apps.accounts.middleware.ChildModeMiddleware" in settings.MIDDLEWARE
    templates = {}
    for mode in ("adult", "child"):
        templates[f"{mode}/catalog.html"] = "{% for b in books %}{{ b.title }}{% endfor %}"
        templates[f"{mode}/book_detail.html"] = "{{ book.title }}"
        templates[f"{mode}/shelf.html"] = "{% for e in entries %}{{ e.book.title }} {{ e.current_page }}{% endfor %}"
        progress = ('{% csrf_token %}{{ entry.current_page }}/{{ entry.page_count }} '
                    '{{ request_id }}{% for e in errors %}{{ e }}{% endfor %}')
        templates[f"{mode}/shelf_entry.html"] = progress
        templates[f"{mode}/_progress.html"] = progress
    engine = settings.TEMPLATES[0]
    settings.TEMPLATES = [{**engine, "APP_DIRS": False, "OPTIONS": {
        **engine["OPTIONS"], "loaders": [("django.template.loaders.locmem.Loader", templates),
                                         "django.template.loaders.app_directories.Loader"],
    }}]


@pytest.fixture
def diary(guardian, child, library_rendering):
    book = Book.objects.create(title="Synthetic 120", author="Demo", page_count=120, genre="story")
    adult_entry = ShelfEntry.objects.create(reader=guardian.reader, book=book)
    child_entry = ShelfEntry.objects.create(reader=child.reader, book=book)
    sibling = ChildProfile.objects.create(guardian=guardian, nickname="Alex", age_band="7-8", avatar="owl")
    sibling_reader = Reader.objects.create(kind="child", child=sibling)
    sibling_entry = ShelfEntry.objects.create(reader=sibling_reader, book=book)
    foreign = Account.objects.create_user("other-library@demo.local")
    foreign_reader = Reader.objects.create(kind="adult", account=foreign)
    foreign_child = ChildProfile.objects.create(guardian=foreign, nickname="Demo", age_band="9-11", avatar="fox")
    Reader.objects.create(kind="child", child=foreign_child)
    private_book = Book.objects.create(title="Foreign shelf marker", author="Demo", page_count=120, genre="story")
    foreign_entry = ShelfEntry.objects.create(reader=foreign_reader, book=private_book)
    return SimpleNamespace(guardian=guardian, child=child, book=book, adult_entry=adult_entry,
                           child_entry=child_entry, sibling_entry=sibling_entry,
                           foreign=foreign, foreign_child=foreign_child, foreign_entry=foreign_entry)


def unsaved(response, status):
    assert response.status_code == status
    assert "HX-Trigger" not in response


def progress(entry):
    return reverse("record_progress", args=[entry.public_id])


def enter_child(client, diary):
    client.force_login(diary.guardian)
    response = client.post(reverse("child_mode_start", args=[diary.child.public_id]))
    assert response.status_code == 302 and response["Location"] == "/copil/"
    assert client.session["active_child"] == str(diary.child.public_id)


def test_public_metadata_and_anonymous_mutations(diary, client):
    assert client.get(reverse("catalog")).status_code == 200
    assert client.get(reverse("book_detail", args=[diary.book.public_id])).status_code == 200
    Book.objects.filter(pk=diary.book.pk).update(is_active=False)
    for public_id in [diary.book.public_id, uuid.uuid4()]:
        unsaved(client.get(reverse("book_detail", args=[public_id])), 404)
    assert b"Synthetic 120" not in client.get(reverse("catalog")).content
    for url in [reverse("add_to_shelf", args=[diary.book.public_id]), progress(diary.adult_entry),
                reverse("finish_book", args=[diary.adult_entry.public_id])]:
        payload = {"page": 35, "request_id": uuid.uuid4()}
        unsaved(client.post(url, payload), 302)
        response = client.post(url, payload, HTTP_HX_CURRENT_URL="http://testserver/carti/", **HX)
        unsaved(response, 401)
        assert response.content == b"" and response["HX-Redirect"].startswith("/cont/intrare/?next=")
    unsaved(client.get(reverse("my_shelf")), 302)
    unsaved(client.get(reverse("my_shelf"), **HX), 401)
    assert not ProgressEvent.objects.exists()


def test_adult_ignores_submitted_authority_and_keeps_shelf_private(diary, client):
    client.force_login(diary.guardian)
    tampering = {"reader": diary.foreign.reader.public_id, "guardian": diary.foreign.pk,
                 "child": diary.foreign_child.public_id, "public_id": diary.foreign_entry.public_id}
    shelf = client.get(reverse("my_shelf"), tampering)
    assert shelf.status_code == 200
    assert [e.public_id for e in shelf.context["entries"]] == [diary.adult_entry.public_id]
    assert b"Foreign shelf marker" not in shelf.content
    book = Book.objects.create(title="Adult addition", author="Demo", page_count=120, genre="story")
    add = client.post(reverse("add_to_shelf", args=[book.public_id]), tampering, **HX)
    assert add.status_code == 204 and add["HX-Trigger"] == "saved"
    entry = ShelfEntry.objects.get(book=book)
    assert entry.reader_id == diary.guardian.reader.pk
    assert add["HX-Redirect"] == reverse("shelf_entry", args=[entry.public_id])
    saved = client.post(progress(diary.adult_entry), {**tampering, "page": 35, "request_id": uuid.uuid4()}, **HX)
    assert saved.status_code == 200 and saved["HX-Trigger"] == "saved"
    diary.adult_entry.refresh_from_db()
    diary.child_entry.refresh_from_db()
    diary.foreign_entry.refresh_from_db()
    assert diary.adult_entry.current_page == 35
    assert diary.child_entry.current_page == diary.foreign_entry.current_page == 0
    detail = client.get(reverse("book_detail", args=[diary.book.public_id]), tampering)
    assert detail.context["shelf_book_ids"] == {book.public_id, diary.book.public_id}
    assert not client.session.get("mode")


@pytest.mark.parametrize("child_mode", [False, True])
def test_real_scoped_entry_lookup_rejects_every_other_reader(diary, client, child_mode):
    if child_mode:
        enter_child(client, diary)
        other_entry = diary.adult_entry
    else:
        client.force_login(diary.guardian)
        other_entry = diary.child_entry
    for public_id in [other_entry.public_id, diary.sibling_entry.public_id,
                      diary.foreign_entry.public_id, uuid.uuid4()]:
        unsaved(client.get(reverse("shelf_entry", args=[public_id])), 404)
        for route in ("record_progress", "finish_book"):
            response = client.post(reverse(route, args=[public_id]), {"page": 35, "request_id": uuid.uuid4()}, **HX)
            unsaved(response, 404)
            assert b"Foreign shelf marker" not in response.content
    assert not ProgressEvent.objects.exists()


@pytest.mark.parametrize("htmx_add", [False, True])
def test_real_guardian_login_child_add_35_replay_conflict_and_finish(diary, client, htmx_add):
    login = client.post(reverse("login"), {"username": diary.guardian.email, "password": PASSWORD})
    assert login.status_code == 302
    start = client.post(reverse("child_mode_start", args=[diary.child.public_id]))
    assert start.status_code == 302 and client.session["active_child"] == str(diary.child.public_id)
    assert client.get(reverse("catalog")).templates[0].name == "child/catalog.html"
    assert client.get(reverse("book_detail", args=[diary.book.public_id])).templates[0].name == "child/book_detail.html"
    book = Book.objects.create(title="Child addition", author="Demo", page_count=120, genre="story")
    headers = HX if htmx_add else {}
    for created in (True, False):
        added = client.post(reverse("add_to_shelf", args=[book.public_id]),
                            {"reader": diary.guardian.reader.public_id}, **headers)
        entry = ShelfEntry.objects.get(book=book)
        assert entry.reader_id == diary.child.reader.pk
        assert added.status_code == (204 if htmx_add else 302)
        assert added["HX-Redirect" if htmx_add else "Location"] == reverse("shelf_entry", args=[entry.public_id])
        assert (added.get("HX-Trigger") == "saved") is (htmx_add and created)
        if htmx_add:
            assert added.content == b""
    page = client.get(reverse("shelf_entry", args=[entry.public_id]))
    assert page.status_code == 200
    key = page.context["request_id"]
    for _ in range(2):
        saved = client.post(progress(entry), {"page": 35, "request_id": key}, **HX)
        assert saved.status_code == 200 and saved["HX-Trigger"] == "saved"
        assert str(saved.context["request_id"]) != str(key)
    assert ProgressEvent.objects.filter(entry=entry).count() == 1
    unsaved(client.post(progress(entry), {"page": 36, "request_id": key}, **HX), 409)
    invalid_key = str(uuid.uuid4())
    rejected = client.post(progress(entry), {"page": 121, "request_id": invalid_key}, **HX)
    unsaved(rejected, 422)
    assert rejected.context["request_id"] == invalid_key
    entry.refresh_from_db()
    assert entry.current_page == 35
    finish_key = uuid.uuid4()
    finish_url = reverse("finish_book", args=[entry.public_id])
    for _ in range(2):
        finished = client.post(finish_url, {"request_id": finish_key}, **HX)
        assert finished.status_code == 200 and finished["HX-Trigger"] == "saved"
    unsaved(client.post(finish_url, {"request_id": uuid.uuid4()}, **HX), 422)
    unsaved(client.post(progress(entry), {"page": 35, "request_id": uuid.uuid4()}, **HX), 422)
    assert ProgressEvent.objects.filter(entry=entry, kind="finish").count() == 1
    stats = client.get(reverse("my_shelf")).context["stats"]
    assert stats.pages_total == 120 and stats.books_finished == 1
    diary.adult_entry.refresh_from_db()
    assert diary.adult_entry.current_page == 0


def test_real_child_middleware_denies_adult_and_unknown_routes(diary, client):
    enter_child(client, diary)
    for url in ("/familie/", "/admin/", "/club/cod/", "/not-a-child-route/"):
        for method in (client.get, client.post):
            response = method(url)
            unsaved(response, 302)
            assert response["Location"] == reverse("pin_gate")
            refused = method(url, **HX)
            unsaved(refused, 403)
            assert refused.content == b""
    assert not ProgressEvent.objects.exists()


@pytest.mark.parametrize("invalid", ["deleted", "foreign", "reader_uuid", "missing", "malformed"])
def test_invalid_active_child_never_falls_back_to_adult(diary, client, invalid):
    enter_child(client, diary)
    if invalid == "deleted":
        active = str(diary.child.public_id)
        diary.child.delete()
    else:
        active = {"foreign": str(diary.foreign_child.public_id), "reader_uuid": str(diary.child.reader.public_id),
                  "missing": str(uuid.uuid4()), "malformed": "not-a-uuid"}[invalid]
    session = client.session
    session["active_child"] = active
    session.save()
    for url in [reverse("catalog"), reverse("my_shelf"), progress(diary.adult_entry),
                reverse("add_to_shelf", args=[diary.book.public_id]), reverse("shelf_entry", args=[uuid.uuid4()])]:
        response = client.post(url, {"page": 35, "request_id": uuid.uuid4()}, **HX)
        unsaved(response, 403)
        assert response.content == b""
        normal = client.get(url)
        unsaved(normal, 302)
        assert normal["Location"] == reverse("pin_gate")
    diary.adult_entry.refresh_from_db()
    assert diary.adult_entry.current_page == 0 and not ProgressEvent.objects.exists()
    assert client.session["mode"] == "child"


@pytest.mark.parametrize("child_mode", [False, True])
def test_real_csrf_for_add_progress_and_finish(diary, child_mode):
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(diary.guardian)
    assert browser.get(reverse("family")).status_code == 200
    token = browser.cookies[settings.CSRF_COOKIE_NAME].value
    if child_mode:
        response = browser.post(reverse("child_mode_start", args=[diary.child.public_id]), {"csrfmiddlewaretoken": token})
        assert response.status_code == 302
    entry = diary.child_entry if child_mode else diary.adult_entry
    book = Book.objects.create(title="CSRF addition", author="Demo", page_count=120, genre="story")
    actions = [(reverse("add_to_shelf", args=[book.public_id]), {}, 204),
               (progress(entry), {"page": 35, "request_id": uuid.uuid4()}, 200),
               (reverse("finish_book", args=[entry.public_id]), {"request_id": uuid.uuid4()}, 200)]
    for url, payload, success in actions:
        unsaved(browser.post(url, payload, **HX), 403)
        response = browser.post(url, {**payload, "csrfmiddlewaretoken": token}, **HX)
        assert response.status_code == success and response["HX-Trigger"] == "saved"


@pytest.mark.parametrize("child_mode", [False, True])
def test_expired_database_session_cannot_save(diary, client, child_mode):
    if child_mode:
        enter_child(client, diary)
    else:
        client.force_login(diary.guardian)
    key = client.session.session_key
    Session.objects.filter(session_key=key).update(expire_date=timezone.now() - timedelta(seconds=1))
    entry = diary.child_entry if child_mode else diary.adult_entry
    response = client.post(progress(entry), {"page": 35, "request_id": uuid.uuid4()},
                           HTTP_HX_CURRENT_URL=f"http://testserver/raft/{entry.public_id}/", **HX)
    unsaved(response, 401)
    assert response.content == b"" and response["HX-Redirect"].startswith("/cont/intrare/?next=/raft/")
    normal = client.post(progress(entry), {"page": 35, "request_id": uuid.uuid4()})
    unsaved(normal, 302)
    assert normal["Location"].startswith("/cont/intrare/?next=")
    assert not ProgressEvent.objects.exists()


def test_inactive_and_unknown_books_cannot_be_added(diary, client):
    client.force_login(diary.guardian)
    hidden = Book.objects.create(title="Inactive", author="Demo", page_count=120, genre="story", is_active=False)
    before = ShelfEntry.objects.count()
    for book_id in (hidden.public_id, uuid.uuid4()):
        for headers in ({}, HX):
            unsaved(client.post(reverse("add_to_shelf", args=[book_id]), **headers), 404)
    assert ShelfEntry.objects.count() == before


@pytest.mark.django_db(transaction=True)
def test_add_and_progress_acknowledgements_follow_real_commit(diary, client):
    client.force_login(diary.guardian)
    book = Book.objects.create(title="Commit boundary", author="Demo", page_count=120, genre="story")
    commits = []
    def observe(sender, instance, **kwargs):
        if instance.book_id == book.pk:
            assert connection.in_atomic_block
            page = instance.current_page
            transaction.on_commit(lambda: commits.append(page))
    post_save.connect(observe, sender=ShelfEntry)
    try:
        added = client.post(reverse("add_to_shelf", args=[book.public_id]), **HX)
        assert added.status_code == 204 and added["HX-Trigger"] == "saved"
        assert commits == [0] and not connection.in_atomic_block
        entry = ShelfEntry.objects.get(book=book)
        saved = client.post(progress(entry), {"page": 35, "request_id": uuid.uuid4()}, **HX)
        assert saved.status_code == 200 and saved["HX-Trigger"] == "saved"
        assert commits == [0, 35] and not connection.in_atomic_block
    finally:
        post_save.disconnect(observe, sender=ShelfEntry)


def real_authz_lock_response():
    # Runs inside the isolated, migrated file DB from test_concurrency.
    from django.test import Client

    assert "apps.accounts.middleware.ChildModeMiddleware" in settings.MIDDLEWARE
    settings.ALLOWED_HOSTS = ["testserver"]
    engine = settings.TEMPLATES[0]
    settings.TEMPLATES = [{**engine, "APP_DIRS": False, "OPTIONS": {
        **engine["OPTIONS"], "loaders": [("django.template.loaders.locmem.Loader",
                                         {"adult/_progress.html": "{{ entry.current_page }} {{ request_id }}"})],
    }}]
    browser = Client()
    browser.force_login(reader.account)
    extra = Book.objects.create(title="Locked add", author="Demo", page_count=120, genre="story")
    connection.close()
    settings.DATABASES["default"]["OPTIONS"]["timeout"] = 0.15
    key = uuid.uuid4()
    actions = [(f"/raft/{entry.public_id}/progres/", {"page": 35, "request_id": key}, 200),
               (f"/carti/{extra.public_id}/adauga/", {}, 204)]
    for url, fields, success in actions:
        def attempt():
            close_old_connections()
            try:
                before = time.monotonic()
                response = browser.post(url, fields, HTTP_HX_REQUEST="true")
                return response, time.monotonic() - before
            finally:
                connection.close()
        before_events = ProgressEvent.objects.count()
        before_page = ShelfEntry.objects.get(pk=entry.pk).current_page
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                response, elapsed = pool.submit(attempt).result(timeout=5)
                assert 0.10 <= elapsed < 3
                assert response.status_code == 503 and "HX-Trigger" not in response
                assert ProgressEvent.objects.count() == before_events
                assert ShelfEntry.objects.get(pk=entry.pk).current_page == before_page
                assert not ShelfEntry.objects.filter(book=extra).exists()
        saved = browser.post(url, fields, HTTP_HX_REQUEST="true")
        assert saved.status_code == success and saved["HX-Trigger"] == "saved"
        replay = browser.post(url, fields, HTTP_HX_REQUEST="true")
        assert replay.status_code == success
    assert ProgressEvent.objects.count() == 1
    assert ShelfEntry.objects.filter(book=extra).count() == 1


def test_real_authz_file_backed_lock_503_and_retry(tmp_path):
    from .test_concurrency import run_scenario

    run_scenario(tmp_path, real_authz_lock_response)
