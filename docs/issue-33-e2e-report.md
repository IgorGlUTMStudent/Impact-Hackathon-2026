# Issue #33 — real Django HTTP/DB integration evidence

Date: 2026-10-30. Executor: Igor / Codex. Scope: Django test-client integration,
not browser, PWA, PostgreSQL or public-host acceptance.

Baseline: canonical upstream/main **17197080a48edee56a727b3ec68d2de509cd2035**.
Origin is Igor's fork, whose main was older. Branch:
`feat/issue33-real-demo-e2e`. Tested implementation HEAD:
**992b84c27b1394b01c7abb9eec177319d8a62bad**. The subsequent evidence-only commit
does not alter executable code. Code + local-evidence candidate HEAD:
**fb0017e8c7ed143d0f1d3735b932ec7697f30665**. Final documentation-only submission
SHA/checks are recorded in [PR #37](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/37).
Contract: docs/issue33-e2e-contracts, documents 00 and 01.

Recon confirmed #21/#22/#29/#30/#31 integrated in main, no existing demo_flow.py,
and only the documentation contract PR #36 open. No production corrections or
cross-owner edits were necessary. Only test_demo_flow.py and this report change.

## Harness and setup provenance

Module-wide `pytest.mark.django_db(transaction=True)` avoids a surrounding test
atomic block: real redemption opens durable atomic and must not be weakened.
Tests use the configured URLconf, reverse(), real middleware/authz/services,
shared ViewModels and checked-in adult/child templates. Assertions verify the
actual owner templates rendered; no fallback template/locmem/fake route is added.

`seed_demo` sets up canonical catalog/rules and unrelated synthetic principals;
it is not run with --reset, and it supplies no events, grants or memberships.
The positive guardian starts as a synthetic Account/Reader without children/PIN.
Child creation, PIN setup, child-mode start, add, progress, finish and redemption
are real HTTP POSTs. Staff issue_code is explicitly permitted setup; no plaintext
code is reproduced here. Revocation/expiry are marked negative fixture mutations
after real activation. The adult test has no child or PIN. Security-only helpers
create principal relationships, never a successful diary write.

## Scenario-to-test index

All new tests are in `tests/test_demo_flow.py`.

| Acceptance | Test and observed HTTP/DB assertions |
|---|---|
| E33-01 | `test_guardian_child_reading_report_finish_and_real_club`: login302; family POST302 creates ChildProfile/Reader; PIN POST302 stores verified hash; start302; persisted child session; child/home200 |
| E33-02 | Same test: child catalog/detail200 with real templates; HTMX add204/HX-Redirect creates child-only entry; duplicate204 has no saved trigger; entry200 |
| E33-03 | Same: genuine rendered UUID; progress35 twice ->200/saved, stored35, one event and no grant; changed payload same UUID409 |
| E33-04 | Same: independent login POST/new session; child report/dashboard200 show35/120 and StatsVM(1,0,35,35); adult stats zero; GETs add no events |
| E33-05 | Same: new finish UUID ->200/saved; replay200/saved; another UUID422; stored finished/120, exactly one finish event and first-book grant |
| E33-06 | Same: real child achievements200 shows first-book earned, club-reader locked; nonmember corner403 |
| E33-07 | Same: real issue_code staff setup; separate adult-session redeem302/PRG and server message, no saved trigger; consumed code targets child; one active dated membership; no adult entitlement; replay422 |
| E33-08 | Same: child corner200, only published activities; exactly one club-reader; adult nonmember403; negative fixture revoke/expiry403, badge retained |
| E33-09 | `test_standalone_adult_public_catalog_to_finished_dashboard`: public catalog/detail200; anonymous add302/login, then real login/add302/progress302/finish302; DB finished120, two own events, first-book once; dashboard StatsVM(1,1,120,120); no children/PIN/foreign writes |
| N01/N02 | `test_real_security_refusals_preserve_stored_diary`: second guardian foreign report/entry/write404; real child mode blocks dashboard/family/redeem/admin302 to PIN and empty HTMX403 |
| N03/N04/N05 | Same: anonymous and actually expired database session401/HX-Redirect; invalid pages -1/121 ->422; UUID changed page or kind409; original35/event/grant counts unchanged |
| N07 | Same: CSRF-enforcing Client without token403, no changes |
| N08 | `test_lock_fault_injection_is_unsaved_with_real_authz`: negative-only narrow LockTimeout injection at library write call ->503/Retry-After/no saved trigger; entry0, zero events/grants. No injection in positive journeys. Session-expiry part is real in security test. |

Reuse existing focused coverage instead of copying all club unit tests:

- N06: `tests/test_club_views.py::test_generic_errors_persistent_fifth_sixth_and_expiry`
  proves identical invalid/used/expired422, durable counts, fifth422/sixth429 with
  Retry-After (valid code/new session), expiry and success. Foreign code targets:
  `::test_foreign_and_tampered_targets_404`; reset:
  `::test_reset_only_current_redeem_key`.
- N05 across books: `tests/test_progress.py::test_idempotency_key_covers_all_entries_for_reader`.
- N08 real file-backed lock: `tests/test_library_authz_integration.py::test_real_authz_file_backed_lock_503_and_retry`;
  unrelated DB errors: `tests/test_progress.py::test_unrelated_operational_errors_are_not_mislabeled_as_lock`
  and `tests/test_club_views.py::test_lock_mapping_does_not_mask_unrelated_db_errors`.

These run as part of the full suite on the candidate code; they are additional
focused evidence, not substituted for the new positive HTTP journey.

## Executed checks

Windows / Python3.12.16, Django5.2.18, pytest9.2.0. Commands use local .tools/uv.exe
(untracked and not part of this PR).

- `uv sync --frozen`: PASS, 14 packages checked.
- `uv run pytest tests/test_demo_flow.py -v`: **4 passed in 4.93s**, zero skips.
- `uv run pytest -rs`: **362 passed, 4 failed, 4 skipped in 123.37s** (exit1).
  Failures are unchanged Windows minimal-environment subprocess tests in
  tests/test_review_fixes.py: test_wsgi_without_settings_module_fails_closed_without_secret,
  test_wsgi_without_settings_module_starts_with_prod,
  test_wsgi_respects_explicit_settings_module, test_manage_py_still_defaults_to_dev.
  They fail importing _overlapped with WinError10106; no tests were altered or
  suppressed to hide this. New E2E passes in this full run as well.
- `uv run python manage.py check`: PASS, no issues (0 silenced).
- `uv run python manage.py makemigrations --check --dry-run`: PASS, no changes detected.
- `git diff --check`: PASS before implementation commit; repeated for evidence.
- Ubuntu/Python3.12 CI on candidate **fb0017e**: **366 passed, 4 skipped in157.50s**,
  no failures; system check and migration drift PASS. Actual workflow:
  https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41095557004
  (job124200268715). The final evidence-only HEAD also requires its own green
  check; its result will be attached to PR #37 before handoff.

Four existing skips in test_library_views.py are opt-in immutable UI snapshots
with mocked authz, not the newly integrated actual templates: two cases at line205
and one at line252 require LIBRARY_ADULT_UI_REF; one case at line205 requires
LIBRARY_CHILD_UI_REF. Variables were not configured; no new skip/xfail was added.
The new E2E verifies both checked-in owner template sets without those overrides.
The skipped cases are test_real_owner_detail_template_render_with_mocked_authz
(adult/anonymous, adult/authenticated, child/authenticated) and
test_real_adult_templates_catalog_detail_add_35_finish_with_mocked_authz (adult).
They also remain skipped in Ubuntu; none of the four new E2E tests is skipped.

## Limitations and ownership

No reproduced application defect in the new E2E tests; no owner handoff for a
code change was needed. Arsenii and Alisa's independent security/library reviews
remain separate: this executor does not self-approve or self-merge.

The existing concurrent throttle check/failure-commit gap remains documented in
club integration notes and is not changed here. Real browser/JavaScript UX,
Android PWA installation/offline behavior, PostgreSQL concurrency, public HTTPS
hosting/redeploy persistence and two-device rehearsal: **NOT RUN**.
Issues #34/#35 remain separate gates. No screenshots/recordings were produced.
Issue #33 is submitted for independent review, not marked accepted by its author.
