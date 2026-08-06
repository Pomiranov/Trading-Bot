# QuantFlow Operational Dashboard — UI/UX Audit

**Date:** 2026‑07‑29 · **Branch:** `quant-site-approved-reference-redesign` · **HEAD:** `a422cab`
**Object:** the operational dashboard's interface layer only — `bot/ui/templates/**`,
`bot/ui/static/css/**`, `bot/ui/static/app/**`.
**Mode:** read-only. No file was modified; no defect was fixed.

> **This audits a different build than `DASHBOARD_APPROVED_REFERENCE_AUDIT.md`.** That audit ran
> against `80ec121`. Three commits have landed since — `935e9ba` (data correctness and read-only
> contracts), `c0d72b5` (authentication, CSRF, rendering), `a422cab` (`/api/v2` contract layer and an
> app factory without side effects) — and they replaced the interface wholesale. `app.js`,
> `style.css`, `design-system.css`, `core/*` and `views/*` are deleted. Findings below supersede
> §6–§24 of the earlier document for the UI layer.

---

## 0. Verdict

The interface was rebuilt against the earlier audit and the rebuild is largely correct. The brand
alignment problem is **solved**: the palette is the site's, the typeface is the site's, self-hosted,
and there is a working lint gate that fails the build on regression. The component layer now has the
things a terminal needs and did not have — a real router, table density modes, per-cell staleness,
confidence bound to sample size, chart text alternatives, an announcer.

Two things stop it from being shippable as an interface today. One is a **cascade collision that
renders the password field 26 pixels wide on the only screen an operator can reach** — reproducible
at every viewport. The other is that **the token copy has already drifted from the site**, which the
project's own linter reports and which proves the copy-don't-import decision needs an owner and a
cadence, not just a checker.

| Dimension | Was (`80ec121`) | Now (`a422cab`) | Note |
|---|---:|---:|---|
| Brand alignment | 2 / 10 | **8 / 10** | Site palette and faces adopted; 2 tokens already drifted |
| Visual consistency | 3 / 10 | **9 / 10** | 6 type roles, 7 radii, 3 shadows, 0 raw hex — lint-enforced |
| Information architecture | 3 / 10 | **8 / 10** | Real routing, `h1`, landmarks, 12 screens; game removed from the rail |
| Interaction design | — | **6 / 10** | Strong primitives; the sign-in form is broken |
| Accessibility | 1 / 10 | **7 / 10** | Captions, `scope`, `aria-sort`, chart alternatives, announcer, `forced-colors`; unverified beyond sign-in |
| Motion | 2 / 10 | **9 / 10** | 0 infinite animations; one bounded shimmer; reduced-motion honoured |
| Responsive | 3 / 10 | **7 / 10** | 7 breakpoints incl. landscape and print; only sign-in verified at runtime |
| Content / i18n | 2 / 10 | **8 / 10** | ru + en, ~202 keys, typed empty-reason codes |

---

## 1. Evidence basis, and its one hard limit

**Runtime-verified.** The dashboard was launched and measured at 1440×900 and 390×844. Every value
in §2 and §4 was read from the live DOM via `getComputedStyle` and `getBoundingClientRect`.

**Not runtime-verified.** `GET /` now redirects to `/login`, and signing in requires entering a
password — which this audit will not do. So **only the sign-in screen could be rendered.** The app
shell, all 12 views, the tables, the charts and every data state are audited **from source**, and are
marked `source-only` where a claim would otherwise imply a rendered observation.

That limit is worth fixing for the next pass: a seeded read-only demo session, or
`QF_DASHBOARD_READ_ONLY=1` combined with a throwaway operator whose password the reviewer sets, would
make the whole surface auditable without ever handing a credential to a tool.

Also verified: `node bot/ui/static/check-dashboard-tokens.mjs` was executed (read-only) and its
output is reproduced verbatim in §3.

---

## 2. The sign-in screen — the only screen an operator sees before authenticating

### 2.1 What is right

