# Issue #33 — independent authorization / child-mode verification

Date: 2026-10-30. Executor: Vladimir / Antigravity agent (GLM 5.3 Flash, effort max), role:
security/authorization reviewer for contract 02. This is an independent audit of the merged
authorization surface plus Igor's PR #37 E2E candidate; it is not self-approval and not a
browser/production certification. Final acceptance belongs to the ChatGPT project-brain reviewer.

## 1. Executive verdict

**PASS — no authorization defect reproduced.** All matrix cells A01–A12 were exercised on the exact
PR #37 head by real Django test-client HTTP + DB checks (existing suites + 7 narrow audit probes).
One minor robustness finding (P2, fail-closed 500, not reachable through the app's own HTTP surface)
and one Windows-only environment block were found. Neither blocks the gate.

- `MERGE_GATE_37: READY_FOR_INDEPENDENT_REVIEW` (from the authorization standpoint).
- Merge/close decisions for PR #37 and Issue #33 stay with the ChatGPT reviewer; this executor does
  not merge, approve or close anything.
- The only file changed by this submission is this report, on branch `review/issue33-vladimir-authz`.

## 2. SHA ledger

| Ref | SHA | Note |
| --- | --- | --- |
| `origin/main` at review time | `5e6b645961baeafb7d532b589c770d59e8d303fb` | includes merged #38; local stale `main` was not used |
| Tested Igor PR #37 head | `c2f7e56eedede107a195c6bd78b3c99cc59a836b` | verified three ways: `git fetch … refs/pull/37/head` → `git rev-parse FETCH_HEAD`; `gh pr view 37` `headRefOid`; CI run headSha (see §4) |
| PR #36 head (acceptance oracle `docs/contracts/issue-33/00-acceptance.md`) | `338a0c14e84f0d96c72fdddd15de8d82112036e6` | PR #36 was still OPEN at review time; the oracle was read from its head ref, not from main |
| This report branch | `review/issue33-vladimir-authz` (branched from `5e6b645…`) | branch SHA recorded on the GitHub PR |

Audited candidate delta vs main: `tests/test_demo_flow.py` (+273) and `docs/issue-33-e2e-report.md`
(+115) only. The authorization code itself (`apps/accounts/…`, middleware, contracts) is already on
main and was audited where it lives.

GitHub state checks performed before testing: PR #38 is **MERGED** (merge commit
`5e6b6459…`, 2026-10-30T18:00:37Z) and its diff touches only
`docs/reviews/issue-33-library.md` — no review was issued for implementing new tests; Issue #33 is
OPEN; PR #37 is OPEN/draft, mergeable.

## 3. A01–A12 verification matrix

