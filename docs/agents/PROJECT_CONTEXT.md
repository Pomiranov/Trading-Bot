# Project Context — Quant / QuantFlow

Достаточный контекст, чтобы начать работу над задачей **без повторного чтения всего репозитория**. Составлено 2026-08-06 по коду на commit `7f357e3`, ветка `quant-site-approved-reference-redesign`.

Приоритет источников — [`AGENTS.md §2`](../../AGENTS.md): **код > `docs/source/` > всё остальное**. Этот документ — навигационный слой над Source Pack, а не замена ему. Утверждения ниже проверены по коду; там, где утверждение взято из Source Pack, стоит ссылка.

---

## 1. Что это за продукт

Алгоритмическая торговая система для MOEX: генерация сигналов по декларативным правилам, риск-менеджмент, paper- и live-исполнение через брокерские API, операторский Dashboard, Telegram-бот и маркетинговый сайт.

**Главное ограничение, которое обязан знать каждый агент** (`docs/source/01 §8`):

> **Система однопользовательская. Сайт продаёт подписки.**
>
> В `bot/` нет ни одного совпадения на `tenant|subscription|billing|stripe`. Ни одна доменная таблица не имеет `owner_id`. Один глобальный брокерский счёт `TINKOFF_ACCOUNT_ID`. Telegram-доступ — статический whitelist `chat_id`. Сайт публикует цены 5 000 / 10 000 ₽/мес, при том что оплата не подключена.

**Практический вывод:** не начинать работу над клиентским кабинетом, подписками и онбордингом до решения `OQ-ARCH-01`.

---

## 2. Три слабо связанных продукта в одном репозитории

| Продукт | Технологии | Точка входа | Порт |
|---|---|---|---|
| **Торговое ядро + Telegram-бот** | Python, `python-telegram-bot>=20` | `bot/main.py` | — |
| **Операторский Dashboard** | Flask + vanilla JS SPA | `bot/ui/dashboard.py` | `127.0.0.1:5001` (по умолчанию) |
| **Маркетинговый сайт** | Next.js 15.5.22, React 19, TypeScript 5 | `website/` | `3000` (dev) |

Плюс общая инфраструктура: TimescaleDB (`5432`), Adminer (`8080`), база знаний `knowledge/`.

`bot/main.py` в одном процессе поднимает Telegram-бота (в отдельном потоке) и `trading_loop()`; захватывает PID-lock (`_acquire_pid_lock`), поэтому два экземпляра одновременно не работают.

---

## 3. Технологический стек (проверено по `requirements.txt` и коду)

| Слой | Технология |
|---|---|
| Telegram | **`python-telegram-bot>=20`** — не aiogram (`aiogram`: 0 вхождений) |
| Dashboard | Flask ≥3.1, Jinja2, vanilla JS |
| БД | TimescaleDB / PostgreSQL 15; `psycopg2-binary`, `asyncpg`, SQLAlchemy ≥2.0 |
| Индикаторы | `ta` ≥0.11, pandas ≥2.0 |
| Статистика | `scipy` ≥1.11 (для `hypothesis_engine`) |
| Брокеры | `tinkoff-investments` ≥0.2.0b55; Bybit REST (`bot/broker/bybit_client.py`); провайдеры `finam`, `tinkoff` |
| Безопасность | `cryptography` ≥42 (AES-256-GCM), `argon2-cffi` ≥23.1 |
| Мониторинг | `psutil` |
| Сайт | Next.js 15.5.22 (turbopack), React 19.1, TypeScript 5, Three.js / r3f, Framer Motion, Lenis |

**ML-библиотек в проекте нет.** Формулировки «AI», «машинное обучение», «нейросеть», «байесовский» к системе не применяются (`AGENTS.md §4`).

---

## 4. Карта каталогов

