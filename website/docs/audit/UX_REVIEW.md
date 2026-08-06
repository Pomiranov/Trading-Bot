# UX_REVIEW.md

**Scope:** `website/` homepage, section-by-section, evaluated against Apple's design philosophy (simplicity, clarity, hierarchy, spacing, typography, focus, visual rhythm, consistency).

## Headline finding

This codebase already runs its own internal "brand lock" discipline — comments throughout reference a "taste-skill" and "impeccable" rule set (`footer.tsx:5`, `typography.css`, `color.css`) that independently arrives at very Apple-adjacent constraints: one accent color capped at ~3% of pixels, a hero type-size ceiling added specifically because the original spec "read as an AI 'shouting' tell," a WCAG-driven correction to secondary text opacity, a documented rejection of a v2 logomark that misread as a "prohibited" sign. This is uncommon rigor for a project at this stage. The UX review below is mostly about **finishing what this system already commits to**, not correcting its direction.

## Section-by-section

### Hero
- **Hierarchy:** status line (mono, tertiary, smallest) → tagline (largest, serif accent on line 2) → subline (secondary, mid-size) → 3D scene. Textbook Apple ordering: context, statement, explanation.
- **Friction:** the 3D belief-network scene occupies equal visual weight to the headline block on desktop (`md:justify-between`, both roughly half-width). On a first visit, attention likely splits between reading and watching the scene animate, delaying comprehension of the one sentence that matters. This is a legitimate design choice (it's literally showing the product's core mechanism — "rule confidence, live") but should be validated with real scroll/attention data (PostHog's `scroll_depth` + `scene_interaction` events already capture the data needed — pull this once there's traffic, see `CRO_REPORT.md` §5).
- **Consistency:** no shared primitive (`Panel`, `SectionHeading`) is used here — by design, per the comment in `section-heading.tsx` ("Not for the hero — that owns its own `--text-hero` scale"). Reasonable exception, well-documented.

### Philosophy
- This is the best-executed section on the page. The explicit rejection of a 3-card grid in favor of an escalating single column (weight increases block-to-block, per code comment) is a genuinely Apple-grade move — it uses typography, not boxes, to create rhythm. Three short paragraphs, hairline dividers, no filler.
- **No issue found.** This is the reference section for the rest of the site to match.

### Engine Pipeline
- **Complexity vs. payoff:** this is the single most engineering-heavy section (GSAP `ScrollTrigger` pin + horizontal scrub on desktop, plain vertical list on mobile) for what is, informationally, a 7-step list. The scroll-jacking (pinning the viewport, taking over scroll direction) is a real UX risk: it removes the user's default scroll behavior for the duration of the section. It's implemented carefully (media-query gated, `useReducedMotion` respected, mobile gets a plain list) — but it's still the section most likely to frustrate a user who just wants to keep scrolling down.
- **Recommendation:** keep it, but confirm (via the `scroll_depth` funnel) that completion rate through this section isn't meaningfully lower than the sections before/after it. If it is, the fallback (plain vertical list) should become the default, not just the reduced-motion/mobile path.

### Learning System
- The interactive confidence slider is a strong "show, don't tell" moment — it's the one place a visitor can *do* something with the product's core mechanism before signing up. Good use of both pointer and full keyboard support.
- **One clarity gap:** the underlying data is explicitly a "plausible reconstruction, not a query result" (`confidence-data.ts:1-9` comment) — real aggregate stats, fabricated per-trade path. This is disclosed in code comments but the on-page caption only says "illustrative confidence path" (`sections.confidenceChartCaption`). "Illustrative" is doing a lot of work for "we made up the shape of this line but not the summary stats." For a product whose entire pitch is "we don't fabricate," this line should be unambiguous, not softened.

| Issue | Business impact | User impact | Solution | Benefit | Priority |
|---|---|---|---|---|---|
| "Illustrative" caption undersells that the per-trade path is fabricated while real stats are used | A sophisticated visitor who notices the mismatch (the target audience explicitly optimizes for this kind of scrutiny) may distrust the whole page, not just this chart | Minor deception-adjacent ambiguity in the one product whose selling point is not doing that | Make the caption explicit: "Illustrative path (shape only) over a real 29-trade forward-test (win rate 58.6%, PF 1.16)" or similar | Removes the one spot where the site's own "we don't fabricate" standard is softer than everywhere else | High |

