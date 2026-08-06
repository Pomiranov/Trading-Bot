# SITE_AUDIT.md — Quant website, pre-redesign audit

**Date:** 2026-07-27
**Repo:** `/Users/danila/Downloads/Trading-Bot-merge-learning-nik`
**Branch:** `merge-learning-nik` · HEAD `90877d4`
**Scope:** `website/` only. No backend or trading-core code was modified.
**Method:** static source reading, dependency/import graph tracing, `mp4` box parsing + AVFoundation frame decoding, and cross-verification of every marketing claim against the Python backend.

---

## 0. Working-directory conflict — resolved, but `CLAUDE.md` is wrong

`CLAUDE.md` states the canonical root is `/Users/danila/Documents/GitHub/Trading-Bot/` and that `~/Downloads/Trading-Bot-*` are "stale copies" that must never be edited. **That is now inverted.**

| | Documents/GitHub/Trading-Bot | Downloads/Trading-Bot-merge-learning-nik |
|---|---|---|
| HEAD | `7f267fd` (2026-07-20) | **`90877d4` (2026-07-22)** — 5 commits ahead |
| Files under `website/` | 92 | **128** |

Both are on `merge-learning-nik` and share the same remote. This copy is the live one. Work proceeds here as instructed; **`CLAUDE.md` needs its paths corrected** so the next session isn't misdirected.

---

## 1. Project structure

```
Trading-Bot/
├── bot/                 Python app (Telegram + Flask dashboard + trading core)
├── website/             ← THIS AUDIT. Next.js marketing site
├── knowledge/           rules YAML + research journal (source of truth for strategy statuses)
├── tests/  docs/  infra/  data/  design/
└── Create_a_*.mp4 ×3    untracked AI-generated video prototypes (repo root)
```

## 2. Package manager

**npm.** `website/package-lock.json` (463 KB) is the only lockfile — no pnpm/yarn/bun lockfile present. `node_modules` installed (617 entries).

## 3. Frontend app location

`website/` — a standalone Next.js app, not nested in the Python tree.

- Next.js **15.5.20**, React **19.1.0**, TypeScript strict, **App Router**, `src/` directory in use.
- **Tailwind v4, CSS-first.** There is no `tailwind.config.*` at all; all theme extension lives in `@theme` blocks. `postcss.config.mjs` loads only `@tailwindcss/postcss`.
- `next.config.ts`: `typedRoutes: true`, injects `NEXT_PUBLIC_BUILD_SHA` via `git rev-parse` at config load, wrapped in `createNextIntlPlugin("./src/lib/i18n/request.ts")`.
- `tsconfig.json`: one alias, `@/*` → `./src/*`.

**Build health before any changes:** `npx tsc --noEmit` exits **0**. Prior build output present (`.next/server/app/en.html`, `ru.html`). No pre-existing build failure — the stop condition does not trigger.

## 4. Current homepage route

There is **no** `src/app/page.tsx` and no root `src/app/layout.tsx`. `/` is not a real route — `next-intl` middleware with `localePrefix: "always"` redirects `/` → `/en`. The homepage is entirely `website/src/app/[locale]/page.tsx`.

## 5. Current `/ru` route

Served by the dynamic segment: `website/src/app/[locale]/page.tsx` with `locale === "ru"`. No literal `ru/` directory. Both locales are prerendered via `generateStaticParams()` in `[locale]/layout.tsx`. `en` is `defaultLocale`; **Russian is currently secondary**, which contradicts the brief's Russian-first direction.

Full route inventory:

| Path | Kind |
|---|---|
| `src/app/[locale]/layout.tsx` | locale root layout (owns `<html>`/`<body>`) |
| `src/app/[locale]/page.tsx` | homepage |
| `src/app/[locale]/style-tile/page.tsx` | internal design-token showcase |
| `src/app/api/beta/route.ts` | `POST /api/beta` — the only API route |
| `src/app/robots.ts`, `sitemap.ts` | metadata routes |

`middleware.ts` currently sits mid-rename (`website/middleware.ts` → `website/src/middleware.ts`, unstaged, with a corrected import path). It does locale negotiation only — **no CSP and no security headers anywhere in the app.**

## 6. Current section list

15 children of `<main>` in `[locale]/page.tsx`, in order:

`SiteHeader` · `HeroSection` · `PhilosophySection` · `EnginePipelineSection` · `LearningSystemSection` · `DashboardPreviewSection` · `TelegramBotSection` · `BrokerIntegrationsSection` · `SandboxSection` · `StrategyTable` · `PricingSection` · `FaqSection` · `CtaSection` · `Footer` · `ScrollAnalytics`

Eyebrow numbering stops after `04` — eight later blocks are unnumbered.

## 7. Current header and CTA logic

Fixed glass header consuming `--z-nav`. Monogram + 5 desktop anchor links + EN/RU switcher (next-intl `Link`) + `HeaderCta` + `MobileNav`.

**Every CTA funnels to one destination.** `HeaderCta`, `HeroCta` primary, `MobileNav` CTA and `PricingSection`'s "Join the waitlist" all point at `#cta-heading` → the beta email form. There is no sandbox path, no product entry, no login.

## 8. Current design tokens

Five `@theme` files under `src/styles/tokens/`, imported by `globals.css`.

**The palette is already on-brief:** deep black `#050505`, single orange accent `#ff8a1e`, green `#2ce97b`, red `#e5484d`. No purple, no blue AI gradient, no neon. The brief's proposed values are a refinement, not a replacement.

| Token file | Notable |
|---|---|
| `color.css` | `--color-bg #050505`, `--color-surface #0a0a0a`, `--color-panel #111`, text primary/secondary/tertiary at 1.0/0.7/0.38, accent family, glass layer, `--blur-glass 24px` |
| `typography.css` | `--text-label 11px`, `--text-body 16px`, `--text-lead 18px`, 3 fluid steps (`--text-hero`, `--text-section-heading`, `--text-display-number`) |
| `spacing.css` | `--space-section-y clamp(96px,14vw,240px)`, `--space-page-x clamp(24px,8vw,120px)`, `--space-content-max 1440px` |
| `motion.css` | 4 durations, 3 eases |
| `z-index.css` | explicit 8-step scale |

**Tokens declared but unused (zero production consumers):** the entire `motion.css` file (only the style-tile *lists* it), `--space-content-max`, `--space-grid-gutter`, `--text-display-number`, `--blur-glass-sm`, `--color-stabilized`, `--color-accent-dim`, `--color-accent-glow`, `--color-accent-glow-strong`, `--color-accent-highlight`, `--color-border-subtle`, `--radius-sm`, `--radius-xl`, and six of eight z-index steps.

## 9. Current typography

`src/lib/fonts.ts` — Geist (sans), Geist Mono, Cormorant Garamond (serif accent), all via `next/font/google`, self-hosted at build. **`subsets: ["latin", "cyrillic"]` on all three** — Cyrillic coverage is correct and needs no change.

**Scale discipline has failed:** 128 arbitrary `text-[Npx]` utilities against 41 token-class uses — 3:1 against the system — across 11 discrete pixel sizes. Worst offenders `dashboard-mockup.tsx` (33) and `pricing-section.tsx` (12). Also 23 inline text-opacity levels against 3 semantic tokens; the semantic colour classes are used **zero** times.

## 10. Current animation stack

| Library | Version | Real usage |
|---|---|---|
| `gsap` | ^3.15.0 | `engine-pipeline-scroller.tsx` only — ScrollTrigger pin + horizontal scrub, desktop `matchMedia` only, reduced-motion early exit |
| `motion` (Framer) | ^12.42.2 | `faq-section`, `mobile-nav`, `reveal.tsx`, `magnetic-button`, `header-cta`, `hero-cta` |
| `lenis` | ^1.3.25 | `motion/scroll-driver.ts` + `lenis-provider.tsx` |
| `three` + `@react-three/fiber` + `@react-three/drei` | 0.185 / 9.6 / 10.7 | **entirely dead — see §14** |

## 11. GSAP usage

One file. `ScrollTrigger` pin with `pinSpacing`, distance computed as `track.scrollWidth - wrap.clientWidth` with `if (distance <= 0) return`. Uses the **deprecated** `ScrollTrigger.matchMedia` (deprecated since 3.11; 3.15 installed). Correctly early-exits under reduced motion.

