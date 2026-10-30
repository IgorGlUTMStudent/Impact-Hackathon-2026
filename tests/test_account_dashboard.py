"""Guardian dashboard (/panou/) and owned-child report (/familie/<child>/), Issue #27. Real authz, middleware, DB."""

import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Reader
from apps.club.models import Achievement, AchievementGrant, ClubMembership
from apps.core.viewmodels import StatsVM
from apps.library import services
from apps.library.models import Book, ProgressEvent, ShelfEntry
from tests.conftest import HTMX, make_child, make_guardian

pytestmark = pytest.mark.django_db
ZERO = StatsVM(0, 0, 0, 0)


def make_book(title="Carte", pages=120):
    return Book.objects.create(title=title, author="Autor", page_count=pages, genre="story",
                               cover_color="#123456", cover_emoji="📚", source_note="test")


def report_url(child):
    return f"/familie/{child.public_id}/"


def test_routes_resolve_in_real_urlconf():
    assert reverse("adult_dashboard") == "/panou/"
    some = uuid.uuid4()
    assert reverse("child_report", args=[some]) == f"/familie/{some}/"


@pytest.mark.parametrize("url", ["/panou/", "report"])
def test_anonymous_is_sent_to_login(client, child, url):
    url = report_url(child) if url == "report" else url
    response = client.get(url)
    assert response.status_code == 302 and response["Location"] == f"/cont/intrare/?next={url}"
    response = client.get(url, **HTMX)
    assert response.status_code == 401 and response["HX-Redirect"].startswith("/cont/intrare/")
    assert "HX-Trigger" not in response and child.nickname.encode() not in response.content


def test_new_adult_sees_truthful_zero_dashboard(adult_client, guardian):
    response = adult_client.get("/panou/")
    assert response.status_code == 200
    assert response.context["me"] == {"display_name": guardian.display_name}
    assert response.context["my_stats"] == ZERO
    assert response.context["children"] == []
    assert guardian.email.encode() not in response.content
    assert any(t.name in ("adult/dashboard.html", "accounts/dashboard.html") for t in response.templates)


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_writes_are_405(adult_client, child, method):
    assert getattr(adult_client, method)("/panou/").status_code == 405
    assert getattr(adult_client, method)(report_url(child)).status_code == 405


def test_foreign_and_unknown_child_are_identical_404(adult_client):
    other = make_child(make_guardian("altul@demo.local"), "Străin")
    foreign = adult_client.get(report_url(other))
    unknown = adult_client.get(f"/familie/{uuid.uuid4()}/")
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.content == unknown.content


def test_dashboard_lists_only_own_children_and_ignores_forged_params(adult_client, guardian, child):
    other_guardian = make_guardian("altul@demo.local")
    other = make_child(other_guardian, "Străin")
    entry, _ = services.add_to_shelf(other.reader, make_book())
    services.record_progress(other.reader, entry, 50, uuid.uuid4())
    forged = f"?reader={other.reader.pk}&guardian={other_guardian.pk}&child={other.public_id}"
    response = adult_client.get("/panou/" + forged)
    assert [c["child"].public_id for c in response.context["children"]] == [child.public_id]
    assert response.context["children"][0]["stats"] == ZERO
    assert response.context["children"][0]["current_entry"] is None
    assert b"Str\xc4\x83in" not in response.content
    report = adult_client.get(report_url(child) + forged)
    assert report.context["child"].public_id == child.public_id and report.context["entries"] == []


@pytest.mark.parametrize("url", ["/panou/", "report"])
def test_child_mode_is_denied(child_client, child, url):
    url = report_url(child) if url == "report" else url
    response = child_client.get(url)
    assert response.status_code == 302 and response["Location"] == reverse("pin_gate")
    response = child_client.get(url, **HTMX)
    assert response.status_code == 403 and response.content == b"" and "HX-Trigger" not in response


def test_deleted_or_foreign_active_child_stays_denied(child_client, child):
    session = child_client.session
    session["active_child"] = str(make_child(make_guardian("altul@demo.local")).public_id)
    session.save()
    assert child_client.get("/panou/")["Location"] == reverse("pin_gate")
    child.delete()
    assert child_client.get("/panou/")["Location"] == reverse("pin_gate")


