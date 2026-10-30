import hashlib

import pytest
from django.db import transaction
from django.test import Client

from apps.accounts import throttle
from apps.accounts.models import Throttle

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db
LOGIN = "/cont/intrare/"


def attempt(client, email, password):
    return client.post(LOGIN, {"username": email, "password": password})


def test_wrong_password_is_422_generic(client, guardian):
    response = attempt(client, guardian.email, "wrong")
    assert response.status_code == 422
    assert "Email sau parolă greșită." in response.content.decode()


def test_unknown_email_same_response(client, guardian):
    known, unknown = attempt(client, guardian.email, "wrong"), attempt(client, "nobody@demo.local", "wrong")
    assert known.status_code == unknown.status_code == 422
    assert known.context["form"].errors == unknown.context["form"].errors


def test_success_redirects_and_email_is_case_insensitive(client, guardian):
    response = attempt(client, "  PARINTE@Demo.Local ", PASSWORD)
    assert response.status_code == 302 and response["Location"] == "/panou/"


def test_sixth_attempt_locked_even_if_correct(client, guardian):
    for _ in range(5):
        assert attempt(client, guardian.email, "wrong").status_code == 422
    response = attempt(client, guardian.email, PASSWORD)
    assert response.status_code == 429
    assert "_auth_user_id" not in client.session
    assert int(response["Retry-After"]) > 14 * 60


def test_lock_survives_new_session_and_case_variants(client, guardian):
    for _ in range(5):
        attempt(client, guardian.email, "wrong")
    assert attempt(Client(), guardian.email.upper(), PASSWORD).status_code == 429


def test_unknown_email_is_locked_too(client):
    for _ in range(5):
        attempt(client, "ghost@demo.local", "wrong")
    assert attempt(client, "ghost@demo.local", "wrong").status_code == 429


def test_other_email_unaffected(client, guardian):
    for _ in range(5):
        attempt(client, "ghost@demo.local", "wrong")
    assert attempt(client, guardian.email, PASSWORD).status_code == 302


def test_success_resets_counter(client, guardian):
    for _ in range(4):
        attempt(client, guardian.email, "wrong")
    assert attempt(client, guardian.email, PASSWORD).status_code == 302
    for _ in range(4):
        assert attempt(Client(), guardian.email, "wrong").status_code == 422
    assert attempt(Client(), guardian.email, PASSWORD).status_code == 302


def test_lock_expires_after_15_min(client, guardian, clock):
    for _ in range(5):
        attempt(client, guardian.email, "wrong")
    clock.advance(minutes=14, seconds=59)
    assert attempt(client, guardian.email, PASSWORD).status_code == 429
    clock.advance(seconds=1)
    assert attempt(client, guardian.email, PASSWORD).status_code == 302


def test_failures_outside_window_do_not_add_up(client, guardian, clock):
    for _ in range(4):
        attempt(client, guardian.email, "wrong")
    clock.advance(minutes=15)
    for _ in range(4):
        assert attempt(client, guardian.email, "wrong").status_code == 422
    assert attempt(client, guardian.email, PASSWORD).status_code == 302


def test_key_is_stored_hashed():
    throttle.record_failure(Throttle.LOGIN, "secret@demo.local")
    row = Throttle.objects.get()
    assert "secret" not in row.key_hash
    assert row.key_hash == hashlib.sha256(b"login:secret@demo.local").hexdigest()


def test_scopes_are_independent():
    for _ in range(5):
        throttle.record_failure(Throttle.REDEEM, "7")
    with pytest.raises(throttle.Locked):
        throttle.check(Throttle.REDEEM, "7")
    throttle.check(Throttle.PIN, "7")
    throttle.check(Throttle.LOGIN, "7")


def test_record_failure_refuses_to_run_inside_a_caller_transaction():
    # A count written inside a transaction that later rolls back would be lost (Issue #14 integration note).
    with pytest.raises(RuntimeError), transaction.atomic():
        throttle.record_failure(Throttle.REDEEM, "7")


def test_unknown_scope_rejected():
    with pytest.raises(ValueError):
        throttle.check("other", "7")
