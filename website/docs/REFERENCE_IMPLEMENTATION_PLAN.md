# REFERENCE_IMPLEMENTATION_PLAN.md — mapping the approved Gemini Stitch reference onto the Quant site

**Date:** 2026-07-27
**Companion document:** [`SITE_BLOCK_AUDIT.md`](./SITE_BLOCK_AUDIT.md) — read that first; findings are referenced here as **G1…G13** and **D1…D7**.
**Reference:** Stitch board `2281049485843837902`, node `26010fea5161491c9c723b7f5a8b7709` — *"Quant Full Site Redesign Concept"*. Treated as **art direction**, not as spec.
**Status:** plan only. No production code in this phase.

**Non-negotiables carried from the current build into every item below**
1. No fake results. No win rate, profit factor, PnL, Sharpe, equity curve, sample size, or return figure — anywhere, in any state, under any disclaimer.
2. Honest statuses. Broker states derive from real adapter state; strategy states are hand-maintained and must be labelled as such; prices stay `Бесплатно / Планируется / Планируется`.
3. Both locales ship together. `check:i18n` gates parity; a new namespace in `en.json` without `ru.json` fails the build.
4. Backend / trading-core untouched. Nothing under `bot/`, `knowledge/`, `tests/`, `infra/`.
5. No pinning, no scroll-linked transforms, no nested scroll containers. IntersectionObserver only. (**D6**)
6. Reduced motion must degrade to a still, correct page — never to an invisible one.

---

## PART I — DESIGN TOKENS

All tokens live in `src/styles/tokens/`. Three of the five files change; two are new.

### 1.1 Colour — `styles/tokens/color.css`

The file's current doctrine ("there is no brand accent hue; a coloured non-trade pixel is a bug") is **amended, not deleted**. The new rule:

> The palette is monochrome for everything that carries meaning. Cold blue exists as **light**, not as ink: it may appear in `box-shadow`, `radial-gradient`, and SVG `stroke` on decorative geometry. It may never be a text colour, a border on a text container, a status colour, or a CTA fill. Green and red remain trade semantics only.

```
/* ─── Background ─── */
--color-bg               #030303   (unchanged — the deep black base)
--color-bg-elevated      #060607   (new — hero panel / final-CTA panel ground)

/* ─── Surface ─── */
--color-surface          #0a0a0a   (unchanged — resting card)
--color-surface-hover    #111111   (rename of --color-panel; same value)

/* ─── Surface elevated ─── */
--color-surface-elevated #111111   (nested panels, terminal chrome)
--color-surface-raised   #171717   (rename of --color-panel-raised; hover of elevated)

/* ─── Inverted band (D1) ─── */
--color-paper            #f4f2ec   (already declared, currently unused)
--color-paper-surface    #ffffff   (cards on paper)
--color-on-paper         #030303
--color-on-paper-secondary  rgba(3,3,3,0.68)
--color-on-paper-muted      rgba(3,3,3,0.52)
--color-border-on-paper     rgba(0,0,0,0.10)   (exists as --color-line-light; rename)

/* ─── Border ─── */
--color-border           rgba(255,255,255,0.10)   hairline, decorative
--color-border-strong    rgba(255,255,255,0.35)   3.0:1 — interactive edges
--color-border-hover     rgba(255,255,255,0.28)   (rename of --color-highlight-border)

/* ─── Text (contrast vs #030303, unchanged and already verified) ─── */
--color-text-primary     #ffffff                  20.4:1
--color-text-secondary   rgba(255,255,255,0.72)   10.4:1
--color-text-muted       rgba(255,255,255,0.56)    6.5:1   (rename of -tertiary)
--color-text-faint       rgba(255,255,255,0.48)    4.9:1   HARD FLOOR (rename of -quaternary)

/* ─── White CTA ─── */
--color-cta              #ffffff
--color-cta-fg           #030303
--color-cta-hover        rgba(255,255,255,0.88)
--shadow-cta-rest        0 4px 20px rgba(255,255,255,0.10)
--shadow-cta-hover       0 8px 30px -6px rgba(255,255,255,0.18)

/* ─── Cold blue accent — LIGHT ONLY (D2) ─── */
--color-signal           #7cc8ff   /* decorative stroke only, never text */
--color-signal-core      #b8e3ff   /* aperture core / node centres */
--color-signal-dim       rgba(124,200,255,0.16)
--color-signal-line      rgba(124,200,255,0.28)   /* SignalLine stroke */

/* ─── Glow ─── */
--glow-signal-sm    0 0 16px rgba(124,200,255,0.18)
--glow-signal-md    0 0 40px rgba(124,200,255,0.16)
--glow-signal-lg    0 0 120px rgba(124,200,255,0.12)
--glow-white-soft   radial-gradient(ellipse 70% 50% at var(--glow-x,50%) var(--glow-y,0%),
                    rgba(255,255,255,0.035), transparent 70%)   /* = current .section-glow */
--glow-aperture     radial-gradient(circle at 50% 45%,
                    rgba(124,200,255,0.20) 0%,
                    rgba(124,200,255,0.06) 35%,
                    transparent 68%)

/* ─── Card shadows ─── */
--shadow-card-rest   0 1px 2px rgba(0,0,0,0.40)
--shadow-card-hover  0 18px 48px -12px rgba(0,0,0,0.75),
                     0 0 0 1px rgba(255,255,255,0.08),
                     0 0 32px -8px rgba(255,255,255,0.09)
--shadow-panel       0 24px 80px -32px rgba(0,0,0,0.90)

/* ─── Trade semantics — unchanged, do not touch ─── */
--color-success #7fd8a8 · --color-danger #f08a9c · --color-neutral #8a8a8a
```

**Ceiling on cyan.** Peak alpha anywhere is `0.28`, and only on a `stroke`/`shadow`. If a reviewer can name the colour of the page, it is too strong. This is the guard against "crypto-neon".

**Renames.** `-tertiary → -muted` and `-quaternary → -faint` touch ~120 call sites. Do them as one mechanical commit, alone, before any visual work — or skip them and keep the current names. Do **not** interleave a rename with a redesign.

### 1.2 Radius — new file `styles/tokens/radius.css` (**G1, G3, G8**)

```
--radius-xs    4px     chips, dots, inline code
--radius-sm    8px     buttons, inputs, small controls
--radius-md    12px    nested panels, terminal rows
--radius-lg    16px    cards  ← was 8px
--radius-xl    20px    large panels, terminal frame
--radius-2xl   24px    hero panel, final-CTA panel
--radius-full  9999px  pills, status chips
```

> **G8 trap.** Tailwind v4 emits a `@theme` variable only when a utility consumes it — that is why `--radius-xl` currently resolves to an empty string. Every token above must be referenced by at least one `rounded-[var(--radius-*)]` in `src/`, **or** declared in a plain `:root {}` block rather than `@theme`. Verify with `getComputedStyle(document.documentElement).getPropertyValue('--radius-2xl')` after the first build.

The shadcn bridge in `globals.css:504-508` derives `--radius-sm/md/lg/xl` from a single `--radius: 0.5rem`. That derivation must be replaced with direct references, or shadcn components will keep the old 8px scale.

### 1.3 Spacing — `styles/tokens/spacing.css` (**G4, G5**)

```
--space-section-y        clamp(96px, 11vw, 176px)    (was 80/10vw/160)
--space-section-y-major  clamp(128px, 15vw, 232px)   (was 112/14vw/224)
--space-section-y-tight  clamp(72px, 8vw, 112px)     (was 56/7vw/96)

--space-page-x           clamp(24px, 8vw, 120px)     unchanged
--space-grid-gutter      24px                         unchanged
--space-content-max      1280px                       unchanged
--space-prose-max        68ch                         unchanged

/* new — the section-internal scale, currently ad-hoc mt-14 / mt-12 / mt-10 */
--space-header-to-body   clamp(48px, 5vw, 72px)      header → first content
--space-block            clamp(32px, 3.5vw, 48px)    between blocks inside a section
--space-card-gap         20px                         grid gutter between cards
```

**Rhythm rule (fixes G4).** After the change the target content-to-content gaps are: `major → 232+232 = 464` at the joints that open a movement, `default → 352`, `tight → 224`. The current outliers — hero→audience **225** and how→dashboard **404** — resolve because the hero stops being followed by a `default` section and `#how-it-works` stops being 2 563px long once `#foundation` is extracted (**D7**).

**Anchor landing (fixes G5).** `Section` gains `scroll-padding` behaviour: the anchor target becomes an inner marker positioned at `paddingTop - 32px`, not the section box. Implemented as an empty `<span id={id} class="absolute -top-[...]" aria-hidden>` inside the section, with the section itself keeping a non-anchoring id — or equivalently by reducing `scroll-margin-top` per rhythm. Either way the acceptance test is: **after anchor navigation, the section eyebrow sits 104–160px from the viewport top, never 335px.**

