# REDESIGN_QA_REPORT.md — Quant premium redesign

**Date:** 2026-07-27 · **Branch:** `merge-learning-nik` · **Base commit:** `90877d4`
**Scope:** `website/` only. **Zero changes to `bot/`**, the trading core, the schema, or any Python.
**Companion docs:** [`SITE_AUDIT.md`](./SITE_AUDIT.md) · [`SITE_REDESIGN_PLAN.md`](./SITE_REDESIGN_PLAN.md) · [`VIDEO_ASSET_GUIDE.md`](./VIDEO_ASSET_GUIDE.md)

> **This document has three parts, newest first.**
>
> **[Part III](#part-iii--design-excellence--motion-pass-2026-07-27)** is the
> current state: a premium motion, depth and spatial-rhythm pass, plus a bug
> audit that found four production defects Parts I and II had not caught.
>
> **Part II** is the correction pass that reverted the video hero and removed
> orange from the identity. Still accurate, except that Part III corrects its
> claim that orange was *entirely* gone — the favicon was still amber.
>
> **Part I** (from “Verification gate” onward) is the record of the first
> iteration. Its claims about the **video hero** and the **orange accent** are
> **superseded** and no longer describe the live site. Everything else in Part I
> — the brand rename, the information architecture, and every honesty fix in its
> claims table — still holds and was preserved.

---

# Part III — Design excellence & motion pass (2026-07-27)

Triggered by owner feedback on the Part II result: structurally good and honest,
but *too static, too quiet, slightly boring*; sections felt glued together;
blocks felt flat; the sticky header still overlapped content in screenshots.

Audit doc: [`DESIGN_EXCELLENCE_AUDIT.md`](./DESIGN_EXCELLENCE_AUDIT.md) — measured
findings before any code changed.

## III.1 Verification gate

| Check | Result |
|---|---|
| `npx tsc --noEmit` | ✅ clean |
| `npm run lint` | ✅ clean |
| `npm run check:content` | ✅ en/ru parity |
| `npm run check:i18n` | ✅ 303 keys each |
| `npm run check:design` | ✅ `orange-accent 0/0`, `arbitrary-font-size 0/0` |
| `npm run check:media` | ✅ |
| `npm run build` | ✅ 12/12 static pages |
| Production `next start` server log | ✅ **0 errors** (was 3 per page load) |
| Console, 5 viewports | ✅ 0 errors, 0 hydration warnings |
| Horizontal scroll @ 1920/1440/1024/390/320 | ✅ none (`scrollWidth === clientWidth`) |
| Reveals stuck hidden | ✅ 0 of 70 (see note on method) |
| Reduced motion | ✅ 0 running animations, all 70 reveals visible |

> **Note on measuring reveals.** A test that walks the page with
> `window.scrollTo` gives unstable results here — it reported 0, then 7, then 65
> stuck across identical runs. That is the harness, not the page: `scrollTo`
> bypasses Lenis, whose RAF loop then restores its own position, so the walk
> sometimes never advances and the observers never fire. Driven with real wheel
> input (`page.mouse.wheel`), which is what Lenis actually consumes, the page
> reaches the bottom and reports **0 of 70 stuck at every viewport including
> 1920**. Worth knowing for any future automated test — and for any third-party
> script that tries to scroll this page programmatically.

## III.2 Four production bugs found and fixed

These were **pre-existing** and are the most consequential part of this pass.

### 1. `/robots.txt`, `/sitemap.xml` and `/icon.svg` returned 500 — dev *and* production

`[locale]` is a root-level dynamic segment, and `dynamicParams` defaults to
`true`, so it matched **every** single-segment path. All three metadata routes
were rendering the homepage with `locale = "robots.txt"`, failing three levels
down:

```
ENOENT: scandir '…/content/robots.txt/engine-pipeline'
ENOENT: open    '…/content/robots.txt/strategies.json'
RangeError: Incorrect locale information provided   (new Intl.DateTimeFormat)
```

The layout's `hasLocale()` guard could not prevent it: a layout and its page
render **concurrently**, so `page.tsx` had already started fetching with the
bogus locale before `notFound()` was reached. Next's own `isStaticMetadataRoute`
deliberately classifies `robots.txt` and `sitemap.xml` as *dynamic* entrypoints,
so they cannot win that contest on their own.

Fix: `export const dynamicParams = false` in `[locale]/layout.tsx`.

| Route | Before | After |
|---|---|---|
| `/robots.txt` | 500 | 200 `text/plain` |
| `/sitemap.xml` | 500 | 200 `application/xml` |
| `/icon.svg` | 500 | 200 `image/svg+xml` |
| `/en/nonsense` | 500 | 404 |

**Impact:** the two files every crawler requests first were hard errors on a
marketing site whose whole job is to be found.

### 2. The favicon was still Signal Amber

`src/app/icon.svg` had `#E8A33D` on all three strokes and the retired `#0A0A0B`
plate. Every open browser tab still showed the orange brand that Part II
declared removed. It survived because `check-design-tokens.mjs` scans `src/` for
CSS colour patterns and never looks inside an SVG asset. Now `#ffffff` on
`#030303`.

### 3. Hydration mismatch on every reduced-motion page load

`ui/magnetic.tsx` branched its `style` prop on `useReducedMotion()`. The
component's own doc comment warns against branching markup on that preference —
but `style={reduce ? undefined : {x, y}}` *is* a markup branch: Motion
serialises the MotionValue style to `transform: none` on the server and omits it
on a reduced-motion client. React reported a real hydration error for all 5
Magnetic instances. The style is now unconditional; the values simply never
leave 0 because the handlers already early-return.

### 4. `backdrop-filter` was stripped from the bundle — the glass never blurred

Lightning CSS collapsed `backdrop-filter` + `-webkit-backdrop-filter` down to
the **prefixed property alone**, which this engine does not honour. Verified in
the compiled CSS and via `getComputedStyle(...).backdropFilter === "none"` on
the live page. So every "Liquid Glass" surface — the header and the `glass` /
`featured` Surface variants — had been rendering as a plain translucent panel
since the class was written.

This is also *why the header overlap looked so bad*: with a real blur, content
passing underneath would have been smeared illegible on its own.

Fix: declare it inside `@supports (backdrop-filter: blur(1px))`, which stops the
collapse. Confirmed in the production bundle:

```css
@supports ((-webkit-backdrop-filter:blur(1px)) or (backdrop-filter:blur(1px))){
  .glass-premium,.glass-premium-featured{…backdrop-filter:blur(var(--blur-glass))}
  .nav-glass{…backdrop-filter:blur(var(--blur-glass))saturate(140%)}
}
```

## III.3 Sticky header overlap — the owner's screenshot bug

Reproduced at every desktop width (worst case: the Brokers lead at ~6300px),
where section copy ran *under* the header pill and stayed fully legible through
it, colliding with the nav labels.

Three causes, three fixes:

1. **No scrim.** Content approached the header at full opacity. Added
   `.nav-scrim`: a 128px gradient fading the page to black *above* the pill, so
   content dissolves on approach instead of vanishing under a hard edge. One
   paint-only layer, no blur.
2. **Pill too transparent.** `rgba(12,12,14,0.62)` transmits white text at
   roughly a third of its luminance. `.nav-glass` raises it to
   `rgba(6,6,7,0.86)` + saturation — applied as its own class so the `glass`
   Surface variant is untouched.
3. **`NAV_OFFSET = 80` against a 78px header** left 2px of clearance. Anchors
   technically cleared the pill and still looked wrong. Now `104`, mirrored by
   `scroll-margin-top: 104px` in `globals.css` for the no-JS / keyboard-focus
   path — which did not exist before.

## III.4 Spatial rhythm — the "glued together" sections

`major` was the *most common* step (6 of 11 sections), so a three-step scale
signalled nothing. Worse, **Telegram and Brokers were the only two sections with
neither air nor a divider — and they were adjacent**, collapsing a ~500px
stretch of the middle of the page into one undifferentiated block.

Rebalanced around movements — `major` opens one, `default` continues it, `tight`
binds sections that are genuinely one idea:

| Section | Before | After |
|---|---|---|
| audience | major, divider | **default**, divider |
| how-it-works | major, divider | major, divider, **glow** |
| dashboard | major, divider | major, divider, **glow** |
| telegram | tight, **no divider** | tight, **divider** |
| brokers | tight, **no divider** | **major**, **divider**, **glow** |
| strategies | major, divider | **default**, divider |
| pricing | major, divider | major, divider, **glow** |

Telegram deliberately stays `tight`: it is the second interface onto the same
state as the dashboard, so the two *should* read as one movement — it just needed
a hairline to stop them merging.

## III.5 Motion system added

All compositor-only (`opacity` / `transform` / `stroke-dashoffset`). No scroll
hijacking, no GSAP, no ScrollTrigger, no pinning — `IntersectionObserver` remains
the page's single reveal mechanism.

| Motion | Where | Detail |
|---|---|---|
| Ring breathe | Hero aperture | 3 rings, desynced 9/11/13s |
| Vector flow | Hero exit vector | dashes travel outward, 6s |
| Node ping | Hero exit node | sonar pulse, 4.5s |
| Aperture scan | Hero | one faint trace crossing, 14s, clipped to the rings |
| Pointer parallax | Hero panel | max **7px**, 500ms trail, no rotation |
| Stage rail | 7 pipeline cards | hairline draws L→R with the card's stagger |
| Confidence bars | Telegram card | 10 bars fill 45ms apart on first reveal |
| Section glow | 4 sections | 3.5% peak white radial |

**Reduced-motion contract.** No keyframe uses `animation-fill-mode`, so the
global reset (`duration: 0.01ms`, `iteration-count: 1`) reverts each element to
its *base* style — which is authored as the correct resting state. Verified: 0
running animations, hero elements at `opacity: 1 / transform: none`, tilt at
identity, all 70 reveals visible.

The hero still ships **zero client JS for its content**: `PointerTilt` is a
~40-line client shell and `HeroVisual` is passed through as `children`, so the
LCP markup is still server-rendered HTML.

## III.6 "Как работает" — orphan card and collapsed joints

- **Orphan fixed.** Seven stages over three columns left card 7 (`ПАМЯТЬ`) alone
  beside two empty cells. The last card now spans the row when the count would
  orphan it, and carries the loop note beside it in a second column — which is
  the better composition anyway, since that stage *is* the one that closes the
  loop. Derived from `stages.length`, not hardcoded, so an eighth stage
  rebalances instead of reintroducing the bug elsewhere.
- **Three collapsed joints opened.** `ГРАНИЦЫ УВЕРЕННОСТИ` and `НА ЧЁМ ЭТО
  СТОИТ` each nearly touched the paragraph above them, because one flat
  `gap-14` served joints of four different semantic weights. Both now get a
  hairline rule plus real air; the principles block gets a full tight-step.
- **Sequence made legible** via the stage rails (III.5).

## III.7 Verified working, unchanged

Confirmed by interaction test rather than assumed:

- **Product terminal** — 6 tabs (Обзор / Портфель / Сигналы / Бэктест /
  Аналитика / Риск), correct `tablist` / `tab` / `tabpanel` roles, exactly one
  visible panel, distinct content per tab, `aria-selected` tracks, **arrow-key
  roving focus works**, Enter activates.
- **Telegram demo** — buttons mutate local state only, `aria-live` present,
  copy still says the demo changes nothing and nothing reaches a broker.
- **Broker statuses** — `active` → success, `beta` / `planned` → muted. Beta is
  *not* rendered green.
- **Focus rings** visible on every interactive element sampled.
- **Scroll integrity** — the Part II backward-jump fix is intact and untouched.

## III.8 Honesty — unchanged

No win rate, profit factor, sample size, equity curve or return figure was
added. The hero's three tiles remain *configured limits* (5% / 2% / 0.20), the
terminal stays captioned as demonstrational, and the hero visual still contains
no chart, no curve and no plotted series — deliberately, since a moving line on
a trading site is a performance claim regardless of its caption.

## III.9 Known, not fixed

- **`NEXT_PUBLIC_SITE_URL` is unset locally**, so `robots.txt` and `sitemap.xml`
  emit `https://quantflow.example` while `layout.tsx` falls back to
  `https://quantflow.app`. Two different placeholder domains in one build. Set
  the env var before launch — now that these routes actually serve, the URL in
  them matters.
- `check-design-tokens.mjs` still does not scan SVG assets, which is how the
  amber favicon survived. Worth extending.
- This work is **uncommitted and lives in `~/Downloads/Trading-Bot-merge-learning-nik`**,
  not the canonical `~/Documents/GitHub/Trading-Bot`. See the note at the top of
  the audit doc.

---

# Part II — Design correction pass (2026-07-27)

Triggered by main-owner feedback: the first iteration read “too raw”, and the
generated-video hero was not what was wanted. Ten numbered design corrections
plus a scroll-bug hunt and a full bug audit.

## II.1 Verification gate

| Check | Result |
|---|---|
| `npx tsc --noEmit` | **0 errors** |
| `npm run lint` | **0 errors, 0 warnings** |
| `npm run build` | ✓ 12/12 static pages, **0 warnings** |
| `npm run check:content` | ✓ `content/en` / `content/ru` in parity |
| `npm run check:i18n` | ✓ **303 keys each**, exact parity |
| `npm run check:design` | ✓ 4/4 budgets, incl. new `orange-accent 0/0` |
| Console (production) | **0 errors, 0 warnings, 0 hydration warnings** |
| CSS parse warnings | **0** (one existed before — see II.2) |
| Homepage First Load JS | **394 kB → 356 kB** (−38 kB; GSAP no longer bundled) |

## II.2 Two blocking bugs found before any redesign work

**1. The dev server was returning HTTP 500 on every page.**
`scripts/check-design-tokens.mjs:30` carried the hint string
`"use a token: text-[length:var(--text-label|caption|body|lead|h3)]"`. Tailwind v4
scans *every* non-ignored file in the project for class candidates, including its
own lint scripts. It extracted that placeholder as a real utility and emitted
`font-size: var(--text-label|caption|body|lead|h3)`, which is invalid CSS:

```
./src/app/globals.css:908:32  Parsing CSS source code failed
font-size: var(--text-label|caption|body|lead|h3);
                           ^-- Unexpected token Delim('|')
```

In `next build` this surfaced only as “Found 1 warning while optimizing generated
CSS”, which is why it had shipped unnoticed; in `next dev` it took the whole page
to a 500.

Rewriting the hint fixed it — and then **writing the literal into this very
report reintroduced the warning**, because Tailwind was scanning `docs/` too.
That made the real defect obvious: prose *about* a utility should never be able to
become a utility. The root fix is scoping the scan in `globals.css`:

```css
@import "tailwindcss" source(none);
@source "../../src";
```

`source(none)` is required — a bare `@source` *extends* automatic detection rather
than replacing it, which is why the first attempt still warned. After scoping,
verified that no utilities were lost: h1 `54.72px`, CTA `rgb(255,255,255)` on
`rgb(3,3,3)` at `48px`, surface `#0a0a0a` / 1px border / 28px padding, selected tab
`#171717`, section rhythm `201.6px`. Dev 500, build warning, and the whole class of
bug are gone.

**2. Reduced-motion users could not see the page at all.**
Found during the audit, on the production build: **all 32 cards were stuck at
`opacity: 0`**. `Reveal` used `initial={reduce ? false : { opacity: 0, … }}`.
`useReducedMotion()` is `false` on the server and the user's real value on the
client, so the server always emitted `opacity: 0` inline — and `initial={false}`
on a reduced-motion client means *“adopt the current DOM state and do not
animate”*, so that `opacity: 0` was never cleared.

Fixed by never branching *markup* on the preference (the rule `ui/magnetic.tsx`
already documented): identical props everywhere, only the transition duration
collapses to `0`. Plus a CSS safety net — under `prefers-reduced-motion: reduce`,
`[data-reveal]` is force-reset to `opacity: 1; transform: none`, so content is
visible even if the IntersectionObserver never fires or JS fails outright.
Re-measured: **0 of 64 reveal wrappers hidden, 0 of 32 cards invisible, without
scrolling.**

## II.3 The scroll bug — reproduced, diagnosed, fixed

**Symptom (owner):** while scrolling, the page pulls the user backward / the
scroll position jumps.

**Reproduction**, 1440×900, production build, real (trusted) wheel events:

| Step | Value |
|---|---|
| Scroll down, then reload | `scrollY` 12 262 → browser restored to 11 014 |
| Send **one** downward wheel tick (+100) | page drops to **10 324** before settling at 11 174 |
| **Backward jump on purely downward input** | **−690 px** |

**Root cause:** `history.scrollRestoration` was left at its default `"auto"`. The
browser restores the previous offset *asynchronously, after first paint*, while
Lenis is constructed in a React effect that runs *before* that restore lands — so
Lenis captured a stale internal `animatedScroll`. The first wheel event then
animated from that stale origin, yanking the page back by the size of the
discrepancy.

This is confirmed by Lenis' own source: `onNativeScroll` (`lenis.mjs`) only
resyncs `animatedScroll` when `isScrolling` is `false` or `"native"` — mid smooth
animation it does not, leaving the desync window open.

**Fix**, in `components/motion/scroll-driver.ts`:
1. `history.scrollRestoration = "manual"` — the browser no longer moves the
   document behind Lenis' back. (The old restore was landing 1 248 px off its own
   target anyway, because document height depends on revealed content.)
