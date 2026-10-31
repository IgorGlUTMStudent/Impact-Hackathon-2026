# Staging & recovery — repetiții sigure fără resetarea producției

Scop: repetă demo-ul de câte ori e nevoie **fără** să strici starea demonstrației și **fără** nicio scriere
periculoasă în baza demo live. Pereche cu [`run-of-show.md`](run-of-show.md) și [`pitch-ro.md`](pitch-ro.md).

## 0. Reguli hard

- **Niciodată `seed_demo --reset` pe hostul demo** (Render/PostgreSQL): șterge conturile demo și, cu ele,
  rafturile, progresul și insigniile copiilor Mia și Alex. Idem pentru orice SQL care șterge rânduri.
- **Nicio scriere directă în DB-ul demo** (admin Django / SQL extern). Toate pregătirile se fac prin UI,
  admin-ul autorizat sau, pentru repetiții brute, pe baze **locale disposable**.
- **Codurile de club:** emise de staff în avans, plaintext ținut în afara GitHub-ului (plic / manager de
  parole al operatorului). Fiecare cod e single-use. **Nu** crea coduri fixe „de demo" în seed/teste/docs.
- **Nu** publica parole/PIN-uri demo în docs, slide-uri sau issue-uri.

## 1. Verificarea stării ÎNAINTE de fiecare repetiție (5 minute)

Mia și Alex există din `seed_demo` sub `parinte1@demo.local`, dar starea lor **nu e garantată curată** —
repetițiile anterioare pot fi lăsate rafturi, progres 35/120, cărți terminate, membra activă. Nu presupune
nimic; verifică:

| Verificare | Unde | Ce cauți |
|---|---|---|
| Raftul Miei | `/panou/` → raportul Miei (sau `/familie/< Mia >/`) | Are deja „Capra cu trei iezi"? La ce pagină? E deja terminată? |
| Insigne existente | `/realizari/` în modul copil | „Prima carte" / „Cititor de Club" deja acordate? |
| Apartenența la club | raportul copilului (secțiunea membership) | Membră activă până la ce dată? |
| Sesiuni vechi | deschide browserul profilului „Copil" | Fără sesiuni de mod copil rămase; log out complet |

**Consecințe de știut (single-use / una-dată):**

- Un cod răscumpărat **se consumă** — al doilea POST cu același cod → 422. Ai nevoie de cod nou pentru
  fiecare repetiție completă a pasului 8 din run-of-show.
- „Terminat" nu se întoarce înapoi prin UI: cartea terminată arată „Felicitări", nu mai acceptă progres.
  Pentru repetiții repetate, folosește o **carte de rezervă** pe raft (ex. „Punguța cu doi bani") sau un
  cont de rezervă.
- `first-book` se acordă o singură dată per cititor; la repetițiile ulterioare insigna nu mai e „nouă".

## 2. Pregătirea de rezervă (backup paths)

- **Carte de rezervă pe raft:** înainte de repetiție, adaugă din contul părintelui (sau în mod copil) o a
  doua carte pe raftul Miei; dacă „Capra" e deja terminată, demonstrezi progresul pe cartea de rezervă. **Afișează numărul real de pagini al cărții de rezervă:** „Punguța cu doi bani" are 40 de pagini în seed, deci 35/40, nu 35/120. Dacă exact 35/120 este obligatoriu pe scenă, pregătește o altă carte de 120 pagini pe un cititor curat, fără resetarea producției.
- **Cont de rezervă:** dacă starea Miei/Alex e complicată, operatorul creează prin UI un cont nou
  („Familia rezervă"), un copil și un PIN demo — 2 minute, fără DB access. Folosește contul rezervă pe scenă.
- **Coduri de rezervă:** staff-ul emite **2–3 coduri unice** înainte de ziua demo-ului; fiecare merge la un
  singur copil/familie. Ține evidența privată a celui folosit.
- **Record backup:** după o rulare reușită, înregistrează ecranul (fiecare pas din run-of-show) ca rezervă
  „dacă rețeaua căde" — nu înlocuiește demo-ul live, doar îl asigură.

## 3. Trezirea hostului (cold start, serviciu gratuit)

Serviciul Render gratuit intră în sleep după inactivitate (documentația Render: ~15 min idle, trezire de
ordinul minutului — **măsoară trezirea reală în ziua demo-ului, nu o presupune**).

- Cu **10–15 minute înainte** de prezentare: `GET https://gustul-cartilor.onrender.com/carti/` din browser
  (read-only) și apoi încă un `GET` la ~1–2 minute înainte de intrare pe scenă. Verifică `/healthz/`
  răspunde `{"status":"ok","db":true}`.
- Dacă primul request agață: așteaptă trezirea completă și reia verificarea — nu începe scena pe un host
  semi-trezit.
- **Nu** configura uptime-monitor extern și **nu** modifica serviciul Render — read-only smoke doar.

## 4. Repetiții brute — doar pe bază locală disposable (laptop)

Pentru repetiții nelimitate (inclusiv „strici tot"), folosește varianta Mode A din
[`docs/demo-deployment.md` § 10](../demo-deployment.md#10-local-fallback-runbook-only-if-the-host-fails-before-the-demo--windows-powershell):
SQLite disposable **în afara repo-ului**, `config.settings.dev`, `seed_demo` (idempotent, fără `--reset`).

Dacă vrei totuși o bază locală curată de la zero: oprește `runserver`, **șterge fișierul SQLite disposable**
al Mode A (el e al tău, local, creat pentru asta), apoi `migrate` + `seed_demo` din nou. Această „resetare"
este permisă **doar** pe acel fișier local disposable — niciodată pe `db.sqlite3`-ul altcuiva, niciodată pe
host. Recreezi codul de club local doar pentru a repeta pasul 8 (admin local → Membership code).

## 5. Recuperare după incident (pe scenă)

| Incident | Acțiune |
|---|---|
| Login greșit / parolă uitată | Nu ghici la infinit (throttle 5 încercări). Trece pe **fallback laptop** (§ 4) sau pe înregistrarea backup. |
| Salvarea nu merge (rețea slabă) | Aplicația arată „Nu s-a salvat" — recunoaște onest, repeta salvarea o dată, apoi traseul rapid. |
| Codul refuzat (422) | Codul a fost deja folosit — ia codul de rezervă din plic; dacă nici el nu merge, sări pasul 8–9 și închide cu pasul 5 (persistența). |
| Hostul nu se trezește | Fallback laptop imediat; menționează că varianta demo locală rulează același cod (același SHA de pe `main`). |
| PIN uitat | Folosește „Am uitat PIN-ul — ieși din cont" (logout) și re-autentificare cu parolă — e și asta o demonstrație de securitate. |

## 6. Jurnal de repetiție (completează manual la fiecare rulare)

| Data | Traseu (complet/rapid/fallback) | Durată | Problema întâmpinată | Eticheta codului (NICIODATĂ plaintext) | Stare lăsată |
|---|---|---|---|---|---|
| | | | | | |