### 1.4 Typography — `styles/tokens/typography.css`

Six roles today, 8 rendered sizes measured — the system works. Changes are additive only.

```
--text-label              11px / 1.4 / 0.14em      unchanged
--text-caption            13px / 1.5 / -0.006em    unchanged
--text-body               16px / 1.65 / -0.011em   unchanged
--text-lead               18px / 1.6 / -0.013em    unchanged
--text-h3                 20px / 1.35 / -0.018em   unchanged
--text-section-heading    clamp(1.75rem, 3.5vw, 3rem)      unchanged
--text-hero               clamp(2.5rem, 4.6vw, 4.5rem)     ← was clamp(2.25rem,3.8vw,3.75rem)
--text-display-number     clamp(1.75rem, 3vw, 2.5rem)      unchanged

/* new */
--text-h2-sub             clamp(1.25rem, 2vw, 1.5rem)   node titles on the pipeline spine
--text-numeral            clamp(2rem, 4vw, 3.25rem)     the 01/02/03 in Foundation
```

Hero goes from 54.72px → **66px at 1440**, which restores the reference's headline dominance (**G13**). Both families already load latin + cyrillic; `--text-hero` at 66px must be re-checked in RU for the 3-line break.

**Label rationing (G7).** 127 rendered `--text-label` instances. Target ≤ 70. `MonoLabel`'s own docstring cites "max 1 per 3 sections"; the practical rule for this build: **one eyebrow per section, plus mono only for genuinely technical strings** (tickers, module names, `sourceRef`, timeframes, status words). Remove it from decorative captions and from the hero proof strip's separators.

### 1.5 Motion — `styles/tokens/motion.css`

```
--duration-micro    150ms    colour / opacity on hover
--duration-base     300ms    card state change
--duration-reveal   800ms    ← was 600ms; matches the reference's 0.8s
--duration-panel    500ms    tab / panel swap
--duration-orbit-a  32s      Q-aperture outer orbit
--duration-orbit-b  46s      middle
--duration-orbit-c  61s      inner  (three coprime periods → never resync)
--duration-breathe  9s / 11s / 13s   ring opacity (current values, keep)

--ease-out-expo   cubic-bezier(0.16, 1, 0.3, 1)
--ease-out-quart  cubic-bezier(0.25, 1, 0.5, 1)
--ease-out-quint  cubic-bezier(0.22, 1, 0.36, 1)   ← the reference's "quint"; already
                                                     the literal used in Reveal
--ease-lenis      cubic-bezier(0.32, 0, 0.15, 1)
```

**Motion contract.** Every loop is `opacity` / `transform` / `stroke-dashoffset` only. No keyframe uses `animation-fill-mode`, so the base style *is* the resting state and the reduced-motion reset (duration → 0.01ms, iterations → 1) yields a still, correct instrument. **Never add an opacity ramp to the hero entrance** — `globals.css:120-127` records that it cost ~150ms of LCP by disqualifying the subtree as an LCP candidate.

### 1.6 Z-index — `styles/tokens/z-index.css`
Unchanged. `--z-base 0 · --z-nav 40 · --z-modal-backdrop 80 · --z-modal 90 · --z-toast 100 · --z-tooltip 110`. New decorative layers (grid backplate, signal lines) use negative z-index **inside their own stacking context**, never a new global tier.

---

## PART II — REUSABLE COMPONENTS

Eleven required by the brief. Six are new, five are refactors of what exists. Props below are the **contract**, not implementation.

| # | Component | File | Status | Notes |
|---|---|---|---|---|
| 1 | `PremiumSection` | `ui/premium-section.tsx` | **refactor** of `ui/section.tsx` | Adds `tone` and `connector`. |
| 2 | `SectionHeader` | `ui/section-header.tsx` | **keep + extend** | Already correct; add `tone` and `align="split"`. |
| 3 | `GlassPanel` / `SurfaceCard` | `ui/surface.tsx` | **split** | `SurfaceCard` = the 95% case. `GlassPanel` = HUD over imagery only. |
| 4 | `InteractiveCard` | `ui/interactive-card.tsx` | **new** | The whole card is one link. Fixes **G6**. |
| 5 | `SignalLine` | `ui/signal-line.tsx` | **new** | The connective tissue. Audience→pipeline, spine, route diagram. |
| 6 | `QMark` / `BrandMark` | `ui/brand-mark.tsx` | **refactor** of `ui/monogram.tsx` | Sizes + optional glow. |
| 7 | `StatusChip` | `ui/status-chip.tsx` | **refactor** of `ui/status-pill.tsx` | Adds `variant` so `beta` ≠ `planned` visually. |
| 8 | `TerminalPanel` | `ui/terminal-panel.tsx` | **new** (extract) | Chrome pulled out of `dashboard-terminal.tsx`. |
| 9 | `PricingCard` | `ui/pricing-card.tsx` | **new** (extract) | With an honest `emphasis` flag. |
| 10 | `RevealOnScroll` | `motion/reveal.tsx` | **keep, rename export** | Already correct. Do not rewrite. |
| 11 | `MagneticButton` / button system | `ui/button*.tsx`, `ui/magnetic.tsx` | **keep + consolidate** | Already correct. |

Supporting new primitives (not in the brief, needed by it): `ui/grid-backplate.tsx`, `ui/aside-note.tsx`, `ui/device-frame.tsx`, `ui/scroll-affordance.tsx`, `hero/q-aperture.tsx`, `how-it-works/pipeline-spine.tsx`, `hooks/use-active-section.ts`.

### 2.1 `PremiumSection`

```ts
type Tone   = "dark" | "paper";              // D1
type Rhythm = "hero" | "major" | "default" | "tight";

interface PremiumSectionProps {
  id: string;
  rhythm?: Rhythm;                 // default "default"
  tone?: Tone;                     // default "dark"
  width?: "content" | "prose";
  divider?: boolean;
  glow?: ReactNode;                // clipped, aria-hidden
  connector?: "in" | "out" | "both" | false;  // SignalLine at the seam
  labelledBy?: string;
  className?: string;
  children: ReactNode;
}
```

**Preserve verbatim from `ui/section.tsx`:**
- `overflow-hidden` is **never** set on the `<section>`. Clipping lives on the glow layer. (An `overflow-hidden` ancestor silently disables ScrollTrigger pinning and constrains the page — documented at `section.tsx:41-48`.)
- One inner container at `--space-content-max`, so header and content share one left edge.
- `divider` is a prop, not an nth-child selector.
- `SectionBleed` escapes horizontal padding only — **never `100vw`**, which disagrees with the scrollbar and creates horizontal overflow at exactly the desktop widths this page cares about.

**New in `tone="paper"`:** sets `--section-bg`, `--section-fg`, `--section-border`, `--card-bg`, `--card-bg-hover` on the section, so every descendant card inverts through the existing custom-property plumbing without a single component learning about paper.

### 2.2 `SurfaceCard` / `GlassPanel`

```ts
type SurfaceVariant = "flat" | "raised" | "featured";
interface SurfaceCardProps extends ComponentPropsWithoutRef<"div"> {
  variant?: SurfaceVariant;   // default "flat"
  interactive?: boolean;      // default true — every card highlights
  padding?: "sm" | "md" | "lg";
}
interface GlassPanelProps extends ComponentPropsWithoutRef<"div"> {
  blur?: "sm" | "md";
  bordered?: boolean;
}
```

`.card-premium` (globals.css) stays exactly as-is and is the single hover/focus language:
- `@media (hover: hover) and (pointer: fine)` gate — a `:hover` rule sticks after a tap on touch and reads as a stuck selected state.
- `:focus-within` **and** `:focus-visible`, so a card containing a link highlights on keyboard focus.
- The lift is the only part inside `@media (prefers-reduced-motion: no-preference)`; border/background/shadow are not motion and stay.
- Background changes via `background-color`, not a translucent `::after` veil, so body copy keeps full contrast.

`GlassPanel` must keep the `@supports (backdrop-filter: blur(1px))` wrapper from `globals.css:293-302`. Lightning CSS collapses the unprefixed property away otherwise and every glass surface silently loses its blur.

### 2.3 `InteractiveCard` — fixes **G6** / brief item #7

```ts
interface InteractiveCardProps {
  href: string;
  label: string;                    // the visible CTA text
  analytics?: { target: CtaTarget; location: string };
  index?: number;                   // stagger
  eyebrow?: ReactNode;              // "01" or a route glyph
  children: ReactNode;
}
```

