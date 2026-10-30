from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Reader
from apps.club.models import ClubMembership
from apps.club.services import is_member

pytestmark = pytest.mark.django_db


@pytest.fixture
def reader():
    account = Account.objects.create_user("member@demo.local", "synthetic-password")
    return Reader.objects.create(kind=Reader.ADULT, account=account)


def test_membership_boundaries_and_revoke(reader):
    now = timezone.now()
    assert not is_member(reader, now)
    membership = ClubMembership.objects.create(
        reader=reader, source=ClubMembership.ADMIN,
        valid_from=now, valid_until=now + timedelta(days=90),
    )
    assert not is_member(reader, now - timedelta(microseconds=1))
    assert is_member(reader, now)
    assert not is_member(reader, membership.valid_until)
    membership.status = ClubMembership.REVOKED
    membership.save()
    assert not is_member(reader, now)
    ClubMembership.objects.create(
        reader=reader, source=ClubMembership.ADMIN,
        valid_from=now, valid_until=now + timedelta(days=1),
    )
    assert is_member(reader, now)


def test_issuing_requires_staff_and_stores_only_digest(reader):
    from django.core.exceptions import PermissionDenied
    from apps.club.services import issue_code, code_digest
    account = reader.account
    with pytest.raises(PermissionDenied):
        issue_code(account, label="Synthetic", expires_at=timezone.now() + timedelta(days=1))
    account.is_staff = True
    account.save()
    code, plaintext = issue_code(account, label="Synthetic", expires_at=timezone.now() + timedelta(days=1))
    assert code.code_hash == code_digest(plaintext)
    assert plaintext not in str(code.__dict__)
    assert code_digest(" ab-c D\t") == code_digest("ABCD")


def test_redemption_without_adapter_fails_closed(reader):
    from apps.club.services import redeem_code, IntegrationPending
    with pytest.raises(IntegrationPending):
        redeem_code(reader.account, reader, "anything")


def test_staff_activation_and_revocation(reader):
    from apps.club.services import activate_membership, revoke_membership
    actor = reader.account
    actor.is_staff = True
    actor.save()
    now = timezone.now()
    membership = activate_membership(
        actor, reader, valid_from=now, valid_until=now + timedelta(days=90),
    )
    assert is_member(reader)
    revoke_membership(actor, membership)
    assert not is_member(reader)
    membership.refresh_from_db()
    assert membership.revoked_by == actor and membership.revoked_at


def test_admin_code_display_is_once_and_not_cacheable(admin_client):
    from django.urls import reverse
    from apps.club.models import MembershipCode
    response = admin_client.post(reverse("admin:club_membershipcode_add"), {
        "label": "Synthetic", "expires_at_0": "2027-01-01", "expires_at_1": "12:00:00",
        "membership_days": "90", "_save": "Save",
    })
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    plaintext = response.content.decode().split("<code>")[1].split("</code>")[0]
    code = MembershipCode.objects.get()
    from apps.club.services import code_digest
    assert code.code_hash == code_digest(plaintext)
    later = admin_client.get(reverse("admin:club_membershipcode_change", args=[code.pk]))
    assert plaintext not in later.content.decode()
    assert code.code_hash not in later.content.decode()
