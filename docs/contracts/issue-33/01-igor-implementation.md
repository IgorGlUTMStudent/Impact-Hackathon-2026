# ISSUE-33 / EXECUTOR-01 — Igor: Implement real Django cross-module E2E

**Assigned executor:** Igor (Codex). **Model: gpt sol 6.1; effort: high**. Escalate to **xhigh** only for confirmed cross-module debugging blockers.
**Parent issue:** https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/33
**Canonical acceptance:** docs/contracts/issue-33/00-acceptance.md
**Expected output:** code + executed tests + report + pushed GitHub PR. This is an executable prompt, not a task-completion claim.

## Agent prompt (copy in full)

You are the integration engineer responsible for completing Issue #33. The priority is to make the **actual integrated Gustul Cărților MVP** verifiably work end-to-end on the repository's configured Django URLconf, middleware, templates and persistent test DB. Do not write an isolated demonstration or substitute fixtures for the core user journey.

### 0. Sync and reconnaissance before editing

1. Fetch origin/main, inspect the current main HEAD, the existing open PRs and Issue #33. The snapshot when this contract was written was 17197080a48edee56a727b3ec68d2de509cd2035; newer real GitHub state takes precedence. Clearly record the baseline SHA.
2. Read AGENTS.md, the current route/authorization contracts, spec.md, actual account/library/club/core views, app URLs, models, tests/conftest.py, test_account_dashboard.py, test_library_views.py, test_club_views.py, test_progress.py and test_child_mode.py. Distinguish design documents from actual current behavior.
3. Use a clean integration branch off latest origin/main, e.g. feat/issue33-real-demo-e2e; do not edit main directly, and do not overwrite anyone's worktree or uncommitted changes.
4. Discover whether an integration test/demo script has already landed since this contract. Reuse/extend evidence rather than duplicating tests.

### 1. Main deliverable

Create tests/test_demo_flow.py (new file) containing **real end-to-end HTTP integration tests** covering matrix E33-01..E33-09 from 00-acceptance.md. Use pytest-django, Django Client, reverse(), the configured app URLs, real middleware, real authz and DB, and real repo templates. Separate tests by meaningful scenario (e.g. happy family+club path, standalone adult, security/failure paths) while sharing only safe setup helpers.

Positive flow:
- Start with a synthetic guardian account; ideally exercise actual login POST and family/PIN flows at least once. Existing factories can create setup principals in tests focused on later steps but **must not manufacture the result being proved**.
- Family: create child via /familie/ HTTP POST; verify child Reader actually stored; set PIN using the real form (pin, pin_confirm, password); enter child mode via genuine POST /familie/<uuid>/mod-copil/.
- Child: GET /copil/, GET catalog/book detail, POST add-to-shelf for an active 120-page fixture book; ensure one child-owned ShelfEntry, not adult-owned or foreign.
- Save absolute page 35 through POST /raft/<entry>/progres/ with a genuine UUID. Assert stored page=35, one ProgressEvent and expected HTMX or plain-form response. Replay SAME UUID and payload: no duplicate event/grant. SAME UUID with a different page should fail 409 without a saved trigger.
- New separate Django Client that logs in as the same guardian **in adult mode**, not copied from the child session: GET /familie/<child>/ and /panou/, assert 35/120 and pages_total=35/pages_7d=35 sourced from DB. Verify GET creates no events.
- Finish with NEW request_id by HTTP POST /raft/<entry>/terminat/; assert status finished, page=120, exactly one general first-book achievement and one finish event; replay same UUID is idempotent and new UUID is rejected.
- In child mode before membership: general achievement visible, club-only club-reader locked, /clubul-meu/ returns 403.
- For setup, issue a real one-time club code through club.services.issue_code with a legitimate synthetic staff account (allowed fixture setup; avoid printing the plaintext or storing it in public evidence). Submit the code through guardian HTTP POST /club/cod/ with reader=<own child public_id>. Use a separate guardian adult-mode client or legitimate PIN exit. Assert exactly one active membership/code redemption, club-reader grant once, member-only corner 200 for child and 403 for nonmember/revoked/expired; code reuse fails.
- Separate adult reader **with no children** completes public catalog -> login -> own shelf -> progress -> finish -> own dashboard without child PIN. Assert independence of adult/child progress and entitlements.

### 2. Real response contract: don't 'fix' the app into an imaginary API

