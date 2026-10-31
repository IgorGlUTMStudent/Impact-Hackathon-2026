# Pitch (RO) — 3 minute, Gustul Cărților · Impact Hackathon 2026

**Scop:** un script gata de repetat, în română, cu replici exacte. Pereche cu
[`run-of-show.md`](run-of-show.md) (demonstrația pas cu pas) și
[`staging-and-recovery.md`](staging-and-recovery.md) (pregătirea demo-ului).

**Vorbitori:** Vladimir (narațiune, pitch) + Denis (demonstrația pe telefon/laptop). **Înainte de scenă:** două profiluri de browser autentificate separat în același guardian: **A = adult** pe `/panou/`; **B = copil** (mod copil Mia), cu cartea nefinalizată pregătită pe ecranul de progres. Nu transforma A în mod copil. Scenariul complet de 9 pași din run-of-show este o **repetiție EXTINSĂ**, nu o promisiune că încape în segmentul live de 55 s.

**Regulă de onestitate (pentru orice adaptare):**
- `IMPLEMENTED` = există în cod și e demonstrat în demo-ul de față.
- `VERIFIED` = demonstrat ȘI verificat pe browser/dispozitiv real (vezi
  [`acceptance-ledger.md`](acceptance-ledger.md) — la 31.10.2026 majoritatea verificărilor reale sunt **NOT RUN**).
