import { cn } from "@/lib/utils";

/**
 * The blend between the page's black base and one of its two paper bands.
 *
 * ── The problem ──
 *
 * `tone="paper"` flips a section's tokens, which is the right mechanism, but it
 * flips them at a hard edge: #030303 meets #f4f2ec on one pixel row. Measured on
 * the live page that read as two sites stacked, and it was worst at the top of
 * `#foundation`, where the sticky header's black scrim also sat on the white and
 * showed as a grey smear across it.
 *
 * ── Why an in-flow band and not a gradient inside the section ──
 *
 * The first attempt was an absolutely-positioned gradient pinned inside the
 * paper section's own top padding. It works only as long as nothing grows: the
 * blend has to be shorter than `--space-section-y-major`, which is a clamp, so
 * the safe height is set by the *smallest* viewport (128px) while the widest one
 * has 232px of padding going unused. And the moment a heading wraps to a third
 * line on a narrow screen, dark-on-dark text.
 *
 * A real element in the flow cannot overlap anything and needs no per-breakpoint
 * arithmetic.
 *
 * ── What changed in this pass ──
 *
 * Three things, all aimed at the same complaint: the blend still read as an
 * abrupt cut with a grey smear in the middle of it.
 *
 *   1. **It is taller.** 160px at every viewport was not enough room for a
 *      220-luminance-level change, so the change happened in a visible ~60px
 *      horizon two-thirds of the way down and the rest of the band was flat
 *      grey. It went to 176/256px, and then — because that was still being read
 *      as an edge — to 208px on a phone and 352px from `lg`. The ramp has six
 *      stops instead of four, weighted so no two adjacent stops are more than
 *      about 60 levels apart.
 *
 *      A fourth thing was added later, and it is the one that finally settled
 *      the complaint: **the crossing happens as the reader scrolls**, via a
 *      second copy of the ramp that fades out on a view timeline. A gradient of
 *      any height is still a static image the reader pans across; the held ramp
 *      makes the paper front actually advance. See `held` below.
 *
 *   2. **The grid crosses it.** The same 64px geometry as the hero backplate,
 *      in white over the dark end and in graphite over the paper end, each
 *      masked to its own half and overlapping through the middle. That is what
 *      makes the band read as one material changing state rather than as a
 *      gradient someone inserted between two sections — there is a structure
 *      running through it that belongs to both sides.
 *
 *   3. **The section that follows gives up its top padding**, via an
 *      adjacent-sibling rule in globals.css. The blend was previously followed
 *      by up to 232px of empty paper before the heading, so the reader crossed a
 *      careful transition and then arrived nowhere.
 *
 * The route line that used to run down the middle of the blend is gone, with the
 * rest of the connector family. See the note above `.band-blend` in globals.css.
 */

interface BandTransitionProps {
  /**
   * Which way the blend runs.
   *
   * `into-paper` — black at the top, paper at the bottom. Place it immediately
   *                *before* a `tone="paper"` section.
   * `into-dark`  — paper at the top, black at the bottom. Place it immediately
   *                *after* one.
   *
   * Getting this backwards produces a visible band of the wrong colour rather
   * than a subtle error, which is deliberate: it fails loudly.
   */
  direction: "into-paper" | "into-dark";
  className?: string;
}

/** The grid, as one declaration, so the two tinted copies cannot drift apart. */
const GRID_LINES =
  "repeating-linear-gradient(to right, currentColor 0 1px, transparent 1px 64px), " +
  "repeating-linear-gradient(to bottom, currentColor 0 1px, transparent 1px 64px)";

/**
 * Every grid layer is masked twice and the masks are intersected: once
 * vertically, to keep each tint on the half of the ramp it is legible against,
 * and once horizontally, so the lines dissolve before they reach the viewport
 * edge. Without the horizontal fade the grid ends in a hard vertical cut at the
 * screen edge and reads as a texture that was pasted in.
 */
const EDGE_FADE = "linear-gradient(to right, transparent 0%, #000 18%, #000 82%, transparent 100%)";

