"""PR-5 isolation tests. This adapter is NOT a production throttle/authz API."""
import hashlib
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Reader, Throttle
from apps.club.models import ClubMembership
from apps.club.services import InvalidCode, issue_code, redeem_code

pytestmark = pytest.mark.django_db(transaction=True)


class TestAdapter:
    __test__ = False

    def authorize(self, actor, reader):
        assert reader.account_id == actor.pk

    def check(self, actor):
        pass  # no real lock policy: waiting for PR-2

    def record_failure(self, actor):
        counter, _ = Throttle.objects.get_or_create(
            scope="redeem", key_hash=hashlib.sha256(str(actor.pk).encode()).hexdigest(),
        )
        counter.failures += 1
        counter.save()

    def reset(self, actor):
        Throttle.objects.filter(scope="redeem").delete()


@pytest.fixture
def setup():
    account = Account.objects.create_user("redeem@demo.local", "synthetic-password", is_staff=True)
    reader = Reader.objects.create(kind=Reader.ADULT, account=account)
    code, plaintext = issue_code(
        account, label="Synthetic", expires_at=timezone.now() + timedelta(days=1),
    )
    return account, reader, code, plaintext, TestAdapter()


def test_single_use_and_committed_failure(setup):
    actor, reader, code, plaintext, adapter = setup
    membership = redeem_code(actor, reader, plaintext, _integration=adapter)
    assert membership.valid_until - membership.valid_from == timedelta(days=90)
    with pytest.raises(InvalidCode):
        redeem_code(actor, reader, plaintext, _integration=adapter)
    assert Throttle.objects.get(scope="redeem").failures == 1
    assert ClubMembership.objects.count() == 1
    code.refresh_from_db()
    assert code.redeemed_at is not None
    reader.delete()
    code.refresh_from_db()
    assert code.redeemed_at is not None and code.redeemed_for is None


def test_grant_failure_rolls_back_consumption(setup):
    actor, reader, code, plaintext, adapter = setup
    with patch("apps.club.services.evaluate_achievements", side_effect=RuntimeError("abort")):
        with pytest.raises(RuntimeError):
            redeem_code(actor, reader, plaintext, _integration=adapter)
    code.refresh_from_db()
    assert code.redeemed_at is None
    assert not ClubMembership.objects.exists()


def test_expired_and_unknown_have_same_error(setup):
    actor, reader, code, plaintext, adapter = setup
    code.expires_at = timezone.now() - timedelta(seconds=1)
    code.save()
    errors = []
    for raw in (plaintext, "unknown"):
        with pytest.raises(InvalidCode) as error:
            redeem_code(actor, reader, raw, _integration=adapter)
        errors.append(str(error.value))
    assert errors[0] == errors[1]
    assert Throttle.objects.get(scope="redeem").failures == 2


def test_two_clients_have_single_winner(setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections, connections, OperationalError
    actor, reader, code, plaintext, adapter = setup
    barrier = Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                redeem_code(actor, reader, plaintext, _integration=adapter)
                return "won"
            except InvalidCode:
                return "used"
            except OperationalError as error:
                # SQLite shared-memory tests return SQLITE_LOCKED immediately;
                # the view integration must map DB lock failure to 503.
                if "locked" not in str(error).lower():
                    raise
                return "locked"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert outcomes.count("won") == 1
    assert any(result in {"used", "locked"} for result in outcomes)
    assert ClubMembership.objects.filter(code=code).count() == 1
