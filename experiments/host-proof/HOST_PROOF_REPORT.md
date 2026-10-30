# Host Proof H1–H7 — evidence checkpoint (2026-10-30)

Issue: #11. Branch: `spike/host-proof-h1-h7`. **Status: H1–H7 accepted PASS for the synthetic demo host by the project lead (2026-10-30), with different evidence levels: H3/H4 corroborated by Render logs, H1/H2 manually reported, H5/H6/H7 explicitly accepted on the lead's authority after the implementer's PARTIAL findings. Missing measurements and real-device test details below remain UNKNOWN, and are not retrospectively invented. Decision: GO for synthetic host-proof spike only, NOT acceptance of the actual product deployment.**

## Scope and source integrity

This is an isolated synthetic Django probe in `experiments/host-proof/`, not the Gustul Cărților app, production settings, or a capacity benchmark. Evidence below is attributed either to the implementer's handoff or direct GitHub/Render connector inspection on 2026-10-30. No credentials, user data, internal database URL or secret values are in this document. The existing `utm-curs-i-orar-2027` service was not changed.

**Original probe commit:** `153a9e150c1c010626f700ea316eca2f8e9ae944`. Current live deploy is `9dec3198b55225fbc00a06dd7db1d4de12683be4`; the PR branch has subsequent evidence-only changes. The live deploy and PR head need not match.

## Current infrastructure (verified through Render)

- Workspace: `My Workspace`.
- Isolated free web service: `gustul-host-proof-h-20261030`, `srv-dbi8lc6i0phs73d5opk0`, Frankfurt, Python; branch `spike/host-proof-h1-h7`; automatic Git-triggered deploy **off**. URL: https://gustul-host-proof-h-20261030.onrender.com
- Separate free PostgreSQL 18: `gustul-host-proof-h`, `dpg-dbi8k4dg1s2s73ea9sag-a`, Frankfurt, status `available`, expires **2026-11-29 12:14 UTC**. Free DB is temporary; do not rely on it for long-term data.
- Initial Render build **succeeded** (Django 5.2.18, dj-database-url 2.3.0, psycopg 3.2.12, gunicorn 23.0.0). Initial deploy `dep-dbi8lcei0phs73d5oqfg` **failed** at 2026-10-30 12:17:31 UTC, exit 1, because `DATABASE_URL` was absent.
- **Recovery verified via Render connector, 2026-10-30 12:29:40 UTC:** After the user saved environment settings, deployment `dep-dbi8qsss728c73clq180` ran successfully for commit `a808b7f9a91afd781fc9cd838e3f0b4582231518`. Logs show successful Django auth/contenttypes/sessions migrations, Gunicorn listening on `0.0.0.0:10000`, and Render says `Your service is live`. This first confirmed startup and DB connection; subsequent Render access logs confirmed public browser requests from Windows and Android, and a manual cross-device value readback was reported after the 303 fix. No credential or database URL is exposed.
- Container log indicated `WEB_CONCURRENCY=1`; other CPU, latency, and IP header behavior not tested. Separate attempted read-only DB connector query was blocked by an empty external IP allowlist; this does **not** establish failure of the internal Render connection.

## H1–H7 status