| Property | Measured value |
|---|---|
| Document | `lang="ru"`, `title="Вход · QuantFlow"`, `<main>`, `<form>`, exactly one `<h1>` («Терминал оператора») |
| DOM size | **47 nodes** |
| External requests | **zero** — no CDN, no Google Fonts, fonts self-hosted and preloaded |
| Inline event handlers | **none** |
| Fonts | `Geist, ui-sans-serif, system-ui, -apple-system, sans-serif`, resolved |
| Ground | `rgb(3,3,3)` = `--qf-bg` `#030303` — the site's exact value |
| Primary CTA | `#ffffff` fill, `#0a0a0a` text → **20.4:1** (was `#fff` on `#F7931A` = 2.30:1) |
| Field labels | 13px, `rgba(255,255,255,0.56)` → 6.5:1, both `<label for>`-associated |
| Autocomplete | `username` / `current-password` — correct, so password managers work |
| Error region | `aria-live="assertive"` on `#qf-login-error` |
| Touch targets | inputs and submit **36px** at desktop, **44px** at 390px wide |
| Horizontal scroll | none at 390px; card 342px with a 24px gutter |
| Reduced motion | `prefers-reduced-motion` rule present and reachable |
| CSRF | session-bound token in a readable `qf_csrf` cookie, echoed as `X-CSRF-Token` (`login.html:132-133`, `session_auth.py:42-43`) — a header-based scheme, not a hidden field, so a naïve "is there a `csrf` input?" check gives a false negative |
| Copy | «Все действия оператора записываются в журнал аудита.» — states the audit trail up front |

The 13px label is **not** a seventh type size: `app.css:1171` redefines `--qf-caption-size: 13px`
inside `@media (max-width: 767px)`. A token override for mobile density is correct, and the linter
correctly does not flag it.

### 2.2 F‑UI‑01 — the password field renders 26 pixels wide · **Blocker**

**Measured, 1440×900 desktop:**

| Element | Rendered width | Intended |
|---|---:|---:|
| `input#qf-username` | 334px | 334px |
| `input#qf-password` | **26px** | ~294px |
| `button#qf-password-toggle` | **334px** | 36px |

Identical at 390×844 (input 26px, toggle 276px). The 26px is exactly the input's own
`padding: 0 12px` plus its 1px borders — i.e. the field has been squeezed to zero content width.

**Mechanism — a cascade collision between two rules of equal specificity.**

```css
/* bot/ui/static/css/app.css:872-876 */
.qf-input-group .qf-btn {
  flex: 0 0 auto;
  width: var(--qf-control-lg);      /* 36px — the intent */
  border-color: var(--qf-border-strong);
}

/* bot/ui/static/css/app.css:1082-1085 — LATER in the file */
.qf-signin-card .qf-btn {
  min-height: var(--qf-control-lg);
  width: 100%;                      /* wins: same specificity (0,2,0), declared later */
}
```

Both selectors are two classes, so specificity ties and source order decides. `width: 100%` resolves
the toggle to the full 334px group width, `flex: 0 0 auto` forbids it from shrinking, and the input —
`flex: 1 1 auto; min-width: 0` at `app.css:870` — absorbs the entire overflow and collapses.

**User impact.** The operator cannot see what they are typing, and the element that *looks* like the
password field is the reveal-password button. On a screen with no alternative path. Combined with the
fact that no default password exists (`passwords.py:138-146`), a first-time operator meets a form
they cannot reasonably complete.

**Why it escaped.** The linter has no layout rule — it checks tokens, not rendered geometry. There is
no visual-regression coverage, and the sign-in screen is behind no test. A single 400px-wide DOM
assertion would have caught it.

**Fix direction** (not applied): scope the full-width rule to the submit button only —
`.qf-signin-card .qf-btn[type="submit"]` — or add `width: var(--qf-control-lg)` back inside
`.qf-signin-card .qf-input-group .qf-btn`. Prefer the former: a blanket
`.qf-signin-card .qf-btn { width: 100% }` will collide with the next button added to that card too.

### 2.3 F‑UI‑02 — the cold-blue sign-in geometry reads as a stray line · Low

