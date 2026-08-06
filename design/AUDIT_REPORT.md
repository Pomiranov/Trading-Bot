# QuantFlow Dashboard — Аудит (2026-07-19)

## Шаг 1: Инвентаризация экранов

| Экран / раздел | Файл | Что показывает сейчас | Данные из таблицы | Статус |
|---|---|---|---|---|
| **Dashboard: Hero balance** | `ui/dashboard.py → /api/metrics` | portfolio_value = 1M + SUM(pnl), pnl_today, drawdown, sharpe | `trades` (legacy) | BROKEN — нули если таблица пуста |
| **Dashboard: Equity Curve** | `ui/dashboard.py → /api/equity` | Кривая капитала по дням | `trades` (legacy) → fallback: `candles SBER` | PHANTOM — fallback к цене SBER не является equity |
| **Dashboard: Signals table** | `ui/dashboard.py → /api/signals` | Последние 50 записей из trades как «сигналы» | `trades + trade_feedback` (LEGACY JOIN) | BROKEN — это торги, не сигналы |
| **Dashboard: Positions sidebar** | `ui/dashboard.py → /api/positions` | Открытые позиции из legacy trades | `trades WHERE closed_at IS NULL` | BROKEN — читает legacy, не `paper_positions` |
| **Dashboard: Log** | `ui/dashboard.py → /api/log` | Новости из таблицы news | `news` | WORKS (если есть данные) |
| **Dashboard: PnL Неделя / Месяц** | `dashboard.html` только HTML | Всегда «—» | нигде | PHANTOM — нет запроса, нет данных |
| **Dashboard: Risk Panel** | `platform_routes.py → /api/platform/risk/status` | Unrealized (Tinkoff API!), Просадка, Позиции, Win Rate | `risk_manager` in-memory + Tinkoff API | BROKEN — Unrealized всегда «—» без токена |
| **Dashboard: Brokers** | `platform_routes.py → /api/platform/brokers` | Tinkoff, Bybit, Finam статус | config только | WORKS (Finam hardcoded = «В разработке») |
| **Dashboard: System health** | `platform_routes.py → /api/platform/health` | DB, SSE, engine uptime | system singletons | WORKS |
| **Dashboard: Recent trades sidebar** | `platform_routes.py → /api/platform/overview` | 10 последних сделок | `trades` (legacy) → fallback `paper_trades` | BROKEN — legacy приоритет |
| **Dashboard: Paper Feed** | SSE `/api/platform/stream` | Real-time события из paper engine | SSE hub (in-memory) | WORKS (если engine запущен) |
| **Portfolio: Balance + charts** | `platform_routes.py → /api/platform/portfolio` | Баланс, позиции, allocation | `paper_accounts + paper_positions` | WORKS |
| **Portfolio: Equity chart** | `platform_routes.py → /api/platform/analytics` | Кривая equity | `equity_snapshots` | WORKS (если данные есть) |
| **Portfolio: Ops history** | `render.js → /api/platform/overview` | История операций | `trades` (legacy) fallback `paper_trades` | BROKEN — legacy приоритет |
| **Portfolio: Open positions table** | `platform_routes.py → /api/platform/portfolio/positions` | Открытые позиции | `paper_positions` | WORKS |
| **Signals: Live indicators grid** | `dashboard.py → /api/signals/live` | RSI, MACD, ADX, BB по тикерам | `candles` | WORKS |
| **Signals: Signals table** | `platform_routes.py → /api/platform/signals` | Сигналы из `trading_signals` | `trading_signals` | WORKS |
| **Backtest: Run + history** | `platform_routes.py → /api/platform/backtest/run` | Запуск бэктеста, equity, drawdown | `candles + backtest_runs` | WORKS |
| **Analytics: Stats grid** | `platform_routes.py → /api/platform/analytics` | 8 метрик + charts + таблица | `paper_trades + equity_snapshots` | WORKS (нули если нет paper_trades) |
| **Analytics: Engine status** | `platform_routes.py → /api/platform/engine/status` | running/stopped, сигнализирует «Stopped» | paper_engine in-memory | WORKS (defaults to Stopped) |
| **Settings: Config + tokens** | `dashboard.py → /api/settings` | DB host, risk params, Tinkoff config | config | WORKS |
| **Miniapp: Quant Hunter** | `miniapp.js + game.js` | Игра + live trade data | SSE + paper data | WORKS |
| **Learning: Belief System** | — | **НЕТ UI** | `belief_system` | MISSING |
| **Learning: Hypotheses pipeline** | — | **НЕТ UI** | `hypotheses` | MISSING |
| **Learning: Skipped signals** | — | **НЕТ UI** | `skipped_signals` | MISSING |
| **Learning: Forward state** | — | **НЕТ UI** | `forward_state` | MISSING |

