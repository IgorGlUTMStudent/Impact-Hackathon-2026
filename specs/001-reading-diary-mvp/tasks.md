---
description: "Task list for the Gustul Cărților P0 reading-diary slice"
---

# Tasks: Gustul Cărților — P0 reading-diary vertical slice

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [execution-plan.md](./execution-plan.md)

**Generation**: written by hand from `.specify/templates/tasks-template.md` (the `specify` CLI is not installed on the author's machine; no `/speckit-tasks` command was run). Owners and PR numbers follow the [execution plan](./execution-plan.md#workstreams-and-ownership).

**Status rule**: `[x]` only for work merged or in an open PR **with executed checks reported in that PR**. Everything else is `[ ]`. Planned tests are NOT RUN until their PR reports real output.

## Format: `[ID] [P?] [Story] Description — owner (PR)`

- **[P]**: can run in parallel (different files, no unmet dependency)
- **[Story]**: US1–US5 from spec.md; foundation tasks have none
- Paths are relative to the repository root (layout in [plan.md § Source Code](./plan.md#source-code-repository-root--to-be-created-in-m0-not-in-this-pr))

## Critical path

```text
H (host proof, Igor, parallel from now) ─────────────────────────────┐
M0 foundation (Arsenii, PR-1) ─┬─ M1 PR-2 auth/child mode/throttles (Arsenii)
                               ├─ M1 PR-3 library services (Alisa) ── M2 PR-4 library views (Alisa)
                               └─ M1 PR-5 club services (Igor) ────── M2 PR-6 club views + e2e (Igor)
UI from contracts + /_preview/ (Vladimir PR-7, Denis PR-8) ──────────┴─ M3 demo on phone + laptop ── M4 hardening, rehearsal
```

Shared files with a single owner: see [execution-plan.md § Files nobody edits concurrently](./execution-plan.md#files-nobody-edits-concurrently).

---

## Phase 1 — M0 Setup and foundation (Arsenii, PR-1, Issue #10)

**Goal**: one runnable Django project with the full shared schema, migrations, seeds and checks, so every workstream can branch from it.

- [x] T001 `pyproject.toml` (Python 3.12, Django 5.2 LTS, dj-database-url, whitenoise, gunicorn; dev: pytest, pytest-django; optional `postgres` extra) + `uv.lock`, `.python-version` — Arsenii (PR-1)
- [x] T002 `manage.py`, `config/settings/{base,dev,prod}.py`, `config/urls.py`, `config/wsgi.py`, `.env.example`, `.gitignore` — Arsenii (PR-1)
- [x] T003 SQLite `OPTIONS = {"transaction_mode": "IMMEDIATE", "timeout": 5}`, `ATOMIC_REQUESTS=False`, no WAL; Postgres via `DATABASE_URL` — Arsenii (PR-1)
- [x] T004 Custom `accounts.Account` (email login, case-insensitive unique email) set as `AUTH_USER_MODEL` before the first migration — Arsenii (PR-1)
- [x] T005 Models + initial migrations: `accounts` (Account, ChildProfile, Reader, Throttle), `library` (Book, ShelfEntry, ProgressEvent), `club` (ClubMembership, MembershipCode, Achievement, AchievementGrant, ClubActivity) — Arsenii (PR-1)
- [x] T006 Minimal admin registration (children read-only, nickname only; code hashes never shown) — Arsenii (PR-1)
- [x] T007 `apps/core/viewmodels.py` (BookVM, ShelfEntryVM, StatsVM, GrantVM, AchievementVM, ChildVM, MascotLine) — Arsenii (PR-1)
- [x] T008 Empty `apps/<app>/urls.py` included from `config/urls.py`; `/healthz/`; DEBUG-only `/_preview/<adult|child>/<template>` with synthetic context — Arsenii (PR-1)
- [x] T009 Stub `club.services.evaluate_achievements()` returning `[]`, marked `NOT IMPLEMENTED — PR-5` — Arsenii (PR-1)
- [x] T010 Idempotent `manage.py seed_demo` (+ guarded `--reset`), credentials from env only — Arsenii (PR-1)
- [x] T011 `tests/test_models.py`, `tests/test_seed.py`, `tests/test_foundation.py` — Arsenii (PR-1)
- [x] T012 Vendored `static/js/htmx.min.js` 2.0.11 — Arsenii (PR-1)
- [ ] T013 Independent review of PR-1 and merge — reviewer

**Checkpoint M0**: PR-1 merged; `uv run pytest` green; `seed_demo` idempotent on a fresh DB.

## Phase 1b — Host proof H (Igor, PR-0 / PR #12, parallel)

- [ ] T020 [P] H1–H7 evidence per [execution-plan.md § Host proof](./execution-plan.md#host-proof-separate-critical-path-activity); GO/NO-GO or declared laptop fallback — Igor

---

## Phase 2 — M1 services (parallel after M0)

### Identity, child mode, throttles (Arsenii, PR-2)

- [ ] T030 `accounts/throttle.py` (`check`, `record_failure`, `reset`) over `accounts.Throttle` — Arsenii
- [ ] T031 [US4] Signup (`/cont/inregistrare/`), `ThrottledLoginView`, POST `logout`; adult `Reader` created with the account — Arsenii
- [ ] T032 [US1] Family CRUD (`/familie/`), 6-child limit, child `Reader` created with the child — Arsenii
- [ ] T033 [US3] PIN set (`/familie/pin/`, password re-auth), `child_mode_start`, `pin_gate` (PIN only, 5 → 5 min), logout recovery — Arsenii
- [ ] T034 [US3] `ChildModeMiddleware` deny-by-default + HTMX 401/403 guard; `accounts/authz.py` (`current_reader`, `get_child_for_guardian`, `get_entry_for_reader`) — Arsenii
- [ ] T035 Tests: `test_authz.py`, `test_child_mode.py`, `test_login_throttle.py` — Arsenii

### Reading domain (Alisa, PR-3)

- [ ] T040 [P] [US1] `library/services.py`: `add_to_shelf`, `record_progress`, `finish_book` per [data-model § Concurrency](./data-model.md#concurrency-and-idempotency-p0-policy) (replay, 409, commit order, 503) — Alisa
- [ ] T041 [P] [US1] `library/stats.py`: `reader_stats` — Alisa
- [ ] T042 [P] Tests: `test_progress.py`, `test_stats.py`, `test_concurrency.py` (file-based SQLite) — Alisa

### Club (Igor, PR-5)

- [ ] T050 [P] [US2] `club/services.py`: `is_member`, `redeem_code` (+ `redeem` throttle), real `evaluate_achievements` replacing the stub — Igor
- [ ] T051 [P] [US2] Admin actions: activate/revoke membership, issue codes (plaintext shown once) — Igor
- [ ] T052 [P] Tests: `test_membership.py`, `test_achievements.py` — Igor

---

## Phase 3 — M2 views and UI (after the matching M1 service)

- [ ] T060 [US1] [US4] [US5] Library views/urls: anonymous catalog, book detail, add, shelf, shelf entry, progress, finish; `HX-Trigger: saved`; 409/503 handling — Alisa (PR-4)
- [ ] T061 [US2] Club views: redeem, achievements, club corner (members only) — Igor (PR-6)
- [ ] T062 [P] [US1] [US4] `templates/base.html`, `_toast.html`, `templates/adult/*`, `static/css/app.css`, `static/js/app.js` (422 swap only; 401/403/409/503 → "Nu s-a salvat"), `locale/ro` — Vladimir (PR-7)
- [ ] T063 [P] [US1] [US3] `templates/child/*`, `static/css/child.css`, mascot + avatars, `apps/core/mascot.py`, manifest, `sw.js`, `/offline/` — Denis (PR-8)
- [ ] T064 E2E `tests/test_demo_flow.py` (demo path + adult self-reader smoke) — Igor (PR-6)
- [ ] T065 [P] `tests/test_i18n.py` — Vladimir

**Checkpoint M2**: `test_demo_flow.py` passes via the test client.

## Phase 4 — M3/M4 demo and hardening

- [ ] T070 Demo script in [quickstart.md](./quickstart.md) on a real phone + laptop against the host that passed H (or declared fallback); record observed latency — all
- [ ] T071 Security counter-examples 1–13 executed and reported — Arsenii (coordination), each owner for their tests
- [ ] T072 Demo-ready tag, `seed_demo --reset` rehearsal, fallback rehearsal, pitch visuals — Denis (PR-9), Igor

## Open gates (not tasks)

G1–G6 stay open (spec.md). Nothing above implies partner approval, legal compliance or production readiness.
