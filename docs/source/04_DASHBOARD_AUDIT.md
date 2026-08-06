# 04 — Dashboard Audit (Flask + vanilla SPA operator terminal)

| Field | Value |
|---|---|
| **Дата аудита** | 2026-08-05 |
| **Путь к проекту** | `/Users/danila/Downloads/Trading-Bot-merge-learning-nik` |
| **Ветка** | `quant-site-approved-reference-redesign` |
| **Commit HEAD** | `a54a100b4d542f1d866b5f89336ce0703fea6ced` |
| **Статус документа** | ACTIVE — Source of Truth по Dashboard |
| **Область аудита** | `bot/ui/` — IA, навигация, сценарии оператора, реальность данных, состояния, realtime, адаптивность, доступность |
| **Фактический маршрут** | `http://127.0.0.1:5001` по умолчанию (`DASHBOARD_HOST`/`DASHBOARD_PORT`). Для аудита запускался на **5051** в режиме `QF_DASHBOARD_READ_ONLY=1` |
| **Связанные документы** | [02](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md) · [05](05_TELEGRAM_BOT_AUDIT.md) · [06](06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md) · [07](07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md) · [11](11_MASTER_ROADMAP.md) |

### Что удалось проверить
- Живой запуск Flask-приложения: `QF_DASHBOARD_READ_ONLY=1 DASHBOARD_PORT=5051 python3 bot/ui/dashboard.py` — стартовало успешно, лог подтвердил `read_only=True · schema_ok=True · engine_autostart=False`.
- Состояние схемы БД: `python -m qf_platform.migrate --check` → «схема актуальна (версия в БД: 4, ожидается 4)».
- Полную карту маршрутов: 12 экранов SPA, 42 маршрута `/api/v2`, ~30 legacy `/api/*` и `/api/platform/*`.
- **Фактическое принуждение аутентификации** — HTTP-пробы всех значимых эндпоинтов без сессии.
- Заголовки безопасности живого ответа.
- Страницу `/login` во всех трёх её состояниях (по коду) и фактически отрендеренное состояние.
- Весь код SPA (5 816 строк JS) и backend (4 322 строки Python) чтением.

### Что проверить не удалось
- **Аутентифицированный интерфейс.** Учётные данные оператора отсутствуют; создание пользователя (`migrate --create-user`) — мутация БД и ввод пароля, что выходит за рамки разрешённого в этом аудите. Поэтому **визуальная проверка 12 экранов, их empty/error/loading-состояний, realtime-обновлений и мобильной адаптации не выполнялась.** Все утверждения об этих экранах ниже — из чтения кода и помечены INFERRED.
- Работу SSE-потока с реальными событиями (эндпоинт проверен только на принуждение auth).
- Поведение с реальным брокерским счётом.

### Установленный факт об окружении
На стенде **есть как минимум один оператор**: живая `/login` рендерит форму входа, а не баннеры «Оператор не создан» / «База данных недоступна» (проверено поиском `qf-login-form` = найдено, `Оператор не создан` = 0).

---

## Executive Summary

Dashboard — **функционально самая проработанная часть системы после сайта, и самая сильная по безопасности**. Это операторский терминал, а не клиентский кабинет: 12 экранов, 42 контрактных API-маршрута, серверные сессии с ролями, CSRF, идемпотентность мутаций и полный audit trail.

**Ключевой вывод по реальности данных: mock-данных в Dashboard практически нет.** Целенаправленный поиск `mock|demo|fake|placeholder|stub|dummy|hardcoded` по `bot/ui/static/app` и `bot/ui/api` не выявил ни одного подставного набора данных — единственные совпадения относятся к HTML-атрибуту `placeholder` в полях фильтра («SBER») и к комментарию об удалённой декоративной анимации. Все экраны читают реальные значения из TimescaleDB через `/api/v2`. **Это принципиально отличает Dashboard от демонстрационного терминала на сайте**, где значения намеренно синтетические и явно помечены как таковые (`dashboard.demoNote`).

