# ISSUE-33 / EXECUTOR-03 — Alisa: independent library/progress correctness verification

**Executor:** Alisa (Codex). **Model: gpt sol 6.1; effort: high**.
**Parent issue:** https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/33
**Canonical acceptance:** docs/contracts/issue-33/00-acceptance.md
**Mode:** read-only integration verification first, library-owned bug fixes only after reproducible evidence. Igor owns tests/test_demo_flow.py.
**Deliverable:** docs/reviews/issue-33-library.md via GitHub PR, plus a separate narrow library fix PR if needed.

## Agent prompt (copy in full)

You are the independent reviewer of the **real reading diary service and HTTP integration** for Impact Hackathon Issue #33. Igor is responsible for the new cross-module end-to-end test. Do not duplicate or overwrite his test implementation, do not create mocked substitute routes, and do not conflate an isolated library unit pass with a real guardian/child E2E pass.

### 0. Synchronize and inspect

Fetch the newest origin/main; record its commit SHA and inspect open PRs, particularly Igor's #33 implementation candidate if one exists. Read:
- docs/contracts/issue-33/00-acceptance.md;
- apps/library/models.py, services.py, stats.py, views.py, urls.py;
- apps/accounts/authz.py and middleware.py (read only);
- apps/club/services.py (read only, including evaluate_achievements);
- core/viewmodels.py and the real adult/child shelf, book-detail and progress templates;
- tests/test_progress.py, test_stats.py, test_concurrency.py, test_library_views.py, test_library_authz_integration.py, test_account_dashboard.py;
- specs/001-reading-diary-mvp/contracts/routes.md and data-model.md.

Actual committed runtime code takes precedence over stale task checkboxes or quickstart descriptions.

### 1. Required independent verification

L33-01. Real catalog/list/detail:
- anonymous catalog and active book details work;
- inactive book does not permit add;
- adult and active-child server-selected reader cannot be replaced by browser-supplied reader, guardian or child identifiers;
- POST /carti/<book>/adauga/ creates one ShelfEntry for current Reader, and a duplicate add stays idempotent.

L33-02. Persisted progress at 35/120:
- POST /raft/<entry>/progres/ with page=35 and UUID request_id;
- current_page=35 in DB, one genuine ProgressEvent, child owner isolation, appropriate 2xx/redirect depending on HTMX/plain mode;
- same reader + same request_id + same semantic payload is replay-safe (no extra event/grant);
- same UUID reused with different page, book entry or event kind returns 409 without a success trigger;
- invalid page (<0 or >120) and invalid UUID return 422, do not mutate persisted state. Check current implementation for rejected payload type handling without changing service contracts.

L33-03. Stats and guardian read:
- a different authenticated guardian **session for the same account** sees the child's real 35/120 and pages_total/pages_7d=35;
- the unrelated adult self-reader totals stay independent;
- GET reads are side-effect free and cross-guardian child report is 404;
- note that StatsVM pages_total is current stored shelf totals, not necessarily sum of every ProgressEvent.

L33-04. Finish and achievements:
- finish_book with new UUID sets current_page=120 and finished state exactly once;
- retry with **identical** UUID is idempotent; new UUID after finishing is 422;
- club.services.evaluate_achievements runs as real integration side-effect;
- non-member finishing can earn general first-book but **not** club-reader; after real membership redemption club-only grant may be evaluated once.
- Preserve transaction ordering and no false HX-Trigger: saved after failed write.

L33-05. Error handling and contention:
- 401 HTMX expired/anonymous mutation has HX-Redirect and no success partial;
- 403 child-mode attempt on adult-only URL (coordinate with Arsenii);
- 404 on a foreign entry and unknown UUID;
- 503 lock-specific DB busy maps to unsaved, no partial update;
- 422 validation partial is eligible for 422-only client swap, but do not change general HTMX swap policy;
- no positive-flow tests may inject fake authz/club services.

### 2. Critical response nuances (existing API)

- Plain add -> 302; HTMX add -> 204 HX-Redirect, HX-Trigger: saved only if new row created.
- Plain progress/finish -> 302; HTMX progress/finish -> 200 partial, HX-Trigger: saved only after success/committed replay (not on 4xx/5xx).
- Finishing at exactly page_count by a progress write already makes entry terminal. For test "progress 35 -> finish", do NOT first save page 120 with an unrelated request_id.
- UUID uniqueness spans the reader across **all** shelf entries, not just one book.
- Do not replace atomic writes with test-only shortcuts or discard PostgreSQL-safe reader locking to silence tests.

### 3. Ownership and tests

Scope of your potential fixes: apps/library/services.py, stats.py, views.py, urls.py and library-specific tests. **No** changes to shared models/migrations, apps/accounts, apps/club, templates, middleware, config or tests/test_demo_flow.py without an explicit decision gate and coordination with owner.

Run focused suite (only the files that actually exist), the complete suite, Django check and migration drift:
- uv sync --frozen
- uv run pytest tests/test_progress.py tests/test_stats.py tests/test_concurrency.py tests/test_library_views.py tests/test_library_authz_integration.py -v
- uv run pytest
- uv run python manage.py check
- uv run python manage.py makemigrations --check --dry-run
- git diff --check

If a new failing test is warranted, reproduce the defect before implementing the minimal correction; use real DB + URLconf. Report the environment and exact counts, including skips or Windows-specific issues. If Igor's PR is live, review and rerun on the fully integrated candidate, rather than concluding solely from an older main.

### 4. GitHub handoff

Publish docs/reviews/issue-33-library.md with a table L33-01..L33-05: PASS/FAIL/NOT RUN, path to exact tests and commands, PR/head SHA, scenario and HTTP/DB evidence, and critical limitations. If no code change is needed, push report alone on review/issue33-library and open a doc PR referencing #33. If code fix is needed, use a separate small library-only PR and notify Igor of the prerequisite.

**Immediately push all work to GitHub**, include exact tested SHA and outcomes, and request **independent ChatGPT project-brain review**. You do not approve or merge your own PR. The project brain independently reviews test truthfulness, diff and final Ubuntu CI before merge.

Return final DONE / PARTIAL / BLOCKED, report/PR link, actionable issues and whether Igor's E2E must be rerun. Do not build P1 features, new UI, recommendations, rankings or separate club entitlements.
