import { cn } from "@/lib/utils";

/**
 * The blend between the page's black base and one of its two paper bands, with
 * the route line running through it.
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
 * A real element in the flow cannot overlap anything, needs no per-breakpoint
 * arithmetic, and — the reason it is worth its height — it is somewhere for the
 * route line to *be*. The transition is exactly where the spine crosses from one
 * material into the other, so the band that performs the crossing is the natural
 * host for it.
 *
 * ── The stroke changes material with the background ──
 *
 * The spine here is stroked with a vertical gradient rather than a flat colour,
 * because neither tone survives the whole band: the cold hairline
 * (`--color-signal-line`, 28% alpha) is invisible on #f4f2ec, and the graphite
 * used on paper is invisible on black. Interpolating between them means the line
 * stays legible across the blend and reads as one continuous route that changes
 * material — which is the thing the two bands are for.
 *
 * A gradient SVG stroke on decorative geometry is the permitted use of the cold
 * blue. See the doctrine at the top of tokens/color.css: it is light, never ink.
 * The `cyan-as-ink` gate in check-design-tokens.mjs refuses `via-*`/`to-*` colour
 * utilities in component source for exactly this reason, so the stops are
 * declared as SVG `stop-color` on an aria-hidden path, which is the shape the
 * doctrine allows.
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
  /**
   * Draw the route line through the blend. On by default — a transition band
   * with nothing in it is dead height. Off for a blend that is purely a colour
   * change, where the route has already terminated.
   */
  spine?: boolean;
  className?: string;
}

export function BandTransition({ direction, spine = true, className }: BandTransitionProps) {
  const intoPaper = direction === "into-paper";

  /**
   * Unique per direction, because both variants can appear on one page (they do:
   * Foundation and Pricing are each entered and left) and duplicate SVG gradient
   * ids in one document resolve to whichever came first.
   */
  const gradientId = `band-route-${direction}`;

  return (
    <div
      aria-hidden="true"
      className={cn(
        // `h-40` (160px) at every viewport. The blend does not need to scale with
        // the section rhythm — it is a material change, and a material change
        // reads the same at any width. Fixed height also means it can never
        // become the tallest thing on a small screen.
        "relative isolate h-40 w-full",
        className,
      )}
      style={{
        /*
          Four stops, and the fourth is the one that matters.

          The first version was `bg → panel-raised → paper`. On paper that
          measured as a hard horizon rather than a blend, and the reason is the
          token values: --color-bg is #030303 and --color-panel-raised is #171717.
          Both are near-black, so a stop at 55% spent the whole first half of the
          band going from black to *slightly less black* and then crossed 220
          luminance levels in the remaining 45%. All of the change happened in
          ~40px, which is the abrupt cut this component exists to remove.

          Inserting a genuine mid-tone — a 45/55 mix of paper into the graphite,
          around three-quarters of the way along — spreads the luminance ramp
          across the whole 160px. `color-mix` keeps it derived from the two
          tokens rather than hard-coding a grey that would then need maintaining
          if either end of the palette moved.
        */
        backgroundImage: intoPaper
          ? "linear-gradient(to bottom, var(--color-bg) 0%, var(--color-panel-raised) 38%, color-mix(in srgb, var(--color-paper) 45%, var(--color-panel-raised)) 72%, var(--color-paper) 100%)"
          : "linear-gradient(to bottom, var(--color-paper) 0%, color-mix(in srgb, var(--color-paper) 45%, var(--color-panel-raised)) 28%, var(--color-panel-raised) 62%, var(--color-bg) 100%)",
      }}
    >
      {spine ? (
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="route-spine absolute inset-0 h-full w-full"
        >
          <defs>
            {/*
              `userSpaceOnUse`, and this is load-bearing rather than a style
              preference.

              The default is `objectBoundingBox`, and per the SVG spec a gradient
              in those units is *disabled entirely* when the referencing element's
              bounding box has zero width or height. This path is `M50 0 V100` — a
              perfectly vertical line, so its bbox is zero-wide, so the gradient
              did not render and the line was invisible. Measured: the transition
              band drew its background ramp correctly and contained no visible
              spine at all.

              In user space the coordinates are viewBox units, so y1=0 → y2=100
              spans the band top to bottom regardless of the path's bbox.
            */}
            <linearGradient
              id={gradientId}
              gradientUnits="userSpaceOnUse"
              x1="0"
              y1="0"
              x2="0"
              y2="100"
            >
              {/* Ordered to match the background ramp: whichever end sits on
                  black gets the cold hairline, whichever sits on paper gets
                  graphite. */}
              <stop
                offset="0%"
                stopColor={
                  intoPaper ? "var(--color-signal)" : "var(--color-border-on-paper-strong)"
                }
                stopOpacity={intoPaper ? "0.45" : "0.5"}
              />
              <stop offset="50%" stopColor="var(--color-signal)" stopOpacity="0.3" />
              <stop
                offset="100%"
                stopColor={
                  intoPaper ? "var(--color-border-on-paper-strong)" : "var(--color-signal)"
                }
                stopOpacity={intoPaper ? "0.5" : "0.45"}
              />
            </linearGradient>
          </defs>

          <path
            d="M50 0 V100"
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      ) : null}
    </div>
  );
}
