# SITE_REDESIGN_PLAN.md — Quant premium redesign

**Date:** 2026-07-27 · **Branch:** `merge-learning-nik` · **Base:** `90877d4`
**Prerequisite:** [`SITE_AUDIT.md`](./SITE_AUDIT.md) — read it first; this plan does not repeat its findings.
**Scope:** `website/` only. **No `bot/` changes.** No trading-core, no schema, no Python.

---

## Context

Why this work is happening, and what it has to fix.

The site is not visually broken — it is already black-and-white with a single orange accent, and its motion layer (GSAP pin, Lenis, coordinated reduced-motion) is genuinely well built. The audit found the real problems elsewhere:

1. **It overstates the product.** Three brokers are badged "Integrated" when only one works. Hero performance figures are a rejected backtest variant mislabelled as a forward test. The site claims confidence bounds the code contradicts. For a product that can place real orders in someone's brokerage account, this is the highest-cost defect on the page.
2. **The only conversion path is a dead end.** Every CTA funnels to a form that `console.log`s the address and discards it, while telling the user they'll be contacted.
3. **The brand is wrong.** QuantFlow → **Quant**, and the positioning needs to become "automated trading operator," not "belief-updating engine."
4. **The design system is declared but not obeyed.** 128 arbitrary font sizes against 41 token uses; 7 container widths; an entire unused Three.js stack; 11 duplicate glass implementations.
5. **Russian is secondary** and must become primary.

The intended outcome: Quant reads as a serious, precise, expensive trading operator — simple enough for a beginner, credible enough for an experienced trader, and honest enough that a partner or investor can verify every claim against the repository.

### Owner decisions governing this plan

| # | Decision |
|---|---|
| 1 | **Remove every result number.** No win rate, profit factor, sample size, Sharpe, P&L, drawdown, equity %, "3 active". Verified *system constants* stay (20-trade floor, 0.05–0.95 bounds, 0.20 signal gate, 5%/2%/5 risk limits). |
| 2 | **Primary CTA = «Получить доступ к песочнице»** → access-request form. **Never «Начать с песочницы»** — there is no self-service onboarding. Secondary = «Посмотреть как работает». Separate lower CTA = «Запросить Live-доступ». |
| 3 | **Refactor + delete dead code.** Reuse the working base. Remove the Three.js scene, orphaned hero visuals, duplicated glass/button/magnetic logic. One HeroVideo pipeline. i18n intact. |
| 4 | **Video 1 only, gitignored, watermark untouched, path-swappable.** Videos 2 and 3 unused. |

---

## 1. New information architecture

| # | Section | `id` | Origin |
|---|---|---|---|
| — | Header | — | REFACTOR `nav/site-header.tsx` |
| 1 | Hero | `hero` | REFACTOR `hero/hero-section.tsx` + new `HeroVideo` |
| 2 | AudienceRouting | `audience` | **NEW** |
| 3 | HowQuantWorks | `how-it-works` | REFACTOR `engine-pipeline/` (+ absorbs Philosophy, Confidence constants) |
| 4 | DashboardShowcase | `dashboard` | REFACTOR `dashboard-preview/` |
| 5 | TelegramOperator | `telegram` | REFACTOR `telegram-bot/` + new signal card |
| 6 | BrokerExecution | `brokers` | REFACTOR `broker-integrations/` |
| 7 | StrategyLab | `strategies` | REFACTOR `strategy-layer/` (+ absorbs confidence slider) |
| 8 | Safety | `safety` | **NEW** (+ absorbs Sandbox) |
| 9 | Pricing | `pricing` | REFACTOR |
| 10 | FAQ | `faq` | REFACTOR + split server/client |
| 11 | FinalCTA | `access` | REFACTOR `cta/` |
| — | Footer | — | REFACTOR |

Convention everywhere: `<section id="{slug}" aria-labelledby="{slug}-heading">`. Nav anchors target `#{slug}`, not `#{slug}-heading`.

**Three sections stop being sections; none of their content is deleted** (this keeps `check:content` green without touching `content/`):

| Retired | Content destination |
|---|---|
| `PhilosophySection` | 3 MDX blocks become the **premise band** atop HowQuantWorks. `getPhilosophyBlocks` stays alive. |
| `LearningSystemSection` | Confidence slider + chart + data `git mv` to `strategies/`; the 20-trade / 0.05 / 0.95 trio becomes HowQuantWorks step 4. `getLearningSystemCopy` stays alive. |
| `SandboxSection` | Folds into Safety as the sandbox-before-live pillar. All 12 `sandbox.*` keys survive. |

