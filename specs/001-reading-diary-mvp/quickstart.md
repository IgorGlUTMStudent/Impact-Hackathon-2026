# Quickstart, demo script and verification plan

> No application code exists yet. Commands in §1 become valid after PR-1 (M0). Nothing below has been run; all checks are **NOT RUN**.

## 1. Local setup (after M0)

```bash
git clone https://github.com/Slave-of-Skynet/Impact-Hackathon-2026.git
cd Impact-Hackathon-2026
cp .env.example .env            # set DJANGO_SECRET_KEY, DEMO_PASSWORD, DEMO_PIN locally
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo --reset
uv run python manage.py runserver 0.0.0.0:8000
uv run pytest
```

Phone on the same network: open `http://<laptop-ip>:8000` (PWA install needs HTTPS — use the demo host for that).

## 2. Demo script (target < 3 minutes)

| Step | Device | Action | Expected |
|---|---|---|---|
| 1 | Laptop | Sign in as demo guardian → "Familia mea" | Children Mia and Alex listed, private |
| 2 | Phone | Same guardian → Mia → "Mod copil" | Child home with mascot "Salut!" |
| 3 | Phone | Catalog → book card → "Adaugă în raft" | Book in "Citesc acum", 0/120 |
| 4 | Phone | "Am citit până la pagina" 35 → Save | Bar 29%, mascot "Bravo! Ai ajuns la pagina 35." |
| 5 | Laptop | Reload Mia's report | 35/120, pages last 7 days = 35 |
| 6 | Phone | "Am terminat cartea" | "Prima carte" badge; club badge shown locked "pentru membrii clubului" |
| 7 | Laptop | "Cod de club" → code for Mia | "Membru al clubului până la …" |
| 8 | Phone | Achievements / Clubul meu | "Cititor de Club" unlocked; club activities visible |
| 9 | Phone | Type `/panou/` in the address bar | PIN gate, not the adult dashboard |

P0 smoke outside the stage script (US4/US5): logged-out browser opens `/carti/` → catalog visible; "Adaugă în raft" → sign-in page. Seeded adult without children signs in → adds a book → saves a page → finishes it → `/panou/` shows own shelf and totals.

## 3. Security counter-examples

Each item names the check that will confirm it. Status column stays **NOT RUN** until the check is executed and its real output is attached to a PR.

| # | Counter-example (must be impossible) | Automated test (planned) | Manual check | Status |
|---|---|---|---|---|
| 1 | Another guardian reads/changes a child's progress by swapping IDs | `test_authz.py::test_foreign_child_report_404`, `::test_foreign_entry_progress_404` | Copy Mia's report URL into guardian B's browser → 404 | NOT RUN |
| 2 | A regular reader grants themselves a club badge from the browser | `test_achievements.py::test_non_member_never_gets_members_only`, `::test_no_grant_endpoint_exists` (URL resolver scan) | DevTools: replay progress POST with extra fields → no club grant | NOT RUN |
| 3 | Child on a shared device reaches parent settings by tapping/typing | `test_child_mode.py::test_adult_routes_redirect_to_pin_gate` (parametrized over **all** URL names from the resolver that are not in `CHILD_ALLOWED`, so new routes are covered automatically), `::test_pin_gate_rejects_password`, `::test_pin_lockout_after_5`, `::test_correct_pin_refused_while_locked`, `::test_logout_recovery_ends_session` | Type `/panou/`, `/familie/`, `/club/cod/`, `/admin/` in child mode; enter a wrong PIN 5×; use "Am uitat PIN-ul" and check `/panou/` then asks for email + password | NOT RUN |
| 4 | A minor's profile is public or appears in a ranking/feed | `test_authz.py::test_no_public_profile_routes` (URL resolver has no public reader/child route) | Logged-out browser: no route exposes nicknames | NOT RUN |
| 5 | Repeated or concurrent requests double books or awards | `test_concurrency.py::test_replay_same_request_id_returns_prior_result`, `::test_reused_request_id_with_other_page_is_409`, `::test_two_request_ids_same_entry_commit_order`, `::test_finish_race_counts_once`; `test_achievements.py::test_grant_unique` | Double-tap Save on a slow network (DevTools throttling); save from two tabs at once | NOT RUN |
| 6 | Parent sees only UI state, not stored progress | `test_demo_flow.py` uses two separate clients | Reload + second device (demo step 5) | NOT RUN |
| 7 | Network error shown as saved | — (client behaviour) | DevTools offline → Save → toast "Nu s-a salvat", bar unchanged after reload | NOT RUN |
| 8 | Hard-coded Russian (or untranslated) strings in the Romanian UI | `test_i18n.py::test_templates_have_no_cyrillic` (scan `templates/`) | Browse all P0 screens in `ro` | NOT RUN |
| 9 | Demo needs real minors' data or unlicensed content | `test_seed.py::test_seed_is_synthetic` (fixed nicknames, no emails outside `demo.local`, no cover image URLs) | Review seed file in PR | NOT RUN |
| 10 | Stack / module count unrealistic for remaining time | — | M0 exit criterion met within its time box; otherwise trigger fallbacks in execution plan | NOT RUN |
| 11 | Expired session or refused request looks like a saved write | `test_child_mode.py::test_htmx_mutation_without_session_is_401_no_partial`, `::test_htmx_mutation_after_session_expiry_stores_nothing`, `::test_htmx_adult_route_in_child_mode_is_403`, `::test_saved_trigger_only_after_commit` | Delete the session cookie in DevTools → Save → "Nu s-a salvat", then sign-in; reload shows the old value | NOT RUN |
| 12 | Unlimited guessing of password, PIN or membership code | `test_login_throttle.py` (5 cases), `test_child_mode.py::test_pin_lockout_after_5`, `test_membership.py::test_redeem_failures_throttled` | 6 wrong logins → 429 even with the right password; same for PIN (5 min) and codes | NOT RUN |
| 13 | Database busy makes a save half-applied or falsely "saved" | `test_concurrency.py::test_lock_timeout_returns_503_and_stores_nothing` | — | NOT RUN |

Host and performance evidence is tracked separately in the [host proof](./execution-plan.md#host-proof-separate-critical-path-activity) (H1–H7, all NOT RUN).

## 4. Validation commands for this architecture PR

```bash
git diff --check
specify integration status        # must report default/installed: none
```