```
bot/                     ядро на Python
  main.py                единая точка входа: Telegram-бот + trading_loop, PID-lock
  config.py              загрузка .env → dataclass-конфиги (ИСТИНА по именам переменных)
  tg/                    Telegram: bot.py, handlers/, fsm/, menus/, middlewares/,
                         notifications/, formatters/
  ui/                    Dashboard: dashboard.py, api/ (platform_routes.py + v2/),
                         templates/, static/ (app.js, core/, views/, miniapp/)
  qf_platform/           платформенный слой: schema.py (ИСТИНА по схеме БД), migrate.py,
                         dto.py, contracts.py, repositories/, services/, bootstrap.py
  learning/              trading_orchestrator, hypothesis_engine, belief_updater,
                         decision_evaluator, feedback, memory_writer
  backtest/              engine.py, advanced_engine.py, run_*.py
  broker/                base.py, registry.py, tinkoff_client.py, bybit_client.py, providers/
  services/              bot_engine, broker_service, trading_service, paper_auto_engine,
                         statistics_service, user_store, tinkoff/
  security/              session_auth, dashboard_auth, credential_vault, encryption, audit,
                         csrf, guards, http_middleware, permissions, readonly, redaction, secrets
  auth/                  session_manager, passwords, cookies, csrf, brute_force,
                         user_repository, jwt_service (legacy), redis_client
  signals/               indicators.py, rules_engine.py
  risk/                  risk_manager.py
  market/                data_hub.py
  engine/                paper_engine.py
  realtime/              sse_hub.py
  gateway/               trade_gateway.py
  data/                  runtime, git-ignored (credential_vault.json, user_prefs.json)

website/                 Next.js: src/app/[locale]/, components/, content-layer/, lib/,
                         styles/tokens/ (ИСТИНА по дизайн-токенам), content/{en,ru}/,
                         messages/{ru,en}.json (ИСТИНА по контенту), scripts/ (гейты)
knowledge/               rules/rules.yaml (ИСТИНА по правилам), processed/, theory/, raw/
tests/                   platform_tests/, dashboard_tests/, security_tests/
docs/                    source/ (Source Pack 00–14), agents/ (эта среда), остальное — см. §9
design/                  дизайн-документы Dashboard (большая часть исторические)
scripts/                 validate.sh, agents/ (worktree-тулинг)
infra/                   logrotate/
Projects/trading-bot/    legacy, только docker-compose для БД
```

---

## 5. Данные

Схема — **`bot/qf_platform/schema.py`**, `SCHEMA_VERSION = 4`, 21 таблица. `quantflow_schema.sql` устарел, не использовать.

Основные группы таблиц:

| Группа | Таблицы |
|---|---|
| Сигналы и сделки | `trading_signals`, `trades`, `skipped_signals` |
| Paper trading | `paper_accounts`, `paper_positions`, `paper_trades` |
| Рынок | `candles`, `news` |
| Обучение | `belief_system`, `hypotheses`, `trade_feedback` |
| Бэктест / форвард | `backtest_runs`, `forward_state`, `equity_snapshots` |
| Операторы и доступ | `dashboard_users`, `dashboard_sessions`, `dashboard_login_attempts` |
| Аудит и надёжность | `audit_events`, `system_events`, `action_idempotency` |
| Миграции | `schema_migrations` |

Проверка схемы — безопасна, только читает:

```bash
python3 -m qf_platform.migrate --check
```

Создание оператора (единственный способ создать пользователя):

```bash
python3 -m qf_platform.migrate --create-user NAME --role administrator
```

---

## 6. API

| Контракт | Префикс | Файлы | Статус |
|---|---|---|---|
| **v2** | `/api/v2` | `bot/ui/api/v2/routes_read.py`, `routes_actions.py` | **актуальный** — envelope, коды ошибок, валидация всех параметров с отказом вместо тихого fallback |
| v1 / legacy | `/api/platform`, `/api/*` | `bot/ui/api/platform_routes.py` | legacy, срок удаления не решён (`OQ-ARCH-02`) |
| SSE | `/stream` | `bot/realtime/sse_hub.py` | живые обновления Dashboard |
| Сайт | `/api/beta` | `website/src/app/api/beta/route.ts` | заявка на доступ |

Маршруты сайта: `/[locale]` (ru/en), `/[locale]/style-tile`.

Контрактный слой `/api/v2` — сильная сторона проекта, **ломать нельзя** (`docs/source/01 §13`).

---

## 7. Потоки

**Сигнал → сделка:**

