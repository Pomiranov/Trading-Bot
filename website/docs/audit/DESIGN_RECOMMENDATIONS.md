# DESIGN_RECOMMENDATIONS.md

**Scope:** concrete, token-level and component-level recommendations. Grounded in the actual values in `src/styles/tokens/*.css` and the actual components in `src/components/ui/`, `src/components/sections/` — not generic design advice.

## Principle for this document

The existing token system already encodes an unusually specific set of constraints (see quotes below). Recommendations here either (a) close a gap where the system's own rules aren't yet fully applied, or (b) add a new, small primitive that follows the existing rules rather than introducing a new pattern. Nothing here proposes changing the color, type, or motion tokens themselves — they're well-reasoned as-is.

## 1. Color — no changes recommended

`color.css`: single accent (`--color-accent: #e8a33d`, "Signal Amber"), capped under ~3% of pixels by design intent, with `--color-danger` as the one documented functional exception ("form/error states only, never decorative"). The tertiary-text opacity (`0.48`, not a more "designed-looking" `0.35`) was already corrected once for a real WCAG AA failure (2.97:1 → needed 3:1) — this is evidence of prior real accessibility auditing, not guesswork. **No further changes.** Any new component (see §4 below) must draw only from these existing tokens — no new colors.

## 2. Typography — one small gap

Type scale (`typography.css`): `--text-label` (11px), `--text-body` (16px), `--text-lead` (18px), `--text-hero` (clamped 2.5rem–6rem), `--text-section-heading` (clamped 1.75rem–3rem). Consistently applied across every section reviewed.

**Gap:** there is no token for a *nav-scale* label — the smallest existing size (`--text-label`, 11px/uppercase/wide-tracking) is designed for eyebrow labels above section headings, not for a persistent UI chrome element like a header link. Reusing `--text-label` for a new header (see §4) is directionally correct (don't invent a new size for one component) but confirm at implementation time that 11px uppercase reads comfortably as a tappable nav link at arm's length on mobile — if not, `--text-body` at a reduced opacity is the next-closest existing token, still no new value needed.

## 3. Spacing, Motion, Z-index — no changes recommended, one unused token to finally use

- `--space-section-y` (clamp 96–240px) and `--space-page-x` (clamp 24–120px) are applied consistently across all 8 homepage sections. No drift found.
- `motion.css`'s `--ease-out-expo`/`--ease-out-quart` are used consistently in the animated components read (`Reveal`, `magnetic-button.tsx`'s spring config uses Motion's own spring physics rather than these eases, which is correct — springs and eased curves are different tools and shouldn't share a token).
- `z-index.css` defines `--z-nav: 40` — **currently unused anywhere in the codebase.** This is the clearest signal in the whole token system that a header/nav component was planned and never built. Recommendation: use it exactly as reserved, for exactly one thing (a header), rather than reaching for an arbitrary `z-50` when that header gets built.

## 4. New primitive: a minimal site header

This is the one new component recommended across all five audit documents (cross-ref `MARKETING_AUDIT.md` §2, `CRO_REPORT.md` §1, `BRAND_POSITIONING.md` §5). Design constraints for it, derived entirely from existing patterns in this codebase rather than external convention:

- **Structure:** mirror the Footer's own restraint — `Monogram` + wordmark on one side, a single link/button on the other. Do not add a multi-item nav menu; there is nothing to navigate to except the four sections the footer already (will) link to, and duplicating that in a header adds chrome without adding function.
- **Style:** thin bar, `--z-nav` (already reserved), mono uppercase text matching the footer's `font-mono text-[13px]` treatment, a hairline `border-b` in `--color-border` — visually it should read as an extension of the footer's chrome, not a new visual language.
- **Behavior:** `position: fixed`, transparent/backdrop-blur background so it doesn't compete with the Hero's full-bleed layout — it should feel like a label on the page, not a bar sitting on top of it. This matches how the Hero's own status line already behaves (small, mono, tertiary-colored, unobtrusive).
- **Primary action:** reuse `MagneticButton` (already built, already used once in `BetaForm`) for the "Request Private Access" link so the header's one interactive element feels like part of the same system as the form it points to, not a new button style.
- **Secondary action (locale):** a same-restraint `EN / RU` toggle using the existing `Link`/`usePathname` from `src/lib/i18n/navigation.ts` — this closes a real gap (bilingual content with no way to switch locale from the UI) without adding a new interaction pattern (it's just two text links, styled like the footer's nav links).
- **What NOT to add:** no hamburger menu, no dropdown, no logo animation on scroll, no hide-on-scroll-down/show-on-scroll-up behavior. Every one of those is a common pattern on Path B sites (see `BRAND_POSITIONING.md`) and each would add a decision/animation this page's own restraint doesn't currently spend anywhere else.

## 5. Component-level notes

- **`Panel`** (`panel.tsx`) is defined but used in zero of the 8 homepage sections — the Dashboard Preview mockup hand-builds its own card instead. This isn't necessarily wrong (the component's own comment says "use only when elevation communicates real hierarchy," and the mockup may have needed bespoke chrome to match the real dashboard's own colors, per `dashboard-colors.ts`) — but it's worth confirming at the next section-design pass whether `Panel` should be the mockup's outer wrapper even if its internals stay bespoke, purely for consistency's sake.
- **`StatNumber`**: comment notes count-up-on-scroll motion is "wired in Phase 4" — i.e., already planned, not a new recommendation. No action needed now; flagging only so it isn't rediscovered as a "bug" later.
- **`MagneticButton`**: currently used in exactly one place (`BetaForm`'s submit button). The new header CTA (§4) becomes its second use — good, this is exactly the kind of primitive that should have 2+ call sites before anyone considers whether it needs new props/variants.

## Priority Summary

- **High:** ship the header primitive described in §4 — it's the only concrete new UI surface recommended in this entire audit, and three other documents independently converge on needing it.
- **Low/no-action:** color, spacing, motion tokens — already disciplined, don't touch.
