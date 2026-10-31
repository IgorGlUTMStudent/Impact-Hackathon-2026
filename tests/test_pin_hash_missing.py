"""Issue #40: an account in valid child mode with a missing (out-of-band nulled) ``pin_hash``
must fail closed on the PIN gate — a clean 422, never an HTTP 500, never an unlock.

The state is not reachable through the ordinary UI (``child_mode_start`` requires a PIN and the
admin omits ``pin_hash``); the mutation here is a test-only ORM change on the disposable test DB.
"""

import pytest

from apps.accounts.models import Throttle

from .conftest import PASSWORD, PIN

pytestmark = pytest.mark.django_db

GATE = "/parinte/"


def null_pin_hash(guardian):
    guardian.pin_hash = None
    guardian.save(update_fields=["pin_hash"])


def test_missing_pin_hash_is_fail_closed_422_not_500(child_client, guardian):
    null_pin_hash(guardian)
    response = child_client.post(GATE, {"pin": PIN})  # valid-format PIN — even the previously correct one
    assert response.status_code == 422
    assert "PIN greșit." in response.content.decode()
    assert child_client.session["mode"] == "child"  # child mode is not cleared
    assert child_client.get("/panou/")["Location"] == GATE  # adult routes stay denied
    assert child_client.get("/familie/")["Location"] == GATE


def test_missing_pin_hash_failures_are_throttled(child_client, guardian):
    null_pin_hash(guardian)
    for _ in range(5):
        assert child_client.post(GATE, {"pin": PIN}).status_code == 422
    assert child_client.post(GATE, {"pin": PIN}).status_code == 429  # 5 failures → 5-minute lock
    assert child_client.session["mode"] == "child"  # lockout never unlocks adult mode


def test_logout_recovery_remains_available_without_pin_hash(child_client, guardian):
    null_pin_hash(guardian)
    assert child_client.post(GATE, {"pin": PIN}).status_code == 422
    response = child_client.post("/cont/iesire/")
    assert response.status_code == 302 and response["Location"] == "/cont/intrare/"
    assert "_auth_user_id" not in child_client.session and "mode" not in child_client.session
    # Password login still works; the account is not broken by the nulled hash.
    assert child_client.post("/cont/intrare/", {"username": guardian.email, "password": PASSWORD}).status_code == 302
    assert child_client.get("/familie/").status_code == 200


def test_missing_pin_hash_does_not_break_child_navigation(child_client, guardian, child):
    null_pin_hash(guardian)
    assert child_client.get("/copil/").status_code == 200  # child surfaces keep working
    assert child_client.get("/carti/").status_code == 200
    assert not Throttle.objects.filter(scope=Throttle.PIN).exists()  # GETs never touch the PIN throttle
