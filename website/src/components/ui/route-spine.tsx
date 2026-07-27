import { cn } from "@/lib/utils";

/**
 * The page's continuous decision route: the thin line that carries the eye from
 * one section into the next, drawing itself as the reader scrolls.
 *
 * ── Why this exists alongside `ui/signal-line.tsx` ──
 *
 * `SignalLine` draws once, on an IntersectionObserver, and then stops. That is
 * correct for a static bracket but it is not a *route* — the line is either
 * absent or complete, and a reader arriving mid-section sees no relationship
 * between where they were and where they are going. The brief here is a
 * connector whose progress tracks scroll position continuously, so following it
 * feels like travelling along it.
 *
 * ── The hard constraint, and how this satisfies it without breaking it ──
 *
 * Nothing on this site may read or write scroll position except
 * `motion/scroll-driver.ts`. That is not a style preference: a second reader on
 * the value Lenis animates is exactly the coupling that produced the
 * backward-scroll bug (documented at length in that module), and every reveal on
 * the page was moved to IntersectionObserver to eliminate it.
 *
 * So this uses **native CSS scroll-driven animation** — `view-timeline-name` on
 * the wrapper, `animation-timeline` on the geometry. The progress value is
 * computed by the compositor from the element's own position in its scrollport.
 * No scroll listener, no `getBoundingClientRect` in a rAF loop, no JS at all:
 * this component ships zero client bytes and is a server component. There is
 * nothing for Lenis to desync from, because nothing here observes scrolling —
 * the browser resolves the timeline itself.
 *
 * ── Failure modes all land on "drawn" ──
 *
 * The same rule `SignalLine` documents, and for the same reason. The base style
 * is the *finished* line: `stroke-dashoffset: 0`. The animation is layered on
 * top only inside `@media (prefers-reduced-motion: no-preference)` and
 * `@supports (animation-timeline: view())`. Consequences:
 *
 *   • no JS at all              → drawn (there is no JS to fail)
 *   • reduced motion            → drawn, instantly, no animation attached
 *   • Firefox / older Safari    → drawn, the @supports block never applies
 *   • timeline never resolves   → drawn
 *
 * A line that animated its opacity or its width would vanish in those cases
 * instead. See `.route-spine*` in globals.css.
 *
 * ── It cannot cause horizontal scroll or layout shift ──
 *
 * The SVG is `w-full` inside the section's own content container, so it is
 * bounded by the same max-width as the text beside it and can never be wider
 * than its parent. It animates `stroke-dashoffset` only — a compositor-only
 * property that triggers neither layout nor paint reflow — so its height is
 * fixed from first render and identical in every state. `aria-hidden`, so it is
 * absent from the accessibility tree entirely.
 *
 * ── Tone is automatic ──
 *
 * The stroke is `--color-route-stroke`, which `.section-paper` re-points to a
 * graphite. A cyan hairline at 28% alpha is invisible on #f4f2ec, and raising
 * its alpha to compensate would read as a print registration error. Because the
 * variable is re-pointed by the *band*, a spine placed inside a paper section
 * inverts without knowing paper exists — the same mechanism every card uses.
 */

type Variant = "stem" | "fan" | "gather";

interface RouteSpineProps {
  /**
   * `stem`   — one vertical line. The connector between two sections.
   * `fan`    — one line descending, then splitting to `lanes` column centres.
   *            Put it *above* a card row so the route visibly feeds into it.
   * `gather` — `lanes` column centres converging into one line. Put it *below*
   *            a card row so the row visibly feeds onward.
   */
  variant?: Variant;
  /** Column count for `fan` / `gather`. Ignored by `stem`. */
  lanes?: number;
  /** Height role. `sm` inside a section, `md` between sections, `lg` for a major hinge. */
  size?: "sm" | "md" | "lg";
  /**
   * Draws a small dot where the line begins, marking the junction. Off for the
   * first spine on the page, where there is nothing above it to join.
   */
  node?: boolean;
  className?: string;
}