| Check | Status | Evidence or remaining requirement |
|---|---|---|
| H1 HTTPS accessible on phone + laptop | **PASS (manual, user-reported)** | User reported H1 PASS on 2026-10-30. Earlier Windows curl validated TLS/HTTP 200 and browser logs included Android/Windows requests. Precise phone network mode, device and certificate-warning observation were **not separately described**; do not call this independently verified |
| H2 Manifest, service worker, Android install | **PASS (manual, user-reported)** | User reported H2 PASS on 2026-10-30. Previously checked: manifest/SW/PNG endpoints HTTPS 200 and correct MIME/dimensions. Device-install, standalone, SW control and offline subtest observations/screenshots were **not separately supplied**, so they are accepted only as a self-report, not independently reproduced; iOS remains NOT RUN |
| H3 Persist a database value through restart **and redeploy** | **PASS (manual, post-redeploy)** | User confirmed **Value: 35** after new deploy `dep-dbi93l0m7kps73c800k0` became **LIVE** at **12:48:21 UTC**, with Django `No migrations to apply` and new Gunicorn worker. Independent Render HTTP logs show Windows `GET /value/` **200** at **12:49:40 UTC** on the new instance after authentication; numeric value was observed by user, not captured in logs. This validates persistence through the deploy (which restarts the app). Separate standalone restart not tested |
| H4 Cross-device login / save / read | **PASS (manual, user-reported)** | User confirmed after hotfix: Android saved 35; Windows loaded 35 on refresh. Access logs corroborate Android POST 303 followed by GET 200 and Windows GET 200; payload contents are not logged, so 35 is user-observed, not independently read via SQL. Whether the phone used mobile data vs Wi-Fi is unverified |
| H5 Latency / cold-start / failure behavior | **PASS (project-lead acceptance, limited evidence)** | Lead explicitly marked H5 PASS (2026-10-30). Independently documented six laptop GETs, TTFB first 373.086 ms, subsequent 301.996–387.600 ms. No recorded phone save, remote authenticated POST or proven cold-start timing; accepted as a demo risk, not a benchmark |
| H6 Free-tier resource constraints | **PASS (project-lead risk acceptance)** | Lead explicitly marked H6 PASS (2026-10-30), accepting documented free-plan risk. Verified web/DB Free Frankfurt and DB expiration 2026-11-29; capacity, quota, billing settings and forwarded client-IP provenance still UNKNOWN |
| H7 Demo fallback rehearsal | **PASS (project-lead attestation; details not provided)** | Lead explicitly marked H7 PASS (2026-10-30), superseding the implementer's earlier PARTIAL status. The repo independently contains a local two-session/restart test and LAN runbook; exact later phone/LAN observation, date/time, network and readback details were not supplied, so physical rehearsal is not independently verified |

## Final project-lead acceptance (2026-10-30, after H5–H7 agent report)

The project lead stated **“всё pass, р5-7 можно мержить”** and authorized merging the Host Proof PR. Record H5, H6 and H7 as **PASS by project-lead acceptance**. This is a decision/attestation, **not new measurements**: the latest agent report had H5–H7 PARTIAL. In particular, it did not time a confirmed cold start or remote authenticated phone save, did not establish remaining Render hours/billing, and had not physically rehearsed phone↔laptop LAN. The project lead supplied no further measurements, device details or screenshots when granting acceptance. Do not infer them. Existing timings, limits and runbook remain the supported technical evidence.

**Scoped GO:** merge the isolated `experiments/host-proof/` research into `main` as completed infrastructure exploration; proceed with a separate full-product deployment/rehearsal decision. Render Free web and PostgreSQL Free are suitable only subject to their documented limits; database expires 2026-11-29 12:14 UTC and has no backups. Do not treat this as certification of the actual minors-facing app, actual PWA, security or reliability. A presentation-day fallback check remains recommended.

## H5–H7 follow-up (2026-10-30)

**H5 — observed on Windows laptop, 15:41:45–15:41:47 +02:00 (13:41 UTC):** `curl.exe -sS -o NUL -w 'status=%{http_code} dns=%{time_namelookup} connect=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total}' --connect-timeout 8 --max-time 70 https://gustul-host-proof-h-20261030.onrender.com/health/` was invoked once, then five consecutive times, each in a new curl process. All returned HTTP 200, exit 0, TLS verified. Values are milliseconds:

| Request | DNS | Connect | TLS complete | TTFB | Total |
|---|---:|---:|---:|---:|---:|
| First | 118.646 | 174.237 | 251.818 | 373.086 | 373.181 |
| 1 | 18.939 | 103.854 | 228.747 | 351.732 | 351.846 |
| 2 | 15.672 | 123.307 | 250.862 | 387.600 | 389.341 |
| 3 | 17.671 | 86.988 | 205.374 | 327.073 | 327.838 |
| 4 | 13.800 | 58.730 | 192.305 | 306.089 | 306.691 |
| 5 | 53.730 | 110.521 | 191.361 | 301.996 | 302.142 |

