# Run of show — demonstrația live (2–3 minute)

Pereche cu [`pitch-ro.md`](pitch-ro.md) (ce se spune) și [`staging-and-recovery.md`](staging-and-recovery.md)
(pregătirea, codurile, recuperarea). **Verificat de E2E**: același traseu rulează automat în
`tests/test_demo_flow.py::test_guardian_child_reading_report_finish_and_real_club` (CI verde pe `main@3f2bb62`).

## Pregătit ÎNAINTE de scenă (obligatoriu)

1. **Codul de club este emis din timp** de staff autorizat (admin → Membership code → plaintext afișat o
   singură dată) și pus într-un plic. **NU se creează cod în Django admin în timpul scenei** și nu se
   publică nicăieri. Codul e single-use: o răscumpărare reușită îl consumă.
2. Starea raftului copilului demo este verificată conform [`staging-and-recovery.md`](staging-and-recovery.md).
3. Hostul este „încălzit" (un `GET /carti/` cu 1–2 minute înainte — serviciul gratuit doarme după 15 min
   de inactivitate; măsoară trezirea reală, nu o presupune).
4. Două **profiluri de browser separate** pe același laptop (sau laptop + telefon), AUTENTIFICATE INDEPENDENT cu **același cont guardian** `parinte1@demo.local`: **A = „Părinte”**, rămas în modul adult pe `/panou/`; **B = „Copil”**, autentificat separat, inițial în modul adult, pregătit să intre în `mod-copil` pentru Mia. Verifică distincte cookie-uri/sesiuni; nu două tab-uri în același profil. Dacă B nu e autentificat, pasul 2 NU funcționează; dacă A intră în mod copil, pasul 5 NU poate citi raportul părintelui. Pentru prezentarea de 3 minute pregătește ambele sesiuni ÎNAINTE de cronometru.

## Traseul principal (țintă 2:30)

| # | Timp | Fereastra | Acțiune exactă | Rezultat așteptat |
|---|---|---|---|---|
| 1 | 0:00–0:15 | Părinte **A** | Confirmă sesiunea adult independentă pe `/panou/` (dacă pornești fără preautentificare: login `parinte1@demo.local` în profilul A) | A rămâne în modul adult, vede Mia și Alex; **nu** apăsa `mod-copil` în A |
| 2 | 0:15–0:30 | Copil **B** (autentificat separat în același cont guardian) | Din propriul panou apasă **mod copil** pentru Mia (`POST /familie/< Mia >/mod-copil/`) | Doar B ajunge la `/copil/`; profilul A rămâne în adult mode |
| 3 | 0:30–0:55 | Copil **B** | Catalog → „Capra cu trei iezi" → **„Adaugă pe raft"** → ecranul de progres `/raft/<entry>/` (verifică din timp dacă e deja pe raft) | Cartea apare „Citesc acum”, ecranul de progres este deschis în B |
| 4 | 0:55–1:10 | Copil **B** | Introdu **35** → Salvează (doar dacă această carte nu este terminată) | Partial HTMX: bară ~29%, mascota „Bravo! Ai ajuns la pagina 35.” |
| 5 | 1:10–1:25 | Părinte **A** (a doua sesiune, deja adult) | Refresh `/panou/` → raportul Miei | **35/120 vizibil** în A, independent de cookie-ul/sesiunea B |
| 6 | 1:25–1:45 | Copil **B** | Pe ecranul cărții: **„Am terminat cartea”** → `/realizari/` (doar dacă e prima carte terminată pentru acest copil) | „Felicitări”, insigna **„Prima carte”** pentru primul finish |
| 7 | 1:45–2:00 | Copil **B** → adult **B** | Apasă „Mod Părinte” → `/parinte/` → PIN corect | Numai B revine în adult mode; A a fost adult tot timpul |
| 8 | 2:00–2:15 | Părinte **A** | `/club/cod/` → copil: **Mia**, un cod unic preemis de staff (nu proiecta plaintext-ul) | Confirmare „Membru al clubului până la …”; codul este consumat o singură dată |
| 9 | 2:15–2:35 | Adult **B** → copil **B** | Din B, repetă pasul 2 → `/clubul-meu/` → `/realizari/` | Activități member-only; `club-reader` depinde de finish + membership și reevaluarea efectivă a regulilor |

**Atenție la timp:** pașii 1–9 sunt varianta EXTINSĂ de ~2:35 doar pentru demo/repetiție, fără întregul pitch verbal. În pitch-ul TOTAL de 3:00 (`pitch-ro.md`) segmentul 1:00–1:55 arată numai **B salvează 35/120 → A vede 35/120** din stări pregătite; finish/insigne/cod sunt explicate sau arătate separat dacă timpul permite. Măsoară timpul real, nu presupune că toate nouă acțiuni încap în 55 s. Pasul 5 este dovada centrală de cross-session (nu de redeploy).

## Traseul rapid de rezervă (~1:00, dacă ceva se blochează)

1. **A** rămâne autentificat ca adult; în profilul **B**, autentificat independent în același guardian, intră în mod copil Mia (pas 2).
2. Cartea deja pe raft (stare verificată înainte) → salvează 35/120 (pas 4).
3. Fereastra Părinte **A** → refresh → 35/120 (pas 5). **Stop.** Închizi cu: „Asta e produsul: progresul copilului,
   vizibil familiei, protejat de PIN."
4. Dacă și asta eșuează pe host: **fallback laptop** conform [`staging-and-recovery.md`](staging-and-recovery.md)
   (SQLite disposable local, același script, `http://127.0.0.1:8000`).

## Greșeli de evitat (constrânsuri hard)

- **Fără** crearea/afișarea codului în admin în timpul scenei; **fără** coduri fixe publicate (`CLUB-DEMO-2026`
  și prietenii sunt interzise în seed, teste, docs).
- **Fără** `seed_demo --reset` pe baza de date demo live — șterge rafturile și premiile copiilor demo.
- **Fără** parole/PIN/coduri reale pe ecran mai mult decât e necesar; nu le arăta în camere mari și nu le
  pune în slide-uri.
- Dacă o salvare eșuează pe scenă: **nu** deschide DevTools; treci pe traseul rapid de rezervă și menționează
  onest „rețeaua de la locație" — aplicația arată „Nu s-a salvat", nu minte.
