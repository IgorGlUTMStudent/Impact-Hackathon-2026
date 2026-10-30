"""Issue #33: real merged HTTP/DB journeys, not browser or public-host proof.

Only principals/catalog/rule definitions are setup data. All successful journey
writes use configured HTTP routes, real middleware/authz/services and templates.
transaction=True is essential: redemption forbids an enclosing test atomic block.
"""
from datetime import timedelta
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Account, ChildProfile, Reader
from apps.club.models import AchievementGrant, ClubActivity, ClubMembership
from apps.club.services import issue_code
from apps.core.viewmodels import StatsVM
from apps.library import services
from apps.library.models import Book, ProgressEvent, ShelfEntry
from tests.conftest import HTMX, PASSWORD, PIN, make_child, make_guardian

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def catalog_book():
    # Real idempotent command seeds rule definitions/catalog, not successful
    # reading events, memberships or grants. Demo principals are unrelated.
    call_command("seed_demo")
    return Book.objects.filter(is_active=True, page_count=120).order_by("pk").first()


def login(account, client=None):
    client = client if client is not None else Client()
    response = client.post(reverse("login"), {"username": account.email, "password": PASSWORD})
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(account.pk)
    assert client.session.get("mode") != "child"
    return client


def rendered(response, template):
    assert response.status_code == 200
    assert template in {t.name for t in response.templates}


def unsaved(response, status):
    assert response.status_code == status
    assert "HX-Trigger" not in response


def add_book(client, book, reader, *, htmx=False):
    response = client.post(reverse("add_to_shelf", args=[book.public_id]), **(HTMX if htmx else {}))
    entry = ShelfEntry.objects.get(reader=reader, book=book)
    url = reverse("shelf_entry", args=[entry.public_id])
    if htmx:
        assert response.status_code == 204 and response["HX-Redirect"] == url
        assert response["HX-Trigger"] == "saved"
    else:
        assert response.status_code == 302 and response["Location"] == url
    return entry


