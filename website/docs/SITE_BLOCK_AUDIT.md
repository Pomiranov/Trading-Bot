# SITE_BLOCK_AUDIT.md — Quant landing, block-by-block audit against the approved Gemini Stitch reference

**Date:** 2026-07-27
**Repo / branch:** `~/Downloads/Trading-Bot-merge-learning-nik` · `merge-learning-nik` · HEAD `90877d4`
**Scope:** `website/` only. Nothing under `bot/`, `knowledge/`, `tests/`, `infra/` was read for modification or touched.
**Status:** analysis only. No component was changed, no section removed, no production code written.

**Method**
- Full source read of all 13 section components, 11 UI primitives, the motion layer, the token files and the two message catalogues.
- Live DOM measurement against the running dev server (`localhost:3000/ru`) at **1440×900** and **390×844**: computed styles, bounding boxes, scroll widths, section rhythm, rendered type scale, radii census, chromatic-colour census, anchor-landing offsets.
- Approved reference: the Gemini Stitch board *"Quant Full Site Redesign Concept"* (`stitch.withgoogle.com/projects/2281049485843837902`, node `26010fea…`), read as art direction, not as spec.

Language: English, to match the existing `website/docs/` set. Russian UI strings are quoted verbatim.

---

## 0. Reference-material inventory

There is **no `design-references/` folder in the repo.** What exists:

| Location | What it is | Use for this work |
|---|---|---|
| `design/` (repo root) | `DESIGN_SYSTEM.md`, `AUDIT_REPORT.md`, `ROADMAP.md`, `screens/P0_*.md` | **Product dashboard** (Flask/Telegram app), not the marketing site. Amber `#F7931A` palette. Out of scope — and its accent is exactly what the new direction forbids. |
| `website/docs/SITE_AUDIT.md`, `SITE_REDESIGN_PLAN.md`, `DESIGN_EXCELLENCE_AUDIT.md`, `REDESIGN_QA_REPORT.md`, `docs/audit/*` | Previous audit round that produced the current build | Historical context; several defects listed there are already fixed in this tree. |
| Stitch MCP projects (3, owned) | `Trading Bot Dashboard P0`, `Institutional AI Trading Interface`, `Quantix AI Trading Ecosystem` | **All three are orange/amber `#F7931A`/`#FF9500`/`#FF8C00`.** They are *not* the approved reference and directly contradict the new brief. Do not mine them for colour. |
| Stitch board `2281049485843837902` + the attached PNG | **The approved reference** | Sole art-direction source. |

> **Action item (housekeeping, not part of the build):** create `website/docs/design-references/` and commit the approved reference PNG plus this pair of documents, so the art direction stops living only in a chat attachment and a private Stitch URL.

---

## 1. What the approved reference actually specifies

Decomposed from the board, left column → right column:

| Fragment | Content |
|---|---|
| **A1** | Header: dark rounded pill, `QUANT` wordmark left, 5 centre nav items with an **underline on the active item**, `EN \| RU`, white pill CTA right |
| **A2** | Hero: **dark rounded panel** (not full-bleed), headline left, **Q-aperture right — tilted elliptical orbit rings, cyan/blue glow, node dots on the orbits, dark aperture core**, faint grid |
| **A3** | Proof strip: a **separate darker bar inside the bottom of the hero panel**, mono micro-items |
| **A4** | Audience: **light section**, eyebrow `AUDIENCE`, H2, 3 dark cards, and a **bracket connector descending from the cards into the next section** |
| **B1** | How Quant Works: black, **vertical glowing spine**, nodes `01…07` on the spine, cards alternating left/right, dotted connectors |
| **B2** | Foundation / "На чём это стоит": **light section**, eyebrow `FOUNDATION`, H2, 3 dark cards with numbered `01/02/03` |
| **B3** | Terminal: black, text + CTA left, **terminal panel right** |
| **B4** | Telegram: **light section**, text left, phone + signal card right |
| **C1** | Execution: light, broker cards with **logos** and status chips, second row of route cards |
| **C2** | Strategy ladder: table with status chips |
| **C3** | Pricing: 3 cards, **middle emphasised**, `$10 / $30 / $50` |
| **C4** | Final CTA: **black rounded panel**, headline, white CTA, footer columns |

Motion notes visible in the Stitch agent log beside the board:
- Scroll reveal: fade + 20px rise, **0.8s, quint easing**
- Q-Aperture: **breathing** animation, concentric rings rotating at varying slow speeds
- Sticky header: transparent → **compact blurred black bar after 100px**

---

## 2. Structural mapping — the requested section list vs. what the code actually renders

This matters before anything else, because **two of the thirteen requested "sections" are not sections.**

| # (brief) | Requested block | Reality in code | DOM id |
|---|---|---|---|
| 1 | Header / Navigation | `nav/site-header.tsx` + `nav/mobile-nav.tsx` | `<header>` (fixed) |
| 2 | Hero | `hero/hero-section.tsx` | `#hero` |
| 3 | Audience | `audience/audience-section.tsx` | `#audience` |
| 4 | How Quant Works | `how-it-works/how-it-works-section.tsx`, **first block only** (7 pipeline cards + loop note) | `#how-it-works` |
| 5 | Confidence / principles | **NOT a section.** Sub-block inside `how-it-works-section.tsx:212-225` — `"Границы уверенности"` + 3 `<Stat>` | — |
| 6 | "На чём это стоит" | **NOT a section.** Sub-block inside `how-it-works-section.tsx:232-272` — `principlesHeading` + 3 principle cards from MDX | — |
| 7 | Terminal / Dashboard | `dashboard/dashboard-section.tsx` + `dashboard-terminal.tsx` | `#dashboard` |
| 8 | Telegram | `telegram/telegram-section.tsx` + `signal-card.tsx` | `#telegram` |
| 9 | Brokers / execution routes | `brokers/brokers-section.tsx` | `#brokers` |
| 10 | Strategy laboratory | `strategies/strategies-section.tsx` + `strategy-table.tsx` | `#strategies` |
| — | **Безопасность (Safety)** | `safety/safety-section.tsx` — **6 cards + caveat. Missing from the brief's list, is nav-linked, must not be dropped.** | `#safety` |
| 11 | Pricing / access | `pricing/pricing-section.tsx` **and** `access/access-section.tsx` — two separate sections | `#pricing`, `#access` |
| 12 | FAQ | `faq/faq-section.tsx` | `#faq` |
| 13 | Final CTA / Footer | `access/access-section.tsx` (final CTA) + `footer/footer.tsx` | `#access`, `<footer>` |

**Consequences:**
1. `#how-it-works` currently carries **three separate arguments** in one 2 563px-tall section — the longest block on the page by 1 286px. The reference treats *Foundation* as its own titled section (**B2**, with its own eyebrow and H2). Splitting is both an art-direction requirement and a structural fix.
2. `#safety` is real, nav-linked (`nav.safety` → `"Безопасность"`), and absent from the brief. It is **kept and audited below as §11**.
3. The brief's "Pricing / access" and "Final CTA" overlap: `#pricing` and `#access` are distinct sections with distinct jobs. Both audited.

---

## 3. Global findings (measured, not inferred)

### 3.1 What is already correct — do not regress it