```
data_hub → signals/indicators + rules_engine (knowledge/rules/rules.yaml)
  → risk/risk_manager (сайзинг от ATR, стоп, дневной лимит, лимит позиций)
  → gateway/trade_gateway → paper_engine  |  broker (Tinkoff / Bybit)
  → запись в TimescaleDB → learning/ (memory_writer → decision_evaluator → belief_updater
    → hypothesis_engine) → уведомление Telegram + SSE в Dashboard
```

**Уверенность (confidence)** — скаляр в `belief_system`, EMA с α=0.15, границы [0.05, 0.95] (`bot/learning/belief_updater.py`). Это **не** вероятность и **не** ML-предсказание.

**Аутентификация оператора:** серверные сессии + Argon2id (`bot/security/session_auth.py`, `bot/auth/session_manager.py`, `bot/auth/passwords.py`), CSRF двойной, CSP с per-request nonce, двухуровневая защита от подбора, audit trail с переходами состояния. `bot/auth/jwt_service.py` — legacy, не «текущая модель».

---

## 8. Запуск и обязательные проверки

```bash
# База данных
docker compose up -d                      # trading_db (5432) + trading_adminer (8080)

# Dashboard
python3 bot/ui/dashboard.py               # 127.0.0.1:5001

# Торговый бот + Telegram  (ВНИМАНИЕ: не запускать, если может работать другой экземпляр)
python3 bot/main.py

# Сайт
cd website && npm run dev                 # :3000
```

Обязательные проверки перед сдачей (полностью — `AGENTS.md §5`):

```bash
cd website && npm run typecheck && npm run lint && npm run check && npm run build
python3 -m pytest tests/                        # ожидается 161 passed, 72 skipped
python3 -m qf_platform.migrate --check
node bot/ui/static/app/format.test.mjs          # ожидается 27/27
node bot/ui/static/check-dashboard-tokens.mjs   # красный (Q-02) — см. ниже
```

Гейты сайта: `check:content`, `check:i18n`, `check:design`, `check:media` — все четыре входят в `npm run check`.

**Известные красные гейты** (не ваша ответственность, если падали до правки): `check-dashboard-tokens.mjs` exit 1 (`Q-02` / `RM-P2-015`), `npm run qa:landing` exit 2 — не установлен Playwright (`Q-03` / `RM-P1-020`). `npm run build:messages` намеренно заблокирован — удалил бы 56 живых ключей.

CI отсутствует: каталога `.github/` в репозитории нет (`RM-P0-003`).

---

## 9. Документы: чему верить

**Верить:**

- `docs/source/00–14` — Source Pack, авторитетный набор;
- `docs/agents/*` — эта агентская среда;
- `docs/DASHBOARD_OPERATIONS.md`, `website/docs/SECURITY_REVIEW.md`, `website/docs/LANDING_COPY_REMOVALS.md`, `website/docs/adr/0001-monogram.md`, `bot/ui/static/miniapp/BOTFATHER.md`.

**Не считать актуальными** (`docs/source/13`):

`README.md` («байесовская», «институциональная платформа» — оверклейм) · `docs/PROJECT_ARCHITECTURE.md` (aiogram, JWT, не отражает `qf_platform`) · `docs/PROJECT_STRUCTURE.md` («ONE location») · `docs/README.md` (самый старый) · `design/ROADMAP.md` · `design/AUDIT_REPORT.md` · `docs/windows-deployment.md` (дубль) · все `website/docs/audit/*`, `website/docs/SITE_*`, `REDESIGN_QA_REPORT.md`, `REFERENCE_IMPLEMENTATION_PLAN.md`, `DESIGN_EXCELLENCE_AUDIT.md` — исторические.

Документы **не удалять** — помечать `DEPRECATED` со ссылкой на замену.

---

## 10. Launch Blockers (12) — коротко

Полностью: `docs/source/00 §9` и `docs/source/11_MASTER_ROADMAP.md`.

