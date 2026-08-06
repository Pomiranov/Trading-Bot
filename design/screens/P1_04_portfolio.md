# P1 · Screen 4: Portfolio

> Приоритет: P1 — нужен для монетизации, пользователь должен видеть свои деньги.
> Данные: paper_accounts + paper_positions + equity_snapshots + candles.

---

## Stitch Prompt

```
[PASTE DESIGN SYSTEM PREFIX FROM design/DESIGN_SYSTEM.md HERE]

---

SCREEN: QuantFlow Portfolio

PURPOSE:
Portfolio overview combining paper trading account with market data. Shows total balance,
allocation chart, equity curve, open positions (full table with SL/TP), trade history,
and market overview with candlestick charts per ticker.

DATA SOURCES:
- Account + positions: GET /api/platform/portfolio → paper_accounts + paper_positions
- Portfolio positions: GET /api/platform/portfolio/positions
- Equity curve: GET /api/platform/analytics → equity_snapshots
- Candles (chart): GET /api/candles?ticker=SBER&limit=120
- Market overview: GET /api/portfolio → candles last price + 1d/30d change
- Operations history: GET /api/platform/paper/trades

PAGE HEADER:
Title: "Portfolio" | Breadcrumb: "Allocation · Equity · PnL · ROI"
Right badges: source badge "Paper RUB" (blue) | "Обновлено 14:32" (muted)

SECTION 1 — METRICS GRID (auto-fill, min 118px cards, 8 cards):
  Balance:          "1 248 304 ₽" (hero-sized)
  Available:        "824 100 ₽"
  Margin Used:      "424 204 ₽"
  Unrealized PnL:   "+3 240 ₽" (green, from paper_positions SUM unrealized_pnl)
  Day PnL:          "+4 832 ₽" (green)
  Open Positions:   "3"
  Closed Trades:    "124"
  ROI:              "+24.8%"

SECTION 2 — FOUR-COLUMN LAYOUT (1.2fr 1fr 1fr 280px):

Panel A — Equity Curve (1.2fr):
  ECharts area chart, height 240px. Same style as Analytics.
  Shows equity from start to now. Orange line + gradient fill.

Panel B — Asset Allocation (1fr):
  ECharts donut chart, height 180px. 
  Colors: SBER=#F7931A, GAZP=#3861fb, LKOH=#00c076, NVTK=#f6465d, etc.
  Below chart: allocation list rows:
    [orange dot] SBER  ████████████  42%
    [blue dot]   GAZP  ████████      28%
    [green dot]  LKOH  ████          18%
    [grey dot]   Cash  ███           12%

Panel C — По валютам (1fr):
  ECharts donut, height 180px.
  RUB = orange (100% for paper RUB mode).
  Below: currency breakdown list.

Panel D — Positions scroll panel (280px):
  Header: "Позиции" | count
  Scrollable list, max height 280px.
  Each: ticker bold | direction badge | qty | unrealized_pnl colored
  Tap → scrolls to full positions table below

SECTION 3 — HIGHLIGHTS ROW (2 columns: 1fr 1fr):

Best Positions (top 3 by unrealized_pnl):
  Each row: [direction badge] TICKER entry→current | +PnL green | +% green
  Sub: "Открыта 3д 4ч"
  Empty: "—" centered

Worst Positions (bottom 3):
  Same, values in red.

SECTION 4 — OPEN POSITIONS TABLE (full width, glass panel):
  Header: "Открытые позиции" | sub: "Live sync · SSE + polling"
  
  Scrollable horizontally. Columns:
  Symbol | Exchange | Side | Entry | Current | Amount | Leverage | Margin | Unreal. PnL | ROI% | SL | TP | Open Time | Actions
  
  Example row:
  SBER | MOEX | [LONG↑] | 312.40 | 318.20 | 100 шт | 1× | 31 240 ₽ | +580 ₽ | +1.86% | 306.00 | 322.00 | 16.07 09:14 | [Close ×]
  
  SL column: red "306.00" with small % distance "–2.1%"
  TP column: green "322.00" with "+3.1%"
  ROI: green if positive, red if negative
  Actions: [×] close button → confirm modal → POST /api/platform/paper/position/{id}/close
  
  Bottom: [Открыть позицию] button (secondary) — navigates to Signals

SECTION 5 — OPERATIONS HISTORY TABLE (full width, glass panel):
  Header: "История операций" | sub: "paper_trades · Синхронизация Dashboard + Telegram"
  
  Columns: Дата | Тип | Symbol | Exchange | Side | PnL | Комис. | Причина | Статус
  
  Row: 
  19.07 14:32 | Закрытие | SBER | MOEX | [LONG↑] | +480 ₽ | 9.4 ₽ | take_profit [TP green badge] | [DONE grey]
  
  Pagination: "Загрузить ещё 50" below

SECTION 6 — MARKET OVERVIEW (full width, glass panel):
  Header: "Market Overview" | sub: "Динамический список инструментов"
  
  Search bar: "Поиск актива..." (full width top)
  
  Watchlist bar: horizontal scrollable chip list
    [SBER ×] [GAZP ×] [LKOH] ... [+ Добавить]
  
  Ticker cards grid (auto-fill min 160px):
  Each card (ticker-card component):
    Exchange badge (xs muted top-right)
    Symbol: "SBER" (mono bold md)
    Price: "312.40 ₽" (mono lg)
    1D change: "+1.54%" (green) | bar sparkline (24px, 7 days)
    30D change: "+8.2%" (green)
    Volume: "48.2M"
  Click → chart below updates

SECTION 7 — MARKET CHART (full width, glass panel):
  Header: title updates to "SBER · Котировки" | sub: "1d · MOEX"
  Ticker tabs: [SBER] [GAZP] [LKOH] ...
  
  Lightweight-charts candlestick, height 280px. Dark theme:
    Up candles: #00c076 fill
    Down candles: #f6465d fill
    Grid: rgba(255,255,255,0.04)
    Crosshair: rgba(255,255,255,0.2)
  
  Empty: "Нет данных свечей для SBER. Загрузите исторические данные."

INTERACTIONS:
- Closing position: [×] → confirm dialog "Закрыть SBER LONG 100 шт?" → POST close → SSE event → table updates
- Ticker card click → chart section scrolls into view + chart updates
- Watchlist chip [×] → removes from watchlist (localStorage)
- [+ Добавить] → inline input field appears
- SSE "portfolio_updated" → positions table refreshes with highlight animation

EMPTY STATES:
- No paper account: "Аккаунт будет создан при первом запуске Paper Engine" + [Запустить] link
- No positions: "Нет открытых позиций" + "→ Найти сигналы" link in empty-state style
- No trades history: "История пуста. Сделки появятся после первого запуска."
- No market data: "Нет рыночных данных. Данные загружаются из MOEX."

DO NOT:
- Show Tinkoff real portfolio as "Portfolio" (it's a separate tab in Settings)
- Show paper trades in "Operations History" mixed with legacy trades
- Show SL/TP from legacy trades table (use paper_positions.stop_loss / take_profit)
```
