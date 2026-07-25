# QuantFlow Design System v3
> Префикс-блок для всех Stitch-промптов. Вставляй в начало каждого промпта перед описанием конкретного экрана.

---

## Design System Prefix (paste before every Stitch prompt)

```
DESIGN SYSTEM — QuantFlow Trading Terminal v3

THEME: Professional dark trading terminal inspired by TradingView and Binance Pro.
Background is near-black (#050508), not dark-grey. All panels use glass morphism with
subtle backdrop blur. Primary accent is Bitcoin Orange (#F7931A). This is a desktop-first
web app (min 1280px), built with Flask + Jinja2 + vanilla JS + Chart.js / ECharts.
Do NOT use React, Vue, or any frontend framework. No SVG illustrations — use only
geometric UI shapes and text data.

PALETTE:
  Background:     #050508  (app background)
  Surface L1:     #08090d  (page bg)
  Surface L2:     #0c0e14  (sidebar, elevated panels)
  Surface L3:     #111318  (cards)
  Surface L4:     #161a22  (card secondary / inputs)
  Surface L5:     #1c212b  (hover states)
  Glass card:     rgba(17,19,24,0.75) + backdrop-filter:blur(16px)
  Border:         rgba(255,255,255,0.07)
  Border hover:   rgba(255,255,255,0.15)
  Divider:        rgba(255,255,255,0.05)

  Accent Orange:  #F7931A   (primary actions, active nav, brand)
  Accent dim:     rgba(247,147,26,0.12)
  Accent glow:    rgba(247,147,26,0.30)

  Long/Bull:      #00c076   (green, gains, BUY signals)
  Long dim:       rgba(0,192,118,0.12)
  Short/Bear:     #f6465d   (red, losses, SELL signals)
  Short dim:      rgba(246,70,93,0.12)

  Blue:           #3861fb   (info badges, links)
  Blue dim:       rgba(56,97,251,0.12)
  Purple:         #8b5cf6   (miniapp, special features)

  Text primary:   #eaecef
  Text secondary: #b7bdc6
  Text tertiary:  #848e9c
  Text muted:     #5e6673

TYPOGRAPHY:
  Primary font:   Inter (400, 500, 600, 700)
  Monospace font: JetBrains Mono (400, 500, 600)
  
  Scale:
    xs:   11px / line-height 1.4
    sm:   12px / line-height 1.5
    base: 13px / line-height 1.5
    md:   14px / line-height 1.5  ← default UI text
    lg:   16px / line-height 1.4
    xl:   20px / line-height 1.3
    2xl:  28px / line-height 1.2
    3xl:  36px / line-height 1.1  ← hero numbers
  
  Hero numbers (portfolio value, equity): JetBrains Mono, 36px, weight 700
  KPI values: JetBrains Mono, 20px, weight 600
  Table tickers: JetBrains Mono, 12px, weight 700
  Labels/caps: Inter, 11px, weight 500, uppercase, letter-spacing 0.06em

SPACING (4px grid):
  4 / 8 / 12 / 16 / 20 / 24 / 32 / 48px

RADIUS:
  xs: 4px   (badges, tags)
  sm: 6px   (buttons, inputs, small cards)
  md: 10px  (cards, panels)
  lg: 14px  (main cards, hero card)
  xl: 18px  (modal)

SHADOWS:
  sm:  0 1px 2px rgba(0,0,0,0.4)
  md:  0 4px 24px rgba(0,0,0,0.5)
  lg:  0 12px 48px rgba(0,0,0,0.6)
  glow: 0 0 24px rgba(247,147,26,0.30)

LAYOUT:
  Sidebar width:   240px (collapsible to 64px)
  Topbar height:   52px
  Content padding: 16px 20px 24px
  Card gap:        12px

COMPONENT LIBRARY:

1. KPI CARD
   States: loading (shimmer), populated, positive delta, negative delta
   Structure:
     - Label: Inter 11px uppercase muted, letter-spacing 0.06em
     - Value: JetBrains Mono 20px weight 600 (positive=#00c076, negative=#f6465d, neutral=#eaecef)
     - Sub-label: Inter 11px #848e9c
   Card bg: #111318, border: rgba(255,255,255,0.07), radius: 10px
   On hover: border-color rgba(247,147,26,0.2), translateY(-2px)

2. HERO CARD (balance / main metric)
   Full-width or 1.4fr in grid. Gradient bg: linear-gradient(135deg, rgba(247,147,26,.07) 0%, rgba(56,97,251,.04) 100%)
   - Top row: label (muted caps) + source badge (blue)
   - Value: JetBrains Mono 36px weight 700
   - Sub: Inter 12px text-tertiary (e.g. "1 248 сделок · Win Rate 63%")
   - Sparkline: 36px height, orange line, no axes

3. POSITION ROW
   States: profit (green left-border 3px), loss (red left-border 3px)
   Layout: ticker (mono bold) | entry→current | shares | PnL (colored) | PnL% | SL badge
   Progress bar: 3px height shows % distance from entry to SL

4. SIGNAL BADGE / CARD
   - BUY/LONG: bg rgba(0,192,118,0.12), color #00c076, border rgba(0,192,118,0.2)
   - SELL/SHORT: bg rgba(246,70,93,0.12), color #f6465d, border rgba(246,70,93,0.2)
   - HOLD/NEUTRAL: bg rgba(255,255,255,0.06), color #848e9c
   Signal card has 3px left-accent-border matching direction color.

5. CONFIDENCE METER
   Horizontal bar, 6px height, radius 3px.
   bg: rgba(255,255,255,0.06)
   fill: gradient from #f6465d (0%) → #F7931A (50%) → #00c076 (100%)
   Label above: "Confidence" Inter 10px muted
   Value right: "73%" JetBrains Mono 12px

6. HYPOTHESIS STAGE BADGE
   - observation: bg rgba(56,97,251,0.12), color #3861fb, border rgba(56,97,251,0.2), text "OBS"
   - candidate:   bg rgba(247,147,26,0.12), color #F7931A, text "CAND"
   - active:      bg rgba(0,192,118,0.12), color #00c076, text "ACTIVE"
   - rejected:    bg rgba(246,70,93,0.12), color #f6465d, text "REJECT"

7. CHART CONTAINER
   bg: transparent (card provides bg)
   Grid lines: rgba(255,255,255,0.04)
   Axis text: #5e6673, Inter 10px
   Tooltip: bg #161a22, border rgba(255,255,255,0.1), radius 8px, shadow md

8. TABLE (pro-table)
   Header: Inter 10px uppercase #5e6673, bg rgba(0,0,0,0.25), sticky top
   Row: Inter 12px #b7bdc6, border-bottom rgba(255,255,255,0.05)
   Row hover: bg rgba(247,147,26,0.03)
   Ticker cells: JetBrains Mono 12px weight 700 #eaecef

9. STATUS PILL
   bg: rgba(255,255,255,0.04), border rgba(255,255,255,0.07), radius 20px, padding 4px 10px
   Dot: 6px circle. Online=#00c076 (pulse glow), Offline=#f6465d, Connecting=#F7931A (pulse)

10. EMPTY STATE
    Center-aligned, padding 32px.
    Icon: 40px emoji or simple geometric shape, opacity 0.7
    Title: Inter 16px weight 600 #eaecef
    Desc: Inter 12px #5e6673, max-width 320px

ICONS: Use Lucide icon set (stroke, 18×18, stroke-width 1.5). No filled icons except
for the sidebar nav (20×20). No emojis in production UI except empty states.

MOTION:
  Duration: 220ms standard, 400ms slow (sidebar), 120ms fast
  Easing: cubic-bezier(0.16, 1, 0.3, 1)
  Card hover: translateY(-2px)
  Value changes: counter animation 650ms ease-in-out-cubic
  View transitions: opacity 0→1 + translateY(8px→0), 350ms

DO NOT:
  - Use white backgrounds
  - Use bright colors outside the palette above
  - Show placeholder/lorem text
  - Add decorative illustrations or icons as main content
  - Use gradients on text (except logo)
  - Stack more than 3 levels of nesting in layout
  - Use border-radius > 18px
```

---

## Palette Quick Reference

```
#050508  background
#08090d  page-bg
#0c0e14  sidebar
#111318  card
#161a22  card-2 / input
#1c212b  hover

#F7931A  accent / orange
#00c076  long / green
#f6465d  short / red
#3861fb  blue / info
#8b5cf6  purple

#eaecef  text-1
#b7bdc6  text-2
#848e9c  text-3
#5e6673  muted
```

---

## Component States Checklist

Для каждого компонента Stitch должен показать:
- [ ] Default / populated
- [ ] Loading (shimmer skeleton)
- [ ] Empty state (no data)
- [ ] Error state (API failed)
- [ ] Hover / interactive
- [ ] Positive value (green)
- [ ] Negative value (red)