At 1440×900 a horizontal `--qf-signal-stroke` line (`rgba(124,200,255,0.24)`) crosses the viewport
behind the card and extends well past its edges on both sides. It is within doctrine — cold blue as
light, 0.24 alpha, decorative stroke, sign-in surface only, exactly as `tokens.css:162-166` permits —
but composed as an unterminated rule it reads as a rendering artefact rather than as intent. It also
sits at the card's vertical midpoint, so it appears to pass *through* the password row.

**Recommendation:** either terminate it within the card's optical width, or drop its alpha below the
point where it registers as an edge. This is a composition note, not a doctrine violation.

### 2.4 F‑UI‑03 — no `env(safe-area-inset-*)` on the sign-in surface · Low

`getComputedStyle(document.body).paddingBottom` is `0px` at 390×844. The card is vertically centred
so it clears the notch today, but a keyboard-open viewport on iOS will push the submit button under
the home indicator. `viewport-fit=cover` is already set in `dashboard.html:5`; the inset variables
are not used.

### 2.5 F‑UI‑04 — primary CTA text is caption-sized · Low

The submit button computes to `font-size: 12px` on a 36px control. That is `--qf-caption-size` — the
role reserved for table cells and metadata. A single primary action on a sign-in card is the one
place the interface can afford `--qf-body-size` (14px). Contrast is fine; hierarchy is not.

---

## 3. Design-token conformance

`bot/ui/static/check-dashboard-tokens.mjs` (379 lines) is a real gate and it runs. Verbatim output:

```
✓ raw-hex-outside-tokens         0/0     ✓ inner-html                 0/0
✓ raw-rgba-outside-tokens        0/0     ✓ inline-event-handler       0/0
✓ orange-accent                  0/0     ✓ arbitrary-font-size        0/0
✓ purple                         0/0     ✓ tiny-text                  0/0
✓ saturated-blue-cyan-as-ink     0/0     ✓ arbitrary-radius           0/0
✓ orbitron                       0/0     ✓ arbitrary-shadow           0/0
✓ google-fonts-runtime           0/0     ✓ radii                      7/7
✓ cdn-script                     0/0     ✓ shadows                    3/3
✓ infinite-animation             0/0     ✓ type-roles                 6/6

✗ token-provenance: 2 value(s) drifted from the site
    --qf-accent-hover = rgba(255, 255, 255, 0.88)  but site --color-accent-hover = rgba(255, 255, 255, 0.94)
    --qf-paper        = #f4f2ec                    but site --color-paper        = #ebe8e0
```

**Every quantitative defect from the earlier audit is closed.** For the record: 36 distinct hex
literals → 0 outside the token file; 126 rgba → 0; 20 rendered font sizes → 6 roles; 11 radii → 7;
34 shadows → 3; 13 infinite animations → 0; 31 `innerHTML` sinks → 0; two CDN scripts and three
Google Fonts requests → none.

### 3.1 F‑UI‑05 — the token copy has already drifted · High

`tokens.css:1-11` documents the decision deliberately: the dashboard holds a **copy** of the site's
tokens rather than importing them, so "a marketing deploy [cannot] change an operator's screen", with
the linter as the drift detector. That reasoning is sound — an operator's terminal should not
inherit a release cadence it does not control.

The prediction has now come true within days: the site moved `--color-paper` to `#ebe8e0` and
`--color-accent-hover` to `rgba(255,255,255,0.94)`, and the dashboard still carries the old values.
The detector fired, exactly as designed. What is missing is the other half of the mechanism — **who
reconciles a drift, and when.** A red check with no owner becomes a permanently red check, and a
permanently red check is a disabled check.

Note that both drifted values are consequential rather than cosmetic: `--qf-paper` is the live-mode
inversion, i.e. the strongest safety signal in the interface, and `--qf-accent-hover` is the hover
state of every primary action.

**Recommendation:** make the reconciliation explicit — a named owner, a rule that the dashboard
adopts the site's value unless there is a written terminal-specific reason (as already exists for
type sizes and durations), and a short note in `tokens.css` for each deliberate divergence so the
linter can be taught to allow it.

---

## 4. Information architecture and navigation

`source-only` except where noted.

**Screens** — 12 client routes, all server-answered so a deep link survives a reload
(`views.py:61-63`, `router.js`): `overview, portfolio, positions, trades, signals, strategies,
backtest, analytics, risk, status, events, settings`.

