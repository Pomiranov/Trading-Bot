# QuantFlow Design → Implementation Roadmap

## Критические фиксы (блокируют P0 экраны)

### Fix 1: Переключить метрики Dashboard с legacy trades на paper_accounts

**Проблема:** `/api/metrics` считает portfolio_value = 1_000_000 + SUM(legacy_trades.pnl)  
**Файл:** `bot/ui/dashboard.py` → функция `_db_metrics()` и route `/api/metrics`  
**Решение:** Убрать эндпоинт или переключить на `/api/platform/portfolio`

```python
# БЫЛО (dashboard.py line ~126):
def _db_metrics() -> dict:
    rows = _query("SELECT COUNT(*), ... FROM trades WHERE closed_at IS NOT NULL")
    ...
    portfolio = BASE_CAPITAL + total_pnl  # WRONG

# ДОЛЖНО БЫТЬ: читать из paper_accounts
# Используй AnalyticsService.trade_stats() + PortfolioService.get_summary()
```

**JS:** В `app.js` / `core/sync.js` — заменить вызов `/api/metrics` на `/api/platform/analytics/summary`

---

### Fix 2: Equity Curve — убрать fallback на цену SBER

**Проблема:** `_candle_equity()` в `dashboard.py` — если нет legacy trades, показывает цену SBER как "equity". Это фейковые данные.  
**Файл:** `bot/ui/dashboard.py` → `api_equity()` route  
**Решение:**

```python
@app.route("/api/equity")
def api_equity():
    # Читать только equity_snapshots через AnalyticsService
    svc = AnalyticsService(_engine)
    result = svc.equity_curve(limit=200)
    return jsonify(result)
    # НЕТ fallback на candles/SBER
```

---

### Fix 3: Positions — читать paper_positions вместо legacy trades

**Проблема:** `/api/positions` → `SELECT FROM trades WHERE closed_at IS NULL` — это legacy  
**Файл:** `bot/ui/dashboard.py` → `_db_positions()` и `api_positions()`  
**Решение:** Заменить на `PaperTradingService.refresh_positions()`

---

### Fix 4: Signals table — читать trading_signals вместо trades+trade_feedback

**Проблема:** `/api/signals` делает JOIN trades+trade_feedback, отдаёт это как «сигналы»  
**Файл:** `bot/ui/dashboard.py` → `_db_signals()`  
**Решение:** Удалить `_db_signals()`, в JS использовать `/api/platform/signals`

---

### Fix 5: Log — читать system_events вместо news

**Проблема:** `/api/log` читает таблицу `news` и показывает как системный лог  
**Файл:** `bot/ui/dashboard.py` → `_db_log()`  
**Решение:**

```python
def _db_log():
    rows = _query("""
        SELECT created_at, level, source, message
        FROM system_events
        ORDER BY created_at DESC LIMIT 50
    """)
```

---

### Fix 6: PnL Неделя / PnL Месяц — добавить API эндпоинт

**Проблема:** `#dashPnlWeek` и `#dashPnlMonth` — никогда не заполняются  
**Файл:** `bot/ui/api/platform_routes.py`  

```python
@platform_bp.route("/analytics/pnl-periods")
def api_pnl_periods():
    svc = AnalyticsService(_engine)
    daily = svc.daily_pnl(days=30)
    
    import datetime
    now = datetime.date.today()
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)
    
    week_pnl = sum(r["pnl"] for r in daily 
                   if r["day"] >= str(week_ago))
    month_pnl = sum(r["pnl"] for r in daily)
    
    return jsonify({
        "week": round(week_pnl, 2),
        "month": round(month_pnl, 2),
    })
```

**JS:** В `app.js` добавить вызов и обновление `#dashPnlWeek`, `#dashPnlMonth`

---

### Fix 7: Risk Panel Unrealized — читать paper_positions вместо Tinkoff

