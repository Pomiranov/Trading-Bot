import { cn } from "@/lib/utils";

/** The grid itself, as one declaration, so the lit copy cannot drift from the base. */
const GRID_LINES = `repeating-linear-gradient(to right, currentColor 0 1px, transparent 1px 64px), repeating-linear-gradient(to bottom, currentColor 0 1px, transparent 1px 64px)`;

/** Fades the grid out at the panel's edges so it has no visible boundary. */
const EDGE_FADE = "radial-gradient(ellipse 80% 70% at 50% 45%, #000 0%, transparent 78%)";

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
 */
export function GridBackplate({
  className,
  signal = false,
}: {
  className?: string;
  /** Light the grid up around the pointer. Requires a `SignalField` ancestor. */
  signal?: boolean;
}) {
  return (
    <>
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute inset-0 text-[color:var(--color-border)]",
          className,
        )}
        style={{
          backgroundImage: GRID_LINES,
          opacity: 0.5,
          maskImage: EDGE_FADE,
          WebkitMaskImage: EDGE_FADE,
        }}
      />

      {signal ? (
        <div
          aria-hidden="true"
          className={cn("signal-field__grid pointer-events-none absolute inset-0", className)}
          style={{ backgroundImage: GRID_LINES }}
        />
      ) : null}
    </>
  );
}
