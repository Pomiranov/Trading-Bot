import { cn } from "@/lib/utils";

/** The grid itself, as one declaration, so the lit copy cannot drift from the base. */
const GRID_LINES = `repeating-linear-gradient(to right, currentColor 0 1px, transparent 1px 64px), repeating-linear-gradient(to bottom, currentColor 0 1px, transparent 1px 64px)`;

/**
 * How the grid is faded out at its own edges, so it never terminates in a
 * visible line. Three shapes, because the three places this is used are three
 * different aspect ratios and one mask cannot serve all of them.
 *
 * `pool`  — a centred ellipse. Correct for the hero panel, which is close enough
 *           to square that an elliptical falloff reaches all four edges at
 *           roughly the same rate.
 *
 * `panel` — independent fades per axis. On a wide, short panel (the closing
 *           access panel is ~1210×740 at 1440px) the `pool` ellipse covered only
 *           x 10–90% and y 10–80%, so every vertical line stopped dead ~110px
 *           short of the panel foot and every horizontal one ~120px short of its
 *           right edge. That is the "line hanging in space" artefact this pass
 *           was opened to remove: a mask tuned for one aspect ratio, reused at
 *           another. Two long linear ramps intersect into a soft rectangular
 *           vignette that reaches much closer to all four edges and dissolves
 *           over ~18% rather than cutting.
 *
 * `band`   — full-bleed horizontally, faded only at the left and right margins
 *            and held at full strength vertically. For a grid that runs the
 *            entire height of a section and must join the transition band above
 *            and below it without a seam: fading the top or bottom would put a
 *            horizon inside the section, which is the exact thing the paper
 *            bands are being repaired for.
 */
const EDGE_FADE = {
  pool: "radial-gradient(ellipse 80% 70% at 50% 45%, #000 0%, transparent 78%)",
  panel:
    "linear-gradient(to right, transparent 0%, #000 12%, #000 88%, transparent 100%), " +
    "linear-gradient(to bottom, transparent 0%, #000 10%, #000 86%, transparent 100%)",
  band: "linear-gradient(to right, transparent 0%, #000 14%, #000 86%, transparent 100%)",
} as const;

export type GridMask = keyof typeof EDGE_FADE;

/**
 * The faint technical grid behind a dark panel.
 *
 * Two `repeating-linear-gradient`s rather than an SVG pattern or an image: it
 * is one paint, no request, no extra DOM, and it scales to any panel size
 * without re-tiling artefacts.
 *
 * Masked to fade out at the edges so the grid has no visible boundary. A grid
 * that stops in a hard line reads as a texture someone pasted in; one that
 * dissolves reads as depth. The alpha is deliberately at the threshold of
 * perception — if you can count the cells without looking for them, it is too
 * strong.
 *
 * `aria-hidden` and pointer-events-none: it is atmosphere, not content.
 *
 * ── The `signal` layer ──
 *
 * With `signal`, a second copy of the same grid is stacked on top in the cold
 * signal colour, masked to a soft circle at the pointer. The effect is that the
 * grid lines *near the cursor* light up and fade back as it moves away — the
 * "premium signal pulse" the brief asks for, applied to real geometry rather
 * than as a glow floating over it.
 *
 * It requires an ancestor `ui/signal-field.tsx`, which supplies the pointer
 * position. Without one the variables are unset, `--signal-on` falls back to 0,
 * and this layer is fully transparent — so the panel is unchanged on touch, under
 * reduced motion, and with no JS. It paints and composites; it never lays out,
 * so it cannot shift anything.
 *
 * The lines are drawn with `currentColor` and the colour set per layer, so the
 * base and the lit copy are guaranteed to be the same geometry on the same 64px
 * pitch. Two hand-written copies of the gradient pair is exactly how they would
 * drift by a pixel and start shimmering against each other.
 *
 * Cyan in a `radial-gradient` mask over a decorative grid is the permitted use of
 * the signal colour — light, not ink. See the doctrine at the top of
 * tokens/color.css.
 *
 * ── `tone="paper"` ──
 *
 * The same geometry on the light bands, in graphite hairlines instead of white.
 * It exists so the grid does not stop where the page changes material: before
 * this, `#foundation` and `#pricing` had a grid only inside the 176–256px
 * transition band above them and bare paper for the remaining ~900px, which is
 * most of why a band read as a white block someone inserted rather than as the
 * same page changing state.
 *
 * Its lit layer is *not* cyan. Cold blue on #f4f2ec is invisible at the alpha
 * the palette doctrine permits and reads as a print registration error above it
 * — the same reasoning that keeps the blue off route cards inside a paper band.
 * It lights in cold white instead, which on paper means the ground lifts toward
 * white and the lines cool very slightly. See `.signal-field__grid--paper`.
 */
export function GridBackplate({
  className,
  signal = false,
  tone = "dark",
  mask = "pool",
}: {
  className?: string;
  /** Light the grid up around the pointer. Requires a `SignalField` ancestor. */
  signal?: boolean;
  /** Which ground the grid is drawn on. Sets the hairline colour. */
  tone?: "dark" | "paper";
  /** Which edge falloff to use. See EDGE_FADE for how to choose. */
  mask?: GridMask;
}) {
  const paper = tone === "paper";
  const fade = EDGE_FADE[mask];

  return (
    <>
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute inset-0",
          paper
            ? "text-[color:var(--color-line-light)]"
            : "text-[color:var(--color-border)]",
          className,
        )}
        style={{
          backgroundImage: GRID_LINES,
          // Paper is the brighter ground, so a hairline at the same alpha reads
          // heavier on it than the white one does on black. Held further back so
          // the two bands and the dark page are the same *perceived* grid.
          opacity: paper ? 0.34 : 0.5,
          maskImage: fade,
          WebkitMaskImage: fade,
          maskComposite: "intersect",
          WebkitMaskComposite: "source-in",
        }}
      />

      {signal ? (
        <div
          aria-hidden="true"
          className={cn(
            "signal-field__grid pointer-events-none absolute inset-0",
            paper && "signal-field__grid--paper",
            className,
          )}
          style={{
            backgroundImage: GRID_LINES,
            // The lit copy carries the panel's own edge fade too, or it would
            // stay at full strength out to the clipped edge while the grid
            // underneath it has already dissolved — lighting lines that are not
            // visibly there.
            ["--signal-edge-fade" as string]: fade,
          }}
        />
      ) : null}
    </>
  );
}
