# Issue #33 — library/progress correctness verification

Date: 2026-10-30. Executor: Alisa / Codex, library owner. This is an independent
execution/review of the integrated candidate, not self-approval of earlier library
PRs or of Issue #33. Final acceptance belongs to the ChatGPT project-brain reviewer.

## Scope, refs and conclusion

- Baseline merged main: `17197080a48edee56a727b3ec68d2de509cd2035`.
- Canonical acceptance read from PR #36, contract ref
  `5b33839484dac4ac35290988fc2b41af1e37568c`,
  `docs/contracts/issue-33/00-acceptance.md`. It was not yet in main during this run.
- Igor's [PR #37](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/37)
  full-local-suite candidate: `fb0017e8c7ed143d0f1d3735b932ec7697f30665`, fetched through
  `refs/pull/37/head` (the source branch is in his fork). Executable test commit:
  `992b84c27b1394b01c7abb9eec177319d8a62bad`.
- Final reviewed candidate: `c2f7e56eedede107a195c6bd78b3c99cc59a836b`.
  Its only change from fb0017e8 is 13 added / 4 removed evidence-document lines.
  `git diff --exit-code fb0017e8..c2f7e56 -- apps config templates static tests pyproject.toml uv.lock`
  returned 0. E2E/focused/system/schema checks were rerun at that exact final head;
  no redundant local full-suite rerun is claimed for the evidence-only revision.
- Candidate differs from baseline only in `tests/test_demo_flow.py` and
  `docs/issue-33-e2e-report.md`. Both were read; neither was edited by this review.
- **No reproducible library application defect found; no library fix PR needed.**
  This submission changes this report only, on `review/issue33-library`.
- Library L33-01..05 verification passes with the execution/environment caveats
  below. A local full-suite pass is NOT claimed. No approval/merge of #37 or closure
  of #33/#34/#35 is performed by this executor.

## Evidence provenance and harness

The required existing library tests were run on both refs. Some existing route
tests use scoped `views.authz` doubles and locmem templates; those passes are unit
evidence only. `test_library_authz_integration.py` uses real authz/middleware with
locmem library rendering, so it is backend security evidence, not final UI proof.

Actual merged-template evidence comes from Igor's four candidate tests and the
separate library-focused console probe reproduced in the appendix. The probe uses
the configured URLconf, real adult/child templates, actual authz/middleware and
library/club services, `Client(enforce_csrf_checks=True)`, and a migrated disposable
file-backed SQLite DB. No route/template/service/authz replacement occurs. It was
executed successfully on baseline AND candidate. It is review-only code, not an
alternate checked-in `test_demo_flow.py` implementation.

Probe setup creates synthetic account/readers, catalog metadata and two rule
definitions. Child creation, PIN configuration, child mode, add/progress/finish
and code redemption are actual HTTP writes. Staff `issue_code` is the explicitly
permitted setup path; no membership/grant is inserted to fake a happy path. No
plaintext issued code or real user data appears in this report.

There is no enclosing transaction around the console probe. Igor's module uses
`pytest.mark.django_db(transaction=True)`. Both satisfy real redemption's outermost
durable-transaction requirement without changing production safeguards.

## Library acceptance matrix

Paths below identify exact tests at final candidate `c2f7e56` (identical executable
sources to fb0017e8); `probe` means the reproducible appendix, run against those
candidate sources and against baseline.

