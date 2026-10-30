# Execution plan after architecture review (proposal)

**Not a task backlog.** This is the roadmap to start controlled parallel work once Issue #7 review approves the architecture. Detailed `tasks.md` is generated afterwards. Hackathon deadline is `[UNKNOWN]`; durations are estimates for AI-assisted developers.

## Critical path

```mermaid
flowchart LR
    R[Architecture PR reviewed] --> G7[G7: stack sign-off by team lead]
    G7 --> M0[M0: PR-1 skeleton + full schema + seeds]
    R --> H[H: host proof PR-0<br/>starts immediately, in parallel]
    H --> M3
    M0 --> M1a[PR-2 auth, family, child mode, throttles]
    M0 --> M1b[PR-3 library services]
    M0 --> M1c[PR-5 club services]
    M1b --> M2a[PR-4 library views]
    M1a --> M2a
    M1c --> M2b[PR-6 club views + e2e test]
    M2a --> M3[M3: demo path works on public URL]
    M2b --> M3
    T1[PR-7 adult templates] --> M3
    T2[PR-8 child templates + mascot + PWA] --> M3
    M3 --> M4[M4: hardening, demo rehearsal, pitch]
```

| Milestone | Exit criterion (observable) | Est. |
|---|---|---|
| **H** | Host proof evidence complete (see below), or the laptop fallback declared. Runs in parallel from the moment review starts; it does not wait for M0 | 1–2 h, started first |
| **M0** | G7 signed off; PR-1 merged; `uv run pytest` green on empty suite + model tests; `seed_demo` runs locally | 1.5–2 h |
| **M1** | Services merged with unit tests: authz/child mode, login/PIN/redeem throttles, progress (idempotent, ranges, concurrency cases), membership + achievements | +2–3 h |
| **M2** | Views wired to templates; `tests/test_demo_flow.py` passes end-to-end via test client, including the adult self-reader smoke | +2–3 h |
| **M3** | Manual demo script in [quickstart.md](./quickstart.md) passes on a real phone + laptop against the host that passed **H** (or the declared laptop fallback); observed latency recorded | +1 h |
| **M4** | Counter-example checklist executed and reported; demo-ready tag; fallback rehearsed | +1–2 h |

## Host proof (separate critical-path activity)

Owner: Igor (PR-0). Start immediately with a throwaway "hello + one table" Django app; do not wait for PR-1. No host is named in the pitch or docs as "the" host until this passes. Each line needs real evidence in the PR-0 description (screenshot, command output or note with time). Until then the status is **NOT RUN**.

| # | Evidence | How | Status |
|---|---|---|---|
| H1 | HTTPS works from a phone on mobile data | Open the URL on a phone, no certificate warning | NOT RUN |
| H2 | PWA installability conditions | Served over HTTPS, manifest + service worker load, Android Chrome offers "Install" / "Add to home screen" | NOT RUN |
| H3 | A DB write survives a web-app **reload** and a **redeploy** | Write a row, reload, check; redeploy, check. Record whether the filesystem is persistent or ephemeral (an ephemeral disk means SQLite is lost → Postgres or another host) | NOT RUN |
| H4 | Login and a save work from the phone | Sign in, save a value, read it on a laptop | NOT RUN |
| H5 | Observed latency | Note TTFB and save round trip from the phone (numbers only, no pass/fail target) and whether the first request after idle is slow | NOT RUN |
| H6 | Free-tier limits understood | Note worker count, CPU quota use after a test session, expiry date; whether the disk is local (needed for WAL) and which header carries the client IP | NOT RUN |
| H7 | Fallback ready | The same tag runs on the presenter laptop with the phone on the same network; rehearsed once | NOT RUN |