1. Нет клиентских аккаунтов / модели доступа — `RM-P0-001`
2. Автономная торговля без подтверждения при обещании обратного — `RM-P0-002`
3. Нет privacy policy / terms / раскрытия рисков — `RM-P1-011`
4. Нет биллинга при опубликованных ценах — `RM-P0-009`
5. Заявки на доступ по умолчанию не сохраняются — `RM-P0-006`
6. Нет бэкапа торговой истории и audit trail — `RM-P1-015`
7. Нет CI — `RM-P0-003`
8. Нет мониторинга и алертинга — `RM-P1-022`
9. Werkzeug dev-сервер в production — `RM-P1-012`
10. Audit trail неполон: не покрывает 2 из 3 путей исполнения сделки — `RM-P0-008`
11. SEO нерабочий (placeholder-домен) — `RM-P0-007`
12. Торговое ядро без тестов — `RM-P1-021`

Вопросы, блокирующие планирование: `OQ-ARCH-01` модель доступа · `OQ-TRADE-01` дефолтный режим исполнения · `OQ-LEGAL-01` модель согласия · `OQ-LEGAL-03` статус деятельности · `OQ-SEC-01` CVE или апгрейд Next · `OQ-BIZ-01` монетизация. **`OQ-OPS-07`** (две копии репозитория, `CLAUDE.md` направлял в устаревшую) — закрыт 2026-08-06 этой инфраструктурной задачей.

---

## 11. Технический долг

- Торговое окно в наивном локальном времени, лог заявляет UTC (`A-04`).
- Два Telegram-бота; уникальная функциональность в legacy (`A-05`).
- Дубли: `bot/auth/` vs `bot/security/`, `/api/v1` vs `/api/v2`, две схемы БД, два `rules.yaml` (`A-06`, `B-04`).
- ~12 000 строк торговой логики без тестов (`Q-05`).
- Решение не воспроизводимо: версия правил не сохраняется (`B-03`).
- 3 high-severity CVE в npm-дереве (`S-03`) — `npm audit fix --force` запрещён.

---

## 12. Сильные стороны — не ломать

- Контрактный слой `/api/v2`: envelope, коды ошибок, валидация всех параметров с отказом вместо тихого fallback.
- Безопасность Python-части: серверные сессии, Argon2id, CSP с per-request nonce, двойной CSRF, двухуровневая защита от подбора, идемпотентность (`action_idempotency`), audit trail с переходами состояния, AES-256-GCM.
- **Ноль** `TODO` / `FIXME` / `HACK` / `XXX` на 258 файлов кода.
- Все 6 гейтов сайта зелёные; адаптивность без overflow вплоть до 320 px; дизайн-система enforced скриптом.
- **Честность контента сайта** — все конкретные технические заявления проверены построчно и подтверждаются кодом, включая четыре добровольных раскрытия невыгодных ограничений. Это ключевой актив продукта.
- Комментарии в коде объясняют *почему*, с отвергнутыми альтернативами и описанием прошлых инцидентов.

---

## 13. Критические правила проекта (`docs/source/01 §14`)

1. Определяйте корень через `git rev-parse --show-toplevel`.
2. Никогда не переключайте `TINKOFF_SANDBOX=false` без явного согласования — реальные деньги.
3. Не запускайте Telegram-бота, если может работать другой экземпляр.
4. Не коммитьте `.env`, `credential_vault.json`, любые секреты.
5. Не выполняйте `migrate` без `--check` на боевой БД без бэкапа и согласования.
6. Не выполняйте `npm audit fix --force`.
7. Не ослабляйте честность контента сайта и не добавляйте цифры доходности.
8. Правьте `knowledge/rules/rules.yaml`, а не дубль `knowledge/rules.yaml`.
9. Не удаляйте документы — помечайте.
10. Проверяйте любое утверждение о продукте против кода перед публикацией на сайте.

---

## 14. Развёртывание

Целевая среда — Windows Server 2019, сервисы через NSSM: `QuantFlowBot` (`bot/main.py`), `QuantFlowDashboard` (`bot/ui/dashboard.py`), опционально сайт. Актуальная инструкция — `docs/WINDOWS_DEPLOYMENT.md` (файл в нижнем регистре `docs/windows-deployment.md` — устаревший дубль). Dashboard сейчас работает на Werkzeug dev-сервере — Launch Blocker `RM-P1-012`.