export function BandTransition({ direction, className }: BandTransitionProps) {
  const intoPaper = direction === "into-paper";

  /*
    Six stops, and the middle two are the ones that matter.

    The first version was `bg → panel-raised → paper`. On paper that measured as
    a hard horizon rather than a blend, and the reason is the token values:
    --color-bg is #030303 and --color-panel-raised is #171717. Both are
    near-black, so a stop at 55% spent the whole first half of the band going
    from black to *slightly less black* and then crossed 220 luminance levels in
    the remaining 45%.

    Two genuine mid-tones — a 22% and a 55% mix of paper into the graphite —
    spread that crossing across the second half of the band instead of
    concentrating it in one horizon. `color-mix` keeps them derived from the two
    tokens rather than hard-coding greys that would need maintaining if either
    end of the palette moved.
  */
  const BLACK = "var(--color-bg)";
  const GRAPHITE = "var(--color-panel-raised)";
  const MIX = (paper: number) =>
    `color-mix(in srgb, var(--color-paper) ${paper}%, var(--color-panel-raised))`;
  const PAPER = "var(--color-paper)";

  /*
    The dark half is deliberately steeper than the light half. Perceived
    lightness is not linear in sRGB: the first two stops cover ~20 luminance
    levels and read as one tone, so they are given only a quarter of the band,
    and the three stops that actually cross the gap get the rest.
  */
  const ramp = intoPaper
    ? `linear-gradient(to bottom, ${BLACK} 0%, ${GRAPHITE} 26%, ${MIX(22)} 46%, ${MIX(55)} 64%, ${MIX(85)} 82%, ${PAPER} 100%)`
    : `linear-gradient(to bottom, ${PAPER} 0%, ${MIX(85)} 18%, ${MIX(55)} 36%, ${MIX(22)} 54%, ${GRAPHITE} 74%, ${BLACK} 100%)`;

  /*
    ── The held ramp: the same change, later ──

    A second copy of the ramp with *identical endpoints* and a crossover pushed
    most of the way toward the paper end. It sits on top of the ramp above and
    fades out as the blend crosses the viewport, so the paper front visibly
    advances through the band while the reader scrolls rather than being a fixed
    gradient they pan past. That is the "resolves as you scroll" the brief asks
    for, and it is the part a static gradient cannot do at any height.

    Endpoints being identical is the load-bearing constraint, not a detail. This
    layer's top row must equal the neighbouring section's colour and its bottom
    row must equal the other neighbour's, at every opacity — otherwise the
    element it is trying to blend away from reappears as a seam at one edge for
    the whole first half of the animation. Only the middle may move.

    Base opacity is 0, so every failure mode — no view-timeline support, reduced
    motion, a timeline that never resolves — lands on the finished ramp rather
    than on a band stuck dark. Same rule as the grid layers below it.
  */
  const held = intoPaper
    ? `linear-gradient(to bottom, ${BLACK} 0%, ${BLACK} 44%, ${GRAPHITE} 68%, ${MIX(22)} 84%, ${MIX(62)} 94%, ${PAPER} 100%)`
    : `linear-gradient(to bottom, ${PAPER} 0%, ${MIX(62)} 6%, ${MIX(22)} 16%, ${GRAPHITE} 32%, ${BLACK} 56%, ${BLACK} 100%)`;

  /**
   * The two tints, on the existing hairline tokens rather than fresh alphas:
   * `--color-border` is the white hairline the hero grid already uses, and
   * `--color-line-light` is its declared counterpart for use on paper.
   *
   * Whichever end of the ramp is dark gets the white grid; whichever end is
   * paper gets the graphite one. They overlap through the middle third, which is
   * where the ground itself is ambiguous and neither tint alone would carry.
   */
  /*
    Each layer fades out at *both* ends, not just at the one where the other
    tint takes over. The first version ran the outer end all the way to the
    band's edge, and because the section on that side has no grid of its own the
    lines terminated in a hard horizontal cut — 1px stubs stopping dead in the
    black, which is precisely the "accidental line" artefact this pass exists to
    remove. Fading both ends makes the grid materialise inside the blend and
    dissolve before it reaches either neighbour, so it belongs to the transition
    rather than leaking out of it.
  */
  const UPPER = "linear-gradient(to bottom, transparent 0%, #000 24%, #000 42%, transparent 68%)";
  const LOWER = "linear-gradient(to bottom, transparent 32%, #000 58%, #000 78%, transparent 100%)";

  const layers = [
    {
      // White hairlines, masked to whichever half of the band is dark.
      key: "on-dark",
      colour: "var(--color-border)",
      fade: intoPaper ? UPPER : LOWER,
    },
    {
      // Graphite hairlines, masked to whichever half is paper.
      key: "on-paper",
      colour: "var(--color-line-light)",
      fade: intoPaper ? LOWER : UPPER,
    },
  ];

  return (
    <div
      aria-hidden="true"
      className={cn(
        /*
          Fixed heights rather than a clamp on the section rhythm: the blend is a
          material change, and a material change wants the same amount of room to
          happen in at any width. Fixed also means it can never become the
          tallest thing on a small screen.

          `overflow-hidden` so the grid layers cannot contribute to document
          width — this element spans the full viewport, outside any section's
          horizontal padding, and the no-horizontal-scroll guarantee is absolute.
        */
        /*
          Taller than it was — 176/224/256 became 208/288/352. A 220-level
          luminance change needs room, and at 256px the crossing was still
          happening fast enough to read as a horizon two-thirds of the way down
          rather than as a material changing. 352px at `lg` is about a fifth of
          a 1440×900 viewport, which is the point where the eye stops being able
          to see both ends of the ramp at once and therefore stops reading it as
          an edge at all.
        */
        "band-blend relative isolate h-52 w-full overflow-hidden sm:h-72 lg:h-88",
        className,
      )}
      style={{ backgroundImage: ramp }}
    >
      {/* The held ramp. First child, so it sits under the grid layers — the grid
          belongs to the blend as a whole and should not fade with the ground. */}
      <div
        className="band-blend__hold pointer-events-none absolute inset-0"
        style={{ backgroundImage: held }}
      />

      {layers.map((layer) => (
        <div
          key={layer.key}
          className="band-blend__grid pointer-events-none absolute inset-0"
          style={{
            color: layer.colour,
            backgroundImage: GRID_LINES,
            maskImage: `${layer.fade}, ${EDGE_FADE}`,
            maskComposite: "intersect",
            WebkitMaskImage: `${layer.fade}, ${EDGE_FADE}`,
            WebkitMaskComposite: "source-in",
          }}
        />
      ))}
    </div>
  );
}