2. Hash deep-links applied by us after `load`, with the nav offset, so they still
   work.
3. `lenis.resize()` + resync after `load` and on debounced resize, so any
   programmatic scroll from elsewhere cannot leave Lenis stale.
4. Restoration is restored to its previous value on cleanup.

**A second, independent contributor was also fixed:** `data-lenis-prevent` sat on
three elements, one of them the **full-viewport-width** horizontal track. That
attribute opts an element out of Lenis on *both* axes, so vertical wheel input
over those regions scrolled natively while Lenis' position went stale — the same
desync, triggered by nothing more than moving the cursor. Replaced with the
axis-scoped **`data-lenis-prevent-horizontal`**, which releases only horizontal
gestures (needed for Mac trackpad table scrolling) and keeps vertical scrolling on
the smooth path.

**Verification** (production build, real wheel events):

| Test | Before | After |
|---|---|---|
| Backward jump after reload + 1 downward tick | **−690 px** | **0 px** |
| Full-page traversal, 140 ticks / 14 000 px | — | **0 backward events**, reaches document end |
| Scroll amplification | — | **0.91×** (no double-counting) |

## II.4 Design corrections 1–10

**1 · Hero — video removed, composition restored.** `HeroVideo` is gone from the
homepage. The right side is now `hero-visual.tsx`: a static monochrome system
object — concentric measurement rings, the Q aperture kept subtle at 25 % width
and 90 % opacity, one white node where the aperture's tail exits, and a six-stage
decision rail naming real `bot/` modules. No chart, no curve, no figure, no
percentage: a rising line would be a performance claim even under a caption.
Copy is the owner's text verbatim; primary CTA is white-on-black, secondary is an
outline arrow link. The three tiles that remain are **configured limits**
(`bot/config.py:66-71`, `trading_orchestrator.py:63`), not results.