| ID | Result | Scenario and actual HTTP/DB evidence | Exact test/probe source |
|---|---|---|---|
| L33-01 | PASS | Anonymous catalog/detail 200; real adult/child detail selection; inactive detail/add 404. Child add ignores forged reader/guardian/child identifiers, writes only the active child's shelf. First HTMX add 204 + HX-Redirect + saved; duplicate 204 has no saved trigger, one row; normal duplicate 302. Adult authority isolation is also exercised through actual authz. | Probe L33-01; `tests/test_demo_flow.py::test_guardian_child_reading_report_finish_and_real_club`; `::test_standalone_adult_public_catalog_to_finished_dashboard`; `tests/test_library_authz_integration.py::test_adult_ignores_submitted_authority_and_keeps_shelf_private` (locmem rendering disclosed). |
| L33-02 | PASS | Page 35/120 persisted; one event `(from_page=0,to_page=35,reader=active child)`. Replay with semantic page `035` adds no event/grant. Same reader UUID with another page, entry or kind returns 409/no saved/no mutation. -1/121/non-numeric/decimal page and invalid UUID return 422; request UUID remains unchanged on 422. Plain progress replay returns 302. | Probe L33-02 including HTTP cross-entry conflict; candidate guardian/child test; `tests/test_progress.py::test_idempotency_key_covers_all_entries_for_reader`, `::test_invalid_page_has_no_writes`, `::test_invalid_request_id_has_no_writes`, `::test_stale_entry_cannot_supply_from_page`. |
| L33-03 | PASS | A distinct login/client/session for the same guardian reads the real child report at 35/120, pages_total=35 and pages_7d=35; own adult total remains 0. GET report/dashboard leave captured domain rows unchanged; unrelated guardian report/entry is 404. | Probe L33-03; candidate guardian/child test; `tests/test_account_dashboard.py::test_child_progress_is_visible_from_another_guardian_session` and `::test_foreign_and_unknown_child_are_identical_404` independently rerun in the 26-test follow-up. |
| L33-04 | PASS | Fresh finish UUID -> 200/saved, terminal page120/status/finished_at, one finish event and one first-book grant. Identical UUID replays (HTMX200/plain302); another UUID gets422. Nonmember has no club-reader and corner403. Real staff-issued code redeemed by the independent adult session ->302, consumed code, one child membership and club-reader grant; code replay422; child corner200, adult nonmember403. | Probe L33-04; candidate `test_guardian_child_reading_report_finish_and_real_club`; `tests/test_progress.py::test_finish_is_terminal_but_original_payload_replays`, `::test_progress_to_last_page_finishes_and_replays`; candidate `test_standalone_adult_public_catalog_to_finished_dashboard`. |
| L33-05 | PASS, full-run caveat | Real anonymous/expired HTMX ->401 + HX-Redirect/empty body; child adult-route ->403/empty; foreign/unknown entry404; strict CSRF403. Errors never emit saved. Real file-backed progress/add lock503 leaves no partial write, retry/replay succeeds. Source/Node checks preserve 422-only swap; no browser event-loop claim. One baseline full run had an extra harness timeout, detailed below. | Probe L33-05; `tests/test_library_authz_integration.py::test_real_authz_file_backed_lock_503_and_retry`; `tests/test_concurrency.py`; `tests/test_progress.py::test_unrelated_operational_errors_are_not_mislabeled_as_lock`; candidate `test_real_security_refusals_preserve_stored_diary` and separate negative-only `test_lock_fault_injection_is_unsaved_with_real_authz`; `tests/test_child_ui.py::test_node_child_js_runner`. |

`pages_total` is SUM of currently stored shelf pages, not event-history deltas.
The positive-delta/7-day-window/correction behavior is separately verified by
`tests/test_stats.py::test_stats_empty_history_positive_deltas_replay_finish_and_isolation`
and `::test_seven_day_boundary_and_multiple_shelf_entries`.

Read-only assertions concern shelf/event/grant/membership/reader domain state for
the provisioned readers. They do not claim the session backend never refreshes a
session on GET. The temporary second shelf entry used for cross-book UUID conflict
is created after the guardian's exact StatsVM(1,0,35,35) observation.

## Commands and actual results

Environment: Windows, Python 3.12.10, Django 5.2.18, pytest 9.2.0 / pytest-django
4.14.0, frozen uv dependencies. SQLite uses the committed IMMEDIATE/5-second
settings. No shared schema, app code, UI, settings or test file was changed.
JUnit outputs are ignored local artifacts, not extra source changes.

