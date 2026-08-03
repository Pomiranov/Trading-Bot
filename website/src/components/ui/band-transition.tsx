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
    ── Nine stops, mixed in oklab, placed on a smoothstep ──

    This is the change that actually settled the "переход слишком резкий"
    complaint, and it is two independent fixes that had to land together.

    **1. The interpolation space.** Every mid-tone used to be
    `color-mix(in srgb, …)`. sRGB is not perceptually uniform anywhere, and it
    is worst exactly here — mixing a near-black with a near-white in gamma space
    puts the perceptual midpoint at about 22% of the mix fraction, so a stop
    written as "55% paper" rendered far lighter than 55% of the way across and
    the band spent its second half almost done. `in oklab` makes the mix
    fraction mean what it says. Same two tokens, same six characters changed,
    and it is the single most visible line in this file.

    **2. The stop *positions*, which are now a curve rather than a spacing.**
    Even a perceptually-linear ramp reads as a slab of grey being panned past,
    because the eye locks onto the two places where the rate of change starts
    and stops. So the stops are placed on a smoothstep (3t²−2t³) in oklab L
    rather than at even intervals: the change begins imperceptibly, happens in
    the middle, and *settles* asymptotically into the paper.

    That settle is what removes the knee. The band used to reach full paper at
    100% and the section below it was flat paper from its first pixel, so there
    was a discontinuity in the first derivative at the seam — invisible as an
    edge, but readable as "the gradient stopped here". The last 12% of the ramp
    now covers five luminance levels.

    The two mix families exist because the ramp crosses --color-panel-raised on
    its way: below it, graphite is mixed into black; above it, paper is mixed
    into graphite. Deriving both from tokens rather than hard-coding greys is
    what keeps the band correct if either end of the palette moves.
  */
  const BLACK = "var(--color-bg)";
  /** Graphite mixed down into the page black — the ramp's bottom quarter. */
  const DARK = (graphite: number) =>
    `color-mix(in oklab, var(--color-panel-raised) ${graphite}%, var(--color-bg))`;
  /** Paper mixed up out of the graphite — everything above it. */
  const MIX = (paper: number) =>
    `color-mix(in oklab, var(--color-paper) ${paper}%, var(--color-panel-raised))`;
  const PAPER = "var(--color-paper)";

  /**
   * Position → colour, as the smoothstep tabulates it. Written out rather than
   * computed so the ramp is readable as a shape, and so the mirrored
   * `into-dark` direction is provably the same curve rather than an
   * approximation of it.
   */
  const STOPS: [number, string][] = [
    [0, BLACK],
    [18, DARK(59)],
    [30, MIX(8)],
    [42, MIX(28)],
    [54, MIX(49)],
    [66, MIX(69)],
    [78, MIX(84)],
    [88, MIX(94)],
    [100, PAPER],
  ];

  /**
   * Renders a stop table as a top-to-bottom gradient, mirroring it for the
   * `into-dark` direction so both blends are the same curve read in opposite
   * directions rather than two hand-written approximations of each other.
   */
  const gradient = (stops: [number, string][]) =>
    `linear-gradient(to bottom, ${(intoPaper
      ? stops
      : stops.map(([at, colour]): [number, string] => [100 - at, colour]).reverse()
    )
      .map(([at, colour]) => `${colour} ${at}%`)
      .join(", ")})`;

  const ramp = gradient(STOPS);

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

    It is now derived from the same STOPS table, compressed into the band's last
    60% with a flat black hold above it, rather than hand-written. That is what
    guarantees the endpoint constraint mechanically instead of by review: the
    first stop is BLACK at 0% and the last is PAPER at 100% by construction, so
    no future edit to the curve can reintroduce the seam.
  */
  const HOLD_FROM = 40;
  const held = gradient([
    [0, BLACK],
    ...STOPS.map(([at, colour]): [number, string] => [
      HOLD_FROM + (at * (100 - HOLD_FROM)) / 100,
      colour,
    ]),
  ]);

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

      {/* Grain, between the two ramps and the grid.

          Above the ramps because it is dithering *them* — a 220-level gradient
          over 208–352px bands in 8-bit sRGB, which is inside Chromium's visible
          Mach-band range and is a large part of why the blend read as a
          gradient fill rather than as a material. Below the grid because the
          hairlines are geometry and should stay crisp. See
          `.band-blend__grain` in globals.css. */}
      <div className="band-blend__grain" />

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
