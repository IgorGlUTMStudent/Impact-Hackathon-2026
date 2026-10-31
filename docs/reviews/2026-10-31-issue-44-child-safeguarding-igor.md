# Issue #44 — safeguarding audit / răspunsuri pentru juriu

## 1. Вердикт

**READY_WITH_DISCLOSED_LIMITATIONS** для объяснения границ MVP на демо,
не заключение о готовности публичного социального сервиса для детей.
На проверенном коде не воспроизведён P0/P1 обход владения или доступ незнакомца
к истории ребёнка. В текущих маршрутах **нет открытых DM, поиска детей,
публичных детских профилей или обмена пользовательскими сообщениями**.
Это ограничение поверхности контакта, **не проверка возраста/личности**.

Проверенный main: **`1ab1a9ebd583f903538e7a7a367560c807ba1bc6`**.
Известный P2 [#40](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/40)
воспроизведён, без разблокировки режима. Дополнительно подтверждено отсутствие
`Cache-Control: no-store` у нескольких приватных страниц; реальная утечка через
историю браузера не проверялась. Эти ограничения раскрываются ниже.

## 2. Область, происхождение и сохранность работы

- Дата: 31.10.2026, Europe/Bucharest. Исполнитель: Игорь / Codex.
- Ветка: `audit/issue-44-igor-child-safety`, от актуального **upstream/main**.
  `origin` — fork IgorGlUTMStudent; его main оставался
  `0ff53ef94c508657ba3ea8ade47236b264d49e45`, поэтому не принят за текущий командный код.
- До аудита: `feat/issue33-real-demo-e2e` @ `c2f7e56eedede107a195c6bd78b3c99cc59a836b`;
  только неотслеживаемый `.tools/`. Выполнены status/branch/rev-parse/remotes,
  fetch origin/upstream. Ничего не reset/stash/clean; `.tools/` не включён в PR.
- Прочитаны AGENTS.md, constitution, ADR0001, spec, routes/authorization,
  Issues #44/#40, все app URLconf, account/club/library/core guards и views,
  модели/forms/admin/ViewModels, owner templates, app.js/child.js/sw.js,
  настройки и перечисленные ниже тесты. Инструменты: Git, rg, PowerShell,
  Django Client/pytest, GitHub connector. Не выполнялся запрос к публичному сервису.
- Таймкоды ментора **47:23–53:03** взяты из задания/Issue #44, аудио независимо
  не переслушивалось; после 50:35 транскрипт ненадёжен. Это вопросы/feedback,
  не формальные требования, согласованная политика или правовое заключение.
- Меняется **только этот Markdown**. Ни auth/schema/settings, ни pitch не менялись.

Все `file:line` ниже относятся к
[проверенному дереву](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/tree/1ab1a9ebd583f903538e7a7a367560c807ba1bc6),
а не к меняющемуся main. Контракты сверялись с реализацией, не заменяли её.

## 3. Матрица поверхности и доказательств

Сокращения статуса: **CT** = `CONFIRMED_BY_CODE_AND_TEST`,
**C** = `CONFIRMED_BY_CODE_ONLY`, **ABSENT** = `NOT_PRESENT_IN_CURRENT_ROUTES`,
**RISK** = `RISK_CONFIRMED`, **U** = `UNKNOWN / NOT_TESTED`.

| Поверхность / route | Actor | Данные / действия | Серверная защита | Источник и выполненный тест | Статус | Остаточный риск |
|---|---|---|---|---|---|---|
| `/cont/inregistrare/`, `/cont/intrare/` | Посетитель | Email/password/display_name; создание взрослого Reader | Валидаторы, парольный hash, CSRF; login DB throttle | accounts/views.py:40,65; forms.py:12,17; `test_family::test_signup_ignores_staff_fields`, `test_login_throttle::test_sixth_attempt_locked_even_if_correct` | CT | Саморегистрация не удостоверяет взрослого, родство или возраст; отдельного identity/age assurance в цепочке нет (C). Signup сообщает о занятом email (forms.py:23), не обещать полное отсутствие enumeration. |
| `/familie/`, `/<child>/editeaza/`, `sterge/`, `mod-copil/` | Adult, свой guardian | Nickname, age band, фиксированный avatar; CRUD/выбор ребёнка | login, child-mode deny; guardian из request.user; UUID + ownership; POST mutations | accounts/views.py:157,179,194,219; authz.py:79; `test_family::test_foreign_child_is_404_for_every_family_mutation` | CT | Привязка — отношение аккаунтов в БД, не доказательство реального родительства; возраст задаётся пользователем. |
| `/panou/`, `/familie/<child>/` | Adult, свой guardian | Имя аккаунта, собственные дети, книги/страницы/награды | login; guardian-scoped queries, чужой child404; child-mode deny | accounts/views.py:97,123; `test_account_dashboard::test_foreign_and_unknown_child_are_identical_404`, `test_dashboard_lists_only_own_children_and_ignores_forged_params` | CT | Нет явного no-store: см. F2. |
| `/familie/pin/`, `/parinte/`, POST logout | Свой authenticated session | Установка PIN с password reauth; выход из child mode | Не принимает client mode/guardian; PIN hash, DB account throttle; logout заканчивает сессию | accounts/views.py:204,219,232; forms.py:51; throttle.py:20,55; `test_child_mode::test_pin_gate_does_not_accept_password`, `test_pin_lockout_after_5_and_correct_pin_refused_while_locked`, `test_logout_recovery_ends_session` | CT | PIN защищает переключение режима, не возраст, устройство или утраченный уже открытый adult-сеанс. F1. |
| Любой adult/admin/новый route в child mode | Ребёнок в session | Запрет прямого URL/HTMX обхода UI | Deny-by-default allowlist; повторная валидация active_child; normal302 PIN, HTMX403 | accounts/middleware.py:8,17; authz.py:54,66; `test_child_mode::test_new_unlisted_route_is_denied_by_default`, `test_adult_urls_via_htmx_are_403_without_partial` | CT | Тест нового route добавляет только отрицательный тестовый URL; реальный E2E отдельно проверяет рабочие маршруты. |
| `/carti/`, `/carti/<book>/` | Public/adult/child | Только каталог BookVM; фильтры книг, не поиск пользователей | Активные книги; текущий Reader только для своих shelf markers | library/views.py:35,86,97; core/viewmodels.py:15; `test_library_authz_integration::test_public_metadata_and_anonymous_mutations`; локальная проба sentinel | CT | Каталог редактирует привилегированный admin; ссылки/полный контент издателей не реализованы как детский UGC. |
| `/raft/`, `/<entry>/`, `/progres/`, `/terminat/` | Current Reader | Своя книга/прогресс | real current_reader, entry scoped by reader, POST+CSRF, UUID idempotency; committed saved only | library/views.py:35,67,105,157,177; authz.py:88; `test_library_authz_integration::test_real_scoped_entry_lookup_rejects_every_other_reader`, `test_expired_database_session_cannot_save`, `test_real_csrf_for_add_progress_and_finish` | CT | UUID не является разрешением. No-store непоследователен; F2. |
| `/copil/` | Валидный child session | Ник, avatar, своя текущая книга и награды | login + child-only + ownership; private/no-store | core/child_views.py:24,121; `test_child_ui::test_child_home_isolation_between_families`, `test_child_home_invalid_active_child_fails_closed` | CT | Уже видимый экран/Back/bfcache устройства не протестирован. |
| `/realizari/`, `/club/cod/` | Current Reader / adult для redemption | Свои earned/locked; код self/own child | Реальные authz, ownership, durable throttle; child не может redeem; no-store | club/views.py:35,76; services.py:75; `test_club_views::test_foreign_and_tampered_targets_404`, `test_generic_errors_persistent_fifth_sixth_and_expiry`, `test_demo_flow::test_guardian_child_reading_report_finish_and_real_club` | CT | Membership/code — entitlement, не проверка возраста/личности. Известное конкурентное окно check/failure commit не устранено этим аудитом. |
| `/clubul-meu/` | Любой активный member Reader | Staff-published title/start/place события | DB membership при каждом GET; только published; нет attendee list/RSVP/контактов | club/views.py:97; club/models.py ClubActivity; `test_club_views::test_service_and_club_http_vertical_slice` | CT | **Реальный read-only event surface существует**: время/место доступны adult и child members. Это не подтверждение безопасности реальной встречи. Не размещать частные адреса/списки детей. |
| `/admin/` | Staff + Django model permissions | Account email/name; ограниченный просмотр детских nickname; каталог/club actions | Django admin permissions; child-mode deny; ChildProfile/Reader/entries read-only; PIN hash не выводится | accounts/admin.py:8,25,38; library/admin.py:16,23; club/admin.py:18,62; `test_review_fixes::test_admin_never_renders_pin_hash`, `test_admin_child_profile_shows_nickname_only`; club permission tests | CT | Back office доверенный: это не обещание, что staff не видит PII вообще. Нужны контроль выдачи staff-доступа и отдельный аудит эксплуатации. |
| `/offline/`, `/manifest.webmanifest`, `/sw.js`, static | Public; invalid child session fail-closed | Публичная offline shell/static assets | SW не ставит POST в очередь; не записывает diary/family HTML в CacheStorage | core/pwa.py:24,38,55; static/sw.js:14,65,72,91; `test_pwa::test_offline_view_no_private_data`, `test_pwa_fails_closed_when_child_is_invalid`; child JS tests | CT для локального HTTP/script checks | Это не аудит установленного браузерного SW, HTTP cache или bfcache; F2 / U. |
| `/healthz/`, DEBUG `/_preview/<template>` | Public только допустимый mode | JSON status/db bool; preview — синтетический контекст | Health не возвращает пользователей; preview route DEBUG-only и view тоже отказывает без DEBUG | core/views.py:15,26,69; config/urls.py:16; `test_foundation::test_preview_view_refuses_when_debug_off_even_if_routed`, `test_preview_route_absent_when_built_with_debug_off` | CT | Проверено локально; реальные production DEBUG/TLS/error-page/log settings не исследовались на хосте. |
| DM/chat/feed, отзывы/комментарии, public child profile, user search, рейтинг, invitations, обмен/адреса доставки, uploads, book notes | Нет зарегистрированного handler | Соответствующих моделей/форм/маршрутов не обнаружено | Полная конфигурация config/urls.py + четыре apps/*/urls.py, модели/forms/views и шаблоны; rg с исключением bundled htmx | ABSENT | Не обещание на будущие ветки/версии. Есть private free text display_name/nickname и staff-curated book/event text; не говорить «никакого пользовательского ввода». |
| Identity/age verification, модерация, report/block, безопасность offline встречи | Не реализовано как продуктовый workflow | Нет возрастного/документального подтверждения и процесса safeguarding | account signup/family forms и inventory выше | ABSENT | Нужен отдельный partner/privacy/safeguarding decision gate до social launch. |

Корень `/` не зарегистрирован в текущем URLconf; утверждение старого page-map о
работающем landing не использовалось как evidence. Полноценного public user API
не найдено: JSON health/manifest не являются API детских профилей.

## 4. Threat cases и ledger выполненных проверок

**Только локальные синтетические данные**. Windows, CPython3.12.16/Django5.2.18.
`uv` — локальный `.tools/uv.exe`, не включён в PR. Для команд с БД явно задан
process-local `DATABASE_URL=sqlite:///D:/ImpactHackaton2026/audit-isolated.sqlite3`;
pytest создаёт собственную test DB, не базу публичного приложения. Никаких
Render/admin/deployed DB/стресс-запросов. Prod-settings tests используют фиктивные
параметры PostgreSQL для проверки конфигурации, не доказательство подключения.

| Команда | Фактический результат |
|---|---|
| `uv sync --frozen` | PASS: 14 packages checked |
| `uv run python manage.py check` | PASS: no issues (0 silenced) |
| `uv run pytest tests/test_authz.py tests/test_child_mode.py tests/test_login_throttle.py -q -o addopts=` | **66 passed in43.74s**, exit0 |
| `uv run pytest tests/test_family.py tests/test_account_dashboard.py tests/test_library_authz_integration.py tests/test_club_views.py tests/test_pwa.py tests/test_child_ui.py tests/test_review_fixes.py tests/test_demo_flow.py -q -o addopts= -rs` | **118 passed,4 failed in90.00s**, exit1, no skips |
| `uv run pytest tests/test_foundation.py::test_preview_view_refuses_when_debug_off_even_if_routed tests/test_foundation.py::test_preview_route_absent_when_built_with_debug_off tests/test_prod_settings.py -q -o addopts=` | **10 passed in1.37s**, exit0 |
| `uv run python .tools/issue44_probe.py` | exit0, isolated_test_db=true; details ниже. Локальный одноразовый диагностический скрипт, не новый production/regression file. |
| `git diff --check` | PASS до публикации отчёта |

Четыре failures — существующие Windows subprocess-тесты test_review_fixes.py:
`test_wsgi_without_settings_module_fails_closed_without_secret`,
`test_wsgi_without_settings_module_starts_with_prod`,
`test_wsgi_respects_explicit_settings_module`, `test_manage_py_still_defaults_to_dev`.
Все падают при import `_overlapped`, **WinError10106**, в minimal subprocess env.
Это не PASS, не пропуски и не доказательство дефекта live TLS; ничего не xfail/skip
и не исправлялось ради отчёта. Остальные security/admin/E2E checks в этом запуске
прошли. Полный локальный pytest для #44 **NOT RUN** — выполнены focused suites.
CI отчётного PR, если выполнен, является отдельным evidence, не локальным запуском.

Одноразовая проба: Django setup_test_environment/setup_databases на SQLite
in-memory test DB, override DEBUG=False/testserver; создано только синтетическое
семейство, книга и entry, Client без сети; finally teardown_databases. Не выводились
email/PIN/cookies/child UUID. Проба подтвердила escape никнейма с HTML-маркером,
отсутствие маркера ребёнка в anonymous catalog, preview404 при DEBUG=False,
заголовки F2 и сценарий F1. Это ограниченная проверка, не полный XSS pentest.

## 5. Находки и точные границы риска

### F1 — P2, RISK_CONFIRMED: известный #40, без observed bypass

Источник: accounts/views.py:232,246. В изолированном тесте: valid owned child
session, затем out-of-band `Account.pin_hash=None`; POST валидного по формату PIN
на `/parinte/` → **500**, session.mode остаётся child; GET `/panou/` →302 к PIN,
POST logout→302. Через нормальный child_mode_start отсутствующий PIN не допускается.
Не найден HTTP-путь, который сам создаёт такое состояние. Не дублировать Issue #40.
Owner Арсений: отдельный fail-closed guard и regression missing-hash →422,
mode неизменен, logout работает. Здесь shared auth не менялся.

### F2 — P2 hardening, RISK_CONFIRMED для заголовков; browser disclosure U

В однократной runtime-пробе GET200: `/panou/`, `/familie/`,
`/familie/<owned child>/`, child `/raft/`, `/raft/<owned entry>/` имеют
**Cache-Control отсутствует**, Vary=`Cookie, Accept-Language`.
Child `/copil/` имеет private/no-store/must-revalidate, `/realizari/` — private,
no-cache/no-store. Код: accounts/views.py:95–174, library/views.py:105–124;
для сравнения core/child_views.py:121 и club/views.py:35,76,94.

Повторение: на isolated transactional test DB создать synthetic guardian/child,
войти отдельными Django Clients, normal HTTP start child mode, GET указанных
страниц и проверить `response.status_code`, `response.get('Cache-Control')`,
`response.get('Vary')`. Нового сетевого/публичного воспроизведения не требуется.

Это подтверждает **отсутствие явного запрета хранения**, а не доказанную утечку
чужой семье: ownership guards сохраняются, Vary:Cookie присутствует. Общий телефон,
уже открытая вкладка, Back/bfcache и конкретный браузер после mode switch/logout
**NOT TESTED**; no-store сам по себе не обещает очистить уже отображённый экран.
Предложение владельцам Арсений/Алиса: согласовать no-store для authenticated
account/library responses (включая приватные partials), targeted regression
`test_private_responses_no_store`, затем реальный browser back/logout check #35.
Не внедрять общий middleware без owner decision gate.

### Дополнительные ограничения — не скрытые P0 claims

- SignupForm сообщает «email уже занят» (accounts/forms.py:23–27); generic login
  errors не означают отсутствие signup enumeration. Код просмотрен; специальная
  атака перебором email не проводилась. Для будущего internet-facing hardening
  Арсению оценить generic signup/rate limits; не заявлять готовый anti-abuse.
- Login/PIN/redeem DB limits подтверждены тестами, но это не защита от всех
  распределённых/одновременных атак. В частности, residual redeem check/failure
  gap остаётся в club/services.py:76; новая concurrency гарантия не заявляется.
- Сессия sliding30 days, HttpOnly/SameSite=Lax (base.py:108–111); production
  Secure cookies/HTTPS/DEBUG=False заданы в prod.py:12,33–40. Это просмотр кода и
  отдельные settings tests, не измерение live cookies/логов/error pages или
  доказательство соответствия правилам обработки детских данных.

**P0/P1 blocker в проверенной поверхности не воспроизведён**. Это ограниченный
аудит конкретного SHA, не сертификация и не оценка всех возможных атак.

## 6. Răspunsuri pentru juriu — română, apoi traducere rusă

### 1. Cum vă asigurați că minorii sunt în siguranță pe platformă?

**RO:** În MVP, profilul copilului este creat și gestionat din contul părintelui,
iar serverul verifică accesul la datele propriei familii. Am testat izolarea
istoricului de lectură și restricțiile modului copil. Nu oferim mesagerie deschisă
sau profiluri publice ale copiilor; aceste limite reduc riscul, fără să garanteze siguranță absolută.

**RU:** В MVP профиль ребёнка создаётся и управляется из родительского аккаунта,
а сервер проверяет доступ к данным своей семьи. Мы проверили изоляцию истории
чтения и ограничения детского режима. Открытых сообщений и публичных детских
профилей нет; эти границы уменьшают риск, но не гарантируют абсолютную безопасность.

### 2. Poate un adult să pretindă că este copil și să comunice cu minorii?

**RO:** Nu verificăm încă identitatea sau vârsta reală: un adult poate crea în
propriul cont un profil declarat de copil. Dar în MVP nu există mesagerie între
utilizatori, căutare de copii sau profiluri publice prin care să contacteze alți
minori. Nu prezentăm această limitare de funcționalitate drept verificare a vârstei.

**RU:** Мы пока не проверяем реальную личность или возраст: взрослый может создать
в своём аккаунте профиль, обозначенный как детский. Но в MVP нет сообщений между
пользователями, поиска детей или публичных профилей для контакта с другими
несовершеннолетними. Мы не выдаём ограничение функций за проверку возраста.

### 3. Ce protejează PIN-ul părintelui și ce NU protejează?

**RO:** PIN-ul protejează ieșirea din modul copil către funcțiile părintelui pe
același cont și dispozitiv. Încercările greșite sunt numărate pe server și pot
bloca temporar ieșirea; recuperarea se face prin deconectare și autentificare din nou.
PIN-ul nu dovedește identitatea, vârsta sau relația de rudenie și nu înlocuiește parola contului.

**RU:** PIN защищает выход из детского режима к родительским функциям в том же
аккаунте и на устройстве. Ошибочные попытки учитываются сервером и могут временно
заблокировать выход; восстановление — через выход из аккаунта и повторный вход.
PIN не доказывает личность, возраст или родство и не заменяет пароль аккаунта.

### 4. Cum veți introduce în siguranță schimbul de cărți, comunitățile și evenimentele offline?

**RO:** Schimbul între utilizatori și comunitățile cu mesaje nu sunt implementate;
acum membrii pot doar vedea activități publicate de administrator, inclusiv locul lor.
Înainte de contacte sau întâlniri facilitate de platformă, vom stabili cu partenerul
reguli de protecție a copiilor, contact prin părinte, raportare/blocare și moderare.
Orice verificare a identității sau vârstei trebuie decisă separat, împreună cu evaluarea juridică și de confidențialitate.

**RU:** Обмен между пользователями и сообщества с сообщениями не реализованы;
сейчас участники могут лишь видеть опубликованные администратором мероприятия,
включая место. До организации контактов или встреч через платформу мы должны
согласовать с партнёром защиту детей, контакт через родителя, жалобы/блокировку и модерацию.
Любая проверка личности или возраста требует отдельного решения вместе с правовой оценкой и оценкой приватности.

### Varianta de scenă, aproximativ 20–30 secunde

**RO:** În MVP, copilul folosește un profil gestionat din contul părintelui.
Serverul separă datele familiilor, iar PIN-ul protejează revenirea la funcțiile
părintelui. Nu avem mesagerie deschisă, căutare de copii sau profiluri publice.
Nu pretindem că verificăm vârsta reală. Înainte de funcții sociale, avem nevoie
de reguli de protecție a copiilor, contacte prin părinți și moderare, convenite cu partenerul.

**RU:** В MVP ребёнок пользуется профилем из родительского аккаунта. Сервер
разделяет данные семей, PIN защищает возврат к родительским функциям. Открытых
сообщений, поиска детей и публичных профилей нет. Мы не утверждаем, что проверяем
реальный возраст. До социальных функций нужны согласованные с партнёром правила
защиты детей, контакты через родителей и модерация.

**Limită onestă / Честное ограничение:** Autorizarea contului și PIN-ul nu verifică
vârsta sau identitatea reală. / Авторизация аккаунта и PIN не проверяют реальный возраст или личность.

## 7. Следующие gates и handoff к #35

Для pitch Владимиру: использовать четыре RO-ответа и короткую версию выше;
демонстрировать private-family boundaries, не «все дети проверены».
Аккаунт guardian — технический владелец профиля, не установленный юридический
статус. Не обещать полную анонимность от staff, отсутствие любого кэширования,
проведённый browser pentest или готовность к реальным встречам.

До social launch нужны отдельные согласованные решения: guardian-mediated
contacts и обмен без публичных адресов; доступ/сопровождение на offline событиях;
privacy/data retention/deletion; правила контента и обращений, report/block,
moderation и safeguarding incident process, ответственность оператора;
необходимость и пропорциональность identity/age assurance с партнёром и
профильными специалистами. Всё перечисленное — будущие gates, не текущие функции.
Сбор биометрии не предлагается этим аудитом.

Browser/Android installed PWA/Back/logout/общий телефон, live environment/error
logs/HTTPS/cookies, реальная persistence #43 и эксплуатационные права staff:
**UNKNOWN / NOT_TESTED** здесь. #35/#43 не закрываются этим отчётом.
F1 передать существующему #40; F2 — owners Арсений/Алиса и browser QA #35.
Независимое решение по #44 принимает ChatGPT project brain после публикации;
исполнитель не self-approve/self-merge и не закрывает #44.
