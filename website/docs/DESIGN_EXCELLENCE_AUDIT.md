# Design Excellence Audit — Quant landing

**Date:** 2026-07-27
**Build audited:** `merge-learning-nik`, working tree at `~/Downloads/Trading-Bot-merge-learning-nik`
**Method:** live DOM measurement + screenshots via Playwright at 1920 / 1440 / 1024 / 390 / 320, plus a reduced-motion pass.
**Scope:** `website/` only. No file under `bot/`, `knowledge/`, `tests/`, `infra/` or `scripts/` (trading core) was read for modification or touched.

> **Repo note.** `CLAUDE.md` names `~/Documents/GitHub/Trading-Bot/` as canonical and calls `~/Downloads/Trading-Bot-*` stale. For the website that is now inverted: the Documents clone is three commits old (amber accent, Three.js hero, no header, none of the sections below), while this tree holds ~125 changed/untracked files including every section under audit. The audit and all edits are against this tree, as instructed. **This work is uncommitted and lives outside the canonical repo — it needs to be committed and pushed.**

---

## Verdict in one line

The page is structurally sound, honest, and already carries a real design system — a single `Section` shell, a single `Surface` card primitive, one `Reveal` mechanism, contrast-checked monochrome tokens. What it lacks is **progression**: every section is paced the same, painted the same, and revealed the same, so a page with genuinely good bones reads as a well-typeset document rather than a product.

The owner's four complaints are all reproducible, and three of them are one root cause each.

---

## A. Confirmed bugs

### A1 — Sticky header overlaps content · **critical**

Reproducible at every desktop width. Scroll to ≈6300px (end of the Brokers heading block): the section lead runs *underneath* the fixed header pill and is fully legible through it, colliding with the nav items.

Measured:
- Header is `position: fixed`, total height **78px** (`pt-4` + a 62px glass pill).
- `.glass-premium` background is `rgba(12,12,14,0.62)` with `blur(24px)`. At 62% over pure black, white body copy underneath still transmits at roughly a third of its luminance — enough to read, and enough to visually collide with the nav labels sitting on top of it.
- There is **no scrim** above or behind the header, so content approaches it at full opacity and simply slides under.

Second, related defect: `NAV_OFFSET = 80` (`motion/scroll-driver.ts:54`) against a 78px header leaves **2px** of clearance. Anchor navigation technically clears the pill but lands section eyebrows flush against its bottom edge, which is what reads as "labels appear behind the nav" in screenshots.

Third: sections carry no `scroll-margin-top`. Every in-page jump currently depends on the JS interceptor in `lenis-provider.tsx`; if JS fails, or focus moves to an anchor by keyboard, the native jump lands 78px too high.

### A2 — Orphan card in "Как работает" · **high**

`how-it-works-section.tsx:114` renders seven pipeline stages into `lg:grid-cols-3`. Seven over three leaves card 7 (`ПАМЯТЬ`) alone in the final row with two empty cells beside it. At 1440 this is a visibly broken-looking grid — the section's own source comment acknowledges the one-card last row but treats it as a reveal-ordering question rather than a composition one.

### A3 — Collapsed spacing inside "Как работает" · **high**

Three vertical joints in that section are effectively zero:
- the loop paragraph sits directly beneath the orphan card's bottom edge;
- the `ГРАНИЦЫ УВЕРЕННОСТИ` eyebrow nearly touches the paragraph above it;
- the `НА ЧЁМ ЭТО СТОИТ` eyebrow does the same.

The section uses one flat `gap-14` for joints of four different semantic weights, so a new movement gets the same air as a sibling paragraph.

---

## B. Rhythm — where sections feel glued

Measured section padding at 1434px viewport (tokens resolve to major = 201.6px, default = 144px, tight = 96px):

| Section | Rhythm | Pad Y | Divider |
|---|---|---|---|
| hero | — | 128 / 80 | — |
| audience | major | 201.6 | ✅ |
| how-it-works | major | 201.6 | ✅ |
| dashboard | major | 201.6 | ✅ |
| **telegram** | **tight** | **96** | **❌** |
| **brokers** | **tight** | **96** | **❌** |
| strategies | major | 201.6 | ✅ |
| safety | default | 144 | ✅ |
| pricing | major | 201.6 | ✅ |
| faq | default | 144 | ✅ |
| access | major | 201.6 | ✅ |

Two problems fall straight out of this table:

**B1 — Telegram and Brokers are the only sections with neither air nor a divider.** They are also adjacent. The result is a ~500px stretch in the middle of the page where three distinct arguments (terminal → Telegram → brokers) run together with no boundary of any kind. This is precisely the "glued together" the owner flagged, and it is the *only* place on the page where it happens.

**B2 — `major` is the default, so it signals nothing.** Six of eleven sections are major. A three-step scale where the loudest step is the most common step is a flat scale with extra tokens. Nothing in the vertical rhythm tells the eye that the hero→audience transition and the brokers→strategies transition are different kinds of joint.

