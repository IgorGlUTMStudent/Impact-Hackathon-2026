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
    assert response["Referrer-Policy"] == "no-referrer"
    plaintext = response.content.decode().split("<code>")[1].split("</code>")[0]
    code = MembershipCode.objects.get()
    from apps.club.services import code_digest
    assert code.code_hash == code_digest(plaintext)
    later = admin_client.get(reverse("admin:club_membershipcode_change", args=[code.pk]))
    assert plaintext not in later.content.decode()
    assert code.code_hash not in later.content.decode()


@pytest.mark.parametrize("days", [0, 1])
def test_admin_code_duration_validation(admin_client, days):
    from unittest.mock import patch
    from django.urls import reverse
    from apps.club.models import MembershipCode

    with patch("apps.club.admin.secrets.token_hex", return_value="A" * 40) as generate:
        response = admin_client.post(reverse("admin:club_membershipcode_add"), {
            "label": "Synthetic", "expires_at_0": "2027-01-01", "expires_at_1": "12:00:00",
            "membership_days": str(days), "_save": "Save",
        })
    assert response.status_code == 200
    if days == 0:
        assert "membership_days" in response.context["adminform"].form.errors
        assert not MembershipCode.objects.exists()
        generate.assert_not_called()
        assert b"<code>" not in response.content
    else:
        assert MembershipCode.objects.get().membership_days == 1
        generate.assert_called_once()
        assert b"<code>" in response.content


@pytest.fixture
def club_staff(client):
    from django.contrib.auth.models import Permission
    account = Account.objects.create_user("staff@demo.local", "synthetic-password", is_staff=True)
    client.force_login(account)
    return client, account, Permission


def test_staff_operations_require_model_permissions(club_staff, reader):
    from django.urls import reverse
    client, actor, Permission = club_staff
    membership_url = reverse("admin:club_clubmembership_add")
    code_url = reverse("admin:club_membershipcode_add")
    for url in (membership_url, code_url):
        assert client.get(url).status_code == 403
        assert client.post(url, {}).status_code == 403
    actor.user_permissions.add(*Permission.objects.filter(
        content_type__app_label="club", codename__in=["add_clubmembership", "add_membershipcode"],
    ))
    response = client.post(membership_url, {
        "reader": str(reader.pk), "valid_from_0": "2026-01-01", "valid_from_1": "12:00:00",
        "valid_until_0": "2027-01-01", "valid_until_1": "12:00:00", "_save": "Save",
    })
    assert response.status_code == 302
    membership = ClubMembership.objects.get()
    assert membership.granted_by == actor and membership.source == ClubMembership.ADMIN
    response = client.post(code_url, {
        "label": "Synthetic", "expires_at_0": "2027-01-01", "expires_at_1": "12:00:00",
        "membership_days": "1", "_save": "Save",
    })
    from apps.club.models import MembershipCode
    assert response.status_code == 200 and b"<code>" in response.content
    assert MembershipCode.objects.get().created_by == actor


def test_club_admin_rejects_edit_delete_and_bulk_delete(admin_client, admin_user, reader):
    from django.urls import reverse
    from apps.club.models import MembershipCode
    from apps.club.services import issue_code
    code, _ = issue_code(admin_user, label="Synthetic", expires_at=timezone.now() + timedelta(days=1))
    now = timezone.now()
    membership = ClubMembership.objects.create(
        reader=reader, code=code, source=ClubMembership.CODE,
        valid_from=now, valid_until=now + timedelta(days=1),
    )
    for model, obj in (("clubmembership", membership), ("membershipcode", code)):
        delete_url = reverse(f"admin:club_{model}_delete", args=[obj.pk])
        assert admin_client.get(delete_url).status_code == 403
        assert admin_client.post(delete_url, {"post": "yes"}).status_code == 403
        assert admin_client.post(reverse(f"admin:club_{model}_change", args=[obj.pk]), {}).status_code == 403
        admin_client.post(reverse(f"admin:club_{model}_changelist"), {
            "action": "delete_selected", "_selected_action": [str(obj.pk)], "index": "0",
        })
    membership.refresh_from_db()
    code.refresh_from_db()
    assert membership.reader == reader and membership.code == code
    assert code.redeemed_at is None
