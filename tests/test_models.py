"""Schema invariants from data-model.md, checked against the real database constraints."""

import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Account, ChildProfile, Reader, Throttle
from apps.club.models import Achievement, AchievementGrant, ClubMembership, MembershipCode
from apps.library.models import Book, ProgressEvent, ShelfEntry

pytestmark = pytest.mark.django_db


def raises_integrity(fn):
    with pytest.raises(IntegrityError), transaction.atomic():
        fn()


@pytest.fixture
def adult():
    return Account.objects.create_user("ana@demo.local", "x-strong-pass-1", display_name="Ana")


@pytest.fixture
def child(adult):
    return ChildProfile.objects.create(guardian=adult, nickname="Mia", age_band="9-11", avatar="fox")


@pytest.fixture
def adult_reader(adult):
    return Reader.objects.create(kind=Reader.ADULT, account=adult)


@pytest.fixture
def book():
    return Book.objects.create(
        title="Carte test", author="Autor", page_count=120, genre="story", cover_color="#000000",
        cover_emoji="📘", source_note="test",
    )


# 1. Reader has exactly one owner, matching its kind


def test_reader_valid_adult_and_child(adult, child):
    assert Reader.objects.create(kind=Reader.ADULT, account=adult).account == adult
    assert Reader.objects.create(kind=Reader.CHILD, child=child).child == child


def test_reader_with_both_owners_rejected(adult, child):
    raises_integrity(lambda: Reader.objects.create(kind=Reader.ADULT, account=adult, child=child))


def test_reader_without_owner_rejected():
    raises_integrity(lambda: Reader.objects.create(kind=Reader.ADULT))


@pytest.mark.parametrize("kind", [Reader.CHILD, "robot"])
def test_reader_kind_must_match_owner(adult, kind):
    raises_integrity(lambda: Reader.objects.create(kind=kind, account=adult))


def test_one_reader_per_account(adult, adult_reader):
    raises_integrity(lambda: Reader.objects.create(kind=Reader.ADULT, account=adult))


# 2. Uniqueness


def test_email_unique_case_insensitive_in_db(adult):
    # bulk_create skips the manager's normalization, so this proves the DB constraint itself.
    raises_integrity(lambda: Account.objects.bulk_create([Account(email="ANA@Demo.Local", display_name="X")]))


def test_manager_normalizes_email_and_login_lookup_is_case_insensitive(adult):
    assert Account.objects.create_user(" Bob@Demo.LOCAL ", "x-strong-pass-1", display_name="B").email == "bob@demo.local"
    assert Account.objects.get_by_natural_key("ANA@demo.local") == adult


def test_shelf_reader_book_unique(adult_reader, book):
    ShelfEntry.objects.create(reader=adult_reader, book=book)
    raises_integrity(lambda: ShelfEntry.objects.create(reader=adult_reader, book=book))


def test_progress_reader_request_id_unique(adult_reader, book):
    entry = ShelfEntry.objects.create(reader=adult_reader, book=book)
    rid = uuid.uuid4()
    ProgressEvent.objects.create(entry=entry, reader=adult_reader, from_page=0, to_page=10, kind="progress", request_id=rid)
    raises_integrity(
        lambda: ProgressEvent.objects.create(
            entry=entry, reader=adult_reader, from_page=10, to_page=20, kind="progress", request_id=rid
        )
    )


def test_grant_reader_achievement_unique(adult_reader):
    ach = Achievement.objects.create(code="t", title="T", description="d", rule="books_finished_gte", threshold=1, icon="i")
    AchievementGrant.objects.create(reader=adult_reader, achievement=ach)
    raises_integrity(lambda: AchievementGrant.objects.create(reader=adult_reader, achievement=ach))


def test_throttle_scope_key_unique():
    Throttle.objects.create(scope=Throttle.LOGIN, key_hash="a" * 64)
    Throttle.objects.create(scope=Throttle.PIN, key_hash="a" * 64)  # same key, other scope: allowed
    raises_integrity(lambda: Throttle.objects.create(scope=Throttle.LOGIN, key_hash="a" * 64))


# 3. Range / interval / status invariants


@pytest.mark.parametrize("pages", [0, 2001])
def test_book_page_count_out_of_range_rejected(pages):
    raises_integrity(
        lambda: Book.objects.create(
            title="X", author="Y", page_count=pages, genre="story", cover_color="#000000", cover_emoji="x", source_note="t"
        )
    )


@pytest.mark.parametrize("pages", [1, 2000])
def test_book_page_count_bounds_accepted(pages):
    Book.objects.create(title="X", author="Y", page_count=pages, genre="story", cover_color="#0", cover_emoji="x", source_note="t")


@pytest.mark.parametrize("days", [0, -1])
def test_membership_interval_must_be_positive(adult_reader, days):
    now = timezone.now()
    raises_integrity(
        lambda: ClubMembership.objects.create(
            reader=adult_reader, valid_from=now, valid_until=now + timedelta(days=days), source="admin"
        )
    )


def test_membership_valid_interval_accepted(adult_reader):
    now = timezone.now()
    ClubMembership.objects.create(reader=adult_reader, valid_from=now, valid_until=now + timedelta(days=90), source="admin")


def test_finished_requires_finished_at_and_reading_forbids_it(adult_reader, book):
    raises_integrity(lambda: ShelfEntry.objects.create(reader=adult_reader, book=book, status="finished"))
    raises_integrity(
        lambda: ShelfEntry.objects.create(reader=adult_reader, book=book, status="reading", finished_at=timezone.now())
    )
    ShelfEntry.objects.create(reader=adult_reader, book=book, status="finished", finished_at=timezone.now())


def test_current_page_cannot_be_negative(adult_reader, book):
    raises_integrity(lambda: ShelfEntry.objects.bulk_create([ShelfEntry(reader=adult_reader, book=book, current_page=-1)]))


def test_code_redeemed_for_requires_redeemed_at(adult, adult_reader):
    raises_integrity(
        lambda: MembershipCode.objects.create(
            code_hash="h" * 64, label="L", expires_at=timezone.now(), created_by=adult, redeemed_for=adult_reader
        )
    )


def test_deleting_child_cascades_to_reader_and_shelf(child, book):
    reader = Reader.objects.create(kind=Reader.CHILD, child=child)
    ShelfEntry.objects.create(reader=reader, book=book)
    child.delete()
    assert not Reader.objects.filter(pk=reader.pk).exists()
    assert not ShelfEntry.objects.exists()


def test_book_on_a_shelf_cannot_be_deleted(adult_reader, book):
    from django.db.models import ProtectedError

    ShelfEntry.objects.create(reader=adult_reader, book=book)
    with pytest.raises(ProtectedError):
        book.delete()
