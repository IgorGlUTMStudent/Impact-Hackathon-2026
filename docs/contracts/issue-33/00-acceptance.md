# ISSUE-33 — Canonical acceptance contract for real cross-module E2E

- Issue: https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/33
- Contract date: 2026-10-30
- Baseline inspected: main @ 17197080a48edee56a727b3ec68d2de509cd2035
- Contract owner / independent final verifier: ChatGPT project brain
- Verification model: **gpt terra 6.1**, effort **xhigh**
- Status: **PLANNED; this contract is NOT proof that E2E passes**
- Executing owner: Igor (implementation contract 01); Arsenii and Alisa provide non-overlapping focused reviews (02 and 03).
- Previous baseline evidence: GitHub Actions run 41089432476 SUCCESS (362 passed, 4 skipped); no tests/test_demo_flow.py in inspected main. Baseline unit CI is not full integrated E2E.

## 1. Purpose and boundaries

Prove ONE realistic P0 user journey on **merged Django URLs, middleware, templates, services and database**, with no fake URLconf, ephemeral replacement templates, mocked current_reader, mocked view/service calls or manually injected successful state in the tested path.

The #33 gate is a **Django HTTP/test-client E2E integration gate**, NOT browser/device E2E. Browser + Android PWA + real user rehearsal belong to #35; actual HTTPS host / persistent deployment belongs to #34. Do not mark those tasks completed because #33 passes.

Source of truth at baseline:
- specs/001-reading-diary-mvp/contracts/routes.md
- specs/001-reading-diary-mvp/contracts/authorization.md
- specs/001-reading-diary-mvp/spec.md
- apps/accounts/urls.py; apps/library/urls.py; apps/club/urls.py; apps/core/urls.py
- tests/conftest.py (PASSWORD, PIN, HTMX, guardians/child factories)
- apps/library/services.py; apps/club/services.py
- Current runtime code and real tests override stale prose where they differ. Treat any **new** schema/API/security change as a decision gate, not a unilateral test fix.

## 2. Required positive acceptance matrix

Each item requires test name, HTTP request(s), response code/redirect, **database** assertion, and explicit source of setup data. Assertions about rendered templates alone never count.

| ID | Real scenario | Mandatory evidence |
| --- | --- | --- |
| E33-01 | Guardian signs in via POST /cont/intrare/; guardian creates a child via POST /familie/ (or use a specifically marked setup fixture for auth-only tests), sets 4–6 digit PIN via /familie/pin/, enters /familie/<child>/mod-copil/ | Account/ChildProfile/Reader relationship persisted; session uses child mode; /copil/ GET 200 |
| E33-02 | In child mode, GET /carti/, GET /carti/<book>/, POST /carti/<book>/adauga/ | Only active child's reader owns ShelfEntry; 120-page seeded/fixture book; /raft/<entry>/ GET 200 |
| E33-03 | POST /raft/<entry>/progres/ with page=35 and UUID request_id, then replay SAME payload/UUID | First saves 35/120, one ProgressEvent; replay does not add event/grant; HTMX committed response may carry HX-Trigger: saved even on replay; different payload with same UUID => 409 |
| E33-04 | **Different authenticated client/session** of same guardian GET /familie/<child>/ and /panou/ after child write | Stored current_page=35, StatsVM pages_total=35 and pages_7d=35, correct child; no reads create events. Do not clone the child session. |
| E33-05 | Child finishes the 120-page book via POST /raft/<entry>/terminat/ with NEW UUID, then replay same UUID | Finished status/pages 120; exactly one finish event and one general first-book grant; replay does not double count. A new UUID against already finished entry => 422. |
| E33-06 | Before membership, child GET /realizari/ and /clubul-meu/ | General badge earned; club-only club-reader absent/locked; club corner 403; authenticated adult/guardian status does not implicitly entitle child. |
| E33-07 | Staff issues a real one-time code via production issue_code service **in fixture setup**; guardian exits child mode using POST /parinte/ PIN or uses a legitimately separate adult session; POST /club/cod/ with reader=<own child public_id>, code=<issued plaintext> | One MembershipCode consumed and exactly one ClubMembership for child; club-reader AchievementGrant created once by real evaluate_achievements; no adult entitlement leakage; code replay => 422 (unless throttle already locked). |
| E33-08 | Child GET /clubul-meu/ and /realizari/ after redemption; separate non-member / revoked / expired reader checks | Child corner 200 and club badge earned once; published activities only; nonmember/revoked/expired corner 403. Verify revocation/expiry through fixture-specific DB setup, not as the main happy-path shortcut. |
| E33-09 | Separate adult with no children: GET catalog public, login, add book, progress, finish, GET /panou/ | Own reader stats and finished book persist; no PIN required; nothing written to another reader. |