def test_guardian_child_reading_report_finish_and_real_club(catalog_book):
    """E33-01..08: only code issuance is staff setup, never membership insertion."""
    guardian = make_guardian("e33-family@demo.local", pin=None)
    writer = login(guardian)
    assert not guardian.children.exists()
    rendered(writer.get(reverse("family")), "adult/family.html")
    created = writer.post(reverse("family"), {"nickname": "Mia E33", "age_band": "9-11", "avatar": "fox"})
    assert created.status_code == 302
    child = ChildProfile.objects.get(guardian=guardian)
    reader = Reader.objects.get(child=child, kind=Reader.CHILD)
    assert reader.account_id is None
    configured = writer.post(reverse("pin_set"), {"pin": PIN, "pin_confirm": PIN, "password": PASSWORD})
    assert configured.status_code == 302
    guardian.refresh_from_db()
    assert check_password(PIN, guardian.pin_hash)
    entered = writer.post(reverse("child_mode_start", args=[child.public_id]))
    assert entered.status_code == 302 and entered["Location"] == reverse("child_home")
    assert writer.session["mode"] == "child"
    assert writer.session["active_child"] == str(child.public_id)
    rendered(writer.get(entered["Location"]), "child/home.html")
    rendered(writer.get(reverse("catalog")), "child/catalog.html")
    rendered(writer.get(reverse("book_detail", args=[catalog_book.public_id])), "child/book_detail.html")
    entry = add_book(writer, catalog_book, reader, htmx=True)
    duplicate = writer.post(reverse("add_to_shelf", args=[catalog_book.public_id]), **HTMX)
    assert duplicate.status_code == 204 and "HX-Trigger" not in duplicate
    assert ShelfEntry.objects.filter(book=catalog_book).count() == 1
    assert not ShelfEntry.objects.filter(reader=guardian.reader).exists()
    page = writer.get(reverse("shelf_entry", args=[entry.public_id]))
    rendered(page, "child/shelf_entry.html")
    request_id = str(page.context["request_id"])
    UUID(request_id)
    progress_url = reverse("record_progress", args=[entry.public_id])
    for _ in range(2):
        saved = writer.post(progress_url, {"page": 35, "request_id": request_id}, **HTMX)
        assert saved.status_code == 200 and saved["HX-Trigger"] == "saved"
        assert "child/_progress.html" in {t.name for t in saved.templates}
        entry.refresh_from_db()
        assert entry.current_page == 35
        assert ProgressEvent.objects.filter(reader=reader).count() == 1
        assert not AchievementGrant.objects.filter(reader=reader).exists()
    unsaved(writer.post(progress_url, {"page": 36, "request_id": request_id}, **HTMX), 409)

    viewer = login(guardian)  # independent login POST: never copy writer's session
    assert viewer.session.session_key != writer.session.session_key
    events_before = ProgressEvent.objects.count()
    report = viewer.get(reverse("child_report", args=[child.public_id]))
    rendered(report, "adult/child_report.html")
    assert report.context["child"].public_id == child.public_id
    [shown] = report.context["entries"]
    assert (shown.current_page, shown.page_count) == (35, 120)
    assert report.context["stats"] == StatsVM(1, 0, 35, 35)
    dashboard = viewer.get(reverse("adult_dashboard"))
    rendered(dashboard, "adult/dashboard.html")
    assert dashboard.context["my_stats"] == StatsVM(0, 0, 0, 0)
    [card] = dashboard.context["children"]
    assert card["child"].public_id == child.public_id
    assert card["current_entry"].current_page == 35
    assert card["stats"] == StatsVM(1, 0, 35, 35)
    assert ProgressEvent.objects.count() == events_before

    finish_url = reverse("finish_book", args=[entry.public_id])
    finish_id = uuid4()
    for _ in range(2):
        finished = writer.post(finish_url, {"request_id": finish_id}, **HTMX)
        assert finished.status_code == 200 and finished["HX-Trigger"] == "saved"
    unsaved(writer.post(finish_url, {"request_id": uuid4()}, **HTMX), 422)
    entry.refresh_from_db()
    assert entry.status == ShelfEntry.FINISHED and entry.current_page == 120
    assert ProgressEvent.objects.filter(reader=reader, kind=ProgressEvent.FINISH).count() == 1
    assert ProgressEvent.objects.filter(reader=reader).count() == 2
    assert AchievementGrant.objects.filter(reader=reader, achievement__code="first-book").count() == 1
    badges = writer.get(reverse("achievements"))
    rendered(badges, "child/achievements.html")
    assert "first-book" in {g.code for g in badges.context["earned"]}
    assert "club-reader" in {item["achievement"].code for item in badges.context["locked"]}
    unsaved(writer.get(reverse("club_corner")), 403)

    staff = Account.objects.create_user("e33-staff@demo.local", PASSWORD, is_staff=True)
    code, raw_code = issue_code(staff, label="E33 synthetic", expires_at=timezone.now() + timedelta(days=1))
    activated = viewer.post(reverse("redeem_code"), {"reader": str(child.public_id), "code": raw_code})
    assert activated.status_code == 302 and activated["Location"] == reverse("redeem_code")
    assert "HX-Trigger" not in activated
    confirmation = viewer.get(activated["Location"])
    rendered(confirmation, "adult/redeem_code.html")
    assert any("Membru al clubului" in str(m) for m in confirmation.context["messages"])
    code.refresh_from_db()
    assert code.redeemed_at and code.redeemed_for == reader
    membership = ClubMembership.objects.get(reader=reader)
    assert membership.code == code and membership.status == ClubMembership.ACTIVE
    assert membership.valid_from <= timezone.now() < membership.valid_until
    assert not ClubMembership.objects.filter(reader=guardian.reader).exists()
    unsaved(viewer.post(reverse("redeem_code"), {"reader": str(child.public_id), "code": raw_code}), 422)
    assert ClubMembership.objects.filter(reader=reader).count() == 1
    assert AchievementGrant.objects.filter(reader=reader, achievement__code="club-reader").count() == 1
    hidden = ClubActivity.objects.create(title="E33 unpublished", place="Synthetic", starts_at=timezone.now())
    corner = writer.get(reverse("club_corner"))
    rendered(corner, "child/club_corner.html")
    assert corner.context["activities"]
    assert hidden.title.encode() not in corner.content
    assert len(corner.context["activities"]) == ClubActivity.objects.filter(is_published=True).count()
    badges = writer.get(reverse("achievements"))
    assert [g.code for g in badges.context["earned"]].count("club-reader") == 1
    unsaved(viewer.get(reverse("club_corner")), 403)  # adult is not entitled by child
    # Explicit negative fixture mutations after the real activation happy path.
    membership.status = ClubMembership.REVOKED
    membership.save()
    unsaved(writer.get(reverse("club_corner")), 403)
    membership.status = ClubMembership.ACTIVE
    membership.valid_until = timezone.now() - timedelta(seconds=1)
    membership.valid_from = membership.valid_until - timedelta(days=1)
    membership.save()
    unsaved(writer.get(reverse("club_corner")), 403)
    assert [g.code for g in writer.get(reverse("achievements")).context["earned"]].count("club-reader") == 1