Two fragilities worth recording: an `overflow-hidden` ancestor silently kills pinning (this section is the one that *doesn't* set it, which is why it works), and a wrong container width silently disables the animation with no error.

## 12. Framer Motion usage

`reveal.tsx` is the shared `whileInView` fade/rise with 70 ms stagger and `useReducedMotion` opt-out — used by 10 sections. `faq-section.tsx` is the only client component reading `useTranslations` directly.

**Latent hydration bug found:** framer-motion's `useReducedMotion` reads the preference during the *first* render (`const [shouldReduceMotion] = useState(prefersReducedMotion.current)`). `hero-cta.tsx` branches **markup** on it (`reduce ? <a> : <motion.div>`), so reduced-motion users get a server/client tree divergence.

## 13. Lenis usage

`scroll-driver.ts` owns a single Lenis + GSAP ScrollTrigger RAF loop via `gsap.ticker`, and never instantiates Lenis under `prefers-reduced-motion`. `lenis-provider.tsx` intercepts all `a[href^='#']` clicks with an 80 px nav offset. Well built.

**Gap:** a stale anchor fails **silently** — `document.querySelector(href)` misses and nothing happens, no warning. With 9 anchor ids about to change, this is the single most likely undetected regression.

**Gap:** Lenis `smoothWheel` swallows horizontal trackpad gestures. No element uses `data-lenis-prevent`, so both horizontally-scrolling regions (§19) will still feel broken on a Mac trackpad even after their CSS is fixed.

## 14. Duplicated glass/card/button styles

Quantified, with call sites:

- **Glass surfaces: 11 implementations.** `ui/panel.tsx`, `ui/glass-panel.tsx` (zero importers), the `.glass-premium` / `.glass-premium-featured` classes, and 9 hand-rolled blocks (`site-header:34-43`, `mobile-nav:86-99`, `hero-section:149-157`, `sandbox-section:16-23`, `pricing-section:104-122` and `:172-174`, `dashboard-mockup:191-197`, `cta-section:87-93`, `beta-form:61-68`).
- **`pricing-section.tsx:112-122` hand-copies the exact `mask-composite: exclude` gradient border** that `.glass-premium-featured` already ships in `globals.css:152-169` and that `ui/glass-panel.tsx`'s `featured` variant already wraps. Three implementations of one effect.
- **Buttons: 4 paths.** `ui/button.tsx` + `buttonVariants` (the intended source of truth), plus bare `buttonVariants` anchors in `pricing-section:214`, plus a hand-rolled gradient anchor in `mobile-nav:158-174`.
- **Stat treatments: 5.** `ui/stat-number.tsx` plus hand-rolled copies in `hero-section:109-138`, `sandbox-section:71-95`, `cta-section:81-111`, and the `dashboard-mockup` metric tiles.
- **Status dots/pills: 5.** `ui/status-pill.tsx` plus `brokers:104-118`, `footer:60-74`, `hero:40-63`, `hero:174-187`.
- **Eyebrow labels: 8 inline copies** at 10px/0.18em, while `ui/mono-label.tsx` (the token-correct 11px/0.16em) is used **only by the style-tile**.
- **`faq-section.tsx:95-106` reimplements `SectionHeading` inline** with the same five CSS variables.

## 15. Duplicated magnetic / hover logic

**Magnetic spring maths exists 3× near-identically** — `ui/magnetic-button.tsx`, `nav/header-cta.tsx:8-33`, `hero/hero-cta.tsx:8-39` — same `useMotionValue`/`useSpring`/clamp, differing only in `RADIUS` (12 / 10 / 14).

**Arrow-link hover exists 2×** — `hero-cta.tsx:71-86` and `cta/explore-link.tsx`, identical `onMouseEnter`/`onMouseLeave` colour mutation. Both land at **3.07:1** contrast with a 20 px hit area.

## 16. i18n structure

Two layers, both clean in design:

1. **UI strings** — `messages/{en,ru}.json`, loaded by `src/lib/i18n/request.ts`, hydrated via `NextIntlClientProvider`. 13 namespaces.
2. **Long-form content** — MDX + JSON per locale under `content/{en,ru}/`, read at build time through a swappable `ContentSource` interface (`src/content-layer/`). 11 files per locale.

`scripts/check-content-parity.mjs` (`npm run check:content`) enforces MDX filename parity, `learning-system.mdx` presence, and `strategies.json` id parity plus field equality on `market`/`timeframe`/`status`/`source`.

**Gap: there is no parity guard on `messages/*.json`** — only on `content/`. Given RU/EN parity is a hard requirement, this is the most valuable missing check.

## 17. RU/EN parity

**Currently exact: 184 leaf keys per locale, 224 lines each, zero asymmetry.** Content files are symmetric 11-for-11.

Two content defects, not parity defects:

- `philosophy/02-what-we-dont.mdx:7` says confidence is held **"between 20% and 80%"** / «между 20% и 80%» in both locales, while `learning-system.mdx`, `confidence-data.ts` and the message files all use **0.05/0.95**. The site contradicts itself, and the code says 0.05/0.95 (`bot/learning/belief_updater.py:46-47`).
- `scene.*` (5 keys × 2) and `nav.menu` are dead — no call site.

## 18. Current media assets

**`website/public/` contains exactly one file:** `public/fallback/hero.png` (101 KB) — and it is **orphaned**, referenced only by the unused `hero-scene-mount.tsx`. `public/fonts/` and `public/og/` exist but are **empty**, so neither is in git.

No `<video>` element exists anywhere in the site today.

### The three prototype videos (repo root, untracked)

Measured by parsing `mp4` boxes and decoding frames via AVFoundation:

| File | Size | Notes |
|---|---|---|
| `Create_a_premium_black_and_whi.mp4` | 1,989,550 B | **selected as hero prototype** |
| `Create_a_black_and_white_abstr.mp4` | 2,312,271 B | rejected |
| `Create_a_premium_monochrome_D.mp4` | 2,564,928 B | rejected (generic dashboard) |

All three: **1280×720, exactly 24.000 fps, 10.000 s, H.264 + AAC stereo 48 kHz.**

Facts about the selected file that constrain the design:

- **Faststart-optimised** — `ftyp`+`uuid`+`moov` = 14,607 B before `mdat`, so `preload="metadata"` costs ~15 KB, not 2 MB.
- **C2PA provenance manifest** in a `uuid` box (`d8fec3d6-1b0e-483c-9297-5828877ec481`, 6,282 B), signed *Google C2PA Media Services 1P ICA G3*, timestamped `2026-07-26T20:57:26Z`.
- **Burned-in visible mark located at x ≈ 88–94 %, y ≈ 86–92 %** — verified identical at t=0.05/0.5/5.0/9.9 s. This hard-constrains framing (see plan §Hero).
- **Subject:** Q aperture spans x 42–88 %, y 15–90 %, centroid ≈ 70 % / 51 %; orange core peaks at **t = 6.0 s**. The left third (x 0–35 %) is empty black on every frame.
- **It does not loop.** Mean luma t=0 → 2.3/255 (pure black), t=9.9 → 16.7. `loop` produces a hard black flash every 10 s.
- **1.99 MB is 2.2× over** a reasonable 900 KB hero budget.

**Tooling reality:** `ffmpeg`/`ffprobe` are **absent**. Available and verified working: Swift 6.3.3 + AVFoundation (exact-frame decode), `sharp` 0.34.5 with librsvg + libwebp (SVG → WebP). `sips` **cannot write** WebP (read-only in `sips --formats`). `qlmanage -t` would yield a black frame (t=0 is black). Playwright's bundled ffmpeg is built `--disable-everything` — no H.264 decoder, no mp4 demuxer.

## 19. Responsiveness

Breakpoint ladder is mixed: `md:768 / lg:1024 / xl:1440` are overridden but `sm` and `2xl` keep Tailwind defaults, so `sm:640` sits under a custom `md:768`.

**Two confirmed mobile bugs, both irrecoverable content loss at 375 px:**

1. **`strategy-table.tsx:56-63`** — `overflow-x-auto` is on the `Reveal`, but an inner `div.rounded-xl.overflow-hidden` wraps a `min-w-[760px]` table and clips it. Measured `clientW 307 / scrollW 760`. **453 px of table is unreachable**; only `STRATEGY` and part of `MARKET` are visible.
2. **`dashboard-mockup.tsx:228-231`** — the tab row sits inside the `overflow-hidden rounded-xl` frame at `:192`. Measured `clientW 307 / scrollW 410`. **The `SIGNALS` tab cannot be reached.**

**Grid does not hold:** section `h2`s land on **7 different left edges** (115/237/254/267/337/425/643 px) across **7 different container widths** (1204/1040/960/900/760/1280/1434). `--space-content-max` is declared but unused outside the style-tile.

All 12 blocks share an identical **201.6 px** vertical padding — a metronome, not a rhythm.

## 20. Accessibility

**Passing:** semantic landmarks and `aria-labelledby` on every section; status never conveyed by colour alone; the confidence slider is properly `role="slider"` with keyboard support and aria values; no horizontal page scroll on mobile.

**Failing:**

- **Contrast.** ~33 distinct text styles fail WCAG AA, much service text at 1.4–3.4:1. Worst: footer copyright **1.43:1**, pipeline captions **1.65:1**, build SHA **1.71:1**, dashboard-mockup labels 1.88–2.44:1, the `RU` locale toggle **2.53:1**, nav links **3.71:1**, arrow links **3.07:1**.
- **Focus.** `faq-section.tsx:29` sets `outline: "none"` with **no replacement**, defeating the global `:focus-visible` rule. The email input's ring is replaced by an 8 %-opacity outline.
- **Labels.** The email field's only label is `sr-only`.
- **Target size (WCAG 2.2).** Nav links 18 px, EN/RU toggle 15×18, slider handle 16×16, footer links 18 px, arrow links 20 px.

## 21. Reduced motion

**Genuinely thorough** — this is a strength. Three coordinated layers: a global `@media (prefers-reduced-motion: reduce)` block in `globals.css:223-232`, `useReducedMotion` in `reveal.tsx`, and a GSAP early-exit plus Lenis never instantiating.

Two defects: the `hero-cta.tsx` markup branch (§12) is a hydration mismatch, and the global block's `animation-duration: 0.01ms !important` is a blunt instrument that will also neutralise any intended crossfade.

## 22. Console errors

Not captured live in this pass — the dev server was not started, so no runtime console baseline exists yet. Static analysis surfaces two likely sources: `dashboard-mockup.tsx:176-189` injects a `<style>` tag from inside a client component, and `layout.tsx:82` sets `suppressHydrationWarning` on `<html>`, which will **mask** real mismatches. Live capture at 5 viewports is the Phase 3 entry gate (plan §QA).

## 23. Hydration errors

One confirmed latent mismatch (`hero-cta.tsx`, §12), masked in practice by `suppressHydrationWarning`.

Two risks to manage during the rebuild: `Intl.NumberFormat`/`DateTimeFormat` at `strategy-table.tsx:39` and `stat-number.tsx:24` must stay server-side (Node and browser ICU can disagree on separators), and `layout.tsx:84` currently ships **all 184 keys** to the browser via `getMessages()`.

## 24. Bundle / performance concerns

- **`three` + `@react-three/fiber` + `@react-three/drei` are shipped for nothing.** Ten scene files, ~40 MB of transitive install, zero render paths. Nothing imports `HeroSceneMount` or `SectionSceneMount`.
- **`lucide-react` is installed and never imported** — icons are hand-rolled inline SVG. `components.json` sets `"iconLibrary": "lucide"`, so `npx shadcn add` would silently reinstall it.
- **`tw-animate-css`** is imported in `globals.css:8`; its only `animate-*` consumers were the dead scene mounts.
- **LCP is self-blocked.** `qf-hero-enter` starts at `opacity: 0` with fill-mode `both` and a **0.15 s delay** on the hero's right column. Chrome's LCP algorithm ignores fully transparent elements, so the hero visual is LCP-ineligible for ≥150 ms.
- `hero-scene-mount.tsx` puts `priority` on the orphaned `hero.png` — a high-priority fetch for an image that never renders.
- Vercel serves `/public` with `max-age=0, must-revalidate`, so a 2 MB video would revalidate on every navigation.
- `dashboard-mockup.tsx` is 461 lines with 33 arbitrary font sizes — the largest single component.

## 25. Marketing claims that may be misleading

Every claim was traced to code. Full evidence table in `SITE_REDESIGN_PLAN.md`; the material findings below. **Four further defects live only in the rendered hero canvas and are documented in §26** — they are invisible to any audit of the message files, because the strings are hardcoded inside the component.

| Severity | Claim | Reality |
|---|---|---|
| **Critical** | All three brokers badged **"Integrated"** with a green dot (`broker-integrations-section.tsx:104-118`) | **Finam is nine `NotImplementedError`s** (`bot/broker/providers/finam.py:63-118`), `is_connected=False` hardcoded at `:56`, constructed with empty credentials. **Bybit is not in `bot/broker/registry.py:46-52`** — its order code is unreachable; only read-only balance use at `portfolio_service.py:80-107`. Only T-Invest is real. |
| **Critical** | Beta form shows *"Request received. We follow up if it's a fit."* | `src/lib/beta/adapter.ts:12-18` only `console.log`s the address and discards it. No DB, no email, no CRM. The success state is shown for a submission that went nowhere. |
| **High** | Hero stats **58.6% / 1.16× / 29**, sourced as `"real-forward-test"` | It is a **backtest out-of-sample holdout** (`bot/backtest/run_osc_oos_debug.py`), not a forward test — *and* it is the **filter-OFF variant the project rejected**. The shipped config is `n=18 / WR 72.2% / PF 1.67` (`knowledge/processed/strategies/structural_downtrend_filter.md:41-45`). |
| **High** | `wrd_moex` "drawdown −936000", n=191 with PF 0.65 | −936k is **cumulative PnL, not drawdown**; n=191 pairs with PF **0.86** (full period), while 0.65 is OOS-only (`knowledge/rules/rules_wrd_moex.yaml:28-29`). |
| **High** | Confidence "held between 20% and 80%" | Code clamps **0.05–0.95** (`belief_updater.py:46-47`). Contradicts the site's own `learning-system.mdx`. |
| **High** | *"Every position size is a mathematical function of conviction"* | `position_size_multiplier` is computed (`trading_orchestrator.py:240-255`) and **never applied**. `bot/run_forward_d1.py:19-20` says so explicitly: «логируется, но НЕ применяется». |
| **High** | *"A strategy earns capital allocation only after 20 verified trades"* | An unknown strategy is bootstrapped at confidence 0.5 and **approved immediately** with zero trades (`trading_orchestrator.py:186-200`). |
| Medium | Dashboard Sharpe **1.34** "90-day rolling", ₽1,048,230, +8.3%, −4.8% | Fabricated. Sharpe *is* computed (`belief_updater.py:226-242`) but **no 90-day rolling window exists**. |
| Medium | *"MOEX & Crypto market access"*, *"T-Invest & Bybit routing"*, mock row `ob_bybit_h4` | **No crypto strategy exists**; tickers are MOEX-only. H4 explicitly abandoned in `rules_osc_range.yaml:23-25`. |
| Medium | Mock toast *"Strategy osc_range frozen · conf below 0.30"* | Threshold is **0.20** and it blocks *signals*, not strategies. **No auto-freeze code exists**; `belief_system` has no status column. |
| Medium | Hero `LIVE ·` pill, footer *"Systems operational"* + green dot | Both **static text with no telemetry**. Real health endpoints exist and are unused. |
| Medium | *"Same RulesEngine, same belief gate, same RiskManager"* (paper) | RulesEngine ✅. **RiskManager ❌** — `paper_engine.py:609-618` docstring says it *"must NOT touch risk.risk_manager"*. **Belief gate ❌** — not in the paper execution path. |
| Medium | Dashboard tabs incl. **Risk** and **History** | Both are **API-only, not pages**. Real views: Dashboard, Portfolio, Signals, Backtest, Analytics, Learning, Settings. |
| Low | *"3 active"* strategies | 1 forward-deployed, 3 tracked. |
| Low | `pricing.badge` "Recommended" on an unpriced tier | No payment code exists anywhere in the repo. |

### Claims that hold up — and one that is *under*-claimed

Verified sound and worth keeping verbatim: the 7-step engine pipeline with **every `sourceRef` resolving** to a real symbol; the anti-AI honesty (**zero ML dependencies** in `requirements.txt`); pre-trade risk enforcement (`bot/main.py:177`, `trade_gateway.py:108-119`); the shared Telegram↔Dashboard state layer; and the "pricing is not live" disclosure.

**Under-claimed:** the site makes **no security claims at all**, yet the code has AES-256-GCM `SecretBox` (`bot/security/encryption.py:38,59`), a `0600` credential vault, and a Postgres append-only audit log. Critically, **`BrokerAdapter` has no withdraw/transfer method in its interface** (`bot/broker/base.py:141-219`) — all six repo-wide `withdraw` hits are a balance field, a history enum, and a notification toggle. *"Quant cannot move money out of your broker account"* is verified by absence and safe to state.

**Honest caveat that must accompany the vault claim:** the vault is opt-in via `SECRETS_MASTER_KEY`; without it, credentials fall back to plaintext `.env` (`bot/security/credential_store.py:50-57`).

---

## 26. Live browser baseline (captured)

Captured against the running dev server on `localhost:3000/ru`, viewport 1440×1000 and 390×844.

### Console — clean

No errors, no warnings, **no hydration warnings**. Only React DevTools notices and Vercel Analytics debug logs. **Caveat:** `layout.tsx:82` sets `suppressHydrationWarning` on `<html>`, so the `hero-cta.tsx` mismatch (§12) would not surface here even though it exists.

### Mobile clipping bugs — both reproduced exactly

Measured DOM at 390 px:

```
DIV.rounded-xl.overflow-hidden   clientW 326 · scrollW 760 · overflow-x: hidden   ← the clip
DIV.overflow-x-auto              clientW 328 · scrollW 328 · overflow-x: auto     ← nothing to scroll
```

**434 px of the strategy table is unreachable.** The `overflow-x-auto` wrapper is inert because the inner `overflow-hidden` already truncated the content — its `scrollWidth` equals its `clientWidth`. `table { min-width: 760px }` confirmed. This is exactly the failure mode §19 predicted, and it confirms the fix must move the border/radius onto the scrolling element itself.

`document.documentElement.scrollWidth > innerWidth` is `false` — no page-level horizontal scroll — but **`<main>` reports `scrollWidth 1434` against `clientWidth 390`**, i.e. 1044 px of overflow is being clipped by an ancestor rather than laid out. Worth watching during the container rework.

### Type and opacity sprawl — worse than the static count

**13 distinct rendered font sizes** on the mobile homepage alone (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 28, 36 px) — the static grep found 11. **7 distinct opacity values**, including three animation-interpolated ones (0.588, 0.867, 0.958).

`<video>` count: **0**. `<canvas>` count: **1** — confirming there is no video today and the hero visual is the 2D canvas.

### New claim defects visible only in the rendered hero

The hero's canvas (`hero-signal-flow.tsx`) carries four problems that source-reading the message files did not reveal, because its labels are **hardcoded English strings inside the component**:

1. **The "CONFIDENCE" chart rises monotonically from 50 % to 80 % with green/red dots — it reads as an equity curve.** Visually it is a profit chart, which is precisely what the brief forbids. It is the single most misleading element in the hero.
2. **Its Y axis is labelled 20 % / 50 % / 80 %** — encoding the *wrong* confidence bounds. The code clamps 0.05–0.95 (`belief_updater.py:46-47`). The hero graphic therefore reproduces the same contradiction as `philosophy/02-what-we-dont.mdx:7`.
3. **`BELIEF GATE — Bayesian bounds`.** There is nothing Bayesian in `belief_updater.py` — no prior, no likelihood, no posterior. It is an EMA toward an equal-weighted mean.
4. **`EXECUTE — T-Invest · Bybit`** implies Bybit order routing, which is unwired (`registry.py:46-52`).

Additionally, all six stage labels (`MARKET DATA`, `INDICATORS`, `RULES ENGINE`, `BELIEF GATE`, `RISK MANAGER`, `EXECUTE`) render **in English on the Russian page** — an i18n hole no message-file audit would catch, since the strings never reach `messages/ru.json`.

### Accent restraint has slipped

`color.css:5` states the intent: *"Orange sits at ~3% of pixels max (institutional restraint)."* In the rendered hero the accent carries the eyebrow pill, all three stat numbers, the full-width gradient CTA, the entire chart line and fill, and the running-status dot simultaneously. The discipline is documented but not held.

### Still outstanding

Screenshots at 1920×1080 / 1024×768 / 320×700, the `/en` pass, LCP/CLS instrumentation, and the reduced-motion network assertion are deferred to Phase 7 QA, where they serve as before/after comparisons rather than baseline-only. Exact checks are specified in [`SITE_REDESIGN_PLAN.md`](./SITE_REDESIGN_PLAN.md) §10.

The responsive and accessibility findings in §19–§21 also draw on `docs/audit/DESIGN_AUDIT_2026-07.md`, which did instrumented DOM measurement at 1440×900 and 375×812.