Common focused command:

```powershell
uv sync --frozen
uv run pytest tests/test_progress.py tests/test_stats.py tests/test_concurrency.py tests/test_library_views.py tests/test_library_authz_integration.py -v
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
git diff --check
```

Actual pytest invocations added `--junitxml=.venv/<report>.xml` for counts, and
full runs used `--tb=no` without suppressing tests. Exact report basenames/results:

| Ref | Command / local report | Actual result |
|---|---|---|
| baseline 1719708 | `uv sync --frozen` | 14 packages checked in 2ms |
| baseline 1719708 | common focused command; `issue33-library-focused.xml` | 90 passed, 4 skipped in 27.48s |
| baseline 1719708 | full suite; `issue33-library-full.xml` | 357 passed, 5 failed, 4 skipped in 608.32s; NOT green |
| baseline 1719708 | `uv run pytest tests/test_concurrency.py::test_reused_request_id_with_other_page_is_conflict -v --tb=short` | 1 passed in 1.21s |
| baseline 1719708 | `uv run pytest tests/test_account_dashboard.py tests/test_concurrency.py -v --tb=short --junitxml=.venv/issue33-library-followup.xml` | 26 passed in 23.81s |
| candidate fb0017e8 | `uv sync --frozen` | 14 packages checked in 1ms |
| candidate fb0017e8 | `uv run pytest tests/test_demo_flow.py -v --junitxml=.venv/issue33-candidate-e2e.xml` | 4 passed in 7.32s; no skip |
| candidate fb0017e8 | common focused command; `issue33-candidate-focused.xml` | 90 passed, 4 skipped in 23.57s |
| candidate fb0017e8 | full suite; `issue33-candidate-full.xml` | 362 passed, 4 failed, 4 skipped in 543.45s; only the four existing Windows subprocess checks failed |
| final c2f7e56 | `uv run pytest tests/test_demo_flow.py -v --junitxml=.venv/issue33-final-e2e.xml` | 4 passed in 8.22s; no skip |
| final c2f7e56 | common focused command; `issue33-final-focused.xml` | 90 passed, 4 skipped in 24.69s |
| both refs | `uv run python .venv/issue33_library_probe.py` | exit 0; L33-01..05 JSON results PASS; genuine templates/services and strict CSRF |
| baseline, fb0017e8 and final c2f7e56 | Django check / migration drift / diff check | No issues (0 silenced) / No changes detected / clean; exit 0 |

### Full-run failures and skipped tests

The baseline full run's fifth failure was
`tests/test_concurrency.py::test_reused_request_id_with_other_page_is_conflict`:
`subprocess.TimeoutExpired`, including the anomalous text
`timed out after -369.5 seconds`. This was a child-process harness timeout, not a
failed event/order/conflict assertion. It passed in the initial 90-test focused
run, in isolation, and in the subsequent complete concurrency/dashboard run.
Root cause of that local timing anomaly is NOT established; no production lock
guarantee or timeout assertion was weakened to hide it.
It did not recur in the candidate full run, the candidate/final focused runs or
the full Ubuntu runs. This is not evidence that its runner root cause was fixed.

The other four baseline failures are unchanged M0 subprocess checks in
`tests/test_review_fixes.py`: `test_wsgi_without_settings_module_fails_closed_without_secret`,
`test_wsgi_without_settings_module_starts_with_prod`,
`test_wsgi_respects_explicit_settings_module`, and `test_manage_py_still_defaults_to_dev`.
The latter three directly show `_overlapped` / WinError10106; the first fails its
expected ImproperlyConfigured assertion with condensed subprocess stderr. These
four checks also fail in the prior Windows executor runs and pass in Ubuntu CI.
No local full-suite PASS is inferred from selective reruns.