`07-memory-writer.mdx` is **kept** and rendered as the closing feedback-loop arrow beneath the 6 steps — no content deletion, and it honestly shows the loop.

---

## 2. Section-by-section redesign

**Header** — brand "Quant" (from `nav.brand`, currently hardcoded in two files). Nav: Продукт → `#dashboard`, Как работает → `#how-it-works`, Безопасность → `#safety`, Тарифы → `#pricing`, FAQ → `#faq`. Primary CTA → `#access`. Locale toggle contrast lifted from 2.53:1 and hit area to ≥24 px.

**Hero** — two columns. Left: eyebrow, two-line headline, subline, two CTAs, proof strip. Right: `HeroVideo` at **16/9** (not the current `aspect-square` — see §5). Below: a three-tile row that replaces the deleted performance stats with **risk limits** — 5% на позицию / 2% дневной лимит / порог сигнала 0.20 — all config-backed. Entrance becomes **transform-only** (no `opacity`) so the poster stays LCP-eligible.

**AudienceRouting** *(new)* — "Один Quant. Разный уровень контроля." Three cards: Новичку → Safety, Трейдеру → HowQuantWorks, Партнёру/разработчику → BrokerExecution. Same product at three depths.

**HowQuantWorks** — premise band (3 philosophy blocks), then 6 steps, each with a **simple line first, technical module second**, keeping the existing desktop pin/pan and mobile `<ol>` fallback. GSAP migrated off deprecated `ScrollTrigger.matchMedia`.

| Step | Simple (RU) | Technical |
|---|---|---|
| Observe | Quant смотрит на свечи и ничего не додумывает | `loader.get_candles()` |
| Context | Определяет, в каком режиме рынок | `IndicatorEngine.latest()` → `classify_regime(adx)` |
| Strategy | Проверяет условия стратегии по правилам | `RulesEngine.evaluate()` |
| Confidence | Измеряет, насколько стратегия себя оправдывает | `TradingOrchestrator.check_signal()`, порог 0.20 |
| Risk | Считает размер и проверяет лимиты до входа | `RiskManager.calculate_position()` → `check_trade_allowed()` |
| Execute | Отправляет заявку через ваш брокерский аккаунт | `TinkoffClient.place_market_order()` |
| ↩ loop | Записывает решение отдельно от результата | `MemoryWriter.save_trade()` |

**DashboardShowcase** — operator terminal, not a fake filled dashboard. Shows the **seven real views** (Dashboard, Portfolio, Signals, Backtest, Analytics, Learning, Settings) with an explicit note that Risk and History are API-only. The mockup keeps its chrome, tabs, table structure and decision states (`исполнено` / `заблокировано` / `песочница`) but **every fabricated figure is removed**. Fixes the clipped tab row.

**TelegramOperator** — four features. The signal card is rendered honestly: it has a confidence bar and **one button, «Исполнить в песочнице»**. The two-step Confirm/Cancel is described separately as the *manual order* path, because that is where it actually lives. Auto mode is real and stated with its manual-stop caveat.

**BrokerExecution** — per-broker badges from a status vocabulary defined once:

| Broker | Badge | RU one-liner |
|---|---|---|
| T-Invest | **Активен · Песочница по умолчанию** | Рабочий маршрут для MOEX. Один клиент обслуживает и песочницу, и Live — по умолчанию включена песочница, переключение делается вручную. |
| Bybit | **Бета · только чтение** | Подключён для чтения балансов и позиций. Отправка заявок через Bybit не включена, крипто-стратегий в системе пока нет. |
| Финам | **Планируется** | Адаптер заведён, методы ещё не реализованы. Второй независимый маршрут для MOEX — после T-Invest. |

`brokerIntegrations.integrated` is deleted. The "Crypto" market pill on Bybit is removed — it advertises a market the system doesn't trade. `validation` stays **unassigned**; no broker qualifies.

**StrategyLab** — "Стратегии продвигаются доказательствами, а не обещаниями." Four lifecycle lanes, table of `id / market / timeframe / status / lastUpdate` — **no metrics column**. Honest lane occupancy:

| Lane | Rows |
|---|---|
| Активная | **0** — rendered as an explicit empty lane |
| Форвард | `osc_range_moex_d1_fwd` |
| Кандидат | **0** |
| Заморожена | `trend_moex`, `wrd_moex` |

Two disclosure lines carry the section: statuses are hand-maintained in the research journal (no DB field, no auto-freeze), and we don't publish result figures — the status *is* the information. **Keeping the Active lane visibly empty is the most credible element on the page**; frozen strategies read as discipline. Fixes the 453 px table clip.

