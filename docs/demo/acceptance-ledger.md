# Acceptance ledger — verificări manuale demo (P0)

Reguli:
- O linie trece din `NOT RUN` doar cu **dovadă reală** (link/screenshot cu nota `LOCAL SYNTHETIC` /
  înregistrare / output) și de către owner-ul indicat. CI verde **nu** înseamnă browser-verificat.
- `#43 SYNTHETIC PASS` (`docs/qa/issue-43-synthetic-persistence.md`) dovedește persistența doar pe SQLite
  disposable, cross-proces. **Nu** este persistență reală Render/PostgreSQL după restart/redeploy.
- [PR #55](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/55) aduce două capturi **LOCAL SYNTHETIC** și relatarea unui parcurs local cu un singur profil schimbând modurile; nu demonstrează independent două sesiuni sau hostul public. Nu converti din acest motiv rândurile de mai jos din `NOT RUN` în `PASS`.
- Statusuri: `NOT RUN` · `PASS` · `FAIL(+link la defect)` · `BLOCKED(+motive)`.
- Fără date personale reale în dovezi: conturi sintetice `@demo.local` doar.

| # | CHECK | STATUS | EVIDENCE | OWNER | NEXT |
|---|---|---|---|---|---|
| 1 | Desktop E2E complet pe host: părinte → mod copil Mia → carte → 35/120 → părinte (sesiune separată) vede 35/120 → terminare → „Prima carte" → cod unic → colțul membrului | NOT RUN | | Vladimir + Denis | Rulare per [`run-of-show.md`](run-of-show.md); cronometrează (< 3 min) |
| 2 | Telefon real (Android), **date mobile** (nu Wi-Fi): login → catalog → salvare progres | NOT RUN | | Denis | Fără DevTools; consemnează latența reală |
| 3 | PWA instalată pe Android: instalare, pornire din icon, **offline fallback** (`/offline/`), salvare cu rețea eșuată → „Nu s-a salvat", nu „salvat" fals | NOT RUN | | Denis | Mod avion pentru offline; documentează ce se vede offline |
| 4 | PIN greșit: 5 încercări → blocare 5 min; PIN corect refuzat cât e blocat; recuperare prin logout + re-login | NOT RUN | | Arsenii | Confruntă cu testele automate (`test_child_mode.py`) |
| 5 | Sesiune expirată: salvare după expirare → „Nu s-a salvat", nu stare fals-salvată; re-login reușește | NOT RUN | | Arsenii | Poate fi combinat cu #3 |
| 6 | Prima lansare / landing: `GET /` pe host merge (după merge PR #51) și logo-ul anonim duce la landing; linkuri signup/catalog/login corecte | NOT RUN | | Vladimir | Verifică și pe mobil |
| 7 | Dispozitiv partajat: Back/logout după switch copil↔părinte — Back/bfcache nu expune conținut contrar permisiunilor | NOT RUN | | Denis / Vladimir | PR #47 adaugă no-store la headere; headerele nu dovedesc comportamentul browserului — test pe Chrome + un al doilea browser |
| 8 | Member-only: non-membru pe `/clubul-meu/` → refuz clar (403), fără conținut de activități; membru vede activitățile | NOT RUN | | Igor | Compară `parinte2@demo.local` (non-membru) vs copil cu membră |
| 9 | Pornire lentă (cold start): măsurată real trezirea serviciului gratuit după 15+ min idle | NOT RUN | | Vladimir | Completează cu valoarea măsurată în `staging-and-recovery.md` § 3 |
| 10 | Fallback laptop: Mode A (SQLite disposable local) gata de rulat, scriptul complet cronometrat | NOT RUN | | Vladimir | Vezi `docs/demo-deployment.md` § 10; pregătește înainte de ziua demo |
| 11 | Persistență reală după restart/redeploy Render (fără scrieri noi între): 35/120 rămâne | NOT RUN | | Vladimir (owner Render) | `#43` e doar sintetic; ledgerul live e în `docs/demo-deployment.md` § 9 |
| 12 | Repetiție completă a pitch-ului RO (3:00) + varianta 30 s, cronometrate | NOT RUN | | Vladimir | Vezi [`pitch-ro.md`](pitch-ro.md) |

## Cum se completează

1. Rulare → status + dovezi + dată + owner. `PASS` fără link nu se acceptă.
2. `FAIL` → deschide issue cu pașii de reproducere; nu „repara tăcând".
3. La final: completează și „Not yet in MVP" din README rămâne adevărat — ledgerul nu schimbă scope-ul.
