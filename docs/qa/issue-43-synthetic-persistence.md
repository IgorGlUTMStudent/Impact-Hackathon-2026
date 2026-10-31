# Issue #43 — Synthetic persistence acceptance (SYNTHETIC ONLY)

**Status:** SYNTHETIC PASS. This proves local Django route correctness and cross-process
readback from a disposable file-backed SQLite database. It does **not** prove Render
restart/redeploy durability, PostgreSQL storage, public HTTPS or phone/PWA behaviour.
`SYNTHETIC PASS ≠ RENDER PERSISTENCE VERIFIED`; issue **#34 stays OPEN**.

## 1. Scope and environment

- **Scope:** synthetic-only acceptance of the revised #43 — reuse the existing real-route
  session integration tests (G43-S1), add the single missing cross-process boundary
  (G43-S2), re-run existing negative regressions (G43-S3). No product, schema, contract or
  deployment changes; the only code change is the new self-contained harness
  `scripts/synthetic_persistence_check.py` plus this report.
- **Base:** `main@1ab1a9ebd583f903538e7a7a367560c807ba1bc6` (verified equal to
  `origin/main` after `git fetch --all --prune`; working tree clean).
- **OS:** Windows x64 (build 26300), Git Bash shell.
- **Toolchain:** Python 3.12.13, Django 5.2.18, pytest 9.2.0, pytest-django 4.14.0,
  uv 0.11.24, `DJANGO_SETTINGS_MODULE=config.settings.dev` (pytest ini + harness override).

## 2. Gate ledger