**Safety** — six pillars: Quant не выводит средства (verified by absence of any withdraw method in `BrokerAdapter`) · пределы риска до входа · ограниченная уверенность 0.05–0.95 · остановка вручную (**explicitly: автоматического kill switch нет**) · шифрование ключей AES-256-GCM + журнал аудита, **с оговоркой** про `SECRETS_MASTER_KEY` · песочница по умолчанию.

**Pricing** — Explore / Sandbox / Live, 4 features each. `pricing.badge` ("Рекомендуется") deleted — recommending an unpriced tier is a pattern with nothing behind it. Live tier states its gates: valid broker key, no withdrawal permission, risk settings, consent, manual stop. CTA → «Запросить доступ». "Bybit routing" removed from the Live tier.

**FAQ** — 5 → 10 questions per the brief, server shell + client list, `outline: "none"` removed.

**FinalCTA** — «Начните с песочницы. Перейдите к Live, когда будете готовы.» Primary form + a separate «Запросить Live-доступ» block.

---

## 3. Copy map RU/EN

Russian is authored first; English is a parity translation, not the source.

**Hero (RU)**

> **Рынок создаёт шум.**
> **Quant превращает его в решение.**
>
> Автоматический торговый оператор для MOEX и Bybit: анализирует рынок, проверяет стратегию, ограничивает риск и исполняет сделку через ваш брокерский аккаунт.
>
> `[Получить доступ к песочнице]` `[Посмотреть как работает →]`
>
> Eyebrow: Закрытое тестирование · MOEX · песочница по умолчанию
> Proof: Песочница · Telegram · Dashboard · MOEX + Bybit · Пределы риска

Note the eyebrow replaces `LIVE · MOEX D1 · osc_range_moex_d1_fwd` — "LIVE" beside a strategy id implies live capital, which `TINKOFF_SANDBOX=true` contradicts.

### i18n restructure

The `sections{}` namespace is a grab-bag serving six components and is the main source of drift — it is **deleted** and split. One namespace per section.

| Namespace | Verdict |
|---|---|
| `seo` | KEEP, extend to 4 (adds `ogTitle`, `ogDescription`) |
| `nav`, `hero`, `pricing`, `faq`, `footer` | KEEP name, rewrite contents |
| `scene` (5) | **DELETE** — dead |
| `sections` (31) | **DELETE** — split into `how`, `dashboard`, `strategyLab`, `finalCta` |
| `sandbox` (11) | **DELETE** — folded into `safety` / `pricing` / `faq` |
| `telegramBot` → `telegram`, `brokerIntegrations` → `brokers`, `dashboardMockup` → `dashboard.mock`, `beta` → `accessForm` | RENAME |
| `common`, `audience`, `how`, `strategyLab`, `safety`, `finalCta` | **ADD** |

`common` holds the status vocabulary (`brokerStatus.*`, `strategyStatus.*`), the simple/technical toggle labels, and the site-wide no-results disclosure — so a status word is defined **once**.

**Leaf count: 184 → 258 per locale.** Both files must stay key-identical, enforced by a new guard (§4).

### FAQ questions (RU)

Это AI? · Можно ли начать без риска для капитала? · Что такое песочница? · Кто принимает решение? · Можно ли подтверждать сделки вручную? · Где хранятся API-ключи? · Может ли Quant выводить деньги? · Есть ли гарантированная доходность? · Какие рынки поддерживаются? · Когда доступен Live?

Answers are grounded in code, not aspiration. "Это AI?" answers: no ML dependencies exist; confidence is a smoothed move toward a target derived from the equal-weighted mean of win rate, profit factor and expectancy, step 0.15, bounded 0.05–0.95. **Never "Bayesian"** — there is no prior, likelihood or posterior in `belief_updater.py`.

### Brand rename — 32 occurrences

Copy: `messages/{en,ru}.json` lines 3, 4, 7, 21, 57, 177 (×2). MDX: `content/{en,ru}/philosophy/01-what-bots-do.mdx:7`. Components: `site-header.tsx:48,59`, `footer.tsx:48`, `dashboard-mockup.tsx:218`, `monogram.tsx:25`, `style-tile/page.tsx:47,195`. Metadata: `layout.tsx:21,50`, `sitemap.ts:4`, `robots.ts:3`, `.env.example`. Comments: `monogram.tsx:4`, `typography.css:2`, `color.css:2`.

