# PR-5 progress and integration gate (2026-10-30)

Historical staged-PR report. The subsequent real PR-26 integration and current
limitations are documented in [deploy-club-integration.md](deploy-club-integration.md).

Refs #16; real redemption integration is tracked by **Issue #23**, dependent
on #14 / PR-2. This is a staged club-domain implementation, not deployment
evidence or a completed production redemption flow. Club primitives can be
reviewed separately; the product redeem flow remains blocked by #23.

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

Local Python 3.12.16 provisioned with uv; `uv sync --frozen` succeeded
(14 packages checked).
Commands used the local `.tools/uv.exe` executable (not committed).

- `git diff --check`: PASS.
- `uv run python manage.py check`: no issues (0 silenced).
- `uv run python manage.py makemigrations --check --dry-run`: no changes detected.
- `uv run pytest tests/test_review_fixes.py tests/test_foundation.py tests/test_membership.py tests/test_achievements.py tests/test_club_redemption.py -q`:
  **34 passed, 4 failed** (38 collected, verified separately). The four failures
  are unchanged subprocess tests with Windows WinError 10106 importing
  `_overlapped` under a minimal environment. No skips or xfails were added.
- Full local `uv run pytest`: **66 passed, 4 failed in 61.71s**. The same four
  unchanged Windows subprocess failures remain; both prior Linux CI failures
  and all new form/permissions/deletion tests pass locally.
- Ubuntu/Python 3.12 CI for fix commit `b3e6167`: **101 passed in 18.18s**;
  system check and migration-drift check also passed. GitHub tests the PR merge
  ref, so its test count can include additions from the current base branch.
  Evidence: https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41073163154
  (job 124122250973). Subsequent documentation-only HEAD checks are linked in PR #20.

## Review fixes (2026-10-30)

Only the two obsolete M0 assertions were updated, as requested by independent
review: strict read-only models retain add/change/delete denial, all protected
models retain no-delete/no-bulk-delete checks, while club creation is permitted
under model permissions. The old achievement-stub test now uses a real reader,
100 stored pages and achievement definition, verifying one grant and no replay
duplicates. Arsenii was notified in Issue #14.

CodeForm now rejects membership_days=0 before code generation or database writes;
admin client tests cover 0 and 1, staff with/without permissions, direct delete
GET/POST, forged bulk delete, existing-record edit denial and dependent-record
preservation. One-time plaintext and privacy response headers remain covered.
No models, migrations, config, dependencies or accounts modules changed.

Concurrent SQLite shared-memory test confirms exactly one membership; loser may
receive SQLITE_LOCKED rather than invalid-code (future view must map DB lock to
503). File-backed SQLite/PostgreSQL concurrent-client rehearsal: NOT RUN.
Actual public app deployment, mobile tests and PR-6 e2e: NOT RUN.

Do not self-merge. Independent review and green CI are required for the staged
club primitives; real redemption remains unavailable until Issue #23 is resolved.
