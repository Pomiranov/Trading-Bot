# P0 · Screen 2: Analytics — Performance Dashboard

> Приоритет: P0 — без этого нельзя понять работает ли стратегия.
> Стек: Flask + ECharts + vanilla JS. Данные из paper_trades + equity_snapshots.

---

## Stitch Prompt

```
[PASTE DESIGN SYSTEM PREFIX FROM design/DESIGN_SYSTEM.md HERE]

---

SCREEN: QuantFlow Analytics — Paper Trading Performance

PURPOSE:
Full performance analysis of the paper trading engine. Shows cumulative equity curve,
8 key metrics (Sharpe, Sortino, Drawdown, Win Rate, Profit Factor, ROI, Total PnL,
Avg Hold Time), monthly/daily PnL breakdown, best/worst trades, and closed trades
history. Also shows engine start/stop control.

DATA SOURCES:
- Full analytics: GET /api/platform/analytics → AnalyticsService.full_report()
  Returns: { stats, equity_curve, monthly_pnl, daily_pnl, best_worst, strategy_breakdown }
- Engine status: GET /api/platform/engine/status → { running: bool, trades_today: int }
- Engine control: POST /api/platform/engine/start | /stop
- Trades list: GET /api/platform/paper/trades?limit=50

PAGE HEADER (standard topbar content):
Title: "Analytics" | Breadcrumb: "Paper Trading Performance · Strategy Analysis"
Right buttons: [▶ Запустить движок] (primary orange) | [Обновить] (secondary)

ENGINE STATUS BAR (card, full width, 4-column grid):
  Status:           "Running" (green dot) / "Stopped" (red dot)
  Комиссия:         "0.03%"
  Проскальзывание:  "0.01%"
  Источник данных:  "Paper · MOEX DB" (dynamic, from API)
  
  If engine stopped: bar has subtle red-left-border-3px, status text is red.
  If engine running: bar has green-left-border-3px.

SECTION 1 — STATS GRID (8 KPI cards, responsive: 8 cols → 4 cols → 2 cols)

Cards (all KPI card component):
  1. Всего сделок   | value: "124"       | sub: "paper trades"
  2. Win Rate       | value: "63.2%"     | sub: "победных" | positive if >50%
  3. Profit Factor  | value: "1.84"      | sub: "вал.прибыль/убыток" | positive if >1.5, orange if 1-1.5, red if <1
  4. Sharpe Ratio   | value: "1.42"      | sub: "аннуализированный" | green >1, orange 0.5-1, red <0.5
  5. Sortino Ratio  | value: "2.18"      | sub: "по downside" | same color logic
  6. Max Drawdown   | value: "-4.8%"     | sub: "от пика" | always red, lighter if small
  7. Total PnL      | value: "+248 303 ₽"| sub: "за всё время" | green/red
  8. ROI %          | value: "+24.8%"    | sub: "от начального капитала" | green/red

Loading state: shimmer in all 8 cards simultaneously.
Empty state (no paper_trades): all cards show "—" with tooltip "Нет сделок в paper engine"

SECTION 2 — CHARTS ROW (2 columns: 2fr 1fr)

Chart A — Equity Curve (2fr):
  Header: "Equity Curve" | sub: "Paper Trading · Полная история"
  ECharts area chart, height 260px.
  Orange gradient fill (opacity 0.15 at bottom → 0.45 at top).
  Line: #F7931A, width 2px.
  X-axis: dates. Y-axis (right): ₽.
  Reference line: "Начало: 1 000 000 ₽" (dashed, muted).
  Tooltip: shows date, equity, absolute change from start, ROI%.
  Empty: "Нет данных equity curve. Запустите paper engine и дайте ему поработать."

Chart B — Monthly PnL (1fr):
  Header: "Monthly P&L" | sub: "По месяцам"
  ECharts bar chart, height 260px.
  Positive bars: #00c076. Negative bars: #f6465d.
  X-axis: "Июл", "Авг" etc. Y-axis: ₽.
  Tooltip: month | pnl | trades | win_rate%.
  Empty: "Нет месячных данных"

SECTION 3 — BOTTOM ROW (3 columns: 1fr 1fr 1fr)

Panel A — Daily PnL (30 days):
  Header: "Дневная P&L (30 дней)"
  Scrollable table (max 280px), newest first:
    Дата | P&L | Сделок
    "19 Июл" | "+4 832 ₽" (green) | "3"
    "18 Июл" | "-1 240 ₽" (red)   | "2"
  Zero-PnL days shown in muted grey "0 ₽".
  Empty: "Нет сделок за 30 дней"

Panel B — Лучшие сделки (top 5 by PnL):
  Header: "Лучшие сделки"
  Each item (compact row):
    Ticker badge | direction | "+4 832 ₽" green | "+1.54%" | date muted
    Sub: "Entry 312.4 → Exit 317.2 · 4.2ч"
  Empty: "—"

Panel C — Худшие сделки (worst 5 by PnL):
  Header: "Худшие сделки"
  Same format, values in red.
  Empty: "—"

SECTION 4 — CLOSED TRADES TABLE (full width card):
  Header: "История Paper Trades" | sub: "124 сделок"
  Pro table, scrollable x on mobile.
  Columns: Тикер | Dir | Entry | Exit | Qty | PnL | PnL% | Комис. | Причина | Закрыта
  
  Row example:
    SBER | [LONG green badge] | 312.40 | 317.20 | 100 | +480 ₽ [green] | +1.54% | 9.4 ₽ | take_profit | 19.07 14:32
  
  Причина (close_reason) shown as small badge:
    take_profit: [TP green]
    stop_loss:   [SL red]
    manual:      [grey]
    signal:      [blue]
  
  Pagination: "Показать ещё 50" button below table.
  Empty: full empty state with icon 📊 and "Нет закрытых сделок"

SECTION 5 — STRATEGY BREAKDOWN (collapsible, default closed):
  Header: "По источникам сигналов" | collapse chevron
  Bar chart horizontal: source name | bar | trades count | total_pnl
    rules_engine | ████████ | 89 сделок | +180 204 ₽
    manual       | ████     | 35 сделок | +68 099 ₽

ENGINE CONTROL MODAL (appears on click "Запустить движок"):
  Title: "Запустить Paper Engine"
  Body: "Движок будет автоматически генерировать сигналы и открывать позиции
         на виртуальном счёте. Реальные деньги не используются."
  Buttons: [Отмена] [▶ Запустить] (orange primary)
  After start: modal closes, status bar updates to "Running", toast "Движок запущен"

EMPTY / ERROR STATES:
- No paper account: warning card "Аккаунт не создан. Будет создан автоматически при первом запуске."
- Engine never ran: info banner "Движок ни разу не запускался. Нажмите «▶ Запустить» для начала."
- API error: each section shows its own error state independently (not full-page error)

DO NOT:
- Show Sharpe from legacy trades table
- Hardcode "Источник данных: MOEX · DB"
- Show Sortino as always 0
- Mix paper_trades and legacy trades data
```