**Deliberately not renamed:** `docs/audit/*.md` (dated records — rewriting them falsifies history; add a one-line "written pre-rename" note instead), `qf-*` keyframe names, `--qf-accent` references that quote backend variable names, and `icon.svg`/`favicon.ico` (geometric, no letterforms).

### Forbidden wording — enforced

гарантированная прибыль · risk-free · без риска · предсказывает рынок · революционный AI · fully autonomous · institutional-grade · automatic kill switch · "fully integrated broker". `footer.tagline1` loses "институционального уровня" — nothing in the repo justifies it.

---

## 4. Component plan

### Final `ui/` roster

| File | Status | Collapses |
|---|---|---|
| `section.tsx` | **NEW** | 13 bespoke section shells, 7 container widths, 7 left edges |
| `section-header.tsx` | **NEW** | 8 inline eyebrow+heading pairs |
| `surface.tsx` | **NEW** | `panel.tsx` + `glass-panel.tsx` + 9 hand-rolled glass blocks + 3 copies of the featured gradient border |
| `magnetic.tsx` | **NEW** | 3 copies of the spring maths → 1 |
| `button-link.tsx` | **NEW** | 4 CTA anchor implementations → 1 |
| `arrow-link.tsx` | **NEW** | 2 copies; adds focus-visible + ≥44 px hit area |
| `icon.tsx` | **NEW** | inline SVGs from `telegram-bot-section.tsx:5-37`, shared with brokers/safety |
| `stat.tsx` | RENAME from `stat-number.tsx` | 5 hand-rolled stat treatments → 1 |
| `status-pill.tsx` | MODIFY | + 4 hand-rolled dots; `StrategyStatus` becomes `active\|forward\|candidate\|frozen` |
| `mono-label.tsx`, `section-heading.tsx`, `button.tsx`, `monogram.tsx` | MODIFY | now actually adopted |
| `magnetic-button.tsx`, `panel.tsx`, `glass-panel.tsx` | **DELETE** | |

`lib/strategy-status.ts` is **new**, moving the status type out of the UI layer so `content-layer/types.ts` stops importing from `@/components/ui/status-pill`.

### The section shell — one container, one edge

```
Section props: id · rhythm("hero"|"major"|"default"|"tight") · width("content"|"prose")
               divider · glow · children        +  SectionBleed for full-bleed children
```

Three rules, each fixing a measured defect:

1. **Never `overflow-hidden` on `<section>`** — it silently kills GSAP pinning. Six sections currently set it for their glow; the one that doesn't is precisely the one whose pin works. Glows move into a clipped `aria-hidden` child, so they can no longer leak *or* break pinning.
2. Inner `mx-auto max-w-[var(--space-content-max)]` — **one** width. Set to **1280px** (from the unused 1440px), matching the header's existing `max-w-[1280px]`, so header and content share one edge at every viewport.
3. `divider` replaces the positional hack `main > *:not(:first-child):not(:nth-child(2))` in `globals.css:219-221`, which breaks the moment `SiteHeader` moves out of `<main>` and again when GSAP injects a pin-spacer.

Resulting vertical grouping, visible without labels: `[Hero] · [Audience] · [HowItWorks] · [Dashboard · Telegram · Brokers] · [Strategies · Safety] · [Pricing · FAQ · Access]`.

### New guard scripts

- **`check-messages-parity.mjs`** (`check:i18n`) — there is currently **no** guard on `messages/*.json`, only on `content/`. This plan adds ~74 keys per locale; this is the highest-value new file here.
- **`check-design-tokens.mjs`** (`check:design`) — fails on `text-\[\d+px\]` or raw `rgba(255,255,255,` above a budget. `eslint-plugin-tailwindcss` has no working v4 support, so a grep gate is the pragmatic option and is what prevents the 128-arbitrary-size drift from returning.
- **`check-media.mjs`** (`check:media`) — **warn-only, always exits 0.** Reports absent optional video; fails nothing.

### `strategies.json` and the parity script

New shape drops `metrics{}` entirely, keeps `id / market / timeframe / status / statusNote / lastUpdate / source`. `status` becomes `forward` (was `live`) and `frozen` for both `trend_moex` and `wrd_moex`.

**No change to `check-content-parity.mjs` is required** — it compares `["market","timeframe","status","source"]` and never reads `metrics`. Two traps to avoid: new MDX frontmatter fields (`stepLabel`, `plain`) are **invisible** to the script, so EN/RU can drift undetected; and renaming `status` without editing the field list at `:104` would make the comparison pass **vacuously**. Recommended hardening (~6 lines): fail if either locale contains a `metrics` key, and validate `status` against the four allowed values — turning "no result numbers" from a convention into a CI gate.

