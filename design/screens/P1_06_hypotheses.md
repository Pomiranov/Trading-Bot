# P1 · Screen 6: Learning — Hypotheses Pipeline (НОВЫЙ ЭКРАН)

> Приоритет: P1 — визуализация научного подхода бота, дифференциатор для монетизации.
> Статус: MISSING в текущем UI. Подраздел экрана Learning (вкладка или секция).
> Данные: hypotheses table (уже в schema).

---

## Backend: что нужно добавить

```python
# В platform_routes.py добавить:
@platform_bp.route("/learning/hypotheses")
def api_hypotheses():
    stage = request.args.get("stage")  # filter by stage
    sql = """
        SELECT hypothesis_id, description, market, stage,
               conditions, total_trades, winning_trades, win_rate,
               profit_factor, expectancy, confidence,
               stat_test_result, created_at, promoted_at, rejected_at, updated_at
        FROM hypotheses
        WHERE (:stage IS NULL OR stage = :stage)
        ORDER BY 
            CASE stage 
                WHEN 'active' THEN 1 
                WHEN 'candidate' THEN 2 
                WHEN 'observation' THEN 3 
                WHEN 'rejected' THEN 4 
            END,
            updated_at DESC
    """
    return jsonify(_query(sql, {"stage": stage}))

@platform_bp.route("/learning/skipped")
def api_skipped_signals():
    rows = _query("""
        SELECT skip_reason, COUNT(*) as count, 
               MAX(skipped_at) as last_at
        FROM skipped_signals
        GROUP BY skip_reason
        ORDER BY count DESC
    """)
    return jsonify(rows)
```

---

## Stitch Prompt