- HTMX add_to_shelf: 204 and HX-Redirect on success; only a newly created row may set HX-Trigger: saved.
- Plain add_to_shelf: 302 to shelf entry.
- HTMX progress/finish: 200 partial + HX-Trigger: saved after commit, including valid idempotent replay (which creates no new DB event).
- Plain progress/finish: redirect 302.
- Redeem: plain 302 to /club/cod/ with server-side success message; HTMX 200 with HX-Redirect and **no** HX-Trigger: saved. A code redemption MUST NOT be tested as a 'saved' diary event.
- Actual ProgressEvent uniqueness spans (reader, request_id) even across multiple books; finishing at book page_count is terminal. For a 120-page book, don't record page=120 and then try to finish with a different request_id: the terminal condition would already have been reached.
- Existing club code throttle is DB backed; its residual concurrent invalid-attempt gap is documented and **not** fixed within #33 without owner approval. Do not introduce a globally wrapping transaction around club.services.redeem_code: it explicitly forbids an enclosing atomic block.

### 3. Security/correctness gates (negative tests)

Cover E33-N01..N08 with actual routes where practicable. Confirm:
- foreign child report and foreign reader entry -> 404;
- child mode adult/staff routes -> 302 PIN gate; HTMX -> 403 empty body;
- anonymous HTMX save -> 401 HX-Redirect, no saved trigger, no writes;
- 422 out-of-range page preserving prior progress;
- 409 UUID semantic conflict preserving event count;
- failed/reused code 422; foreign child code target 404; redemption throttle sixth attempt 429 + Retry-After;
- CSRF-enforcing Django Client rejects POST without token;
- controlled lock error -> 503 and zero write (narrow fault injection permitted **only** here, clearly labeled; never in positive E2E).

Use existing focused tests where a unique negative gate is already covered, and explicitly name them in the report. Avoid swelling the test suite with trivial duplicates.

### 4. Scope and ownership restrictions

You own:
- tests/test_demo_flow.py (new), docs/issue-33-e2e-report.md (new).
- Tiny corrections to **apps/club/** and club-owned test files only if independently justified by a reproduced integration failure.
- No changes to models/migrations, config/urls.py, settings, shared authz, templates, CSS, library service logic, pyproject.toml or lockfile without a **written decision gate and named owner**.

If a failure belongs in apps/accounts/ or shared authorization, post the smallest reproducible trace to Arsenii; if in apps/library/, send to Alisa; if in templates/child/, to Denis; if in adult templates/JS, to Vladimir. Prefer a separate owner PR over cross-editing. Keep your branch focused on integration verification. Do not 'solve' missing coverage by creating a second fake URLconf or editing tests to match broken product behavior.

### 5. Execution and handoff

Run and capture actual command outputs:
- uv sync --frozen
- uv run pytest tests/test_demo_flow.py -v
- uv run pytest
- uv run python manage.py check
- uv run python manage.py makemigrations --check --dry-run
- git diff --check

If Python/uv is unavailable or Windows-specific failures occur, report the exact environment, exception, and a reproducible Linux/CI result; do not claim all green from partial runs. Never silently skip or xfail a failure. The final GitHub Actions run must be green for the final integration SHA, not an earlier branch state.

Produce docs/issue-33-e2e-report.md with:
- exact baseline and head SHAs; scenario-to-test index; each executed check and outcome, tests passed/failed/skipped;
- CI run link; screenshots or excerpts only when they genuinely exist;
- outstanding defects with owner; known limitations; real browser, PWA, Postgres and public-host proof explicitly tagged NOT RUN if not actually performed;
- no secrets, personal child data or club code plaintext.

**Immediately after implementation**, commit and push the branch to GitHub, open a PR referencing #33, include report + commands/results, and request **independent ChatGPT project-brain review**. Do not self-approve or self-merge. Await an actual independent review decision. The reviewer independently checks diff, reproducibility, security and GitHub CI; only then may the reviewer merge.

### 6. Exit conditions

- ACCEPTED: actual HTTP + DB positive E2E; negative contract proof; Ubuntu CI green on final SHA; independent review approved; no violated ownership gates.
- BLOCKED: missing real view/template/authz, service mocking for happy path, fabricated proof, unresolved P0 regression, unsafe merge or no pushed PR.
- IMPORTANT: do not mark #34 (real deployment) or #35 (phone/browser/pitch) done because #33 passes.

At the end of your response, report concise DONE / PARTIAL / BLOCKED, GitHub branch/PR link, commits, tests and any needed owner handoffs. Do not spend time on new recommendations/social feed/leaderboards, nonessential redesign or a second UI framework.


### 7. Non-negotiable pytest-django transaction setup

The real club.services.redeem_code explicitly rejects an enclosing transaction and uses atomic(durable=True). Tests covering code redemption **must use pytest.mark.django_db(transaction=True) or transactional_db**, as the existing tests/test_club_views.py and tests/test_club_redemption.py do. Default pytest.mark.django_db / db fixtures can add an outer transaction and fail even when product code is correct. Do not weaken or remove the production durable-transaction guard to make a faulty test harness pass. Clearly note this harness choice in the report.