---

## 5. Video placement plan

**One video, one placement: the hero, right column.** Videos 2 and 3 are documented as rejected references and never wired.

### Framing is dictated by the measured watermark

The mark sits at **x 88–94 %, y 86–92 %**. With `object-fit: cover` and `object-position: 70% x`, the visible right edge of the source is `896 + 0.3·W′`:

| Container aspect | Cropped | Watermark | Q form |
|---|---|---|---|
| **16 / 9** | **0 %** | **intact** | **intact** |
| 1.41 (hard floor) | 21 % | at the edge | intact |
| 4 / 3 | 25 % | **clipped** | marginal |
| **1 / 1 (today's `aspect-square`)** | 44 % | **clipped** | **clipped** |

So: **default `16/9`, never below `1.41`.** At 16/9 the cover crop is a no-op, which makes cropping-out the watermark structurally impossible rather than merely unintended. `objectPosition: "70% 51%"` matches the measured subject centroid — it is a composition choice, and at 16/9 it is inert.

**Overlay is left-edge only** (`linear-gradient(to right, transparent 0%, #000 28%)`), landing inside the source's empty black band (x 0–35 %). **Bottom and right fades are forbidden** — the mark is 8–14 % from the bottom and 6–12 % from the right. Mobile is also 16/9, so nothing crops there either; a taller mobile block would be achieved by **re-authoring the poster**, not by cropping.

### Hydration: post-mount attachment

Three candidate mechanisms were tested. `useReducedMotion()` driving markup **mismatches** (framer-motion reads the preference during first render). `<source media="(prefers-reduced-motion: reduce)">` works in Chromium and genuinely suppresses the fetch — but MDN documents `media` as `<picture>`-only, and if a browser ignores it the video **autoplays for a reduced-motion user**: it fails *open*.

**Chosen: create the `<video>` in `useEffect` after idle.** The element is absent from both the SSR HTML and the first client render, so the trees are byte-identical and post-mount insertion is not a hydration event. It is the only option that is simultaneously mismatch-proof, fail-closed on accessibility, and browser-independent.

`<video>` is never attached when: reduced motion · viewport < 768 px · `Save-Data: on` · `sources` is empty. No source string is ever assigned, so **nothing is fetched at all**.

### Graceful degradation when the mp4 is absent

This is the CI/Vercel case and it must look intentional. The mechanism is the ordered `<source>` list plus the poster beneath: all candidates 404 → `networkState` settles at `NETWORK_NO_SOURCE` → `onPlaying` never fires → `opacity` stays `0` → **the poster remains the visible hero**. No error boundary, no layout change, no CLS. `sources: []` skips the `<video>` entirely.

### Poster: design it, don't extract it

`sharp` (already resolved in `node_modules` with librsvg + libwebp) rasterizes an authored SVG built from the existing `Monogram` geometry. Measured:

| | 1280×720 | 768×432 |
|---|---|---|
| **Designed SVG → WebP q80** | **6.6 KB** | **3.4 KB** |
| Extracted frame → WebP q80 | 18.4 KB | 10.1 KB |

**2.8× smaller** at a strong LCP candidate, and — decisively — the poster is *committed* while the video is not. An extracted frame would permanently commit Google-generated pixels, **including the burned-in mark**, into the repo as a production asset. The designed poster is original, licence-clean, and stays correct when the master is swapped. It also makes mobile art direction possible by authoring rather than cropping.

This is **not** a watermark-removal measure and the guide states so: the poster is an independently authored brand graphic, not an edited frame. The video plays byte-for-byte unmodified whenever it plays.

Rejected alternatives, recorded so they aren't re-litigated: `qlmanage -t` yields a **black frame** (t=0 measures 2.3/255); `sips` **cannot write** WebP; Playwright's bundled ffmpeg has no H.264 decoder and no mp4 demuxer.

### Loop defect

The prototype **does not loop** — t=0 is black, t=9.9 is lit. Short-term fix: `loopRange: [6.4, 9.9]` in `hero-media.ts`, a JS-clamped window over the settled range. Long-term: the production master must be *authored* to loop, first frame matching last.

### Git handling

`website/.gitignore` gains `/public/media/**/*.{mp4,webm,mov}`; repo root gains `/*.mp4` and `.playwright-mcp/`. Because the patterns are extension-scoped, **`public/media/quant-hero/README.md` is committable** — so the directory exists in a fresh clone. That matters: `public/fonts/` and `public/og/` both exist locally, are both empty, and neither is in git, leaving no trace for the next developer.

`VIDEO_ASSET_GUIDE.md` (`website/docs/`) documents: prototype status and measured facts · the watermark policy verbatim · rejected references · the production asset table with budgets · full ffmpeg commands for once ffmpeg is installed · poster export · loop authoring · the swap procedure. It also records the honest side-effect that **any transcode drops the C2PA `uuid` box**, since `libx264` does not carry ISOBMFF `uuid` boxes forward — a byproduct of re-encoding, not a provenance-stripping measure — so the untouched original must be retained locally.

**Required production assets**

| File | Res | Codec | Budget | Audio |
|---|---|---|---|---|
| `hero-desktop.mp4` | 1280×720 | H.264 High L4.0, faststart | ≤ 900 KB | none (`-an`) |
| `hero-desktop.webm` | 1280×720 | VP9 | ≤ 650 KB | none |
| `hero-mobile.mp4` | 768×432 | H.264 High L3.1 | ≤ 350 KB | none |
| `hero-poster.webp` | 1280×720 | WebP q80 | ≤ 8 KB | — |
| `hero-poster-mobile.webp` | 768×432 | WebP q80 | ≤ 4 KB | — |

The prototype's 1.99 MB is a **recorded, accepted 2.2× breach** for local prototyping only.

---

## 6. Design token plan

The palette is already correct; this is convergence on the brief's values plus removal of what nothing uses.

| Change | Detail |
|---|---|
| Align to brief | `--q-black #030303`, `--q-signal #FF7A1A`, `--q-success #22E58B`, `--q-danger #FF4D6D`, add `--q-paper #F4F2EC` for a single inverted band |
| `--space-content-max` | 1440 → **1280px**, and actually consumed |
| Vertical rhythm | one 201.6 px metronome → **3 steps** (`tight` / `default` / `major`) |
| Type scale | add `--text-caption 13px`, `--text-h3 20px` so the 11 ad-hoc sizes have token homes; 128 arbitrary sizes → 6 roles |
| Opacity | 23 inline levels → 4 semantic tokens; add `--color-text-quaternary: rgba(255,255,255,0.5)` as the legal floor |
| Wire `motion.css` | currently **zero** production consumers — connect the durations/eases to `Section`, `Surface`, `Reveal`, `button` |
| Delete | `--color-stabilized`, `--color-accent-dim`, `--color-accent-glow-strong`, `--blur-glass-sm`, `--z-scene`, `--z-scene-overlay`; unused keyframes `qf-shimmer`/`qf-fade-up`/`qf-float-c`/`qf-border-flow`; `.text-glow-orange` |
| Glass discipline | glass only for HUD/video overlay and the featured pricing tier; other cards become precise flat surfaces with hairline borders |

Contrast floor: **4.5:1 for all text, 3:1 for UI borders.** This is what fixes the 33 failing styles — footer copyright 1.43:1, pipeline captions 1.65:1, build SHA 1.71:1, locale toggle 2.53:1, nav links 3.71:1, arrow links 3.07:1.

---

## 7. Animation plan

Keep the architecture, reduce the surface, wire the tokens.

**Allowed:** hero video · hero entrance (**transform-only** — no `opacity`, so the poster stays LCP-eligible) · the existing pinned HowQuantWorks pan · card reveal via `Reveal` · active-card focus · signal-dot movement · magnetic CTA hover, desktop only.

**Removed:** the entire Three.js ambient scene · **`hero-signal-flow.tsx` is deleted outright** · the illustrative confidence trajectory animation goes with its deleted numbers.

The canvas deletion is not a stylistic call. Audit §26 found four separate defects baked into it as hardcoded English strings: its "CONFIDENCE" chart rises 50 %→80 % and **reads as an equity curve** (exactly what the brief forbids); its axis labels encode the **wrong** confidence bounds (20/80 vs the code's 0.05/0.95); it asserts **"Bayesian bounds"**, which `belief_updater.py` contradicts; and it shows **"EXECUTE — T-Invest · Bybit"**, implying unwired Bybit routing. All six stage labels also render in **English on the Russian page**. The `HeroVideo` replaces it, and the six pipeline stages are told properly — translated, and with real module names — in HowQuantWorks.

**Technical split held:** GSAP **only** for the pinned cinematic sequence · Framer Motion **only** for local UI transitions · CSS for hover/focus · Lenis **only** as scroll coordinator.

**Fixes:** migrate `ScrollTrigger.matchMedia` → `gsap.matchMedia()` · call `ScrollTrigger.refresh()` on hero video `loadedmetadata` (metadata load shifts layout after ScrollTrigger measures) · add `data-lenis-prevent` to the strategy table and dashboard tab row, or both horizontal-scroll fixes will still feel broken on a Mac trackpad · add a dev-only warning in `lenis-provider.tsx` when an anchor target is missing.

**Reduced motion:** no scroll-scrub, no magnetic movement, poster instead of video, all content complete. Replace the blunt global `animation-duration: 0.01ms !important` with targeted opt-outs so intended crossfades aren't collaterally killed.

---

## 8. Accessibility plan

| Item | Action |
|---|---|
| Contrast | Every text style to ≥4.5:1; borders ≥3:1. Service text opacity 0.15–0.28 → 0.45–0.55. |
| Focus | Delete `outline: "none"` at `faq-section.tsx:29`; restore the global `:focus-visible` ring; visible ring on the email input. |
| Labels | Email label becomes **visible**, not `sr-only`. |
| Target size | Nav links, locale toggle, footer links, arrow links to ≥24 px (WCAG 2.2 AA); slider handle 16 → 24 px. |
| Video | `aria-hidden` on wrapper *and* element; `tabIndex={-1}`; no `controls`; `disablePictureInPicture`; one `sr-only` description **outside** the hidden subtree (`hero.videoDescription`, both locales). |
| Audio | `muted` attribute **and** DOM property in the `ref` — React does not serialise `muted` to SSR HTML, and an unmuted video is autoplay-blocked. The file **does** carry an AAC stereo track; whether it is silent could not be verified, so the production encode must strip audio (`-an`). No captions: abstract particle motion, no speech. |
| Landmarks | `SiteHeader` moves **outside** `<main>` — a banner must not be a `main` descendant. |
| Mobile | Both content-loss bugs fixed (453 px table clip, unreachable SIGNALS tab). |

---

## 9. Performance plan

| Metric | Budget |
|---|---|
| LCP element | `h1#hero-heading` **or** `hero-poster.webp` — anything else fails |
| LCP | ≤ 1.2 s desktop; ≤ 1.8 s at 4× CPU throttle |
| CLS | ≤ 0.02 total; **hero contributes 0.000** |
| Posters | ≤ 8 KB / ≤ 4 KB |
| Video request start | **strictly after** the LCP entry |
| `/media/` bytes at 390×844 | ≤ 4 KB, **0** video requests |
| Video requests under reduced motion | **0** |

**Wins:** drop `three` + `@react-three/fiber` + `@react-three/drei` (~40 MB install, 10 dead files) and `lucide-react`; verify-then-drop `tw-animate-css`. Set `components.json` `iconLibrary` to `"none"` or the next `npx shadcn add` silently reinstalls what was just removed. Then `rm -rf node_modules package-lock.json && npm install` to prune the lockfile.

**Loading order:** poster is in the SSR HTML so the preload scanner finds it in the initial response, with `fetchPriority="high"` and `decoding="sync"`. **Exactly one** `fetchPriority="high"` on the page — the `priority` currently on the orphaned `hero.png` must go. Box reserved by `aspect-ratio` + `width`/`height` before any bytes arrive. No `<link rel=preload>` (redundant with an in-HTML `<img>`, and risks double-fetching the wrong art-direction variant). Video attaches on `requestIdleCallback(…, {timeout: 2000})` with a `setTimeout(200)` fallback for Safari.

**Cache:** add a `/media/:path*` → `public, max-age=31536000, immutable` header in `next.config.ts` (Vercel otherwise serves `/public` as `max-age=0, must-revalidate`). `immutable` makes the swap **filename-versioned**, which dovetails with "swappable by changing file paths only" — one string in `hero-media.ts`.

**Client bundle:** `layout.tsx:84` ships all 184 keys via `getMessages()`. After the FAQ server/client split, `dashboard.mock` is the only namespace still needed client-side. Narrow the provider **last**, building the allow-list from `grep -rn 'useTranslations(' src/` — getting it wrong yields a runtime `MISSING_MESSAGE` throw, not a build error.

---

## 10. Implementation order

Each phase ends green on `npx tsc --noEmit && npm run lint && npm run check:content && npm run check:i18n && npm run build`.

| Phase | Work |
|---|---|
| **3 — Media** | Playwright baseline capture (5 viewports, console, hydration) · media dirs + `.gitignore` · copy prototype to `hero-prototype.mp4` · author poster SVG → `sharp` → WebP · `VIDEO_ASSET_GUIDE.md` · `check-media.mjs` |
| **4 — Tokens** | token files (additive first) · new `ui/` primitives · `lib/strategy-status.ts` · `check-messages-parity.mjs` + `check-design-tokens.mjs` |
| **5 — Dedupe** | retire duplicated call sites, then delete `magnetic-button` / `panel` / `glass-panel` / `header-cta` / `hero-cta` / `explore-link` |
| **6a — Hero** | `hero-media.ts` + `HeroVideo` + hero rebuild; transform-only entrance |
| **6b — Renames** | `git mv` directories only, no content edits — keeps the diff reviewable |
| **6c — Sections** | rebuild bodies; fix the two clipping bugs and the focus bug |
| **6d — Rewire** | `page.tsx` order · delete the `globals.css` nth-child hack · both `messages/*.json` in one commit · MDX frontmatter · `strategies.json` |
| **6e — Cleanup** | delete scene + orphans; drop deps; prune lockfile |
| **7 — QA** | below |
| **8 — Report** | `REDESIGN_QA_REPORT.md` |

### Phase 7 QA

Typecheck · lint · build · `check:content` · `check:i18n` · `check:design` · `check:media`. Then Playwright: screenshots at 1920×1080 / 1440×1000 / 1024×768 / 390×844 / 320×700 on `/ru` **and** `/en` · LCP element identity via `PerformanceObserver` · CLS with shift sources · resource timing asserting the mp4 starts **after** the LCP entry · mobile reload asserting **zero** video requests · `emulateMedia({reducedMotion:'reduce'})` asserting zero video requests and no `<video>` in the DOM · console error baseline · keyboard-only pass over header → FAQ → form · **the absent-file test**: rename the mp4 away, rebuild, confirm the poster is LCP and CLS is unchanged. That last one also empirically confirms the 404-advances-to-next-`<source>` behaviour, which is currently spec-derived rather than measured.

---

## 11. Risks and trade-offs

| Risk | Mitigation |
|---|---|
| **Stale anchors fail silently.** 9 ids change; `lenis-provider` swallows a missed `querySelector`. Highest-probability undetected regression. | Dev-only warning + a `comm -23` diff of every `href="#…"` against every `id="…"` in CI. |
| **GSAP pin breaks invisibly.** An `overflow-hidden` ancestor kills pinning; `if (distance <= 0) return` disables the section with no error. | `Section` structurally forbids `overflow-hidden`; glow moves to a clipped child; pan track stays full-bleed with its own padding; visual check at 1280/1440/1920. |
| **Parity script passes vacuously** if `status` is renamed without editing the field list at `:104`. | Harden the script in Phase 4, before the JSON changes. |
| **MDX frontmatter drift is invisible** to the parity script. | `source.mdx.ts` throws on missing required frontmatter instead of yielding `undefined` cards. |
| **Analytics taxonomy breaks.** Every `journey_step.section` value changes; `scene_interaction` disappears. Funnels go blank with no error. | Decide explicitly: hard cut + documented in the QA report. |
| Hydration mismatch from `Intl.*` in client components | Keep formatting server-side; pass pre-formatted strings into client cards. |
| `suppressHydrationWarning` on `<html>` masks real mismatches | Remove during the refactor. |
| 1280px container reflows everything | `dashboard-mockup` is authored around 960px and pipeline cards are fixed `w-[340px]` — re-verify both at 1280/1440/1920. |
| `sharp` is an **optional** transitive dep of `next` | Poster generation is a one-off local step, not a build step. Guide says `npm i -D sharp` if it fails. |
| Empty Active + Candidate lanes may read as an unfinished page | Deliberate. Framed as discipline with explicit copy. Fallback available: legend-as-ladder with only the three real rows. |

### Two launch blockers this redesign does not itself resolve

1. **`src/lib/beta/adapter.ts` discards every signup.** Copy is being made honest (`accessForm.success` → «Заявка отправлена.», a statement about the send rather than a promise), but the follow-up promise in `accessForm.successDetail` and `finalCta.lead` is a **false statement** until a real `BETA_ADAPTER` destination is configured. Plan: gate `successDetail` on an env flag so it cannot ship un-wired. **This must be resolved before the site goes public** — it is the only conversion path.
2. **Watermark verification.** The mark's position is measured, and the 16/9 framing keeps it in frame. But per the brief, a watermarked asset must stay out of the final public build. The prototype is gitignored and the site renders poster-only without it, so a public deploy is currently watermark-free by construction. Shipping the video publicly requires a clean licensed master.

### Explicitly out of scope

No `bot/` changes. No new routes. No login/dashboard integration. Wiring the hero pill or footer status to real telemetry is **not** done — instead both are relabelled honestly, because wiring them would mean touching backend surfaces.