**Безопасность — образцовая для этого класса приложений:**
- Аутентификация принуждается **fail-closed на уровне приложения** (`@app.before_request`), а не пер-роутом. Проверено пробами: **все** данные и действия отдают `401` без сессии; публичны только `/health` (тело — `{"db":true,"status":"ok"}`, ничего лишнего) и `/api/v2/auth/session`.
- Полноценный **CSP с per-request nonce**: `default-src 'self'; script-src 'self' 'nonce-…'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`.
- Сессионная cookie `HttpOnly` + `SameSite=Strict`; отдельная CSRF-cookie намеренно не `HttpOnly` (double-submit).
- Мутации проходят через `@mutating` с обязательной причиной, идемпотентностью и записью `state_before`/`state_after` в `audit_events`.

**Главные проблемы:**
1. **Dashboard — терминал одного оператора, а не кабинет клиента.** Нет ни подписки, ни профиля клиента, ни подключения собственного брокера — то, что перечислено в требованиях аудита («подписка», «подключение брокеров», «профиль») в продукте отсутствует как концепция ([D-01]).
2. **Werkzeug dev-сервер** — единственный способ запуска; production WSGI не настроен ([D-02]).
3. **Английская локаль — заглушка** («English is a stub with the same keys») при том что сайт двуязычен ([D-03]).
4. **72 контрактных теста аутентифицированных маршрутов пропускаются** по умолчанию, то есть основной API-контракт Dashboard в CI не проверяется ([Q-02](08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md)).
5. **Realtime реализован только на legacy v1** (`/api/platform/stream`), тогда как SPA работает через v2 ([D-04]).

---

## 1. Фактическая информационная архитектура (VERIFIED — из кода)

**Точка входа:** `bot/ui/dashboard.py` (57 строк, launcher) → `bot/ui/app_factory.py:create_app()` (294 строки).

`dashboard.py` был отрефакторен из 751-строчного модуля, который выполнял DDL и стартовал торговый поток **при импорте**. Сейчас импорт не делает ничего, кроме сборки приложения — это зафиксировано в docstring и подтверждается кодом.

**Навигация SPA** (`bot/ui/static/app/main.js:35-49`) — 12 экранов в двух группах:

| Группа | id | path | Назначение |
|---|---|---|---|
| Операционная | `overview` | `/` | Состояние движка, последние события, здоровье |
| | `portfolio` | `/portfolio` | Портфель и баланс |
| | `positions` | `/positions` | Открытые позиции (+ закрытие) |
| | `trades` | `/trades` | История сделок |
| | `signals` | `/signals` | Сигналы (+ исполнение) |
| | `strategies` | `/strategies` | Реестр стратегий и решений |
| | `backtest` | `/backtest` | Прогоны на истории |
| | `analytics` | `/analytics` | Разрезы по стратегиям/режимам |
| | `risk` | `/risk` | Лимиты и их использование |
| Служебная | `health` | `/status` | Системное здоровье |
| | `events` | `/events` | Журнал событий (фильтры level/q/correlation_id) |
| | `settings` | `/settings` | Учётные данные, смена пароля, обслуживание |

**Отдельный документ:** `/miniapp` — «Quant Hunter», игра (`bot/ui/static/miniapp/game.js`). Вынесена из операционной навигации осознанно: docstring `views.py:108` объясняет, что её 67 KB ассетов грузились на каждой странице дашборда — 21 % локального payload для скрытого экрана. Сейчас — отдельный маршрут.

**Deep links работают:** `views.py:82` регистрирует `/<any(portfolio, positions, trades, signals, strategies, backtest, analytics, risk, status, events, settings)>` и отдаёт ту же SPA-оболочку, поэтому прямая ссылка и перезагрузка сохраняют экран. Роутер (`router.js`) дополнительно запоминает последний маршрут в `localStorage` (`qf.lastRoute`), но **только** если URL ничего не сказал — явный URL всегда выигрывает. Причина зафиксирована в docstring: алерт не мог сослаться на экран, о котором он.

