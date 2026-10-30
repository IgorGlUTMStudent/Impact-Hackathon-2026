# Research: stack and hosting for the P0 slice

**Date**: 2026-10-30 · **Feature**: [spec.md](./spec.md) · Facts marked ✅ were checked against the cited page on this date; ⚠️ means a third-party or unconfirmed source; ❓ means not verified.

## 1. Inputs that constrain the choice

- `[TEAM DECISION]` One responsive, installable PWA; Romanian first; server-side authorization for children and membership; no payments; no AI dependency in P0.
- `[TEAM INPUT — UNCONFIRMED]` "We write everything in Python" (one teammate's chat message, 2026-10-30). It is **not** a team decision and is not used as a reason to reject any option below. Stack was independently reviewed in PR #8 and **approved by the team lead at G7 on 2026-10-30** ([spec.md](./spec.md#decision-gates-blocking-items-need-answers-before-freezing)).
- Five developers working in parallel with AI agents (Claude Code, Codex, Antigravity), unknown remaining hackathon time `[UNKNOWN]`.
- The club must be able to take over the code later `[PARTNER REPORTED 19:20–19:33]`.

## 2. Options compared

| Criterion | **A. Django 5.2 LTS monolith + server-rendered templates + HTMX** | B. FastAPI + SQLAlchemy/SQLModel + Jinja2/HTMX | C. Next.js (TypeScript) + Supabase (Auth + Postgres RLS) | D. Python UI frameworks (Flet / Reflex / NiceGUI) |
|---|---|---|---|---|
| Language | Python | Python | TypeScript | Python |
| Auth, sessions, CSRF, password hashing | Built in | Must assemble (libraries + own glue) | Managed service | Varies; mostly own glue |
| Admin back office (membership codes, revoke, catalog) | **Built-in Django admin** — near zero work | Must build | Supabase dashboard (not club-friendly) or build | Must build |
| Server-side authorization model | Views + one `authz` module; tests with Django test client | Dependencies per route; own tests | RLS policies in SQL — powerful but easy to get subtly wrong under time pressure | State lives on server websockets; unusual model |
| Migrations, seed data | Built in (`makemigrations`, fixtures/management command) | Alembic, extra setup | Supabase migrations | Varies |
| PWA on phones | Plain HTML + manifest + small service worker | Same as A | Strong (Next PWA tooling) | Weak: Flet web renders on canvas (heavy, poor accessibility); Reflex/NiceGUI need persistent websocket |
| Parallel work for 5 | Django apps = natural module boundaries; templates can be built against documented context | Similar, more shared glue code | Good, but frontend/backend split by language | Poor: UI and state tightly coupled |
| AI-agent friendliness | Very high: mature, heavily documented, conventional layout | High | High | Lower: newer, less training data, fast-changing APIs |
| Handover to club | One repo, one process, one DB file or Postgres | One process + more custom code | Two vendors (Vercel-like host + Supabase) | Niche framework |
| Third-party risk in hackathon | Low (no external service needed to run) | Low | Medium: service limits/config, keys | Medium |

**Team-approved implementation choice (G7, 2026-10-30): Option A — Django 5.2 LTS + HTMX, server-rendered, installable PWA, one canonical style (HTML forms + HTMX partials, no parallel JSON API in P0).**

Rationale, on the merits for this hackathon and independent of any language preference: the riskiest parts of this product are *authorization* (guardian ↔ child, child mode, membership) and *persistence*. Django gives sessions, CSRF, password hashing, ORM constraints, migrations and an admin back office out of the box, so the team writes product logic instead of security plumbing. The club admin needs a back office on day one, and Django admin covers it with almost no work. Everything runs in one process with one database, which makes AI-assisted debugging, deployment and handover simple. HTMX keeps the UI responsive (progress updates without full reloads) while every state change still goes through the server.

Not recommended: **B** duplicates what Django provides (auth/admin) with more custom security code. **C** is a credible option, but needs two vendors to run, a back office built from scratch, and authorization written as RLS policies the team has not tested, which is the riskiest place to be wrong under time pressure. **D** weakens the PWA/mobile story and parallel UI work. Option C remains a documented alternative, but would require a new team architecture decision to replace the approved stack. Note: the Flet suggestion made earlier in chat (before the PWA requirement and review checklist were known) is withdrawn for these reasons.

Versions: Django 5.2 is an LTS release supported until April 2028 ⚠️ ([endoflife.date](https://endoflife.date/django)); Django 6.0 is supported only until April 2027 ⚠️. Pin `Django>=5.2,<5.3`. Python 3.12. HTMX 2.x vendored as a static file (no CDN dependency at demo time). Exact patch versions to be pinned in the first implementation PR via `uv lock`.

## 3. Storage

- **SQLite** for local development and for the demo host if it has a persistent disk; schema written to stay **PostgreSQL-compatible** (no SQLite-only features). Switching is a settings change (`DATABASE_URL`).
- SQLite allows **one writer at a time** (whole-database lock) and `select_for_update()` has no effect on it ✅ ([Django docs](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update)). Django ≥ 5.1 can open transactions as `IMMEDIATE` so writers wait up to `timeout` instead of failing mid-transaction ✅ ([Django SQLite notes](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes)). P0 policy: [data-model.md § Concurrency](./data-model.md#concurrency-and-idempotency-p0-policy). No concurrent-user capacity is claimed.
- WAL mode is used only on a local disk; SQLite WAL does not work over network filesystems. Whether the free host's disk is local is unknown ❓ until the host proof. Until then, the default rollback journal is used.
- Uniqueness and range invariants are enforced by **database constraints**, not only by forms (see [data-model.md](./data-model.md)).

## 4. Hosting options for the public demo (gate G6)

| Option | Facts | Fit |
|---|---|---|
| **PythonAnywhere free** (first candidate to try; not verified) | 1 web app with **1 web worker** and 1-month expiry, **100 CPU seconds**, 512 MiB disk ✅ ([help page](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), checked 2026-10-30); outbound internet restricted to an allowlist ⚠️ ([blog](https://blog.pythonanywhere.com/221/)). Persistent file system (SQLite survives restarts) ❓, HTTPS on the free subdomain ❓, cold starts ❓, whether the disk is network-backed ❓ — all checked by the host proof | Possible if the host proof passes. One worker means requests are served one at a time, and the CPU quota can run out during heavy testing. Not a high-concurrency plan |
| Render free web service + Render free Postgres | Free web services have an **ephemeral** filesystem — SQLite is lost on redeploy/restart/spin-down ✅; free Postgres **expires 30 days** after creation, 1 GB, no backups ✅ ([render.com/docs/free](https://render.com/docs/free)); idle spin-down cold start ❓ | Acceptable for a hackathon only with Postgres; cold start risk on stage |
| Team VPS (if any member provides one) | Unknown `[UNKNOWN]` | Best control if available |
| **Fallback — local laptop** | `runserver`/`gunicorn` on the presenter laptop, phone on the same network (or a tunnel). Data persists in the laptop's SQLite file — real persistence, but **not a public deployment** | Always available; say so honestly in the pitch |

No host is chosen until one passes the **host proof** (evidence checklist in [execution-plan.md](./execution-plan.md#host-proof-separate-critical-path-activity)). The host proof is a separate critical-path activity started immediately, not a final-hour step.

## 5. PWA approach

- `manifest.webmanifest` (name, icons, `display: standalone`, theme color), served from the site root.
- Minimal service worker: cache static assets and an `/offline/` page; **network-only for all HTML and POST requests** — no background sync, no offline queue, so nothing is ever falsely shown as saved.
- HTMX error hooks show "Nu s-a salvat" on network or server errors.

## 6. Security building blocks (all built-in unless noted)

- Django auth (PBKDF2 password hashing), session cookies (`HttpOnly`, `Secure` in prod, `SameSite=Lax`), CSRF middleware (HTMX sends the token via `hx-headers`).
- PIN stored with Django's password hashers (`make_password`); failed attempts counted per account in the database; lockout stored server-side.
- Membership codes: random 10-character code shown once to the admin, stored as a hash; constant-time lookup via hash; failed redemptions throttled per account.
- Throttling is **not** built in: stock Django `LoginView` has no rate limit. P0 adds one small DB table (`accounts.Throttle`) and helper (`accounts/throttle.py`) used by three separate limits: login, PIN, code redemption ([authorization.md](./contracts/authorization.md#brute-force-limits-three-separate-throttles)). No extra service; a database instead of a per-process cache, so counters survive restarts.

## 7. Open technical unknowns

- ❓ HTTPS, disk persistence, local vs network disk, client-IP header and observed latency on the candidate host — verify in the host proof.
- ✅ Final stack sign-off — **G7 approved by team lead, 2026-10-30**.
- ❓ Brand assets (logo, mascot) availability — G6; until then use a neutral placeholder mascot drawn by the team.
- ❓ Hackathon deadline and judging format — affects how much P1 is attempted.
