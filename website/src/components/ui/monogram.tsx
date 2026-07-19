import type { SVGProps } from "react";

/**
 * QuantFlow mark. Not a literal "QF" wordmark — a single geometric form
 * drawn from the belief-network visual language itself, so the mark and the
 * hero 3D scene share one design DNA. Reads as an instrument dial / gauge,
 * intentionally (control-room precision, not a logo-as-decoration).
 *
 * v2 (first pass read as a "prohibited" circle-slash sign — rejected after
 * a screenshot check, see docs/adr/0001-monogram.md). Redesigned around a
 * single open ring:
 *  - One end terminates in a solid node (frozen — the fixed, proven rule).
 *  - The other end uncoils into a straight trailing line, tangent to the
 *    ring's own curve (fluid — trust that keeps moving, never resolves).
 *
 * Pure stroke linework, single weight, one color via currentColor.
 */
export function Monogram(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="QuantFlow"
      {...props}
    >
      {/* Open ring — 300° arc, 60° gap at upper right */}
      <path
        d="M 80.9 41.7 A 32 32 0 1 1 58.3 19.1"
        stroke="currentColor"
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Fluid tail — uncoils tangent from the ring's own curvature */}
      <path
        d="M 58.3 19.1 L 37.0 13.4"
        stroke="currentColor"
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Frozen anchor — solid node at the ring's other terminus */}
      <circle cx="80.9" cy="41.7" r="7" fill="currentColor" />
    </svg>
  );
}
