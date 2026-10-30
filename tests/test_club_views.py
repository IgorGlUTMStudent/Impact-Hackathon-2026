"""Real authz/middleware + club HTTP. No fake URLconf or template replacements."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client
from django.utils import timezone

from apps.accounts import throttle
from apps.accounts.models import Account, ChildProfile, Reader, Throttle
from apps.club.models import AchievementGrant, ClubActivity, ClubMembership, MembershipCode
from apps.club.services import InvalidCode, is_member, issue_code, redeem_code
from apps.library import services as library
from apps.library.models import Book, ProgressEvent

pytestmark = pytest.mark.django_db(transaction=True)
URL = "/club/cod/"


@pytest.fixture
def family(client):
    actor = Account.objects.create_user("family@demo.local", "synthetic-password", is_staff=True)
    adult = Reader.objects.create(kind=Reader.ADULT, account=actor)
    child = ChildProfile.objects.create(guardian=actor, nickname="Mia", age_band="9-11", avatar="fox")
    reader = Reader.objects.create(kind=Reader.CHILD, child=child)
    client.force_login(actor)
    return actor, adult, child, reader


def code_for(actor):
    return issue_code(actor, label="Synthetic", expires_at=timezone.now() + timedelta(days=1))


def mode(client, child):
    session = client.session
    session["mode"] = "child"
    session["active_child"] = str(child.public_id)
    session.save()


def test_anonymous_and_readonly_methods():
    client = Client()
    for url in (URL, "/realizari/", "/clubul-meu/"):
        assert client.get(url).status_code == 302
        response = client.get(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 401 and "HX-Redirect" in response
        assert "no-store" in response["Cache-Control"]


def test_target_resolution_prg_and_htmx(client, family):
    actor, adult, child, reader = family
    _, raw = code_for(actor)
    response = client.get(URL + "?success=1")
    assert [c.public_id for c in response.context["children"]] == [child.public_id]
    assert b"Membru al clubului" not in response.content
    response = client.post(URL, {"reader": str(child.public_id), "code": raw})
    assert response.status_code == 302 and response["Location"] == URL
    assert "no-store" in response["Cache-Control"]
    assert is_member(reader) and not is_member(adult)
    assert b"Membru al clubului" in client.get(URL).content
    _, raw = code_for(actor)
    response = client.post(URL, {"reader": "self", "code": raw}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200 and response["HX-Redirect"] == URL
    assert "HX-Trigger" not in response and is_member(adult)


@pytest.mark.parametrize("target", ["foreign-child", "reader-uuid", "missing", "garbage"])
def test_foreign_and_tampered_targets_404(client, family, target):
    actor, adult, child, reader = family
    other = Account.objects.create_user("other@demo.local", "synthetic-password")
    foreign = ChildProfile.objects.create(guardian=other, nickname="Alex", age_band="9-11", avatar="fox")
    foreign_reader = Reader.objects.create(kind=Reader.CHILD, child=foreign)
    value = {"foreign-child": str(foreign.public_id), "reader-uuid": str(reader.public_id),
             "missing": str(uuid4()), "garbage": "garbage"}[target]
    _, raw = code_for(actor)
    assert client.post(URL, {"reader": value, "code": raw}).status_code == 404
    assert not ClubMembership.objects.exists() and not Throttle.objects.exists()
    from django.http import Http404
    with pytest.raises(Http404):
        redeem_code(actor, foreign_reader, raw)
    # Even a stale instance with tampered in-memory ownership is re-read.
    foreign_reader.child = child
    with pytest.raises(Http404):
        redeem_code(actor, foreign_reader, raw)


def test_child_mode_denies_redeem_and_revalidates_session(client, family):
    actor, adult, child, reader = family
    mode(client, child)
    for method in (client.get, client.post):
        assert method(URL).status_code == 302
        response = method(URL, HTTP_HX_REQUEST="true")
        assert response.status_code == 403 and response.content == b""
    assert client.get("/realizari/").status_code == 200
    for url in ("/realizari/", "/clubul-meu/"):
        assert client.post(url).status_code == 405
    child.delete()
    assert client.get("/realizari/").status_code == 302
    assert client.get("/realizari/", HTTP_HX_REQUEST="true").status_code == 403
    assert not ClubMembership.objects.exists()


def test_changed_guardian_session_fails_closed(client, family):
    _, _, child, _ = family
    mode(client, child)
    other = Account.objects.create_user("new@demo.local", "synthetic-password")
    child.guardian = other
    child.save()
    assert client.get("/clubul-meu/", HTTP_HX_REQUEST="true").status_code == 403


def test_csrf_and_expired_session(family):
    actor, _, _, _ = family
    client = Client(enforce_csrf_checks=True)
    client.force_login(actor)
    assert client.post(URL, {"reader": "self", "code": "bad"}).status_code == 403
    page = client.get(URL)
    token = client.cookies["csrftoken"].value
    response = client.post(URL, {"reader": "self", "code": "bad", "csrfmiddlewaretoken": token})
    assert response.status_code == 422
    client.logout()
    client.cookies["csrftoken"] = token  # session expiry retains the browser CSRF cookie
    response = client.post(URL, {"reader": "self"}, HTTP_HX_REQUEST="true", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 401 and "HX-Redirect" in response


def test_generic_errors_persistent_fifth_sixth_and_expiry(client, family):
    actor, adult, child, reader = family
    used, used_raw = code_for(actor)
    redeem_code(actor, adult, used_raw)
    expired, expired_raw = code_for(actor)
    expired.expires_at = timezone.now() - timedelta(seconds=1)
    expired.save()
    valid, valid_raw = code_for(actor)
    start = timezone.now()
    bodies = []
    with patch("apps.accounts.throttle.timezone.now", return_value=start):
        for attempt, raw in enumerate(["unknown", used_raw, expired_raw, "bad-4", "bad-5"], 1):
            response = client.post(URL, {"reader": str(child.public_id), "code": raw}, HTTP_HX_REQUEST="true")
            assert response.status_code == 422 and "HX-Trigger" not in response
            assert response.context["error"] == "Cod invalid sau expirat"
            assert raw.encode() not in response.content
            bodies.append(response.context["error"])
            assert Throttle.objects.get(scope=Throttle.REDEEM).failures == attempt
        fresh_client = Client()
        fresh_client.force_login(actor)
        response = fresh_client.post(URL, {"reader": str(child.public_id), "code": valid_raw})
        assert response.status_code == 429 and int(response["Retry-After"]) == 900
    with patch("apps.accounts.throttle.timezone.now", return_value=start + timedelta(minutes=15)):
        response = client.post(URL, {"reader": str(child.public_id), "code": valid_raw})
        assert response.status_code == 302 and is_member(reader)
    assert not Throttle.objects.filter(scope=Throttle.REDEEM).exists()


def test_reset_only_current_redeem_key(family):
    actor, adult, _, _ = family
    throttle.record_failure(Throttle.LOGIN, actor.email)
    throttle.record_failure(Throttle.PIN, str(actor.pk))
    throttle.record_failure(Throttle.REDEEM, "other-account")
    with pytest.raises(InvalidCode):
        redeem_code(actor, adult, "bad")
    row = Throttle.objects.get(scope=Throttle.REDEEM, failures=1,
                               key_hash=throttle._key_hash(Throttle.REDEEM, str(actor.pk)))
    assert str(actor.pk) != row.key_hash and len(row.key_hash) == 64
    _, raw = code_for(actor)
    redeem_code(actor, adult, raw)
    assert not Throttle.objects.filter(pk=row.pk).exists()
    assert Throttle.objects.count() == 3


def test_lock_mapping_does_not_mask_unrelated_db_errors(client, family):
    with patch("apps.club.views.services.redeem_code", side_effect=OperationalError("database is locked")):
        response = client.post(URL, {"reader": "self", "code": "bad"})
    assert response.status_code == 503 and response["Retry-After"] == "5"
    assert "HX-Trigger" not in response
    with patch("apps.club.views.services.redeem_code", side_effect=OperationalError("connection lost")):
        with pytest.raises(OperationalError):
            client.post(URL, {"reader": "self", "code": "bad"})
    assert not ClubMembership.objects.exists()


def test_service_and_club_http_vertical_slice(client, family):
    actor, adult, child, reader = family
    call_command("seed_demo")
    book = Book.objects.filter(page_count=120).first()
    entry, _ = library.add_to_shelf(reader, book)
    request_id = uuid4()
    library.record_progress(reader, entry, 35, request_id)
    assert library.record_progress(reader, entry, 35, request_id).replayed
    entry.refresh_from_db()
    assert entry.current_page == 35 and ProgressEvent.objects.filter(reader=reader).count() == 1
    library.finish_book(reader, entry, uuid4())
    assert AchievementGrant.objects.filter(reader=reader, achievement__code="first-book").count() == 1
    assert not AchievementGrant.objects.filter(reader=reader, achievement__code="club-reader").exists()
    _, raw = code_for(actor)
    assert client.post(URL, {"reader": str(child.public_id), "code": raw}).status_code == 302
    assert client.post(URL, {"reader": str(child.public_id), "code": raw}).status_code == 422
    assert AchievementGrant.objects.filter(reader=reader, achievement__code="club-reader").count() == 1
    hidden = ClubActivity.objects.create(title="Private hidden activity", place="Synthetic",
                                         starts_at=timezone.now(), is_published=False)
    mode(client, child)
    response = client.get("/clubul-meu/")
    assert response.status_code == 200 and hidden.title.encode() not in response.content
    activities = response.context["activities"]
    assert len(activities) == ClubActivity.objects.filter(is_published=True).count()
    assert [a["starts_at"] for a in activities] == sorted(a["starts_at"] for a in activities)
    earned = client.get("/realizari/?reader=other").context["earned"]
    assert {g.code for g in earned} == {"first-book", "pages-100", "club-reader"}
    membership = ClubMembership.objects.get(reader=reader)
    membership.status = ClubMembership.REVOKED
    membership.save()
    assert client.get("/clubul-meu/").status_code == 403
    assert len(client.get("/realizari/").context["earned"]) == 3
    membership.status = ClubMembership.ACTIVE
    membership.valid_until = timezone.now() - timedelta(seconds=1)
    membership.valid_from = membership.valid_until - timedelta(days=1)
    membership.save()
    assert client.get("/clubul-meu/").status_code == 403
    client.force_login(actor)
    # force_login does not unlock child mode: explicitly use a separate adult session.
    adult_client = Client()
    adult_client.force_login(actor)
    assert adult_client.get("/clubul-meu/").status_code == 403
    assert adult_client.get("/realizari/").context["earned"] == []
    _, raw = code_for(actor)
    assert adult_client.post(URL, {"reader": "self", "code": raw}).status_code == 302
    assert adult_client.get("/clubul-meu/").status_code == 200
    assert adult_client.post("/realizari/").status_code == 405
    adult_entry, _ = library.add_to_shelf(adult, book)
    library.record_progress(adult, adult_entry, 35, uuid4())
    library.finish_book(adult, adult_entry, uuid4())
    assert "first-book" in {g.code for g in adult_client.get("/realizari/").context["earned"]}