Against the earlier audit's §12 target: **Positions, Strategies, Risk, System Health (`/status`) and
Event Log (`/events`) now exist.** Quant Hunter is gone from the operational rail and is a separate
document (`views.py:115`), so its 67 KB no longer loads with the terminal. `Orders` is correctly
absent — no order entity exists.

**Routing is real.** `pushState`, `popstate`, `document.title` set per route with a `· QuantFlow`
suffix, and the `<h1>` updated alongside it (`router.js:92-116`, `dashboard.html:76`). The earlier
finding — no bookmarkable view, no restorable state, no tab title — is closed. `health` is
deliberately kept off the client route list so `GET /health` stays a liveness probe and cannot
collide with the System Health *view* at `/status` (`views.py:57-59`).

**The three-tier status hierarchy from §13.2 of the earlier audit is implemented structurally**
(`dashboard.html:93-103`): a persistent, non-dismissible environment band with
`role="status" aria-live="polite"`; a fault region documented as zero-height when healthy — "there is
no green 'all clear' band"; then the view. Whether the band actually inverts to paper in LIVE could
not be rendered.

### 4.1 F‑UI‑06 — the sidebar collapse control is label-only, with no icon · Low

`dashboard.html:59-64` renders the toggle as `‹` plus the text «Свернуть» inside
`.qf-sidebar-footer-text`. In the 64px rail state that text is presumably hidden, leaving a bare
`‹` glyph as the only affordance — a typographic character doing an icon's job, at whatever weight
Geist gives it. The same applies to the topbar's `☰` (`dashboard.html:72`). Every other icon in the
document is a proper inline SVG in `currentColor`; these two are text glyphs. `aria-label` and
`aria-expanded` are correct, so this is a visual-consistency point, not an accessibility one.

### 4.2 F‑UI‑07 — «Выйти» carries both a visible label and a duplicate `sr-only` label · Low

`dashboard.html:55-58`: a visible «Выйти» plus `<span class="qf-sr-only">Выйти из системы</span>`.
A screen reader announces the concatenation — "Выйти Выйти из системы". The `sr-only` expansion is
only useful when the visible text is *insufficient*; here it is redundant. Same pattern on the
sidebar toggle (`:62-63`), where visible «Свернуть» is followed by
`sr-only` «Свернуть панель навигации» — that one is arguably justified, since «Свернуть» alone is
ambiguous about *what* collapses. Pick one convention and apply it consistently.

---

## 5. Component layer

`source-only`. The primitives that the earlier audit specified in §29 are present, and in several
places they go further than specified.

| Primitive | Where | Note |
|---|---|---|
| `panel`, `chartPanel` | `ui.js:24,594` | `chartPanel` takes `summary`, `tableRows`, `tableColumns` — the text alternative is part of the constructor, not an afterthought |
| `freshnessMeta(sliceMeta)` | `ui.js:50` | Per-slice freshness rather than one global timestamp — closes the earlier §21 finding that a partial sync was stamped fresh |
| `sampleMeta(n)`, `confidenceValue(value, n, {mature})` | `ui.js:74,207` | Confidence cannot be constructed without a sample size, and immaturity is an explicit flag |
| `staleMark(ageSeconds, absolute)` | `ui.js:220` | Relative age plus the absolute on hover — the per-**cell** staleness the earlier audit required |
| `stateFor(snapshot, {onRetry, skeleton, emptyExtra})` | `ui.js:237` | One state machine for loading / empty / partial / stale / error |
| `errorState`, `partialNote(missing)` | `ui.js:316,356` | `partialNote` names *which* fields are missing |
| `environmentChip`, `chip`, `status({state,label,shape})` | `ui.js:166,178,188` | `shape` is a first-class parameter — status is not carried by hue alone |
| `limitMetric({limit,current})` | `ui.js:142` | A value against its limit, which is what a risk figure means |
| `confirmDialog`, `actionButton({permitted, reason, danger})` | `ui.js:435,574` | A control renders its own permission state and *why* it is denied |
| `toasts`, `mountAnnouncer` | `ui.js:409,412` | `window.QFToast` was previously referenced twice and never defined |