### Dashboard Preview
- Correctly labeled as illustrative, with its own disclosure caption already on-page. The deliberate choice to keep the *real* dashboard's own color palette (`dashboard-colors.ts`) rather than reskin it in the marketing site's Signal Amber is the right call — it signals "this is what the real tool looks like," not "this is what the marketing team thinks the tool should look like."
- **No issue found.**

### Strategy Table
- Showing a frozen, underwater strategy (`wrd_moex`, PF 0.65, drawdown -936,000) next to the live one is the strongest trust-building move on the entire page, and it's uncommon in this industry. Keep it exactly as is; do not let a future "make it look better" pass remove the losing row.
- **No issue found** beyond the general horizontal-scroll-on-mobile pattern (`min-w-[760px]` inside `overflow-x-auto`), which is a reasonable, standard solution for tabular data that doesn't compress further.

### CTA / Footer
- See `MARKETING_AUDIT.md` §2–3 and `CRO_REPORT.md` §1 for the conversion-specific findings (single CTA, dead footer links). From a pure UX-consistency standpoint: the footer is the only place on the page using `<a href="#">` placeholders, which breaks the "every interactive element does something" rule the rest of the page follows (the confidence slider, the pipeline scroller, the hero scene are all fully functional).

## Spacing, Typography, Rhythm

- `--space-section-y: clamp(96px, 14vw, 240px)` gives generous, consistent breathing room between all 8 sections — this alone accounts for a large share of why the page feels calm rather than cluttered. No changes needed.
- Type scale is disciplined: one label size, one body, one lead, one hero (clamped, with an explicit note about *lowering* the original spec because it read as artificial), one section-heading size. No ad-hoc font sizes found outside these tokens in the sections reviewed.
- Serif italic (`Cormorant Garamond`) is reserved for exactly two uses (hero tagline2, philosophy pull-quote accents) per the typography token comment ("ONE accent use only... never mix families for in-line emphasis") — verified in the sections read; no violations found.
- `MonoLabel` eyebrow usage is explicitly rationed ("max 1 per 3 sections" per its own comment) — this is a real anti-pattern many marketing sites fall into (an eyebrow label above every single section heading) that this codebase has pre-emptively guarded against.

## Accessibility

- Focus rings are handled globally (`globals.css:47-50`, `:focus-visible` with a 3px offset accent outline) rather than per-component — consistent by construction.
- `StatusPill` explicitly never conveys status by color alone (component comment: "the label text itself always states the status") — correct, verified pattern.
- Reduced motion is handled in every animated component reviewed (hero scene, pipeline scroller, confidence slider all branch on `useReducedMotion`/`prefers-reduced-motion`) — better coverage than most sites this animation-heavy achieve.
- **Gap:** no visible focus-order/skip-link was found for keyboard users who want to bypass the pinned, scroll-jacked Engine Pipeline section specifically — reduced-motion users get the plain list (which is fine), but a keyboard user with motion *enabled* who tabs through the page has no way to skip the pin. Low-severity given the section resolves on its own scroll distance, but worth a note.

| Issue | Business impact | User impact | Solution | Benefit | Priority |
|---|---|---|---|---|---|
| No skip mechanism past the pinned Engine Pipeline section for keyboard users with motion enabled | Minor — affects a narrow slice of users (keyboard nav + motion enabled) | Slight friction navigating past a section that temporarily changes scroll behavior | Optional: add a visually-hidden "skip pipeline" anchor link before the section | Marginal accessibility completeness | Low |

## Priority Summary

- **High:** make the confidence-chart disclosure unambiguous (illustrative shape vs. real stats).
- **Low:** optional skip-link past the pinned pipeline section.
- Everything else in this document is either already correct (Philosophy, Dashboard Preview, Strategy Table, spacing/type system, most of accessibility) or overlaps with `MARKETING_AUDIT.md`/`CRO_REPORT.md` findings, cross-referenced above rather than duplicated.