If H1–H4 fail on the first candidate, try the next one from [research.md](./research.md#4-hosting-options-for-the-public-demo-gate-g6). If none passes before M3, use the laptop fallback and say so honestly.

## Workstreams and ownership

Assignment by dependency and by keeping shared files with one owner; the AI tool is not treated as a role.

| Person (tool) | Workstream | PRs | Owns (only they edit) | Depends on |
|---|---|---|---|---|
| **Арсений** (Claude Code) | Foundation + identity/security | **PR-1** skeleton: `pyproject`, `config/*`, custom `Account`, **all models + initial migrations for all apps**, admin registration stubs, `core/viewmodels.py`, stub `club.services.evaluate_achievements()` returning `[]`, debug-only `/_preview/<template>/` route, `seed_demo`, SQLite `IMMEDIATE` + timeout settings · **PR-2** signup, `ThrottledLoginView`, family CRUD, PIN, `ChildModeMiddleware` (deny-by-default, HTMX 401/403), `pin_gate`, logout recovery, `accounts/throttle.py`, `accounts/authz.py` + `test_authz.py`, `test_child_mode.py`, `test_login_throttle.py` | `config/`, `apps/accounts/`, all `models.py` + migrations until M1 (later changes = decision gate), `core/viewmodels.py` | Architecture approval; G7 stack sign-off before PR-1 merges |
| **Алиса** (Codex) | Reading domain | **PR-3** `library/services.py` (`add_to_shelf`, `record_progress`, `finish_book`), `library/stats.py` + `test_progress.py`, `test_stats.py`, `test_concurrency.py` · **PR-4** library views/urls (anonymous catalog, book detail, add, shelf, shelf entry, progress, finish) choosing `adult/` or `child/` templates by mode; 409/503 handling and `HX-Trigger: saved` | `apps/library/` (except models after M0) | PR-1 (models), PR-2 for `current_reader` (can mock it in tests until then) |
| **Игорь** (Codex + Antigravity, separate worktrees) | Club, entitlement, integration, deploy | **PR-0** host proof H1–H7 (starts first, parallel to everything; notes only, no secrets) · **PR-5** `club/services.py` (`is_member`, `redeem_code` with the `redeem` throttle, `evaluate_achievements`), admin actions (issue codes showing plaintext once, revoke) + `test_membership.py`, `test_achievements.py` · **PR-6** club views (redeem, achievements, club corner), deploy script/docs, `tests/test_demo_flow.py` | `apps/club/` (except models after M0), deploy docs, `tests/test_demo_flow.py` | PR-1; PR-3 for e2e |
| **Владимир** (Antigravity) | Adult UX + design system + i18n | **PR-7** `templates/base.html`, `_toast.html`, design tokens in `static/css/app.css`, all `templates/adult/*` (including the P0 adult self-reader shelf and progress screens), HTMX error/toast handling in `static/js/app.js` (401/403/409/503 → "Nu s-a salvat"; "saved" only on `HX-Trigger: saved`), `locale/ro` catalog (runs `makemessages` at M3) | `templates/base.html`, `templates/adult/`, `static/css/app.css` tokens section, `static/js/app.js`, `locale/` | Context contracts only (works with `/_preview/` after PR-1) |
| **Денис** (Antigravity) | Child UX, mascot, PWA, demo | **PR-8** `templates/child/*`, child styles (own CSS section/file `static/css/child.css`), mascot + avatars assets, `core/mascot.py` script (keys from routes contract), `manifest.webmanifest`, `sw.js`, `/offline/` · **PR-9** demo script polish, screenshots with synthetic data, pitch visuals | `templates/child/`, `static/css/child.css`, `static/img/`, `static/sw.js`, manifest, `apps/core/mascot.py`, `apps/core/pwa.py` | Context contracts only; PR-1 for preview |

### Before PR-1 merges (no blocking)

- Vladimir and Denis design screens (Figma/paper/HTML prototypes) from the [context contracts](./contracts/routes.md#template-context-contracts-for-parallel-ui-work) and the mascot script.
- Alisa and Igor write their service functions and tests against [data-model.md](./data-model.md) in branches based on PR-1's branch (rebase after merge).
- Igor runs the host proof (PR-0 notes in the PR description, no secrets).
- The team lead gives G7 stack sign-off; PR-1 does not merge before it.

### Files nobody edits concurrently

| File / area | Single owner | Others do instead |
|---|---|---|
| `config/settings/*`, `config/urls.py` | Arsenii | Request a change in the PR thread; app URLs live in `apps/<app>/urls.py` already included by PR-1 |
| `apps/*/models.py`, migrations | Arsenii until M1, then app owner **with a decision-gate note** | Propose field changes in the PR; never run `makemigrations` for another app |
| `core/viewmodels.py` | Arsenii | Ask for new fields |
| `templates/base.html`, CSS tokens | Vladimir | Child styles go in `child.css` |
| `locale/` | Vladimir | Wrap strings in `{% translate %}` / `gettext` only |
| `pyproject.toml` / `uv.lock` | Arsenii | Ask before adding a dependency |

### PR rules

- Branch from `main` after PR-1 (`feat/<area>-<short>`), small PRs, `Refs #7`.
- Each PR lists the exact commands run (`uv run pytest …`, `uv run python manage.py check`) and their real output.
- Review by ChatGPT (independent) or a teammate; no self-merge.

## Smoke / e2e scenario (automated in `tests/test_demo_flow.py`, repeated manually in M3)

1. `seed_demo --reset`.
2. Guardian signs in → creates child → sets PIN → starts child mode.
3. Child adds book (120 p) → saves page 35 → page 35 persisted → replay same `request_id` → no change.
4. New client session as guardian → child report shows 35/120 and pages_7d = 35.
5. Child finishes book → `first-book` granted; `club-reader` **not** granted (not a member).
6. Guardian (after PIN) redeems code for child → membership active → `evaluate_achievements` grants `club-reader` once.
7. Child opens club corner → 200; second child (non-member) → 403.
8. Adult self-reader smoke (US4/US5, not on stage): logged-out client opens catalog → 200, "add to shelf" → login; the seeded adult without children signs in → adds a book → saves a page → finishes → own dashboard shows the stored totals; no PIN or child UI involved.

Test file owners not listed above: `tests/test_i18n.py` — Vladimir; `tests/test_seed.py` — Arsenii.

Failure checks (manual + tests): out-of-range page, foreign IDs (404), adult URLs in child mode (redirect to PIN gate; HTMX 403), wrong PIN ×5 (lock, correct PIN refused while locked), logout recovery, login ×5 wrong (lock), used/expired code (generic error, throttled), network off / session expired (no "saved"), same `request_id` with other data (409), lock timeout (503, nothing stored), revoked membership (club corner denied).

## Fallbacks (honest)

| Failure | Fallback | What we say |
|---|---|---|
| Public host fails the host proof or its free-tier limits (HTTPS, persistence, CPU quota) | Second host option from research (Render + free Postgres), else laptop | "Running on our laptop; data is real and persisted locally, not yet publicly deployed" |
| SQLite "database is locked" errors during rehearsal | Shorten the failing transaction; if it persists, switch `DATABASE_URL` to Postgres | Report the observed errors; do not claim concurrency we did not measure |
| Child mode middleware unstable | Keep PIN gate, temporarily limit child mode to the 4 child pages via allow-list only | Same security claim must still pass counter-examples 3; if not, do not claim it |
| HTMX issues | Plain form POST + redirect (same views) | Slightly less smooth UI |
| Time runs out before club flow | Admin activates membership manually during demo | Code redemption shown as "next" |

Never replace the database with browser storage to "make the demo work".

## High-upside after P0 is stable (do not expand P0)

- Animated mascot reactions and confetti on achievements (Denis).
- Scripted onboarding dialogue: mascot asks interests, answers by buttons → rule-based book suggestions (P1).
- Visual reading map / book passport stamps (Denis, Vladimir).
- Russian UI (Vladimir).
- Mentor-side AI quiz drafts behind human approval (Deferred; architecture leaves room: new `quiz` app, no child-facing generation).
- Pitch: problem stats (PISA reading) to be verified before use; demo video as backup.
