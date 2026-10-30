# Real club backend and HTTP integration — 2026-10-30

Refs #16, #23, #28. Base: canonical upstream/main `ecea1f3` (PR #20 and #26
merged); origin is Igor's fork, whose main is older. Feature branch:
`feat/igor-club-redemption-routes`. No accounts/library/core/config/UI-owner
files, models, migrations or dependencies changed.

## Implemented and tested

Production redemption uses real PR-26 authz/throttle, no TestAdapter or
IntegrationPending. Target ownership is re-read from the DB. Session mode is
enforced by ChildModeMiddleware at the HTTP boundary (actor alone has no session).
The view resolves self via current_reader and child UUID via
get_child_for_guardian. A Reader UUID cannot substitute for a ChildProfile UUID.

Code update, membership, achievement evaluation and account-specific redeem
reset share one durable transaction. Invalid-code failure is recorded AFTER
that transaction, through the independent durable record_failure, then InvalidCode
is raised. Caller transactions are refused. This fixes nested durable atomic
failure while preserving failed attempts. Code plaintext is neither reflected
nor logged; Django sensitive-variable/POST annotations protect error reports.

Five bad attempts persist five failures; fifth is 422, sixth (even correct code,
fresh session) is 429 with Retry-After=900 on frozen clocks. At lock expiry correct
code succeeds. Reset leaves other accounts and login/PIN scopes unchanged.

Conditional code update has at most one winner; rollback test injects failure in
achievement evaluation and confirms code/membership remain unconsumed. Two real
SQLite clients with distinct accounts race for one code, yielding exactly one
membership; loser can be invalid-code or SQLITE_LOCKED. PostgreSQL: NOT RUN.

Residual throttle race: PR-26 check is a read; an invalid attempt releases the
account lock before independent record_failure commits. Concurrent checks may
pass during that gap and delayed failures can arrive after a success/reset.
Strict concurrent rate-limit serialization is NOT claimed. No accounts API was
rewritten. Lock errors alone map to 503/Retry-After; unrelated DB errors propagate.

## HTTP security matrix

Real middleware/authz and Django Client tests (no fake URLconf/templates):

| Status | Evidence |
|---|---|
| 200 | private GETs; active member corner; committed HTMX redemption + HX-Redirect |
| 302 | anonymous login, child adult-route to PIN, normal committed POST-redirect-GET |
| 401 | anonymous/expired-session HTMX + HX-Redirect |
| 403 | child-mode redemption, missing CSRF, nonmember/revoked/expired corner |
| 404 | foreign/unknown/tampered child UUID; foreign Reader at service boundary |
| 405 | POST to achievements/corner |
| 422 | identical unknown/used/expired code errors, durable failures |
| 429 | sixth attempt, including valid code and a new session, Retry-After |
| 503 | lock-specific error mapping; unrelated OperationalError is not masked |

No false saved trigger. Success is a server message after commit, not a query
parameter; pages and redirects are no-store. Achievements GET creates no grants,
uses server-selected reader, preserves earned badges after revocation. Member
corner rechecks DB every request and displays only published activities ordered
by starts_at/pk. Adult entitlement does not entitle the child, or conversely.

## Actual local verification

Commands run with local `.tools/uv.exe` (not committed), Python 3.12.16:

- `uv sync --frozen`: 14 packages checked.
- `uv run python manage.py check`: no issues (0 silenced).
- `uv run python manage.py makemigrations --check --dry-run`: no changes detected.
- `uv run pytest tests/test_club_redemption.py tests/test_membership.py tests/test_achievements.py -v`:
  **17 passed in 5.32s** (final tests).
- `uv run pytest tests/test_club_views.py -v`: **13 passed in 5.26s** (final tests).
- After strengthening the two-account race to verify exactly one club grant as
  well as one membership, `uv run pytest tests/test_club_redemption.py -v`:
  **6 passed in 2.06s**.
- Full `uv run pytest`: **201 passed, 4 failed in 94.74s**, before the final two
  added service tests, subsequently verified above. Unchanged Windows subprocess
  failures in test_review_fixes.py: test_wsgi_without_settings_module_fails_closed_without_secret,
  test_wsgi_without_settings_module_starts_with_prod,
  test_wsgi_respects_explicit_settings_module, test_manage_py_still_defaults_to_dev.
  All fail importing _overlapped with WinError 10106 under minimal environment.
  No skips or xfails added. Ubuntu CI result will be attached to the PR.
- `git diff --check`: PASS.

## Integration status and handoff

Club backend: PASS locally. Club HTTP: PASS locally with minimal club-owned
fallback templates. Canonical adult/child templates are selected first whenever
available. Fallbacks do not prove final design or browser acceptance.

Real library-service + club-HTTP smoke passes: child saves 35 of 120, replay adds
no event, finish grants first-book, guardian redeems for child, club-reader granted
once, child corner 200, revoke/expiry 403; separate adult self-reader reads and
finishes without PIN. This is not the complete demo URL flow.

Cross-module demo E2E: **BLOCKED** on library routes PR #21, adult UI PR #22,
Issue #27 (account read-route integration), and recovered child UI (reverted #24).
Those were not integrated into this branch. No tests/test_demo_flow.py exists;
no fake routes/templates or skipped demo test are used as evidence. Public app
deployment, Android/browser rehearsal and PostgreSQL concurrency: **NOT RUN**.
Issue #16 remains open. Request independent ChatGPT review; do not self-merge.