**Tables** (`table.js`) implement everything the earlier §18 asked for: a **mandatory** `caption` as
the accessible name; `scope="col"`; `aria-sort` with `role="columnheader"` and `tabindex="0"` on
sortable headers; three density modes (`compact` / `comfortable` / `monitoring`) with the preference
**persisted per table** via `storageKey`; a selected row; and server-side sorting where the dataset
demands it. `localStorage` access is guarded for quota and private mode (`table.js:82`).

**Charts** (`charts.js`) are the strongest part of the rebuild. `role="img"` with `aria-label` on
every canvas; a keyboard-navigable series — `tabindex="0"` plus «стрелками влево и вправо по точкам»
in the accessible name; and a `role="status" aria-live="polite"` readout so a keyboard user *hears*
the value change as they walk the series (`charts.js:92-100`). The file's own stated principle is the
right one: "a chart whose numbers are only obtainable by eyeballing a line against an axis is a
picture, not an instrument" (`app.css:879-881`).

### 5.1 F‑UI‑08 — the chart readout is `aria-live="polite"` on an arrow-key interaction · Medium

A polite live region is queued behind whatever the screen reader is currently saying. For an
interaction where the user is *deliberately stepping* through points, each step should preempt the
last, or a fast traversal produces a backlog of stale values announced after the user has moved on.
`aria-live="assertive"` is usually wrong for anything ambient — but this is a direct response to a
keypress, which is exactly the case where it is right. Consider `assertive` here, or drive the
announcement through the `#qf-announcer` element with a debounce.

### 5.2 F‑UI‑09 — no visible focus style asserted for chart data points · Medium

`app.css:913` styles `.qf-chart[tabindex]:focus-visible`, so the chart *container* shows a ring. Once
focus is inside and the user arrows through points, nothing in the CSS indicates *which* point is
current — the readout carries it textually, and a sighted keyboard user gets no positional cue.
A crosshair or point marker bound to the focused index would close this. WCAG 2.4.7 arguably applies
to the focused sub-component, not only to the container.

---

## 6. Accessibility

Verified at runtime on sign-in; `source-only` elsewhere.

| Criterion | Status | Evidence |
|---|---|---|
| 1.3.1 Info & Relationships | **Pass** (was fail) | One `<h1>` per view, updated by the router; `<aside>`, `<nav>`, `<header>`, `<main>`; table `caption` + `scope="col"` |
| 2.4.1 Bypass Blocks | **Pass** (was absent) | `.qf-skip-link` first in tab order (`dashboard.html:35`) |
| 4.1.3 Status Messages | **Pass** (was total fail) | `#qf-band` polite, `#qf-faults`, `#qf-announcer`, `#qf-login-error` assertive, chart readout |
| 1.4.3 Contrast | **Pass** on measured surfaces | Text ramp 20.4 / 10.4 / 6.5 / 4.9:1; CTA 20.4:1; `#5e6673` deleted |
| 1.4.11 Non-text Contrast | **Pass** | `--qf-border-strong` at .35 = 3:1, mandatory on interactive edges (`tokens.css:114-119`) |
| 1.4.1 Use of Colour | **Pass by design** | `status()` takes `shape`; every state carries a word |
| 2.5.8 Target Size | **Pass** | 36px desktop, 44px at ≤767px via token remap (`app.css:1172-1174`) |
| 2.2.2 Pause/Stop/Hide | **Pass** (was 13 infinite animations) | Linter enforces zero; one bounded 3-cycle shimmer |
| 2.3.3 / reduced motion | **Pass** | `base.css:309`; verified reachable at runtime |
| 1.4.12 / high contrast | **Pass** (was absent) | `forced-colors` maps the whole palette to system keywords (`tokens.css:274-299`); `prefers-contrast: more` raises the ramp to 7:1+ (`:307-315`) |
| 1.1.1 Non-text Content | **Pass** (was fail) | Every chart ships a summary and a data-table alternative |
| 2.1.1 Keyboard | **Likely pass, unverified** | Sortable headers focusable; charts arrow-navigable; table selected state exists |
| 3.3.1 Error Identification | **Likely pass, unverified** | `.qf-field-error` + assertive region |
| 2.1.4 Character Key Shortcuts | **Pass** (was fail) | Shortcuts are toggleable and persisted — `localStorage['qf.shortcuts']` (`router.js:148-157`); the old handler hijacked ⌘R with no modifier guard and no opt-out |

