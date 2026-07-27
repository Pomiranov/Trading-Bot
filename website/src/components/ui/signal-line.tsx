"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Orientation = "vertical" | "horizontal" | "bracket";

interface SignalLineProps {
  orientation: Orientation;
  /** Fractional positions along the line, 0..1, that get a node dot. */
  nodes?: number[];
  /** Static renders fully drawn immediately — for decoration that never animates. */
  behaviour?: "draw" | "static";
  className?: string;
}

/**
 * The page's connective tissue: audience → pipeline, the broker route diagram,
 * and any place where two blocks need to read as *connected* rather than
 * merely adjacent.
 *
 * ── Three rules, each of which fixes something that has actually gone wrong ──
 *
 * 1. **In flow, never absolutely positioned across a section boundary.** A
 *    connector spanning two sections has to be re-derived at every breakpoint
 *    and misaligns the moment a card grows a line of text. The audience→pipeline
 *    bracket is owned by the *bottom of the audience section*, so deleting the
 *    section below it leaves nothing floating.
 *
 * 2. **IntersectionObserver only.** No scroll listener, no `getBoundingClientRect`
 *    in a rAF loop, no scroll-linked transform. Nothing on this page may read or
 *    write scroll position except `motion/scroll-driver.ts` — the previous
 *    pinned-ScrollTrigger pipeline is exactly what produced the backward-scroll
 *    bug, and a scroll-driven connector would reintroduce the same coupling.
 *
 * 3. **The base style is the drawn state.** `data-drawn` starts `"true"` on the
 *    server and only flips to `"false"` on a client that has both JS and no
 *    reduced-motion preference. So: no JS → drawn. Reduced motion → drawn.
 *    Observer never fires → drawn. The line can fail in every direction and
 *    still be visible, which is the opposite of the `initial={false}` trap that
 *    once left all 32 cards at `opacity: 0`.
 *
 * Hidden below `md`: single-column layouts have nothing for a connector to
 * connect, and a vertical hairline beside one column of cards reads as an
 * artefact rather than as a signal.
 */
export function SignalLine({
  orientation,
  nodes = [],
  behaviour = "draw",
  className,
}: SignalLineProps) {
  const ref = useRef<SVGSVGElement>(null);
  // Server value is `true` (= drawn). See rule 3 above: every failure mode must
  // land on "visible", so the animated state is opt-in on the client only.
  const [drawn, setDrawn] = useState(true);

  useEffect(() => {
    if (behaviour === "static") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const el = ref.current;
    if (!el) return;

    setDrawn(false);

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setDrawn(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [behaviour]);

  const stroke = "var(--color-signal-line)";
  const drawnAttr = behaviour === "static" ? "true" : String(drawn);

  if (orientation === "bracket") {
    /**
     * Descends from the audience card row and gathers into a single stem
     * feeding the pipeline below. Drawn in a 0–100 × 0–100 viewBox with
     * `preserveAspectRatio="none"` so the horizontal span stretches with the
     * container while the stroke stays 1px — a uniformly scaled bracket would
     * thin out to nothing at 1440.
     */
    return (
      <svg
        ref={ref}
        aria-hidden="true"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className={cn("hidden h-16 w-full md:block", className)}
        style={{ filter: "drop-shadow(0 0 6px var(--color-signal-dim))" }}
      >
        <path
          className="signal-draw"
          data-drawn={drawnAttr}
          style={{ ["--signal-len" as string]: "300" }}
          d="M16 0 V44 H84 V0 M50 44 V100"
          fill="none"
          stroke={stroke}
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  if (orientation === "horizontal") {
    return (
      <svg
        ref={ref}
        aria-hidden="true"
        viewBox="0 0 100 8"
        preserveAspectRatio="none"
        className={cn("hidden h-2 w-full md:block", className)}
      >
        <line
          className="signal-draw"
          data-drawn={drawnAttr}
          style={{ ["--signal-len" as string]: "100" }}
          x1="0"
          y1="4"
          x2="100"
          y2="4"
          stroke={stroke}
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
        {nodes.map((at) => (
          <circle key={at} cx={at * 100} cy="4" r="1.6" fill="var(--color-signal)" opacity="0.7" />
        ))}
      </svg>
    );
  }

  return (
    <svg
      ref={ref}
      aria-hidden="true"
      viewBox="0 0 8 100"
      preserveAspectRatio="none"
      className={cn("h-full w-2", className)}
    >
      <line
        className="signal-draw"
        data-drawn={drawnAttr}
        style={{ ["--signal-len" as string]: "100" }}
        x1="4"
        y1="0"
        x2="4"
        y2="100"
        stroke={stroke}
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