Connection timings are curl's cumulative timestamps, not independent phase durations. This is the first request in this measurement run, **not a proven cold start**; prior sleep was not established. Network type was not recorded. At 15:42 +02:00 an anonymous `curl.exe` GET `/value/` produced 302 to `/login/` and a POST `/health/` without CSRF produced 403. No authentication secret, POST value or database setting was read or changed. Remote authenticated POST/save timing and phone timing are **NOT RUN**; credentials were not accessed. The optional `verify_latency.py` asks for test credentials privately, checks that 35 is present, asks before writing the same 35 once, and reports POST plus readback duration. It must be run only when no other person is writing. Local-only testing verified login 303, POST 303, GET 200 and 35 readback; a non-35 baseline was refused with the value unchanged. An initial automated harness timed out because Windows `getpass` expected interactive input; a second run injected disposable test inputs locally and passed. These are not remote or phone timings. For a phone: time a normal `/health/` open and one synthetic save-to-visible-readback, then report both durations and device/network without secrets; do not call it a cold start unless prior sleep is evidenced.

**H6 — observed:** Render API on 2026-10-30 confirmed web Free, Frankfurt, one configured instance, active, auto-deploy off; PostgreSQL 18 Free, Frankfurt, available and expiry 2026-11-29 12:14 UTC. Previously observed boot logs reported one Gunicorn worker. On the web instance, Render metrics at **13:43 UTC** show CPU `0.0004045` CPU and memory `78,147,580` bytes; these are point-in-time observations, not a capacity or remaining-quota guarantee. A fresh log query returned HTTP 503 (logs temporarily unavailable); no new cold-start event was established. Remaining workspace free hours, billing settings, forwarded-IP trust chain, and DB filesystem remain UNKNOWN. Published free plan limits and sources are recorded below; docs rechecked 2026-10-30.

**H7 — local only:** `C:\Users\user\Documents\Impact-Host-Proof\.venv-host-proof\Scripts\python.exe experiments/host-proof/verify_local.py` exited 0: `PASS: localhost HTTP, two independent sessions, 17 -> 35, server restart -> 35`. User reported that a real phone is currently unavailable; physical LAN/hotspot check is **NOT RUN**. The new [fallback runbook](FALLBACK_RUNBOOK.md) uses an explicit local SQLite file outside Git and supersedes the older inline setup below. It includes phone acceptance, non-destructive diagnostics and laptop-only/video fallback. No recording has been made.

**10–15 minutes before presenting:** open `/health/` and confirm it responds; sign in and check `/value/`, optionally make one deliberate synthetic save and verify it; check PostgreSQL is available and not expired; prepare and rehearse the local fallback. Opening the service can wake it, but does not guarantee uptime or avoid another spin-down. Decide in advance whether to use the laptop-only demonstration or a separately prepared recording if the network fails.

## Human acceptance update (2026-10-30)

- Project lead explicitly reported **H1 = PASS** and **H2 = PASS** after the manual verification instructions. These statuses are recorded as **user-reported**, not as a second independent device/browser experiment.
- No device model, Chrome version, confirmation of mobile-data-only HTTPS, exact install/standalone steps, or offline-result details were supplied in that short status message; avoid inventing these specifics. Earlier independent HTTP assets/curl evidence is retained above.
- **Later decision:** Project lead subsequently accepted H5/H6/H7 as PASS for this synthetic infrastructure spike. Cold-start/phone-save measurements and physical fallback details are not available for independent reproduction, and free-plan billing/quota risk remains explicitly accepted.

## Cross-device value overwrite investigation (2026-10-30, 12:36 UTC)

- Render Gunicorn access logs show `POST /value/` with HTTP **200** from Android at **12:36:14 UTC**, followed by two `POST /value/` HTTP **200** from Windows at **12:36:19 UTC** and **12:36:24 UTC**. The server logs contain request paths and statuses, **not posted numeric values**.
- The original `value()` handler wrote on POST then returned HTML **200** rather than a redirect. Browser refresh on a POST result can resend the previous form. This is a strong explanation for the user reporting that the PC did not show the phone's value `35`: the PC appears to have sent subsequent writes; exact numeric overwrite remains **unverified**.
- **Fix pushed in** `1e4f6fb` and `a0383f9`: successful save returns **HTTP 303 `Location: /value/`**; successful login also returns 303 to the read page; GET value responses set **Cache-Control: no-store**. No domain contracts or unrelated services changed. A deployment was initiated for commit `a0383f9` (deploy `dep-dbi8vu6gekts7397eblg`). Render deployment **became live** at **12:40:32 UTC** for commit `a0383f9` (build and deploy succeeded). After rollout, logs show Android `POST /value/` **303** at **12:46:36 UTC**, automatic Android `GET /value/` **200** at **12:46:37 UTC**, and Windows `GET /value/` **200** at **12:46:39 UTC**. User confirmed Windows displayed `35`. **H4 passed at manual-evidence level**, without exposing numeric form payload in logs.
- Regression test after deploy: first browser save 17 → must navigate via GET and show 17; second device save 35 → first device **refreshes GET** and shows 35; no second POST from the first device on refresh. Then validate persistence across restart/redeploy.

