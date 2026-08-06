# QUANT CONTEXT INDEX — карта контекста для всех агентов

**Дата:** 2026-08-06. **Проверено фактически**, не пересказано.

Это компактный вход. Ни один агент не читает базу знаний целиком: 15 документов Source
Pack — около 700 КБ. Читается **один документ под конкретный вопрос**.

---

## 1. Карта проекта

**Quant** (внутреннее имя **QuantFlow**) — алгоритмический торговый оператор для
Московской биржи. Три слабо связанные части:

| Часть | Где | Что это |
|---|---|---|
| Маркетинговый сайт | `website/` | Next.js 15 + next-intl, локали `/ru` и `/en`, порт 3000 |
| Операторский Dashboard | `bot/ui/` | Flask + SPA на vanilla ES-модулях, 12 экранов, порт 5001 |
| Торговый бот и движок | `bot/` | торговый цикл `bot/main.py`, Telegram через `python-telegram-bot` |
| Платформенный слой | `bot/qf_platform/` | схема, репозитории, сервисы, контракт `/api/v2` |
| База данных | Docker | TimescaleDB (pg15), ~20 таблиц, `SCHEMA_VERSION = 4` |

**Канонический корень:** `/Users/danila/Downloads/Trading-Bot-merge-learning-nik`
**Remote:** `https://github.com/Pomiranov/Trading-Bot.git` (private), default branch `main`
**Вторая копия** `/Users/danila/Documents/GitHub/Trading-Bot` — **не canonical**, отстаёт
более чем на 140 коммитов, агентам недоступна.

### Замеренные факты на 2026-08-06

| Величина | Значение | Как получено |
|---|---|---|
| Ветка | `quant-site-approved-reference-redesign` | `git rev-parse --abbrev-ref HEAD` |
| HEAD | `7f357e3` | `git rev-parse --short HEAD` |
| Тесты | **161 passed, 72 skipped** | `python3 -m pytest tests/ -q` |
| Python-файлов под `bot/` | **176** | `find bot -name '*.py'` |
| Тестовых файлов | 7 `test_*.py`, 233 собираемых теста | `find tests -name 'test_*.py'` |
| Файлов `website/` (source) | 150 | без `node_modules`, `.next` |
| Документов Source Pack | **15** | `ls docs/source/*.md` |

Число «14 документов» — **неверно**. Число «187 .py файлов» из
`01_CURRENT_PROJECT_CONTEXT.md` — **неверно**, фактически 176.

---

## 2. Источники истины

Приоритет, от высшего к низшему (`AGENTS.md §2`):

1. **Текущий код** — окончательная истина всегда.
2. **`docs/source/`** — 15 документов, истина на момент коммита `a54a100`.
3. Всё остальное — справочно, с обязательной проверкой.

| Тема | Источник истины | Устаревший дубль — не использовать |
|---|---|---|
| Схема БД | `bot/qf_platform/schema.py` | `quantflow_schema.sql` (5 таблиц, не авторитетен) |
| Дизайн-токены сайта | `website/src/styles/tokens/` | `design/DESIGN_SYSTEM.md` |
| Дизайн-токены дашборда | `bot/ui/static/css/tokens.css` | — |
| Торговые правила | `knowledge/rules/rules.yaml` | `knowledge/rules.yaml` (идентичный дубль) |
| Переменные окружения | `bot/config.py`, `.env.example` | `CLAUDE.md` (исторически врал) |
| Контент сайта | `website/messages/{ru,en}.json` | — |
| Контракт API | `bot/ui/api/v2/` | `bot/ui/legacy_api.py`, `bot/ui/api/platform_routes.py` |
| Аутентификация | `bot/security/session_auth.py`, `bot/auth/session_manager.py` | `bot/auth/jwt_service.py` (мёртвый слой) |

---

## 3. Source Pack — 15 документов

