import pytest
from django.http import HttpResponse
from django.test import Client
from django.urls import path

import config.urls

from apps.accounts.models import ChildProfile, Throttle

from .conftest import HTMX, PASSWORD, PIN, make_child, make_guardian

pytestmark = pytest.mark.django_db
GATE = "/parinte/"


@pytest.fixture
def add_route(settings):
    """Extend the real URLconf with a test-only route (the real one may belong to a PR not merged yet)."""

    def add(route, name):
        extra = path(route, lambda request: HttpResponse(name), name=name)
        settings.ROOT_URLCONF = type("urls", (), {"urlpatterns": [extra, *config.urls.urlpatterns]})

    return add


def wrong_pin(client):
    return client.post(GATE, {"pin": "0000"})


# --- entering child mode -----------------------------------------------------------------------------------------

def test_start_sets_session_and_goes_to_child_home(adult_client, child):
    response = adult_client.post(f"/familie/{child.public_id}/mod-copil/")
    assert response.status_code == 302 and response["Location"] == "/copil/"
    assert adult_client.session["mode"] == "child"
    assert adult_client.session["active_child"] == str(child.public_id)


def test_start_requires_post(adult_client, child):
    assert adult_client.get(f"/familie/{child.public_id}/mod-copil/").status_code == 405
    assert "mode" not in adult_client.session


def test_start_without_pin_redirects_to_pin_setup(adult_client, guardian, child):
    guardian.pin_hash = None
    guardian.save()
    response = adult_client.post(f"/familie/{child.public_id}/mod-copil/")
    assert response["Location"] == "/familie/pin/" and "mode" not in adult_client.session


def test_start_for_foreign_child_is_404(adult_client):
    other_child = make_child(make_guardian("altul@demo.local"))
    assert adult_client.post(f"/familie/{other_child.public_id}/mod-copil/").status_code == 404
    assert "mode" not in adult_client.session


# --- deny by default -----------------------------------------------------------------------------------------------

ADULT_URLS = ["/familie/", "/familie/pin/", "/panou/", "/club/cod/", "/admin/", "/admin/login/", "/cont/intrare/",
              "/cont/inregistrare/", "/healthz/", "/nu-exista/"]


@pytest.mark.parametrize("url", ADULT_URLS)
def test_adult_urls_redirect_to_pin_gate(child_client, url):
    for method in (child_client.get, child_client.post):
        response = method(url)
        assert response.status_code == 302 and response["Location"] == GATE, (method, url)


@pytest.mark.parametrize("url", ADULT_URLS)
def test_adult_urls_via_htmx_are_403_without_partial(child_client, url):
    response = child_client.post(url, **HTMX)
    assert response.status_code == 403 and response.content == b""
    assert "HX-Trigger" not in response


def test_child_mutations_on_family_change_nothing(child_client, child):
    child_client.post(f"/familie/{child.public_id}/editeaza/", {"nickname": "Hacked"})
    child_client.post(f"/familie/{child.public_id}/sterge/", {"confirm": "1"})
    child_client.post("/familie/", {"nickname": "Nou", "age_band": "7-8", "avatar": "owl"})
    assert list(ChildProfile.objects.values_list("nickname", flat=True)) == ["Mia"]


def test_new_unlisted_route_is_denied_by_default(child_client, add_route):
    add_route("nou/", "brand_new_adult_page")
    assert child_client.get("/nou/")["Location"] == GATE


def test_allowed_routes_pass_the_middleware(child_client, add_route):
    add_route("copil/", "child_home")
    assert child_client.get("/copil/").content == b"child_home"


def test_deleted_child_leaves_only_pin_gate_and_logout(child_client, child, add_route):
    add_route("copil/", "child_home")
    child.delete()  # e.g. by the guardian on another device
    assert child_client.get("/copil/")["Location"] == GATE  # fails closed, does not fall back to adult mode
    assert child_client.get("/familie/")["Location"] == GATE
    assert child_client.get(GATE).status_code == 200


# --- PIN gate ------------------------------------------------------------------------------------------------------

