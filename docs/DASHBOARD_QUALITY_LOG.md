# Dashboard Quality Program — Log

Living log for the ongoing Dashboard excellence pass (`bot/ui/*`). Updated after every
audit round. Format per page: **Audited → Findings → Fixed → Verified → Backlog**.

## Scope note

The review brief names pages that don't exist as separate views in this codebase today
(Sandbox Trading, Orders, Risk Management, Strategy Center, Notifications). Rather than
inventing new routes/pages to match the brief literally — which would violate "don't add
functionality beyond what's needed" — these are tracked as *features embedded in existing
views*:

| Brief page          | Actual location today                                  |
|----------------------|----------------------------------------------------------|
| Risk Management      | Риск-метрики panel on Dashboard, risk fields on Settings |
| Orders               | Позиции / Открытые позиции tables on Dashboard/Portfolio |
| Notifications         | Toast system (`.toast-root`), Ошибки/Лог panels          |
| Strategy Center       | Strategy selector on Backtest, `rules_engine` on Signals |
| Sandbox Trading       | Paper Trading feed on Dashboard                          |

If a genuinely new page is ever warranted, it needs an explicit decision, not a quality pass.

---

## Dashboard (`view-dashboard`) — Round 1

**Audited:** sidebar/topbar shell, hero + metric cards, keyboard shortcuts, focus handling,
error/degraded-data behavior, table markup, chart color tokens.

### Findings & fixes

1. **Critical — full render failure on partial API outage.**
   `QFRender.dashboard()` began with `if (!overview) return;`. Since `overview`,
   `portfolio`, `stats`, and `equity` are independent `Promise.allSettled` calls
   (`core/sync.js`), a single failing endpoint (`/api/platform/overview`) silently
   blanked the *entire* dashboard — including data from calls that succeeded.
   Reproduced live in dev (no DB configured): `overview` 404s, `stats`/`equity`/`portfolio`
   (market) 200s, yet nothing rendered.
   **Fix:** split the function into independent `if (overview)` / `if (portfolio)` /
   `if (stats)` blocks (`views/render.js`); positions/signals/equity-chart/timestamp now
   render regardless of which specific call failed.
   **Verified:** live-tested against the actual 404 in this dev environment — confirmed
   `Активные позиции` list and the `обновлено HH:MM:SS` timestamp now render even when
   `overview` is unavailable; previously neither appeared.

2. **No visible keyboard-focus indicator anywhere except form inputs.**
   This UI advertises keyboard shortcuts (`1–6` navigate, `R` refresh) in the sidebar
   footer, making visible focus state a real workflow requirement, not decoration.
   Only `:focus` (not `:focus-visible`) existed, and only for `.qf-input`/`.qf-select`.
   **Fix:** added `a/button/[tabindex]:focus-visible` accent ring in `design-system.css`;
   sidebar nav items use `outline-offset: -2px` since `.sidebar` has `overflow: hidden`
   (a positive offset would be clipped).
   **Verified:** live Tab-key test — ring renders correctly and un-clipped on nav items.

3. **No `aria-current` on the active nav item.**
   Active page was communicated by color/glow only — invisible to screen readers.
   **Fix:** `showView()` in `app.js` now toggles `aria-current="page"`; the
   template's hardcoded initial-active Dashboard link got the attribute too (it never
   goes through `showView()` on first paint — caught this in live verification, not
   theoretically).
   **Verified:** confirmed `aria-current` present after reload and after each nav click.

4. **Collapse/mobile-menu toggles had no `aria-expanded`.**
   Both are disclosure controls; state was visual-only.
   **Fix:** `SidebarProvider.apply()` (`core/layout.js`) now syncs
   `aria-expanded` on `#sidebarToggle` and `#mobileMenuBtn`.
   **Verified:** live-checked both attributes reflect state correctly.

5. **Inconsistent table markup.** Dashboard's inline signals table used a bare
   `<table>` while Portfolio/Signals use `.qf-table`. **Fix:** added `.qf-table`
   (not `.pro-table` — that forces `min-width: 900px`, wrong for this 5-column table
   and would've added a pointless horizontal scrollbar; caught before shipping).

6. **Chart color tokens** — audited, found already correct
   (`charts.js` `COLORS.long/short/accent/blue` match the CSS custom properties exactly;
   tooltip bg `#161a22` = `--qf-surface-2` exactly). No change made — noted so this isn't
   re-investigated next round.

### Backlog (not done this round, reasoning noted)

- Bare "Загрузка…" text in some side-panel initial states (positions/brokers/system/log)
  vs. skeleton shimmer used in the hero card — cosmetic inconsistency, low severity since
  it resolves within one fetch cycle in practice. Lower priority than the render-failure fix.
- `setBotStatus('live')` is called unconditionally at the end of `dashboard()` regardless
  of whether `overview` actually loaded — arguably should reflect degraded state. Deferred:
  `setBotStatus` is also driven from SSE connect/disconnect elsewhere, and changing its
  semantics needs a dedicated look at all call sites, not a drive-by edit.
  → tracked as its own item, not silently done.
- Clickable `.ticker-card` / similar div-based "buttons" are not keyboard-operable
  (no `tabindex`, no keydown handler). Real gap, but converting non-semantic clickable
  divs to operable controls touches render.js behavior per call site — deferred to a
  dedicated accessibility pass rather than rushed alongside this round.

---

## Portfolio / Signals / Backtest / Analytics / Settings-Brokers / Mini App

Not started. Queued in the same order as the task backlog.
