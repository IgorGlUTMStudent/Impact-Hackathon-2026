import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

UI_LANGUAGES = [("ro", "Română"), ("ru", "Русский")]
AGE_BANDS = [("7-8", "7–8"), ("9-11", "9–11"), ("12-15", "12–15")]
# Keys only; the drawings are owned by the child UX workstream (static/img/avatars/<key>.svg).
AVATARS = [(key, key) for key in ("fox", "owl", "cat", "bear", "rabbit", "hedgehog", "squirrel", "turtle")]
MAX_CHILDREN_PER_GUARDIAN = 6  # abuse limit, enforced by the family service (PR-2), not by the DB


def normalize_email(email):
    # Whole address lower-cased: Lower("email") uniqueness below must see the same value.
    return (email or "").strip().lower()


class AccountManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(email=normalize_email(username))

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        account = self.model(email=normalize_email(email), **extra_fields)
        account.set_password(password)  # None → unusable password
        account.save(using=self._db)
        return account

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra_fields)


class Account(AbstractBaseUser, PermissionsMixin):
    """Adult identity. Logs in with email; guardianship and club membership are separate axes."""

    # unique=True satisfies Django's auth check (auth.E003); case-insensitive uniqueness is the Lower() constraint.
    email = models.EmailField(max_length=254, unique=True)
    display_name = models.CharField(max_length=40)
    ui_language = models.CharField(max_length=2, choices=UI_LANGUAGES, default="ro")
    # Hashed with make_password; failed attempts live in Throttle(scope="pin").
    pin_hash = models.CharField(max_length=128, blank=True, null=True)
    is_staff = models.BooleanField(default=False, help_text="Club admin (back office); not a reader role.")
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = AccountManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="account_email_ci_unique"),
        ]

    def clean(self):
        super().clean()
        self.email = normalize_email(self.email)

    def __str__(self):
        return f"Account {self.pk}"  # no email in logs/admin titles (FR-045)


class ChildProfile(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    guardian = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="children")
    nickname = models.CharField(max_length=20, validators=[MinLengthValidator(2)])
    age_band = models.CharField(max_length=5, choices=AGE_BANDS)
    avatar = models.CharField(max_length=20, choices=AVATARS)
    ui_language = models.CharField(max_length=2, choices=UI_LANGUAGES, default="ro")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(age_band__in=[value for value, _ in AGE_BANDS]),
                name="child_age_band_valid",
            ),
        ]

    def __str__(self):
        return self.nickname


class Reader(models.Model):
    """Owner of a shelf: exactly one of an adult account or a child profile."""

    ADULT, CHILD = "adult", "child"
    KINDS = [(ADULT, "Adult"), (CHILD, "Child")]

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=5, choices=KINDS)
    account = models.OneToOneField(
        Account, null=True, blank=True, on_delete=models.CASCADE, related_name="reader"
    )
    child = models.OneToOneField(
        ChildProfile, null=True, blank=True, on_delete=models.CASCADE, related_name="reader"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="adult", account__isnull=False, child__isnull=True)
                    | models.Q(kind="child", account__isnull=True, child__isnull=False)
                ),
                name="reader_exactly_one_owner_matching_kind",
            ),
        ]

    def __str__(self):
        return f"Reader {self.public_id}"


class Throttle(models.Model):
    """Failed-attempt counter; read/written only via accounts/throttle.py (PR-2)."""

    LOGIN, PIN, REDEEM = "login", "pin", "redeem"
    SCOPES = [(LOGIN, "Login"), (PIN, "Guardian PIN"), (REDEEM, "Membership code")]

    scope = models.CharField(max_length=6, choices=SCOPES)
    key_hash = models.CharField(max_length=64, help_text="SHA-256 hex of the scope key; never the raw email.")
    failures = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "key_hash"], name="throttle_scope_key_unique"),
            models.CheckConstraint(
                condition=models.Q(scope__in=["login", "pin", "redeem"]), name="throttle_scope_valid"
            ),
        ]