**2 · Global card hover.** One primitive: `.card-premium` in `globals.css`, wired
through `ui/surface.tsx`, which now defaults `interactive` to **true** — 31 cards
carry it. Verified by forcing `:hover` over CDP (synthetic mouse moves do not
reliably update Chromium's hover node):

| Property | Rest | Hover |
|---|---|---|
| background | `#0a0a0a` | `#111111` |
| border | `rgba(255,255,255,.1)` | `rgba(255,255,255,.28)` |
| shadow | `0 1px 2px rgba(0,0,0,.4)` | `0 18px 48px -12px rgba(0,0,0,.75)` + white glow |
| transform | `none` | `translateY(-6px)` |

Hover is gated behind `@media (hover: hover) and (pointer: fine)` so it cannot
stick after a tap on touch; `:focus-within` gives the same highlight to keyboard
users; the lift alone yields to reduced motion.

**3 · Scroll reveal.** `Reveal` animates `opacity 0→1`, `y 28→0`,
`scale .98→1`, staggered 80 ms, IntersectionObserver-based — it reads no scroll
events, so it cannot desync from the scroll driver. `amount: 0.2` because a tall
card on a 390 px viewport may never show 25 % of itself at once.

**4 · Horizontal card section — pinning removed.** The old track over-panned:
`distance = track.scrollWidth − wrap.clientWidth` counted the track's own page
padding, so a 2 702 px row travelled 1 268 px when its content needed ~1 038 px —
measured result: three cards fully off-screen left, 230 px of dead space right,
four cards partially clipped. It was also a native `overflow-x-auto` scroller
*and* a transformed element *and* had `scroll-snap-type: x mandatory`, so the
browser's snapping moved `scrollLeft` underneath the transform. Replaced with a
staggered reveal grid (1 / 2 / 3 columns). **0 pin-spacers remain on the page.**

**5 · “На чём это стоит”.** The three principles — *Доказательства, а не
интуиция* / *Ограниченная уверенность* / *Заморозка — это дисциплина* — were
plain paragraphs; they are now three numbered `raised` cards with title, body and
a technical note, revealing one after another. The notes are new `sourceRef`
frontmatter, each verified against real code before being written:
`belief_updater.py:37` (`MIN_TRADES_FOR_CONFIDENCE = 20`), `belief_updater.py:46-47`
(0.05 / 0.95), `trading_orchestrator.py:63` (`MIN_STRATEGY_CONFIDENCE = 0.20`).

**6 · Operator terminal — interactive.** `dashboard-terminal.tsx`: six clickable
sections (Обзор · Портфель · Сигналы · Бэктест · Аналитика · Риск), each swapping
a distinct preview. A real WAI-ARIA tablist — `role="tab"` + `aria-selected` +
`aria-controls`, one tab in the focus order, Arrow/Home/End roving focus.
`aria-selected` rather than `aria-pressed`: the latter would announce six
independent toggles instead of one six-way choice. Selected state is a solid white
rail plus a lighter panel — no colour. Verified: all six panels distinct,
keyboard traversal works, 82 px tap targets at 390 px.

**7 · Telegram signal card — interactive.** `signal-card.tsx`. *Исполнить в
песочнице* → “Заявка отправлена в песочницу” + **“Демо-режим: ничего не ушло
брокеру и никакая сделка не открыта.”**; *Пропустить* → “Сигнал пропущен”; both
reversible via *Показать снова*. `role="status"` + `aria-live="polite"`. **No
fetch, no server action, no broker call** — the qualifier is load-bearing, since
“Заявка отправлена” alone would imply a real sandbox order.

**8 · Scroll bug** — see II.3. **9 · Bug audit** — see II.5.

**10 · Content honesty.** All prior fixes preserved. Two new disclosures were
required by the six-tab set: “Риск” is served over the API and is not a separate
page yet, and the product also has Learning and Settings sections this demo
omits — both stated in the section note rather than glossed over.

## II.5 Bug audit — 5 viewports, production build

| Viewport | H-overflow | Section overlaps | Clipped text | Rogue wide els | Pin-spacers | Orange pixels |
|---|---|---|---|---|---|---|
| 1920×1080 | **0 px** | **0** | 0 | 0 | 0 | **0** |
| 1440×900 | **0 px** | **0** | 0 | 0 | 0 | **0** |
| 1024×768 | **0 px** | **0** | 0 | 0 | 0 | **0** |
| 390×844 | **0 px** | **0** | 0 | 0 | 0 | **0** |
| 320×640 | **0 px** | **0** | 0 | 0 | 0 | **0** |

“Orange pixels” scans every element's computed background, colour and border for
an orange-range RGB triple. Also checked: **reduced motion** (II.2),
**keyboard navigation** — 30 focusables tabbed, **all 30** show a visible 2 px
white ring, none missing.

**Non-defects, recorded so they are not re-investigated:**
- The only elements wider than the viewport are `min-w-[680px]` tables *inside*
  their `overflow-x-auto` scrollers. Page overflow is 0 px.
- The only “clipped text” hit is `<span class="sr-only">Технически: </span>` —
  `width: 1px; overflow: hidden` is what `sr-only` *is*.
- The only console errors are `/_vercel/insights/script.js` and
  `/_vercel/speed-insights/script.js` 404s, which exist only when deployed on
  Vercel. Pre-existing and environmental.
- A hydration mismatch appeared **2 of 12 times in `next dev`**, its stack inside
  React's streaming *replay* path. It does **not** reproduce in production:
  **0 hydration errors in 14 cold production loads** across two viewports. Dev
  streaming artifact, not a markup branch.

## II.6 What was reverted from the video hero

| Reverted | Detail |
|---|---|
| `HeroVideo` mounted on the homepage | Removed from `hero-section.tsx` |
| `HERO_MEDIA` as a live dependency | Nothing imports it |
| `hero.videoDescription` copy | Deleted in both locales — it described “одна оранжевая сигнальная точка” |
| `check:media` in the `build` script | Removed: the build no longer has a hero-media dependency |
| 1.94 MB `.mp4` on the critical path | Gone. It was gitignored, so the poster was the real hero everywhere except one machine |

**Kept, deliberately:** `hero-video.tsx`, `hero-media.ts`, the four committed
posters, `scripts/media/*` and `docs/VIDEO_ASSET_GUIDE.md`. Both components now
open with a **⚠ NOT MOUNTED** header pointing at `hero-visual.tsx`, so nobody
assumes the homepage uses them. Nothing was deleted.

## II.7 Colour system

`--color-accent` changed from `#ff7a1a` to **`#ffffff`**, keeping the token name
so ~25 call sites converted at once: a filled CTA became white-on-black (20.4:1),
emphasised labels resolved to primary text, focus rings became white. Also
retired: the orange selection highlight, the orange glass-hover border, the
orange featured-tier gradient, and orange `rgba` literals in `mobile-nav.tsx` that
the first grep missed — caught by a new `check:design` rule, `orange-accent`,
budget **0**, which matches both retired oranges in hex and `rgba` form so this
cannot regress silently.

Green and red survive only as trade semantics and were desaturated (`#22e58b` →
`#7fd8a8`, `#ff4d6d` → `#f08a9c`) so they read as data next to pure white. Every
status still renders its state as text, so nothing depends on colour alone.
`raw-white-alpha` was ratcheted **12 → 6** after routing hover/CTA states through
new `--color-highlight-*`, `--color-fill-subtle` and `--shadow-cta-*` tokens.

## II.8 GSAP

With the pinned track gone, GSAP had no ScrollTriggers left, so the
Lenis↔ScrollTrigger bridge in `scroll-driver.ts` was maintaining a
synchronisation path with nothing on the far side of it. Removed; Lenis now runs
on a plain `requestAnimationFrame` loop. Every reveal on the page is
IntersectionObserver-based, so **nothing except the scroll driver reads or writes
scroll position** — which is what makes this class of bug structurally hard to
reintroduce. `gsap` remains in `package.json` but is no longer imported: −38 kB
off the homepage bundle.

---

# Part I — original redesign

> Superseded where noted above: the **video hero** and the **orange accent**
> described below are no longer the live design. Everything else still holds.

## 1. Verification gate — all green

| Check | Result |
|---|---|
| `npx tsc --noEmit` | **0 errors** |
| `npm run lint` | **0 errors, 0 warnings** |
| `npm run check:content` | ✓ `content/en` and `content/ru` in parity |
| `npm run check:i18n` | ✓ **251 keys each**, exact parity |
| `npm run check:design` | ✓ all four token budgets met |
| `npm run check:media` | ✓ 4 posters present |
| `npm run build` | ✓ 12/12 static pages |

**Diff: 84 files changed, 2,253 insertions, 4,875 deletions — net −2,622 lines.**

---

## 2. What changed

### Brand
QuantFlow → **Quant** across copy, metadata, OG tags, components and comments. Dated audit records under `docs/audit/` were deliberately left unrenamed — rewriting them would falsify the historical record.

The mark was redesigned from an open instrument dial to a **Q aperture**: a 320° ring with a 40° blade opening and a tail crossing the lower-right edge. The tail is what makes it read as a Q rather than a loading spinner, and it carries the concept — a decision that has cleared every gate leaves along it. Geometry is shared between `ui/monogram.tsx` and `scripts/media/build-poster.mjs`, so nav, footer and hero poster are literally one system. The mark now inherits text colour; **orange appears only on actions and signals**.

### Information architecture
12 sections → the new story: Hero → Audience → HowItWorks → Dashboard → Telegram → Brokers → Strategies → Safety → Pricing → FAQ → Access.

Three sections were retired without losing any content: Philosophy became the principles band inside HowItWorks, LearningSystem's constants became its confidence-bounds block, and Sandbox folded into Safety. No file under `content/` was deleted, which is why `check:content` passed untouched throughout.

### Claims — every defect from the audit is fixed

| Was | Now |
|---|---|
| All three brokers badged "Integrated", green dot | **T-Invest Active · sandbox by default** / **Bybit Beta · read-only** / **Finam Planned** |
| Hero: 58.6% / 1.16× / 29 trades | **No performance figures anywhere.** Hero shows configured limits: 5% per position, 2% daily loss, 0.20 signal floor |
| "Confidence held between 20% and 80%" | **0.05–0.95**, matching `belief_updater.py:46-47` |
| "Bayesian bounds" (in the hero canvas) | Described accurately as a smoothed equal-weighted mean of win rate, profit factor and expectancy |
| "Every position size is a function of conviction" | "Confidence decides *whether* a trade happens; it does not yet scale how large it is" |
| "A strategy earns capital only after 20 verified trades" | "Confidence only starts moving after 20 closed trades; below that it sits at neutral 0.5" |
| Sharpe 1.34, ₽1,048,230, +8.3% equity curve | Mockup replaced by a structural schematic with **no figures at all** |
| Risk + History shown as dashboard pages | The **seven real views**, with an explicit note that risk and history are API-only |
| Footer "Systems operational" + pulsing green dot | "Closed testing" — a claim the page can actually support |
| Implied automatic freeze / kill switch | "Statuses are maintained by hand… there is no automatic freeze"; "**there is no automatic kill switch**" |
| No security claims at all | The genuinely strong ones added: AES-256-GCM vault, audit log, and **"Quant cannot withdraw funds"** — verified by absence of any withdraw method in `BrokerAdapter` |

The `hero-signal-flow.tsx` canvas was **deleted outright**, not reworked. It contained four separate false claims baked in as hardcoded English strings — including a "CONFIDENCE" chart that rose 50%→80% and read visually as an equity curve, and axis labels encoding the wrong bounds. All six of its stage labels also rendered in English on the Russian page.

### Security caveat, stated rather than omitted
Safety explicitly discloses that vault encryption is opt-in via `SECRETS_MASTER_KEY`, and that without it credentials fall back to a plain `.env` (`bot/security/credential_store.py:50-57`).

### Design system
- **128 arbitrary `text-[Npx]` → 0**, enforced by `check:design`
- 7 container widths / 7 left edges → **one** (`--space-content-max: 1280px`, matching the header)
- One 201.6 px vertical metronome → **three rhythm steps**
- Text contrast floor raised to **4.9:1** (`--color-text-quaternary`); every token carries its measured ratio in a comment
- 11 glass implementations → one `Surface` with four variants
- 3 copies of magnetic-spring maths → one `Magnetic`
- 4 CTA anchor implementations → one `ButtonLink`
- 5 stat treatments → one `Stat`; 5 status indicators → one `StatusPill`

**Caught during the rebuild:** the shadcn bridge in `globals.css` redefines `--color-muted` as a *surface* colour, which silently clobbered the muted status colour and would have rendered every muted pill invisible against its own panel. Our token was renamed `--color-neutral`, with comments on both sides.

### Accessibility
- `outline: "none"` removed; FAQ rebuilt on native `<details>/<summary>` — keyboard, screen-reader semantics and find-in-page for free, and **one fewer client component**
- Email label is now **visible**, not `sr-only`
- Hit targets raised to ≥44 px (buttons), ≥24 px (nav, locale, footer, arrow links)
- `SiteHeader` moved outside `<main>` — a banner must not be a `main` descendant
- Hero video: `aria-hidden`, `tabIndex={-1}`, no `controls`, `disablePictureInPicture`, `muted` set as a DOM property (React does not serialise it to SSR HTML, and an unmuted video is autoplay-blocked)
- One `<h1>`, clean H1→H2→H3 throughout, all 11 `aria-labelledby` references resolve

### Performance
- Dropped `three`, `@react-three/fiber`, `@react-three/drei`, `lucide-react`, `tw-animate-css` — 10 dead scene files, all unreferenced
- `components.json` `iconLibrary` set to `"none"`, or the next `npx shadcn add` would silently reinstall lucide
- **Fonts 8 → 4** preloaded (~100 KB saved): Cormorant Garamond was loading on every page for a single internal style-tile usage
- `/media/*` now served `immutable` for a year

---

## 3. Measured results

All figures from the production build (`next start`), Playwright, Chromium.

### Hero media
| Metric | Result |
|---|---|
| Poster (desktop) | **hero-poster.avif, 6.0 KB**, requested at 22 ms |
| Poster (mobile) | **hero-poster-mobile.avif, 4.1 KB** |
| Video request start | **232 ms** — after DOMContentLoaded (30 ms) |
| **CLS** | **0.000** |
| TTFB | 14 ms |
| LCP element | `img[hero-poster.avif]` ✓ |
| High-priority images | exactly 1 |

### Watermark policy — verified, not assumed
```
video natural: 1280x720   srcAR 1.7778
container box:            boxAR 1.7778
cropPercent: 0            watermarkInFrame: true
```
The container aspect ratio matches the source exactly, so `object-fit: cover` performs **no crop at all**. The burned-in mark (measured at x 88–94 %, y 86–92 %) cannot leave frame. The readability gradient is left-edge only, landing inside the source's empty black band.

### Conditional loading
| Condition | Video elements | Video bytes |
|---|---|---|
| Desktop, motion allowed | 1 | 1.94 MB (after LCP) |
| **Mobile (390 px)** | **0** | **0** |
| **Reduced motion** | **0** | **0** |
| **mp4 absent (CI/Vercel)** | 1, `networkState: 3`, opacity 0 | 0 |

Under reduced motion all 11 sections and 12,329 characters of content remain — nothing is lost, only motion.

**The absent-file test empirically confirmed the poster-only fallback** that was previously only spec-derived: with the mp4 renamed away, the build succeeded, the warn-only `check:media` printed its notice, the page returned 200, `networkState` settled at `NETWORK_NO_SOURCE`, the video stayed at opacity 0, and the poster remained the hero at 584×328.

### Responsive — 5 viewports × 2 locales, all clean
`1920×1080 · 1440×1000 · 1024×768 · 390×844 · 320×700`, RU and EN: **no horizontal page scroll in any of the 10 combinations.**

Both previously-broken tables now scroll properly, with no clipping element between the scroller and the table, and `data-lenis-prevent` so Mac trackpad gestures work:

| Table | Before | After (390 px) |
|---|---|---|
| Strategy register | 434 px unreachable | **360 px reachable by scrolling** |
| Dashboard schematic | SIGNALS tab unreachable | **333 px reachable by scrolling** |

**Three overflow bugs were introduced and fixed during this work**, all the same root cause — a grid item's default `min-width: auto` refusing to shrink below a `whitespace-nowrap` button carrying a long Russian label:
1. Dashboard schematic overflowed at 390 px → `min-w-0` on the grid children
2. Hero overflowed at 320 px → `min-w-0` + the primary CTA goes full-width and wraps below `sm`
3. Access form overflowed at 320 px → same treatment

A final 1 px residual at 320 px came from the fixed header being sized to the initial containing block while `<main>` narrowed for the 6 px scrollbar. Fixed with `overflow-x: clip` on **both** `html` and `body` — `clip` rather than `hidden` specifically because `hidden` creates a scroll container and would silently disable GSAP pinning. **Pin re-verified working afterwards** (`pinSpacerExists: true`).

### Console
Two errors, both pre-existing and environmental: Vercel Analytics and Speed Insights scripts 404 when not deployed on Vercel. **No hydration warnings.**

---

## 4. Known blockers before public launch

### 4.1 The access form does not store anything — BLOCKING
`src/lib/beta/adapter.ts` still defaults to a console adapter that logs the address and discards it.

**What changed:** the API now returns `{ ok, delivered }`, and the UI is driven by `delivered`, not by HTTP 200. With no destination configured the form shows `accessForm.successUndelivered` — which states plainly that intake is not connected and the address was not stored — instead of the old *"Request received. We follow up if it's a fit."* The site can no longer tell a user something untrue.

**To go live:**
```bash
BETA_ADAPTER=webhook
BETA_WEBHOOK_URL=https://…      # Formspree, a webhook, an automation
```
A `webhookAdapter` is implemented and reports `delivered: true` only when the endpoint accepts. **This is still the only conversion path on the site — nothing else on this list matters as much.**

### 4.2 Video is a watermarked prototype — BLOCKING for public video
The current asset carries a visible provenance mark and a C2PA manifest. Today the public build is watermark-free **by construction**: the mp4 is gitignored, so CI/Vercel render poster-only. Shipping video publicly requires a clean licensed master meeting the specs in `VIDEO_ASSET_GUIDE.md` §5.

### 4.3 Analytics taxonomy — deliberate hard cut
Every `journey_step.section` value changed with the section slugs, `scene_interaction` is gone, and `cta_clicked.target` is now a typed union (`sandbox_access` / `live_access` / `how_it_works` / `explore`). Saved PostHog funnels keyed on the old strings will go blank silently rather than error.

---

## 5. Remaining issues and trade-offs

| Item | Status |
|---|---|
| **Prototype video is 1.94 MB — 2.2× the 900 KB budget** | Accepted for local prototyping only; recorded in the guide. Never fetched on mobile or under reduced motion. |
| **Prototype does not loop cleanly** | t=0 is black, t=9.9 is lit, so native `loop` flashes. Clamped to `loopRange: [6.4, 9.9]`. Production master must be authored to loop; then set `loopRange: undefined`. |
| Automated screenshots | Playwright's screenshot repeatedly timed out on its font/stability wait with the video playing. Responsive verification was done numerically instead across all 10 combinations, which is stricter. One 1440 px visual was captured via the in-app browser. |
| `raw-white-alpha` budget at 8/12 | Deliberate headroom. Remaining uses are one-off glass tints and the hamburger; the budget is a ratchet that may go down, never up. |
| `suppressHydrationWarning` on `<html>` | Still present (`layout.tsx:82`) and still masks real mismatches. Worth removing now that the known offender is gone. |
| Empty Active/Candidate lanes | Per your direction, rendered as a **status ladder with occupancy counts** rather than four big lanes, plus: *"Active-стратегии появляются только после форварда и допуска к Live."* |
| Paper-trading claim | Softened to "same RulesEngine and the same risk limits", since `paper_engine.py:609-618` explicitly does not use `risk.risk_manager` and the belief gate is not in its path. |
| `--color-paper` token unused | Declared for a future inverted band; no section uses it yet. |

---

## 6. Production asset requirements

Full specs, encoding commands and swap procedure in [`VIDEO_ASSET_GUIDE.md`](./VIDEO_ASSET_GUIDE.md).

| File | Res | Codec | Budget | Audio |
|---|---|---|---|---|
| `hero-desktop.mp4` | 1280×720 | H.264 High L4.0, faststart | ≤ 900 KB | none (`-an`) |
| `hero-desktop.webm` | 1280×720 | VP9 | ≤ 650 KB | none |
| `hero-mobile.mp4` | 768×432 | H.264 High L3.1 | ≤ 350 KB | none |
| `hero-poster.avif` / `.webp` | 1280×720 | AVIF q50 / WebP q72 | 7 / 16 KB | — |
| `hero-poster-mobile.avif` / `.webp` | 768×432 | AVIF q50 / WebP q72 | 5 / 9 KB | — |

Swapping is a **one-file edit**: `HERO_MEDIA` in `src/components/sections/hero/hero-media.ts`. Use version-suffixed filenames — `/media/*` is served `immutable`.

---

## 7. Next steps

1. **Configure `BETA_ADAPTER`** — §4.1. Nothing else unblocks the funnel.
2. **Commission a clean hero master** — §4.2, authored to loop, audio stripped.
3. **Correct `CLAUDE.md`** — it still names `~/Documents/GitHub/Trading-Bot/` as canonical and forbids editing this copy, but this copy is 5 commits ahead with 36 more website files.
4. Decide the analytics migration — §4.3.
5. Optional: remove `suppressHydrationWarning`; add a light `--color-paper` band if an inverted section is wanted; consider wiring the footer status to `/health` (needs a backend surface, deliberately out of scope here).

---

## 8. New tooling this adds

| Script | Purpose |
|---|---|
| `npm run check:i18n` | Message parity — also catches ICU placeholder mismatches and untranslated copies. **There was previously no guard on `messages/*.json` at all.** |
| `npm run check:design` | Fails on arbitrary font sizes, raw white alphas over budget, legacy accent hex, inline `fontSize`. This is what keeps the type scale from drifting back. |
| `npm run check:media` | **Warn-only, always exits 0** — a missing video is a supported state, not an error. |
| `npm run media:poster` | Regenerates posters from the brand geometry. Fails if any exceeds budget. |
| `npm run build:messages` | Generates both locales from one bilingual source, so parity is guaranteed by construction. |
| `npm run check` | Runs all four checks. |