**F‑UI‑10 · Medium — the sign-in screen has no skip link and no landmark for the form's purpose.**
Not a violation (there is nothing to bypass), but the login document does not reuse the shell's
`.qf-skip-link`, so the two documents have different tab-order conventions. Harmless today; worth
noting because a second pre-auth screen (password reset, 2FA) would inherit the inconsistency.

**F‑UI‑11 · Medium — `forced-colors` maps `--qf-success`, `--qf-danger` and `--qf-warning` all to
`CanvasText`** (`tokens.css:290-292`). That is the correct instinct — hand the palette to the OS —
but it means profit, loss and warning become *the same colour* in high-contrast mode. The rebuild's
own doctrine saves it: `status()` carries a shape and every state carries a word, so meaning
survives. Worth an explicit test rather than an assumption, because it is precisely the mode where a
regression would be invisible to everyone reviewing in a normal palette.

---

## 7. Motion

`--qf-ease` is `cubic-bezier(0.16, 1, 0.3, 1)` — byte-identical to the site's `--ease-out-expo`.
Durations diverge deliberately and the reason is documented in place: 220ms base rather than the
site's 300ms, because "a dense grid at the site's 300ms feels sluggish under repeated interaction"
(`tokens.css:244-252`). `--qf-ease-bounce` is deleted, with the correct rationale — an overshoot on a
numeric readout makes a value appear to exceed itself before settling.

Zero infinite animations, lint-enforced. The single loop in the system is the skeleton shimmer,
bounded to `--qf-skeleton-cycles: 3` then static: "a shimmer that runs for 30 s is a hang rendered as
a feature" (`tokens.css:253-255`).

Nothing from the site's scroll-driven layer was ported — no reveal, no Lenis, no orbits, no magnetic
cursor, no ambient glow. This was the earlier audit's clearest prohibition and it was honoured.

---

## 8. Responsive

Seven breakpoints (`app.css`): 1359, 1279, 1023, 767, a landscape rule at `max-height: 480px`, a
`min-width: 1680px` step, and `@media print`. The landscape and print rules are both beyond what was
asked for; the landscape rule matters specifically for a phone held sideways to watch a position.

Runtime-verified at 390×844: no horizontal scroll, card 342px with a 24px gutter, controls remapped
to the 44px touch target, caption size raised to 13px.

**F‑UI‑12 · Medium — the responsive behaviour of the app shell is unverified.** The sidebar's
240px → 64px rail → overlay progression, the tables' `qf-table--responsive` mode, and the chart
panels' fixed heights (`260px`, `160px`, `200px` — `screens.js:692-695`) at 390px wide are all
source-only. Fixed pixel chart heights on a 390px viewport are the classic place this breaks: a
260px-tall chart in a 342px-wide card is nearly square, which for a time series is close to
unreadable. Needs measurement once a review session is possible.

---

## 9. Content, formatting and i18n

The dashboard is now **bilingual** — `ru` and `en` catalogues, ~202 keys, in `app/i18n.js:12,260,275`.
The earlier finding (113 Cyrillic vs 224 Latin-only strings, zero i18n layer, an accidental English
nav over Russian content) is closed.

`i18n.js:297-298` exposes `emptyReasonText(code)` — empty states are driven by a **typed code from
the data contract**, not by a string chosen at the render site. That is the mechanism the earlier
§21 required: it makes «Сделок пока нет», «Нет сделок за выбранный период», «Не удалось загрузить»
and «База данных недоступна» structurally impossible to collapse into one «Нет данных».

`format.js` (297 lines) has **`format.test.mjs` beside it (247 lines)** — the only tested module in
the interface, and the right one to test first, since the earlier audit found the same quantity
formatted differently in different views.

