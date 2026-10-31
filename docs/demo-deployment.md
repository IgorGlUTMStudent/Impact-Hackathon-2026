# Real product deployment — Render + persistent PostgreSQL (issue #34)

**Status: CODE_READY (2026-10-31).** This is the reproducible deployment contract and evidence ledger —
**not** a proof of a live deployment. HOST_LIVE and PERSISTENCE_VERIFIED require the Render owner's
actions (decision gate §3). Executor: GLM agent. Render operator and acceptance owner: Владимир.
Independent review: ChatGPT project brain. Device/browser acceptance is issue #35, deliberately separate.

## 1. Base and commits

| Item | Value |
|---|---|
| Base | `main` @ `5bad4d39486678c73e0343638585ef3c87ae5e96` (post-#33 E2E merge; CI run 41127164520: 366 passed, 4 pre-existing optional skips) |
| Branch | `feat/issue34-real-django-deploy` |
| Deployed commit | **none** — no product service exists yet (NOT CREATED) |

## 2. Render workspace state (verified 2026-10-30, per issue #34 and `experiments/host-proof/HOST_PROOF_REPORT.md`)

- Web service `gustul-host-proof-h-20261030` (`srv-dbi8lc6i0phs73d5opk0`, Frankfurt, free, branch
  `spike/host-proof-h1-h7`, auto-deploy off) — **synthetic probe, not the product**; must not be converted into it.
- Free PostgreSQL `gustul-host-proof-h` (Frankfurt, expires 2026-11-29 12:14 UTC, no backups).
- `utm-curs-i-orar-2027` exists and stays **untouched**.
- No service runs the real Gustul Cărților app.

## 3. DECISION_REQUIRED — Владимир (Render owner)

Render Free allows **only one free PostgreSQL per workspace** ([render.com/docs/free](https://render.com/docs/free), checked 2026-10-30), and the workspace's slot is already occupied by the host-proof DB. Options:

- **A (preferred candidate — availability NOT guaranteed):** a new separate Hobby workspace under
  Владимир's account (e.g. `gustul-demo`). It would carry its own free quotas (one free Postgres + 750
  free instance hours per month) and full isolation from the probe and from `utm-curs-i-orar-2027`.
  Workspace creation in Render can include a plan/payment-method step
  ([render.com/docs/team-members](https://render.com/docs/team-members) — up to five Hobby workspaces,
  billing details confirmed during creation), so this is **not** an automatic zero-cost guarantee:
  Владимир must verify in his own Render UI the actual plan, that a second free PostgreSQL is permitted,
  and that no charge can be triggered — and only then create anything. The agent creates no workspaces,
  services or databases without that explicit owner approval.
- **B:** a paid PostgreSQL in the current workspace (cost decision gate; verify current pricing).
- **C:** an external free Postgres provider (Neon/Supabase) — introduces a new vendor (decision gate).
- **Not allowed without a separate explicit decision:** reusing `gustul-host-proof-h` (experimental tables),
  touching `utm-curs-i-orar-2027`, deleting or recreating any existing resource.

Free-tier facts to plan around ([render.com/docs/free](https://render.com/docs/free), checked 2026-10-30):
free DB expires **30 days after creation** (14-day grace, then deletion; record the exact expiry date at
creation), 1 GB, no backups; the web service spins down after 15 idle minutes (~1 min to wake); free web
services have **no shell/SSH** (one-off commands run from the operator laptop, §7); 750 free instance
hours/month per workspace.

## 4. Target infrastructure (`render.yaml`, repo root)

- Web service `gustul-cartilor` — runtime `python`, plan `free`, region `frankfurt`, health check
  `/healthz/`, branch `main`, auto-deploy on commit.
- PostgreSQL `gustul-cartilor-db` — plan `free`, region `frankfurt` (database name `gustul_cartilor`).
  Region is fixed at creation and cannot be changed later.
- The database entry sets **`ipAllowList: []`** (deny-by-default): external connection attempts are
  refused, and the only client is the web service itself through Render's **internal** connection string
  injected as `DATABASE_URL` — same-region service↔DB internal connectivity works with an empty
  allowlist ([blueprint spec](https://render.com/docs/blueprint-spec),
  [creating & connecting](https://render.com/docs/postgresql-creating-connecting)). This is configuration
  for future provisioning, **not** evidence of an actually closed host: service and DB do not exist yet.
- `DATABASE_URL` is injected into the service from the database connection string by the blueprint.

Commands, stages kept separate (no single unconditional blob):

| Stage | Command |
|---|---|
| build | `uv sync --frozen --extra postgres --no-dev && uv run --no-sync python manage.py collectstatic --noinput` |
| start | `uv run --no-sync python manage.py migrate --noinput && uv run --no-sync gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60` |

Notes:

- Render's Python native runtime supports `uv` when `uv.lock` exists at the repo root
  ([changelog 2025-06-12](https://render.com/changelog/added-uv-to-the-python-native-runtime)); Python 3.12
  is pinned by `.python-version` + `requires-python = ">=3.12,<3.13"` in `pyproject.toml`, independent of the
  image default. If Render's UI still asks for a Python version, set the full `PYTHON_VERSION` (any 3.12.x).
- Service env vars are available at build time on native runtimes, so `collectstatic` (WhiteNoise
  `CompressedManifestStaticFilesStorage`) can run in the build step.
- `migrate` runs in the start command right before gunicorn — safe for one instance, idempotent
  ("No migrations to apply" on redeploys). The same proven pattern started the host-proof deploy
  successfully. Render's `preDeployCommand` is the documented alternative if preferred.
- **No `seed_demo` and no `--reset` anywhere in build/start.** Redeploys never re-seed and never touch
  demo PINs/passwords/progress/achievements.

## 5. Environment variables (names only — values live only in Render)

| Variable | Value / source |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `DJANGO_SECRET_KEY` | generated by Render (`generateValue: true`); stable across deploys |
| `DATABASE_URL` | from the **internal** `gustul-cartilor-db` connection string (the external URL stays unused; the allowlist is empty) |
| `DJANGO_ALLOWED_HOSTS` | exact public hostname, e.g. `gustul-cartilor.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | matching `https://` origin |
| `DEMO_PASSWORD` / `DEMO_PIN` | deliberately **not** stored on the service — one-time seed from the operator laptop (§7) |

`config/settings/prod.py` also appends Render's auto-provided `RENDER_EXTERNAL_HOSTNAME` /
`RENDER_EXTERNAL_URL` to `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` as a safety net (owner review requested,
§12). Security posture (asserted by tests, §8): `DEBUG=False`, `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER` (Render terminates TLS), HSTS 3600;
`/_preview/…` is DEBUG-only (both the URLconf gate and the view's own check); `/healthz/` returns
`{"status":"ok","db":true}` after a real `SELECT 1`.

## 6. D34 stage ledger — honest status

| Stage | Status | Evidence / what remains |
|---|---|---|
| D34-01 isolated infra + real PostgreSQL via `DATABASE_URL` | **PREPARED / BLOCKED (decision gate §3)** | guard implemented and tested (§8); service and DB NOT CREATED; live PostgreSQL routing NOT VERIFIED |
| D34-02 reproducible build/start | **PREPARED** | commands validated locally with prod settings (§8); actual Render build NOT RUN |
| D34-03 secrets, HTTPS, sessions | **PREPARED** | settings guard + probe tests pass (§8); live HTTPS/cookies/CSRF on the public domain NOT RUN |
| D34-04 demo seed + staff club code | **MANUAL_REQUIRED** | procedure written (§7); NOT RUN |
| D34-05 external HTTPS smoke of the real app | **NOT RUN** | checklist §9 |
| D34-06 real devices + local fallback | **MANUAL_REQUIRED** | device part belongs to #35; fallback runbook §10 |

## 7. One-time demo seed and club-code workflow (operator, after first deploy)

1. In the Render dashboard, add the operator's **exact** external IPv4/IPv6 (or a narrow CIDR) as a
   temporary entry in the database **Access Control** — the allowlist is otherwise empty
   (`ipAllowList: []`, §4). Never use `0.0.0.0/0` and never leave the database open for demo convenience.
   The one-time seed connects through the database's **external** URL from the operator's laptop.
2. From the laptop (repo checkout; `uv sync --frozen --extra postgres` — the seed connects to PostgreSQL
   and needs the psycopg driver), run the seed **once**. Values live in this PowerShell session only and
   are never committed or pasted anywhere:

   ```powershell
   $env:DATABASE_URL = '<DB external URL>'   # session-local; never publish this value
   $env:DEMO_PASSWORD = Read-Host 'Demo password'
   $env:DEMO_PIN      = Read-Host 'Demo PIN (4-6 digits)'
   uv run --no-sync python manage.py seed_demo
   Remove-Item Env:DATABASE_URL, Env:DEMO_PASSWORD, Env:DEMO_PIN
   ```

   Expected counter output: `demo_accounts=4, children=2, readers=5, books=12, achievements=3, activities=2`.
   `seed_demo` without `--reset` is idempotent and never prints credentials (tested).
3. Remove the temporary IP entry in the Render dashboard and **verify the allowlist is empty again**
   (the `ipAllowList: []` state). The service↔DB connection is internal and unaffected by this.
4. Club code: sign in at `https://<host>/admin/` as `admin@demo.local` (seeded staff) → MembershipCode →
   Add; hand the code to the parent privately. The app neither logs nor reflects the code, and
   `seed_demo` never creates codes (tested). Admin can add codes but not edit or delete them (read-only admin).

Never run `seed_demo --reset` against the demo host afterwards: it deletes demo children's shelves,
progress and grants.

## 8. Local verification actually executed (this branch, 2026-10-31, Windows 10.0.26300, Python 3.12.13, uv 0.11.24)

| Command | Result |
|---|---|
| `uv sync --frozen` | OK (locked graph); `uv sync --frozen --extra postgres` additionally installs `psycopg-binary 3.3.6` (mirrors the Render build) |
| prod env (synthetic secret/hosts/origin, `DATABASE_URL=postgres://synthetic:synthetic@localhost:5432/synthetic`): `uv run --no-sync python manage.py collectstatic --noinput` | `148 static files copied … 440 post-processed` |
| same env: `uv run --no-sync python manage.py check --deploy` | only `security.W005` + `security.W021` (HSTS subdomains/preload — deliberate demo-host choices); with the short synthetic key `security.W009` also fires and disappears with a 50+ char real key |
| `uv run pytest tests/test_prod_settings.py -v` | **8 passed** |
| `uv run pytest tests/test_foundation.py tests/test_prod_settings.py -q` | **23 passed** |
| full `uv run pytest -rs` | see §11 |
| `uv run python manage.py check` | no issues (0 silenced) |
| `uv run python manage.py makemigrations --check --dry-run` | No changes detected |
| `git diff --check` | clean |

Known Windows-only, pre-existing: the 4 subprocess tests in `tests/test_review_fixes.py` fail locally in a
minimal-environment interpreter (documented in `docs/deploy-club-integration.md`); Ubuntu CI is the source
of truth for them. No skips or xfails were added.

CI interlock (found by the first CI run on `494950f`, run 41139115030): the two WSGI regression probes in
`tests/test_review_fixes.py` predated the new prod contract — without `DATABASE_URL` the new guard now
fails the process before the secret-key guard. They now carry a synthetic PostgreSQL `DATABASE_URL`
(docs §12), and CI installs `--extra postgres` so the prod-start probe has the psycopg driver, exactly
like the deployment build. Final run counts: see the PR description.

## 9. D34-05 external HTTPS smoke checklist + persistence ledger (to execute on the live host)

Record HTTP status, observed values and timestamps for each step. No DSNs, credentials, session cookies,
PINs or children's personal data in the report.

1. `GET /healthz/` → `200 {"status":"ok","db":true}`.
2. `GET /carti/` → `200` with the real seeded catalog (12 books incl. "Capra cu trei iezi", 120 pages) — not a host-proof page.
3. Guardian A (`parinte1@demo.local`) logs in at `/cont/intrare/`, lands on `/panou/`; PIN flow works; enter child mode for Mia → `/copil/`.
4. Add "Capra cu trei iezi" to the shelf; POST progress **page 35** through the real form (CSRF); the mascot confirms the save.
5. Guardian B (independent login, second browser/profile) refreshes → sees **35/120**.
6. Trigger a real Render restart (if supported) and a separate redeploy (new deploy id) **without any new write**; Guardian A refreshes → still **35/120**. Fill the ledger below (`restart NOT RUN` must be stated if only redeploy is checked).
7. Finish the book → `first-book` achievement; redeem the staff-issued code for the child → `club-reader` badge and `GET /clubul-meu/` → 200; a non-member gets 403.
8. `GET /manifest.webmanifest`, `/sw.js`, `/offline/` and one static asset → 200 with correct MIME/scope.
9. Log in again later: no `DisallowedHost`, no HTTPS redirect loop, CSRF intact, secure cookies kept.

Persistence ledger (fill during live verification):

| Check | Before | Restart/deploy id | After | Evidence |
|---|---|---|---|---|
| page 35/120 readable by second guardian | | | | |
| page 35/120 after restart | | | | |
| page 35/120 after redeploy | | | | |

## 10. Local fallback runbook (only if the host fails before the demo) — Windows PowerShell

Real Django with `config.settings.dev` and one disposable SQLite file **outside the repository**. The
production `DATABASE_URL`, PostgreSQL and `config.settings.prod` are never used here. Status: the
file/path mechanics of Mode A below were executed once on the development machine (2026-10-31: directory
created under `$env:LOCALAPPDATA`, one `DATABASE_URL` for `migrate` → `seed_demo` → dev server, identical
`DATABASES['default']['NAME']` before and after, `curl` on `/healthz/` and `/carti/`); the browser
two-profile script and a **physical phone-LAN rehearsal have NOT RUN**.

### Mode A — laptop-only (the normal fallback)

Run every line in **one and the same PowerShell window**: the environment lives in the session, and
`migrate`, `seed_demo` and `runserver` must all see the same `DATABASE_URL`.

```powershell
# 0. From any checkout of this repository:
cd <repo-root>

# 1. Disposable database directory outside the repository (safe to re-run).
$dir   = Join-Path $env:LOCALAPPDATA 'GustulDemoFallback'
New-Item -ItemType Directory -Force $dir | Out-Null
#    Path format dj-database-url parses on Windows: sqlite:/// + forward slashes.
$dbUrl = 'sqlite:///' + (Join-Path $dir 'demo.sqlite3').Replace('\', '/')

# 2. ONE environment for everything that follows:
$env:DJANGO_SETTINGS_MODULE = 'config.settings.dev'   # never config.settings.prod here
$env:DATABASE_URL           = $dbUrl                  # never the production PostgreSQL URL
$env:DEMO_PASSWORD          = Read-Host 'Disposable demo password'
$env:DEMO_PIN               = Read-Host 'Disposable demo PIN (4-6 digits)'

# 3. Install the locked dependencies, then verify the target BEFORE writing anything:
uv sync --frozen
uv run python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
#    Must print the same $dir path (forward slashes, as constructed above); the file may not exist yet.

# 4. Prepare and launch (no seed_demo --reset anywhere, DATABASE_URL never changed):
uv run python manage.py migrate --noinput
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8000
```

In two independent browser profiles on the same laptop, replay the #33 script at
`http://127.0.0.1:8000` (child saves page 35; the guardian sees it after refresh). This is the normal
fallback; it is **not** a phone-LAN test.

After stopping the server (Ctrl+C), in the same window and session, confirm every process used the same
file:

```powershell
uv run python manage.py shell -c "from django.conf import settings; from apps.library.models import Book; print(settings.DATABASES['default']['NAME'], Book.objects.count())"
# Same path as in step 3 and 12 books → server, seed and checks shared the one outside-repo SQLite.
```

### Mode B — phone + laptop LAN (optional, trusted network only)

Only if a phone must join. In the same session, **before** step 4 of Mode A: add the laptop's private
IPv4 with `$env:DJANGO_ALLOWED_HOSTS = '<LAN-IP>'` (dev.py appends it), bind with
`uv run python manage.py runserver 0.0.0.0:8000`, and open `http://<LAN-IP>:8000` on the phone in the
same trusted Wi-Fi/hotspot. Firewall: if Windows asks, allow inbound **TCP 8000 for the Private profile
only** — never disable the firewall globally and never forward the port to the internet. A plain-HTTP LAN
origin is not a secure context: PWA installation and the service worker can be unavailable, so this
proves neither HTTPS nor PWA installability.

**Never** point the fallback at the production `DATABASE_URL`, and record exactly what was actually run.

## 11. Tests and CI

- Local full suite (2026-10-31, this branch, Windows): **370 passed, 4 failed, 4 skipped** — the 4 failures
  are the pre-existing Windows-only subprocess tests in `tests/test_review_fixes.py` (§8); the 4 skips are
  the pre-existing optional UI-integration skips. No new skips/xfails.
- Confirmed CI snapshot on the pre-fix head `40f0d59ed48e175d407fc3d3b50bdde4f9872095`:
  [run 41139884310](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41139884310) —
  **374 passed, 4 skipped, 0 failed** (Ubuntu). CI for each later head is linked in the PR description
  and never substituted for this snapshot.

## 12. Owner-review notes (cross-owner changes in this PR)

`config/settings/prod.py` (prod-only; flagged for foundation/accounts owner review):

1. **Fail-closed `DATABASE_URL` guard, checked before base settings load.** An unset or empty-but-present
   `DATABASE_URL` now raises a clear `ImproperlyConfigured` instead of falling back to local SQLite.
   Background: `dj_database_url.config()` returns `{}` for an empty-but-set variable, which made
   `base.py` crash with `KeyError: 'ENGINE'` — a pre-existing landmine this guard also fixes.
2. **SQLite refusal:** an explicit `sqlite://` `DATABASE_URL` in prod raises (ephemeral host disk).
3. **Render host auto-append:** `RENDER_EXTERNAL_HOSTNAME` / `RENDER_EXTERNAL_URL` are appended to
   `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` when present; explicit env values still take precedence.
   Dev/test SQLite behaviour is unchanged (tested).

`tests/test_foundation.py` — `test_prod_settings_are_safe` previously asserted prod's SQLite fallback
(`transaction_mode == "IMMEDIATE"`); under the new contract it asserts the PostgreSQL engine and no SQLite
options. `test_prod_settings_require_secret_key` pins a valid `DATABASE_URL` so the raised error is the
secret-key guard.

`tests/test_review_fixes.py` — the two WSGI regression probes now carry a synthetic PostgreSQL
`DATABASE_URL`: the fail-closed probe must exercise the *secret-key* guard (not the new database guard),
and the prod-start probe starts on a PostgreSQL engine. The latter needs the psycopg driver, so
`.github/workflows/django-checks.yml` now runs `uv sync --frozen --extra postgres`, mirroring the
production build command. The dev-settings probe and `manage.py diffsettings` probe are unchanged.

`render.yaml`, `tests/test_prod_settings.py`, `docs/demo-deployment.md` are new files; no models,
migrations, public URLs or authz/club contracts changed.

## 13. Handoff

- **Владимир:** decide §3, provision per §4–§5, run §7 once, then execute §9 and fill the persistence
  ledger; hand devices/PWA rehearsal to #35 with Денис.
- **ChatGPT project brain:** independent review of this PR, especially §12.
- The PR stays open with `Refs #34` (not `Closes`); no self-merge; the product service switches to `main`
  only after this PR is merged and CI is green, with Владимир's final coordination.

## 14. Cross-reference: synthetic persistence proof (#43, 2026-10-31)

Issue #43 was revised to a **synthetic-only** scope: `scripts/synthetic_persistence_check.py`
proves the real Django routes persist `35/120` into a disposable file-backed SQLite database
across a writer→reader process boundary (evidence: `docs/qa/issue-43-synthetic-persistence.md`).
This adds no evidence to the #34 ledger: live Render restart/redeploy persistence on the real
PostgreSQL host remains **NOT VERIFIED** until the §9 ledger is filled.
