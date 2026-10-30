# PR-5 progress and integration gate (2026-10-30)

Refs #16; dependency: #14 / PR-2. This is a reviewable partial implementation,
not deployment evidence or a completed production redemption flow.

Implemented: database membership boundaries; secure hashed code issuance;
staff activation/revocation; conditional single-use consumption with membership
and achievement writes in one transaction; idempotent achievement evaluation;
admin one-time plaintext response with no-store headers. No schema changes.

## PR-2 adapter pending

`redeem_code(actor, reader, raw_code)` fails closed with IntegrationPending.
The private `_integration` argument is an isolated test seam, NOT a stable
accounts API. Nothing imports or replaces accounts.authz/accounts.throttle.
An eventual reviewed adapter must enforce adult mode, authenticated account,
self/own-child ownership (foreign target -> 404), account-scoped persistent
5/15-minute redemption throttling and 429 even for valid codes during lock.
Boundary-attempt semantics, key types and exception types await Arsenii.

The service rejects enclosing transactions. Its rejection is raised after the
outermost transaction commits. Adapter `record_failure` must persist its update
without raising inside that transaction; any boundary-lock outcome must likewise
be reported after commit. Adapter `check` must serialize per-account attempts.
TestAdapter deliberately does NOT implement real authorization or throttling.
Real authz/child-mode/IDOR/lock-expiry tests remain NOT RUN pending PR-2.

## Actual verification

Local Python 3.12.16 provisioned with uv; `uv sync --frozen` succeeded.
Commands used the local `.tools/uv.exe` executable (not committed).

- `git diff --check`: PASS.
- `uv run python manage.py check`: no issues (0 silenced).
- `uv run python manage.py makemigrations --check --dry-run`: no changes detected.
- `uv run pytest tests/test_membership.py tests/test_achievements.py tests/test_club_redemption.py`:
  **11 passed in 5.50s**, including admin POST and subsequent no-plaintext GET.
- Full `uv run pytest` before the final two admin/service tests were added:
  **58 passed, 6 failed in 39.21s**. Two M0 assertions still require the explicit
  achievement stub and no club-admin additions; owner coordination is needed to
  retire those assertions. Four subprocess tests fail on Windows with WinError
  10106 while importing `_overlapped` under their minimal environment. These
  files were left unchanged because they are outside Igor's assigned scope.

Concurrent SQLite shared-memory test confirms exactly one membership; loser may
receive SQLITE_LOCKED rather than invalid-code (future view must map DB lock to
503). File-backed SQLite/PostgreSQL concurrent-client rehearsal: NOT RUN.
Actual public app deployment, mobile tests and PR-6 e2e: NOT RUN.

Do not merge until independent review and PR-2 integration resolve these gates.