def test_standalone_adult_public_catalog_to_finished_dashboard(catalog_book):
    """E33-09: separate adult, no children/PIN; real plain form responses."""
    adult = make_guardian("e33-adult@demo.local", pin=None)
    visitor = Client()
    rendered(visitor.get(reverse("catalog")), "adult/catalog.html")
    rendered(visitor.get(reverse("book_detail", args=[catalog_book.public_id])), "adult/book_detail.html")
    response = visitor.post(reverse("add_to_shelf", args=[catalog_book.public_id]))
    assert response.status_code == 302 and response["Location"].startswith(reverse("login"))
    assert not ShelfEntry.objects.filter(reader=adult.reader).exists()
    login(adult, visitor)
    entry = add_book(visitor, catalog_book, adult.reader)
    entry_url = reverse("shelf_entry", args=[entry.public_id])
    page = visitor.get(entry_url)
    rendered(page, "adult/shelf_entry.html")
    response = visitor.post(reverse("record_progress", args=[entry.public_id]),
                            {"page": 35, "request_id": page.context["request_id"]})
    assert response.status_code == 302 and response["Location"] == entry_url
    entry.refresh_from_db()
    assert entry.current_page == 35
    assert visitor.get(reverse("adult_dashboard")).context["my_stats"] == StatsVM(1, 0, 35, 35)
    response = visitor.post(reverse("finish_book", args=[entry.public_id]), {"request_id": uuid4()})
    assert response.status_code == 302 and response["Location"] == entry_url
    dashboard = visitor.get(reverse("adult_dashboard"))
    rendered(dashboard, "adult/dashboard.html")
    assert dashboard.context["my_stats"] == StatsVM(1, 1, 120, 120)
    assert dashboard.context["children"] == [] and not adult.children.exists()
    adult.refresh_from_db()
    assert adult.pin_hash is None and visitor.session.get("mode") != "child"
    entry.refresh_from_db()
    assert entry.status == ShelfEntry.FINISHED and entry.current_page == 120
    assert ProgressEvent.objects.filter(reader=adult.reader).count() == 2
    assert not ProgressEvent.objects.exclude(reader=adult.reader).exists()
    assert AchievementGrant.objects.filter(reader=adult.reader, achievement__code="first-book").count() == 1
    assert not ClubMembership.objects.exists()


def test_real_security_refusals_preserve_stored_diary(catalog_book):
    """E33-N01..05/N07/N08 session expiry with real routes and middleware."""
    # Security-only principal/relationship setup; diary mutations remain HTTP.
    guardian = make_guardian("e33-secure@demo.local")
    child = make_child(guardian)
    client = login(guardian)
    entry = add_book(client, catalog_book, guardian.reader)
    progress = reverse("record_progress", args=[entry.public_id])
    key = uuid4()
    assert client.post(progress, {"page": 35, "request_id": key}, **HTMX)["HX-Trigger"] == "saved"
    snapshot = (ProgressEvent.objects.count(), AchievementGrant.objects.count())
    for page in (-1, 121):
        unsaved(client.post(progress, {"page": page, "request_id": uuid4()}, **HTMX), 422)
    unsaved(client.post(progress, {"page": 36, "request_id": key}, **HTMX), 409)
    unsaved(client.post(reverse("finish_book", args=[entry.public_id]), {"request_id": key}, **HTMX), 409)
    other = login(make_guardian("e33-foreign@demo.local"))
    unsaved(other.get(reverse("child_report", args=[child.public_id])), 404)
    unsaved(other.get(reverse("shelf_entry", args=[entry.public_id])), 404)
    unsaved(other.post(progress, {"page": 90, "request_id": uuid4()}, **HTMX), 404)
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(guardian)  # CSRF-negative setup only, not positive E2E auth proof
    unsaved(strict.post(progress, {"page": 90, "request_id": uuid4()}, **HTMX), 403)
    assert client.post(reverse("child_mode_start", args=[child.public_id])).status_code == 302
    for url in (reverse("adult_dashboard"), reverse("family"), reverse("redeem_code"), reverse("admin:index")):
        response = client.get(url)
        assert response.status_code == 302 and response["Location"] == reverse("pin_gate")
        rejected = client.get(url, **HTMX)
        unsaved(rejected, 403)
        assert rejected.content == b""
    expired = login(guardian)
    session = expired.session
    session.set_expiry(-1)
    session.save()
    for anonymous in (expired, Client()):
        response = anonymous.post(progress, {"page": 90, "request_id": uuid4()}, **HTMX)
        unsaved(response, 401)
        assert response["HX-Redirect"].startswith(reverse("login"))
    entry.refresh_from_db()
    assert entry.current_page == 35
    assert (ProgressEvent.objects.count(), AchievementGrant.objects.count()) == snapshot


def test_lock_fault_injection_is_unsaved_with_real_authz(catalog_book):
    """E33-N08 only: narrow deterministic fault injection, never happy path."""
    guardian = make_guardian("e33-lock@demo.local", pin=None)
    client = login(guardian)
    entry = add_book(client, catalog_book, guardian.reader)
    with patch("apps.library.views.services.record_progress", side_effect=services.LockTimeout):
        response = client.post(reverse("record_progress", args=[entry.public_id]),
                               {"page": 35, "request_id": uuid4()}, **HTMX)
    unsaved(response, 503)
    assert int(response["Retry-After"]) > 0
    entry.refresh_from_db()
    assert entry.current_page == 0 and not ProgressEvent.objects.exists()
    assert not AchievementGrant.objects.exists()