All four skips are pre-existing optional immutable UI-snapshot cases in
`tests/test_library_views.py` (LIBRARY_ADULT_UI_REF / LIBRARY_CHILD_UI_REF unset).
They are unit-style snapshot checks. Igor's new four E2E tests use actual checked-in
adult/child templates without those overrides or skips. The skipped snapshot tests
are not counted as positive integration evidence.

### Verified Ubuntu CI, kept separate from local execution

- Baseline main [41089432476](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41089432476),
  exact SHA1719708: **362 passed, 4 skipped in 148.99s**, Django/schema checks PASS.
- Igor candidate [41095557004](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41095557004),
  exact SHAfb0017e8: **366 passed, 4 skipped in 157.50s**, Django/schema checks PASS.
  Head/SHA and log summaries were independently read through GitHub CLI.
- Final head [41096122407](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41096122407),
  exact SHAc2f7e56: **366 passed, 4 skipped in 95.02s**, Django/schema checks PASS.
- This report-only PR's CI is tracked in its PR description. It is based on main
  and does not include Igor's unmerged test file; its CI must not be mislabeled
  as a second candidate E2E run.

## Candidate review and handoff

Reviewed `tests/test_demo_flow.py`: real configured routes, actual owner templates,
real DB assertions and distinct guardian login/session are present. It uses
transaction=True for durable redemption. The only patched service call is inside
the explicitly negative lock-fault test; there is no injected happy-path success.
Normal adult self-reader flow, code activation, one-time grants, revoked/expired
membership denial and no child-to-adult authority leakage are asserted. Existing
club negative/throttle tests are reused by the full candidate run, not replaced.

No prerequisite library fix was reproduced. Igor does not need a library-code
change/rebase for this report. If candidate HEAD or integrated runtime changes,
rerun the E2E/focused/full checks on that new exact head; this report is not blanket
approval of later revisions. Independent ChatGPT project-brain review is requested;
this executor neither approves nor merges its own report or Igor's candidate.

Browser/phone/Android PWA event-loop behavior, PostgreSQL concurrency, deployed
HTTPS persistence/redeploy and two-device rehearsal are NOT RUN here. They remain
#34/#35 gates. Residual club throttle concurrency semantics remain unchanged.

## Reproducing the independent console probe

Save the following as `.venv/issue33_library_probe.py` at the reviewed checkout,
then run `uv run python .venv/issue33_library_probe.py`. It uses a newly migrated
temporary SQLite DB (asserted before queries), inherits no production database,
and removes it after closing connections. The output is the L33 matrix above;
expected Django 4xx log lines are negative checks, not positive-save evidence.
This appendix is an audit reproducer, not a replacement for Igor's test ownership.
Probe source SHA-256:
`3253b748b68066c3926691c5293ee23ca622ab0f38227aad707fd7d57816de7a`.