const HEIGHT: Record<NonNullable<RouteSpineProps["size"]>, string> = {
  sm: "h-12",
  md: "h-20",
  lg: "h-28",
};

/**
 * Path geometry in a 0–100 × 0–100 box with `preserveAspectRatio="none"`, so the
 * horizontal span stretches with the container while `vectorEffect` keeps the
 * stroke at 1px. A uniformly scaled connector would thin to nothing at 1440.
 *
 * ── There is no length arithmetic here, deliberately ──
 *
 * The draw is a clip wipe on the wrapper, not `stroke-dashoffset`. Two attempts
 * at the dash version failed, both because `vectorEffect="non-scaling-stroke"`
 * resolves dash lengths in *screen pixels* while this geometry is viewBox units
 * on a horizontally-stretched box — a 66-unit crossbar renders ~800px long. The
 * connectors came out as a dash pattern with visible gaps. The full account is in
 * the `.route-spine` block in globals.css; the consequence for this file is that
 * no path needs to know, or state, how long it is.
 */
function geometry(variant: Variant, lanes: number) {
  if (variant === "stem") {
    return { d: "M50 0 V100" };
  }

  // Column centres, evenly distributed: 1/2N, 3/2N, … Matches how a CSS grid
  // with equal columns and a gap places its cells closely enough for a 1px
  // hairline — the connector reads as aligned, and it stays aligned when the
  // grid reflows because both are fractions of the same width.
  const centres = Array.from({ length: lanes }, (_, i) => ((2 * i + 1) / (2 * lanes)) * 100);
  const first = centres[0];
  const last = centres[centres.length - 1];

  if (variant === "fan") {
    // Down the middle to the crossbar, out along it, then down into each lane.
    const drops = centres.map((x) => `M${x.toFixed(2)} 55 V100`).join(" ");
    return { d: `M50 0 V55 M${first.toFixed(2)} 55 H${last.toFixed(2)} ${drops}` };
  }

  // gather — up out of each lane, in along the crossbar, then down the middle.
  const rises = centres.map((x) => `M${x.toFixed(2)} 0 V45`).join(" ");
  return { d: `${rises} M${first.toFixed(2)} 45 H${last.toFixed(2)} M50 45 V100` };
}

export function RouteSpine({
  variant = "stem",
  lanes = 3,
  size = "md",
  node = true,
  className,
}: RouteSpineProps) {
  const { d } = geometry(variant, lanes);

  return (
    /*
      The wrapper owns the timeline. `view-timeline-name` has to sit on an
      element with a real CSS box, and an SVG <path> does not reliably generate
      one for timeline purposes — declaring it here and referencing it by name
      from the path is the supported arrangement. Timeline lookup walks
      ancestors, so the path finds it.

      Hidden below `md` for `fan` / `gather` only: those gather *columns*, and
      below md the grids they belong to are a single column, where a crossbar
      spanning nothing reads as an artefact. A plain `stem` still connects two
      stacked sections at every width, which is the whole point of it on mobile.
    */
    <div
      aria-hidden="true"
      className={cn(
        "route-spine pointer-events-none relative w-full",
        HEIGHT[size],
        variant !== "stem" && "hidden md:block",
        className,
      )}
    >
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="h-full w-full overflow-visible"
      >
        <path
          d={d}
          fill="none"
          stroke="var(--color-route-stroke)"
          strokeWidth="1"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />

        {/*
          The junction dot, marking where this connector joins the one above.

          Not a <circle>: `r` is in user units on a stretched viewBox, so it would
          render as a wide ellipse — 3px tall and ~36px across at 1440. A
          zero-length path with a round cap and `non-scaling-stroke` draws a true
          circle of exactly `strokeWidth` at every viewport instead.

          It needs no animation of its own. The clip wipe reveals top-down and the
          node sits at the top, so it lights up first and the line then draws away
          from it — which is the right reading for a junction.
        */}
        {node ? (
          <path
            d="M50 0 V0.01"
            stroke="var(--color-route-stroke-strong)"
            strokeWidth="3"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        ) : null}
      </svg>
    </div>
  );
}
