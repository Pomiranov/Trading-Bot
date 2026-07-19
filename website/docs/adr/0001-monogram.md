# ADR 0001: Monogram concept

**Status:** first pass, Phase 0 (revised once within Phase 0 after a visual
check — see "Revision" below). Final polish (favicon/app-icon set, OG
embedding) happens in Phase 6.

## Decision

The mark is not a literal "QF" wordmark. It is a single geometric form
built from the belief-network visual language used in the hero 3D scene —
an open ring, reading intentionally as an instrument dial/gauge:

- The ring **never fully closes** — echoes confidence bounded
  [0.05, 0.95] rather than [0, 1]. The system never claims certainty.
- One terminus is a **solid node** (frozen — the fixed, proven rule).
- The other terminus **uncoils into a short trailing line**, tangent to
  the ring's own curvature (fluid — trust that keeps moving, never fully
  resolves).

Pure stroke linework, single weight (9/100 of the viewBox), one color via
`currentColor` — no separate light/dark variant needed. Source component:
`src/components/ui/monogram.tsx`.

## Revision (still Phase 0)

The first version replaced the trailing line with a straight diagonal
crossing the full ring diameter (frozen anchor point *inside* the ring,
fluid end exiting through the gap). Rendered at icon scale, it read
immediately as a "prohibited / not allowed" sign (circle-slash), which is
actively bad for a trading product. Caught via a screenshot check before
moving on — see `frontend-design` skill's self-critique guidance. Replaced
the diameter-crossing line with a tangent-only trail plus a separate anchor
node, both living at the ring's own two termini instead of cutting across
the interior. Same frozen/fluid duality, no "no" sign risk.

## Why not the alternatives

- Literal "QF" letterforms — reads as a generic corporate lockup, doesn't
  connect to the product's actual mechanism.
- A graph/node icon — too literal, closer to the banned "obvious chart"
  direction from the brief.
- An arrow or coin motif — explicitly excluded (crypto/growth-hack
  association the brand is trying to repel).

## Legibility constraint

Designed at 100×100 and tested down to 16px (favicon). Stroke width is
proportionally chunky (8%) specifically so the ring and the crossing line
both survive at favicon scale without becoming a gray blob — thin
single-pixel-equivalent strokes were rejected during this pass for that
reason.

## Open follow-ups (Phase 6)

- Render a light-background variant check (black-on-white) for contexts
  that can't use the dark surface.
- Generate the full favicon/app-icon size set (16/32/48/180/512) and an
  OG-image embedding.
