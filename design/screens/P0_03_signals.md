# P0 · Screen 3: Signals Center

> Приоритет: P0 — основа для торговых решений.
> Данные: trading_signals + live indicators из candles. Связка с belief_system для confidence.

---

## Stitch Prompt

```
[PASTE DESIGN SYSTEM PREFIX FROM design/DESIGN_SYSTEM.md HERE]

---

SCREEN: QuantFlow Signals Center

PURPOSE:
Aggregated view of all trading signals. Shows live indicator cards per ticker (RSI,
MACD, ADX, Bollinger), the signals table from DB, and allows generating new signals
and executing them as paper trades. Confidence % comes from trading_signals.probability_pct
and optionally from belief_system.confidence for the strategy that generated the signal.

DATA SOURCES:
- Live indicators: GET /api/signals/live → computed from candles table (RSI, MACD, ADX, BB)
- Signals table: GET /api/platform/signals?limit=100 → trading_signals table
- Generate: POST /api/platform/signals/generate → creates new signals + SSE event
- Execute: POST /api/platform/signals/{id}/execute → opens paper position
- Signal detail: GET /api/platform/signals/{id}

PAGE HEADER:
Title: "Signals Center" | Breadcrumb: "AI · Indicators · Strategy"

FILTER TOOLBAR (horizontal, wraps on small screens):
  [Exchange dropdown: Все биржи / MOEX / Bybit] 
  [Asset input text: "Актив..."]
  [Strategy: Все стратегии / rules_engine / indicators]
  [Direction: Все / LONG / SHORT]
  [Asset class: Все / Stocks / Crypto / Futures / ETF]
  [Date from: date input]
  [Сгенерировать] (orange primary button)
  [Обновить] (secondary button)

SECTION 1 — STATS PILLS ROW (horizontal, flex-wrap):
  Pill: "Всего · 47"     (white number, muted label)
  Pill: "▲ LONG · 29"   (green number)
  Pill: "▼ SHORT · 18"  (red number)
  Pill: "✓ Active · 12" (orange)
  Pill: "⊘ Expired · 35" (muted)
  Pill: "Ср. Confidence 68%" (blue)

SECTION 2 — LIVE INDICATOR CARDS GRID (auto-fill, min 220px per card):

Each card (signal-card component):
  Top: ticker (mono bold lg) | [BUY/SELL/HOLD badge] | exchange badge (xs muted)
  Price: "312.40 ₽" (mono xl)
  
  Mini data grid (2×2 inside card):
    RSI 14:   value (red if >70, green if <30, muted if 30-70)
    MACD hist: value (green if >0, red if <0)
    ADX:       value (bold orange if >25 = trending)
    BB %:      value (red if >0.9, green if <0.1)
  
  Confidence bar (6px height):
    Label "Confidence" (muted 10px) | bar gradient red→orange→green | "68%" (mono 12px)
  
  Bottom: [▶ Исполнить] button (full width, primary if BUY, secondary if SELL)
  
  Card border: 3px left accent (green=BUY, red=SELL, orange=HOLD)
  Card hover: translateY(-2px), shadow md
  
  Loading state: full shimmer card same dimensions
  Empty state card: "TICKER · Нет данных" with muted "< 35 свечей"

SECTION 3 — SIGNALS JOURNAL TABLE (full width card):
  Header: "Журнал сигналов" | sub: auto-updated "14:32:18"
  
  Pro table (scrollable x):
  Columns: Asset | Exchange | Strategy | Direction | Entry | SL | TP1 | RR | Conf.% | Time | Status | Actions
  
  Row example:
    SBER | MOEX | rules_engine | [LONG ↑] | 312.40 | 306.00 | 322.00 | 1:1.6 | [bar 68%] | 14:32 | [NEW blue] | [▶ Exec]
  
  Direction: arrow icon + text "LONG" (green) or "SHORT" (red)
  RR: Risk/Reward ratio "1:1.6" — green if >1.5, orange if 1-1.5, red if <1
  Confidence: horizontal mini-bar (60px) + percentage
  Status badges:
    new:      [NEW blue]
    active:   [ACT orange pulse dot]
    closed:   [DONE green]
    expired:  [EXP grey]
    cancelled:[grey strikethrough style]
  
  TP column: shows TP1, with "+2" badge (TP colour=green) if multiple TP levels exist
  Actions: [▶] execute button, [👁] detail drawer opener
  
  Footer: "Показать ещё" button | "Экспорт CSV" link

SIGNAL DETAIL DRAWER (slides from right, 400px):
  Triggered by clicking [👁] or any signal row.
  
  Header: "SBER · LONG · #1847" | [close ×]
  
  Section "Параметры":
    Entry:      312.40 ₽
    Stop Loss:  306.00 ₽ (–2.1%)
    Take Profit 1: 322.00 ₽ (+3.1%)
    Take Profit 2: 328.00 ₽ (+5.0%)
    Risk/Reward: 1:1.48
    Confidence: 68% (confidence meter component)
  
  Section "Контекст":
    Strategy:   rules_engine
    Asset class: stocks
    Exchange:   MOEX
    Timeframe:  1d
    Generated:  19.07.2026 14:32
  
  Section "Metadata" (from signals.metadata JSONB, if present):
    Rendered as key-value pairs in monospace.
  
  Footer: [▶ Исполнить в Paper] (orange full-width) | [Закрыть]

TRIGGERED RULES PANEL (appears below table when row selected, collapsible):
  Title: "Сработавшие правила"
  Tags list: each rule as blue tag pill
    [RSI_OVERSOLD] [MACD_CROSS_UP] [ADX_TRENDING] [BB_LOWER_TOUCH]
  If no rules: "Нет данных о сработавших правилах"

INTERACTIONS:
- [Сгенерировать] → POST generate → spinner on button → table refreshes → toast "12 сигналов сгенерировано"
- [▶ Исполнить] → confirm modal → POST execute → SSE event → toast "Позиция открыта: SBER LONG 100"
- Filters → instant filter applied to loaded data (client-side), re-fetch on Apply
- Clicking signal row → opens detail drawer (no navigation)
- SSE "signals_updated" event → row counter badge updates, new rows slide in top of table

EMPTY STATES:
- No signals + no candle data: "Нет данных. Добавьте тикеры в конфигурацию бота."
- No signals but candle data: "Нажмите «Сгенерировать» для создания сигналов."
- All signals filtered out: "Нет сигналов по выбранным фильтрам" with [Сбросить фильтры] link
- Signal execute failed: toast error "Ошибка исполнения: недостаточно средств"

DO NOT:
- Show signals from legacy trades+trade_feedback JOIN
- Show buy_score/sell_score as "confidence" (use probability_pct from trading_signals)
- Use live RSI values as trade signals without the signals table entry
```