| Item | Evidence |
|---|---|
| **No horizontal scroll, either breakpoint** | 1440: `scrollWidth 1434 === clientWidth 1434`. 390: `390 === 390`. Zero elements overflow the viewport box. `html`/`body` both use `overflow-x: clip` (deliberately *not* `hidden` — documented in `globals.css:39-52`). |
| **The "mouse pulls the page backward" bug is fixed** | `scroll-driver.ts:79-82` sets `history.scrollRestoration = "manual"`, plus `resync()` after `load` and on resize. The root cause (async browser restore landing after Lenis captured `scrollY≈0`) is documented at `scroll-driver.ts:6-46`. Wide tables use `data-lenis-prevent-horizontal`, **not** the bare `data-lenis-prevent` — the bare form is exactly what reintroduces the lurch (`strategy-table.tsx:22-31`). |
| **Reduced motion works, on three layers** | (1) global `prefers-reduced-motion` reset in `globals.css:454-462`; (2) `[data-reveal] { opacity: 1 !important; transform: none !important }` safety net at `:477-480`; (3) Lenis is never instantiated at all (`scroll-driver.ts:109`). `Reveal` and `Magnetic` both branch **behaviour only, never markup** — the hydration-mismatch trap is documented in both files. |
| **Sticky header does not overlap headings** | Pill bottom = **78px**; `NAV_OFFSET = 104`; `scroll-margin-top: 104px` on `section[id]`. Clearance = **26px**. Both numbers are single-sourced and cross-referenced. |
| **Header blur genuinely applies** | `getComputedStyle(.nav-glass).backdropFilter === "blur(24px) saturate(1.4)"`. The Lightning-CSS `@supports` workaround at `globals.css:293-302` is working. |
| **Type scale is disciplined** | Only **8 rendered font sizes** across the whole page (11/13/16/18/20/40/48/54.72). Enforced by `scripts/check-design-tokens.mjs` with a 0-budget on arbitrary `text-[Npx]`. |
| **No fake results anywhere** | Chromatic-colour census returns exactly one hue family — the desaturated success green `rgb(127,216,168)`. No P&L, win rate, profit factor, Sharpe, equity curve or sample size in any component. `Stat` shows only configured limits and system constants. Pricing reads `"Бесплатно" / "Планируется" / "Планируется"`. |
| **Accessibility baseline is strong** | Real WAI-ARIA tablist in the terminal (roving focus, `aria-selected`, `aria-controls`); native `<details>` FAQ; every status carries a **text label** beside its dot; `:focus-visible` is global. |

### 3.2 Global problems

