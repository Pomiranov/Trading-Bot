# MARKETING_AUDIT.md

**Scope:** `website/` — the QuantFlow marketing site (Next.js, `en`/`ru`, single page at `/{locale}`).
**Method:** direct code/content read (no assumptions from the product roadmap) — see companion docs for detail. Every finding below is anchored to an actual file.

## 0. The one fact that reframes everything else

The site is not a mass-market SaaS landing page. It is a single-page, invite-gated manifesto: nav copy is "Request Private Access" (`messages/en.json:8`), the email placeholder is `you@fund.com`, there is no pricing, no self-serve signup, no public dashboard — only a `console.log` behind the one form (`src/lib/beta/adapter.ts`). The audit brief that triggered this review assumes a subscription consumer product (pricing page, checkout, Telegram bot showcase, testimonials). **That product doesn't exist on this site yet, and shouldn't be faked into existence.** This document audits the site QuantFlow actually is — an exclusive-access research/quant tool — and treats "should we build the mass-market layer" as a strategy question, not a code fix. See `BRAND_POSITIONING.md` §1 for that question.

Everything below assumes the current positioning (private, exclusive, institutional) is correct and asks: does the site execute that positioning well, and where are the plain execution gaps (dead links, missing SEO, unhandled errors) that undercut it regardless of strategy?

## 1. First Impression

- **Professionalism:** high. The single-accent-color system (`#e8a33d` "Signal Amber" on `#0a0a0b`), restrained mono/serif type pairing, and the "honest data" discipline (strategy table shows a *frozen, losing* strategy right next to the live one — `strategies.json`, `wrd_moex` PF 0.65) read as unusually credible for a trading product. Most competitors in this space oversell backtests; this one deliberately doesn't.
- **5-second value prop:** partially clear. "Knowledge is frozen. Trust is fluid." is a strong, quotable line but it's a metaphor, not a claim — a first-time visitor gets *mood* before they get *what this does*. The subline ("tracks which proven rules are actually working, and sizes conviction accordingly") does the explaining, but it's the 4th thing on the page (status pill → tagline → tagline → subline), competing with a 3D scene for attention share.
- **Would a professional trader trust it?** Yes — the strategy table's willingness to show a losing, frozen strategy (`trend_moex`, `wrd_moex`) is exactly the kind of transparency that reads as credible to a sophisticated audience.
- **Would a beginner understand it?** No. Terms like "belief gate", "OOS metrics", "confidence floor/ceiling" are used with no glossary or plain-language fallback. That's fine *if* beginners are explicitly out of scope (see §0) — but the product brief claims both audiences. Pick one for this page; a beginner-friendly explainer layer, if wanted, should be a separate `/learn` surface, not a dilution of this one.
- **Premium feel:** yes, and it's the site's biggest asset — don't spend it on generic SaaS patterns (see `BRAND_POSITIONING.md`).

| Issue | Business impact | User impact | Solution | Benefit | Priority |
|---|---|---|---|---|---|
| Value prop is implied, not stated, until the 3rd line of copy | Visitors who don't self-select as sophisticated traders bounce before the subline explains anything | Confusion in the first 2 seconds for anyone outside the target niche | Keep the tagline, but let the status line (`LIVE · MOEX D1 · ...`) do more work, or move the subline weight up visually (already secondary color/size — consider equal size to tagline2 on mobile where vertical space is cheaper) | Faster comprehension without diluting the manifesto tone | Medium |

## 2. User Journey (as it exists in code)

`page.tsx:19-29`: Hero → Philosophy → Engine Pipeline → Learning System → Dashboard Preview → Strategy Table → CTA → Footer. One linear scroll, no navigation, no way to jump ahead or skip back except native scroll/find-in-page.

Mapped to the brief's intended funnel:

```
Lands on homepage        → OK (Hero)
Learns what QuantFlow is → OK (Philosophy, 3 short blocks)
Builds trust             → OK (Engine Pipeline: literal source-code refs per stage)
Explores features        → OK (Learning System: real interactive confidence slider)
Understands benefits     → Weak — benefits are implied by the engineering, never stated as "why this matters to you"
Sees proof                → OK, unusually honest (Strategy Table shows real + frozen strategies)
Registers                → The ONLY conversion action on the entire page, and it's the very last section
Starts using the platform → Doesn't exist yet — no login, no app; the ask is "email us"
Purchases subscription   → Doesn't exist — no pricing anywhere
```

**Primary friction point:** there is exactly one place to convert (`CtaSection`, bottom of a long, animation-heavy scroll), and no persistent way to reach it. A visitor convinced by the Hero has to scroll past 6 more sections — including a pinned, scroll-jacked horizontal section (`EnginePipelineScroller`) — to act on that conviction. See `CRO_REPORT.md` §1 for the fix.

