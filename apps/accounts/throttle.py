"""DB-backed failed-attempt throttles: login, guardian PIN, membership code (contracts/authorization.md).

Public interface (frozen for PR-5, Issue #14):

    check(scope, key)           -> None; raises Locked while the key is locked (even a correct attempt must be refused)
    record_failure(scope, key)  -> None; commits its own transaction, so the count survives a later rollback
    reset(scope, key)           -> None; call after a successful attempt

`scope` is Throttle.LOGIN / PIN / REDEEM. `key` is a str: the normalized email for login, str(account.pk) for pin
and redeem (never an id taken from the request). Keys are stored only as SHA-256(scope:key).
"""

import hashlib
import math
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Throttle

# scope -> (failures allowed in the window, window length, lock length after the last allowed failure)
LIMITS = {
    Throttle.LOGIN: (5, timedelta(minutes=15), timedelta(minutes=15)),
    Throttle.PIN: (5, timedelta(minutes=15), timedelta(minutes=5)),
    Throttle.REDEEM: (5, timedelta(minutes=15), timedelta(minutes=15)),
}


class Locked(Exception):
    """The key is locked. `retry_after` = whole seconds until the lock ends (for Retry-After / "peste N min")."""

    def __init__(self, retry_after):
        super().__init__(f"locked for {retry_after}s")
        self.retry_after = retry_after

    @property
    def minutes(self):
        return max(1, math.ceil(self.retry_after / 60))


def _key_hash(scope, key):
    if scope not in LIMITS:
        raise ValueError(f"unknown throttle scope {scope!r}")
    return hashlib.sha256(f"{scope}:{key}".encode()).hexdigest()


def check(scope, key):
    row = Throttle.objects.filter(scope=scope, key_hash=_key_hash(scope, key)).only("locked_until").first()
    now = timezone.now()
    if row and row.locked_until and row.locked_until > now:
        raise Locked(math.ceil((row.locked_until - now).total_seconds()))


def record_failure(scope, key):
    limit, window, lock = LIMITS[scope]
    # durable: a failure recorded inside a caller's transaction could be rolled back with it, unlocking brute force.
    with transaction.atomic(durable=True):
        now = timezone.now()
        row, _ = Throttle.objects.select_for_update().get_or_create(
            scope=scope, key_hash=_key_hash(scope, key), defaults={"window_started_at": now}
        )
        lock_over = row.locked_until is not None and row.locked_until <= now
        if lock_over or now - row.window_started_at >= window:
            row.failures, row.window_started_at, row.locked_until = 0, now, None
        row.failures += 1
        if row.failures >= limit:
            row.locked_until = now + lock
        row.save()


def reset(scope, key):
    Throttle.objects.filter(scope=scope, key_hash=_key_hash(scope, key)).delete()