| Gate | Status | Exact command | Result / evidence |
|---|---|---|---|
| G43-S1 independent Django sessions (existing integration test) | **PASS** | `uv run pytest tests/test_demo_flow.py -q` | exit 0 — 4 passed. `test_guardian_child_reading_report_finish_and_real_club` on this HEAD: child-mode `POST` saves `35/120` (`HX-Trigger: saved`, 1 `ProgressEvent`), a second independent login of the same guardian gets a different `session.session_key`, `child_report` shows `(35, 120)` with `StatsVM(1, 0, 35, 35)`, and read-only `GET child_report`/`adult_dashboard` leave `ProgressEvent.objects.count()` unchanged |
| G43-S1 continued | **PASS** | `uv run pytest tests/test_child_mode.py tests/test_authz.py -q` | exit 0 — 52 passed (40 + 12) |
| G43-S2 cross-process disposable-SQLite readback | **PASS** (2/2 runs) | `uv run python scripts/synthetic_persistence_check.py` | exit 0 both runs; writer process exits 0 after a real `POST page=35`, reader process (new Python process, own login) reads `35/120` from the same SQLite file, `ProgressEvent` count unchanged, `same_db_file=true`, `session_keys_differ=true` — raw output in §3 |
| G43-S3 negative regressions (reused, not cloned) | **PASS** | same three pytest files as above | exit 0; invariant→test-ID mapping in §4 |
| Full suite (local Windows) | **PARTIAL — pre-existing failures** | `uv run pytest --tb=no` | exit 1 — `4 failed, 370 passed, 4 skipped in 205.94s`. All 4 failures are `tests/test_review_fixes.py` WSGI/manage.py subprocess probes crashing with `UnicodeDecodeError` (cp1251 bytes vs UTF-8 reader thread) — Windows-only. Verified unrelated to this change: with `scripts/` temporarily removed the same 4 fail identically. CI (Ubuntu) on the base SHA recorded `374 passed, 4 skipped, 0 failed` (issue #34 ledger) |
| `uv run python manage.py check` | **PASS** | exit 0 | "System check identified no issues (0 silenced)." |
| `uv run python manage.py makemigrations --check --dry-run` | **PASS** | exit 0 | "No changes detected" (no schema drift) |
| `git diff --check` | **PASS** | exit 0 | no whitespace errors |

Exact-head GitHub CI: PENDING at time of writing — will be recorded in the PR description
once the run finishes; not claimed green before completion.

## 3. G43-S2 synthetic trace (actual harness output)

`uv run python scripts/synthetic_persistence_check.py` (run twice, identical verdicts):

```json
{"role": "seed", "status": "OK"}
{"role": "writer", "status": "OK", "db_basename": "synthetic.sqlite3", "current_page": 35, "page_count": 120, "progress_events": 1}
{"role": "reader", "status": "OK", "db_basename": "synthetic.sqlite3", "same_db_file": true, "outside_repo": true, "current_page": 35, "page_count": 120, "progress_events": 1, "progress_events_unchanged": true, "session_keys_differ": true}
{"role": "orchestrator", "status": "cleanup", "temp_db_removed": true}
```

Process sequence (every step a separate `sys.executable` subprocess; the orchestrator
itself never opens the database):

1. **Temp DB:** `tempfile.TemporaryDirectory(prefix="gc43-synth-")` under the system temp
   dir (asserted outside the repository), file `synthetic.sqlite3`. Disposable synthetic
   credentials (email/password/PIN) are generated per run with `secrets`, passed to
   children via environment, never printed or persisted.
2. **Env guard:** child environments are scrubbed of `DATABASE_URL`,
   `DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DEMO_PASSWORD`,
   `DEMO_PIN`, `DJANGO_SUPERUSER_*`, then pinned to `config.settings.dev` +
   `DATABASE_URL=sqlite:///<temp path>`. `.env` cannot override these (real env wins).
3. **Preflight (before any migration):** separate process verifies effective
   `settings.DATABASES["default"]` engine is `django.db.backends.sqlite3`, its `NAME`
   resolves to exactly the temp file, under the temp dir, not the repo `db.sqlite3`.
   Every DB-touching child re-checks and aborts otherwise.
4. **Migrate:** real `python manage.py migrate --noinput` subprocess, exit 0.
5. **Seed:** ORM fixture setup only (no `seed_demo`, no reset): synthetic guardian with
   PIN, child profile + child reader, one active 120-page book. State file holds safe IDs
   only (public UUIDs, pks, counts, a SHA-256 of the writer session key).
6. **Writer process:** fresh `django.test.Client` → `POST /cont/intrare/` 302 →
   `POST /familie/<child>/mod-copil/` 302 → `/copil/`, session `mode=child` →
   `POST /carti/<book>/adauga/` 204 + `HX-Trigger: saved` → `GET /raft/<entry>/` 200
   (renders `request_id`) → `POST /raft/<entry>/progres/` `page=35` 200 +
   `HX-Trigger: saved` + `child/_progress.html`. Read-only readback: entry `35/120`,
   exactly 1 `ProgressEvent`. Process exits 0. No ORM progress writes anywhere.
7. **Writer fully exits** (returncode 0 recorded) **before** the reader starts.
8. **Reader process (new Python process, same DB file):** counts `ProgressEvent` before
   any request (== writer's 1) → own fresh `POST` login 302 (new session; its key's
   SHA-256 differs from the writer's; mode is not `child`; no cookie/session reuse) →
   `GET /familie/<child>/` 200 `adult/child_report.html`, child belongs to the logged-in
   guardian, entries `(35, 120)`, stats `StatsVM(1, 0, 35, 35)` → `GET /panou/` card shows
   the child's current entry `35/120` → `ProgressEvent` count after the GETs is unchanged
   and the stored entry is still `reading 35/120`. Exit 0 with the JSON above
   (`same_db_file=true`, `outside_repo=true`, `session_keys_differ=true`).
9. **Cleanup:** the `TemporaryDirectory` context removes the DB and state file; nothing
   outside the temp dir is touched. Repo `db.sqlite3` is never opened by the harness.

Explicitly rejected shortcuts (all avoided): two clients in one process, `refresh_from_db`
as "persistence", `:memory:` SQLite, ORM assignment of `current_page`, different DB files,
copied reader session, re-seeding or re-POSTing in the reader.

## 4. G43-S3 negative invariants → executed test IDs

All from the three files executed above (exit 0); no new negative tests were added —
existing regressions were reused as instructed.

| Invariant | Test ID(s) |
|---|---|
| Expired/anonymous HTMX mutation → `401`, no `HX-Trigger: saved`, no write | `tests/test_child_mode.py::test_htmx_mutation_without_session_is_401_no_partial`; `tests/test_child_mode.py::test_htmx_mutation_after_session_expiry_stores_nothing`; `tests/test_demo_flow.py::test_real_security_refusals_preserve_stored_diary` (expired + plain-anonymous clients → 401 + `HX-Redirect`, stored-diary snapshot unchanged) |
| Foreign guardian/reader cannot read or mutate child data → `404` fail-closed | `tests/test_demo_flow.py::test_real_security_refusals_preserve_stored_diary` (foreign `child_report`, `shelf_entry`, `record_progress` → 404); `tests/test_authz.py::test_get_child_for_guardian_owner_only`; `tests/test_authz.py::test_get_entry_for_reader_owner_only`; `tests/test_child_mode.py::test_start_for_foreign_child_is_404` |
| Adult route from child mode → PIN-gate 302, HTMX `403` with empty body | `tests/test_child_mode.py::test_adult_urls_redirect_to_pin_gate[*]` (10 URLs); `tests/test_child_mode.py::test_adult_urls_via_htmx_are_403_without_partial[*]`; `tests/test_demo_flow.py::test_real_security_refusals_preserve_stored_diary` (dashboard/family/redeem/admin from child mode) |
| Same `request_id` reused with different data → `409`, progress unchanged | `tests/test_demo_flow.py::test_guardian_child_reading_report_finish_and_real_club` (progress 409); `tests/test_demo_flow.py::test_real_security_refusals_preserve_stored_diary` (progress + finish 409, out-of-range 422, stored entry still 35) |
| Lock/fault injection → `503` unsaved, no partial write | `tests/test_demo_flow.py::test_lock_fault_injection_is_unsaved_with_real_authz` |

## 5. Explicit NOT RUN / NOT VERIFIED ledger

| Item | Status |
|---|---|
| `REAL_BROWSER` | **NOT RUN** |
| `RENDER_REDEPLOY` / `RENDER_RESTART` | **NOT RUN** (no interaction with Render, per scope) |
| `POSTGRES_PERSISTENCE` | **NOT VERIFIED** |
| `PHONE_PWA` | **NOT RUN** (#35 scope) |
| Production data / live host | untouched; `PRODUCTION_DATA_TOUCHED: NO` |
| Issue #34 | **OPEN** — real-host persistence (gunicorn restart + redeploy on PostgreSQL) unproven |

## 6. Residual risks and relation to #34 / #35

- The writer/reader proof covers *process lifetime* against one SQLite file. A real Render
  redeploy replaces the container **and** uses PostgreSQL, so #34's live gate (35/120
  surviving redeploy + independent guardian session on the public host) remains the only
  acceptance path for production durability. Nothing here may be cited as #34 evidence.
- SQLite-specific concurrency policy (`transaction_mode=IMMEDIATE`, timeout 5s) was not
  exercised under load; not a goal of this synthetic gate.
- The 4 local Windows failures in `tests/test_review_fixes.py` are subprocess output-decode
  failures (cp1251 console vs UTF-8 reader threads), pre-existing on `main` and green in
  Ubuntu CI; they warrant a separate small Windows-encoding fix if the team wants green
  local runs, outside #43 scope.
- #35 (real browser, phone, PWA, pitch) untouched.

## 7. Reproduce

```bash
uv sync --frozen
uv run pytest tests/test_demo_flow.py -q
uv run pytest tests/test_child_mode.py tests/test_authz.py -q
uv run python scripts/synthetic_persistence_check.py   # creates + deletes its own temp DB
uv run pytest --tb=no                                   # full suite
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

The harness is self-contained: each run generates a fresh system-temp directory, a fresh
SQLite file and fresh synthetic credentials, then deletes them on exit. It never touches
the repo `db.sqlite3`, `.env`, any host `DATABASE_URL`, or anything outside its own temp
directory. No real paths, credentials, PINs or child data are printed or committed.
