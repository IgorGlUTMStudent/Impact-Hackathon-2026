"""Real PR-26 throttle integration and transactional code consumption."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Reader, Throttle
from apps.club.models import ClubMembership
from apps.club.services import InvalidCode, issue_code, redeem_code

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def setup():
    account = Account.objects.create_user("redeem@demo.local", "synthetic-password", is_staff=True)
    reader = Reader.objects.create(kind=Reader.ADULT, account=account)
    code, plaintext = issue_code(
        account, label="Synthetic", expires_at=timezone.now() + timedelta(days=1),
    )
    return account, reader, code, plaintext


def test_single_use_and_committed_failure(setup):
    actor, reader, code, plaintext = setup
    decorated = " - ".join(plaintext.lower()[i:i+4] for i in range(0, len(plaintext), 4))
    membership = redeem_code(actor, reader, decorated)
    assert membership.valid_until - membership.valid_from == timedelta(days=90)
    with pytest.raises(InvalidCode):
        redeem_code(actor, reader, plaintext)
    assert Throttle.objects.get(scope="redeem").failures == 1
    assert ClubMembership.objects.count() == 1
    code.refresh_from_db()
    assert code.redeemed_at is not None
    reader.delete()
    code.refresh_from_db()
    assert code.redeemed_at is not None and code.redeemed_for is None


def test_grant_failure_rolls_back_consumption(setup):
    actor, reader, code, plaintext = setup
    with patch("apps.club.services.evaluate_achievements", side_effect=RuntimeError("abort")):
        with pytest.raises(RuntimeError):
            redeem_code(actor, reader, plaintext)
    code.refresh_from_db()
    assert code.redeemed_at is None
    assert not ClubMembership.objects.exists()


def test_expired_and_unknown_have_same_error(setup):
    actor, reader, code, plaintext = setup
    code.expires_at = timezone.now() - timedelta(seconds=1)
    code.save()
    errors = []
    for raw in (plaintext, "unknown"):
        with pytest.raises(InvalidCode) as error:
            redeem_code(actor, reader, raw)
        errors.append(str(error.value))
    assert errors[0] == errors[1]
    assert Throttle.objects.get(scope="redeem").failures == 2


def test_two_clients_have_single_winner(setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections, connections, OperationalError
    actor, reader, code, plaintext = setup
    other = Account.objects.create_user("race@demo.local", "synthetic-password")
    other_reader = Reader.objects.create(kind=Reader.ADULT, account=other)
    from apps.club.models import Achievement, AchievementGrant
    from apps.library.models import Book, ShelfEntry
    achievement = Achievement.objects.create(
        code="race-member", title="Synthetic", description="Synthetic",
        rule=Achievement.SHELF_SIZE_GTE, threshold=1, members_only=True, icon="book",
    )
    book = Book.objects.create(title="Synthetic", author="Synthetic", page_count=120,
        genre="story", cover_color="#123456", cover_emoji="📘", source_note="Synthetic")
    for target_reader in (reader, other_reader):
        ShelfEntry.objects.create(reader=target_reader, book=book)
    barrier = Barrier(2)

    def attempt(target):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                redeem_code(target[0], target[1], plaintext)
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
        outcomes = list(pool.map(attempt, [(actor, reader), (other, other_reader)]))
    assert outcomes.count("won") == 1
    assert any(result in {"used", "locked"} for result in outcomes)
    assert ClubMembership.objects.filter(code=code).count() == 1
    assert AchievementGrant.objects.filter(achievement=achievement).count() == 1


def test_nested_caller_transaction_is_rejected(setup):
    from django.db import transaction
    actor, reader, code, plaintext = setup
    with transaction.atomic():
        with pytest.raises(RuntimeError, match="outermost"):
            redeem_code(actor, reader, plaintext)
    code.refresh_from_db()
    assert code.redeemed_at is None and not Throttle.objects.exists()


def test_inactive_actor_cannot_redeem(setup):
    from django.core.exceptions import PermissionDenied
    actor, reader, code, plaintext = setup
    actor.is_active = False
    with pytest.raises(PermissionDenied):
        redeem_code(actor, reader, plaintext)
    assert not ClubMembership.objects.exists()
