from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import Reader


class ClubMembership(models.Model):
    """Time-bounded entitlement of a reader. Active = status active and valid_from <= now < valid_until,
    computed per request by club.services.is_member (PR-5); never stored in the session."""

    ACTIVE, REVOKED = "active", "revoked"
    STATUSES = [(ACTIVE, "Activ"), (REVOKED, "Revocat")]
    ADMIN, CODE = "admin", "code"
    SOURCES = [(ADMIN, "Admin"), (CODE, "Cod")]

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="memberships")
    status = models.CharField(max_length=7, choices=STATUSES, default=ACTIVE)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    source = models.CharField(max_length=5, choices=SOURCES)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    code = models.OneToOneField(
        "club.MembershipCode", null=True, blank=True, on_delete=models.SET_NULL, related_name="membership"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__gt=models.F("valid_from")), name="membership_valid_interval"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "revoked"]), name="membership_status_valid"
            ),
        ]


class MembershipCode(models.Model):
    """One-time code. Plaintext is shown once to staff and never stored; issuing/redeeming is PR-5."""

    code_hash = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=80, help_text="E.g. 'Grupa 9–11, noiembrie'. No child names.")
    expires_at = models.DateTimeField()
    membership_days = models.PositiveIntegerField(default=90)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    redeemed_at = models.DateTimeField(null=True, blank=True)
    # SET_NULL: a used code stays used if the reader is later deleted.
    redeemed_for = models.ForeignKey(
        Reader, null=True, blank=True, on_delete=models.SET_NULL, related_name="redeemed_codes"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(redeemed_for__isnull=True) | models.Q(redeemed_at__isnull=False),
                name="code_redeemed_for_requires_redeemed_at",
            ),
            models.CheckConstraint(condition=models.Q(membership_days__gte=1), name="code_membership_days_min"),
        ]

    def __str__(self):
        return self.label


class Achievement(models.Model):
    """Seeded rule definition. Grants come only from club.services.evaluate_achievements (PR-5)."""

    BOOKS_FINISHED_GTE, PAGES_TOTAL_GTE, SHELF_SIZE_GTE = "books_finished_gte", "pages_total_gte", "shelf_size_gte"
    RULES = [
        (BOOKS_FINISHED_GTE, "Books finished ≥"),
        (PAGES_TOTAL_GTE, "Pages total ≥"),
        (SHELF_SIZE_GTE, "Shelf size ≥"),
    ]

    code = models.SlugField(max_length=40, unique=True)
    # Stored in Romanian (default UI language); Russian titles are P1 (i18n workstream).
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    rule = models.CharField(max_length=20, choices=RULES)
    threshold = models.PositiveIntegerField()
    members_only = models.BooleanField(default=False)
    icon = models.CharField(max_length=60, help_text="Static asset name.")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(threshold__gte=1), name="achievement_threshold_min"),
        ]

    def __str__(self):
        return self.code


class AchievementGrant(models.Model):
    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="grants")
    achievement = models.ForeignKey(Achievement, on_delete=models.PROTECT, related_name="grants")
    granted_at = models.DateTimeField(default=timezone.now)
    was_member = models.BooleanField(default=False, help_text="Membership snapshot at grant time (audit).")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reader", "achievement"], name="grant_reader_achievement_unique"),
        ]


class ClubActivity(models.Model):
    """Members-only item shown on 'Clubul meu'."""

    title = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    place = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    is_published = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "club activities"

    def __str__(self):
        return self.title