| Файл | О чём | Обязателен для |
|---|---|---|
| `00_SOURCE_INDEX.md` | состав пакета, порядок чтения, обозначения | ALL |
| `01_CURRENT_PROJECT_CONTEXT.md` | что за проект, стек, как запустить, терминология | ALL |
| `02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md` | как устроена система | ENGINEERING, PM, BA, SECURITY |
| `03_WEBSITE_AUDIT.md` | сайт: маршруты, контент, SEO, a11y, адаптивность | ENGINEERING, UIUX, MARKETING, SEO |
| `04_DASHBOARD_AUDIT.md` | дашборд: 12 экранов, 42 маршрута `/api/v2`, legacy | ENGINEERING, UIUX, PM, INFRA |
| `05_TELEGRAM_BOT_AUDIT.md` | Telegram и Mini App | ENGINEERING, SECURITY |
| `06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md` | данные, репозитории, сервисы, брокеры | ENGINEERING, INFRA, SECURITY, BA |
| `07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md` | безопасность, приватность, соответствие | SECURITY, ENGINEERING, INFRA, PM |
| `08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md` | тесты, гейты, производительность | ENGINEERING, INFRA, PM |
| `09_PRODUCT_UX_MARKETING_AND_MONETIZATION_AUDIT.md` | аудитория, воронка, монетизация | PM, BA, MARKETING |
| `10_CURRENT_DEVELOPMENT_STATUS.md` | состояние 30 компонентов | PM, BA, ENGINEERING |
| `11_MASTER_ROADMAP.md` | что делать и в каком порядке, 7 фаз | PM, BA, ENGINEERING, SECURITY, INFRA |
| `12_AGENT_WORKSTREAMS_AND_RESPONSIBILITIES.md` | кто за что отвечает, терминология | ALL |
| `13_STALE_DOCUMENTS_REGISTER.md` | можно ли верить старому документу | PM, BA, ENGINEERING, UIUX |
| `14_OPEN_QUESTIONS_AND_DECISIONS.md` | что решить до начала работы | PM, BA, ENGINEERING, SECURITY, INFRA |

Полный инвентарь с проверкой по коду — [`docs/source/SOURCE_MANIFEST.md`](../source/SOURCE_MANIFEST.md).

---

## 4. Правила выбора документа

| Вопрос | Куда идти |
|---|---|
| Что за проект, как запустить | `01` |
| Как это устроено внутри | `02` |
| Почему сайт выглядит и говорит так | `03`, `09` |
| Какие экраны и какие endpoint у дашборда | `04` |
| Как работает Telegram / Mini App | `05` |
| Где лежат данные, какие таблицы, какие брокеры | `06` |
| Насколько это безопасно, что с приватностью | `07` |
| Что проверяется, какие гейты, что красное | `08` |
| Кто пользователь, как он приходит, как платит | `09` |
| Готово ли это | `10` |
| Что делать дальше | `11` |
| Чья это задача | `12` |
| Можно ли верить этому файлу | `13` |
| Почему это нельзя начинать | `14` |

Правило: **если ответ есть в коде — идти в код, а не в документ.**
Если задача упирается в документ другой роли — это признак, что задача принадлежит
другому чату (см. [`PERMANENT_CHAT_POLICY.md`](PERMANENT_CHAT_POLICY.md)).

---

## 5. Статус актуальности

Все 15 документов оценены как **в основном актуальны** (`MOSTLY_CURRENT`): они описывают
срез `a54a100`, текущий HEAD `7f357e3` — отставание на один коммит, содержательно
почти ничего не изменилось.

Подтверждение кодом по выборочной проверке (5–8 утверждений на документ):

| Подтверждён полностью | Подтверждён частично |
|---|---|
| `03`, `04`, `07`, `11`, `12` | `00`, `01`, `02`, `05`, `06`, `08`, `09`, `10`, `13`, `14` |

«Частично» означает, что часть проверенных утверждений разошлась с кодом — конкретика
в `SOURCE_MANIFEST.md` и в `context/*/KNOWN_CONTRADICTIONS.md`.

### Расхождения, которые уже найдены — не искать заново

- Все 15 документов фиксируют HEAD `a54a100`; фактический `7f357e3`.
- `01`: «187 .py файлов под `bot/`» → фактически **176**.
- `00`, `14`: «27 открытых вопросов» → фактически определено **37**.
- `00`, `11`: «50 findings» → фактически 55 блоков, проблемных 48; `W-09` ссылается
  на несуществующий `RM-P3-018`, поэтому реальное покрытие 49 из 50.
- Бейдж `License: MIT` приписан корневому `README.md` — там нет упоминания лицензии
  вообще; бейдж в `docs/README.md`; файла `LICENSE` нет.
- `docs/adr/` **не существует** — ни одного ADR не создано.
- `.github/workflows` отсутствует — CI нет.
- Ни одна задача Roadmap на 2026-08-06 не выполнена.

---

## 6. Что заблокировано и почему

**12 Launch Blockers** (`11_MASTER_ROADMAP.md`). Из них шесть открытых вопросов
блокируют само планирование:

| ID | Вопрос | Крайний момент |
|---|---|---|
| `OQ-ARCH-01` | single-tenant per instance или multi-tenancy | до начала Phase 1 |
| `OQ-TRADE-01` | дефолтный `EXECUTION_MODE` | до `RM-P0-002` |
| `OQ-LEGAL-01` | модель согласия | до включения аналитики / трафика |
| `OQ-LEGAL-03` | статус деятельности | до первой live-сделки не-владельца |
| `OQ-SEC-01` | принять CVE или апгрейдить Next | до Release Gate Phase 1 |
| `OQ-BIZ-01` | монетизация | до Phase 3 |

Ключевое, что подтверждено кодом:

- `EXECUTION_MODE` в проекте **отсутствует полностью**; автономный вызов
  `place_market_order` жив на `bot/main.py:188`; кнопки подтверждения существуют только
  в legacy `bot/ui/telegram_bot.py`, который `main.py` не импортирует.
- Клиентского слоя нет: ноль совпадений `tenant|subscription|billing`, ни одна доменная
  таблица не имеет владельца, доступ по whitelist `chat_id`.
- Бэкапа БД нет вообще при наличии необратимого `POST /api/v2/maintenance/prune-equity`.
- Mini App заблокирован: серверной валидации `initData` нет ни строчки.
- Мониторинга и алертинга нет (ноль совпадений `sentry|prometheus|opentelemetry|grafana`).
- «AI/ML» — не ML: `bot/learning/` считает `current + (target - current) * 0.15`
  с клэмпом `[0.05, 0.95]` и минимумом 20 закрытых сделок. ML-библиотек нет,
  слова `bayes` в коде нет. README называет это «байесовской системой» — оверклейм.

---

## 7. Роль → свой context pack

| Чат | Pack | Skills |
|---|---|---|
| 01 Control Center | [`context/control-center/`](context/control-center/) | `quant-project-manager`, `quant-business-analyst` |
| 02 Engineering | [`context/engineering/`](context/engineering/) | `quant-engineering` |
| 03 UI/UX | [`context/uiux/`](context/uiux/) | `quant-uiux-designer` |
| 04 Marketing | [`context/marketing/`](context/marketing/) | `quant-marketing` |

Общие для всех: `quant-source-context`, `quant-handoff`.

В каждом pack: `README.md`, `REQUIRED_SOURCES.md`, `OPTIONAL_SOURCES.md`,
`CURRENT_FACTS.md`, `OPEN_QUESTIONS.md`, `KNOWN_CONTRADICTIONS.md`, `BOOTSTRAP_PROMPT.md`.

---

## 8. Карта документов агентской среды

| Документ | О чём |
|---|---|
| [`AGENTS.md`](../../AGENTS.md) | общие обязательные правила — единственный источник |
| [`CLAUDE.md`](../../CLAUDE.md) / [`GEMINI.md`](../../GEMINI.md) | тонкие дополнения по агенту |
| [`OPERATING_MODEL.md`](OPERATING_MODEL.md) | уровни ответственности, кто что решает |
| [`AGENT_RESPONSIBILITIES.md`](AGENT_RESPONSIBILITIES.md) | какой агент какие задачи берёт |
| [`PERMANENT_CHAT_POLICY.md`](PERMANENT_CHAT_POLICY.md) | четыре постоянных чата, изоляция, цикл задачи |
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | контекст кодовой базы для быстрого входа |
| [`QUANT_SOURCE_CONTEXT.md`](QUANT_SOURCE_CONTEXT.md) | сводка Source Pack: статусы, блокеры |
| [`MODEL_PROFILES.md`](MODEL_PROFILES.md) | какой профиль и модель под какую работу |
| [`TASK_SPECIFICATION.md`](TASK_SPECIFICATION.md) | формат постановки задачи |
| [`HANDOFF.md`](HANDOFF.md) | формат сдачи результата, 17 полей |
| [`WORKTREE_POLICY.md`](WORKTREE_POLICY.md) | изоляция, порядок работы с worktree |
| [`SECURITY_POLICY.md`](SECURITY_POLICY.md) | секреты, границы доступа |
| [`../source/SOURCE_MANIFEST.md`](../source/SOURCE_MANIFEST.md) | инвентарь Source Pack и что перепроверять |
| [`../GIT_WORKFLOW.md`](../GIT_WORKFLOW.md) | ветки, коммиты, PR |