---

## C. Where blocks look flat

**C1 — The depth system is built but never used.** `ui/section.tsx` accepts a `glow` prop and renders it into a correctly-clipped, `aria-hidden` layer that cannot break a pin. **No section on the page passes one.** The page is therefore a uniform `#030303` from y=0 to y=13637, with the sole exception of the hero visual's own small radial pool. Every card is the same value on the same value.

**C2 — Cards share one elevation.** `Surface` offers `flat` / `raised` / `glass` / `featured`, but the landing uses `flat` almost everywhere, so 30+ cards sit at an identical z-height. Hover works well (`card-premium` is genuinely good — border, background step, 6px lift, real focus-within handling, touch-safe) but at rest there is no hierarchy between a primary card and a supporting one.

**C3 — Section boundaries are hairlines only.** A 1px `rgba(255,255,255,0.1)` border is the entire transition vocabulary between sections.

## D. Where motion is missing

**D1 — The hero is completely static.** `hero-visual.tsx` is pure server-rendered SVG: three rings, four ticks, a dashed exit vector, one node. Nothing moves, ever. This is the first screen and the owner's primary complaint, and it is the largest single gap between the current page and the intended feeling.

**D2 — One reveal for everything.** `Reveal` is the only motion mechanism on the page (a deliberate and correct decision — it is IntersectionObserver-based and cannot desync from Lenis). But every block gets the same 28px rise, same 0.7s, same 80ms stagger. Section headers, cards, tables and stat rows all enter identically, so scroll produces no sense of pacing.

**D3 — No connective motion in the pipeline.** Seven stages are presented as seven independent cards. Nothing communicates that they are a *sequence* — no trace, no direction, no progression.

**D4 — The Telegram confidence bars don't animate.** Ten bars render at their final state. A staged fill on first reveal is the single highest-value micro-interaction available in that section and it is absent.

## E. What is already good (do not regress)

Worth stating plainly, because a "polish pass" is a good way to break working things:

- **Scroll integrity is solved.** `scroll-driver.ts` fixes the backward-jump bug properly (`history.scrollRestoration = "manual"` + hash-on-load + resize resync), documents the reproduction, and removed the GSAP↔Lenis bridge along with the pinned track that caused it. **No horizontal page scroll at any width, 320 → 1920** (verified: `scrollWidth === clientWidth`). Do not reintroduce ScrollTrigger.
- **Reduced motion is handled correctly**, including the subtle trap: `Reveal` never branches its *markup* on the preference (only the duration), plus a `[data-reveal]` force-reset in `globals.css` as a JS-failure safety net. Any new motion must follow the same rule.
- **Honesty holds.** No win rate, profit factor, sample size, equity curve or return figure anywhere. Hero tiles are *configured limits* (5% / 2% / 0.20), broker statuses are derived from real adapter state, the terminal is captioned as demonstrational, and the Telegram card says "ничего не ушло брокеру" explicitly. Nothing in this pass may weaken that.
- **Telegram buttons already work** (local `useState`, `aria-live`, reset affordance) and **broker statuses are already differentiated** (active / beta / planned from real code refs). Phases 8 and 9 are largely done; they need polish, not rebuilding.
- **Colour is already correct.** Strict monochrome, no amber, every text token contrast-checked with the ratio recorded beside it, semantic green/red desaturated to read as data.
- **Console is clean.** Only two expected dev-only 404s (`_vercel/insights`, `_vercel/speed-insights`).
- **Mobile has no page-level overflow.** The 31 elements measuring wider than the viewport at 390 are all inside the strategy table's intended `overflow-x-auto` scroller.

---

## F. Work plan

Ordered by value, and by the owner's stated priorities.

| # | Change | Phase | Fixes |
|---|---|---|---|
| 1 | Top scrim + stronger header glass; `NAV_OFFSET` 80 → 104; `scroll-margin-top` on sections | 11 | A1 |
| 2 | Section depth: wire the unused `glow` slot on anchor sections | 10 | C1, C3 |
| 3 | Hero aperture motion: breathing rings, travelling signal, sweep — CSS-only | 1 | D1 |
| 4 | Rhythm rebalance: give telegram/brokers air + dividers; demote over-used `major` | 4 | B1, B2 |
| 5 | Pipeline: fix orphan card, add signal trace, fix collapsed joints | 5, 6 | A2, A3, D3 |
| 6 | Motion vocabulary: distinct reveal treatments; animated confidence bars | 2, 8 | D2, D4 |

### Constraints carried into implementation

- No new scroll hijacking, no GSAP ScrollTrigger, no pinned sections.
- No fake metrics, no result claims, no restored WR/PF/sample-size figures.
- No video hero, no crypto/neon, no purple, no orange.
- Every new animation must be reduced-motion safe and must not branch server markup on the preference.
- No layout shift from any added motion.
- Nothing outside `website/`.
