"""Database-backed club entitlements and achievement evaluation."""

import hashlib
import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.library.models import ShelfEntry
from apps.accounts import throttle
from apps.accounts.models import Account, Reader, Throttle

from .models import Achievement, AchievementGrant, ClubMembership, MembershipCode


class InvalidCode(ValidationError):
    status_code = 422

    def __init__(self):
        super().__init__("Cod invalid sau expirat")


def code_digest(raw_code):
    normalized = "".join(c for c in raw_code.upper() if not c.isspace() and c != "-")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _staff(actor):
    if not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied


@transaction.atomic
def issue_code(actor, *, label, expires_at, membership_days=90):
    """Return (record, plaintext); callers must display plaintext once, never log it."""
    _staff(actor)
    if expires_at <= timezone.now() or membership_days < 1:
        raise ValidationError("Invalid validity interval")
    plaintext = secrets.token_hex(20).upper()
    record = MembershipCode(
        code_hash=code_digest(plaintext), label=label, expires_at=expires_at,
        membership_days=membership_days, created_by=actor,
    )
    record.full_clean()
    record.save()
    return record, plaintext


@transaction.atomic
def activate_membership(actor, reader, *, valid_from, valid_until):
    _staff(actor)
    membership = ClubMembership(
        reader=reader, source=ClubMembership.ADMIN, granted_by=actor,
        valid_from=valid_from, valid_until=valid_until,
    )
    membership.full_clean()
    membership.save()
    evaluate_achievements(reader)
    return membership


@transaction.atomic
def revoke_membership(actor, membership):
    _staff(actor)
    ClubMembership.objects.filter(pk=membership.pk, status=ClubMembership.ACTIVE).update(
        status=ClubMembership.REVOKED, revoked_at=timezone.now(), revoked_by=actor,
    )


@sensitive_variables("raw_code")
def redeem_code(actor, reader, raw_code):
    """Redeem for self/own child. HTTP middleware enforces adult session mode.

    Invalid attempts are counted AFTER the redemption transaction ends, because
    PR-26 record_failure opens its own durable transaction. An enclosing caller
    transaction is forbidden. There is a residual race between check and that
    independent failure commit; this service does not promise strict concurrent
    throttling. Code consumption and grants remain atomic and single-use.
    """
    if transaction.get_connection().in_atomic_block:
        raise RuntimeError("Redemption requires an outermost transaction")
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied
    key = str(actor.pk)
    membership = None
    with transaction.atomic(durable=True):
        Account.objects.select_for_update().get(pk=actor.pk)
        owned = Reader.objects.filter(pk=reader.pk).filter(
            Q(kind=Reader.ADULT, account_id=actor.pk) |
            Q(kind=Reader.CHILD, child__guardian_id=actor.pk)
        ).first()
        if owned is None:
            raise Http404
        reader = owned
        throttle.check(Throttle.REDEEM, key)
        now = timezone.now()
        code = MembershipCode.objects.filter(
            code_hash=code_digest(raw_code), redeemed_at__isnull=True, expires_at__gt=now,
        ).first()
        won = code is not None and MembershipCode.objects.filter(
            pk=code.pk, redeemed_at__isnull=True, expires_at__gt=now,
        ).update(redeemed_at=now, redeemed_for=reader)
        if won:
            membership = ClubMembership.objects.create(
                reader=reader, source=ClubMembership.CODE, code=code,
                valid_from=now, valid_until=now + timedelta(days=code.membership_days),
            )
            evaluate_achievements(reader)
            throttle.reset(Throttle.REDEEM, key)
    if membership is None:
        throttle.record_failure(Throttle.REDEEM, key)
        raise InvalidCode()
    return membership


def is_member(reader, now=None):
    """Check the current entitlement in the database, including both boundaries."""
    now = timezone.now() if now is None else now
    return ClubMembership.objects.filter(
        reader=reader,
        status=ClubMembership.ACTIVE,
        valid_from__lte=now,
        valid_until__gt=now,
    ).exists()


@transaction.atomic
def evaluate_achievements(reader):
    """Return new grants only; nested calls remain in the caller's transaction.

    Shelf totals reflect stored progress, not event counts (which include replays
    and corrections). Existing grants and their membership snapshots are retained.
    """
    totals = ShelfEntry.objects.filter(reader=reader).aggregate(
        books_finished_gte=Count("pk", filter=Q(status=ShelfEntry.FINISHED)),
        pages_total_gte=Sum("current_page", default=0),
        shelf_size_gte=Count("pk"),
    )
    member = is_member(reader)
    new_grants = []
    for achievement in Achievement.objects.order_by("pk"):
        if achievement.members_only and not member:
            continue
        if totals.get(achievement.rule, 0) < achievement.threshold:
            continue
        grant, created = AchievementGrant.objects.get_or_create(
            reader=reader,
            achievement=achievement,
            defaults={"was_member": member},
        )
        if created:
            new_grants.append(grant)
    return new_grants