## Recovery steps (do not put credentials into GitHub, logs, screenshots, or chat)

1. **DONE (user reported, operationally corroborated):** test database's **Internal Database URL** was configured as `DATABASE_URL` on the isolated test web service; the redeploy now runs migrations and Gunicorn. Both resources are in Frankfurt. Do not open the connection to the public internet.
2. In test service environment settings, verify `DJANGO_SECRET_KEY` has a random nonempty value. For reproducible password-protected smoke flows, set `PROOF_USERNAME` and a strong `PROOF_PASSWORD` (test-only values). Do not disclose any values. Verify or adjust `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` only if logs/request behavior require it; the probe already uses Render's `RENDER_EXTERNAL_HOSTNAME` / `RENDER_EXTERNAL_URL`.
3. **DONE:** Saving environment settings triggered a successful `service_updated` deployment on 2026-10-30 12:29:40 UTC, even though Git-triggered auto-deploy is off. **STILL NEEDED:** check `/health/`, `/manifest.webmanifest`, `/sw.js` over HTTPS on a real browser.
4. On **phone over mobile data** and laptop, use separate authenticated sessions at `/login/`, then `/value/`. Write 17 on device A and read 17 on B; write 35 on B and read 35 on A. Record date/time, HTTP outcomes and visibly observed readback. **No children's data.**
5. **Follow-up redeploy succeeded**: `dep-dbi93l0m7kps73c800k0` became LIVE at 12:48:21 UTC, same application code and documentation changes. **DONE, reported by user**: opened `/value/` in a fresh tab after the deployment, authenticated and saw `35` without writing again; Windows HTTP GET 200 at 12:49:40 UTC corroborated. This confirms the pre-redeploy stored value survived. An additional standalone restart-only test is optional but not performed.
6. Test Android Chrome installation, launch in standalone mode, graceful offline navigation / no offline writes. Record H5 measurements, resource limits, and H7 laptop backup rehearsal. Never claim a capacity benchmark from one user.

### Review gates

- **Reviewer scope:** H1–H7 statuses have now been accepted by the project lead for the synthetic hosting spike, not universally independently verified. Preserve raw observations and known gaps as written. Rehearse full actual Gustul Cărților product separately before presentation.
- **Current decision:** **CONDITIONAL**: Render has successfully deployed and started. **CONDITIONAL GO** for Render + PostgreSQL as an operational, HTTPS-served, cross-device persisted data backend for the hackathon demo, based on H3 and H4 manual observations. **GO** to merge the limited, synthetic host-proof findings, subject to GitHub review. **NO CLAIM** of independently measured cold-start, real-device fallback details, production readiness, or product-level security/PWA acceptance. H1/H2/H5/H7 include lead-reported acceptance without detailed device logs. This does not block M0.
- Probe is intentionally not production identity/child-mode logic. Its login and PWA shell do **not** prove minors' authorization, hardened production cookies or club entitlements.

## Follow-up evidence (2026-10-30)

**Observed:** Render connector reports DB `available`, free PostgreSQL 18, Frankfurt, expiry **2026-11-29 12:14 UTC**; web service free, one instance, auto-deploy off, deploy `dep-dbi93l0m7kps73c800k0` live at 12:48:21 UTC. The prior DB setup is corroborated by successful migrations and H3/H4 user observations; no environment secrets were read. Earlier failed deploy `dep-dbi8lcei0phs73d5oqfg` was followed by successful `dep-dbi8qsss728c73clq180` and later deployments. No recovery-time experiment was made.

At 14:56:21–14:56:32 +02:00 Windows `curl.exe` on laptop, normal network (network type not recorded), validated HTTPS without bypass and returned HTTP 200 for `/health/`. Three consecutive GETs with `curl.exe -sS -o NUL -w 'status=%{http_code} ttfb=%{time_starttransfer} total=%{time_total}' https://gustul-host-proof-h-20261030.onrender.com/health/` returned TTFB **360.960, 402.074, 329.428 ms**, total **361.069, 402.174, 329.563 ms**. This is not phone latency, a measured cold start, POST latency, an SLA, or a capacity test.