---

## Шаг 2: Gap Analysis

### 2.1 Экраны, читающие ЛЕГАСИ таблицы → нужна переработка

**Легаси схема (schema.py / feedback.py):**
```sql
trades: id, ticker, direction, entry_price, quantity, stop_loss, take_profit, 
        pnl, opened_at, closed_at
-- + migration columns: pnl_pct, signal_rules, buy_score, sell_score, 
--                       rsi, macd_hist, adx, atr, status, reason_open
```

**Новая схема (quantflow_schema.sql):**
```sql
trades: + strategy_id, market_regime, market_features JSONB, 
          pnl_r, decision_quality, market, exit_reason
```

**Экраны на переработку:**

| Эндпоинт | Проблема | Что читать вместо |
|---|---|---|
| `/api/metrics` | Считает portfolio = 1M + SUM(legacy pnl) | `paper_accounts.balance` |
| `/api/equity` | equity = кривая legacy trades, fallback = цена SBER | `equity_snapshots` |
| `/api/signals` | JOIN trades + trade_feedback = «сигналы» | `trading_signals` |
| `/api/positions` | `trades WHERE closed_at IS NULL` | `paper_positions` |
| `/api/platform/overview` → recent_trades | `SELECT FROM trades` приоритет | `paper_trades` приоритет |

### 2.2 Метрики показывающиеся как пустые / нулевые

| Элемент | ID в DOM | Причина | Решение |
|---|---|---|---|
| PnL Неделя | `#dashPnlWeek` | Нет API-вызова вообще | Добавить `/api/platform/analytics/summary` с week/month breakdown |
| PnL Месяц | `#dashPnlMonth` | Нет API-вызова вообще | То же |
| Sharpe Ratio | `#metSharpe` | Из legacy trades, 0 если таблица пуста | Читать из `paper_accounts → equity_snapshots` |
| Analytics Engine Status | `#engineStatusText` | Defaults to «Stopped» — engine не запускается авто | Добавить auto-start или четкий UI «Запустить» |
| Profit Factor | `#anProfitFactor` | 0 если нет `paper_trades` | Работает, просто нужны данные |
| Sortino Ratio | `#anSortino` | 0 если < 2 точек equity | Нужны `equity_snapshots` |
| Win Rate / Sharpe card | `#metDrawdown` | Карточка называется «Win Rate / Sharpe», но показывает drawdown | Переименовать или разделить |

### 2.3 Данные новой схемы, не визуализированные в Dashboard

| Таблица / Поле | Описание | Где должно быть |
|---|---|---|
| `belief_system.confidence` | Доверие к стратегии (0-1) | Новый экран «Learning» + badge на каждой стратегии |
| `belief_system.best_regime` | Лучший рыночный режим | Новый экран «Learning» |
| `belief_system.profit_factor` | PF по стратегии | Новый экран «Learning» |
| `belief_system.max_consecutive_losses` | Макс серия убытков | Новый экран «Learning» |
| `hypotheses.stage` | observation/candidate/active/rejected | Новый экран «Hypotheses pipeline» |
| `hypotheses.confidence` | Confidence гипотезы | Там же |
| `hypotheses.stat_test_result` | Результаты статтестов | Там же (detail panel) |
| `skipped_signals.skip_reason` | Почему сигнал пропущен | Analytics sidebar |
| `trades.market_features` JSONB | volume_ratio, rsi_zone, etc | Signal card detail |
| `trades.decision_quality` | Качество решения (0-1) | Per-trade history |
| `trades.pnl_r` | R-multiple | Analytics (ключевая метрика) |
| `trades.market_regime` | trending/ranging/volatile | Performance by regime |
| `forward_state` | Последний обработанный candle | System status |

