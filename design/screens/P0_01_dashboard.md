# P0 · Screen 1: Dashboard (Main Overview)

> Приоритет: P0 — главный экран, первое что видит пользователь.  
> Стек: Flask + Jinja2 + Chart.js + ECharts + vanilla JS. Нет React.

---

## Stitch Prompt

```
[PASTE DESIGN SYSTEM PREFIX FROM design/DESIGN_SYSTEM.md HERE]

---

SCREEN: QuantFlow Dashboard — Main Overview

PURPOSE:
Real-time overview of the paper trading bot's performance. Shows current balance,
today's PnL, weekly/monthly PnL, open positions, live signals, equity curve, and
system health. All data comes from REST APIs polled every 30s + SSE for live trades.

DATA SOURCES (real, no phantoms):
- Balance + PnL metrics: GET /api/platform/portfolio → paper_accounts table
- Equity curve: GET /api/platform/analytics → equity_snapshots table
- Open positions: GET /api/platform/portfolio/positions → paper_positions table
- Signals feed: GET /api/platform/signals (last 10) → trading_signals table
- Paper trade feed: SSE /api/platform/stream → live events
- System health: GET /api/platform/health → DB, engine, SSE status
- Brokers: GET /api/platform/brokers → config status
- PnL week/month: GET /api/platform/analytics (daily_pnl grouped) → paper_trades

LAYOUT:
Full-height viewport. Left sidebar 240px (fixed). Right: topbar 52px + scrollable content.

TOPBAR (52px height, frosted glass rgba(8,9,13,0.85), blur 20px):
Left: hamburger (mobile only) | page title "Dashboard" | breadcrumb "Overview · Live"
Right: "Updated 14s ago" (muted xs) | HH:MM:SS clock (mono) | refresh button (icon) |
       SSE status pill (green dot "Live" / orange "Connecting") |
       Bot status pill (green "Running" / red "Stopped")

SECTION 1 — HERO METRICS ROW (5 cards in grid: 1.4fr 1fr 1fr 1fr 1fr 1fr)

Card 1 (hero, spans 2 rows, gradient bg):
  Top row: label "Общий баланс" (muted caps xs) | source badge "Paper" (blue)
  Value: "1 248 304 ₽" (JetBrains Mono 36px #eaecef)
  Sub: "+124 сделки · Win Rate 63.2%"
  Sparkline chart (36px tall orange area chart, last 30 equity points, no axes)
  States: loading=shimmer block 100px high, error="Нет данных"

Card 2: "PnL Сегодня"
  Value: "+4 832 ₽" (green if positive, red if negative, mono 20px)
  Sub: "+0.39%"

Card 3: "PnL Неделя"
  Value: "+18 240 ₽" (green)
  Sub: "7 дней"

Card 4: "PnL Месяц"
  Value: "+48 903 ₽" (green)
  Sub: "30 дней"

Card 5: "Max Drawdown"
  Value: "-3.2%" (red)
  Sub: "от пика"

Card 6: "Sharpe 252д"
  Value: "1.84" (white if >1, orange if 0.5-1, red if <0.5)
  Sub: "аннуализированный"

SECTION 2 — MAIN GRID (2 columns: 1fr 340px)

LEFT COLUMN:

  Block A — Equity Curve Chart Card:
    Header: "Equity Curve" | subtitle "Paper Trading · Полная история"
    Chart: area chart, height 280px. Orange gradient fill under line.
    X-axis: dates (dd.MM). Y-axis: ₽ values (right-aligned, muted).
    Tooltip: date + "1 248 304 ₽ (+248 304 ₽ от старта)"
    Empty state: "Недостаточно данных для построения графика. Запустите бот."

  Block B — Last Signals Table Card:
    Header: "Последние сигналы" | subtitle auto-updates "Обновлено 14с назад"
    Table columns: Время | Тикер | Сигнал | Entry | SL | TP1 | Вер.% | Статус
    Row example: "14:32" | "SBER" | [BUY badge green] | "312.4" | "306.0" | "322.0" | bar+63% | [NEW badge blue]
    Confidence shown as: small horizontal bar (60px) + "63%" text
    Max 10 rows. "Загрузить ещё →" link below.
    Empty: "Сигналов нет. Нажмите «Сгенерировать» в разделе Signals."

  Block C — Paper Trading Live Feed Card:
    Header: "Paper Trading — Live Feed" | [LIVE badge orange with pulse dot]
    Scrollable list (max 220px), newest on top, slide-in animation.
    Each row: [direction badge] ticker price | "→" | exit_price | pnl colored | timestamp
    Example row: [LONG] SBER 312.40 → 318.20 +1 872 ₽ · 14:33
    Empty: "Запустите движок через кнопку «▶ Запустить» в разделе Analytics"
    Footer: small grey text "Транзакции в реальном времени · SSE"

RIGHT SIDEBAR (340px, flex column, gap 12px):

  Panel 1 — Risk Metrics:
    Header: "Риск-метрики"
    4 rows with label + progress bar + value:
      Unrealized PnL | [bar] | "+3 240 ₽" (from paper_positions, not Tinkoff)
      Просадка       | [bar, red fill if >5%] | "-3.2%"
      Позиции        | [bar] | "3 / 5"
      Win Rate       | [bar, green fill] | "63.2%"
    Bar fill: green <50% drawdown, orange 50-80%, red >80%

  Panel 2 — Active Positions:
    Header: "Активные позиции" | count badge "3"
    Scrollable list (max 220px).
    Each position row:
      Left: ticker (mono bold) + direction badge + qty shares
      Right: unrealized PnL (colored) + PnL%
      Progress bar below: 3px height, distance from entry to SL (red) / TP (green)
    Empty: "Нет открытых позиций" with "→ Открыть через Signals" link

  Panel 3 — Brokers:
    Header: "Брокеры"
    Row per broker: status dot | name | badge
      ● T-Банк | [CONNECTED green] if token set, [NOT CONFIGURED orange] if not
      ● Bybit   | [CONNECTED] or [NOT CONFIGURED]
      ● Finam   | [DEV grey] — always "В разработке"

  Panel 4 — Infrastructure:
    Header: "Инфраструктура"
    3-column mini grid:
      DB: green/red dot + "Online"/"Offline"
      SSE: dot + client count "2 clients"
      Engine: dot + "Running"/"Stopped"
      Forward: dot + last candle time
      Signals: count "12 new"
      Memory: "124 MB" (if available)

  Panel 5 — Recent Trades (from paper_trades):
    Header: "Последние сделки"
    Max 5 rows: ticker | direction badge | pnl colored | time muted
    "Подробнее в Analytics →" link

  Panel 6 — System Log:
    Header: "Системные события"
    Log entries from system_events table (NOT news):
      [INFO/WARN/ERR badge] timestamp | message
    Max 8 entries. Auto-scroll to newest. Color: INFO=blue, WARN=orange, ERR=red.

INTERACTIONS:
- Clicking ticker in any panel → navigates to Portfolio view, auto-selects ticker
- Clicking [▶ Запустить] in broker panel → POST /api/platform/engine/start, status pill updates
- SSE events append to Live Feed with slide animation
- Refresh button spins icon, triggers all polls simultaneously
- Keyboard: 1=dashboard, 2=portfolio, 3=signals, 4=backtest, 5=miniapp, 6=analytics, R=refresh

EMPTY / ERROR STATES:
- All KPI cards: show shimmer on first load, then "—" with tooltip "Нет данных"
- Equity chart empty: centered illustration-free message + button "Запустить бот"
- DB offline: orange banner below topbar "База данных недоступна · Проверьте подключение"
- Engine stopped: blue info banner "Движок остановлен. Запустите для автоматической торговли. [▶ Запустить]"

DO NOT:
- Show any hardcoded portfolio value (like "1 000 000 ₽ base capital")
- Show unrealized PnL from Tinkoff API (use paper_positions.unrealized_pnl)
- Show news as system log
- Mix legacy trades table metrics with paper_accounts metrics
```
