# Gustul Cărților — Impact Hackathon 2026

**Gustul Cărților** este un jurnal de lectură pentru familii, construit pentru **Impact Hackathon 2026**:
copilul citește și își înregistrează progresul pagină cu pagină, părintele urmărește un raport privat
al familiei, iar membrii clubului deblochează activități speciale printr-un cod unic, emis de staff.

- **Cine:** familii cu copii (7–15 ani) și cluburile de lectură care le însoțesc.
- **De ce:** lectura copilului merită urmărită cu blândețe — fără presiune, cu insigni și cu părintele
  mereu în câmp vizual, iar clubul de lectură rămâne conectat la familii.
- **Cum:** o singură aplicație web în limba română, cu mod copil și suport PWA (instalarea pe Android este încă **NOT VERIFIED**).

> [!NOTE]
> **Stack aprobat de echipă (G7, 2026-10-30):** Django 5.2 LTS + HTMX 2.x + PWA instalabilă, Python 3.12.
> Arhitectura e revizuită în [PR #8](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/8);
> partenerul **nu** a semnat încă toate cerințele de business/siguranță (G1–G6 rămân deschise).

## Vezi produsul (demo public)

- **Aplicația live:** <https://gustul-cartilor.onrender.com>
  - **Conectare:** [`/cont/intrare/`](https://gustul-cartilor.onrender.com/cont/intrare/)
  - **Catalog public:** [`/carti/`](https://gustul-cartilor.onrender.com/carti/)
  - Ruta de landing `/` a fost adăugată în [PR #51](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/51);
    verificarea sa în browser pe host rămâne **NOT RUN** până la un smoke test real. Dacă `/` nu răspunde, intră direct la
    `/cont/intrare/` sau `/carti/`.
- Conturi demo sintetice (`seed_demo`, toate fictive): `parinte1@demo.local` (părintele lui **Mia** și **Alex**),
  `parinte2@demo.local` (părinte fără copii), `cititor@demo.local` (cititor adult), `admin@demo.local` (staff).
  Parola și PIN-ul demo se setează la seed (variabilele `DEMO_PASSWORD` / `DEMO_PIN`); **nu se publică niciodată**.

### Ce demonstrează MVP-ul azi

- **Familie și copii:** părintele creează profiluri de copii (poreclă, vârstă, avatar) în contul său.
- **Progres de lectură:** copilul alege o carte din catalog și salvează pagina curentă (ex. 35/120) —
  salvare idempotentă, sigură la rețea slabă.
- **Raport părinte:** același progres e vizibil imediat în sesiunea separată a părintelui (aceeași bază de date).
- **Realizări:** insignă „Prima carte" la terminare; insigna de club rămâne blocată pentru non-membri.
- **Cod de club unic:** staff-ul emite un cod single-use (doar hash în DB, text clar afișat o singură dată);
  părintele îl răscumpără pentru sine sau pentru copil.
- **Colțul membrului:** activități publicate de staff (titlu, dată, loc) doar pentru membri.

### Not yet in MVP (deliberately out of scope)

DM/mesagerie, schimb de cărți între utilizatori, profiluri publice ale copiilor, coordonarea reală a
întâlnirilor offline, generare AI, plăți, verificare de identitate/vârstă. Vezi [`docs/demo/pitch-ro.md`](docs/demo/pitch-ro.md)
pentru roadmap-ul condiționat.

## Status onest (2026-10-31)

| Domeniu | Stare |
|---|---|
| Cod pe `main` | [`3f2bb62`](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/commit/3f2bb62c5387f3120a6529aa4218adf3dc9b2cbb), CI: [374 passed, 4 skipped, 0 failed](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/actions/runs/41153120922) (Ubuntu) |
| Persistența datelor | **SINTETIC DOAR** — [`docs/qa/issue-43-synthetic-persistence.md`](docs/qa/issue-43-synthetic-persistence.md) dovedește 35/120 peste o graniță de proces pe SQLite disposable. **Persistența reală pe Render/PostgreSQL după restart/redeploy: NOT VERIFIED.** |
| Browser/telefon real, PWA instalată, offline | **NOT VERIFIED** — se urmărește în [#35](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/35) (ledger: [`docs/demo/acceptance-ledger.md`](docs/demo/acceptance-ledger.md)) |
| Siguranța copiilor | Fără DM deschise / profiluri publice de copii; **PIN-ul protejează ieșirea din modul copil, nu verifică vârsta sau identitatea** — audit: [`docs/reviews/2026-10-31-issue-44-child-safeguarding-igor.md`](docs/reviews/2026-10-31-issue-44-child-safeguarding-igor.md) |
| Licență | **De confirmat** (`DECISION_REQUIRED: licensing`) — nu etichetați proiectul „open-source" până la decizia echipei/partenerului |

## Rulare locală (Python 3.12 + uv)

Bash:

```bash
git clone https://github.com/Slave-of-Skynet/Impact-Hackathon-2026.git
cd Impact-Hackathon-2026
cp .env.example .env                # valori locale; nu comite niciodată .env
uv sync --frozen                    # Python 3.12 + dependențe lock-uite
uv run python manage.py migrate     # SQLite local disposable (db.sqlite3, git-ignored)
uv run python manage.py seed_demo   # date sintetice idempotente; DEMO_PASSWORD/DEMO_PIN din .env
uv run python manage.py runserver   # http://127.0.0.1:8000 (health: /healthz/)
uv run pytest                       # suita completă
```

Windows PowerShell cu bază **disposable în afara repo-ului** (varianta recomandată pentru repetiții):
vezi [`docs/demo-deployment.md` § 10](docs/demo-deployment.md). Deploy real (Render + PostgreSQL):
[`docs/demo-deployment.md`](docs/demo-deployment.md).

Pe Windows există 4 eșecuri **pre-existente** doar-Windows în `tests/test_review_fixes.py`
(subprocess/encoding); sursa de adevăr este CI-ul Ubuntu pe fiecare PR.

## Arhitectură, documentație, testare

- **Decizii:** [ADR-0001](docs/adr/0001-architecture-gustul-cartilor-mvp.md) · specificația MVP
  [`specs/001-reading-diary-mvp/`](specs/001-reading-diary-mvp/spec.md) (contracte:
  [rute](specs/001-reading-diary-mvp/contracts/routes.md), [autorizare](specs/001-reading-diary-mvp/contracts/authorization.md))
- **Aplicații:** `accounts` (identitate gardian, PIN, mod copil) · `library` (catalog, raft, progres) ·
  `club` (membru, coduri, realizări) · `core` (landing, home copil, mascotă, PWA)
- **Teste:** suita `tests/` (unit + integrare HTMX + E2E Django + concurență); verificări manuale de
  demo/dispozitiv în [`docs/demo/acceptance-ledger.md`](docs/demo/acceptance-ledger.md)
- **Echipă & unelte:** [docs/development-workflow.md](docs/development-workflow.md) (Spec Kit, integrări agent,
  workflow Git) · [ Constituția echipei](.specify/memory/constitution.md) · [`AGENTS.md`](AGENTS.md)
- **Demonstrație:** pitch (RO) [`docs/demo/pitch-ro.md`](docs/demo/pitch-ro.md) · plan de scenă
  [`docs/demo/run-of-show.md`](docs/demo/run-of-show.md) · pregătire & recuperare
  [`docs/demo/staging-and-recovery.md`](docs/demo/staging-and-recovery.md)

## Licență

Licența proiectului **nu este încă decisă** (`DECISION_REQUIRED: licensing`) — alegerea aparține echipei și
partenerului; până atunci repo-ul nu declară nicio licență și proiectul nu trebuie numit „open-source".
