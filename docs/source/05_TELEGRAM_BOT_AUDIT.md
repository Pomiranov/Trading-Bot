# 05 — Telegram Bot Audit

| Field | Value |
|---|---|
| **Дата аудита** | 2026-08-05 |
| **Путь к проекту** | `/Users/danila/Downloads/Trading-Bot-merge-learning-nik` |
| **Ветка** | `quant-site-approved-reference-redesign` |
| **Commit HEAD** | `a54a100b4d542f1d866b5f89336ce0703fea6ced` |
| **Статус документа** | ACTIVE — Source of Truth по Telegram-боту |
| **Область аудита** | `bot/tg/` (активный бот), `bot/ui/telegram_bot.py` (legacy), `bot/ui/static/miniapp/` (Mini App) |
| **Framework** | **python-telegram-bot 22.8** (установленная версия проверена; `aiogram` **не установлен**) |
| **Связанные документы** | [02](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md) · [04](04_DASHBOARD_AUDIT.md) · [06](06_BACKEND_DATA_AND_INTEGRATIONS_AUDIT.md) · [07](07_SECURITY_PRIVACY_AND_COMPLIANCE_AUDIT.md) · [11](11_MASTER_ROADMAP.md) |

### Что удалось проверить
- Полный код обоих Telegram-приложений (4 792 + 1 036 строк) и Mini App (JS + HTML).
- Установленную версию библиотеки: `python-telegram-bot 22.8`; `import aiogram` → `ModuleNotFoundError`.
- Регистрацию всех команд, callback-хендлеров, conversations и middlewares чтением `bot/tg/bot.py`.
- Фактическое принуждение аутентификации на всех API-маршрутах, которые использует Mini App (HTTP-пробы → 401).
- Механизм аутентификации Mini App по коду (клиент + сервер) и его несостыковку.

### Что проверить не удалось
- **Живой запуск бота.** Требует `TELEGRAM_TOKEN` и `run_polling`; запуск занял бы polling-сессию токена пользователя и мог бы конфликтовать с работающим экземпляром (обработчик `Conflict` в коде подтверждает, что это реальный сценарий). **Все утверждения о рантайме — INFERRED из кода.**
- Фактическую отправку сообщений и исполнение сделок через бота.
- Mini App внутри Telegram — требует публичный HTTPS-домен (о чём прямо сказано в `bot/ui/static/miniapp/BOTFATHER.md`).

---

## Executive Summary

Активный бот `bot/tg/` — **качественная, безопасная и функционально богатая реализация**: 12 команд, ~60 callback-хендлеров, 3 FSM-conversation, fail-closed авторизация по whitelist, rate-limiting, применённый в 15 хендлерах, и — что важнее всего — **защита от подмены callback-данных в подтверждении сделки**.

Но вокруг него три серьёзные проблемы:

1. **Ключевая продуктовая возможность заперта в legacy-модуле.** Кнопки `[✅ Подтвердить сделку]` / `[❌ Отклонить]` на **каждую автоматическую** сделку реализованы только в `bot/ui/telegram_bot.py`, который активный бот не использует. Пользователь получает уведомление о совершённой сделке, а не запрос на её одобрение ([T-01]).
2. **Путь исполнения сделки через Telegram не идемпотентен**, в отличие от Dashboard, где та же операция защищена `@mutating(idempotent=True)` с audit trail ([T-02]).
3. **Mini App не может аутентифицироваться внутри Telegram.** Клиент отправляет API-ключ из `sessionStorage`, но серверный валидатор (`bot/security/dashboard_auth.py`) **не подключён ни к одному обработчику** — доступ определяется исключительно сессионной cookie, которой в Telegram WebView нет ([T-03]).