Note: /carti/<book>/adauga/ HTMX success is 204 + HX-Redirect; plain POST typically redirects 302. Progress/finish HTMX success is a 200 partial with HX-Trigger: saved; plain POST usually redirects 302. Redeem success is normal POST 302/PRG or HTMX 200 + HX-Redirect, **without** an HX-Trigger: saved. Accept these genuine current behaviours; do not force all mutations into one response shape.

## 3. Negative/security acceptance matrix

| ID | Required check | Expected |
| --- | --- | --- |
| E33-N01 | A second guardian requests another guardian's child report, or child/other reader shelf entry by public UUID | 404; distinguish neither foreign nor unknown ID |
| E33-N02 | Child-mode session requests /panou/, /familie/, /club/cod/, /admin/ (normal and HTMX variants) | Normal redirect to PIN gate 302; HTMX refusal 403 with empty body; no data leakage |
| E33-N03 | Anonymous/expired HTMX progress POST | 401 + HX-Redirect to sign-in; no 2xx saved trigger, no DB write |
| E33-N04 | Page 121 or negative page on 120-page book | 422; original current_page, events and grants unchanged |
| E33-N05 | Reuse a progress request_id with different page, kind or entry | 409; no new event, no false saved trigger |
| E33-N06 | Invalid/redeemed/expired code, wrong target, and sixth bad redeem attempt | Generic 422 for invalid code; 404 foreign target; rate-limit 429 + Retry-After after 5 failures. Existing documented residual concurrent throttle gap is **not** claimed solved. |
| E33-N07 | CSRF-enforcing Client POST to mutation without token | 403; zero mutation |
| E33-N08 | Simulated lock-specific write failure and session expiry | 503/no trigger/no write for the former (focused test may fault-inject); 401/redirect + zero mutation for latter. Never swallow unrelated database errors. |

Test new integration paths with genuine domain logic. Focused fault injection is acceptable **only** for negative error mapping that cannot be reproduced deterministically, must be identified and separated from positive E2E tests. Existing focused tests can be cited for negative checks if rerun on the **same integrated SHA**; avoid copy-pasting all existing unit tests into the new file.

## 4. Acceptance and stop conditions

### GATE GREEN

1. tests/test_demo_flow.py exists and covers E33-01 through E33-09 by configured real URLs and DB assertions; no fake routes/temporary templates/monkeypatched core service/authz for positive journey.
2. Run exact commands on candidate HEAD: uv sync --frozen; uv run pytest tests/test_demo_flow.py -v; uv run pytest; uv run python manage.py check; uv run python manage.py makemigrations --check --dry-run; git diff --check. Report counts, exits, skipped tests and environment.
3. Ubuntu GitHub Actions for the PR's final commit/merge ref is SUCCESS. If skipped tests remain, enumerate and explain their relevance; do not silently count skips as passes.
4. No regression or undocumented schema, ownership, rate-limit or URL contract change.
5. Evidence report in docs/issue-33-e2e-report.md identifies commit SHA, exact scenario assertions, commands, CI URL and limitations.
6. Changes pushed to a dedicated GitHub branch immediately, linked PR open, and independent ChatGPT review explicitly requested. Owner must NOT self-merge; project brain independently inspects final diff, tests and CI before approving/merging.

### BLOCKED / NOT APPROVED

- A test passes only with fake authz/service/URLconf/template; tests only assert response status with no stored state; the guardian merely reuses the child's session; real club code is bypassed by inserting membership directly in the happy path; tests are skipped/xfail to get green; GitHub CI is not green; implementation hasn't been pushed.
- The actual browser/phone or persistent remote deployment is not yet tested: **#33 may be GREEN but #34/#35 remain OPEN**.

### Ownership and escalation

Igor owns the new integration test and evidence. Arsenii inspects authentication/authorization/child mode, Alisa inspects library/progress/idempotency, without parallel edits to Igor's test file. If real integration reveals cross-owner defects, document the smallest failing reproducer, open a narrowly scoped fix PR with module owner, and rerun #33 against the combined changes. Model choices and exact handoffs are in contracts 01–03.

## 5. Source of proof vs design intent

Some existing plans/quickstart/tasks.md still say NOT RUN or imply no application code exists; those are stale relative to main. Do not silently edit historical architecture records to manufacture evidence. Update the execution status in the final report only from observed checks. Partner approval for G1–G6 and production compliance is outside this contract.


## 6. Critical test harness constraint: durable redemption transactions

The current club.services.redeem_code checks that **no outer transaction is already open** and then opens transaction.atomic(durable=True). Ordinary pytest-django db fixtures / pytest.mark.django_db can wrap a test in a transaction, causing a false failure (RuntimeError: Redemption requires an outermost transaction). Any scenario containing an actual code redemption **MUST** use pytest.mark.django_db(transaction=True) / transactional_db or another harness proven not to wrap the service call in an outer transaction. Follow tests/test_club_views.py and tests/test_club_redemption.py, which already use transaction=True. Do NOT remove the production safety check or bypass redemption to accommodate a wrong test fixture. Record the fixture strategy in the E2E report.