**Проблема:** Risk panel тянет unrealized PnL из Tinkoff API  
**Файл:** `bot/ui/static/views/render.js` или `app.js` — find risk panel refresh logic  
**Решение:** 

```js
// Читать unrealized из /api/platform/portfolio
const portfolio = await fetchJSON('/api/platform/portfolio');
const unrealized = portfolio.open_positions_pnl || 0;
document.getElementById('riskDailyVal').textContent = money(unrealized);
```

---

## Schema Additions (schema.py — idempotent migrations)

Добавить в `PLATFORM_SCHEMA_SQL` в `bot/qf_platform/schema.py`:

```sql
-- Колонки новой схемы для trades (из quantflow_schema.sql)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS strategy_id      VARCHAR(50);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_regime    VARCHAR(20);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_features  JSONB;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pnl_r            NUMERIC(10,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS decision_quality NUMERIC(5,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_reason      VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades (strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_regime   ON trades (market_regime);
```

---

## New Sidebar Items (dashboard.html)

Добавить пункт "Learning" в `<nav class="sidebar-nav">`:

```html
<div class="nav-divider"></div>
<div class="nav-section-label">Intelligence</div>
<a href="#" data-view="learning">
  <svg class="nav-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
    <!-- Lucide "brain" icon paths -->
    <path d="M9.5 2a5 5 0 015 5v.5a4.5 4.5 0 01-4.5 4.5H9v6H7v-6H6A4.5 4.5 0 011.5 7.5V7a5 5 0 015-5"/>
  </svg>
  <span class="nav-label">Learning</span>
</a>
```

И новый view section в HTML:
```html
<section id="view-learning" class="view">
  <!-- Tabs: Belief System | Hypotheses -->
  <!-- Content renders based on active tab -->
</section>
```

---

## New API Routes Summary

| Route | Method | Description | Table |
|---|---|---|---|
| `/api/platform/learning/belief` | GET | Belief system для всех стратегий | `belief_system` |
| `/api/platform/learning/hypotheses` | GET | Hypotheses list, filterable by stage | `hypotheses` |
| `/api/platform/learning/skipped` | GET | Skipped signals grouped by reason | `skipped_signals` |
| `/api/platform/analytics/pnl-periods` | GET | PnL за неделю и месяц | `paper_trades` |

---

## Dependency Map

```
P0 Dashboard fix
  └─ Fix 1 (metrics) → uses /api/platform/analytics/summary ✓ EXISTS
  └─ Fix 2 (equity) → uses AnalyticsService.equity_curve() ✓ EXISTS  
  └─ Fix 3 (positions) → uses PaperTradingService ✓ EXISTS
  └─ Fix 4 (signals) → uses /api/platform/signals ✓ EXISTS
  └─ Fix 5 (log) → uses system_events table ✓ EXISTS
  └─ Fix 6 (pnl-periods) → NEW endpoint needed
  └─ Fix 7 (unrealized) → uses /api/platform/portfolio ✓ EXISTS

P1 Belief System screen
  └─ NEW /api/platform/learning/belief route
  └─ belief_system table ✓ EXISTS in schema

P1 Hypotheses screen  
  └─ NEW /api/platform/learning/hypotheses route
  └─ NEW /api/platform/learning/skipped route
  └─ hypotheses table ✓ EXISTS in schema
  └─ skipped_signals table ✓ EXISTS in schema

P1 Portfolio (mostly works, needs):
  └─ Fix 7 (unrealized from paper)
  └─ Operations history → use paper_trades (NOT legacy trades)
```

---

## Что НЕ добавлять (без данных в схеме)

- **Confidence history chart** — нет таблицы `belief_confidence_history`. Добавить таблицу если нужно.
- **decision_quality per trade** — колонка есть в `quantflow_schema.sql` но не в `schema.py`. Добавить через migration fix выше.
- **Performance by market regime** — нужны заполненные `trades.market_regime`. Убедись что `TradingOrchestrator` пишет это поле.