**Однопользовательская природа подтверждена и здесь:** авторизация — статический whitelist `chat_id` из `.env`. Привязки Telegram-аккаунта к клиентскому аккаунту не существует, потому что не существует клиентских аккаунтов ([A-01](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md#a-01)).

---

## 1. Фактическая архитектура бота (VERIFIED)

**Framework:** python-telegram-bot 22.8. Импорты: `from telegram` (25), `from telegram.ext` (23), `from telegram.error` (2). **Ни одного импорта `aiogram`.**

> **Противоречие с документацией:** `CLAUDE.md` описывает `bot/tg/` как «Telegram bot (handlers, FSM, menus, middlewares, notifications)» — терминология aiogram. Фактически используется PTB: «FSM» реализован через `ConversationHandler`, «middlewares» — через `BaseHandler` в группе `-1`. Понятийно близко, но библиотека другая. Также `CLAUDE.md` называет переменную `BOT_TOKEN`, тогда как код читает `TELEGRAM_TOKEN` (`bot/config.py:37`). См. [X-02](13_STALE_DOCUMENTS_REGISTER.md).

**Точка входа:** `bot/tg/bot.py` → `run_bot()` (блокирующий, `run_polling(drop_pending_updates=True, stop_signals=[])`).

**Запуск:** из `bot/main.py:388` в отдельном daemon-потоке параллельно торговому циклу, либо `python3 bot/main.py --bot-only`.

**Порядок регистрации (важен и сделан правильно):**
1. `app.add_error_handler(handle_error)` — глобальный обработчик.
2. `app.add_handler(AuthMiddleware(), group=-1)` — **auth-гейт до всех хендлеров**.
3. FSM-conversations (`build_trade_conversation`, `build_signal_conversation`, `build_settings_conversation`) — **до** catch-all хендлеров, иначе они бы перехватывали ввод.
4. Команды, затем callback-хендлеры.

**DB-подключение:** `bot/tg/bot.py:96-112` создаёт SQLAlchemy engine (`pool_size=2, max_overflow=3, pool_pre_ping=True`), проверяет `SELECT 1` и кладёт в `app.bot_data["db_engine"]`. При недоступности БД — `logger.warning` и `None`, статистика отключается, бот продолжает работать. Корректная деградация.

## 2. Команды и меню (VERIFIED)

**12 команд:** `/start`, `/dashboard`, `/portfolio`, `/positions`, `/orders`, `/operations`, `/balance`, `/stats`, `/signal`, `/status`, `/help`, `/game`, `/paper`, `/learning`.

**Меню (callback-хендлеры), по разделам:**

| Раздел | Callbacks |
|---|---|
| Навигация | `m_main`, `m_dashboard`, `dash_refresh` |
| Портфель | `m_portfolio`, `port_refresh` |
| Позиции | `m_positions`, `pos_pg_<n>`, `pos_refresh`, `pos_detail_*` |
| Заявки | `m_orders`, `ord_filter_*`, `ord_refresh`, `ord_cancel_*` |
| Операции | `m_operations`, `ops_pg_<n>`, `ops_refresh` |
| Баланс | `m_balance`, `bal_refresh` |
| Статистика | `m_statistics`, `stat_refresh` |
| Аналитика | `m_analytics`, `analytics_paper`, `analytics_broker`, `analytics_strategy`, `analytics_drawdown` |
| Торговля | `m_trading`, `trade_(buy|sell)_*`, `trade_confirm_*` |
| Управление ботом | `m_trading_bot`, `bot_start`, `bot_pause`, `bot_resume`, `bot_stop`, `bot_status`, `bot_logs` |
| Сигналы | `m_signals`, `sig_refresh`, `sig_filter_*`, `sig_generate`, `sig_exec_<id>` |
| Уведомления | `m_notifications`, `notif_toggle_*` |
| Настройки | `m_settings`, `set_brokers`, `set_broker_tinkoff`, `set_broker_finam` |
| Счёт | `m_account`, `acc_accounts` |
| Paper trading | `m_paper`, `paper_toggle`, `paper_stats`, `paper_positions`, `paper_trades`, `paper_risk` |
| Обучение | `m_learning`, `learn_strategies`, `learn_hypotheses`, `learn_decisions` |
| Прочее | `m_help`, `m_game` |

**Заглушки «Раздел в разработке»** (`bot/tg/bot.py`, `_cb_coming_soon` с `show_alert=True`): `set_tokens`, `set_timezone`, `set_currency`, `set_risk`, `set_interval`, `set_security`, `sig_filter_active`. То есть **шесть из подразделов настроек не реализованы**, включая `set_risk` (лимиты риска) и `set_security` — см. [T-05].

**No-op хендлеры** (просто `answer()`): `pos_noop`, `ops_noop`, `pos_hist_*` — метки пагинации и нереализованная история.

## 3. Реальный поток: Telegram user → … → Dashboard (VERIFIED / INFERRED)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ПУТЬ A — Ручная заявка (РАБОТАЕТ, с подтверждением)          VERIFIED   │
└─────────────────────────────────────────────────────────────────────────┘
Telegram user
  │ tap [🟢 Купить]  → callback trade_buy_tinkoff
  ▼
AuthMiddleware (group -1) ── chat_id ∉ whitelist ──► «⛔ Доступ запрещён» STOP
  │ authorized
  ▼
cb_trade_start ── rate_limiter.is_allowed() ── превышено ──► «⏳ Подождите» STOP
  │
  ▼ FSM: TradeStates.ENTER_TICKER
trade_enter_ticker ── валидация (isalpha, ≤12) ── resolve_instrument(broker) ──► не найден: повтор
  │
  ▼ FSM: TradeStates.ENTER_QUANTITY
trade_enter_quantity ── валидация (int > 0)
  │
  ▼ Экран подтверждения: тикер, имя, лоты, штуки, «Рыночная заявка»
  ▼ FSM: TradeStates.CONFIRM_ORDER
trade_confirm
  │  ✅ ПРОВЕРКА ПОДМЕНЫ: figi / quantity / broker_id / direction из callback_data
  │     сверяются с context.user_data. Несовпадение → лог «tamper attempt» + отказ
  ▼
services.trading_service.execute_trade(TradeRequest)
  ▼
gateway.trade_gateway.execute()  ── risk-проверки
  ▼
broker_registry.get("tinkoff") → TinkoffBrokerAdapter.place_market_order()
  ▼
✅ «Заявка размещена» + order_id  /  ❌ текст ошибки
  ✗ БЕЗ идемпотентности, ✗ БЕЗ записи в audit_events        ← [T-02]

┌─────────────────────────────────────────────────────────────────────────┐
│ ПУТЬ B — Автономный цикл (РАБОТАЕТ, БЕЗ подтверждения)       VERIFIED   │
└─────────────────────────────────────────────────────────────────────────┘
bot/main.py trading_loop (каждые POLL_INTERVAL, окно 7–16 локального времени)
  ▼ loader.get_candles → indicator_engine → rules_engine.evaluate
  ▼ orchestrator.check_signal()   ← АЛГОРИТМИЧЕСКАЯ проверка (confidence ≥ 0.20)
  ▼ risk_manager.calculate_position / check_trade_allowed
  ▼ tinkoff_client.place_market_order()      ← НИКАКОГО участия человека
  ▼ notify_trade_open(...)                   ← Telegram получает УВЕДОМЛЕНИЕ,
                                                а не запрос на подтверждение
  ▼ + зеркалирование в paper_* и trading_signals
  ✗ БЕЗ подтверждения, ✗ БЕЗ идемпотентности, ✗ БЕЗ audit_events   ← [T-01], [A-02]

┌─────────────────────────────────────────────────────────────────────────┐
│ ПУТЬ C — Подтверждение автоматической сделки (СУЩЕСТВУЕТ, НЕ ПОДКЛЮЧЕН) │
└─────────────────────────────────────────────────────────────────────────┘
bot/ui/telegram_bot.py:
  _pending_trades[trade_id] = {...}                              (строка 202)
  InlineKeyboard [✅ Подтвердить сделку] callback confirm_trade:<id>  (216-221)
                 [❌ Отклонить]          callback reject_trade:<id>
  cb_confirm_trade / cb_reject_trade                              (605 / 711)
  Прунинг просроченных заявок > 2 ч                               (750-757)
  Регистрация хендлеров                                           (984-985)
  ▲
  └── main.py импортирует tg.bot, НЕ ui.telegram_bot → НЕДОСТУПНО   ← [T-01]

┌─────────────────────────────────────────────────────────────────────────┐
│ ПУТЬ D — Mini App (СТАТИКА ГРУЗИТСЯ, ДАННЫЕ 401 внутри Telegram) INFER. │
└─────────────────────────────────────────────────────────────────────────┘
Telegram WebView → GET /miniapp  (публичный префикс — отдаётся)
  ▼ index.html → telegram-web-app.js + legacy-format/legacy-api/game/miniapp.js
  ▼ miniapp.js: QFApi.paperAccount(), QFApi.positions(), QFApi.overview(),
    QFApi.signals(), fetch('/api/platform/analytics/summary'),
    new EventSource('/api/platform/stream')
  ▼ legacy-api.js отправляет заголовок с sessionStorage['dashboard_api_key']
  ▼ СЕРВЕР: _register_access_control проверяет ТОЛЬКО current_principal()
    (сессионная cookie). API-ключ не рассматривается.
  ▼ ❌ 401 UNAUTHENTICATED на каждый вызов данных              ← [T-03]
```

## 4. Findings

<a id="t-01"></a>
### [T-01] Подтверждение/отклонение автоматической сделки реализовано, но недоступно пользователю

**Статус:** VERIFIED
**Критичность:** Critical
**Приоритет:** P0
**Компонент:** `bot/ui/telegram_bot.py`, `bot/tg/`, `bot/main.py`
**Доказательство:**
- Legacy-модуль содержит полный контур: `_pending_trades` (`:43`), постановка заявки в ожидание (`:202`, `:379`, `:801`), клавиатура `[✅ Подтвердить сделку]`/`[❌ Отклонить]` (`:216-221`, `:392-397`, `:814-819`), обработчики `cb_confirm_trade` (`:605`) и `cb_reject_trade` (`:711`), прунинг заявок старше 2 ч (`:750-757`), регистрация (`:984-985`). Docstring на `:6` прямо описывает: «Кнопки: [✅ Подтвердить сделку] [❌ Отклонить] после каждого BUY/SELL».
- `bot/main.py:30` импортирует `from tg.bot import run_bot, send_notification` — **активный бот**. Единственная ссылка на legacy — `bot/run_forward_d1.py:431`, и только для `send_notification`.
- В активном боте `grep` по `confirm_trade|reject_trade|_pending_trades` даёт **0** совпадений. Есть только `trade_confirm_*` — подтверждение **своей** заявки в FSM, и `sig_exec_<id>` — исполнение сигнала.
- Автономный цикл вызывает `notify_trade_open()` (`bot/main.py:240`) — уведомление **после** исполнения.
**Файлы и маршруты:** `bot/ui/telegram_bot.py:43,202,216,605,711,984`, `bot/main.py:30,188,240`
**Текущее поведение:** Автоматическая сделка исполняется, затем приходит уведомление «сделка открыта». Одобрить или отклонить её нельзя.
**Ожидаемое поведение (по заявлениям сайта):** «Каждую сделку можно подтверждать вручную» (`audience.card1Body`), «последнее слово остаётся за вами» (`hero.subline`).
**Влияние на пользователя:** Обещанный контроль над автоматическими сделками отсутствует. На реальных деньгах — существенный риск.
**Влияние на бизнес:** Расхождение публичного обещания с поведением продукта на финансовом сервисе. Блокер запуска.
**Техническое влияние:** Код существует и работоспособен — нужен перенос, а не разработка с нуля.
**Корневая причина:** Незавершённая миграция с `bot/ui/telegram_bot.py` на `bot/tg/`.
**Рекомендация:** Перенести контур `_pending_trades` в `bot/tg/` вместе с введением `EXECUTION_MODE` ([A-02]). Хранить ожидающие заявки **в БД, а не в памяти процесса** — иначе перезапуск теряет их (в legacy это словарь в памяти). Прунинг по TTL сохранить.
**Зависимости:** [A-02], [A-05], [T-02]
**Оценка объёма:** L
**Критерии приёмки:** При `EXECUTION_MODE=confirm` автономный цикл не отправляет заявку до callback-подтверждения; ожидающие заявки переживают перезапуск; отказ и таймаут пишутся в `audit_events`.
**Roadmap ID:** RM-P0-002

---

<a id="t-02"></a>
### [T-02] Исполнение сделки через Telegram не идемпотентно и не попадает в audit trail

**Статус:** VERIFIED
**Критичность:** High
**Приоритет:** P0
**Компонент:** `bot/tg/handlers/trading.py`, `bot/tg/handlers/signals.py`, `bot/services/trading_service.py`
**Доказательство:**
- `trade_confirm` (`bot/tg/handlers/trading.py:213`) вызывает `execute_trade(req)` напрямую. `services/trading_service.execute_trade` (весь файл прочитан) → `trade_gateway.execute(...)`. Ни ключа идемпотентности, ни записи в `audit_events` на этом пути нет.
- Для сравнения, та же операция в Dashboard: `@mutating(action="signal.execute", idempotent=True)` (`bot/ui/api/v2/routes_actions.py:514`) и `@mutating(action="position.close", idempotent=True, require_reason=True)` (`:447`). Таблица `action_idempotency` (`schema.py:499`) и `audit_events` (`:512`) существуют и используются — но только из v2.
- `grep -rn "idempotency" bot/tg/` → **0 совпадений**.
**Файлы и маршруты:** `bot/tg/handlers/trading.py:213`, `bot/tg/handlers/signals.py` (`cb_signal_execute`), `bot/services/trading_service.py:41`
**Текущее поведение:** Двойное нажатие `[Подтвердить]` в условиях гонки может привести к двум заявкам. Частичную защиту даёт `ConversationHandler` (после первого подтверждения состояние — `END`, и повторный callback не совпадёт с состоянием) и удаление клавиатуры при `edit_message_text`, но это следствие механики UI, а не гарантия. Сделка, совершённая через Telegram, не имеет записи в `audit_events`.
**Ожидаемое поведение:** Одна логическая операция — один результат независимо от числа доставок callback. Каждая сделка — в audit trail, независимо от интерфейса.
**Влияние на пользователя:** Риск дублирующей заявки на реальные деньги. Отсутствие записи в журнале означает, что оператор не увидит в Dashboard, что сделка сделана из Telegram.
**Влияние на бизнес:** Для финансового продукта неполный audit trail — существенный пробел (и вероятное требование при любой сертификации/проверке — вопрос к профильному специалисту).
**Техническое влияние:** Механизм готов (`security/guards.py`, `action_idempotency`); он привязан к Flask-запросу и требует вынесения в интерфейс-независимый слой.
**Корневая причина:** Защитный контур строился под HTTP-роуты; Telegram-путь появился раньше и не был к нему приведён.
**Рекомендация:** Вынести идемпотентность и аудит из HTTP-декоратора в `gateway/trade_gateway`, чтобы **все три** пути исполнения (цикл, Telegram, Dashboard) проходили через одну точку. Ключ идемпотентности для Telegram — `callback_query.id` (уникален и стабилен при повторной доставке).
**Зависимости:** [A-02], [T-01]
**Оценка объёма:** M
**Критерии приёмки:** Повторная доставка одного и того же `callback_query.id` не создаёт второй заявки (тест); сделка из Telegram видна в `GET /api/v2/audit`.
**Roadmap ID:** RM-P0-008

---

<a id="t-03"></a>
### [T-03] Mini App не может аутентифицироваться: серверный валидатор API-ключа не подключён

**Статус:** INFERRED (сильный вывод; см. границы ниже)
**Критичность:** High
**Приоритет:** P1
**Компонент:** `bot/ui/static/miniapp/`, `bot/security/dashboard_auth.py`, `bot/ui/app_factory.py`
**Доказательство:**
- Клиент отправляет API-ключ: `bot/ui/static/miniapp/legacy-api.js:9` — `const key = sessionStorage.getItem('dashboard_api_key')`, добавляется в заголовки (`:7-11`), используется во всех запросах (`:15,25,44,75,81,91`).
- Серверный валидатор существует: `bot/security/dashboard_auth.py:34` — `_api_key_valid()`, сверяет с `config.dashboard.api_key`; `:68` учитывает `require_api_key_for_reads`.
- **Валидатор не подключён:** `grep -rn "dashboard_auth" bot/ --include=*.py` (исключая сам файл) → **0 совпадений**. Модуль — мёртвый код.
- Фактический контроль доступа (`bot/ui/app_factory.py:_register_access_control`) проверяет **только** `current_principal()`; публичны лишь `/health`, `/login`, `/api/v2/auth/session`, `/api/v2/auth/login`, `/api/internal/push` и префиксы `/static/`, `/miniapp`.
- `current_principal()` (`security/session_auth.py:290`) читает `g.qf_principal`, который заполняет `attach_principal()` (`:298-314`) **исключительно** из сессионной cookie (`request.cookies.get(SESSION_COOKIE)`). Ветки для API-ключа нет.
- Mini App действительно нуждается в данных: `miniapp.js:66,70,100,102,103,160` — `QFApi.paperAccount()`, `QFApi.positions()`, `QFApi.overview()`, `QFApi.signals()`, `fetch('/api/platform/analytics/summary')`, `new EventSource('/api/platform/stream')`.
- Все эти маршруты **проверены пробами: 401 без сессии** (`/api/platform/overview`, `/signals`, `/stream`).
**Файлы и маршруты:** `GET /miniapp` (публичен), `/api/platform/*` и `/api/*` (401)
**Текущее поведение:**
- В **браузере**, где у оператора уже есть активная сессионная cookie Dashboard, вызовы проходят (`SameSite=Strict` разрешает same-site) — Mini App работает. Это согласуется с `BOTFATHER.md`: «Локально Mini App работает в браузере».
- Внутри **Telegram WebView** сессионной cookie нет, а API-ключ игнорируется → каждый вызов данных возвращает 401. Интерфейс загрузится (статика публична), данные — нет.
**Ожидаемое поведение:** Mini App аутентифицируется способом, работающим в WebView: валидация `initData` (HMAC-SHA256 на `WebAppData` + токен бота) с выдачей серверной сессии.
**Влияние на пользователя:** Mini App внутри Telegram показывает пустой/ошибочный интерфейс.
**Влияние на бизнес:** Сайт заявляет Telegram как полноценный второй интерфейс («не витрина уведомлений и не упрощённая копия: второй интерфейс к тому же состоянию», `telegram.lead`). Mini App этого не обеспечивает.
**Техническое влияние:** Мёртвый auth-модуль создаёт ложное впечатление, что механизм есть.
**Корневая причина:** Переход на серверные сессии (`session_auth`) не сопровождался переводом Mini App; `dashboard_auth` остался неподключённым.
**Дополнительно (безопасность):** `initData` **нигде не валидируется на сервере**. Клиент читает `tg.initDataUnsafe?.user` (`miniapp.js:18`, `game.js:780`) — по имени поля это заведомо непроверенные данные. Если в будущем Mini App начнёт определять личность по `initDataUnsafe`, это станет полноценной уязвимостью подмены. Сейчас — не уязвимость, потому что данные всё равно недоступны без сессии.
**Границы вывода:** Статус INFERRED, а не VERIFIED, потому что Mini App не запускался внутри Telegram (нужен публичный HTTPS-домен). Вывод построен на четырёх проверенных фактах: клиент шлёт ключ → валидатор ключа не подключён → доступ определяется только cookie → эти маршруты дают 401 без cookie.
**Рекомендация:** Реализовать проверку `initData` по документированному алгоритму Telegram и выдавать по ней короткоживущую серверную сессию. Затем **удалить** `bot/security/dashboard_auth.py`, чтобы не осталось второго, неработающего механизма. Не восстанавливать схему с общим API-ключом в `sessionStorage` — общий секрет в клиентском хранилище хуже сессии.
**Зависимости:** [D-04](04_DASHBOARD_AUDIT.md) (SSE в v1), [A-06](02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md#a-06)
**Оценка объёма:** M
**Критерии приёмки:** Mini App внутри Telegram получает данные; подделанный `initData` отклоняется (тест); `dashboard_auth.py` удалён либо подключён — не оба состояния одновременно.
**Roadmap ID:** RM-P1-013

---

<a id="t-04"></a>
### [T-04] Авторизация — статический whitelist chat_id; привязки Telegram-аккаунта к клиенту не существует

**Статус:** VERIFIED
**Критичность:** High
**Приоритет:** P0 (как часть [A-01])
**Компонент:** `bot/tg/middlewares/auth.py`
**Доказательство:**
- `_allowed_ids()` (`:16-27`) собирает множество из `config.telegram.chat_id` и `config.telegram.allowed_chat_ids`, то есть из `TELEGRAM_CHAT_ID` и `TELEGRAM_ALLOWED_IDS` в `.env`.
- `is_authorized()` (`:38-53`) — **fail-closed**: при пустом whitelist логирует «Telegram auth misconfigured» и возвращает `False`. Это правильное поведение.
- Ни таблицы связи `telegram_user_id ↔ account`, ни процедуры привязки (`/link`, код подтверждения) не существует: `grep -rniE "link.*telegram|telegram.*link|bind.*account"` по `bot/` не даёт релевантных совпадений.
**Файлы и маршруты:** `bot/tg/middlewares/auth.py`, `bot/config.py:36-42`
**Текущее поведение:** Доступ к боту получают только ID, вписанные в `.env` вручную. Добавление пользователя = правка `.env` + перезапуск.
**Ожидаемое поведение (по сайту):** Клиент оформляет доступ и привязывает свой Telegram.
**Влияние на пользователя:** Самостоятельное подключение невозможно.
**Влияние на бизнес:** Онбординг не масштабируется. Проявление [A-01].
**Техническое влияние:** Механизм авторизации сам по себе корректен и безопасен — отсутствует слой выше.
**Корневая причина:** Однопользовательская архитектура.
**Рекомендация:** Не менять до решения [OQ-ARCH-01](14_OPEN_QUESTIONS_AND_DECISIONS.md). **Whitelist сохранить как второй контур даже после введения аккаунтов** — для закрытой beta это адекватная и дешёвая защита.
**Зависимости:** [A-01], [D-01]
**Оценка объёма:** L (в составе multi-tenancy)
**Критерии приёмки:** Определено в ADR по модели доступа.
**Roadmap ID:** RM-P0-001

---

<a id="t-05"></a>
### [T-05] Шесть подразделов настроек — заглушки «Раздел в разработке», включая риск и безопасность

**Статус:** VERIFIED
**Критичность:** Medium
**Приоритет:** P2
**Компонент:** `bot/tg/bot.py`, `bot/tg/handlers/settings.py`
**Доказательство:** `bot/tg/bot.py` регистрирует `_cb_coming_soon` (отвечает «Раздел в разработке», `show_alert=True`) для паттерна `^(set_tokens|set_timezone|set_currency|set_risk|set_interval|set_security|sig_filter_active)$`. Реализованы только `set_brokers`, `set_broker_tinkoff`, `set_broker_finam`.
**Файлы и маршруты:** меню `⚙ Настройки`
**Текущее поведение:** Пользователь видит пункты меню, которые открывают алерт «в разработке». Среди них `set_risk` (лимиты риска) и `set_security`.
**Ожидаемое поведение:** Либо реализация, либо отсутствие пункта в меню. Показывать нереализованный пункт «Риск» в торговом боте особенно неудачно — риск-лимиты воспринимаются как настраиваемые, хотя задаются только через `.env` (`RISK_MAX_POSITION_PCT`, `RISK_MAX_DAILY_LOSS_PCT`, `RISK_MAX_OPEN_POSITIONS`, `RISK_ATR_STOP_MULT`).
**Влияние на пользователя:** Ощущение недоделанности; ложное ожидание, что лимитами можно управлять из бота.
**Влияние на бизнес:** Сайт заявляет «Вы задаёте пределы» (`faq.a4`) — в интерфейсе этого сделать нельзя.
**Техническое влияние:** —
**Корневая причина:** Меню спроектировано шире реализации.
**Рекомендация:** Скрыть нереализованные пункты до готовности (дешевле и честнее), либо реализовать `set_risk` как приоритетный — он подкрепляет заявление сайта.
**Зависимости:** —
**Оценка объёма:** S (скрыть) / M (реализовать `set_risk`)
**Критерии приёмки:** В меню нет пунктов, отвечающих «в разработке».
**Roadmap ID:** RM-P2-016

---

<a id="t-06"></a>
### [T-06] Сильные стороны бота (сохранить)

**Статус:** VERIFIED — положительное наблюдение

1. **Fail-closed авторизация в группе `-1`** — гейт срабатывает раньше любого хендлера; при пустом whitelist доступ закрыт, а не открыт (`auth.py:44-49`).
2. **Защита от подмены callback-данных в подтверждении сделки** (`handlers/trading.py:170-196`) — это лучшая отдельная деталь во всём боте. `figi`, `quantity`, `broker_id`, `direction` из `callback_data` сверяются с `context.user_data`; при несовпадении — `logger.warning("Trade confirm tamper attempt: user=%s …")`, отказ и очистка состояния. Учтено, что `callback_data` приходит от клиента и доверять ему нельзя.
3. **Двухшаговое подтверждение ручной заявки** с полным экраном параметров (тикер, имя инструмента, лоты, штуки, тип заявки) и предупреждением «Заявка будет исполнена по рыночной цене».
4. **Rate limiting реально применён**, а не только объявлен: `rate_limiter.is_allowed()` вызывается в 15 хендлерах (`orders`, `signals`, `operations`, `statistics`, `positions`, `trading`, `balance`, `paper_trading`, `dashboard`, `start`×2, `learning`, `analytics`, `portfolio`, `trading_bot`). Token bucket 30 вызовов / 60 с на пользователя (`middlewares/rate_limit.py`).
5. **Грамотный глобальный обработчик ошибок** (`middlewares/error_handler.py`): `Conflict` (409, другой экземпляр держит polling) логируется один раз без спама; `NetworkError`/`TimedOut` — на уровне `debug` как ожидаемые; остальное — `logger.error` с трейсом. Пользователю выдаются **разные** сообщения по типу исключения (`BrokerNotConfigured` → с указанием пути в меню, `BrokerConnectionError`, `ValueError`), а не одна общая ошибка. Попытка отправить сообщение обёрнута в `try/except`, чтобы сбой доставки не порождал второе исключение.
6. **Валидация пользовательского ввода:** тикер — `isalpha()` и ≤ 12 символов; количество — целое > 0; при ошибке FSM возвращает в то же состояние с подсказкой, а не обрывает диалог.
7. **Корректная деградация без БД** — статистика отключается, бот работает.
8. **`drop_pending_updates=True`** при старте — после простоя бот не отработает лавину устаревших команд. Для торгового бота это важный дефолт.
9. **Диспетчер уведомлений** (`tg/notifications/dispatcher.py`, 385 строк) с типизированными событиями: `notify_trade_open`, `notify_trade_close`, `notify_api_error`, `notify_risk_limit`, `notify_bot_started`, `notify_bot_stopped`, плюс переключатели в меню (`notif_toggle_*`).

## 5. Остальные пункты требований аудита

| Требование | Состояние | Доказательство |
|---|---|---|
| Framework | python-telegram-bot 22.8 | Проверено импортом |
| Точка запуска | `tg.bot.run_bot()` из `main.py` (поток) или `--bot-only` | `bot/main.py:380-391` |
| Состояния и сценарии | 3 `ConversationHandler`: trade, signal, settings; `TradeStates` в `tg/fsm/states.py` | VERIFIED |
| Хранение состояния | `context.user_data` — **в памяти процесса**; при перезапуске FSM теряется. `PersistenceInput` не настроен | VERIFIED — риск для [T-01] |
| Работа с Dashboard | Общая БД; кнопка `m_dashboard` даёт ссылку (`config.dashboard.miniapp_url`) | VERIFIED |
| Работа с backend | Напрямую через Python-импорты (один процесс), не по HTTP | VERIFIED |
| Торговые сигналы | `sig_generate`, `sig_exec_<id>`, фильтры | VERIFIED |
| Автоматический режим | Только `bot_start`/`bot_pause`/`bot_resume`/`bot_stop`; **режимов исполнения нет** | VERIFIED — [A-02] |
| Очереди | Отсутствуют. Уведомления — fire-and-forget `await notify(...)` | VERIFIED |
| Retries | Есть `bot/reliability.py` (retry/circuit-breaker), но в `bot/tg/` не применяется | VERIFIED |
| Rate limits | Свои — token bucket; лимиты **Telegram API** (30 msg/s) не учитываются отдельно | VERIFIED |
| Безопасность токена | `TELEGRAM_TOKEN` из `.env`; `.env` в `.gitignore` (проверено `git check-ignore`); возможен vault | VERIFIED |
| Защита от повторных действий | Только на уровне FSM/UI; идемпотентности нет | VERIFIED — [T-02] |
| Идемпотентность | **Отсутствует** на пути Telegram | VERIFIED — [T-02] |
| Недоступность брокера | `BrokerNotConfigured` / `BrokerConnectionError` → понятные сообщения | VERIFIED |
| Недоступность backend | Backend в том же процессе; при падении БД — деградация статистики | VERIFIED |
| Пользовательские сообщения | Русский, HTML-разметка, эмодзи-статусы, дифференцированные ошибки | VERIFIED |
| Onboarding | `/start` + `/help`; обучающего сценария нет | VERIFIED |
| Локализация | **Только русский.** i18n-слоя в `bot/tg/` нет | VERIFIED — контраст с двуязычным сайтом |
| Поддержка | Канала поддержки в боте нет | VERIFIED |
| **Тесты** | **Ни одного теста на `bot/tg/`.** В `tests/` — только dashboard/platform/security | VERIFIED — [Q-05](08_QA_TESTING_PERFORMANCE_AND_RELIABILITY_AUDIT.md) |
| Production readiness | PARTIALLY IMPLEMENTED — см. [10](10_CURRENT_DEVELOPMENT_STATUS.md) |

---

## Top Critical Findings

1. **[T-01]** Подтверждение автоматических сделок реализовано в legacy-модуле и недоступно пользователю — при том что сайт это обещает.
2. **[T-02]** Путь исполнения через Telegram не идемпотентен и не пишет audit trail, в отличие от Dashboard.
3. **[T-03]** Mini App не аутентифицируется внутри Telegram: валидатор API-ключа — мёртвый код, `initData` не проверяется.
4. **[T-04]** Авторизация — статический whitelist; привязки Telegram к клиентскому аккаунту нет.
5. **[Q-05]** Нулевое тестовое покрытие Telegram-бота (4 792 строки).

## Quick Wins

| ID | Действие | Объём |
|---|---|---|
| [T-05] | Скрыть 6 пунктов настроек, отвечающих «в разработке» | S |
| [T-03] | Удалить мёртвый `bot/security/dashboard_auth.py` (после решения по Mini App) | XS |
| — | Применить `bot/reliability.py` (retry) к брокерским вызовам в хендлерах | S |
| — | Исправить `CLAUDE.md`: PTB вместо aiogram-терминологии, `TELEGRAM_TOKEN` вместо `BOT_TOKEN` | XS |

## Launch Blockers

- [T-01] Отсутствие подтверждения автоматических сделок при публичном обещании обратного.
- [T-02] Неполный audit trail на финансовых операциях.
- [T-04] / [A-01] Нет модели доступа для клиентов.

## Recommended Next Steps

1. Перенести контур подтверждения в `bot/tg/`, храня ожидающие заявки в БД (RM-P0-002).
2. Вынести идемпотентность и аудит в `trade_gateway`, чтобы покрыть все три пути исполнения (RM-P0-008).
3. Реализовать валидацию `initData` для Mini App и удалить мёртвый auth-модуль (RM-P1-013).
4. Завести тесты на `bot/tg/` — начать с `trade_confirm` (проверка подмены — самая ценная для регресса) (RM-P0-003).
5. Скрыть нереализованные пункты меню (RM-P2-016).

## Open Questions

См. [14](14_OPEN_QUESTIONS_AND_DECISIONS.md): OQ-TRADE-01 (режим исполнения по умолчанию), OQ-ARCH-01 (модель доступа), OQ-PROD-02 (нужен ли Mini App вообще, учитывая что бот покрывает те же сценарии), OQ-OPS-02 (как хранить ожидающие подтверждения заявки и что делать по истечении TTL).

## Уровень уверенности аудита

**Высокий** для состава бота, регистрации хендлеров, механизма авторизации, rate-limiting, обработки ошибок, защиты от подмены callback-данных и отсутствия идемпотентности — всё установлено чтением полного кода обоих приложений.
**Средний** для [T-03] (Mini App) — вывод построен на четырёх проверенных фактах, но без запуска внутри Telegram; помечен INFERRED.
**Низкий** для рантайм-поведения: фактическая доставка сообщений, поведение FSM при перезапуске, соблюдение лимитов Telegram API и работа под нагрузкой не проверялись — бот осознанно не запускался.