### 2.4 Компоненты со стилистическими проблемами

1. **Dashboard Hero** — показывает `portfolio_value = 1M + legacy PnL`, а Portfolio показывает `paper_accounts.balance`. **Два разных числа** для одного понятия «баланс».

2. **"Лог" секция** — подаёт новости (news table, sentiment-based) как системный лог. Семантически неверно.

3. **Risk Panel: Unrealized** — тянется из Tinkoff API. Без токена = «—». Нужно заменить на `paper_positions.unrealized_pnl`.

4. **Analytics Status Bar** — `Источник данных: MOEX · DB` hardcoded. Не отражает реальный источник.

5. **"Win Rate / Sharpe" card** — заголовок карточки вводит в заблуждение (показывает Drawdown в `#metDrawdown` и WinRate в `#metWinRate`).

6. **Backtest: стратегии** — только `rules_engine` в dropdown. Нет интеграции с `belief_system.strategy_id`.

7. **Signals filter: биржи** — Finam в фильтре, но брокер hardcoded как «В разработке».

8. **Топбар: две status-pill** — SSE и API отдельно, но SSE status («connecting») остаётся серым при первой загрузке.

---

## Шаг 3: Приоритизация экранов

### P0 — без этого нельзя запускать paper trading для реальных пользователей

| # | Экран | Проблема | Почему P0 |
|---|---|---|---|
| 1 | **Dashboard (переработка)** | Legacy data, phantom metrics, conflicting balance | Главный экран — если показывает ерунду, весь продукт выглядит сломанным |
| 2 | **Analytics (доработка)** | Sharpe=0, Sortino=0 при отсутствии equity_snapshots, нет PnL Week/Month | Без analytics нельзя понять работает ли стратегия |
| 3 | **Signals Center (доработка)** | Confidence % из `trading_signals.probability_pct` — нужно связать с `belief_system.confidence` | Без достоверных сигналов нельзя открывать позиции |

### P1 — без этого нельзя запускать монетизацию (2000 RUB/мес)

| # | Экран | Статус | Почему P1 |
|---|---|---|---|
| 4 | **Portfolio (доработка)** | WORKS but needs polish | Пользователь должен видеть свои деньги красиво |
| 5 | **Learning: Belief System** | MISSING | Уникальное преимущество QuantFlow vs обычного бота |
| 6 | **Learning: Hypotheses Pipeline** | MISSING | Proof-of-learning для премиальных пользователей |

### P2 — nice-to-have для v2

| # | Экран |
|---|---|
| 7 | Backtest (более детальный — добавить R-multiple, regime breakdown) |
| 8 | Settings (подключение стратегий к belief_system) |
| 9 | Quant Hunter miniapp |

---

## Шаг 6: Schema Additions (ROADMAP)

Следующие поля нужно добавить в `schema.py` (idempotent migrations), чтобы dashboard мог их читать:

```sql
-- В таблицу trades (уже есть в quantflow_schema.sql, нет в schema.py):
ALTER TABLE trades ADD COLUMN IF NOT EXISTS strategy_id         VARCHAR(50);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_regime       VARCHAR(20);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_features     JSONB;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pnl_r               NUMERIC(10,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS decision_quality    NUMERIC(5,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_reason         VARCHAR(20);

-- API эндпоинты для MISSING данных:
-- GET /api/platform/learning/belief  → SELECT FROM belief_system
-- GET /api/platform/learning/hypotheses → SELECT FROM hypotheses WHERE stage != 'rejected'
-- GET /api/platform/learning/skipped  → SELECT skip_reason, COUNT(*) FROM skipped_signals GROUP BY skip_reason
-- GET /api/platform/analytics/pnl-periods → weekly/monthly PnL из paper_trades
```