At 14:56:54 +02:00 Python `urllib.request` retrieved `/manifest.webmanifest` (200, `application/manifest+json`, `start_url=/value/`, `display=standalone`, two icons), `/sw.js` (200, `application/javascript`), and `/icon-192.png`, `/icon-512.png` (200, `image/png`; PNG IHDR 192×192 and 512×512). No browser installability, registration, control, or offline behavior was established by this asset inspection. The SW source only caches a fixed offline message, intercepts navigation GETs, and does not queue POSTs; actual device behavior remains untested.

**Documented, not load-tested:** [Render Free](https://render.com/docs/free) describes 15-minute idle spin-down, roughly one minute to spin up, loss of web filesystem writes on restart/redeploy/spin-down, 750 free instance hours per workspace/month, and a 1 GB free DB with 30-day expiry and no backups. [Compute plans](https://render.com/docs/compute-plans) list free web 0.1 CPU / 512 MB and free Postgres 0.1 CPU / 256 MB. Limits are shared with other services and overages can cause suspension or charges depending on billing settings; actual remaining quota and billing settings are unknown. Avoid background keep-alive: manually open the demo shortly before presentation, then verify it responds; this does not guarantee it stays warm. Render documents TLS termination at its load balancer and `X-Forwarded-For` for client IP ([web services](https://render.com/docs/web-services), [client IP discussion](https://render.com/articles/how-render-handles-ddos-attacks)); actual headers, trustworthy proxy chain, CPU usage, database backing filesystem and SQLite WAL suitability are **UNKNOWN**. SQLite on ephemeral Render web storage is unsuitable regardless of WAL. Free DB expiry must be checked against the actual, currently unknown presentation date.

**Local verification:** With the existing isolated Python 3.11 environment containing the pinned dependencies, `python experiments/host-proof/verify_local.py` completed with `PASS: localhost HTTP, two independent sessions, 17 -> 35, server restart -> 35`. It creates and removes a temporary SQLite DB, uses disposable credentials and does not touch the Render DB. `python experiments/host-proof/smoke.py check` returned `System check identified no issues (0 silenced)`; `python -m py_compile experiments/host-proof/smoke.py experiments/host-proof/verify_local.py` and `git diff --check` exited 0. This is not a phone or persistent-laptop-storage rehearsal.

### Rehearse fallback on Windows and a real phone

Use the same probe commit, a trusted local Wi-Fi or phone hotspot, and synthetic data. On the presenter laptop in PowerShell, replace `<LAN-IP>` with its actual IPv4 address on that network. Use a new local password and never paste it into the report or chat. The SQLite file `experiments/host-proof/smoke.sqlite3` is local persistent laptop storage; do not copy the Render connection string. The following starts the Django **development server for demo rehearsal only**:

```powershell
cd <repo-root>
python -m venv "$env:TEMP\impact-host-proof-venv"
$py = "$env:TEMP\impact-host-proof-venv\Scripts\python.exe"
& $py -m pip install -r experiments/host-proof/requirements.txt
Remove-Item Env:DATABASE_URL,Env:RENDER,Env:RENDER_EXTERNAL_HOSTNAME,Env:RENDER_EXTERNAL_URL -ErrorAction SilentlyContinue
$env:DJANGO_SECRET_KEY = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
$env:PROOF_USERNAME = 'synthetic'
$env:PROOF_PASSWORD = Read-Host 'Choose a disposable local password'
$lan = '<LAN-IP>'
$env:ALLOWED_HOSTS = "127.0.0.1,localhost,$lan"
& $py experiments/host-proof/smoke.py migrate --noinput
& $py experiments/host-proof/smoke.py init-value
& $py experiments/host-proof/smoke.py runserver "${lan}:8000" --noreload
```

On phone in the same LAN, open `http://<LAN-IP>:8000/health/`, then `/login/` and `/value/`, log in with the locally chosen credentials and save a synthetic number. On laptop open the same address, sign in and read it. Stop the server with Ctrl+C and rerun the final command in the same PowerShell session; read again. Record time, devices, network type, result and any blocker without passwords or IP addresses. Do not disable the firewall globally; if isolation blocks access, try the phone hotspot and repeat, or use a pre-recorded demo. Plain LAN HTTP does not establish secure-context PWA installation or offline guarantees.