def test_correct_pin_exits_child_mode(child_client):
    response = child_client.post(GATE, {"pin": PIN})
    assert response.status_code == 302 and response["Location"] == "/panou/"
    assert "mode" not in child_client.session and "active_child" not in child_client.session
    assert child_client.get("/familie/").status_code == 200


def test_pin_gate_does_not_accept_password(child_client):
    assert child_client.post(GATE, {"pin": PIN[:0], "password": PASSWORD}).status_code == 422
    assert child_client.session["mode"] == "child"


def test_pin_wrong_counts(child_client, guardian):
    response = wrong_pin(child_client)
    assert response.status_code == 422 and "PIN greșit." in response.content.decode()
    assert Throttle.objects.get(scope="pin").failures == 1
    assert child_client.session["mode"] == "child"


def test_pin_lockout_after_5_and_correct_pin_refused_while_locked(child_client):
    for _ in range(5):
        assert wrong_pin(child_client).status_code == 422
    response = child_client.post(GATE, {"pin": PIN})
    assert response.status_code == 429 and child_client.session["mode"] == "child"
    assert "5 min" in response.content.decode()


def test_pin_lock_is_per_account_not_per_session(child_client, guardian, child):
    for _ in range(5):
        wrong_pin(child_client)
    other_tab = Client()
    other_tab.force_login(guardian)
    other_tab.post(f"/familie/{child.public_id}/mod-copil/")
    assert other_tab.post(GATE, {"pin": PIN}).status_code == 429


def test_pin_lock_expires(child_client, clock):
    for _ in range(5):
        wrong_pin(child_client)
    clock.advance(minutes=4, seconds=59)
    assert child_client.post(GATE, {"pin": PIN}).status_code == 429
    clock.advance(seconds=1)
    assert child_client.post(GATE, {"pin": PIN}).status_code == 302
    assert not Throttle.objects.filter(scope="pin").exists()  # reset on success


def test_logout_recovery_ends_session(child_client, guardian):
    for _ in range(5):
        wrong_pin(child_client)
    assert child_client.get("/cont/iesire/").status_code == 405  # logout is POST only
    response = child_client.post("/cont/iesire/")
    assert response.status_code == 302 and response["Location"] == "/cont/intrare/"
    assert "_auth_user_id" not in child_client.session and "mode" not in child_client.session
    assert child_client.get("/familie/")["Location"].startswith("/cont/intrare/")
    # Back in only with email + password; the PIN lock stays until it expires.
    assert child_client.post("/cont/intrare/", {"username": guardian.email, "password": PASSWORD}).status_code == 302
    assert child_client.get("/familie/").status_code == 200


def test_pin_gate_outside_child_mode_redirects(adult_client):
    assert adult_client.get(GATE)["Location"] == "/panou/"


# --- HTMX, session expiry, CSRF --------------------------------------------------------------------------------------

def test_htmx_mutation_without_session_is_401_no_partial(client, child):
    response = client.post("/familie/", {"nickname": "Nou", "age_band": "7-8", "avatar": "owl"},
                           HTTP_HX_CURRENT_URL="http://testserver/familie/?x=1", **HTMX)
    assert response.status_code == 401 and response.content == b""
    assert response["HX-Redirect"] == "/cont/intrare/?next=/familie/"
    assert "HX-Trigger" not in response
    assert ChildProfile.objects.count() == 1


def test_htmx_mutation_after_session_expiry_stores_nothing(adult_client, child):
    adult_client.session.flush()
    adult_client.cookies.clear()
    response = adult_client.post(f"/familie/{child.public_id}/editeaza/", {"nickname": "Nou"}, **HTMX)
    assert response.status_code == 401
    child.refresh_from_db()
    assert child.nickname == "Mia"


def test_normal_request_without_session_redirects_to_login(client):
    response = client.get("/familie/")
    assert response.status_code == 302 and response["Location"] == "/cont/intrare/?next=/familie/"


def test_csrf_failure_is_403(guardian):
    client = Client(enforce_csrf_checks=True)
    client.force_login(guardian)
    response = client.post("/familie/", {"nickname": "Nou", "age_band": "7-8", "avatar": "owl"}, **HTMX)
    assert response.status_code == 403
    assert ChildProfile.objects.count() == 0
