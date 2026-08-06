---
name: quant-source-context
description: >
  Навигация по базе знаний Quant/QuantFlow. Используй, когда нужно понять, в каком
  документе искать ответ, можно ли доверять найденному факту, какой источник истины
  по теме, что уже признано устаревшим и какие расхождения между документами и кодом
  уже найдены. Обязателен перед тем, как утверждать факт о проекте.
  Ключевые слова: где написано, какой документ, источник истины, актуально ли,
  можно ли верить, docs/source, Source Pack, устаревший документ, противоречие,
  какой файл авторитетнее, что читать по теме.
version: 1.0.0
metadata:
  applies_to: все четыре постоянных чата
---

# Quant — навигация по источникам

> Общие правила — [`AGENTS.md`](../../../AGENTS.md). Этот skill — про **выбор источника**,
> а не про роль.

## Mission

Не дать агенту утверждать факт о проекте, не сверив его с правильным источником.
Никто не читает Source Pack целиком: 15 документов, ~700 КБ. Читается один документ
под конкретный вопрос.

## Trigger

Перед любым утверждением о проекте, которое можно проверить: путь, число, endpoint,
имя таблицы, значение токена, версия, состояние функции, наличие теста.

## Приоритет источников

1. **Текущий код** — окончательная истина всегда.
2. **`docs/source/`** — 15 документов, истина на момент своего коммита (`a54a100`).
3. Всё остальное — справочно, с обязательной проверкой.

Фактические значения на 2026-08-06: ветка `quant-site-approved-reference-redesign`,
HEAD `7f357e3`, тесты `161 passed, 72 skipped`, документов в `docs/source` — **15**
(число 14 неверно).

## Куда идти с вопросом

| Вопрос | Документ |
|---|---|
| Что за проект, как запустить, терминология | `docs/source/01_CURRENT_PROJECT_CONTEXT.md` |
| Как устроена система | `docs/source/02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md` |
| Сайт: маршруты, контент, SEO, a11y | `docs/source/03_WEBSITE_AUDIT.md` |
| Дашборд: 12 экранов, `/api/v2`, legacy | `docs/source/04_DASHBOARD_AUDIT.md` |
| Telegram и Mini App | `docs/source/05_TELEGRAM_BOT_AUDIT.md` |
| Данные, репозитории, сервисы, интеграции | `docs/source/06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md` |
| Безопасность, приватность, соответствие | `docs/source/07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md` |
| Тесты, гейты, производительность | `docs/source/08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md` |
| Аудитория, воронка, монетизация | `docs/source/09_PRODUCT_UX_MARKETING_AND_MONETIZATION_AUDIT.md` |
| Состояние компонента | `docs/source/10_CURRENT_DEVELOPMENT_STATUS.md` |
| Что делать и в каком порядке | `docs/source/11_MASTER_ROADMAP.md` |
| Кто за что отвечает (домены) | `docs/source/12_AGENT_WORKSTREAMS_AND_RESPONSIBILITIES.md` |
| Можно ли верить старому документу | `docs/source/13_STALE_DOCUMENTS_REGISTER.md` |
| Что нужно решить до начала работы | `docs/source/14_OPEN_QUESTIONS_AND_DECISIONS.md` |
| Состав пакета, что перепроверять | `docs/source/SOURCE_MANIFEST.md` |
| Карта всего контекста | `docs/agents/QUANT_CONTEXT_INDEX.md` |

## Источники истины в коде (авторитетнее любого документа)

| Тема | Источник истины | Устаревший дубль — не использовать |
|---|---|---|
| Схема БД | `bot/qf_platform/schema.py` | `quantflow_schema.sql` (5 таблиц, не авторитетен) |
| Дизайн-токены сайта | `website/src/styles/tokens/` | `design/DESIGN_SYSTEM.md` |
| Дизайн-токены дашборда | `bot/ui/static/css/tokens.css` | — |
| Торговые правила | `knowledge/rules/rules.yaml` | `knowledge/rules.yaml` (дубль) |
| Переменные окружения | `bot/config.py`, `.env.example` | `CLAUDE.md` (исторически врал) |
| Контент сайта | `website/messages/{ru,en}.json` | — |
| Контракт API | `bot/ui/api/v2/` | `bot/ui/legacy_api.py`, `bot/ui/api/platform_routes.py` |

## Документы, которые НЕЛЬЗЯ использовать как основание для решения

Перечислены в `docs/source/13_STALE_DOCUMENTS_REGISTER.md`. Среди них: `README.md`,
`docs/PROJECT_ARCHITECTURE.md`, `docs/PROJECT_STRUCTURE.md`, `docs/README.md`,
`design/ROADMAP.md`, `design/AUDIT_REPORT.md`, `docs/windows-deployment.md`,
`design/DESIGN_SYSTEM.md`, `design/screens/P*.md`.

## Расхождения, которые уже найдены — не искать заново

Полный список — `docs/source/SOURCE_MANIFEST.md` и
`docs/agents/context/*/KNOWN_CONTRADICTIONS.md`. Самое важное:

- **Все 15 документов** фиксируют HEAD `a54a100`; фактический — `7f357e3`.
- `01` заявляет «187 .py файлов под `bot/`» — фактически **176**.
- `00` и `14` заявляют «27 открытых вопросов» — фактически определено **37**.
- `00` и `11` заявляют «50 findings» — фактически 55 блоков, из них проблемных 48.
- Бейдж `License: MIT` приписывается корневому `README.md` — там нет упоминания лицензии
  вовсе; бейдж в `docs/README.md`, файла `LICENSE` нет.
- Каталог `docs/adr/` **не существует** — ни одного ADR не создано, поэтому формально
  все открытые вопросы открыты.
- `.github/workflows` отсутствует полностью — CI нет.

## Prohibited actions

- Не утверждать факт о проекте по памяти или по документу, если рядом есть код.
- Не пересказывать документ как текущее состояние, не проверив его дату и HEAD.
- Не использовать `quantflow_schema.sql`, `design/DESIGN_SYSTEM.md`,
  `docs/PROJECT_ARCHITECTURE.md` как основание.
- Не читать вторую копию репозитория `/Users/danila/Documents/GitHub/Trading-Bot` —
  она не canonical, отстаёт более чем на 140 коммитов и агентам недоступна.
- Не увеличивать контекст «на всякий случай»: один вопрос — один документ.

## Definition of Done

Утверждение о проекте считается обоснованным, только если названы: источник,
его дата или коммит, и — при расхождении с кодом — то, что верно по коду.
