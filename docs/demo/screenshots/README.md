# LOCAL SYNTHETIC — скриншоты локальной браузерной проверки (2026-10-31)

Все изображения ниже — **локальные синтетические** прогоны: Django dev server
(`config.settings.dev`), disposable SQLite за пределами репозитория, `seed_demo`
(только вымышленные `@demo.local` аккаунты и книги из общественного достояния).
**Никаких реальных персональных данных, паролей, PIN-кодов или кодов клуба.**
Это НЕ доказательства работы на публичном хосте — проверка Render остаётся в
[`acceptance-ledger.md`](../acceptance-ledger.md) как NOT RUN.

Среда: checkout `origin/main@3f2bb62` + локально применённый незафиксированный PR
[#51](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/51) (маршрут `/`),
Windows 10.0.26300, браузер ZCode in-app (Chromium), viewport 1280×900.

| Файл | Что показано |
|---|---|
| `01-local-landing-local-synthetic.png` | Публичный landing `/` (исправление #49) — hero, ссылки «Creează cont gratuit» / «Explorează cărțile», карточки возможностей |
| `02-local-parent-dashboard-local-synthetic.png` | `/panou/` после входа `parinte1@demo.local` — приветствие, статистика, карточки детей Mia и Alex с кнопками «Raport detaliat» / «Mod Copil» |

Проверенные шаги без скриншота (подтверждены DOM-снимками, журнал в PR):
вход в детском режиме → каталог → «Capra cu trei iezi» → добавление на полку →
сохранение страницы 35/120 через настоящую HTMX-форму (маскот: «Bravo! Ai ajuns
la pagina 35.») → карточка Mia в панели родителя показывает 35/120 (29%) →
PIN-шлюз: неверный PIN даёт «⚠️ PIN greșit.», верный возвращает на `/panou/` →
`/clubul-meu/` для не-участника: «Acces rezervat membrilor clubului.» →
выход + повторный вход: 35/120 сохраняется.