Pattern: `SurfaceCard` is `position: relative`; a single `<a>` carries an `::after { position:absolute; inset:0 }` overlay. One tab stop, one focus ring on the card, `cursor: pointer` on the whole surface, nested text still selectable. Hover = the shared `.card-premium` state **plus** a cold-blue edge (`--color-signal-line` at 1px) and the arrow travelling 4px.

Applies to: 3 Audience cards, the Access "Live" card. (Measured: those 4 are the only cards with a link and `cursor: default`.)

### 2.4 `SignalLine`

```ts
interface SignalLineProps {
  orientation: "vertical" | "horizontal" | "bracket";
  /** "draw" animates stroke-dashoffset on reveal; "static" for reduced motion / decoration */
  behaviour?: "draw" | "static";
  nodes?: { at: number; state?: "idle" | "active" }[];  // 0..1 along the line
  index?: number;
  className?: string;
}
```

Rules:
- **In-flow, never absolutely positioned across a section boundary.** A cross-section absolute connector needs re-derivation at every breakpoint and misaligns the moment a card grows a line. The audience→pipeline bracket is owned by the audience section's bottom edge.
- SVG, `stroke: var(--color-signal-line)`, `--glow-signal-sm`.
- Draws via `stroke-dashoffset` only (compositor-safe, same technique as the existing `hero-vector`).
- Under reduced motion: renders fully drawn, immediately.
- Hidden below `md` where the layout is single-column and the line would be a vertical hairline with nothing to connect.

### 2.5 `QMark` / `BrandMark`

```ts
interface BrandMarkProps extends SVGProps<SVGSVGElement> {
  size?: "xs" | "sm" | "md" | "lg";   // 16 / 20 / 24 / 40 px
  glow?: boolean;                      // adds --glow-signal-sm; hero + aperture only
}
```

Geometry is **unchanged** — 320° ring with a 40° blade opening at upper right, tail at 45° spanning 0.52r→1.32r. It is shared with `scripts/media/build-poster.mjs`; changing it here desyncs the poster. Single-weight stroke, `currentColor`, so it inherits in nav, footer and on paper. `glow` is off everywhere except the hero.

### 2.6 `StatusChip`

```ts
type StatusTone = "signal" | "success" | "danger" | "muted";
interface StatusChipProps {
  tone: StatusTone;
  label: string;                       // ALWAYS rendered — never colour-only
  detail?: string;
  variant?: "solid" | "outline";       // NEW — separates beta from planned
  pulse?: boolean;                     // live telemetry only
}
```

`variant="outline"` is the fix for the Bybit/Finam collision: both stay non-green (correct — neither is production-ready), `beta` becomes `solid muted`, `planned` becomes `outline muted`. **`pulse` stays reserved for genuine live telemetry.** The footer's old "Systems operational" pulsing dot was a claim with no telemetry behind it; do not reintroduce it.

### 2.7 `TerminalPanel`

```ts
interface TerminalPanelProps {
  title: string;
  mode: { label: string; value: string };
  tabs?: { id: string; label: string; desc?: string }[];
  activeTab?: string;
  onTabChange?: (id: string) => void;
  footnote?: ReactNode;
  children: ReactNode;
}
```

Extracted from `dashboard-terminal.tsx`. Replaces the three grey traffic-light dots with `BrandMark size="xs"` + mode chip. **The entire WAI-ARIA tablist implementation moves across intact** — roving focus, `aria-selected`, `aria-controls`, Arrow/Home/End, one tab in the focus order, panels in DOM order after the tablist. Every scrollable table keeps `data-lenis-prevent-horizontal` (**not** the bare attribute — that is what causes the backward lurch).

### 2.8 `PricingCard`

```ts
interface PricingCardProps {
  tier: string;
  price: string;          // pre-formatted; "Бесплатно" / "Планируется"
  available: boolean;     // drives emphasis — NOT a marketing choice
  body: string;
  features: string[];
  cta?: { href: string; label: string };
}
```

`emphasis` is derived from `available`, never hand-set. Today that means **Explore** is the focal card, because it is the only tier that exists. This satisfies the reference's compositional need for a focal card without inventing a commercial offer (**D4**). Uses the `featured` Surface variant, which is already built (`glass-premium-featured`, gradient border via `mask-composite`) and currently used nowhere.

### 2.9 `RevealOnScroll`

**Keep `motion/reveal.tsx` as-is.** Only two changes: export an alias `RevealOnScroll`, and raise the default duration 0.7 → 0.8s to match the reference.

Do not touch the rest. The current implementation encodes three hard-won facts:
- `whileInView` / IntersectionObserver — reads no scroll events and drives no scroll position, so it cannot desync from Lenis the way a scroll-linked tween can.
- `amount: 0.2`, not higher — a tall card on a 390px viewport may never have 25% on screen, and the reveal would never fire.
- `initial` **must not** branch on the reduced-motion preference. It is `false` on the server and the user's real value on the client; `initial={false}` there strands the server-rendered `opacity: 0` forever. Measured: all 32 cards stuck invisible. Collapse the *duration* instead.

70 `[data-reveal]` wrappers exist. Do not add many more — the stagger reads as a queue past ~4 siblings.

### 2.10 Button interaction system

`Button` (cva) + `ButtonLink` + `ArrowLink` + `Magnetic` are already the consolidated system and are correct. Changes:
- `--radius-md` for buttons follows the new scale (8px).
- `Magnetic` unchanged. Its `style` must stay **unconditional** — `style={reduce ? undefined : {x,y}}` looks like a behaviour branch but is a markup branch, and React reported it as a real hydration error for every reduced-motion user across all 5 instances. Behaviour branches inside the handler; markup never.
- `ArrowLink` keeps `-my-2.5 / py-2.5` — that is what gets the hit area to ≥44px without changing the visual rhythm.
- New: a `signal` variant on `Button` — outline with a cold-blue edge glow on hover, for secondary CTAs inside dark panels.

---

## PART III — SECTION-BY-SECTION IMPLEMENTATION

Each entry: reference fragment → composition → grid → cards → hover → scroll → mobile → tokens → components → acceptance criteria.

---

### III.1 Header / Navigation

**Reference fragment:** **A1**.

**Composition.** Two states. *Top state* (scrollY < 100): no pill, no background — wordmark, nav, locale, CTA sitting directly on the hero, with only `.nav-scrim` fading the page beneath. *Compact state* (scrollY ≥ 100): the glass pill materialises, height 78 → 64px, padding tightens, the active nav item carries a 1px underline. Transition 300ms `--ease-out-expo` on `background-color`, `height`, `backdrop-filter`.

**Grid.** `wordmark | nav (centre) | locale · CTA`. `max-w: 1280px` — shares the page's left edge. Nav visible from `md` (768px), not `lg`.

**Cards.** None.

**Hover states.** Nav link: `--color-text-muted → --color-text-primary`, 150ms, plus the underline growing from `scaleX(0)` at the active item only. Locale toggle: same. CTA: existing white-fill hover + `-translate-y-px` + `--shadow-cta-hover`.

