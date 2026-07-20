# P1 · Screen 5: Learning — Belief System (НОВЫЙ ЭКРАН)

> Приоритет: P1 — уникальное преимущество QuantFlow, proof-of-learning для монетизации.
> Статус: MISSING в текущем UI. Требует добавления в sidebar + Flask route.
> Данные: belief_system table (уже в schema).

---

## Backend: что нужно добавить

```python
# В platform_routes.py добавить:
@platform_bp.route("/learning/belief")
def api_belief_system():
    rows = _query("""
        SELECT strategy_id, strategy_name, market, total_trades, 
               winning_trades, win_rate, profit_factor, expectancy,
               sharpe_ratio, confidence, best_regime, best_timeframe,
               max_consecutive_losses, updated_at, last_trade_at
        FROM belief_system 
        ORDER BY confidence DESC
    """)
    return jsonify(rows)
```

---

## Stitch Prompt

```
[PASTE DESIGN SYSTEM PREFIX FROM design/DESIGN_SYSTEM.md HERE]

---

SCREEN: QuantFlow Learning — Belief System

PURPOSE:
Shows the bot's learned confidence in each trading strategy. Each strategy has a
confidence score (0-1) that updates after every trade based on win_rate, profit_factor,
and expectancy. This screen proves to users that the bot actually "learns" — its unique
selling point vs simple rule-based bots.

DATA SOURCE:
- GET /api/platform/learning/belief → belief_system table
  Returns: strategy_id, strategy_name, market, total_trades, winning_trades,
           win_rate, profit_factor, expectancy, sharpe_ratio, confidence,
           best_regime, best_timeframe, max_consecutive_losses, updated_at

ADD TO SIDEBAR (after Analytics, before Settings):
  Icon: brain/neural network icon (Lucide "brain" or "sparkles")
  Label: "Learning"
  Under "Trading" section, position 5

PAGE HEADER:
Title: "Learning" | Breadcrumb: "Belief System · Strategy Confidence"
Right: "Обновлено: 19.07 14:32" muted | [Обновить] secondary button

INTRO CARD (collapsible, shows first time only):
  "QuantFlow учится на каждой сделке. Confidence отражает насколько бот доверяет
   каждой стратегии на основе исторических результатов. Минимум 20 сделок нужно
   для формирования достоверной оценки."
  [×] close button (stores in localStorage)

SECTION 1 — STRATEGY BELIEF CARDS (grid, auto-fill min 300px):

Each strategy card:

  HEADER ROW:
    Left: strategy name "Rules Engine" (Inter 14px weight 600)
          market badge "MOEX" (blue) | best_regime badge: "trending" (orange) / "ranging" (grey)
    Right: last updated time "14:32" (muted xs)

  CONFIDENCE METER (main visual — prominently displayed):
    Label: "Confidence" (muted caps 10px)
    Large bar: height 12px, radius 6px, full width.
    Gradient fill: #f6465d (0%) → #F7931A (50%) → #00c076 (100%)
    Current fill position: e.g. 73% → mostly green
    Text overlay right: "73%" (JetBrains Mono 20px weight 700, colored same as bar end)
    
    States:
      < 30%: red zone label "Стратегия убыточна · Бот снизил лоты"
      30-50%: orange "Накопление данных · Результат неоднозначный"
      50-70%: yellow "Умеренное доверие · Стратегия в работе"
      > 70%: green "Высокое доверие · Полный лот"
    
    Animate bar on load: width 0% → actual% over 800ms ease-out-expo

  METRICS MINI-GRID (2×3, inside card):
    Сделок:      "124"       | Win Rate:    "63.2%" (green)
    Profit Factor: "1.84" (green if >1) | Expectancy: "+0.42R" (green if >0)
    Sharpe:      "1.42"      | Макс серия убытков: "4"
  
  BEST REGIME ROW:
    "Лучший режим:" | [trending] badge | "avg +0.62R за 47 сделок"
    Small note: "Бот автоматически снижает объём в режиме 'ranging'"

  FOOTER: 
    Left: "Последняя сделка: 2ч назад" (muted xs)
    Right: "Мин. сделок для статистики: 20" (muted xs, shown if total_trades < 20)

  Card border-left: 3px, colored by confidence zone (green/orange/red)
  
  INSUFFICIENT DATA STATE (< 20 trades):
    Confidence bar shows question mark instead of value.
    Overlay text: "Недостаточно данных · 12/20 сделок"
    Bar: dashed outline, empty fill, muted.

SECTION 2 — CONFIDENCE HISTORY CHART (full width card):
  Header: "История Confidence · Rules Engine" | (updates when card selected)
  ECharts line chart, height 200px.
  Line: #F7931A, width 2px. Dots at each update point.
  Reference lines: 0.5 (dashed grey "нейтрально"), 0.7 (dashed green "высокое")
  X-axis: dates. Y-axis: 0 to 1 (0% to 100%).
  Note: This requires adding confidence_history table (see ROADMAP.md).
  Fallback if no history: show current confidence as single point + note "История будет доступна после накопления данных"

SECTION 3 — PERFORMANCE BY REGIME TABLE (full width card):
  Header: "Эффективность по режимам рынка"
  
  Table columns: Режим | Стратегия | Сделок | Win Rate | Avg PnL R | Итог ₽
  
  trending  | rules_engine | 47 | 68.1% | +0.62R | +82 400 ₽ (green)
  ranging   | rules_engine | 31 | 48.4% | -0.12R | -8 200 ₽  (red)
  volatile  | rules_engine | 19 | 52.6% | +0.08R | +3 100 ₽  (orange)
  
  Regime badges:
    trending: orange pill "TREND"
    ranging: grey pill "RANGE"
    volatile: red pill "VOLAT"
  
  Bottom note: "Бот автоматически применяет стратегии только в режимах с confidence > 0.5"
  
  Requires: trades.market_regime column populated (see ROADMAP.md)
  Fallback: "Данные по режимам недоступны. Добавьте market_regime в схему trades."

INTERACTIONS:
- Click strategy card → highlights it, updates Confidence History chart below
- Hover confidence bar → tooltip: "Рассчитано на основе: WinRate (33%) + Profit Factor (33%) + Expectancy (33%)"
- [Обновить] → fetches fresh data, bars animate from current to new values

EMPTY STATES:
- No strategies in belief_system: "Система обучения не инициализирована.
  Добавьте стратегии в таблицу belief_system." + code snippet showing INSERT.
- Strategy with 0 trades: card still shows but confidence bar is empty/dashed.
- belief_system not in schema: API returns 404 → error card with migration SQL.

DO NOT:
- Show confidence as simple text number without the visual meter
- Mix belief_system.confidence with paper_accounts.balance
- Show "confidence" label on signal cards from trading_signals.probability_pct
  without clarifying they are different metrics
```
