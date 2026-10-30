# ISSUE #33 — Контракт 02: независимый аудит авторизации и детского режима

**Исполнитель:** Владимир, в Antigravity.  
**AI-модель:** **GLM 5.3 Flash**. **Effort: max**.  
**Роль агента:** security/authorization reviewer, а не автор нового E2E или новой архитектуры.  
**Заказчик и финальный независимый reviewer:** ChatGPT (project brain).  
**Repository:** https://github.com/Slave-of-Skynet/Impact-Hackathon-2026  
**Issue:** https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/33  
**Реализация Игоря:** https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/37  
**Результат Алисы:** https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/pull/38 — merged.  
**Общий acceptance oracle:** docs/contracts/issue-33/00-acceptance.md (в PR #36, если ещё не смёржен).  
**Выходной файл:** docs/reviews/issue-33-authz.md.  
**Выход на GitHub:** отдельная ветка `review/issue33-vladimir-authz`, PR в `main`, обязательный независимый review от ChatGPT.

> **Статус на момент написания (2026-10-30):** `main` HEAD `5e6b645961baeafb7d532b589c770d59e8d303fb` (включает #38). PR #37 — draft, проверенный head `c2f7e56eedede107a195c6bd78b3c99cc59a836b`; его Ubuntu CI: 366 passed, 4 skipped. **Это историческая точка отсчёта, а не приказ тестировать устаревший SHA. Перед работой проверь live-состояние.**

---

## 0. Твоя задача

Ты — независимый инженер по проверке безопасности, выполняющий **последний узкий gate для Issue #33**.

Проверь, что родитель, ребёнок, посторонний родитель и анонимный посетитель не получают чужие данные и не могут обойти ограничения режима ребёнка, PIN или серверные проверки прав.

У Игоря уже есть четыре комплексных HTTP+DB теста в `tests/test_demo_flow.py`. **НЕ дублируй и НЕ переписывай их.** Алиса уже отдельно проверила библиотеку/прогресс. Тебе нужно:

1. проверить реальный код авторизации, middleware и критические маршруты;
2. выполнить **на точном HEAD PR #37** существующие и, при необходимости, дополнительные узкие HTTP/DB тесты;
3. обнаружить реальные регрессии, если они есть;
4. предоставить воспроизводимый отчёт с честными статусами PASS / FAIL / NOT RUN;
5. **сразу опубликовать отчёт и результаты в GitHub**, открыть PR и передать его ChatGPT для независимого аудита.

Ни один результат не считается PASS только по чтению кода или чужому отчёту.

## 1. Синхронизация: не перепутай `main` с PR Игоря

1. До редактирования выполни `git status --short`, `git remote -v`, `git fetch` и проверь последнюю версию `main`, PR #37, Issue #33 и PR #36. Запиши точные SHA.
2. Если рабочая папка содержит чужие изменения, **не сбрасывай, не очищай и не перезаписывай их**. Используй отдельный `git worktree`/чистый checkout.
3. Для проверки Игоря получи его **актуальный** PR HEAD из GitHub, а не только `origin/main`. Универсальный способ, не зависящий от того, как названы remotes:

   ```bash
   git fetch https://github.com/Slave-of-Skynet/Impact-Hackathon-2026.git refs/pull/37/head
   git rev-parse FETCH_HEAD
   # Проверь HEAD и тестируй этот ref в отдельной чистой worktree.
   # Не cherry-pick и не merge PR #37 в main ради аудита.
   ```

4. Сверь полученный SHA с GitHub PR #37; проверь, что итоговый CI относится **именно к нему**, а не к более старому коммиту.
5. **Ветка отчёта должна создаваться от свежего `main`, а не от PR Игоря**. В отчётном PR должен быть только твой `.md` (при отсутствии выявленных дефектов). Проверку на PR Игоря проводи отдельно, в read-only checkout.
6. Убедись, что GitHub PR #38 действительно merged и никакой review не был выдан за внедрение новых тестов.

## 2. Что изучить до проверки

Основные файлы (фактический runtime имеет приоритет над устаревшими планами):

- `apps/accounts/authz.py`: `current_reader`, `active_child_reader`, `get_child_for_guardian`, `get_entry_for_reader`, `login_required`;
- `apps/accounts/middleware.py`: `ChildModeMiddleware`, deny-by-default allowlist и `ALWAYS_ALLOWED`;
- `apps/accounts/views.py`, `forms.py`, `urls.py`, `throttle.py`, `models.py`;
- `apps/core/child_views.py`, `apps/core/urls.py`;
- `config/urls.py`, `config/settings/` (только если нужно для корректности теста);
- `apps/club/views.py`: `redeem_code`, `club_corner` и получение текущего reader (код **не меняй**);
- `apps/library/views.py`: `record_progress` как защищённый endpoint (код **не меняй**);
- `tests/conftest.py`, `tests/test_authz.py`, `tests/test_child_mode.py`, `tests/test_login_throttle.py`, `tests/test_family.py`, `tests/test_account_dashboard.py`, `tests/test_demo_flow.py`;
- `specs/001-reading-diary-mvp/contracts/authorization.md`, `routes.md` и `docs/contracts/issue-33/00-acceptance.md` из PR #36.

Не следуй слепо устаревшим словам «NOT RUN» в документах: проверяй реальный тест и действующий код.

## 3. Обязательная матрица независимой проверки

Для каждого пункта укажи **PASS / FAIL / NOT RUN**, фактический тест, HTTP-статус/заголовки и наблюдаемое изменение либо отсутствие изменения в БД.

| ID | Проверяемое поведение | Обязательный oracle |
|---|---|---|
| A01 — identity | Реальный POST login, создание ребёнка через `/familie/`, установка PIN с повторным вводом пароля, POST входа в child mode | Ребёнок принадлежит текущему guardian, имеет отдельный Reader; детская сессия открывает `/copil/` (200); данные реально в БД |
| A02 — ownership/IDOR | Другой guardian запрашивает `/familie/<child>/`, меняет/удаляет чужого ребёнка, пытается активировать его child mode; пробует чужой `/raft/<entry>/` | 404 или соответствующий запрет без утечки, никаких чужих мутаций; чужой/несуществующий идентификатор не раскрывает данные |
| A03 — reader binding | Приписанные к query/form `reader`, `guardian`, `child` не меняют полномочия | Сервер использует текущий reader или строго принадлежащего guardian ребёнка; adult-self и child данные независимы |
| A04 — child deny-default | В child mode запросить `/panou/`, `/familie/`, `/club/cod/`, `/admin/`, неизвестный и новый неразрешённый маршрут | Обычный запрос → 302 на `/parinte/`; HTMX → 403, пустое тело и без `HX-Trigger: saved` |
| A05 — tampered session | `active_child` удалён, подделан, чужой или ребёнок удалён из БД | Только PIN gate и logout остаются доступными; никаких fallback к взрослому reader или чужой полке |
| A06 — PIN lifecycle | Верный PIN, неверный PIN, 5 ошибок, 6-я попытка, верный PIN во время блокировки, истечение lockout, другой сеанс | Неверный → 422; блокировка → 429 и сохраняется между сеансами; верный во время блокировки не проходит; после восстановления верный PIN очищает child mode |
| A07 — logout/recovery | POST logout в детском режиме | Закрывается **вся** авторизованная сессия; детский режим нельзя превратить во взрослый без корректной повторной аутентификации; GET logout не создаёт обход |
| A08 — login throttling | Неверный/неизвестный email, 5 ошибок и правильный пароль во время lockout, новый сеанс, другая почта | Generic 422 (не раскрывать существование аккаунта); 429 для заблокированного ключа, включая правильный пароль; DB scope/key и сроки соответствуют текущим правилам |
| A09 — expiry / HTMX | Истечение авторизованной сессии и POST прогресса через HTMX | 401 с `HX-Redirect` на login, нет успешного partial или `HX-Trigger: saved`, нет ProgressEvent/изменения page |
| A10 — CSRF / method | Нет CSRF-токена у POST мутации; GET на POST-only route | При `Client(enforce_csrf_checks=True)`: 403 и нет записи; GET на POST-only не выполняет мутацию (405/текущий разрешённый отказ) |
| A11 — club target | Код для `self`; попытки отправить `reader=<foreign child UUID>` или `reader=<Reader UUID>`; детский режим пытается открыть redemption | `self` соответствует только собственному взрослому reader; произвольные цели отклоняются (404), child mode не может погасить код |
| A12 — club throttle | Ошибки погашения клубного кода и лимит, включая новую сессию | Per-account throttle; invalid/used/expired дают generic отказ; при lockout 429 + Retry-After. Если уже подтверждено тестами Игоря/Алисы, допустимо **повторно исполнить адресные тесты**, а не копировать реализацию. |

**Особый акцент:** проверь, не становится ли session/guardian/reader параметр источником доверия. UI-скрытие кнопки — НЕ доказательство запрета. Контроль должен быть на сервере.

Если найден новый уязвимый путь, создай воспроизводимый HTTP+DB негативный тест, который падает **до исправления**. Если корректность зависит от browser JS, пометь её NOT RUN и оставь #35 открытым.

## 4. Правила работы с тестами и транзакциями

- По умолчанию переиспользуй существующие `tests/test_*.py` — они уже содержат много проверок A01–A12. Не создавай гигантский второй тестовый файл без необходимости.
- Для новых интеграционных позитивных probes используй настоящие URLconf, middleware, authz, БД и шаблоны; **не мока́й `current_reader`, `ChildModeMiddleware`, login/PIN или успешные club/library services**.
- Негативные fault-injection тесты допустимы только с явно описанной причиной; они не подтверждают позитивный E2E.
- **Важно о транзакциях:** `apps/accounts/throttle.record_failure()` и `apps/club/services.redeem_code()` используют `transaction.atomic(durable=True)`; не окружай их искусственной общей транзакцией. Существующие тесты работают в собственном harness; для *нового* полного теста code redemption используй `pytest.mark.django_db(transaction=True)`/`transactional_db`, когда это необходимо. Не меняй рабочую бизнес-логику для обхода неправильно настроенного теста.
- Варианты 422/429/401/403/404/409 не должны сопровождаться успешными триггерами сохранения и недопустимой записью.
- Проверки должны работать на синтетических аккаунтах/данных; не публикуй реальные email, PIN, пароли, session cookies, хеши токенов или одноразовые коды.

## 5. Команды и доказательства

Запусти **в checkout финального HEAD PR #37**:

```bash
uv sync --frozen
uv run pytest tests/test_authz.py tests/test_child_mode.py tests/test_login_throttle.py tests/test_family.py tests/test_account_dashboard.py -v
uv run pytest tests/test_demo_flow.py -v
uv run pytest tests/test_club_views.py -v
uv run pytest -rs
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
git diff --check
```

В отчёте для **каждой команды** укажи exact command, exit code, число passed/failed/skipped, ОС/Python и тестируемый SHA.

Если под Windows полная suite падает на уже наблюдавшихся subprocess WinError10106 в `tests/test_review_fixes.py`, **не утверждай локальный GREEN и не выключай тесты**. Приведи конкретные trace/case names и отдельно проверь официальные Ubuntu CI логи на финальном SHA. Чужое CI — дополнение, не замена твоим запускам.

Если тест падает не из-за проекта (env/runner), классифицируй как **ENV BLOCKED**, зафиксируй, что именно не смог проверить, и повтори изолированно, если разумно. Отсутствие фактического исполнения — NOT RUN, даже если исходники выглядят правильными.

## 6. Граница изменений и маршрутизация дефектов

**Без подтверждённого дефекта единственный новый файл — `docs/reviews/issue-33-authz.md`.**

Не изменяй:
- `tests/test_demo_flow.py` Игоря, его PR branch или отчёт;
- `apps/library/`, `apps/club/`, UI, шаблоны, JS/CSS;
- БД-схему, migrations, `config/urls.py`, settings, публичные URL/контракты;
- GitHub `main` напрямую.

Если найден реальный P0-дефект в `apps/accounts/`:
1. зафиксируй минимальный reproduction, воздействие, вероятную причину и текущую проверяемую ошибку;
2. добавь минимальный regression test, только затем маленький accounts-only fix в **отдельной** ветке/PR;
3. не меняй shared APIs/schema/security design без отдельного решения project brain;
4. передай Игорю ссылку на fix PR и требование нового E2E/CI на объединённом SHA;
5. не закрывай Issue #33 до завершения этого gate.

Если обнаружена проблема в другой подсистеме — только отчёт и GitHub handoff владельцу; не делай захватывающий параллельный refactor.

## 7. Обязательный выходной артефакт

Создай `docs/reviews/issue-33-authz.md` со следующей структурой:

1. **Executive verdict:** PASS / FAIL / BLOCKED и можно ли без accounts-блокеров мержить #37.
2. **SHA ledger:** current `main`, точный tested PR #37 HEAD, собственный report branch HEAD; не смешивай их.
3. **A01–A12 matrix:** PASS/FAIL/NOT RUN; название теста/пробы; URL/response; persisted-state observation; ограничения.
4. **Executed commands and raw outcomes:** ОС, Python, pytest, passed/failed/skipped, exit codes, CI URL.
5. **Findings:** P0/P1/P2, конкретный путь и минимальная воспроизводимая атака; или `No actionable authz findings reproduced` (если правда).
6. **Boundaries:** не проверял настоящую PWA/browser UX (#35), production PostgreSQL/remote deployment (#34), реальные внешние сессии/устройства. Не выдавай P0 test-client PASS за production security certification.
7. **Handoff:** нужны ли corrections от Игоря, какие follow-up PR, какие gate ещё открыты.

Не придумывай результаты команд и не вставляй placeholder "PASS", если не запускал тест.

## 8. GitHub delivery — обязательно, без ожидания дополнительного разрешения

После завершения проверок **немедленно**:

1. Обнови `main` из оригинального репозитория и создай отчётную ветку **от `main`**, а не из checkout PR #37: `review/issue33-vladimir-authz` (или уникальное имя, если занято).
2. Добавь только `docs/reviews/issue-33-authz.md`, если дефекты не требуют отдельного code PR.
3. Commit и push в GitHub. Открой **недрафтовый** PR в `Slave-of-Skynet/Impact-Hackathon-2026:main` с названием `docs(review): Issue 33 authz/child-mode verification`; body: `Refs #33`, точный tested Igor SHA, summary результатов, обнаруженные риски и ссылку на его PR #37.
4. Запроси **независимую проверку ChatGPT project brain**, приложи точные ссылки на PR, sha, CI и отчёт. Отметь, что **твоя модель не является независимым финальным reviewer**.
5. **Не мержи свой отчёт, PR #37 или другие PR; не закрывай Issue #33.** Финальное решение остаётся за ChatGPT по реальным GitHub данным. Если появится P0-проблема, создай отдельный ограниченный fix PR и укажи зависимость.

### Финальный формат ответа пользователю

```text
STATUS: PASS | FAIL | BLOCKED
MODEL: GLM 5.3 Flash / effort max
TESTED_IGOR_SHA: <actual SHA>
REPORT_PR: <GitHub URL>
REPORT_SHA: <actual SHA>
LOCAL: <commands and pass/fail/skip totals>
CI: <exact-run URL and outcome>
FINDINGS: <specific issues or none reproduced>
MERGE_GATE_37: READY_FOR_INDEPENDENT_REVIEW | BLOCKED
HANDOFF: <what ChatGPT/Igor must do next>
```

**Главный критерий:** достоверное независимое подтверждение критических границ доступа на текущем PR #37, а не количество написанных тестов. Все результаты — на GitHub, для проверки без доступа к твоему локальному окружению.
