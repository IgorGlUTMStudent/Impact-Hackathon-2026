from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts.models import Account, ChildProfile, Reader

PASSWORD = "x-strong-pass-1"
PIN = "2468"
HTMX = {"HTTP_HX_REQUEST": "true"}


def make_guardian(email, pin=PIN):
    account = Account.objects.create_user(email, PASSWORD, display_name="Părinte")
    Reader.objects.create(kind=Reader.ADULT, account=account)
    if pin:
        account.pin_hash = make_password(pin)
        account.save(update_fields=["pin_hash"])
    return account


def make_child(guardian, nickname="Mia"):
    child = ChildProfile.objects.create(guardian=guardian, nickname=nickname, age_band="9-11", avatar="fox")
    Reader.objects.create(kind=Reader.CHILD, child=child)
    return child


@pytest.fixture
def guardian(db):
    return make_guardian("parinte@demo.local")


@pytest.fixture
def child(guardian):
    return make_child(guardian)


@pytest.fixture
def adult_client(client, guardian):
    client.force_login(guardian)
    return client


@pytest.fixture
def child_client(adult_client, child):
    assert adult_client.post(f"/familie/{child.public_id}/mod-copil/").status_code == 302
    return adult_client


@pytest.fixture
def clock(monkeypatch):
    """Movable clock: clock.advance(minutes=…) shifts timezone.now() for throttles and sessions."""

    class Clock:
        now = timezone.now()

        def advance(self, **delta):
            self.now += timedelta(**delta)

    c = Clock()
    monkeypatch.setattr(timezone, "now", lambda: c.now)
    return c