| Issue | Business impact | User impact | Solution | Benefit | Priority |
|---|---|---|---|---|---|
| Single CTA, bottom-of-page only, no persistent nav | Visitors who decide early have no low-friction way to act; every conversion depends on full-page patience | High-intent early visitors must scroll through 3D scenes and a pinned animation to find the form | Add a minimal persistent header exposing the existing (already-translated, currently unused) `nav.requestAccess` string, linking to `#cta-heading` | Captures high-intent visitors without adding a heavy nav, preserves the manifesto pacing for everyone else | Critical |

## 3. Missing Marketing Infrastructure (execution gaps, not strategy gaps)

These are absent from the codebase outright — confirmed by search, not inference:

- **No `robots.txt` / `sitemap.xml`** — nothing in `public/` or `src/app/` generates either. Search engines have no explicit crawl guidance or discovery map.
- **No Open Graph / Twitter Card metadata** — `generateMetadata` (`layout.tsx:21-39`) sets only `title`/`description`/`alternates.languages`. Any link shared to Slack, Twitter/X, LinkedIn, or Telegram renders with no image and a generic card. `public/og/` exists as a directory but is **empty** — the asset was planned, never produced.
- **No legal pages** — no privacy policy, terms, or risk disclosure exist anywhere. For a financial product collecting emails and (eventually) handling live trading, this is a real compliance gap, not just a trust one. This should not be code-generated (legal text needs actual legal review) but it needs to be on the roadmap before any real signups scale up.
- **Footer nav is fully dead** — all four footer links (`Manifesto`, `System`, `Research`, `Contact`, `footer.tsx:14-17`) point to `href="#"`. A visitor who scrolls to the footer looking for more (exactly the "explores features" journey step) hits four no-ops.
- **`nav.requestAccess` translated in both locales, rendered nowhere** — `messages/en.json:8` / `messages/ru.json:8` define it; no component references it (confirmed by search). This is copy for a nav bar that was written but never built.

| Issue | Business impact | User impact | Solution | Benefit | Priority |
|---|---|---|---|---|---|
| No sitemap/robots | Weaker organic discoverability from day one; no control over crawl budget as content grows (mdx content already exists per-locale) | None directly, but indirectly fewer people ever reach the site | Add `src/app/robots.ts` and `src/app/sitemap.ts` (Next 15 metadata routes) | Baseline SEO hygiene, near-zero cost | High |
| No OG/Twitter metadata, empty `public/og/` | Every shared link (the natural distribution channel for an invite-only product — "here, look at this") looks unfinished | Lower click-through from shared links, weaker perceived legitimacy | Wire textual OG/Twitter metadata now (title/description/locale); commission an actual OG image asset separately (design task, not a code fix) | Immediate improvement to link-sharing credibility | High |
| Footer links are dead (`href="#"` ×4) | Reads as an unfinished/abandoned site to anyone who scrolls that far — directly contradicts the "institutional-grade engineering" goal | Broken expectation — clicking does nothing, no feedback | Point each link at its real in-page destination (all four sections already have stable ids: `#philosophy-heading`, `#engine-pipeline-heading`, `#strategy-layer-heading`, `#cta-heading`) | Removes the single most obvious "unfinished" signal on the page | Critical |
| No privacy/terms/risk-disclosure | Real regulatory/compliance exposure once signups or live trading scale; erodes trust for a financial product specifically | Sophisticated visitors (the target audience) actively look for this and its absence is a red flag, not a neutral | Commission real legal copy; add footer links once it exists — do not placeholder with fabricated text | Removes a credibility red flag specific to fintech | Critical (content owner: legal, not engineering) |

## 4. Copy Audit

The existing copy is already close to the brief's own standard ("write like Apple: simple, confident, precise, benefit-focused") — it avoids buzzwords almost entirely and every claim is falsifiable (source refs down to the function name: `RulesEngine.evaluate()`, `content/en/engine-pipeline/03-rules-engine.mdx`). The real copy gaps are structural, not tonal:

| Issue | Business impact | User impact | Solution | Benefit | Priority |
|---|---|---|---|---|---|
| "Request access" (button) and "Enter a valid email address" (error) are reused verbatim for a network/server failure (`beta-form.tsx:96-105`, both branches render the same `errorMessage` string) | Support burden — users told to "fix their email" retry the exact same input and fail again silently | Actively misleading: a valid email that failed because the server errored gets told the email is invalid | Add a distinct network/server-error string ("Something went wrong. Try again shortly.") and branch on it | Removes a real dead-end in the only conversion flow on the site | High |
| No contact channel other than the beta form | A visitor with a question (partnership, press, security disclosure) has no path — "Contact" in the footer is dead (`href="#"`) | Frustration for exactly the high-value, low-volume inbound (journalists, funds, security researchers) that this positioning should attract | Point "Contact" at the beta form (`#cta-heading`) until a real inbox/alias exists — the form is the only real intake mechanism today | Honest stopgap; no fabricated contact info | High |

## Priority Summary

- **Critical:** persistent CTA access point, dead footer links, legal/compliance pages (content, not code).
- **High:** robots/sitemap, OG metadata, error-message clarity, contact path.
- **Medium:** value-prop legibility in first viewport.