**F‑UI‑13 · Low — three panel titles are hardcoded Russian, bypassing i18n.**
`screens.js:451` `'История риск-событий'`, `:563` `'Счета'`, `:564` `'Показатели'`, `:565`
`'Распределение'`, `:566` `'По инструментам'` are string literals where every sibling uses `t(...)`.
In an `en` session those panels render Russian. Small, mechanical, and exactly the kind of thing that
accumulates — a lint rule for bare Cyrillic literals in `app/**` would prevent it permanently.

---

## 10. Findings summary

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| **F‑UI‑01** | Password input renders 26px wide; toggle takes the full 334px. Cascade collision, equal specificity, later rule wins | **Blocker** | `app.css:872-876` vs `:1082-1085`; measured at 1440×900 and 390×844 |
| **F‑UI‑05** | Token copy already drifted from the site on `--qf-paper` and `--qf-accent-hover`; detector fires, no owner defined | **High** | linter output; `tokens.css:133,157` vs `website/src/styles/tokens/color.css:59,95` |
| F‑UI‑08 | Chart readout is `aria-live="polite"` on a keypress-driven interaction | Medium | `charts.js:92-94` |
| F‑UI‑09 | No visible focus indicator for the focused chart data point | Medium | `app.css:913` |
| F‑UI‑10 | Sign-in document has a different tab-order convention from the shell | Medium | `login.html` vs `dashboard.html:35` |
| F‑UI‑11 | `forced-colors` collapses success / danger / warning to one colour | Medium | `tokens.css:290-292` |
| F‑UI‑12 | App-shell responsive behaviour unverified; fixed chart heights suspect at 390px | Medium | `screens.js:692-695` |
| F‑UI‑02 | Cold-blue sign-in stroke reads as a stray line through the password row | Low | measured at 1440×900 |
| F‑UI‑03 | No `env(safe-area-inset-*)` despite `viewport-fit=cover` | Low | `dashboard.html:5` |
| F‑UI‑04 | Primary CTA text is caption-sized (12px) | Low | measured |
| F‑UI‑06 | Sidebar and topbar toggles use text glyphs where every other icon is SVG | Low | `dashboard.html:59-64,72` |
| F‑UI‑07 | «Выйти» has a redundant duplicate `sr-only` label | Low | `dashboard.html:55-58` |
| F‑UI‑13 | Five panel titles hardcoded in Russian, bypassing i18n | Low | `screens.js:451,563-566` |

---

## 11. Recommended order

1. **F‑UI‑01.** Scope the sign-in full-width rule to `[type="submit"]`. One line. It is the only
   thing between an operator and the product.
2. **Add a layout assertion to the sign-in screen**, then a visual-regression baseline. The token
   linter is excellent and structurally blind to geometry; F‑UI‑01 is proof that a rendered-width
   check is a different class of test, not a redundant one.
3. **F‑UI‑05 — assign the drift owner** and record each deliberate divergence in `tokens.css` so the
   linter can distinguish "intentional" from "stale". A red check nobody owns is a check that will be
   commented out.
4. **Make the authenticated surface reviewable** — a read-only demo session, or documented
   throwaway-operator instructions. Eight of the thirteen findings above are `source-only` and could
   have been either confirmed or dismissed in twenty minutes with a rendered screen. This is the
   single biggest constraint on auditing this build.
5. F‑UI‑08, F‑UI‑09, F‑UI‑11 — the accessibility trio, all in the chart and status layer.
6. F‑UI‑12 — measure the shell at all five viewports; fix chart heights to an aspect ratio below
   768px rather than a pixel value.
7. The five Low findings, as a single housekeeping pass.

## 12. What not to undo

Recorded because it is easy to lose in a later refactor: the copy-don't-import token decision and its
written rationale; the linter and its 18 rules; the mandatory table `caption`; `chartPanel` taking
`summary` and `tableRows` as constructor arguments rather than optional extras; `confidenceValue`
being unable to render without a sample size; per-slice `freshnessMeta` instead of one global
timestamp; the bounded shimmer; the shortcut opt-out; and the `forced-colors` block. Each of these
closes a specific defect from the previous build, and each is the kind of constraint that looks like
overhead to someone who did not see what it replaced.
