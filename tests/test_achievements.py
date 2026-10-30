from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.club.models import AchievementGrant, ClubMembership
from apps.club.services import evaluate_achievements
from apps.library.models import Book, ShelfEntry

pytestmark = pytest.mark.django_db


@pytest.fixture
def reader():
    call_command("seed_demo")
    return Account.objects.get(email="cititor@demo.local").reader


def test_stored_progress_grants_once_and_membership_snapshot_survives_revoke(reader):
    entry = ShelfEntry.objects.create(
        reader=reader, book=Book.objects.filter(page_count=120).first(), current_page=35,
    )
    assert evaluate_achievements(reader) == []
    entry.current_page = 100
    entry.save()
    assert [g.achievement.code for g in evaluate_achievements(reader)] == ["pages-100"]
    entry.current_page = 120
    entry.status = ShelfEntry.FINISHED
    entry.finished_at = timezone.now()
    entry.save()
    assert [g.achievement.code for g in evaluate_achievements(reader)] == ["first-book"]
    now = timezone.now()
    membership = ClubMembership.objects.create(
        reader=reader, source=ClubMembership.ADMIN,
        valid_from=now, valid_until=now + timedelta(days=90),
    )
    grants = evaluate_achievements(reader)
    assert [g.achievement.code for g in grants] == ["club-reader"]
    assert grants[0].was_member
    assert evaluate_achievements(reader) == []
    membership.status = ClubMembership.REVOKED
    membership.save()
    assert evaluate_achievements(reader) == []
    assert AchievementGrant.objects.filter(reader=reader).count() == 3
    assert not AchievementGrant.objects.get(reader=reader, achievement__code="first-book").was_member


def test_grants_rollback_with_caller(reader):
    ShelfEntry.objects.create(
        reader=reader, book=Book.objects.filter(page_count=120).first(), current_page=100,
    )
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            assert evaluate_achievements(reader)
            raise RuntimeError("abort synthetic write")
    assert not AchievementGrant.objects.filter(reader=reader).exists()
