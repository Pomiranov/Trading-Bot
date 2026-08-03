import { cn } from "@/lib/utils";

export interface AssistantOrbProps {
  /** Whether the panel this orb controls is open. Drives `aria-expanded`. */
  open: boolean;
  /** Id of the panel, for `aria-controls`. */
  controls: string;
  /** Accessible name. The orb carries no glyph, so this is the only name it has. */
  label: string;
  onClick: () => void;
}

/**
 * The assistant orb — a glass sphere with light moving inside it.
 *
 * ── Where the design comes from ──
 *
 * `~/Downloads/Vois Asistent.mp4`, read frame by frame rather than from memory:
 * a 720×540, 30fps, 20s seamless loop of a single sphere on pure black. What the
 * frames actually establish, in the order it matters:
 *
 *   • the crown is the darkest part of the object — near-black navy at the top,
 *     which is what makes it read as a sphere rather than as a circle
 *   • the specular rim is on the *lower* edge, brightest lower-left, with a
 *     hairline continuing all the way round
 *   • the interior is a wave, not a gradient: an ice-cyan band sweeps diagonally
 *     through a deeper blue and never repeats its shape across the loop
 *   • the outer halo is very tight — the object is lit from within, and almost
 *     none of that light escapes it
 *
 * ── What was deliberately not copied ──
 *
 * The reference's magenta/violet crest. That is Siri's palette, not this one:
 * the page is monochrome with cold blue as light, and `purple-gradient` is a
 * budget-0 rule in `check-design-tokens.mjs` precisely so a copied snippet cannot
 * reintroduce one. The orb is built from ice-blue through deep navy instead,
 * which is also the only version of it that sits correctly next to the rest of
 * the page.
 *
 * There is also no icon, and that follows the reference exactly — the sphere is
 * the mark. A glyph inside it would be a second focal point in a 56px object, and
 * every candidate (a microphone, a spark, a waveform) says something more
 * specific than this button can currently deliver. `aria-label` carries the name
 * for assistive tech, and `.assistant-dock__hint` reveals it visually on hover,
 * so nothing depends on the reader guessing.
 *
 * ── How the flow is made ──
 *
 * Two oversized gradient fields counter-rotating at coprime periods (24s / 31s)
 * behind a `screen` blend, inside a clipped circle. Two rotations at different
 * rates never return to the same relative position within a human attention
 * span, which is what produces a wave that appears not to loop — the same reason
 * the hero aperture's three orbits are coprime.
 *
 * It is `transform` only, so both layers composite and neither repaints. The
 * `blur` is a static filter, applied once to each layer rather than animated.
 *
 * ── This component is presentational ──
 *
 * It owns no state and knows nothing about what the button does. `open`,
 * `controls` and `onClick` all arrive from `assistant-launcher.tsx`, which is
 * where the future API handler goes. Keeping the sphere free of that is what
 * makes it reusable as an inline entry point later — in the nav, or at the foot
 * of a section — without carrying a panel around with it.
 */
export function AssistantOrb({ open, controls, label, onClick }: AssistantOrbProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      aria-controls={controls}
      aria-label={label}
      data-open={open}
      className={cn("assistant-orb")}
    >
      {/*
        ── Why the sphere is an inner element and not the button itself ──

        The sphere clips its two flow layers with `overflow: hidden`, and the
        button needs a hit area *larger* than the sphere: below `md` the sphere is
        40px, which is the largest it can be and still clear a FAQ row's disclosure
        marker (the derivation is on `.assistant-dock` in globals.css), and 40px is
        under the 44px minimum for a fingertip.

        Those two requirements cannot live on one element — a 44px pseudo-element
        target on the button would be clipped away by the button's own
        `overflow: hidden`. So the button is the target and carries no paint, and
        `__sphere` is the object and carries no hit testing.

        The layers inside are elements rather than pseudo-elements because the
        sphere needs four paint layers — well, flow A, flow B, glass — and an
        element has only `::before` and `::after`. All four are decorative and
        empty, so none of them reaches the accessibility tree.
      */}
      <span className="assistant-orb__sphere">
        <span className="assistant-orb__flow" />
        <span className="assistant-orb__flow assistant-orb__flow--b" />
        <span className="assistant-orb__glass" />
      </span>
    </button>
  );
}