**Клавиатурные шорткаты** реализованы (`router.js:199`, `main.js:693` — `shell.shortcuts`).

## 2. API-поверхность (VERIFIED)

**`/api/v2` — актуальный контракт, 42 маршрута.** 26 read + 16 действий:

*Чтение:* `environment`, `faults`, `health`, `equity`, `equity/underwater`, `drawdown`, `accounts`, `portfolio`, `positions`, `trades`, `trades/learning`, `statistics`, `statistics/distribution`, `analytics/daily`, `signals`, `strategies`, `strategies/<id>`, `strategies/decisions`, `hypotheses`, `risk`, `risk/events`, `events`, `audit`, `market/coverage`, `market/candles`, `overview`.

*Действия:* `auth/session` (GET), `auth/login`, `auth/logout`, `auth/logout-all`, `auth/password`, `engine/start`, `engine/stop`, `faults/<code>/acknowledge`, `learning/run-cycle`, `backtest/run`, `positions/<id>/close`, `signals/<id>/execute`, `settings/credentials` (GET/POST), `settings/credentials/<key>/clear`, `maintenance/prune-equity`.

**Legacy `/api/v1`** — `bot/ui/legacy_api.py` (14 маршрутов: `/health`, `/api/tinkoff/*`, `/api/stats`, `/api/settings`, `/api/settings/tokens`, `/api/candles`, `/api/portfolio`, `/api/equity`, `/api/positions`, `/api/metrics`, `/api/log`, `/api/internal/push`) и `bot/ui/api/platform_routes.py` (~28 маршрутов `/api/platform/*`). Сохранены осознанно — для Telegram Mini App и bot-процесса, с GET'ами, приведёнными к read-only (задокументировано в `bot/ui/api/v2/__init__.py:8-11`).