```python
"""Independent L33 HTTP/DB probe; real URLconf/templates/services, disposable DB."""
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import timedelta
import uuid

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
with tempfile.TemporaryDirectory(prefix="issue33-library-") as directory:
    database = Path(directory) / "review.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"
    os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver"
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection, connections
    from django.test import Client
    from django.test.utils import setup_test_environment
    from django.utils import timezone
    from django.contrib.sessions.models import Session
    from apps.accounts.models import Account, ChildProfile, Reader
    from apps.club.models import Achievement, AchievementGrant, ClubMembership
    from apps.club.services import issue_code
    from apps.library.models import Book, ShelfEntry, ProgressEvent

    assert Path(connection.settings_dict["NAME"]).resolve() == database.resolve()
    setup_test_environment()
    call_command("migrate", verbosity=0)
    password, pin = "Synthetic-review-pass-33!", "2468"
    guardian = Account.objects.create_user("guardian33@demo.local", password, display_name="Review")
    own = Reader.objects.create(kind="adult", account=guardian)
    outsider = Account.objects.create_user("outsider33@demo.local", password, display_name="Other")
    outside_reader = Reader.objects.create(kind="adult", account=outsider)
    staff = Account.objects.create_superuser("staff33@demo.local", None, display_name="Staff")
    def book(title, active=True):
        return Book.objects.create(title=title, author="Synthetic", page_count=120, genre="story",
                                   is_active=active, cover_color="#123456", cover_emoji="book", source_note="synthetic review")
    primary, secondary, hidden = book("Review 120"), book("Conflict target"), book("Hidden", False)
    foreign_entry = ShelfEntry.objects.create(reader=outside_reader, book=secondary)
    for code, member in [("first-book", False), ("club-reader", True)]:
        Achievement.objects.create(code=code, title=code, description="Synthetic review rule",
                                   rule=Achievement.BOOKS_FINISHED_GTE, threshold=1, members_only=member, icon="star")
    def snapshot():
        return [list(ShelfEntry.objects.order_by("pk").values_list("pk", "reader_id", "book_id", "current_page", "status", "finished_at")),
                list(ProgressEvent.objects.order_by("pk").values_list("pk", "reader_id", "entry_id", "from_page", "to_page", "kind", "request_id")),
                list(AchievementGrant.objects.order_by("pk").values_list("pk", "reader_id", "achievement_id")),
                list(ClubMembership.objects.order_by("pk").values_list("pk", "reader_id", "status")),
                list(Reader.objects.order_by("pk").values_list("pk", "account_id", "child_id"))]
    def post(client, url, fields=None, hx=False):
        headers = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
        if hx:
            headers.update(HTTP_HX_REQUEST="true", HTTP_HX_CURRENT_URL="http://testserver/raft/")
        return client.post(url, fields or {}, **headers)
    def login(account):
        client = Client(enforce_csrf_checks=True)
        assert client.get("/cont/intrare/").status_code == 200
        assert post(client, "/cont/intrare/", {"username": account.email, "password": password}).status_code == 302
        return client
    def reject(response, status):
        assert response.status_code == status, (status, response.status_code)
        assert "HX-Trigger" not in response
    results = {}
    anonymous = Client(enforce_csrf_checks=True)
    assert anonymous.get("/carti/").status_code == 200
    detail = anonymous.get(f"/carti/{primary.public_id}/")
    assert detail.status_code == 200 and detail.templates[0].name == "adult/book_detail.html"
    assert anonymous.get(f"/carti/{hidden.public_id}/").status_code == 404
    writer = login(guardian)
    assert post(writer, "/familie/", {"nickname": "Mia", "age_band": "9-11", "avatar": "fox",
                                      "guardian": outsider.pk}).status_code == 302
    child = ChildProfile.objects.get(guardian=guardian)
    assert post(writer, "/familie/pin/", {"pin": pin, "pin_confirm": pin, "password": password}).status_code == 302
    assert post(writer, f"/familie/{child.public_id}/mod-copil/").status_code == 302
    assert writer.session["active_child"] == str(child.public_id)
    assert writer.get("/copil/").status_code == 200
    assert writer.get("/carti/").status_code == 200
    assert writer.get(f"/carti/{primary.public_id}/").templates[0].name == "child/book_detail.html"
    before = snapshot()
    reject(post(writer, f"/carti/{hidden.public_id}/adauga/", hx=True), 404)
    assert snapshot() == before
    add = f"/carti/{primary.public_id}/adauga/"
    first = post(writer, add, {"reader": own.public_id, "child": uuid.uuid4(), "guardian": outsider.pk}, hx=True)
    assert first.status_code == 204 and first["HX-Trigger"] == "saved" and not first.content
    entry = ShelfEntry.objects.get(reader=child.reader, book=primary)
    entry_url = f"/raft/{entry.public_id}/"
    assert first["HX-Redirect"] == entry_url
    duplicate = post(writer, add, hx=True)
    assert duplicate.status_code == 204 and duplicate["HX-Redirect"] == entry_url and "HX-Trigger" not in duplicate
    plain = post(writer, add)
    assert plain.status_code == 302 and plain["Location"] == entry_url
    assert ShelfEntry.objects.filter(reader=child.reader, book=primary).count() == 1
    assert not ShelfEntry.objects.filter(reader=own).exists()
    results["L33-01"] = {"status": "PASS", "public_detail": 200, "child_home": 200,
                           "inactive_add": 404, "htmx_add": 204, "duplicate_trigger": False, "plain_add": 302}
    page = writer.get(entry_url)
    assert page.status_code == 200 and page.templates[0].name == "child/shelf_entry.html"
    request_id = page.context["request_id"]
    progress_url = entry_url + "progres/"
    saved = post(writer, progress_url, {"page": 35, "request_id": request_id, "reader": own.public_id}, hx=True)
    assert saved.status_code == 200 and saved["HX-Trigger"] == "saved"
    assert str(saved.context["request_id"]) != str(request_id)
    assert saved.templates[0].name == "child/_progress.html"
    event = ProgressEvent.objects.get(entry=entry)
    assert (event.reader_id, event.from_page, event.to_page) == (child.reader.pk, 0, 35)
    entry.refresh_from_db()
    assert entry.current_page == 35
    before = snapshot()
    assert post(writer, progress_url, {"page": "035", "request_id": request_id}, hx=True).status_code == 200
    assert post(writer, progress_url, {"page": 35, "request_id": request_id}).status_code == 302
    assert snapshot() == before
    for fields in [{"page": 36, "request_id": request_id}]:
        reject(post(writer, progress_url, fields, hx=True), 409)
    reject(post(writer, entry_url + "terminat/", {"request_id": request_id}, hx=True), 409)
    for bad_page in (-1, 121, "not-a-number", "35.5"):
        key = str(uuid.uuid4())
        rejected = post(writer, progress_url, {"page": bad_page, "request_id": key}, hx=True)
        reject(rejected, 422)
        assert rejected.context["request_id"] == key
    reject(post(writer, progress_url, {"page": 35, "request_id": "bad-uuid"}, hx=True), 422)
    assert snapshot() == before
    results["L33-02"] = {"status": "PASS", "stored": "35/120", "events": 1,
                           "replay_semantic_page": "035", "page_and_kind_conflict": 409, "invalid_payloads": 422}
    viewer = login(guardian)
    assert viewer.session.session_key != writer.session.session_key
    before = snapshot()
    report = viewer.get(f"/familie/{child.public_id}/")
    dashboard = viewer.get("/panou/")
    assert report.status_code == dashboard.status_code == 200
    assert report.templates[0].name == "adult/child_report.html"
    assert report.context["entries"][0].current_page == 35
    assert (report.context["stats"].pages_total, report.context["stats"].pages_7d) == (35, 35)
    assert dashboard.context["my_stats"].pages_total == 0
    assert dashboard.context["children"][0]["stats"].pages_7d == 35
    assert snapshot() == before
    foreign = login(outsider)
    reject(foreign.get(f"/familie/{child.public_id}/"), 404)
    reject(foreign.get(entry_url), 404)
    results["L33-03"] = {"status": "PASS", "different_guardian_session": True, "child_pages_total": 35,
                           "child_pages_7d": 35, "adult_pages_total": 0, "domain_reads_unchanged": True, "foreign_report": 404}
    assert post(writer, f"/carti/{secondary.public_id}/adauga/").status_code == 302
    other = ShelfEntry.objects.get(reader=child.reader, book=secondary)
    before = snapshot()
    reject(post(writer, f"/raft/{other.public_id}/progres/", {"page": 35, "request_id": request_id}, hx=True), 409)
    assert snapshot() == before
    results["L33-02"]["cross_entry_conflict"] = 409
    finish_id = uuid.uuid4()
    finish = entry_url + "terminat/"
    response = post(writer, finish, {"request_id": finish_id}, hx=True)
    assert response.status_code == 200 and response["HX-Trigger"] == "saved"
    entry.refresh_from_db()
    assert entry.current_page == 120 and entry.status == "finished" and entry.finished_at is not None
    before = snapshot()
    assert post(writer, finish, {"request_id": finish_id}, hx=True).status_code == 200
    assert post(writer, finish, {"request_id": finish_id}).status_code == 302
    reject(post(writer, finish, {"request_id": uuid.uuid4()}, hx=True), 422)
    assert snapshot() == before
    assert ProgressEvent.objects.filter(entry=entry, kind="finish").count() == 1
    assert AchievementGrant.objects.filter(reader=child.reader, achievement__code="first-book").count() == 1
    assert not AchievementGrant.objects.filter(reader=child.reader, achievement__code="club-reader").exists()
    assert writer.get("/clubul-meu/").status_code == 403
    achievements = writer.get("/realizari/")
    assert any(g.code == "first-book" for g in achievements.context["earned"])
    assert any(g["achievement"].code == "club-reader" for g in achievements.context["locked"])
    code, plaintext = issue_code(staff, label="Synthetic review", expires_at=timezone.now() + timedelta(days=1))
    assert not connection.in_atomic_block
    redemption = post(viewer, "/club/cod/", {"reader": child.public_id, "code": plaintext})
    assert redemption.status_code == 302 and "HX-Trigger" not in redemption
    code.refresh_from_db()
    assert code.redeemed_at is not None and code.redeemed_for_id == child.reader.pk
    assert ClubMembership.objects.filter(reader=child.reader).count() == 1
    assert AchievementGrant.objects.filter(reader=child.reader, achievement__code="club-reader").count() == 1
    reject(post(viewer, "/club/cod/", {"reader": child.public_id, "code": plaintext}), 422)
    assert ClubMembership.objects.filter(reader=child.reader).count() == 1
    assert AchievementGrant.objects.filter(reader=child.reader, achievement__code="club-reader").count() == 1
    assert writer.get("/clubul-meu/").status_code == 200
    assert viewer.get("/clubul-meu/").status_code == 403
    results["L33-04"] = {"status": "PASS", "finish_http": 200, "plain_finish_replay": 302,
                           "finish_events": 1, "first_book_grants": 1, "club_grants_before_redeem": 0,
                           "redemption": 302, "club_grants_after_redeem": 1, "code_replay": 422, "member_corner": 200}
    before = snapshot()
    for foreign_id in (foreign_entry.public_id, uuid.uuid4()):
        reject(post(writer, f"/raft/{foreign_id}/progres/", {"page": 35, "request_id": uuid.uuid4()}, hx=True), 404)
    denied = post(writer, "/familie/", hx=True)
    reject(denied, 403)
    assert denied.content == b""
    assert anonymous.get("/cont/intrare/").status_code == 200
    denied = post(anonymous, progress_url, {"page": 35, "request_id": uuid.uuid4()}, hx=True)
    reject(denied, 401)
    assert denied.content == b"" and denied["HX-Redirect"].startswith("/cont/intrare/")
    csrf = viewer.post(progress_url, {"page": 35, "request_id": uuid.uuid4()}, HTTP_HX_REQUEST="true")
    reject(csrf, 403)
    expired = login(guardian)
    Session.objects.filter(session_key=expired.session.session_key).update(expire_date=timezone.now() - timedelta(seconds=1))
    denied = post(expired, progress_url, {"page": 35, "request_id": uuid.uuid4()}, hx=True)
    reject(denied, 401)
    assert not denied.content and "HX-Redirect" in denied
    assert snapshot() == before
    results["L33-05"] = {"status": "PASS", "anonymous_expired": 401, "child_adult_route": 403,
                           "foreign_unknown": 404, "csrf": 403, "errors_have_saved_trigger": False,
                           "lock_503": "covered by separately rerun file-backed tests"}
    print(json.dumps({"runtime": "real URLconf/templates/authz/services; separate disposable file SQLite",
                      "outer_transaction": False, "results": results}, ensure_ascii=True, indent=2))
    connections.close_all()

```