```
[PASTE DESIGN SYSTEM PREFIX FROM design/DESIGN_SYSTEM.md HERE]

---

SCREEN: QuantFlow Learning — Hypotheses Pipeline

PURPOSE:
Shows the bot's hypothesis discovery and validation pipeline. Every pattern the bot
finds goes through 3 stages before influencing real trades: observation (30+ trades),
candidate (100+ trades with stat tests), active (300+ trades, proven). This screen
visualizes this scientific process and shows users that the bot doesn't guess — it proves.

This is a sub-section within the "Learning" screen, accessible via tab:
  [Belief System] [Hypotheses] tabs at top of Learning page.

DATA SOURCE:
- GET /api/platform/learning/hypotheses → hypotheses table
- GET /api/platform/learning/skipped → skipped_signals grouped by reason

PAGE LAYOUT (within Learning screen, after tab switch):
Header stays the same. Content area changes to hypotheses view.

STAGE PIPELINE VISUAL (full width, horizontal):
  4 columns representing stages, with arrow connectors between them:
  
  [OBSERVATION]  →  [CANDIDATE]  →  [ACTIVE]  →  [REJECTED]
  "30+ сделок"      "100+ сделок"   "300+ сделок"   "—"
  [12]               [4]             [2]              [31]
  
  Each column: stage name (caps) | count badge | description text xs muted
  Arrow: → with label "статтесты" between CANDIDATE and ACTIVE
  
  Colors:
    OBSERVATION: blue (#3861fb)
    CANDIDATE:   orange (#F7931A)
    ACTIVE:      green (#00c076)
    REJECTED:    grey (#5e6673, slightly transparent)
  
  Click on stage → filters hypothesis cards below

FILTER TABS ROW:
  [Все] [Observation 12] [Candidate 4] [Active 2] [Rejected 31]
  Each tab shows count. Active tab has orange underline indicator.

SECTION 1 — HYPOTHESIS CARDS GRID (auto-fill, min 320px):

Each card:

  HEADER ROW:
    Left: [stage badge] (OBS/CAND/ACTIVE/REJECT colored)
    Right: Created date "12 Июл" (muted xs) | UUID short "#a3f2..." (mono muted xs)

  DESCRIPTION (main content):
    "Стратегия 'rules_engine' в режиме 'trending'" (Inter 13px text-primary)
    Market badge: "MOEX" (blue xs) | "MOEX stocks" context

  PROGRESS BAR (shows trades gathered vs threshold):
    For observation (need 100): 30/100 trades → 30% bar
    For candidate  (need 300): 147/300 → 49%
    For active: shows "✓ Доказана" with green fill 100%
    For rejected: shows "✗ Отклонена" with red fill, opacity 0.5
    
    Label: "47 / 100 сделок до следующей стадии" (muted xs below bar)

  STATS MINI-GRID (3 columns, shown if total_trades > 0):
    Сделок:      "47"
    Win Rate:    "58.3%" (green if >50%)
    Profit Factor: "1.42" (green if >1)
    Expectancy:  "+0.28R" (green if >0)
    Confidence:  confidence meter (mini, 4px)
    Условия:     "volume_ratio > 1.5" (mono xs, from conditions JSONB)

  STAT TEST RESULTS (shown only for CANDIDATE and ACTIVE):
    Compact row: "Binomial p-value: 0.023 ✓" (green if <0.05)
                 "Bootstrap CI: [+0.12, +0.48] ✓" (green if ci_low > 0)
    If not yet tested: "Тесты: ожидание накопления 300 сделок"

  TIMELINE PILLS (horizontal, xs):
    [Created 12 Июл] → [Promoted 18 Июл] (if promoted_at set)
    For rejected: [Created] → [Rejected 19 Июл]

  FOOTER: conditions displayed as code-style tags:
    [strategy_id: rules_engine] [market_regime: trending]

  Card border-left: 3px colored by stage.
  Rejected cards: 60% opacity, visual "faded" appearance.
  
  Active cards: slight green glow on hover (0 0 12px rgba(0,192,118,0.15))

SECTION 2 — ACTIVE HYPOTHESES DETAIL (shown when Active tab selected):

  For each active hypothesis, expanded card showing:
  - Full stat test results in readable form:
    ┌────────────────────────────────────┐
    │ Результаты статистических тестов   │
    │ ──────────────────────────────────  │
    │ Binomial test:   p=0.023  ✓ <0.05 │
    │ Bootstrap 95% CI: [+0.12, +0.48]  │
    │ Win Rate:         53.2%   ✓ >50%  │
    │ Profit Factor:    1.48    ✓ >1.2  │
    │ Expectancy:      +0.28R   ✓ >0    │
    │                                    │
    │ ✓ ГИПОТЕЗА ПРИНЯТА                │
    │ Влияет на торговые решения         │
    └────────────────────────────────────┘
  
  This "test results" block styled as terminal/code block:
    bg: rgba(0,0,0,0.4), border: rgba(255,255,255,0.06), radius 6px, 
    font: JetBrains Mono 11px, padding: 12px 16px

SECTION 3 — SKIPPED SIGNALS BREAKDOWN (full width card, below hypothesis cards):
  Header: "Пропущенные сигналы" | sub: "Почему бот не торгует"
  
  Horizontal bar chart (ECharts):
    max_daily_loss   ████████████████  48 (most common, red bar)
    low_confidence   ████████          24 (orange bar)  
    max_positions    ██████            18 (orange)
    regime_filter    ████              12 (blue)
    manual_skip      ██                6  (grey)
  
  Each bar: label | bar | count | percentage
  Tooltip: "Сигналы пропущены из-за: превышен дневной лимит убытков (-2.1% из -2.5%)"
  
  Note below: "Частые пропуски из-за max_daily_loss означают что стратегия
               работает в убыточную полосу. Проверьте Belief System → confidence."

INTERACTIONS:
- Stage filter tab → filters cards, updates count in pipeline visual
- Card click → expands to show full stat_test_result JSON (parsed)
- Pipeline stage column click → same as tab filter
- [Обновить] → fetches fresh hypotheses + skipped stats

EMPTY STATES:
- No hypotheses at all: "Движок гипотез не запускался. Нужно минимум 30 закрытых 
  сделок для обнаружения первых паттернов."
- No active hypotheses (only observation): "Ни одна гипотеза ещё не доказана.
  Накоплено 47/100 сделок для перехода в стадию candidate."
- All hypotheses rejected: "Все гипотезы отклонены. Текущие стратегии не показывают
  статистически значимого преимущества. Просмотрите Belief System."
- No skipped signals: "Нет данных о пропущенных сигналах" (simple empty text)

DO NOT:
- Show hypothesis.confidence same as belief_system.confidence (different metrics)
- Show rejected hypotheses prominently (fade them, show last)
- Claim stat test "passed" without showing the actual p-value
- Add decorative progress animations that misrepresent the actual trade count
```