- `HYPOTHESIS` = intenție viitoare, **nu** o afirmație despre prezent.
- Fără statistici inventate („70+ familii", cifre PISA), fără criterii de juriu asumate, fără aprobări
  de partener neconfirmate (`PARTNER_UNCONFIRMED`).

---

## Flux principal (3:00)

| Timp | Ecran | Cine | Acțiune + replică (RO) |
|---|---|---|---|
| 0:00–0:20 | Landing `/carti/` (sau `/` după PR #51) | Vladimir | **Problema.** „Fiecare părinte o cunoaște: copilul începe o carte cu entuziasm și, după câteva zile, cartea ajunge pe raft. Noi — părinții și cluburile de lectură — nu avem o modalitate blândă de a vedea progresul copilului și de a-l ține aproape de citit, fără presiune și fără ecrane sociale." |
| 0:20–0:40 | Același | Vladimir | **Utilizatorul.** „Gustul Cărților e făcut pentru familii cu copii de 7–15 ani și pentru cluburile de lectură care le însoțesc. Copilul citește în ritmul lui; părintele rămâne în câmp vizual; clubul rămâne conectat la familii." |
| 0:40–1:00 | `https://gustul-cartilor.onrender.com` | Vladimir | **Produsul.** „E un jurnal de lectură web pentru toată familia, în română, pregătit pentru experiența PWA (instalarea pe Android mai trebuie verificată). Copilul are un mod simplu, cu mascotă; părintele are panoul lui; PIN-ul limitează trecerea din modul copil la funcțiile părintelui, fără a verifica identitatea sau vârsta.” |
| 1:00–1:55 | Demo live (2 ferestre) | Denis (telefon) + Vladimir | **Demonstrația SCURTĂ, țintă 55 s** — două sesiuni distincte pregătite din timp: în **B (copil)** arată cartea nefinalizată „Capra cu trei iezi”, salvează **35/120**; în **A (adult)** actualizează `/panou/` și arată imediat **35/120**. Nu încerca să parcurgi și loginul, finish, PIN, redeem + club în aceste 55 s. **Replică de tranziție:** „Uite totul, live: copilul salvează o pagină — și părintele o vede în sesiunea lui independentă.” Insignele și codul de club sunt menționate verbal sau demonstrate în versiunea extinsă din [`run-of-show.md`](run-of-show.md), numai dacă timpul permite. |
| 1:55–2:25 | Slide/narativ | Vladimir | **Diferențierea** (răspunsul la „de ce nu Goodreads/Discord?" — mai jos). „Nu construim încă o rețea socială. Construim spațiul de citit al familiei: controlul părintelui, drepturile clubului și, mai târziu, legătura cu întâlnirile reale." |
| 2:25–2:45 | Slide/narativ | Vladimir | **Ipoteza de impact + roadmap.** „Ipoteza noastră: dacă progresul e vizibil și sărbătorit în familie, copiii citesc mai mult și cluburile își retențează familiile. Mai departe — doar împreună cu partenerul: schimb de cărți mediat de părinte, întâlniri organizate de club, «Cărți pentru fapte». Fiecare pas are porțile lui: siguranța copiilor, moderare, aprobarea partenerului, confidențialitate, costuri." |
| 2:45–3:00 | Același | Vladimir | **Cererea către partener.** „Vă propunem un pilot cu clubul vostru: 10 familii, o lună, împreună definim regulile de siguranță și măsurăm dacă cititul crește. Ce spuneți?" |

## Răspunsul pregătit: „De ce nu Goodreads/Discord?"

**Nu enumerăm defecte ale competitorilor** — diferența e în ce alegem să facem (și ce refuzăm să facem):

1. **Controlul familiei, nu rețeaua.** La noi copilul nu are profil public, nu are DM, nu apare în feed-uri.
   Profilul copilului există doar în contul părintelui; serverul separă familiile. (`IMPLEMENTED`,
   audit de siguranță: [`docs/reviews/2026-10-31-issue-44-child-safeguarding-igor.md`](../reviews/2026-10-31-issue-44-child-safeguarding-igor.md))
2. **Drepturile clubului.** Codul unic, emis de staff, activează activitățile clubului doar pentru membri —
   clubul își controlează propriul cerc, fără grupuri deschise pe care le moderăm greu. (`IMPLEMENTED`)
3. **Legătura offline, ca ipoteză viitoare.** Platformele generale nu cunosc clubul vostru de cartier.
   Noi vrem ca membrii să vadă activitățile publicate de club (`IMPLEMENTED`) și, în viitor, să
   faciliteze întâlniri reale — **doar după** regulile de însoțire și siguranță stabilite cu partenerul
   (`HYPOTHESIS`, nu prezent).
4. **Ce refuzăm intenționat azi:** mesagerie deschisă, profiluri publice de copii, generare AI, plăți —
   fiecare vine cu costuri de moderare și riscuri pentru minori. Mai puțin, dar sigur.

**Răspuns scurt (20–30 s), RO:** „Goodreads e pentru cititorul adult care vrea rețea; Discord e pentru
comunități open. Noi construim exact opusul pentru copii: fără profil public, fără DM, cu părintele în
cadrul produsului și cu clubul proprietarul propriului cerc. Socializarea reală — întâlnirile — o adăugăm
ulterior, doar împreună cu partenerul și cu regulile lui de siguranță."

## Versiunea de rezervă (30 de secunde)

„Gustul Cărților e jurnalul de lectură al familiei, în română. Copilul salvează pagina curentă, părintele o vede în sesiunea lui separată; modul copil are un PIN de ieșire, fără profiluri publice sau mesagerie. Terminarea cărții acordă o insignă; un cod unic de club deblochează activități pentru membri. Testele automate sunt verzi; persistența după redeploy pe Render nu e încă verificată. Pentru viitor propunem un pilot cu partenerul și funcții sociale doar după reguli de siguranță.”

## Traducere rusă / подсказки команде

- **0:00 Проблема:** «Каждый родитель это знает: ребёнок начинает книгу с энтузиазмом — и через несколько
  дней она возвращается на полку. У нас нет мягкого способа видеть прогресс ребёнка и держать его рядом с
  чтением — без давления и без социальных экранов.»
- **0:20 Пользователь:** «Gustul Cărților — для семей с детьми 7–15 и читательских клубов, которые их ведут.»
- **0:40 Продукт:** «Семейный читательский дневник на румынском, устанавливается как PWA. У ребёнка —
  защищённый режим с маскотом, у родителя — свой панель; между ними — родительский PIN.»
- **1:00 Демо (Денис):** только короткий путь: заранее отдельные сессии **A (родитель)** и **B (ребёнок)**; ребёнок сохраняет 35/120, родитель A обновляет `/panou/`. Полный 9-шаговый сценарий — отдельная репетиция, не 55 секунд.
- **1:55 Дифференциация:** не ругаем конкурентов; акцент — семейный контроль + права клуба + офлайн-связка
  как гипотеза будущего.
- **2:25 Impact/roadmap:** гипотеза, а не факт; всё будущее — через ворота безопасности/модерации/партнёра.
- **2:45 Запрос:** «Пилот: 10 семей, месяц, вместе определяем правила безопасности и измеряем рост чтения.»

## Ce NU spunem pe scenă (verifică înainte de prezentare)

- Nu „70+ familii", nu cifre PISA, nu „platforma universală pentru orice comunitate".
- Nu „copiii sunt verificați/în siguranță absolută": PIN protejează **ieșirea din modul copil**, nu vârsta.
- Nu „persistența pe Render e dovedită": dovedită doar sintetic (#43); live restart/redeploy — **NOT VERIFIED**.
- Nu numim proiect „open-source" (licența nu e decisă).
- Nu publicăm niciodată parole, PIN-uri, coduri de club sau date reale ale copiilor.