Every row below was executed on `c2f7e56…` (Windows, see §4) with the real URLconf, middleware,
`apps/accounts/authz.py`, services and templates. "Probe" = `tests/probe_issue33_authz.py`, a
temporary read-only-worktree file created for this audit (not committed, not part of PR #37); it
contains no mocks and no redemption, so no durable-transaction harness is involved.

| ID | Verdict | Evidence (executed) | Observation (HTTP → DB) |
| --- | --- | --- | --- |
| A01 identity | PASS | `tests/test_demo_flow.py::test_guardian_child_reading_report_finish_and_real_club` (E33-01); `tests/test_child_mode.py::test_start_sets_session_and_goes_to_child_home` | POST `/cont/intrare/` 302; POST `/familie/` 302 → `ChildProfile` + `Reader(kind=CHILD)` persisted, `reader.account_id IS NULL`; POST `/familie/pin/` 302 with password re-auth, `check_password(PIN, guardian.pin_hash)` true in DB; POST `/familie/<child>/mod-copil/` 302 → `/copil/`; GET `/copil/` 200 `child/home.html`; session `mode == "child"`, `active_child == str(child.public_id)` |
| A02 ownership / IDOR | PASS | E33-N01..05 in `test_demo_flow.py`; `test_family.py::test_foreign_child_is_404_for_every_family_mutation`; `test_account_dashboard.py::test_foreign_and_unknown_child_are_identical_404`; `test_child_mode.py::test_start_for_foreign_child_is_404`; probe `test_a02_child_mode_foreign_entry_is_404_no_write` | Foreign guardian: GET `/familie/<child>/` 404, GET `/raft/<entry>/` 404, POST `/raft/<entry>/progres/` 404 (HTMX, no `HX-Trigger`); family rename/delete/mod-copil on foreign child all 404 with zero mutations; foreign and unknown UUID indistinguishable. In child mode, foreign shelf entry GET 404 / progress POST 404, `foreign_entry.current_page == 0`, `ProgressEvent.objects.count() == 0` |
| A03 reader binding | PASS | `ChildForm` fields exclude `guardian` (forms.py:40-42); `test_account_dashboard.py::test_dashboard_lists_only_own_children_and_ignores_forged_params`; `test_club_views.py::test_foreign_and_tampered_targets_404`; probes `test_a03_forged_guardian_param_on_family_create_is_ignored`, `test_a03_forged_reader_param_on_progress_is_ignored` | POST `/familie/` with `guardian=<other account pk>` ignored: `child.guardian_id == session guardian`. POST progress with `reader=<foreign reader public_id>` ignored: own entry 35, foreign entry stays 0, `ProgressEvent.reader_id` = own child reader only. Server identity always from `request.user`/session (`authz.current_reader`, `get_child_for_guardian`, club service re-validates ownership inside its durable transaction) |
| A04 child deny-default | PASS | E33-N02 in `test_demo_flow.py`; `test_child_mode.py::test_adult_urls_redirect_to_pin_gate`, `::test_adult_urls_via_htmx_are_403_without_partial`, `::test_new_unlisted_route_is_denied_by_default`; probe `test_a04_unknown_path_in_child_mode_denied_by_default` | Child session GET `/panou/`, `/familie/`, `/club/cod/`, `/admin/` → 302 → `/parinte/`; same URLs with `HX-Request: true` → 403, empty body, no `HX-Trigger: saved`. Unlisted new route and unresolved path (`/eto-ne-suschestvuet/`) → 302/403-empty (middleware matches view names, `Resolver404` → deny) |
| A05 tampered session | PASS | `test_authz.py::test_child_mode_with_foreign_child_fails_closed`, `::test_child_mode_with_missing_or_bad_child_fails_closed`, `::test_deleted_child_fails_closed_never_adult_reader`; `test_child_mode.py::test_deleted_child_leaves_only_pin_gate_and_logout`; `test_account_dashboard.py::test_deleted_or_foreign_active_child_stays_denied`; `test_club_views.py::test_changed_guardian_session_fails_closed`; probe `test_a05_foreign_active_child_only_pin_gate_and_logout` | Session with `active_child` = foreign/missing/garbage UUID or deleted child: `/copil/`, `/raft/`, `/carti/`, `/realizari/` → 302 to PIN gate; HTMX → 403 empty; only `/parinte/` (200) and POST `/cont/iesire/` (302, session ends) remain; no fallback to the adult reader anywhere |
| A06 PIN lifecycle | PASS + P2 finding | `test_child_mode.py::test_pin_wrong_counts`, `::test_pin_lockout_after_5_and_correct_pin_refused_while_locked`, `::test_pin_lock_is_per_account_not_per_session`, `::test_pin_lock_expires`, `::test_correct_pin_exits_child_mode`; probe `test_a06_child_mode_without_pin_hash_fails_closed` | Wrong PIN → 422 "PIN greșit"; 5 failures → 6th attempt (even correct PIN) → 429; lock persists across sessions (per-account `Throttle(scope="pin")`, key SHA-256-hashed); after lock expiry correct PIN → 302, throttle row deleted. **P2 finding F-1 below:** `pin_gate` POST when `pin_hash IS NULL` raises `TypeError` (500, fail-closed) instead of 422 |
| A07 logout/recovery | PASS | `test_child_mode.py::test_logout_recovery_ends_session` | With the PIN gate locked: GET `/cont/iesire/` → 405 (POST-only, no bypass); POST logout → 302 `/cont/intrare/`, session holds neither `_auth_user_id` nor `mode`; `/familie/` then redirects to login; the adult session is only restored by a fresh POST login with email+password (the PIN lock itself stays until expiry). Django `LogoutView` flushes the whole session — child mode cannot survive into a new adult session |
| A08 login throttling | PASS | `tests/test_login_throttle.py` (14 tests, all executed): `::test_wrong_password_is_422_generic`, `::test_unknown_email_same_response`, `::test_sixth_attempt_locked_even_if_correct`, `::test_lock_survives_new_session_and_case_variants`, `::test_unknown_email_is_locked_too`, `::test_other_email_unaffected`, `::test_success_resets_counter`, `::test_lock_expires_after_15_min`, `::test_failures_outside_window_do_not_add_up`, `::test_key_is_stored_hashed`, `::test_scopes_are_independent`, `::test_record_failure_refuses_to_run_inside_a_caller_transaction` | Wrong password and unknown email → identical generic 422 (no account enumeration); 5 failures/15 min → 429 even with the correct password; lock survives new session and email case variants; other emails unaffected; success resets; keys stored only as SHA-256 (`login:<email>`), scopes independent |
| A09 expiry / HTMX | PASS | E33-N08 (expired-session leg) in `test_demo_flow.py`; `test_child_mode.py::test_htmx_mutation_without_session_is_401_no_partial`, `::test_htmx_mutation_after_session_expiry_stores_nothing`, `::test_normal_request_without_session_redirects_to_login` | Expired/anonymous HTMX POST `/raft/<entry>/progres/` → 401 + `HX-Redirect: /cont/intrare/?next=…`, empty body, no `HX-Trigger: saved`; `entry.current_page` unchanged (35), `ProgressEvent`/`AchievementGrant` counts unchanged; non-HTMX → 302 to login |
| A10 CSRF / method | PASS | E33-N07 in `test_demo_flow.py` (`Client(enforce_csrf_checks=True)`); `test_child_mode.py::test_csrf_failure_is_403`; `test_club_views.py::test_csrf_and_expired_session`; `test_account_dashboard.py::test_writes_are_405`; `test_family.py::test_family_mutations_require_post`; `test_child_mode.py::test_start_requires_post`; probe `test_a10_get_on_post_only_routes_never_mutates` | CSRF-enforcing POST without token → 403 with zero persisted mutations (entry page, child nickname, membership all unchanged). GET on POST-only `record_progress`/`finish_book` → 405 (no mutation: `current_page == 0`, `status == reading`, no events); family mutations in child mode are denied by the middleware (302 to gate) before any handler runs |
| A11 club target | PASS | `test_club_views.py::test_target_resolution_prg_and_htmx`, `::test_foreign_and_tampered_targets_404`, `::test_child_mode_denies_redeem_and_revalidates_session`; E33-07 in `test_demo_flow.py` | POST `/club/cod/` `reader=<own child public_id>` → one `ClubMembership` for the child reader only, adult `is_member` false; `reader=self` → adult reader. `reader=` foreign-child-UUID / Reader-UUID / unknown UUID / garbage → all 404, `ClubMembership.objects.exists()` false, **no `Throttle` rows written for 404 targets**; service-level `redeem_code(actor, foreign_reader, …)` raises `Http404` even with a tampered in-memory instance (ownership re-read in-transaction). Child mode cannot open or POST `/club/cod/` at all (302/403-empty); after the child is deleted even `/realizari/` closes (302) |
| A12 club throttle | PASS | `test_club_views.py::test_generic_errors_persistent_fifth_sixth_and_expiry`, `::test_reset_only_current_redeem_key`; `tests/test_club_redemption.py::test_single_use_and_committed_failure` (executed on the same SHA in the full suite) | Invalid/used/expired codes give one generic 422 ("Cod invalid sau expirat"); 5 failures → 429 + `Retry-After`, persisted across a new session; failure counter is per-account (`str(account.pk)` hashed) and committed in its own durable transaction so a later rollback cannot erase it; lock expiry re-arms the window |

**Special accent — can any session/guardian/reader parameter become a trust source?** No. Verified by
reading the executed code paths and by the A03/A11 evidence: every resolver derives identity from
`request.user` plus guardian-scoped DB queries (`apps/accounts/authz.py:54-92`); `ChildForm` and
`RenameChildForm` whitelist fields so a posted `guardian` is ignored; `redeem_code` re-validates
reader ownership inside its `atomic(durable=True)` block (`apps/club/services.py:92-99`); UI hiding
is never the only control (the middleware allow-list is name-based and deny-by-default,
`apps/accounts/middleware.py:9-43`).

## 4. Executed commands and raw outcomes

Environment: Windows 11 (win32 10.0.26300 x64), Git Bash shell, uv 0.11.24, Python 3.12.13
(uv-managed CPython), Django 5.2.18, pytest 9.2.0, pytest-django 4.14.0, settings
`config.settings.dev`. Checkout: detached worktree at `c2f7e56…`, `git status` clean before runs.

| # | Command | Exit | Result |
| --- | --- | --- | --- |
| 1 | `uv sync --frozen` | 0 | locked deps installed (Django 5.2.18, pytest 9.2.0, …) |
| 2 | `uv run pytest tests/test_authz.py tests/test_child_mode.py tests/test_login_throttle.py tests/test_family.py tests/test_account_dashboard.py -v` | 0 | **112 passed** in 304.15 s |
| 3 | `uv run pytest tests/test_demo_flow.py -v` | 0 | **4 passed** in 20.42 s |
| 4 | `uv run pytest tests/test_club_views.py -v` | 0 | **13 passed** in 19.67 s |
| 5 | `uv run pytest -rs` | 1 | **4 failed, 362 passed, 4 skipped** in 528.28 s — see F-2 (environment block, not claimed as local green) |
| 6 | `uv run pytest tests/probe_issue33_authz.py -v` (temporary audit probes) | 0 | **7 passed** in ~27 s (first iteration exposed probe-side mistakes and finding F-1; final run documented) |
| 7 | `uv run python manage.py check` | 0 | "System check identified no issues (0 silenced)." |
| 8 | `uv run python manage.py makemigrations --check --dry-run` | 0 | "No changes detected." |
| 9 | `git diff --check` | 0 | clean (no whitespace errors) |

Official CI for the tested SHA: **SUCCESS**,
[run 41096122407 / job 124202216925](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41096122407/job/124202216925),
`headSha c2f7e56eedede107a195c6bd78b3c99cc59a836b`, Ubuntu log line:
`366 passed, 4 skipped in 95.02s`. The four locally failing subprocess tests pass there
(362 + 4 = 366), confirming the Windows classification in F-2.

Skips (identical in CI and locally, enumerated per the gate rule): 4 × `tests/test_library_views.py`
(`SKIPPED [2] :205` and `[1] :252`) — `LIBRARY_ADULT_UI_REF` / `LIBRARY_CHILD_UI_REF` not
configured; real owner-UI integration NOT RUN. They are UI-integration gates, not authorization
gates.

## 5. Findings

### F-1 (P2, robustness — no bypass, no leak): PIN gate 500 when `pin_hash` is NULL

- Path: `apps/accounts/views.py:242` — `pin_gate` POST calls
  `check_password(form.cleaned_data["pin"], request.user.pin_hash)`; Django 5.2's
  `check_password` → `verify_password` → `identify_hasher(None)` raises
  `TypeError: object of type 'NoneType' has no len()` → HTTP 500 instead of the contract's 422.
- Minimal reproduction (executed): `tests/probe_issue33_authz.py::test_a06_child_mode_without_pin_hash_fails_closed`
  — `Account` with `pin_hash=None`, session forged to `mode="child"` + own child's
  `active_child`, POST `/parinte/ {"pin": "2468"}` → `TypeError` (500 under DEBUG=False).
- Reachability: **not reachable through the app's own HTTP surface.** `child_mode_start`
  (`apps/accounts/views.py:221-222`) refuses entry without `pin_hash`; nothing in the app unsets
  `pin_hash`; `AccountAdmin` deliberately omits `pin_hash` from all fieldsets
  (`apps/accounts/admin.py:14-22`). Observing the 500 requires a directly edited DB row or a forged
  session — and the outcome is fail-closed: no exit, no data, POST logout still works.
- Risk assessment: availability/robustness nuisance in an unreachable-by-HTTP state; **not** an
  authorization bypass, so it does not block the gate.
- Suggested follow-up (owner: Igor, apps/accounts): treat an empty `pin_hash` as a wrong-PIN 422
  (or clear child mode) in `pin_gate`, plus a one-line regression test. Deliberately **not** fixed
  in this review per contract boundaries (§7 of the issue brief: P0 in `apps/accounts` only would
  warrant a fix PR).

### F-2 (ENV BLOCKED, Windows-only, no project defect): 4 subprocess tests fail locally

`tests/test_review_fixes.py` — `test_wsgi_without_settings_module_fails_closed_without_secret`,
`test_wsgi_without_settings_module_starts_with_prod`, `test_wsgi_respects_explicit_settings_module`,
`test_manage_py_still_defaults_to_dev` — fail on this Windows box: the tests spawn
`python manage.py` / wsgi subprocesses and their reader threads die with
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xcd …` (Windows console code page decoding of
subprocess output; same class of failure as the previously observed WinError 10106 on this file).
No test was disabled or edited. The official Ubuntu CI run on the same SHA passes all four
(`366 passed, 4 skipped`), so they are classified **ENV BLOCKED**, not failures of the project.

### Otherwise

No actionable authorization finding reproduced. In particular: no IDOR on child reports, shelf
entries, family mutations, club redemption or progress writes; no child-mode escape; no PIN/login
throttle bypass; no CSRF or method-level mutation; no account enumeration via login or redemption
responses; no forged-parameter trust anywhere in the audited routes.

## 6. Boundaries (what this review does NOT certify)

- Django test-client HTTP only. No real browser, no PWA install/service-worker behaviour, no
  mascot/JS UX (#35 stays open).
- No production PostgreSQL, no remote HTTPS host, no reverse proxy/Cookie `Secure`/`__Host-`
  deployment checks (#34 stays open). `select_for_update`/durable-transaction semantics were not
  independently re-verified against PostgreSQL locally (existing concurrency tests + CI only).
- Static analysis of templates/JS (`static/js/app.js` HTMX error handling) was not performed; UI-side
  correctness of "saved" toast gating is out of scope here.
- Synthetic accounts and data only; no real emails, PINs, passwords, session cookies, token hashes
  or codes are published in this report.
- A passing test-client matrix is not a production security certification.

## 7. Handoff

- **ChatGPT (project brain)**: independent review of this report, PR #37 (`c2f7e56…`) and the GitHub
  evidence; decide the #33 merge gate. This executor's model (GLM 5.3 Flash) is explicitly **not**
  the independent final reviewer.
- **Igor**: optional P2 follow-up PR for F-1 (`pin_gate` `pin_hash=None` → clean 422 + regression
  test); no changes requested to PR #37's tests, branch or report.
- **Gate status**: A01–A12 all PASS on the tested SHA; PR #37 is READY_FOR_INDEPENDENT_REVIEW from
  the authorization standpoint. Issue #33, #34, #35 remain open until their own gates close.