**Scroll animations.** One IntersectionObserver over the 10 section ids feeding `useActiveSection()`. **No scroll event listener, no `getBoundingClientRect` in a rAF loop** — nothing may read or write scroll position except `scroll-driver.ts` (**D6**, brief item #10). Threshold: a section is active when its top crosses 40% of the viewport.

**Mobile rules.** `< md`: wordmark + CTA + hamburger. Dropdown `top` derives from the measured header height, not the hard-coded `68px` (measured 86px at 390 → an 18px gap today). Panel radius → `--radius-xl`, replacing the raw `rounded-xl`. The two inline `rgba(255,255,255,0.0x)` values go through `--color-fill-subtle` / `--color-highlight-bg`.

**Tokens.** `--radius-xl`, `--color-bg`, `--color-border`, `--duration-base`, `--ease-out-expo`, `--z-nav`.

**Components.** `BrandMark`, `ButtonLink`, `MobileNav`, `useActiveSection`.

**Acceptance criteria.**
1. At scrollY 0 the header has no visible pill background; past 100px it does; the transition never jumps.
2. Exactly one nav item carries the active underline at any scroll position, and it matches the section occupying the viewport centre.
3. `NAV_OFFSET` and `scroll-margin-top` remain equal and single-sourced. If the header height becomes state-dependent, the offset uses the **compact** height (anchor navigation always ends in the compact state).
4. Sticky header never overlaps a section heading: measured clearance ≥ 24px at 1440, 1024, 768, 390.
5. Keyboard: Tab reaches wordmark → 5 links → locale → CTA → hamburger, each with a visible focus ring.
6. No layout shift when the header changes state (CLS contribution 0 — the header is `fixed`).

---

### III.2 Hero

**Reference fragment:** **A2 + A3**.

**Composition.** A **contained dark panel** at `--radius-2xl` on `--color-bg-elevated`, inset from the page edges, with a faint grid backplate and an edge vignette. Inside: two columns. Left — eyebrow, headline (66px at 1440), subline, `[white CTA] [arrow link]`. Right — the **Q-aperture**, free-floating, no window chrome, no title bar, no status pill, no step rail. Across the panel's bottom edge, full width — the **proof strip** as a contained darker bar (A3), 5 mono items with hairline dividers.

The three configured-limit `Stat`s move **into** the proof strip row or directly beneath the aperture as part of the same object — not as a separate stack behind a hairline (**G13**).

**Grid.** `lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]`, `gap-16`. Panel `max-w: 1280px`, page padding outside it.

**Cards.** None — one panel, one instrument.

**Hover states.** CTA magnetic (radius 12, spring 300/20/0.5). Arrow link travels 4px. **The aperture does not react to hover** — `PointerTilt` gives it a ±7px pointer parallax, and per-orbit depth (outer layer moves more than inner) is the only addition. Coarse pointers get nothing.

**Scroll animations.** Entrance: `qf-hero-enter`, **transform-only**, `translateY(24px) → 0`. Never add an opacity ramp — it disqualifies the subtree as an LCP candidate for the whole delay and cost ~150ms last time. Aperture loops, all compositor-only:
- 3 orbit ellipses rotating at 32s / 46s / 61s (coprime — never resync)
- ring opacity breathing at 9s / 11s / 13s, desynced (existing `hero-ring`, keep)
- 2–3 node dots travelling their orbits via `offset-path` or `rotate` on a group
- the exit vector's dashes flowing outward (existing `hero-vector`, keep)
- one faint trace crossing the aperture every 14s (existing `hero-scan`, keep)
- core bloom pulsing `--glow-aperture` opacity 0.7 ↔ 1.0 over 8s

**Mobile rules.** Drop `min-h-dvh` below `md`; target ≤ 1.15 viewports to the CTA (currently 1 479px at 390 = 1.75 viewports). Panel inset shrinks to 16px. Aperture below the text, capped at `aspect-square`, max 320px. Proof strip wraps to two rows. Stats become a 3-up row at `--text-h3`, not `--text-display-number`.

**Tokens.** `--radius-2xl`, `--color-bg-elevated`, `--color-signal*`, `--glow-aperture`, `--glow-signal-lg`, `--text-hero`, `--duration-orbit-*`, `--shadow-panel`.

**Components.** `QAperture` (new), `GridBackplate` (new), `BrandMark glow`, `PointerTilt`, `MonoLabel`, `Stat`, `ButtonLink magnetic`, `ArrowLink`.

**Acceptance criteria.**
1. Zero figures in the aperture. No chart, no curve, no counter, no percentage, no rising line — under any caption. A moving line on a trading site is a performance claim regardless of the disclaimer.
2. The three `Stat` values remain **configured limits** (`5% / 2% / 0.20`) with their labels, verifiable against `bot/config.py:66-71`.
3. Hero renders server-side with zero client JS except `PointerTilt`. No external asset — no video, no image request.
4. LCP element is the `<h1>`, and no ancestor of it starts at `opacity: 0`.
5. Reduced motion: all orbits still, aperture legible, no layout difference.
6. Every animation is `opacity` / `transform` / `stroke-dashoffset`. Verified by reading the compiled keyframes, not by eye.
7. Cyan appears only as stroke and glow. Peak alpha ≤ 0.28. No cyan text.
8. Both locales: RU headline breaks to 3 lines at 1440 without orphans; EN to 2–3.

---

### III.3 Audience

**Reference fragment:** **A4**.

**Composition.** Eyebrow → H2 (`"Один Quant. Разный уровень контроля."`) → lead → **3 route cards** → a **bracket SignalLine descending from the card row into `#how-it-works`**. If **D1** is approved for this band, `tone="paper"`; otherwise dark with a stronger card contrast.

**Grid.** `sm:grid-cols-2 lg:grid-cols-3`, `gap-[var(--space-card-gap)]`. The 1→3 jump at `md` is removed (three Cyrillic cards at ~230px is too tight).

**Cards.** `InteractiveCard`. Each gains a route identity — `01/02/03` at `--text-label` in the corner plus the destination as an `ArrowLink`-styled affordance at the foot. Whole card is the link; targets are unchanged: `#safety`, `#how-it-works`, `#brokers`.

**Hover states.** The distinct "route" hover: `translateY(-6px)`, border → `--color-border-hover`, background → `--card-bg-hover`, **plus** a 1px cold-blue edge (`--color-signal-line`) and `--glow-signal-sm`, plus the arrow travelling 4px. `cursor: pointer` on the whole surface. Focus-visible produces the identical state with one ring around the card. Touch: no sticky hover (`hover: hover and pointer: fine` gate).

**Scroll animations.** `RevealOnScroll index={0,1,2}` → 0/80/160ms. The bracket `SignalLine` draws **after** the third card, `index={3}`, `behaviour="draw"`.

**Mobile rules.** Single column, connector hidden below `md`, cards keep full-card tap targets (≥44px everywhere), route eyebrow inline with the title.

**Tokens.** `--radius-lg`, `--color-signal-line`, `--glow-signal-sm`, `--space-card-gap`, `--duration-base`.

**Components.** `PremiumSection connector="out"`, `SectionHeader`, `InteractiveCard`, `SignalLine orientation="bracket"`, `RevealOnScroll`.

**Acceptance criteria.**
1. All three cards compute `cursor: pointer` and the entire card area navigates.
2. Exactly one tab stop per card; the focus ring surrounds the card, not the inner link.
3. The bracket visually connects the card row to the pipeline heading below at 1440 and 1024; it is absent below `md`.
4. The connector is in-flow — removing `#how-it-works` from the page does not leave a floating line.
5. No sticky hover after tap on a touch device.
6. Both locales render three equal-height cards with no orphaned arrow link.

---

### III.4 How Quant Works — pipeline spine

**Reference fragment:** **B1**.

**Composition.** Eyebrow → H2 (`"Quant не угадывает. Он проверяет."`) → lead → note → **the spine**. A single vertical `SignalLine` runs the height of the block. Seven nodes sit on it at `01…07`. Cards alternate left / right at `lg`. Dotted connectors run node → card. The loop note closes the spine as a terminal element beneath node 07, not as a full-width card.

**Grid.** `lg`: `grid-cols-[1fr_auto_1fr]` — left card column, spine column (fixed ~72px), right card column; each stage occupies one row and places its card in one side column. `md` and below: `grid-cols-[auto_1fr]` — spine on the left, all cards on the right.

**Cards.** `SurfaceCard` per stage. Content order preserved: `01` badge + step label → plain sentence (`--text-h2-sub`) → hairline → technical module name → description → `sourceRef`. `sourceRef` demoted to a `--text-label` line that does not visually floor the card.

**Hover states.** Shared `.card-premium`. **Plus:** hovering a card lights its spine node (`--color-signal-core` fill + `--glow-signal-sm`) and its dotted connector. Node and card are linked by `aria-describedby`, not by hover alone — no information is hover-only.

**Scroll animations.** The spine draws top→bottom as one continuous `stroke-dashoffset` reveal — **one `Reveal` for the whole spine**, not one per row (the current `index={i % 3}` restarts the stagger three times). Cards reveal at `index={i}` capped at 4 so the stagger does not become a queue. Nodes light as they enter.

> **Hard constraint (D6).** No `ScrollTrigger`. No pinning. No scroll-linked transform. No nested scroll container. No `data-lenis-prevent` on any wide element. The previous pinned horizontal track produced four documented defects — over-pan by ~230px, `overflow-x-auto` + transform + scroll-snap fighting each other, vertical wheel bypassing the smooth-scroll driver, and pin-vs-`overflow:hidden` constraining the entire page. This is exactly brief item #10.

**Mobile rules.** Spine left at 20px, cards full width to its right, connectors become 16px stubs. Spine hidden below 480px if it costs more than 24px of horizontal room. Card padding `--space-block / 2`.

**Tokens.** `--color-signal-line`, `--color-signal-core`, `--glow-signal-sm`, `--radius-lg`, `--text-h2-sub`, `--duration-reveal`, `--ease-out-quint`.

**Components.** `PremiumSection rhythm="major" connector="in"`, `SectionHeader`, `PipelineSpine` (new), `SignalLine orientation="vertical"`, `SurfaceCard`, `AsideNote` (new), `RevealOnScroll`, `contentSource.getPipelineStages`.

**Acceptance criteria.**
1. All seven stages present in both locales, sourced from `content/{ru,en}/engine-pipeline/*.mdx`. No copy inlined into the component.
2. Every `sourceRef` preserved and resolving to a real symbol.
3. `document.documentElement.scrollWidth === clientWidth` at 1440, 1024, 768, 390 with the section in view.
4. Scrolling through the section at speed produces **no backward jump**. Measured: `scrollY` is monotonically non-decreasing across 40 consecutive downward wheel events.
5. Zero `ScrollTrigger` instances (`gsap` removed from `package.json`).
6. Reduced motion: spine fully drawn, all nodes lit, all cards visible, no entrance.
7. The `% 3` orphan-span logic is gone; adding an 8th stage requires no layout change.

---

### III.5 Confidence bounds ("Границы уверенности")

**Reference fragment:** none directly — nearest is **B2**'s numbered-card treatment.

**Composition — recommended (option b).** Fold into the **belief-gate node (04)** of the pipeline spine as an expanded node detail: the three constants become a 3-up row inside stage 04's card, since they are literally that gate's parameters. Shortens the page (**G12**) and gives the block the identity it lacks.

**Composition — alternative (option a).** Promote to `<PremiumSection id="confidence">` with eyebrow + H2 + lead, three carded constants, and the learning-system intro as a lead paragraph.

**Grid.** Option b: `grid-cols-3` inside the stage-04 card. Option a: `sm:grid-cols-3`, cards.

**Cards.** Either way the three constants **get containers** — `SurfaceCard padding="sm"` with hover/focus (brief item #6). They are the only figures on the page and currently have the least visual protection.

**Hover states.** Standard `.card-premium`. Each constant gains a `hint` line (the `Stat` slot exists and is unused) stating the unit and the source symbol.

**Scroll animations.** Inherits the spine's node reveal (option b) or `RevealOnScroll index={0,1,2}` (option a).

**Mobile rules.** Stack to a single column below `sm`; values at `--text-h3`, not `--text-display-number`, so RU labels do not wrap unevenly.

**Tokens.** `--radius-md`, `--text-display-number`, `--text-label`.

**Components.** `Stat` (carded variant), `SurfaceCard`, `contentSource.getLearningSystemCopy`.

**Acceptance criteria.**
1. Values remain `MIN_TRADES_FOR_CONFIDENCE` and the min/max clamps from `bot/learning/belief_updater.py:37,46-47`, labelled unambiguously as **configured constants, never measured outcomes**.
2. `Stat` still receives pre-formatted strings — no `Intl` inside the component (hydration hazard).
3. Each constant is reachable by keyboard and has a visible focus state.
4. If option (a): the section has a real `id`, appears in the scroll-spy, and ships a `confidence` namespace in **both** `en.json` and `ru.json`.

---

### III.6 Foundation — "На чём это стоит"

**Reference fragment:** **B2**. This is the clearest 1:1 mapping in the whole reference.

**Composition.** **Extracted into its own section** (**D7**). Eyebrow `FOUNDATION` / `ОСНОВАНИЕ` → H2 `"На чём это стоит"` → lead → 3 cards with prominent `01 / 02 / 03`. **`tone="paper"` if D1 is approved** — this is the strongest candidate for the inverted band because it is the manifesto and the contrast change gives it the weight the copy already claims.

**Grid.** `md:grid-cols-3`, `gap-[var(--space-card-gap)]`. Equal-height cards.

**Cards.** `SurfaceCard variant="raised"` (dark) or `--color-paper-surface` (paper). Numeral at `--text-numeral` (up to 52px) at the card top — promoted from today's 11px `aria-hidden` label. Heading, body, then `sourceRef` on a hairline.

**Hover states.** `.card-premium`. On paper the hover raises the card off `--color-paper` with a soft dark shadow rather than a white glow — the inverted equivalent, and the reason `--card-bg` / `--card-bg-hover` must be section-scoped custom properties rather than hard-coded per variant.

**Scroll animations.** `RevealOnScroll index={0,1,2}`. On paper, add nothing else — an inverted band is already a strong scroll event.

**Mobile rules.** Single column. Numeral shrinks to `--text-display-number`. Paper band keeps full-bleed background with the standard page padding inside.

**Tokens.** `--color-paper`, `--color-paper-surface`, `--color-on-paper*`, `--color-border-on-paper`, `--text-numeral`, `--radius-lg`, `--space-section-y-major`.

**Components.** `PremiumSection tone="paper" rhythm="major"`, `SectionHeader tone="paper"`, `SurfaceCard`, `RevealOnScroll`, `contentSource.getPhilosophyBlocks`.

**Acceptance criteria.**
1. All three principles preserved from `content/{ru,en}/philosophy/*.mdx`. No copy inlined.
2. New `foundation` namespace present in **both** `messages/en.json` and `messages/ru.json`. `npm run check:i18n` passes.
3. Section has `id="foundation"`, appears in the scroll-spy, and is reachable from the footer link list.
4. On paper: every text token re-verified — body ≥ 4.5:1, headings ≥ 7:1 against `--color-paper`. This is a **new contrast surface**; none of the existing ratios in `color.css` apply.
5. `#how-it-works` height drops below ~1 400px (from 2 563px).
6. The seam between the dark section above and the paper band has no sub-pixel hairline gap at any zoom level.

---

### III.7 Terminal / Dashboard

**Reference fragment:** **B3**.

**Composition.** Inverted from today. Left column (narrower): eyebrow, H2 (`"Терминал оператора, а не витрина"` per the reference's framing of the existing copy), lead, the `apiOnlyNote` caveat, and a **CTA** — currently this section has none. Right column (wider): the `TerminalPanel`. The 6-tab list moves **inside** the panel as a compact left rail or segmented control within the terminal chrome, so the section leads with a claim rather than with a control surface.

**Grid.** `lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]`, `gap-14`. Panel may use `SectionBleed` to run slightly wider than the text column at `xl` — **padding escape only, never `100vw`**.

**Cards.** One `TerminalPanel` at `--radius-xl`. Inside: `--radius-md` on nested rows.

**Hover states.** Tab rows: background → `--color-surface-hover`, the left rail marker fading from 0 → 1 (already implemented, keep). Panel itself is `interactive={false}` — it is a display, not a control.

**Scroll animations.** `RevealOnScroll lift={false}` on the panel (a scale on a panel full of 11px tabular text resamples the glyphs). Tab-switch entrance stays `opacity/y:8` at 320ms with `initial` **not** branching on reduced motion.

**Mobile rules.** Stack. Tabs become a horizontal segmented scroller **inside** the panel chrome with `data-lenis-prevent-horizontal` — not six stacked 76px buttons (456px of navigation before any content today). Consider surfacing 4 tabs with the rest behind an overflow control.

**Tokens.** `--radius-xl`, `--radius-md`, `--color-surface-elevated`, `--color-surface-raised`, `--duration-panel`.

**Components.** `PremiumSection rhythm="major"`, `SectionHeader`, `TerminalPanel` (new), `StatusChip`, `MonoLabel`, `ButtonLink`, `RevealOnScroll`.

**Acceptance criteria.**
1. The WAI-ARIA tablist survives the move **unchanged**: `role="tab"`, `aria-selected`, `aria-controls`, one tab in the focus order, Arrow/Home/End roving focus, panels in DOM order after the tablist.
2. Every scrollable table retains `data-lenis-prevent-horizontal`. Zero occurrences of the bare `data-lenis-prevent` in the file.
3. No P&L, equity curve, win rate, profit factor or return figure in any of the six panels. Decision state only.
4. Both caveats present: Риск is API-only; Learning and Settings are omitted from the demo.
5. Traffic-light dots removed.
6. At 390 the section reaches its first content within one viewport.
7. No horizontal page overflow with any of the six panels active.

---

### III.8 Telegram

**Reference fragment:** **B4**.

**Composition.** Left: eyebrow, H2, lead, and the four features as a **compact bordered list** (not four cards — the page has ~20 identical boxes by this point). Right: the interactive `SignalCard` **inside a `DeviceFrame`**, larger than today, which is what makes "оператор в кармане" read instantly. `tone="paper"` is a candidate here per the reference, but see **D1** — the recommendation caps light bands at two.

**Grid.** `lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)]` — the device gets equal or greater weight than the text (today it gets `0.8fr` against `1fr`).

**Cards.** `DeviceFrame` at `--radius-2xl` with a hairline bezel and `--shadow-panel`. Inside, the existing `SignalCard`, untouched in behaviour.

**Hover states.** The two signal-card buttons keep their real pressed/active states. The feature list rows get a subtle background on hover only if they become links; otherwise no hover — a hover state on a non-interactive row is a false affordance.

**Scroll animations.** `RevealOnScroll` on the feature list (single, `index={0}`) and the device (`index={1}`). A gentle 8px parallax on the device at `lg` is acceptable **only** via `PointerTilt`-style pointer input, never scroll-linked.

**Mobile rules.** Stack, device first (it is the artefact), features below as a plain list. Device max-width 300px.

**Tokens.** `--radius-2xl`, `--shadow-panel`, `--space-block`.

**Components.** `PremiumSection rhythm="tight" divider`, `SectionHeader`, `DeviceFrame` (new), `SignalCard`, `StatusChip`, `RevealOnScroll`.

**Acceptance criteria.**
1. The signal card's buttons remain **genuinely pressable** with real state. The previous version drew `aria-hidden` `<span>`s styled as controls — that is the exact "raw" impression being corrected. Never regress to a static mock.
2. `cardDemoHint` / `cardNote` disclaimers preserved.
3. Accept and Skip states are keyboard-reachable and the reset path is reachable without a mouse.
4. State survives a RU↔EN locale switch without a hydration warning.
5. The section is visually distinct from `#dashboard` above it despite `tight` rhythm — measured content gap ≥ 224px, plus a divider or a tone change.

---

### III.9 Brokers / execution routes

**Reference fragment:** **C1**.

**Composition.** Eyebrow → H2 → lead → `disclosure` note → **route diagram** → three broker cards. The diagram is the new element and the reason this section stops being a specification list: *signal → gate → route → broker*, drawn with `SignalLine`, tying the section back to the pipeline.

**Grid.** Route diagram full width. Broker cards `sm:grid-cols-2 lg:grid-cols-3` (the `md`-only 1→3 jump is removed — three cards at 768px are ~230px holding a chip whose `detail` suffix wraps to three lines).

**Cards.** `SurfaceCard`. Order: `StatusChip` → name at `--text-h3` → market label promoted out of `--color-text-faint` to `--color-text-muted` → body. Optional logo per **D5**.

**Hover states.** `.card-premium`. The card's node in the route diagram lights on hover, mirroring the pipeline-spine behaviour so the two sections share one interaction vocabulary.

**Scroll animations.** Route diagram draws left→right, `SignalLine behaviour="draw"`. Cards `RevealOnScroll index={0,1,2}` after it.

**Mobile rules.** Route diagram becomes vertical below `md` (a horizontally-drawn diagram at 390 would need a scroller — do not add one). Cards single column.

**Tokens.** `--color-signal-line`, `--glow-signal-sm`, `--radius-lg`, `--radius-full` (chips).

**Components.** `PremiumSection rhythm="major"`, `SectionHeader`, `SurfaceCard`, `StatusChip variant`, `RouteDiagram` (new), `SignalLine`, `RevealOnScroll`.

**Acceptance criteria.**
1. Statuses unchanged and still derived from real adapter state: T-Invest `active` (registered, real order path, sandbox by default), Bybit `beta` (not in the registry; balances/positions only), Finam `planned` (nine `NotImplementedError`).
2. `beta` and `planned` are **visually distinguishable** (`solid` vs `outline` muted) while neither reads as production-ready.
3. Every status renders its word as text beside the dot. Page survives greyscale.
4. `disclosure` note preserved.
5. No logo appears next to a `planned` status. Logos only if **D5** is confirmed.
6. The diagram makes no throughput, latency or success-rate claim — it is topology only.

---

### III.10 Strategy laboratory

**Reference fragment:** **C2**.

**Composition.** Eyebrow → H2 → lead → **status ladder as a directional progression** (with a connector between stages, not four adjacent boxes) → `currentStateNote` → the register → one merged disclosure.

**Grid.** Ladder `sm:grid-cols-2 md:grid-cols-4` with a `SignalLine` running through the stage dots. Register full width.

**Cards.** Ladder stages are `--radius-md` cells sharing one container. Register stays a table at `md+`; **below `md` it becomes one card per strategy** rather than a 680px horizontal scroller (measured at 390: 344px unreachable except by horizontal gesture).

**Hover states.** Ladder stage: background lift + its dot brightening. Table rows: `--color-surface-hover` background. Cards: `.card-premium`.

**Scroll animations.** Ladder connector draws left→right; stage cells reveal in order. Table reveals once, `lift={false}`.

**Mobile rules.** Ladder 2×2. Register as cards. If a horizontal scroller survives anywhere, it gets a `ScrollAffordance` (edge fade + hint) — today there is none, so the hidden 344px is undiscoverable.

**Tokens.** `--radius-md`, `--color-surface-hover`, `--color-signal-line`.

**Components.** `PremiumSection`, `SectionHeader`, `StatusChip`, `SignalLine orientation="horizontal"`, `ScrollAffordance` (new), `StrategyTable`, `RevealOnScroll`.

**Acceptance criteria.**
1. **No metrics column.** Status is the information. No win rate, no drawdown, no sample size — the register is `id / market / timeframe / status / updated` and stays that way.
2. `frozen` renders muted, never red. It is the outcome of a working process, and publishing it is a discipline signal.
3. The hand-maintained caveat is preserved and visible — copy must never imply this is a live field.
4. Empty stages read as "не занято", not as a bare `0`.
5. Any surviving horizontal scroller keeps `data-lenis-prevent-horizontal` **and** gains a visible affordance.
6. Three real strategies from `content/{ru,en}/strategies.json`, both locales.

---

### III.11 Безопасность (not in the brief's list — kept)

**Reference fragment:** none. Composed to the reference's card rhythm.

**Composition.** Eyebrow → H2 (`"Quant работает с вашим счётом. Вот границы."`) → lead → **two groups**: "гарантии" (4 items) and **"границы гарантии"** (the 2 incomplete-guarantee items: no automatic kill switch, opt-in vault) → `keysCaveat` as an `AsideNote`.

**Grid.** Guarantees `md:grid-cols-2 lg:grid-cols-4`; limits `md:grid-cols-2`, visually heavier.

**Cards.** Guarantees: standard `SurfaceCard`. Limits: `variant="raised"` with a left rule, larger padding, and **more** weight than the guarantees — the caveats are the differentiator and today they look identical to the reassurances.

**Hover states.** `.card-premium` on both groups.

**Scroll animations.** Two stagger groups, capped at `index ≤ 3`.

**Mobile rules.** Single column throughout; limits group keeps its distinct treatment.

**Tokens.** `--radius-lg`, `--color-surface-raised`, `--color-border-strong`.

**Components.** `PremiumSection`, `SectionHeader`, `SurfaceCard`, `AsideNote` (new), `RevealOnScroll`.

**Acceptance criteria.**
1. All six claims preserved with their code provenance.
2. The two incomplete-guarantee items are **visually more prominent**, never softened or equalised upward. The strongest claim (no withdraw/transfer method exists on `BrokerAdapter` at all) stays stated as verified by absence.
3. `keysCaveat` present and legible — the vault is opt-in via `SECRETS_MASTER_KEY`.
4. Section remains reachable from the header nav.

---

### III.12 Pricing

**Reference fragment:** **C3** — composition only, **not** its prices (**D4**).

**Composition.** Eyebrow → H2 → lead → 3 `PricingCard`s with **one focal card** → Live gates as a **requirements checklist** → CTA + note.

**Grid.** `md:grid-cols-3`, `gap-[var(--space-card-gap)]`, equal height. The focal card is 8px taller and uses the `featured` Surface variant.

**Cards.** `PricingCard`. Focal = the tier that is **actually available** (Explore / `Бесплатно`), derived from `available`, never hand-set. That gives the reference's compositional focus without inventing an offer.

**Hover states.** `.card-premium`. The focal card's gradient border brightens. CTA hovers as standard.

**Scroll animations.** `RevealOnScroll index={0,1,2}`; the focal card reveals **last** so the eye lands on it.

**Mobile rules.** Single column, focal card **first**. Gates stack as a checklist.

**Tokens.** `--radius-lg`, `--shadow-cta-*`, `--text-display-number`.

**Components.** `PremiumSection rhythm="major"`, `SectionHeader`, `PricingCard` (new), `SurfaceCard variant="featured"`, `ButtonLink`, `RevealOnScroll`.

**Acceptance criteria.**
1. Prices remain `Бесплатно / Планируется / Планируется`. **No currency figure is invented.** There is no payment code in the repository — `stripe|billing|checkout` returns only a Permissions-Policy header.
2. No "Recommended" badge on an unavailable tier.
3. Live gates read as **requirements**, not as interactive chips. Today they are pill-shaped `<li>`s that look pressable and are not — a false affordance.
4. Live access is presented as gated, never as unrestricted.
5. The `featured` variant is either used here or deleted — it must not remain dead code.

---

### III.13 Final CTA / Access

**Reference fragment:** **C4**.

**Composition.** A **contained panel** at `--radius-2xl` on `--color-bg-elevated`, inset from the page edges — visually rhyming with the hero panel and closing the page as a bookend. Inside: eyebrow, H2, lead, the `AccessForm` as the single dominant action, the trust list, and the Live-access route as a clearly secondary card or link.

**Grid.** Panel `max-w: 1280px`. Inside, `lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]` — the form must be visibly the larger ask (today `1.1/0.9` reads as near-equal for two deliberately unequal asks).

**Cards.** One outer panel + one secondary `InteractiveCard` for Live access.

**Hover states.** Submit button: standard white CTA. Input: border → `--color-border-hover` on hover, `--color-cta` on focus. Live card: the route-card hover.

**Scroll animations.** Panel reveals once, `lift={false}`. The bottom glow stays as it is — a soft white pool, well under a "glow".

**Mobile rules.** Panel inset 16px, single column, form first, Live card below, trust list compact.

**Tokens.** `--radius-2xl`, `--color-bg-elevated`, `--shadow-panel`, `--glow-white-soft`.

**Components.** `PremiumSection rhythm="major"`, `SectionHeader`, `AccessForm`, `InteractiveCard`, `RevealOnScroll`.

**Acceptance criteria.**
1. **The submit path is untouched.** `access-form.tsx` → `/api/beta` → `lib/beta/{schema,adapter}` keeps its react-hook-form + zod validation, its states, and its error handling. Styling only.
2. The `successUndelivered` state is preserved — it tells the truth when the adapter fails, and that is the single most honest state on the site.
3. `consentNote` present before submit.
4. Trust-list dots are **re-toned away from success-green** — green is trade semantics and using it decoratively here weakens the rule everywhere else.
5. The two asks are visibly unequal.
6. Form is fully keyboard-operable; errors are announced (`aria-live`).

---

### III.14 FAQ

**Reference fragment:** none. Composed to the reference's containment language.

**Composition.** H2 (add an eyebrow — this is the only section without one) → ten `<details>` rows **inside a `SurfaceCard` container**, so the 68ch prose column stops floating in a 1280 field.

**Grid.** `width="prose"` at `md+`. At `xl`, consider two columns of five — only if it does not break find-in-page ordering.

**Cards.** One container; rows separated by hairlines.

**Hover states.** Row background → `--color-highlight-bg` on hover and focus-within. A designed chevron replacing the bare `+`, rotating 180° (not 45°) at 300ms.

**Scroll animations.** `RevealOnScroll index={min(i,4)}` — as today.

**Mobile rules.** Full width, generous 44px+ tap rows, chevron right-aligned.

**Tokens.** `--radius-lg`, `--color-highlight-bg`, `--duration-base`.

**Components.** `PremiumSection width="prose"`, `SectionHeader`, `SurfaceCard interactive={false}`, `RevealOnScroll`.

**Acceptance criteria.**
1. **Native `<details>` / `<summary>` retained.** No JS accordion. The previous one was the heaviest and least accessible block on the page and set `outline: none` with no replacement. Native gives keyboard support, screen-reader semantics and find-in-page for free, ships zero JS, and cannot hydration-mismatch.
2. Focus ring visible on every summary.
3. All ten Q&A pairs in both locales.
4. `Ctrl+F` finds text inside collapsed answers (native behaviour — must not be broken by any wrapper).

---

### III.15 Footer

**Reference fragment:** **C4** (lower portion).

**Composition.** Four labelled link columns (Продукт / Как работает / Безопасность / FAQ per the reference), brand block with `BrandMark` + tagline + honest status chip, locale switch, then a rule, then legal + build provenance.

**Grid.** `md:grid-cols-[1.2fr_repeat(4,minmax(0,1fr))]`.

**Cards.** None.

**Hover states.** Links: `--color-text-muted → --color-text-primary` at 150ms, with the existing `-mx-2 px-2 py-2` hit-area expansion retained.

**Scroll animations.** None. The footer is the resting state of the page.

**Mobile rules.** Brand block, then 2×2 link columns, then legal.

**Tokens.** `--space-section-y-tight` for padding (today `py-16` = 128px, out of scale with the 201.6px above it).

**Components.** `BrandMark`, `StatusChip`, locale switch (shared with the header).

**Acceptance criteria.**
1. Status stays `"закрытое тестирование"`. **No pulsing dot.** The previous "Systems operational" pulse was a live-status claim with no telemetry behind it.
2. Build SHA + deploy time preserved as genuine provenance, but the line is **hidden when SHA is `dev`** — a visible `dev` placeholder is the current behaviour in every unset environment.
3. Footer links include `#foundation` once that section exists.
4. Legal text present in both locales.

---

## PART IV — EXECUTION

### 4.1 Phasing

Each phase ends green on `typecheck · lint · build · check · Playwright 1440 + 390`. Do not start the next phase on a red gate.

| Phase | Scope | Risk | Rollback |
|---|---|---|---|
| **0 — Instrumentation** | Add `typecheck` script (**G10**); install Playwright + 1440/390 projects (**G11**); capture current-build baselines; remove dead `gsap` (**G9**) and `hero-video.tsx`/`hero-media.ts`; create `docs/design-references/` and commit the reference | none — no visual change | trivial |
| **1 — Tokens** | New `radius.css`; colour additions (signal, glow, paper, elevated); spacing rhythm; type scale; motion durations. **No component changes.** Verify every token resolves non-empty (**G8**) | Low. Radius 8→16 shifts every card silently | one commit |
| **2 — Primitives** | `PremiumSection`, `SurfaceCard`/`GlassPanel`, `InteractiveCard`, `SignalLine`, `BrandMark`, `StatusChip`, `AsideNote`, `RevealOnScroll` alias, `signal` button variant | Medium — every section imports these | per-component |
| **3 — Structure** | Extract `#foundation` (**D7**); relocate confidence bounds; wire `useActiveSection`; fix anchor landing (**G5**); apply the rhythm scale (**G4**) | Medium — i18n namespaces, nav targets, `check:i18n` | one commit |
| **4 — Hero** | `QAperture`, `GridBackplate`, hero panel, proof strip, mobile height | **High** — LCP, orbit motion, reduced motion | one commit |
| **5 — Pipeline** | `PipelineSpine`, node/card alternation, connectors | **High** — this is where the backward-scroll bug lived | one commit |
| **6 — Product sections** | Dashboard recomposition + `TerminalPanel`; Telegram + `DeviceFrame`; Brokers + `RouteDiagram`; Strategies ladder | Medium — the ARIA tablist must survive intact | per-section |
| **7 — Conversion** | `PricingCard`, Access panel, FAQ container, Footer columns | Low–Medium — **do not touch the form submit path** | per-section |
| **8 — Paper bands** | `tone="paper"` on the approved bands (**D1**), full contrast re-pass | **High** — a new contrast surface; every ratio in `color.css` is measured against `#030303` only | one commit, easily reverted to `tone="dark"` |
| **9 — Polish & QA** | Label rationing (**G7**), page-length pass (**G12**), full verification matrix | Low | — |

### 4.2 Verification protocol

Run at the end of **every** phase.

```bash
cd website
npm run typecheck     # ← must be added in Phase 0; does not exist today
npm run lint
npm run build
npm run check         # content parity + i18n parity + design tokens + media
```

Then, at **1440×900** and **390×844**, in both `/ru` and `/en`:

| # | Check | Pass condition |
|---|---|---|
| 1 | **No horizontal scroll** | `document.documentElement.scrollWidth === clientWidth` at 1440 / 1280 / 1024 / 768 / 390 / 320. Also assert **zero** elements with `getBoundingClientRect().right > clientWidth + 1` outside a declared `overflow-x-auto` container. |
| 2 | **Sticky header** | Header visible at every scroll depth; compact state engages past 100px; never overlaps a heading; clearance ≥ 24px. |
| 3 | **Anchor navigation** | Click each of the header links; the target section's eyebrow lands **104–160px** from the viewport top (today: 231px of dead space on 5 of 10 targets). `location.hash` updates. Deep-link on cold load lands at the same position. |
| 4 | **No backward scroll** | 40 consecutive downward wheel events → `scrollY` monotonically non-decreasing. Repeat after a reload at mid-page. Repeat with the cursor over the strategy table and over each terminal panel. |
| 5 | **Reduced motion** | With `prefers-reduced-motion: reduce`: every `[data-reveal]` computes `opacity: 1` and `transform: none`; Lenis is not instantiated; no orbit is mid-cycle; the page is fully readable with JS disabled. |
| 6 | **Hover states** | Every `[data-slot="surface"]` changes border **and** background on hover at `pointer: fine`, and shows the same state on `:focus-within`. No sticky hover after a tap at `pointer: coarse`. |
| 7 | **Clickable affordance** | Every card containing a navigation link computes `cursor: pointer` **and** the whole card area navigates. Target: **0** cards with a link and `cursor: default` (today: 4). |
| 8 | **CTA form path** | Fill and submit `AccessForm` in both locales. Assert: validation error, network error, success, and `successUndelivered` states all render and are announced. |
| 9 | **i18n** | `check:i18n` green. Visual pass in RU **and** EN — RU is the longer language and is where headings break. |
| 10 | **Contrast** | Every text token ≥ 4.5:1 against its own background, including all paper surfaces. Re-measured, not assumed. |
| 11 | **Keyboard** | Full tab traversal of the page: visible focus at every stop, no trap, tablist roving focus intact, `<details>` operable. |
| 12 | **Performance** | LCP element is the hero `<h1>`; no ancestor starts at `opacity: 0`; CLS ≈ 0; no new blocking request. |
| 13 | **Visual regression** | Full-page 1440 + 390 diffs against the Phase-0 baseline. Every diff is intentional and named. |

### 4.3 Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pipeline spine reintroduces the backward-scroll bug | Medium | **Critical** — the site's worst historical defect | Layout + IntersectionObserver only. Verification check #4 is mandatory and runs after every Phase-5 commit. Zero `ScrollTrigger`, zero scroll listeners outside `scroll-driver.ts`. |
| Cyan drifts into crypto-neon | Medium | High — kills the premium read | Encode the ceiling as a new `check:design` rule: cyan permitted only inside `box-shadow` / `radial-gradient` / SVG `stroke`, peak alpha ≤ 0.28, budget 0 for cyan on `color:` or `background-color:`. |
| Paper bands break contrast | Medium | High | Phase 8 last, isolated, one commit. Every paper token contrast-checked before merge. `tone="dark"` is a one-line revert. |
| `check:design` `raw-white-alpha` budget (6) blown | **High** | Medium — hard build failure | Route every new alpha through a token. If the budget must move, it moves **with a written reason** — the script's doctrine is "budgets may go down, never up". |
| New tokens tree-shaken to empty (**G8**) | High | Medium — silent visual failure | Assert non-empty for every new token in a Phase-1 smoke test. Prefer plain `:root` over `@theme` for anything consumed via inline `style`. |
| ARIA tablist degraded during the dashboard move | Medium | High | Keyboard test (#11) gates Phase 6. The tablist is moved wholesale, not rewritten. |
| Radius 8→16 makes dense UI look bloated | Medium | Low | Nested elements use `--radius-md`; the inner radius stays ~4px below the outer, per the standard nesting rule. |
| i18n parity break from `#foundation` | Medium | Medium — build failure | `check:i18n` runs in every phase gate. Add both catalogues in the same commit. |
| Hero rebuild regresses LCP | Medium | Medium | Keep transform-only entrance; no opacity ramp; no external asset; measure LCP before and after Phase 4. |
| Scope creep into `bot/` | Low | **Critical** | Hard rule: no file outside `website/` is modified. |

### 4.4 Files inventory

**New** — `styles/tokens/radius.css` · `ui/premium-section.tsx` · `ui/interactive-card.tsx` · `ui/signal-line.tsx` · `ui/brand-mark.tsx` · `ui/status-chip.tsx` · `ui/terminal-panel.tsx` · `ui/pricing-card.tsx` · `ui/aside-note.tsx` · `ui/device-frame.tsx` · `ui/grid-backplate.tsx` · `ui/scroll-affordance.tsx` · `hero/q-aperture.tsx` · `how-it-works/pipeline-spine.tsx` · `foundation/foundation-section.tsx` · `brokers/route-diagram.tsx` · `hooks/use-active-section.ts` · `tests/visual/*`

**Modified** — `app/[locale]/page.tsx` · `app/globals.css` · `styles/tokens/{color,spacing,typography,motion}.css` · all 13 section components · `ui/{section,section-header,surface,button,button-link,arrow-link,stat,mono-label,section-heading}.tsx` · `motion/reveal.tsx` (alias + duration only) · `nav/{site-header,mobile-nav}.tsx` · `messages/{en,ru}.json` · `package.json` · `scripts/check-design-tokens.mjs`

**Deleted** — `hero/hero-video.tsx` · `hero/hero-media.ts` · `ui/monogram.tsx` (→ `brand-mark`) · `ui/status-pill.tsx` (→ `status-chip`) · `gsap` dependency

**Never touched** — anything under `bot/`, `knowledge/`, `tests/` (Python), `infra/`, `scripts/` at repo root, `docker-compose.yml`, `.env*` · `app/api/beta/route.ts` and `lib/beta/*` (form **behaviour**; styling of `access-form.tsx` only)

---

## PART V — BRIEF COMPLIANCE MATRIX

| # | Brief requirement | Where it is addressed | Verified by |
|---|---|---|---|
| 1 | Header premium, glass, sticky, no visual noise | III.1 | checks 2, 11 |
| 2 | Hero closer to reference: Q-aperture, orbits, grid, signal glow | III.2, `QAperture`, `GridBackplate` | check 13 + visual review |
| 3 | Audience cards dynamic: hover lift, signal line, route selection | III.3, `InteractiveCard`, `SignalLine` | checks 6, 7 |
| 4 | How Quant Works as a connected pipeline | III.4, `PipelineSpine` | checks 4, 13 |
| 5 | Blocks must not stick together | §1.3 rhythm scale, **G4** | check 13 + gap measurement |
| 6 | All cards/panels have hover/focus states | `.card-premium` on every `SurfaceCard` | check 6 |
| 7 | Clickable elements look clickable | `InteractiveCard`, **G6** | check 7 (target: 0 offenders) |
| 8 | Sticky header must not cover section headings | III.1, `NAV_OFFSET` / `scroll-margin-top` | check 2 |
| 9 | No horizontal scroll bug | `overflow-x: clip`; `SectionBleed` never `100vw`; scrollers axis-scoped | check 1 |
| 10 | No "mouse pulls the page backward" | **D6** hard constraint; `scrollRestoration: manual`; `data-lenis-prevent-horizontal` | check 4 |
| 11 | Reduced motion works | Three-layer contract preserved (§1.5, `RevealOnScroll`) | check 5 |
| 12 | RU/EN i18n not broken | Both catalogues in every commit | check 9 + `check:i18n` |
| 13 | Backend / trading-core untouched | §4.4 "never touched" | file-scope review |
| — | Deep black / white / graphite base | §1.1 | — |
| — | Cold blue accent as secondary signal glow only | §1.1 **D2** + new `check:design` rule | design-token gate |
| — | No orange | Already enforced: `orange-accent` budget 0 | `check:design` |
| — | No crypto-neon | Cyan ceiling: alpha ≤ 0.28, light-only | design-token gate |
| — | No purple gradients | None introduced; none exist | census |
| — | No fake trading results | Preserved everywhere; §III acceptance criteria | per-section AC |
| — | No fake win rate / PF / PnL / Sharpe | Preserved; III.2.1, III.7.3, III.10.1 | per-section AC |
| — | Apple / OpenAI / SpaceX / Grok level | Contained panels, restrained motion, one hover language, honest content | visual review |

---

## PART VI — OPEN DECISIONS

Blocking the build phase. Repeated from `SITE_BLOCK_AUDIT.md` §14 for convenience.

| ID | Decision | Recommendation |
|---|---|---|
| **D1** | Light/inverted sections — how many? | **Two bands: Foundation + Pricing.** Not five. Preserves "deep black base" while delivering the reference's rhythm. |
| **D2** | Cold blue accent — approve the amendment to the monochrome doctrine? | **Approve as light-only** (shadow / gradient / decorative stroke), with the ceiling encoded as a `check:design` rule. |
| **D3** | Radius 8 → 16/20/24 | **Approve.** |
| **D4** | Pricing — copy the reference's `$10/$30/$50`? | **No.** Keep honest prices; take composition only; make **Explore** the focal card. |
| **D5** | Broker logos | **Text-only by default.** Logos only for `active`/`beta` and only with confirmed usage rights. Never beside `planned`. |
| **D6** | Pipeline spine mechanism | **Not a decision — a hard constraint.** IntersectionObserver only. |
| **D7** | Extract `#foundation` (and optionally `#confidence`) | **Approve.** Highest structural value per unit of risk. |

---

*End of plan. Awaiting confirmation to begin the build phase.*