def test_child_progress_is_visible_from_another_guardian_session(guardian, child):
    writer = Client()
    writer.force_login(guardian)
    entry, _ = services.add_to_shelf(child.reader, make_book(pages=120))
    services.record_progress(child.reader, entry, 35, uuid.uuid4())
    events = ProgressEvent.objects.count()

    viewer = Client()
    viewer.force_login(guardian)
    report = viewer.get(report_url(child))
    assert report.status_code == 200
    [shown] = report.context["entries"]
    assert (shown.current_page, shown.page_count, shown.percent, shown.status) == (35, 120, 29, "reading")
    assert report.context["stats"] == StatsVM(1, 0, 35, 35)
    dashboard = viewer.get("/panou/")
    assert dashboard.context["my_stats"] == ZERO  # guardian's own reader is independent
    assert dashboard.context["children"][0]["stats"] == StatsVM(1, 0, 35, 35)
    assert ProgressEvent.objects.count() == events  # GETs write nothing


def test_current_entry_is_newest_unfinished_with_pk_tiebreak(adult_client, guardian, child):
    now = timezone.now()
    second = make_child(guardian, "Ana")
    old, _ = services.add_to_shelf(child.reader, make_book("Veche"))
    tie_a, _ = services.add_to_shelf(child.reader, make_book("Egal A"))
    tie_b, _ = services.add_to_shelf(child.reader, make_book("Egal B"))
    done, _ = services.add_to_shelf(child.reader, make_book("Gata"))
    ShelfEntry.objects.filter(pk=old.pk).update(added_at=now - timedelta(days=3))
    ShelfEntry.objects.filter(pk__in=[tie_a.pk, tie_b.pk]).update(added_at=now - timedelta(days=1))
    services.record_progress(child.reader, done, 120, uuid.uuid4())  # finished and newest: must be skipped

    children = adult_client.get("/panou/").context["children"]
    by_child = {c["child"].public_id: c["current_entry"] for c in children}
    assert by_child[child.public_id].public_id == tie_b.public_id
    assert by_child[child.public_id].book.title == "Egal B"
    assert by_child[second.public_id] is None


def test_grants_only_on_their_childs_report(adult_client, guardian, child):
    second = make_child(guardian, "Ana")
    badge = Achievement.objects.create(code="first", title="Primul pas", description="d",
                                       rule=Achievement.SHELF_SIZE_GTE, threshold=1, members_only=True, icon="star")
    AchievementGrant.objects.create(reader=child.reader, achievement=badge)
    [grant] = adult_client.get(report_url(child)).context["grants"]
    assert (grant.code, grant.title, grant.icon, grant.members_only) == ("first", "Primul pas", "star", True)
    assert grant.granted_at is not None
    assert adult_client.get(report_url(second)).context["grants"] == []
    assert AchievementGrant.objects.count() == 1


@pytest.mark.parametrize("kind, expected", [
    ("valid", True), ("revoked", False), ("expired", False), ("future", False), ("none", False),
])
def test_is_member_is_current_entitlement_not_history(adult_client, child, kind, expected):
    now = timezone.now()
    day = timedelta(days=1)
    # History that must never count as membership on its own: an "active" row whose dates are over.
    ClubMembership.objects.create(reader=child.reader, source=ClubMembership.ADMIN,
                                  valid_from=now - 30 * day, valid_until=now - 20 * day)
    window = {"valid": (-day, day), "revoked": (-day, day), "expired": (-3 * day, -day), "future": (day, 3 * day)}
    if kind in window:
        start, end = window[kind]
        ClubMembership.objects.create(
            reader=child.reader, source=ClubMembership.ADMIN, valid_from=now + start, valid_until=now + end,
            status=ClubMembership.REVOKED if kind == "revoked" else ClubMembership.ACTIVE,
        )
    response = adult_client.get(report_url(child))
    assert response.context["is_member"] is expected
    assert len(response.context["memberships"]) == (2 if kind in window else 1)
    assert set(response.context["memberships"][0]) == {"valid_until", "status"}
    assert any(t.name == "adult/child_report.html" for t in response.templates)
    assert ("Membru Club activ" in response.content.decode()) is expected


def test_report_never_shows_adult_self_reader_entries(adult_client, guardian, child):
    services.add_to_shelf(Reader.objects.get(account=guardian), make_book("A mea"))
    report = adult_client.get(report_url(child))
    assert report.context["entries"] == [] and b"A mea" not in report.content