**Контрактная дисциплина v2** — сильная сторона, детали в [02, A-07](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md#a-07-сильные-стороны-архитектуры-для-сохранения-при-рефакторинге). Кратко: единый envelope, `ErrorCode`, валидация каждого query-параметра с явной ошибкой вместо тихого fallback, разделение `DB_UNAVAILABLE` / `SCHEMA_OUT_OF_DATE`.

## 3. Реальность данных: что настоящее, что нет (VERIFIED)

| Область | Источник | Вердикт |
|---|---|---|
| Сделки, позиции, equity, сигналы, стратегии, гипотезы | TimescaleDB через репозитории `qf_platform` | **РЕАЛЬНЫЕ** |
| Портфель / баланс / операции брокера | `services/tinkoff/*` → Tinkoff Invest API | **РЕАЛЬНЫЕ** (при заданном токене; sandbox по умолчанию) |
| Paper-торговля | `paper_accounts` / `paper_positions` / `paper_trades` | **РЕАЛЬНЫЕ** (симулированное исполнение, настоящие записи) |
| Статистика/аналитика (Sharpe, drawdown, распределения) | `services/statistics_service.py`, `analytics_service` | **РЕАЛЬНЫЕ** вычисления над реальными сделками |
| «Уверенность» стратегий | `belief_system`, EMA-сглаживание | **РЕАЛЬНЫЕ** записи; **не ML** — см. [06](06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md) |
| Здоровье / faults / события | `health_service`, `faults_service`, `system_events` | **РЕАЛЬНЫЕ** |
| Учётные данные (экран Settings) | `credential_vault`, отдаётся только `{configured: bool, length: int}` | **РЕАЛЬНЫЕ**, значения не раскрываются |
| **Mock-данные** | — | **НЕ НАЙДЕНО** |

**Важное разграничение для маркетинга:** демонстрационный терминал на сайте (`website/src/components/sections/dashboard/dashboard-terminal.tsx`) — синтетический и **честно помечен** («Значения демонстрационные и не являются результатами торговли»). Настоящий Dashboard синтетики не содержит. Расхождения «интерфейс обещает то, чего нет в backend» на уровне данных **не обнаружено**.

## 4. Findings

<a id="d-01"></a>
### [D-01] Dashboard — терминал оператора; клиентских сущностей (подписка, профиль, подключение своего брокера) не существует

**Статус:** VERIFIED
**Критичность:** Critical
**Приоритет:** P0
**Компонент:** `bot/ui/`, `bot/qf_platform/schema.py`
**Доказательство:**
- Экран `settings` управляет **системными** учётными данными через `credential_vault` (`/api/v2/settings/credentials`), то есть токенами самой установки, а не «подключением брокера клиентом».
- Таблица `dashboard_users` (`schema.py:450`) содержит `username`, `password_hash`, `role`, `trading_authorized` — операторские поля. Ни `email`, ни `subscription_*`, ни `broker_credentials_id`.
- В навигации нет экранов «Подписка», «Профиль», «Тариф», «Оплата» (12 экранов перечислены выше).
- `grep -rniE "subscription|billing|stripe|payment" bot/` → 0 (кроме поля `payment` в брокерских операциях Tinkoff).
- Онбординга нет: `grep -rniE "onboarding|wizard|getting.?started"` по `bot/ui` — совпадений нет.
**Файлы и маршруты:** `bot/ui/static/app/main.js:35-49`, `bot/qf_platform/schema.py:450`, `/api/v2/settings/credentials`
**Текущее поведение:** Вход по логину/паролю оператора, созданному через CLI (`migrate --create-user`). Один набор системных ключей, один брокерский счёт, общие для всех, кто войдёт.
**Ожидаемое поведение (согласно сайту):** Пользователь регистрируется, получает Sandbox на 7 дней, оформляет подписку, подключает **свой** брокерский ключ, видит **свои** данные.
**Влияние на пользователя:** Второй клиент, войдя, увидел бы данные первого. Регистрация невозможна — только ручное создание оператора в CLI.
**Влияние на бизнес:** Заявленный на сайте путь «Sandbox → Live по подписке» технически не существует. Блокер запуска.
**Техническое влияние:** Это проявление [A-01](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md#a-01) на уровне UI, а не отдельный дефект Dashboard.
**Корневая причина:** Dashboard проектировался как внутренний операторский инструмент; клиентский слой не начинали.
**Рекомендация:** Не строить клиентский кабинет до решения по [OQ-ARCH-01](14_OPEN_QUESTIONS_AND_DECISIONS.md). При выборе «single-tenant per client» текущий Dashboard пригоден почти без изменений — меняется только процедура provisioning.
**Зависимости:** [A-01], [B-05]
**Оценка объёма:** XL (multi-tenant) / S (provisioning-скрипт при single-tenant)
**Критерии приёмки:** Зафиксированное ADR; при multi-tenant — тест, что оператор A не видит данных оператора B.
**Roadmap ID:** RM-P0-001

---

<a id="d-02"></a>
### [D-02] Production-запуск не настроен: единственный путь — Werkzeug dev-сервер

**Статус:** VERIFIED
**Критичность:** High
**Приоритет:** P1
**Компонент:** Deployment Dashboard
**Доказательство:**
- Живой лог запуска содержит предупреждение самого Flask: `WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.`
- Заголовок ответа: `Server: Werkzeug/3.1.8 Python/3.11.0`.
- `requirements.txt` **не содержит** ни `gunicorn`, ни `waitress`, ни `uvicorn`.
- `bot/ui/dashboard.py:56` — `app.run(host=..., port=..., debug=use_debug, use_reloader=use_debug)`.
- WSGI-точка существует (`app` экспортируется на уровне модуля, docstring упоминает `ui.dashboard:app`), то есть подключить сервер несложно — просто не сделано.
- `docs/WINDOWS_DEPLOYMENT.md` описывает запуск как Windows-службы через NSSM, что оборачивает тот же dev-сервер.
**Файлы и маршруты:** `bot/ui/dashboard.py:38-57`, `requirements.txt`, `start.ps1`
**Текущее поведение:** Однопоточный dev-сервер без поддержки нагрузки, без graceful reload; SSE-поток (`/api/platform/stream`) держит воркер занятым.
**Ожидаемое поведение:** `waitress` (Windows-совместим, а деплой заявлен на Windows Server 2019) или `gunicorn` за реверс-прокси.
**Влияние на пользователя:** Зависания при нескольких открытых вкладках, особенно с SSE.
**Влияние на бизнес:** Не соответствует production-требованиям для финансового приложения.
**Техническое влияние:** Точка внедрения готова; нужен один пакет и правка стартового скрипта.
**Корневая причина:** Деплой-контур не завершён.
**Рекомендация:** Добавить `waitress` в `requirements.txt`, запускать `waitress-serve --listen=127.0.0.1:5001 ui.dashboard:app`, оставив `app.run` только для локальной разработки. Обязательно за TLS-терминирующим прокси (см. [S-07](07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md) о HSTS).
**Зависимости:** [S-07]
**Оценка объёма:** S
**Критерии приёмки:** В production заголовок `Server` не содержит `Werkzeug`; предупреждение в логе отсутствует; SSE работает при ≥3 одновременных клиентах.
**Roadmap ID:** RM-P1-012

---

<a id="d-03"></a>
### [D-03] Английская локаль Dashboard — заглушка

**Статус:** VERIFIED
**Критичность:** Medium
**Приоритет:** P2
**Компонент:** `bot/ui/static/app/i18n.js`
**Доказательство:** Docstring файла (строка 2): «The locale layer. Russian is complete; English is a stub with the same keys.» Файл — 310 строк.
**Файлы и маршруты:** весь Dashboard
**Текущее поведение:** Русский полон; английский существует структурно (ключи есть), но переводы — заглушки.
**Ожидаемое поведение:** Либо полный английский (сайт двуязычен и продаёт «Партнёру и разработчику»), либо явное отсутствие переключателя языка, чтобы не показывать полупереведённый интерфейс.
**Влияние на пользователя:** Англоязычный оператор увидит смесь языков.
**Влияние на бизнес:** Сайт обещает англоязычную поверхность (`/en`), продукт её не даёт.
**Техническое влияние:** Структура готова, нужен перевод.
**Корневая причина:** Приоритет русской версии.
**Рекомендация:** Решить по [OQ-UX-03](14_OPEN_QUESTIONS_AND_DECISIONS.md). Дешёвый честный вариант на beta — скрыть переключатель до готовности перевода.
**Зависимости:** —
**Оценка объёма:** M (перевод) / XS (скрыть)
**Критерии приёмки:** Либо все ключи переведены и проверены, либо EN недоступен в UI.
**Roadmap ID:** RM-P2-013

---

<a id="d-04"></a>
### [D-04] Realtime реализован только в legacy v1, тогда как SPA работает через v2

**Статус:** VERIFIED
**Критичность:** Medium
**Приоритет:** P2
**Компонент:** `bot/ui/api/platform_routes.py:426`, `bot/realtime/`
**Доказательство:**
- SSE-эндпоинт — `@platform_bp.route("/stream")`, то есть `/api/platform/stream` (**legacy v1**). Реализация: `sse_hub.subscribe()`, keepalive каждые 25 с, заголовки `text/event-stream`, `X-Accel-Buffering: no`.
- В списке 42 маршрутов `/api/v2` эндпоинта потока **нет**.
- Документированное правило (`bot/ui/api/v2/__init__.py:11`) — «операционный дашборд говорит только с v2». Realtime это правило нарушает.
- Модуль `bot/realtime/` — всего 2 файла / 55 строк.
- Auth принуждается (unauth-проба `/api/platform/stream` → **401**), так что дыры в безопасности нет.
**Файлы и маршруты:** `/api/platform/stream`
**Текущее поведение:** Для realtime SPA обязана обращаться к legacy-слою, который планируется удалить. Это привязывает срок жизни v1 к realtime-функциональности.
**Ожидаемое поведение:** `/api/v2/stream` с тем же envelope-подходом к событиям.
**Влияние на пользователя:** Нет прямого — работает.
**Влияние на бизнес:** Блокирует удаление v1 ([A-06]).
**Техническое влияние:** Перенос простой; вопрос в контракте события.
**Корневая причина:** SSE появился до введения v2.
**Рекомендация:** Перенести поток в v2 в рамках плана удаления v1; сохранить формат события, чтобы не ломать Mini App одновременно.
**Зависимости:** [A-06]
**Оценка объёма:** S
**Критерии приёмки:** `/api/v2/stream` работает; SPA не обращается ни к одному `/api/platform/*`.
**Roadmap ID:** RM-P2-014

---

<a id="d-05"></a>
### [D-05] Сильные стороны Dashboard (сохранить)

**Статус:** VERIFIED — положительное наблюдение

1. **Fail-closed аутентификация на уровне приложения.** `@app.before_request` (`app_factory.py:256,281`) — с прямым замечанием в коде, что прежняя модель была инверсной (allow-list по IP). Проверено пробами:

| Эндпоинт | Без сессии |
|---|---|
| `/api/v2/health`, `/environment`, `/portfolio`, `/positions`, `/trades`, `/equity`, `/faults` | **401** |
| `/api/v2/settings/credentials` | **401** |
| `/api/platform/overview`, `/signals`, `/stream` | **401** |
| `/api/stats`, `/api/settings/tokens` | **401** |
| POST `/api/v2/engine/start`, `/engine/stop`, `/learning/run-cycle` | **401** |
| POST `/api/platform/engine/start`, `/signals/generate` | **401** |
| `/` | **302** → `/login` |
| `/health` (публичный намеренно) | 200, тело `{"db":true,"status":"ok"}` |
| `/api/v2/auth/session` (публичный намеренно) | 200 |

2. **Полноценный CSP с nonce** — живой заголовок:
   `default-src 'self'; script-src 'self' 'nonce-…'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`.
   **Это решение той самой задачи, которую сайт отложил** ([S-02](07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md)) — паттерн в проекте уже есть.
3. **Корректные cookie:** сессионная `HttpOnly` + `SameSite=Strict`; CSRF-cookie намеренно не `HttpOnly` (`session_auth.py:318-343`) с объяснением: «бесполезна без HttpOnly сессионной cookie».
4. **Трассировка запросов:** `X-Request-ID` и `X-Correlation-ID` в каждом ответе; экран `events` фильтруется по `correlation_id`.
5. **Режим `QF_DASHBOARD_READ_ONLY=1`** — при старте логирует точный перечень того, что стало неизменяемым, и что осталось доступным (сессии и журналы). Позволяет проводить QA против реальных данных — этим аудитом и воспользовался.
6. **Движок не стартует сам:** `engine_autostart=False` по умолчанию, требуется `QF_DASHBOARD_AUTOSTART_ENGINE=1` либо кнопка оператора. Для торгового приложения — правильный дефолт.
7. **`QF_DASHBOARD_DEBUG` отказывает при небезопасном bind:** `dashboard.py:47-53` отклоняет debug-консоль Werkzeug, если host не loopback, с прямой формулировкой «консоль Werkzeug это удалённое выполнение кода».
8. **Схема не миграция при старте:** `verify_schema()` только читает; при дрейфе — envelope `SCHEMA_OUT_OF_DATE` с инструкцией, а не тихая миграция.
9. **Честные состояния `/login`:** три различённых случая — БД недоступна / оператор не создан (с точной CLI-командой) / форма. Обоснование в коде: «форма, которая не может сработать, с общим "неверный пароль" — это обращение в поддержку».
10. **Идемпотентность и аудит мутаций:** `@mutating(action="position.close", idempotent=True, require_reason=True)` — запись `state_before`/`state_after`, `idempotency_key`, `actor_role`, `environment` в `audit_events`.

## 5. Сценарии оператора: что работает (INFERRED — из кода, без визуальной проверки)

| Сценарий | Маршрут | Статус |
|---|---|---|
| Вход / выход / выход со всех устройств | `POST /api/v2/auth/login`, `logout`, `logout-all` | FUNCTIONAL |
| Смена пароля | `POST /api/v2/auth/password` | FUNCTIONAL |
| Запуск / остановка движка | `POST /api/v2/engine/start`, `stop` | FUNCTIONAL |
| Просмотр портфеля, позиций, сделок, equity, просадки | 26 read-маршрутов | FUNCTIONAL |
| **Закрытие позиции** | `POST /api/v2/positions/<id>/close` | FUNCTIONAL, с идемпотентностью + причиной + аудитом |
| **Исполнение сигнала** | `POST /api/v2/signals/<id>/execute` | FUNCTIONAL, с идемпотентностью + аудитом |
| Запуск бэктеста и выгрузка | `POST /api/v2/backtest/run`, `/api/platform/backtest/runs/<id>/export` | FUNCTIONAL |
| Цикл обучения вручную | `POST /api/v2/learning/run-cycle` | FUNCTIONAL |
| Подтверждение fault | `POST /api/v2/faults/<code>/acknowledge` | FUNCTIONAL |
| Управление системными ключами | `GET/POST /api/v2/settings/credentials`, `/clear` | FUNCTIONAL (значения не раскрываются) |
| Обслуживание equity | `POST /api/v2/maintenance/prune-equity` | FUNCTIONAL |
| Просмотр audit trail | `GET /api/v2/audit` | FUNCTIONAL |
| **Подтверждение/отклонение автоматической сделки** | — | **ОТСУТСТВУЕТ** — см. [A-02](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md#a-02) |
| **Режим advice-only** | — | **ОТСУТСТВУЕТ** |
| **Автоматический режим (вкл/выкл как режим)** | — | Есть только start/stop движка; режимов исполнения нет |
| **Подписка / оплата / профиль клиента** | — | **ОТСУТСТВУЕТ** — [D-01] |
| **Онбординг** | — | **ОТСУТСТВУЕТ** |

**Про «режим автоматической торговли» и «advice-only» из требований аудита:** этих режимов в продукте нет как концепции. Есть бинарное «движок запущен / остановлен», и запущенный движок торгует автономно. Введение режимов — задача RM-P0-002.

## 6. Состояния UI, адаптивность, доступность (INFERRED / UNVERIFIED)

**INFERRED из кода** — инфраструктура состояний присутствует и выглядит проработанной:
- Ошибки: envelope с `ErrorCode`; `ui.js` (618 строк) содержит компоненты `qf-state--error`; отдельные коды для `DB_UNAVAILABLE` и `SCHEMA_OUT_OF_DATE` доходят до UI как разные сообщения.
- Faults: отдельный экран + `fault.action.hint` (`main.js:404`) — подсказка действия при неисправности.
- Пустые состояния: `table.js` (463 строки) и `qf-state` в `ui.js` — есть.
- Загрузка: `store.js` + `sync.js` (317 строк) управляют состоянием синхронизации.
- Формы: поля пароля с корректными `autocomplete="current-password"` / `"new-password"` (`main.js:606-607`) — мелочь, но признак внимания к деталям.

**UNVERIFIED:** визуальная иерархия, отступы, контраст, hover/focus-состояния, поведение при скролле, мобильная адаптация (реальные ширины), работа со скринридером — **не проверялись**, поскольку аутентифицированный интерфейс недоступен. Существующие внутренние документы по этой теме (`design/DASHBOARD_UIUX_AUDIT.md` — 447 строк, под версионным контролем с 2026-08-06; `design/DASHBOARD_APPROVED_REFERENCE_AUDIT.md` — 2 493 строки) описывают редизайн; их актуальность оценена в [13](13_STALE_DOCUMENTS_REGISTER.md).

Существует собственный гейт токенов Dashboard: `bot/ui/static/check-dashboard-tokens.mjs` — аналог `check:design` сайта. В `package.json` он не подключён (у Dashboard нет `package.json`), то есть запускается вручную.

## 7. Визуальная согласованность с сайтом (INFERRED)

Общие признаки единой системы: те же шрифты Geist (`bot/ui/static/fonts/geist-*.woff2`, включая кириллические подмножества), собственный слой токенов (`static/css/tokens.css`), тёмная палитра. Сайт при этом собран на Tailwind 4 с токенами в `website/src/styles/tokens`, а Dashboard — на рукописном CSS. **Два независимых набора токенов для одного бренда** — риск расхождения; проверить фактическое совпадение значений не удалось (нужен доступ к UI). Отмечено как задача сверки RM-P2-015.

---

## Top Critical Findings

1. **[D-01]** Dashboard — операторский терминал; подписки, профиля клиента и подключения своего брокера не существует. Блокер запуска.
2. **[D-02]** Production-запуск не настроен — Werkzeug dev-сервер.
3. **[A-02]** Подтверждение автоматических сделок отсутствует и в Dashboard тоже (нет режимов исполнения).
4. **[Q-02]** 72 контрактных теста аутентифицированных маршрутов пропускаются — основной API-контракт не покрыт в CI.
5. **[D-04]** Realtime только в legacy v1 — блокирует удаление v1.

## Quick Wins

| ID | Действие | Объём |
|---|---|---|
| [D-02] | Добавить `waitress` и заменить `app.run` в production | S |
| [D-03] | Скрыть переключатель EN до готовности перевода | XS |
| [Q-02] | Задать `QF_TEST_USER`/`QF_TEST_PASSWORD` в CI, включив 72 теста | S |
| — | Подключить `check-dashboard-tokens.mjs` в общий прогон проверок | XS |

## Launch Blockers

- [D-01] Нет клиентского слоя (подписка/профиль/свой брокер).
- [A-02] Нет обязательного подтверждения для автономных сделок.
- [D-02] Нет production WSGI.
- [Q-01] Нет CI/CD ([08](08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md)).

## Recommended Next Steps

1. Решить [OQ-ARCH-01](14_OPEN_QUESTIONS_AND_DECISIONS.md) — от этого зависит, нужен ли клиентский кабинет вообще.
2. Ввести production WSGI (RM-P1-012).
3. Включить 72 пропущенных контрактных теста в CI (RM-P0-003).
4. Провести **визуальный** аудит аутентифицированного Dashboard — создать тестового оператора в отдельной dev-БД (это выходило за рамки текущего аудита).
5. Перенести SSE в v2 (RM-P2-014).

## Open Questions

См. [14](14_OPEN_QUESTIONS_AND_DECISIONS.md): OQ-ARCH-01 (модель доступа), OQ-ARCH-02 (срок удаления v1), OQ-UX-03 (судьба английской локали Dashboard), OQ-OPS-01 (кто и как создаёт операторов в production).

## Уровень уверенности аудита

**Высокий** для карты маршрутов, API-контракта, принуждения аутентификации, заголовков безопасности, состояния схемы и реальности данных — всё проверено запуском, HTTP-пробами и чтением кода.
**Средний** для операторских сценариев — код прочитан целиком, но не выполнялся под аутентификацией.
**Низкий / не проверено** для визуальной части: UI-состояния, адаптивность, доступность, realtime в действии, согласованность токенов с сайтом. Это **главный пробел данного документа**; для его закрытия нужен доступ к аутентифицированному интерфейсу.