| ID | Finding | Evidence | Severity |
|---|---|---|---|
| **G1** | **Radius is far too tight for the reference.** Panel radius is **8px** (`--radius-lg: 0.5rem`). Census: `8px`×36, `6.4px`×6, `4.8px`×12, pill×43. The reference's hero panel, cards and CTA block read at roughly **16–24px**. | measured | High |
| **G2** | **Zero cold accent exists.** `color.css:1-16` states the doctrine: *"There is no brand accent hue… If a pixel is coloured and it is not a trade state, it is a bug."* `--color-accent` is `#ffffff`. The reference's defining feature is a **cold blue/cyan signal glow**. This is a deliberate, documented rule that must be formally amended, not quietly broken. | `color.css`, census | High |
| **G3** | **The page is 100% black; the reference alternates dark ↔ light.** Reference sections **A4, B2, B4, C1–C3** are light. `--color-paper: #f4f2ec` is already declared (`color.css:27`) and used **nowhere**. | measured | High — needs an owner decision (see §14, D1) |
| **G4** | **Section rhythm is uneven and reads as arbitrary.** Content-to-content gaps: hero→audience **225**, audience→how **347**, how→dashboard **404**, dashboard→telegram **299**, telegram→brokers **299**, brokers→strategies **347**, strategies→safety **289**, safety→pricing **347**, pricing→faq **347**, faq→access **347**. The 225 and the 404 are the outliers; the hero already trails a screenful, so 225 reads *tight* while 404 reads *dropped*. | measured | Medium |
| **G5** | **Anchor navigation lands in dead space.** After the 104px offset, the first visible content sits **231px** below the section top for `#how-it-works`, `#dashboard`, `#brokers`, `#pricing`, `#access` (the `major` rhythm's 201.6px padding + 29px). Five of ten nav targets drop the user onto a third of a screen of black. Not an overlap bug — the opposite. | measured | Medium |
| **G6** | **Clickable cards do not look clickable.** 32 `Surface` cards; **4 contain a link and still compute `cursor: default`** — all three Audience cards and the Access "Live" card. `surface.tsx:44` documents this as intentional ("a card is only a pointer target when it actually navigates"), but in these four the *whole card is the route selector* in the reference. | measured | Medium — brief item #7 |
| **G7** | **Label inflation.** The 11px mono eyebrow renders **127 times**. `mono-label.tsx:4-9` itself cites a "max 1 per 3 sections" restraint rule that the page does not honour. The reference uses far fewer, quieter labels. | measured | Medium |
| **G8** | **`--radius-xl` resolves to an empty string at runtime.** Declared in `globals.css:507` inside `@theme inline`, but Tailwind v4 only emits theme vars that a utility consumes — nothing does. Any new component writing `borderRadius: "var(--radius-xl)"` in an inline style gets **nothing**, silently. | measured | Low, but a live trap for the build phase |
| **G9** | **`gsap@^3.15.0` is a dead dependency.** `scroll-driver.ts:34-42` documents its removal; no source file imports it. | source | Low |
| **G10** | **`npm run typecheck` does not exist.** `package.json` has `dev, build, start, lint, check:content, check:i18n, check:design, check:media, media:poster, build:messages`. The brief's verification list requires it. | source | **Blocker for the stated verification protocol** |
| **G11** | **Playwright is not installed in `website/`.** No dependency, no config, no test dir. The brief requires 1440 and 390 visual checks. (A Playwright **MCP server** is available to this session, which covers ad-hoc verification but leaves nothing in the repo.) | source | **Blocker for the stated verification protocol** |
| **G12** | **Page length.** 13 726px at 1440 (≈15 screens); **21 779px at 390 (≈26 screens)**. The reference is materially denser. Mobile especially needs compression, not just restyling. | measured | Medium |
| **G13** | **The hero visual is framed as a window, not as an instrument.** `hero-visual.tsx` wraps the aperture in titled chrome + a status pill + a 6-cell step rail. The reference's Q-aperture **floats free** with no frame at all. | source + reference | High (brief item #2) |

---

## 4. §1 — Header / Navigation

**Anchor:** `<header>` (fixed, outside `<main>`, correct for the banner landmark)
**Files:** `src/components/sections/nav/site-header.tsx`, `src/components/sections/nav/mobile-nav.tsx`, `src/components/ui/monogram.tsx`, `src/components/ui/button-link.tsx`, `globals.css` (`.nav-glass`, `.nav-scrim`)

**Current purpose.** Persistent wayfinding across 5 in-page anchors, locale switch, and the single conversion CTA. Fixed pill with real backdrop blur plus a 128px gradient scrim so content dissolves on approach rather than sliding under a hard edge.

**Current UX/UI problems.**
- **No active-section state.** All five links render identically at `--color-text-tertiary` regardless of scroll position. The reference explicitly shows an underline on the active item. On a 13.7k-px single page this is the single most useful nav affordance and it is absent.
- **Nav label ↔ target mismatch.** `nav.dashboard = "Продукт"` points at `#dashboard`; `nav.how = "Как работает"` at `#how-it-works`. Fine, but the reference's five labels map 1:1 to the five visible ideas, and `#brokers` / `#strategies` — two of the strongest sections — are unreachable from the header.
- **Three visual weights in a 6-item row** (wordmark, 5 tertiary links, locale pair, divider, white CTA, hamburger) inside 62px. Reads busier than the reference.
- **Locale switcher is two always-visible links,** not a toggle. Reference shows `EN | RU` with the inactive one dimmed — closer to what's here than not, but the current `px-2 py-1.5` pair plus a `w-px` divider plus a gap is three separators in 90px.
- **Header does not change on scroll.** Reference calls for transparent → compact blurred bar after 100px. Current header is fully opaque `rgba(6,6,7,0.86)` from pixel zero, so the hero never gets a clean top edge.
- Nav links hidden below `lg` (1024px); the hamburger carries everything 768–1023px, where there is ample room for at least three links.

**What looks raw.**
- The `w-px` divider between the locale pair and the CTA is a hairline artefact, not a designed separator.
- Hamburger is three 14px×1px bars in a 44px box — visually thin next to a solid white CTA pill.
- Mobile dropdown (`mobile-nav.tsx:89`) uses `rounded-xl` — a **raw Tailwind class**, not a token. It is the only rounding on the page that bypasses `--radius-*`.
- `mobile-nav.tsx:45,114` hand-writes `rgba(255,255,255,0.04)` / `rgba(255,255,255,0.05)` inline — burning 2 of the 6 allowed `raw-white-alpha` budget entries in `check-design-tokens.mjs`.

**Conflicts with the approved reference.**
| Reference | Current |
|---|---|
| Active-item underline | none |
| Transparent → blurred-compact at 100px | opaque from 0 |
| Generous pill radius (~16px) | 8px |
| Quiet, evenly-weighted nav row | 3 competing weights |

**Possible layout/scroll/responsive bugs.**
- `NAV_OFFSET = 104` is duplicated as a literal in `globals.css:323` (`scroll-margin-top`) and as a constant in `scroll-driver.ts:66`. They are correct today and cross-documented, but **any header-height change must touch both** — and if the header becomes height-variable on scroll (the reference's compact mode), a single constant can no longer be right for both states.
- Mobile panel is `top-[68px]` hard-coded while the header measures **86px at 390px** — an 18px gap under the pill. Cosmetic today; breaks if header padding changes.
- Header is `fixed` and sized to the initial containing block, so it stays 1440 wide while `<main>` narrows to 1434 once the 6px scrollbar appears. Already mitigated by `overflow-x: clip` on `html` (`globals.css:41-44`) — **do not remove that clip.**

**Keep.**
- `fixed` + `<header>` outside `<main>`.
- `.nav-scrim` gradient — this is the premium device and it works.
- The `@supports` blur workaround (`globals.css:293-302`). Removing it silently kills every glass surface.
- Real `<nav aria-label>` landmarks; `aria-current` on the locale.
- `ButtonLink` for the CTA (single tracking path).

**Rework.**
- Add scroll-state: transparent at top → glass-compact past 100px (height and padding transition, not opacity alone).
- Add scroll-spy active state (IntersectionObserver over section ids — **not** scroll listeners; must not touch the Lenis position).
- Raise pill radius to the new `--radius-lg`.
- Collapse the locale pair into a single toggle; delete the `w-px` divider.
- Tokenise `rounded-xl` and the two inline white alphas in `mobile-nav.tsx`.
- Show nav links from `md` (768px), not `lg`.

**Components involved.** `SiteHeader`, `MobileNav`, `Monogram`, `ButtonLink`, `Magnetic`, `Link` (next-intl).
**Files likely to change.** `nav/site-header.tsx`, `nav/mobile-nav.tsx`, `globals.css` (`.nav-glass`, `.nav-scrim`, new compact state), `motion/scroll-driver.ts` (if `NAV_OFFSET` becomes state-dependent), **new** `ui/brand-mark.tsx`, **new** scroll-spy hook.

---

## 5. §2 — Hero

**Anchor:** `#hero` · **Files:** `hero/hero-section.tsx`, `hero/hero-visual.tsx`, `hero/pointer-tilt.tsx`, `hero/hero-video.tsx` (unused), `hero/hero-media.ts`

**Current purpose.** The argument in one screen: eyebrow → 2-line headline (`"Рынок создаёт шум." / "Quant превращает его в решение."`) → subline → primary CTA + arrow link → 5-item proof strip. Right column: the decision-path instrument + 3 configured-limit stats.

**Current UX/UI problems.**
- **The instrument is framed as an application window.** Title bar with `Monogram` + `"ПУТЬ РЕШЕНИЯ"` + a `ПЕСОЧНИЦА` pill, then the aperture, then a 6-cell step rail. That is three UI chrome layers around what the reference presents as one free-floating object.
- **The aperture is flat.** Three concentric circles at 6/9/13% white opacity, 4 quadrant ticks, one dashed exit vector, one node. At 1440 the panel is ~640×440 and reads as *mostly empty dark rectangle* — measured `aspect-[16/11]` with the mark at 25% width.
- **No depth, no glow, no orbit geometry.** Reference: tilted ellipses at multiple inclinations, node dots riding the orbits, a cyan core bloom, a grid behind. Current: coplanar circles, one white pool at 5.5% alpha.
- **Proof strip is loose inline text.** Five items separated by `·` at `--color-text-quaternary` (4.9:1, the hard floor). The reference gives it a **contained bar** inside the hero panel.
- **Right column is two unrelated stacks** — the panel, then a hairline, then a 3-up stat grid. The stats read as a footnote rather than as part of the composition.
- `min-h-dvh` + `pt-32 pb-20` produces a **1 479px hero at 390px** — 1.75 screens before the fold. On mobile the CTA is well below the first viewport.

**What looks raw.**
- The 6-cell step rail (`hero-visual.tsx:160-177`) uses `gap-px` over a border-coloured background to fake dividers. It works, but at `sm:grid-cols-6` each cell is ~100px wide holding an 11px uppercase Cyrillic word — cramped, and it duplicates information that `#how-it-works` states properly 900px later.
- `figcaption` disclaimer sits outside the panel in 13px quaternary grey — honest, but visually orphaned.
- `hero-video.tsx` (205 lines) and `hero-media.ts` are **dead code**: nothing imports them. `public/fallback/hero.png` is deleted in the working tree while `public/media/quant-hero/*.webp` remain.

**Conflicts with the approved reference.**
| Reference | Current |
|---|---|
| Dark **rounded panel** floating on the page | flat full-bleed black |
| Free-floating Q-aperture, cyan glow, tilted orbits, orbit nodes | framed white-line diagram, no colour, coplanar |
| Faint background grid | none |
| Proof strip as a contained bar in the panel | inline `·`-separated text |
| Headline dominant | headline 54.72px vs a 640px-wide visual — visual wins |

**Possible layout/scroll/responsive bugs.**
- `PointerTilt` writes `--tilt-x/--tilt-y` and `hero-tilt` applies `translate3d(±7px)` with `will-change: transform`. Harmless today (translate only, inside `overflow-x: clip`), but **any added rotation/scale must not increase the element's painted box** or it can push the 6px-scrollbar threshold.
- `min-h-dvh` on iOS Safari re-measures on toolbar collapse → the hero can jump on first scroll. Not observed in this pass (desktop Chromium), flagged for the mobile check.
- `qf-hero-enter` is deliberately **transform-only, never opacity** (`globals.css:120-127`) — an opacity ramp with `fill-mode: both` disqualifies the subtree as an LCP candidate for the whole delay. **The new hero must obey this.**
- Four looping CSS animations (`hero-ring` ×3 desynced, `hero-vector`, `hero-node-ping`, `hero-scan`) are compositor-only. Adding orbit rotation must stay on `transform`/`opacity` only.

**Keep.**
- All copy, both locales. The headline and subline are approved.
- The claim-free contract: no chart, no curve, no figure, no percentage (`hero-visual.tsx:26-33`). **Non-negotiable.**
- The three `Stat` tiles as *configured limits* — `5% / 2% / 0.20`, verifiable in `bot/config.py:66-71`.
- Transform-only entrance; compositor-only loops; the reduced-motion contract.
- Server-rendered, zero-client-JS visual (only `PointerTilt` is a client shell).

**Rework.**
- Rebuild the visual as a **`QAperture`** component: tilted elliptical orbits (multiple inclinations), orbit nodes, a cold-blue core bloom, faint grid backplate, no window chrome, no status pill, no step rail.
- Wrap the hero in a **rounded panel** (`--radius-2xl`) with an inner grid + edge vignette, per reference A2.
- Move the proof strip **into** the panel as a contained bar (reference A3).
- Recompose the right column: aperture and limit tiles as one object, not two stacks.
- Cut hero height on mobile: drop `min-h-dvh` below `md`, target ≤ 1.15 screens to the CTA.
- Delete `hero-video.tsx` / `hero-media.ts` (dead) — or keep and document; do not leave ambiguous.

**Components involved.** `HeroSection`, `HeroVisual`, `PointerTilt`, `Monogram`, `MonoLabel`, `StatusPill`, `Stat`, `ButtonLink`, `ArrowLink`, `Magnetic`.
**Files likely to change.** `hero/hero-section.tsx`, `hero/hero-visual.tsx` → **new** `hero/q-aperture.tsx`, **new** `ui/grid-backplate.tsx`, `globals.css` (orbit keyframes), `styles/tokens/color.css` (glow tokens), `hero/pointer-tilt.tsx` (parallax depth per orbit layer).

---

## 6. §3 — Audience

**Anchor:** `#audience` · **File:** `audience/audience-section.tsx` (52 lines)

**Current purpose.** Route selection. `"Один Quant. Разный уровень контроля."` → three cards (Новичку / Трейдеру / Партнёру и разработчику), each with an `ArrowLink` to `#safety`, `#how-it-works`, `#brokers`.

**Current UX/UI problems.**
- **This is the weakest-designed block on the page and the one the reference invests most in.** Three flat 7-padding boxes with identical treatment: `h3`, paragraph, arrow link. No number, no icon, no differentiation, no ordering signal.
- **The card is a route selector but only the 12-word arrow link is clickable.** Measured: all three compute `cursor: default`; the hit target is the `ArrowLink` alone. Brief item #7 fails here specifically.
- **No connection to the next section.** The reference draws a **bracket connector descending from the three cards into the pipeline** — the audience choice visibly *routes into* how it works. Currently: three cards, a 347px gap, an unrelated H2.
- Hover exists (`.card-premium`: border → 28% white, bg `#0a0a0a`→`#111`, `translateY(-6px)`, soft glow) and it is good — but it is the *same* hover as the other 29 cards, so choosing a route feels no different from reading a safety fact.
- `mt-14` (56px) between the header and the cards is the same as every other section's — no signal that this grid is a *choice* rather than a list.

**What looks raw.**
- Three equal boxes with three equal paragraphs of 4 lines each; the RU copy makes card 3 visibly longer, and `flex-1` on the body pushes the three arrow links to different visual heights relative to their text.
- The arrow links (`"ЧТО ТАКОЕ ПЕСОЧНИЦА →"`) are 13px mono uppercase — at that size in Cyrillic with `0.08em` tracking they read as metadata, not as the primary action of the card.

**Conflicts with the approved reference.**
| Reference | Current |
|---|---|
| Bracket **signal line** from cards into the pipeline | no connector |
| Cards read as selectable routes | cards read as three paragraphs |
| Light section, dark cards (contrast inversion) | black on black |
| Distinct card identity (numbering/weight) | three identical boxes |

**Possible layout/scroll/responsive bugs.**
- `md:grid-cols-3` jumps 1→3 at 768px with no 2-up intermediate; at 768–900px three Cyrillic cards at ~230px each are very tight.
- `Reveal index={i}` staggers 0/80/160ms — correct.
- Any connector drawn between this section and `#how-it-works` **must not** be absolutely positioned across the section boundary: `Section` deliberately never sets `overflow-hidden` (`ui/section.tsx:41-48`) and a cross-section absolute element would need re-derivation at every breakpoint. Draw it as an in-flow element owned by the audience section's bottom.

**Keep.**
- All copy and both locales; the three-audience model.
- The three `href` targets — they are the real routes.
- `Reveal` stagger; the shared `.card-premium` hover as the *base* language.

**Rework.**
- Make the **whole card the link** (single `<a>` wrapping, `cursor: pointer`, one focus ring, `::after` overlay pattern so nested text stays selectable).
- Add per-card identity: `01/02/03` or a route glyph.
- Add the **SignalLine** connector down into `#how-it-works` (reference A4).
- Add a stronger, distinct hover for route cards: lift + cold-blue edge glow + arrow travel, differentiated from passive cards.
- Add an `sm:grid-cols-2` step.

**Components involved.** `Section`, `SectionHeader`, `Surface`, `ArrowLink`, `Reveal`.
**Files likely to change.** `audience/audience-section.tsx`, **new** `ui/interactive-card.tsx`, **new** `ui/signal-line.tsx`, `ui/surface.tsx` (pointer/link variant), `globals.css` (`.card-premium` route variant).

---

## 7. §4 — How Quant Works (pipeline block)

**Anchor:** `#how-it-works` (first of three blocks) · **Files:** `how-it-works/how-it-works-section.tsx:161-204`, `content-layer/source.ts`, `content/{ru,en}/engine-pipeline/01…07-*.mdx`

**Current purpose.** The decision path told twice per stage — plain sentence first, then the real module name + `sourceRef` into the Python codebase. Seven stages: candle-loader → indicator-engine → rules-engine → belief-gate → risk-manager → broker → memory-writer.

**Current UX/UI problems.**
- **It is a grid, and the reference is a pipeline.** Brief item #4 names this directly. Seven cards at `lg:grid-cols-3` say nothing about sequence; the only sequence signal is the `StageRail` hairline drawn L→R on reveal (`:56-67`) and the `01…07` badge.
- The **7-across-3 orphan** is handled by spanning card 7 full-width (`:163-164`, derived from `stages.length % 3 === 1`). Clever and well-reasoned — but it makes stage 7 visually *heavier than stages 1-6*, which inverts the reading: the loop-closer looks like the headline act.
- `StageRail` resets its stagger per row (`index={i % 3}`), so the "signal propagating" read restarts three times instead of running once through seven stages.
- Each card carries **five type levels** (badge, step label, plain sentence, technical name, description, `sourceRef` code) in a 7-padding box. Dense; the `sourceRef` `break-all` monospace at 11px quaternary is the visual bottom of the card and often wraps mid-token.

**What looks raw.**
- The spanning card's two-column split (`:178-185`) puts the loop note behind a `border-l-2` at `self-center` — a quote treatment inside a stage card. Reads as an afterthought that was given a home.
- The `border-l-2 pl-5` note pattern appears **five times** across the page (`how-it-works` ×2, `safety`, `strategies`, `access` trust list is adjacent) with no shared component.

**Conflicts with the approved reference.**
| Reference (B1) | Current |
|---|---|
| Vertical **glowing spine** with nodes `01…07` on it | 3-column card grid |
| Cards alternate left/right off the spine | uniform grid cells |
| Dotted connectors between node and card | none |
| One continuous propagation | stagger resets per row |

**Possible layout/scroll/responsive bugs.**
- **Critical constraint:** the previous version of this section was a **pinned GSAP ScrollTrigger horizontal track** and it was removed for four documented defects (over-pan by ~230px, nested `overflow-x-auto` + transform + scroll-snap fighting, `data-lenis-prevent` on a full-width track killing vertical smooth scroll, and pin-vs-`overflow:hidden` constraining the whole page). See `how-it-works-section.tsx:20-39`. **The new spine must be pure layout + IntersectionObserver. No pinning, no scroll-linked transforms, no nested scroll container.** Reintroducing any of those reintroduces brief item #10.
- `ui/section.tsx` never sets `overflow-hidden` for exactly this reason — a decorative spine must live in the clipped `glow` slot or as an in-flow element, never force a clip on the section.
- At `md:grid-cols-2` the `spans` calculation still keys off `% 3`, so at the 2-column breakpoint card 7 spans 2 while cards 1-6 fill 3 rows evenly — correct by luck, not by construction.

**Keep.**
- All seven stages, both locales, and **every `sourceRef`** — the most verifiable claim on the site.
- Plain-then-technical dual reading.
- MDX content layer (`content/{ru,en}/engine-pipeline/`) — do not inline this copy.
- No pinning. No horizontal scroll container.

**Rework.**
- Rebuild as a **vertical spine**: sticky-free, in-flow, nodes at `01…07`, cards alternating sides at `lg`, single-column with a left rail below `lg`.
- Spine draws in as one continuous gradient reveal (one `Reveal` per node, not per row).
- Move `sourceRef` into a collapsed/secondary treatment so it stops being the card's visual floor.
- Extract the `border-l-2` note into a shared `<Aside>` primitive.
- Retire the `% 3` orphan logic — a spine has no orphan.

**Components involved.** `Section`, `SectionHeader`, `Surface`, `MonoLabel`, `Reveal`, `StageRail`, `StageBody`, `contentSource`.
**Files likely to change.** `how-it-works/how-it-works-section.tsx` (split — see §8/§9), **new** `how-it-works/pipeline-spine.tsx`, **new** `ui/signal-line.tsx`, **new** `ui/aside-note.tsx`, `globals.css` (spine keyframes).

---

## 8. §5 — Confidence / principles ("Границы уверенности")

**Anchor:** none — sub-block at `how-it-works-section.tsx:212-225`
**Files:** same, plus `content/{ru,en}/learning-system.mdx`, `content-layer/source.mdx.ts`

**Current purpose.** Three system constants from `bot/learning/belief_updater.py:37,46-47` — `MIN_TRADES_FOR_CONFIDENCE`, and the min/max confidence clamps — followed by the learning-system intro paragraph. Explicitly constants, **never results**.

**Current UX/UI problems.**
- **No heading, no anchor, no identity.** It opens with an 11px `MonoLabel` (`"Границы уверенности"`) on a hairline, 56px below the pipeline's last card. Nothing tells the reader a new argument started.
- Three bare `Stat`s in a `sm:grid-cols-3` — value, label, no container, no hover, no focus. **They are the only figures on the page and they have the least visual protection.** A reader skimming for numbers finds three unframed digits floating in black.
- Values `12 / 0.20 / 0.85` are dimensionless and unexplained at the point of reading; the explanation is the paragraph underneath, which many readers will not reach.
- The learning-system intro is rendered as an undifferentiated `<div>` of body text at `max-w-72ch` — the longest unbroken prose on the page.

**What looks raw.** Un-carded numbers in a section otherwise built entirely of cards is the clearest "unfinished" tell on the page. Section-internal `gap-14` gives this new topic the same air as a sibling paragraph, which the file's own comment at `:206-211` acknowledges and only partly fixes with `pt-14`.

**Conflicts with the approved reference.** The reference has **no direct analogue** — its nearest fragment is **B2 (Foundation)**, three numbered cards. So this block needs a designed home rather than a mapped one. The reference's card-based rhythm implies: put these three constants in `SurfaceCard`s with the same weight as everything else, or fold them into the pipeline spine at the `belief-gate` node where they actually belong.

**Possible layout/scroll/responsive bugs.**
- No id → **unreachable by anchor**, invisible to the future scroll-spy, and cannot be deep-linked.
- `sm:grid-cols-3` at 640px puts three `--text-h3` (20px) mono values plus 11px labels in ~190px columns; RU labels (`"МИНИМУМ СДЕЛОК"`) wrap to two lines unevenly.

**Keep.**
- The three constants and their provenance. **They must stay labelled as configured constants, never as measured outcomes.**
- `Stat`'s pre-formatted-string contract (`stat.tsx:5-13`) — no `Intl` inside the component; hydration hazard.
- The learning-system MDX source.

**Rework.**
- Give it a real identity: either **(a)** promote to its own `<Section id="confidence">` with eyebrow + H2, or **(b)** attach it to the `belief-gate` node of the new pipeline spine as an expanded node detail. **Recommendation: (b)** — it is literally the belief gate's parameters, and it shortens the page (G12).
- Card the three constants (`SurfaceCard` + hover/focus, brief item #6).
- Add a unit/qualifier line to each (`Stat` already has a `hint` slot, unused here).

**Components involved.** `Stat`, `MonoLabel`, `Reveal`, `contentSource.getLearningSystemCopy`.
**Files likely to change.** `how-it-works/how-it-works-section.tsx`, **new** `how-it-works/confidence-bounds.tsx` (or fold into `pipeline-spine.tsx`), `ui/stat.tsx` (carded variant).

---

## 9. §6 — "На чём это стоит" (Foundation)

**Anchor:** none — sub-block at `how-it-works-section.tsx:232-272`
**Files:** same, plus `content/{ru,en}/philosophy/01-what-bots-do.mdx`, `02-what-we-dont.mdx`, `03-what-we-do.mdx`

**Current purpose.** The manifesto — three numbered principle cards from MDX, each with an optional `sourceRef`. This is the section that carries the honesty positioning.

**Current UX/UI problems.**
- **It is a manifesto rendered as a footnote.** No H2, no eyebrow beyond an 11px `MonoLabel`, no lead. The file's own comment (`:227-231`) says exactly this — *"this is a manifesto, not a footnote to the paragraph above it"* — and the fix applied was a rule + `pt-[var(--space-section-y-tight)]`, which is 96px. That is still less air than any real section gets.
- It is the **third topic inside a 2 563px section**, arriving ~2 200px after that section's H2. By the time a reader reaches it, `#how-it-works`'s heading has been off-screen for two screens.
- Cards use `variant="raised"` (`#111` → `#171717`) while the pipeline cards above use `flat` (`#0a0a0a` → `#111`). Two elevations, 40px apart, with no stated reason — reads as inconsistency rather than hierarchy.
- The `01/02/03` numeral is `aria-hidden` 11px quaternary at the card's top-left — the smallest, dimmest element in a card whose entire point is ordered argument.

**What looks raw.** A titled manifesto with no title. The `MonoLabel` `"На чём это стоит"` at 11px/0.14em sits above three cards at the same size as the word `MOEX` elsewhere on the page.

**Conflicts with the approved reference.**
| Reference (B2) | Current |
|---|---|
| **Its own section** — eyebrow `FOUNDATION` + H2 | 11px label inside another section |
| **Light background, dark cards** | dark on dark |
| Prominent `01/02/03` | 11px `aria-hidden` numeral |
| Clear top-level rhythm | 96px `pt` inside a parent |

**Possible layout/scroll/responsive bugs.**
- No id → not anchorable, not scroll-spy-able.
- The parent section's `divider` + `glow` apply to all three blocks at once; a background inversion for this block alone is impossible without splitting the section.

**Keep.**
- All three principles, both locales, the MDX source, and every `sourceRef`.
- The numbered ordering (they build on each other).

**Rework.**
- **Promote to `<Section id="foundation">`** with eyebrow + H2 + lead. This is the single highest-value structural change in the audit: it fixes G4 (rhythm), G5 (anchor landing), the 2 563px monolith, and reference-fragment B2 in one move.
- Give it the light/inverted treatment if D1 is approved (see §14).
- Promote `01/02/03` to a display numeral.
- Add to nav or footer links.

**Components involved.** `Surface` (`raised`), `MonoLabel`, `Reveal`, `contentSource.getPhilosophyBlocks`.
**Files likely to change.** `how-it-works/how-it-works-section.tsx` (extract), **new** `foundation/foundation-section.tsx`, `app/[locale]/page.tsx` (insert), `messages/{en,ru}.json` (new `foundation` namespace — **must ship in both locales together**, `check:i18n` gates it), `nav/site-header.tsx` (optional link).

---

## 10. §7 — Terminal / Dashboard

**Anchor:** `#dashboard` · **Files:** `dashboard/dashboard-section.tsx` (38), `dashboard/dashboard-terminal.tsx` (449)

**Current purpose.** The operator terminal as an interactive product surface: a vertical 6-tab WAI-ARIA tablist (Обзор / Портфель / Сигналы / Бэктесты / Аналитика / Риск) driving a chrome-framed preview panel.

**Current UX/UI problems.**
- **Layout is inverted relative to the reference.** Current: tablist left `0.8fr`, panel right `1.2fr`. Reference B3: **narrative text + CTA left, terminal panel right** — the panel is the hero of the section and there is no visible tab UI at all. The current version front-loads a control surface before the reader knows what they are looking at.
- The section header's `lead` and `apiOnlyNote` sit above the whole thing, so the panel has no local caption — the reference pairs the panel with a short claim and a button.
- **Six tabs is a lot of choice for a marketing page.** Two of them (`Аналитика`, `Риск`) render definition lists and a bar list that are the least product-like of the six.
- No CTA anywhere in this section — the reference shows one directly under the terminal copy.
- The `demoNote` disclaimer is below the panel in 13px quaternary; honest, but the reference's composition would place the honesty line adjacent to the claim, not orphaned under the artefact.

**What looks raw.**
- The three grey dots at `dashboard-terminal.tsx:396-400` are a **macOS traffic-light imitation in monochrome** — the most generic "this is a fake app screenshot" device available, and it undercuts the "real instrument" positioning. The reference's terminal panel has no traffic lights.
- `min-w-[520px]` tables inside `overflow-x-auto` mean **four of the six panels horizontally scroll at 390px**. Correctly contained (no page overflow) but it is four separate mini-scrollers in one section.
- The regime bar list (`case 4`) uses raw `%`-width spans with no axis, no scale, no tick — a chart that has been stripped of everything that makes a chart legible, in order to avoid making a claim. Honest, but visually unresolved.

**Conflicts with the approved reference.**
| Reference (B3) | Current |
|---|---|
| Text + CTA left, panel right | tablist left, panel right |
| Panel is the visual hero, wide | panel is 1.2/2 of the grid |
| No tab chrome exposed | 6 exposed tabs |
| No traffic-light dots | traffic-light dots |

**Possible layout/scroll/responsive bugs.**
- `data-lenis-prevent-horizontal` on each `DataTable` is **correct and load-bearing** (`dashboard-terminal.tsx:100-102`). The bare `data-lenis-prevent` here would reintroduce brief item #10. Do not "simplify" it.
- Tab switching re-keys a `motion.div` with `initial={{opacity:0,y:8}}`; `initial` must not branch on the reduced-motion preference (documented `:425-431`). Preserve.
- `hidden` panels stay in the DOM — correct for the ARIA pattern; means the section's height is set by the tallest panel.
- At `lg` the grid is `0.8fr / 1.2fr` of 1280 → tablist ~500px, panel ~740px. Below `lg` they stack, putting six tab buttons above the panel — a 6×~76px = 456px block of navigation before any content on mobile.

**Keep.**
- **The entire ARIA tablist implementation.** Roving focus, `aria-selected`, `aria-controls`, Home/End — this is textbook and rare. Any recomposition must carry it over intact.
- The honesty contract at `:11-38`: no P&L, no equity curve, no win rate, no return. Decision *state* only.
- `data-lenis-prevent-horizontal` on every scroller.
- Both caveats (`rkApiNote`, `demoNote`) — Риск is API-only, and Learning/Settings are omitted.

**Rework.**
- Recompose to reference B3: narrative + CTA left, terminal panel right and wider. Move the tablist **inside** the panel as a compact segmented control or a left rail *within* the terminal chrome.
- Replace traffic-light dots with a real instrument chrome (mode chip + connection state + the `QMark`).
- Consider reducing exposed tabs to 4 on mobile with the rest behind an overflow, to cut the 456px pre-roll.
- Add the section CTA.

**Components involved.** `Section`, `SectionHeader`, `Reveal`, `DashboardTerminal`, `Surface` (`raised`), `StatusPill`, `MonoLabel`.
**Files likely to change.** `dashboard/dashboard-section.tsx`, `dashboard/dashboard-terminal.tsx`, **new** `ui/terminal-panel.tsx` (extract the chrome), `ui/button-link.tsx` (reuse).

---

## 11. §8 — Telegram

**Anchor:** `#telegram` · **Files:** `telegram/telegram-section.tsx` (57), `telegram/signal-card.tsx` (184)

**Current purpose.** Telegram as the second interface onto the same state. Four feature cards (2×2) left, one genuinely interactive demo signal card right.

**Current UX/UI problems.**
- **The interactive card — the best artefact in this section — is the smaller half of the grid.** `lg:grid-cols-[1fr_0.8fr]` gives the four static text cards more area than the thing the visitor can actually press.
- Four feature cards are the same treatment as the six safety cards and the three audience cards. By this point in the page the reader has seen ~20 identical bordered boxes.
- No device frame, no context. The reference (B4) shows the signal card **inside a phone**, which is what makes "оператор в кармане" read instantly.
- `rhythm="tight"` (96px) here vs `major` (201.6px) on both neighbours — measured gaps 299px in and 299px out, against 347–404px elsewhere. Deliberate (it is the second interface onto the dashboard's state, per `:22-27`) but it is the section that most reads as *glued* to its neighbour.

**What looks raw.** Two `SurfaceCard` grids of different sizes side by side. The section reads as "here are four facts and a widget" rather than as a product surface.

**Conflicts with the approved reference.**
| Reference (B4) | Current |
|---|---|
| **Light section** | dark |
| Text left, **phone mockup** right | 4 cards left, bare card right |
| One clear artefact | five competing boxes |

**Possible layout/scroll/responsive bugs.**
- `SignalCard` is a client component with real button state — verify its success/skip states survive a locale switch and that the reset path is reachable by keyboard.
- At `lg` breakpoint the 2×2 feature grid and the signal card have independent heights; no alignment constraint, so the right column floats.

**Keep.**
- The signal card being **genuinely pressable** — `telegram-section.tsx:10-17` records that the previous version drew `aria-hidden` `<span>`s styled as controls, which was the exact "raw" impression being corrected. Do not regress to a static mock.
- All four feature texts, both locales.
- The `cardDemoHint` / `cardNote` disclaimers.

**Rework.**
- Invert the emphasis: narrative + 4 features as a compact list left; the signal card **in a phone frame** right, larger (reference B4).
- Light-section treatment if D1 is approved.
- Reduce the four feature cards to a bordered list or an icon row — they do not need to be cards.
- Keep `tight` rhythm but add the reference's visual separation (background inversion does this for free).

**Components involved.** `Section`, `SectionHeader`, `Surface`, `Reveal`, `SignalCard`, `StatusPill`.
**Files likely to change.** `telegram/telegram-section.tsx`, `telegram/signal-card.tsx`, **new** `ui/device-frame.tsx`.

---

## 12. §9 — Brokers / execution routes

**Anchor:** `#brokers` · **File:** `brokers/brokers-section.tsx` (89)

**Current purpose.** Where Quant actually executes, with per-broker status derived from the real state of each adapter — T-Invest `active`, Bybit `beta`, Finam `planned` — each provenance-commented against `bot/broker/`.

**Current UX/UI problems.**
- The three cards are visually identical apart from the status pill text. **Status is the entire information content of this section and it is carried by an 11px pill.**
- `BROKER_STATUS_TONE` maps `beta` and `planned` both to `muted`, so Bybit and Finam are chromatically identical — a partially-working integration and an unimplemented stub look the same at a glance. (Correct conservatism; poor differentiation.)
- The market label (`MOEX` / `Crypto`) is 11px quaternary under the name — the second-most-useful fact, rendered at the dimmest level on the page.
- No routing visualisation. The reference (C1) shows brokers as **execution routes** with a second row of route cards; the current section is a specification list.

**What looks raw.** Three boxes whose only differentiator is a grey pill. There is no visual answer to "which one can I actually use today?" without reading three paragraphs.

**Conflicts with the approved reference.**
| Reference (C1) | Current |
|---|---|
| Broker **logos** | text names only |
| Second row of **route** cards | none |
| Light section | dark |
| Status chips visually distinct per state | two of three identical |

**Possible layout/scroll/responsive bugs.** `md:grid-cols-3` with no 2-up step; three cards at 768px are ~230px wide holding a pill with a `detail` suffix (`"Активный · песочница по умолчанию"`) that wraps to three lines.

**Keep.**
- **The status truth and its provenance comments (`:9-22`).** These map to real adapter state. Never restyle in a way that implies parity between the three.
- The `disclosure` note.
- Text label beside every status dot.

**Rework.**
- Differentiate `beta` from `planned` visually while keeping both non-green (e.g. outline vs. filled chip, or an explicit progress rail).
- Add the route visualisation from C1: *signal → gate → route → broker*, tying this section to the pipeline.
- Promote the market label out of quaternary.
- **Logos: flag, do not assume.** Third-party marks (T-Invest, Bybit, Finam) carry trademark-usage questions, and a Finam logo beside `planned` overstates the relationship. See §14, D5.

**Components involved.** `Section`, `SectionHeader`, `Surface`, `StatusPill`, `Reveal`, `BROKER_STATUS_TONE`.
**Files likely to change.** `brokers/brokers-section.tsx`, `lib/strategy-status.ts` (tone differentiation), **new** `ui/status-chip.tsx`, **new** `ui/route-diagram.tsx`.

---

## 13. §10 — Strategy laboratory · §11 — Безопасность · §12 — Pricing · §13 — Access · §14 — FAQ · §15 — Footer

### §10 — Strategy laboratory (`#strategies`)
**Files:** `strategies/strategies-section.tsx` (104), `strategies/strategy-table.tsx` (113), `content/{ru,en}/strategies.json`

- **Purpose.** A 4-stage status ladder (active/forward/candidate/frozen) with occupancy counts, a current-state note, and the register of 3 real strategies.
- **Problems.** The ladder is a 4-cell `gap-px` strip that reads as a table header, not as a progression — no arrow, no direction, no connector between stages. Two of four stages are empty (`active: 0`, `candidate: 0`) and show a bare `0`, which reads as missing data rather than as discipline. The register table has **five columns and three rows** at 1440 — a lot of chrome for three records. Two disclosure paragraphs stack under it in near-identical quaternary grey.
- **Raw.** The empty-stage dot is `border: 1px solid var(--color-border-strong)` with `backgroundColor: transparent` set via **inline style** (`:59-62`) rather than a class — the only place on the page doing this.
- **Reference conflict (C2).** Reference shows a ladder as a proper table with per-row status chips and a light background. Current ladder and table are two separate treatments of the same taxonomy.
- **Bugs.** Table is `min-w-[680px]` in `overflow-x-auto` with `data-lenis-prevent-horizontal` — measured at 390: container 358, content 702, **344px reachable only by horizontal gesture**. Correct implementation (documented `:17-31`), but there is **no visual scroll affordance** — no fade edge, no hint. `md:grid-cols-4` with no 2-up step.
- **Keep.** No metrics column (`:8-11`) — status *is* the information. `frozen` is muted, never red (`lib/strategy-status.ts:19-22`). The hand-maintained caveat. `data-lenis-prevent-horizontal`.
- **Rework.** Ladder as a directional progression with a connector; empty stages stated as "не занято" rather than `0`; merge the two disclosures; add a scroll affordance to the table; consider card-per-strategy at `<md` instead of a horizontal scroller.
- **Files.** `strategies/strategies-section.tsx`, `strategies/strategy-table.tsx`, **new** `ui/scroll-affordance.tsx`, `ui/status-chip.tsx`.

### §11 — Безопасность (`#safety`) — *not in the brief's list; do not drop*
**File:** `safety/safety-section.tsx` (57)

- **Purpose.** The most important section, because Quant can place orders in a real brokerage account. Six items, two of which state where the guarantee is **incomplete** (no automatic kill switch; the vault is opt-in).
- **Problems.** Six identical cards, `md:grid-cols-2 lg:grid-cols-3`. The two *incomplete-guarantee* items (`item4`, `keysCaveat`) look exactly like the four reassuring ones — the honesty is present in the copy and invisible in the design. That is a real missed opportunity: the caveats are the differentiator.
- **Raw.** The `keysCaveat` uses the same `border-l-2 pl-5` treatment as four other notes across the page, in 13px tertiary.
- **Reference conflict.** No direct fragment. Nearest is B2's three-card foundation grid — but six cards is already the page's densest uniform grid.
- **Keep.** Every claim and its code provenance (`:7-23`). **The incomplete-guarantee items must never be softened or visually equalised upward.**
- **Rework.** Split into "гарантии" (4) and "границы гарантии" (2) with distinct treatment; give the caveats *more* weight, not less.
- **Files.** `safety/safety-section.tsx`, **new** `ui/aside-note.tsx`.

### §12 — Pricing (`#pricing`)
**File:** `pricing/pricing-section.tsx` (106)

- **Purpose.** Three tiers + five Live gates + CTA. Prices: `"Бесплатно" / "Планируется" / "Планируется"`.
- **Problems.** **No emphasised tier** — deliberate, and well-reasoned (`:13-22`: there is no payment code anywhere in the repo, so highlighting an unpriced unavailable tier is a conversion pattern with nothing behind it). The reference (C3) emphasises the middle card. This is a **direct, principled conflict** — see §14, D4. Two of three cards show the same word `"Планируется"` as their price, so the pricing table's most prominent typography is a repeated placeholder. The five Live gates are pill-shaped `<li>`s that **look like filter chips but are not interactive** — a false affordance.
- **Raw.** `Surface` `featured` variant exists (`glass-premium-featured`, gradient border via `mask-composite`) and is **used nowhere**. Built for pricing, unused by pricing.
- **Keep.** Honest prices. No fake "Recommended" badge on an unavailable tier. Live gates inline rather than presenting Live as unrestricted.
- **Rework.** Emphasise the tier that is actually available today (**Explore/free**), not the middle one — that is honest *and* satisfies the reference's compositional need for a focal card. Make the gates read as requirements (checklist), not as chips. Use or delete the `featured` variant.
- **Files.** `pricing/pricing-section.tsx`, **new** `ui/pricing-card.tsx`, `ui/surface.tsx`.

### §13 — Access / Final CTA (`#access`)
**Files:** `access/access-section.tsx` (92), `access/access-form.tsx` (177), `app/api/beta/route.ts`, `lib/beta/{schema,adapter}.ts`

- **Purpose.** The single conversion point. Sandbox request (form, primary) + Live access (link, secondary, gated).
- **Problems.** Two unequal asks side by side at `1.1fr / 0.9fr` read as near-equal. The trust list uses green dots — the only place green appears outside trade semantics, which quietly weakens the "green means a trade state" rule. The reference (C4) makes the final CTA a **contained black panel** with a single dominant action; the current section is a two-column form layout.
- **Raw.** The `glow` here is the one non-`.section-glow` background on the page — an inline `radial-gradient` with `--color-accent-glow` (`:30-38`). One-off.
- **Keep.** The two-tier ask. `AccessForm` and its whole path (react-hook-form + zod + `/api/beta`). The `consentNote`. The `successUndelivered` state — it tells the truth when the adapter fails.
- **Rework.** Recompose as reference C4: contained panel, headline centred or left, one dominant CTA, form revealed or inline beneath. Re-tone the trust dots away from success-green.
- **Files.** `access/access-section.tsx`, `access/access-form.tsx` (styling only — **do not touch the submit path**), `ui/surface.tsx`.

### §14 — FAQ (`#faq`)
**File:** `faq/faq-section.tsx` (51)

- **Purpose.** Ten questions, native `<details>`/`<summary>`, `width="prose"` (68ch).
- **Problems.** Ten rows of hairline-separated text at 68ch inside a 1280 container — the narrowest block on the page, so it reads as a different site. `+` → rotate-45 is the only affordance; no hover background, no row highlight. The section has **no eyebrow and no lead** (only `heading`), the only such section.
- **Raw.** A bare `+` glyph as the disclosure indicator, at `--color-text-tertiary`, 20px line-height. Functional, unstyled.
- **Keep.** **Native `<details>`.** `:8-21` records that the previous JS accordion was the heaviest and least accessible block on the page and set `outline: none` with no replacement. Native gives keyboard, SR semantics and find-in-page for free. Do not replace with a JS accordion for the sake of a height animation.
- **Rework.** Row hover/focus background; a designed chevron; optional 2-column at `xl`; give the prose column a `SurfaceCard` container so it stops floating.
- **Files.** `faq/faq-section.tsx`, `ui/section.tsx` (prose width behaviour).

### §15 — Footer
**File:** `footer/footer.tsx` (77)

- **Purpose.** Brand, tagline, honest closed-testing status, 4 links, legal, build SHA + deploy time.
- **Problems.** Two columns then a rule then legal — the thinnest block on the page (`py-16` = 128px, vs. 201.6px section padding above it). Four links in a single vertical stack; the reference (C4) shows **four labelled columns**. No locale switch in the footer.
- **Raw.** `buildLabel + sha` renders as `dev` in local/preview builds — visible placeholder text in the footer whenever `NEXT_PUBLIC_BUILD_SHA` is unset.
- **Keep.** `status` as `"закрытое тестирование"` — `:5-10` records that the previous "Systems operational" pulsing dot was a live-status claim with no telemetry. **Never reintroduce a pulsing status dot here.** Build SHA/time as genuine provenance.
- **Rework.** Multi-column link layout per C4; add locale switch; hide the build line when SHA is `dev`; align footer padding to the section scale.
- **Files.** `footer/footer.tsx`.

---

## 14. Decisions required before the build phase

These change the outcome materially and are the owner's call, not the implementer's.

| ID | Decision | Why it needs a decision | Recommendation |
|---|---|---|---|
| **D1** | **Light/inverted sections.** The reference makes Audience, Foundation, Telegram, Execution and Pricing **light**. The site is currently 100% black and `--color-paper: #f4f2ec` is declared but unused. | This is the largest single visual change in the whole redesign and it is not reversible cheaply — it affects every card, border and text token in five sections, doubles the contrast-checking surface, and changes what "premium black" means for the brand. | **Adopt, but narrowly:** two light bands maximum (Foundation + Pricing/Execution), not five. Keeps the reference's rhythm and the "deep black base" brief simultaneously. Needs a full second contrast pass. |
| **D2** | **Cold blue/cyan accent.** `color.css:1-16` currently states a hard rule: no brand hue exists; a coloured non-trade pixel is a bug. | The rule is load-bearing (it is what killed the orange) and enforced by `check:design`. Adding cyan must be an explicit amendment with its own boundary, not an exception. | **Adopt as glow-only.** Cyan may appear in `box-shadow`, `radial-gradient`, SVG `stroke` on decorative geometry. It may **never** be a text colour, a border on a text container, a status colour, or a CTA fill. Encode that as a new `check:design` rule so it cannot drift. |
| **D3** | **Radius scale.** 8px → 16/20/24px. | Touches every surface; `--radius` also feeds the shadcn bridge in `globals.css:504-508`. | Adopt. Add `--radius-2xl` and **actually consume it in a utility** or it tree-shakes away (G8). |
| **D4** | **Pricing emphasis + prices.** Reference shows `$10/$30/$50` with the middle card emphasised. Site shows `Бесплатно / Планируется / Планируется` with no emphasis, deliberately. | Copying the reference's prices would be fabricating a commercial offer that has no payment code behind it. | **Keep the honest prices.** Take only the *composition* from C3, and emphasise the tier that is actually available (Explore). |
| **D5** | **Broker logos.** Reference C1 shows T-Invest / Bybit / Finam marks. | Third-party trademarks; and a Finam logo next to `planned` overstates a relationship that is nine `NotImplementedError`s. | Use logos only for `active` and `beta` (T-Invest, Bybit) **if** usage rights are confirmed; keep Finam text-only. Default to text-only until confirmed. |
| **D6** | **Pipeline spine mechanism.** Reference B1 wants a vertical spine. | The last attempt at a scroll-driven pipeline was a pinned GSAP track that produced four documented defects including the backward-scroll bug (brief item #10). | **Hard constraint, not a decision:** the spine is CSS layout + IntersectionObserver only. No `ScrollTrigger`, no pinning, no scroll-linked transform, no nested scroll container. |
| **D7** | **Section splitting.** Extract `#foundation` (and possibly `#confidence`) out of `#how-it-works`. | Adds a `foundation` i18n namespace in **both** locales (gated by `check:i18n`) and a new nav/footer entry. | Adopt. Highest structural value per unit of risk. |

---

## 15. Verification gaps that must be closed before the build phase

| Gap | Fix required |
|---|---|
| `npm run typecheck` does not exist (**G10**) | Add `"typecheck": "tsc --noEmit"` to `website/package.json`. Note `tsconfig.tsbuildinfo` is present, so incremental is already configured. |
| Playwright not installed (**G11**) | Either add `@playwright/test` + a `tests/visual/` suite with 1440/390 projects, **or** declare the Playwright MCP server as the verification path and accept that nothing is committed. Recommend the former for a redesign of this size. |
| `check:design` budgets will move | The `raw-white-alpha` budget is **6** and currently near its cap. New glass/glow work will push past it. Plan to either route new alphas through tokens (preferred) or ratchet the budget **with a written reason** — the script's own doctrine is "budgets may go down, never up". |
| No visual-regression baseline | Capture 1440 + 390 full-page baselines of the *current* build before the first component change, so the redesign can be diffed rather than eyeballed. |
| `gsap` dead dependency (**G9**) | Remove, or the build phase will keep pulling 400+ KB of unused library into the lockfile audit surface. |

---

## 16. Severity roll-up

**Must fix for the reference to be met**
G1 radius · G2 no cold accent · G13 hero framed as a window · §4 audience not connected/not clickable · §7 pipeline is a grid not a spine · §9 foundation has no identity · §10 dashboard composition inverted

**Should fix**
G3 light bands (pending D1) · G4 uneven rhythm · G5 anchor dead-space · G6 clickable affordance · G7 label inflation · G12 page length · §11 safety caveats visually equalised · §12 pricing has no focal card · §13 final CTA not a contained panel

**Housekeeping**
G8 `--radius-xl` empty · G9 dead `gsap` · dead `hero-video.tsx`/`hero-media.ts` · `rounded-xl` and inline alphas in `mobile-nav.tsx` · footer `dev` SHA · missing `design-references/` folder

**Blockers for the stated verification protocol**
G10 no `typecheck` script · G11 no Playwright

---

*End of audit. Implementation mapping continues in `REFERENCE_IMPLEMENTATION_PLAN.md`.*
