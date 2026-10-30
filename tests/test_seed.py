import re

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import Account, ChildProfile, Reader
from apps.club.models import Achievement, ClubActivity, MembershipCode
from apps.library.models import Book

pytestmark = pytest.mark.django_db

MODELS = [Account, ChildProfile, Reader, Book, Achievement, ClubActivity]


def counts():
    return {m.__name__: m.objects.count() for m in MODELS}


def test_seed_twice_creates_no_duplicates(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "synthetic-demo-pass-1")
    monkeypatch.setenv("DEMO_PIN", "2468")
    call_command("seed_demo")
    first = counts()
    call_command("seed_demo")
    assert counts() == first
    assert first == {"Account": 4, "ChildProfile": 2, "Reader": 5, "Book": 12, "Achievement": 3, "ClubActivity": 2}


def test_seed_relations():
    call_command("seed_demo")
    guardian = Account.objects.get(email="parinte1@demo.local")
    assert sorted(guardian.children.values_list("nickname", flat=True)) == ["Alex", "Mia"]
    for child in guardian.children.all():
        assert child.reader.kind == Reader.CHILD
    assert not Account.objects.get(email="parinte2@demo.local").children.exists()
    adult = Account.objects.get(email="cititor@demo.local")
    assert adult.reader.kind == Reader.ADULT and not adult.children.exists()
    staff = Account.objects.get(email="admin@demo.local")
    assert staff.is_staff and not Reader.objects.filter(account=staff).exists()  # staff is not a reader role
    assert set(Achievement.objects.values_list("code", flat=True)) == {"first-book", "pages-100", "club-reader"}
    assert Achievement.objects.get(code="club-reader").members_only
    assert Book.objects.filter(page_count=120).exists()  # demo script book (0/120)


def test_seed_is_synthetic_and_has_no_codes():
    call_command("seed_demo")
    assert all(e.endswith("@demo.local") for e in Account.objects.values_list("email", flat=True))
    assert not MembershipCode.objects.exists()  # codes are issued by staff (PR-5), never seeded or printed
    for book in Book.objects.all():
        assert "http" not in book.source_note and not re.search(r"https?://", book.cover_emoji)


def test_credentials_only_from_env(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_PIN", raising=False)
    call_command("seed_demo")
    guardian = Account.objects.get(email="parinte1@demo.local")
    assert not guardian.has_usable_password() and guardian.pin_hash is None

    monkeypatch.setenv("DEMO_PASSWORD", "synthetic-demo-pass-1")
    monkeypatch.setenv("DEMO_PIN", "2468")
    call_command("seed_demo")
    guardian.refresh_from_db()
    assert guardian.check_password("synthetic-demo-pass-1")
    assert guardian.pin_hash and "2468" not in guardian.pin_hash


def test_seed_output_never_contains_secrets(monkeypatch, capsys):
    monkeypatch.setenv("DEMO_PASSWORD", "synthetic-demo-pass-1")
    monkeypatch.setenv("DEMO_PIN", "2468")
    call_command("seed_demo")
    out = capsys.readouterr().out
    assert "synthetic-demo-pass-1" not in out and "2468" not in out


def test_invalid_pin_rejected(monkeypatch):
    monkeypatch.setenv("DEMO_PIN", "12ab")
    with pytest.raises(CommandError):
        call_command("seed_demo")


def test_reset_recreates_demo_data():
    call_command("seed_demo")
    old_ids = set(ChildProfile.objects.values_list("public_id", flat=True))
    call_command("seed_demo", reset=True)
    assert ChildProfile.objects.count() == 2
    assert not old_ids & set(ChildProfile.objects.values_list("public_id", flat=True))


def test_reset_refused_when_non_demo_accounts_exist():
    call_command("seed_demo")
    Account.objects.create_user("real.person@example.com", "x-strong-pass-1", display_name="R")
    with pytest.raises(CommandError, match="refused"):
        call_command("seed_demo", reset=True)
    assert Account.objects.filter(email="parinte1@demo.local").exists()
