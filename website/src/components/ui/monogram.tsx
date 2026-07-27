import type { SVGProps } from "react";

/**
 * The Quant mark — a decision aperture.
 *
 * A 320° ring with a 40° blade opening at upper right, and a straight tail
 * crossing the ring's lower-right edge. The tail is what makes the form read
 * as a Q rather than a dial or a loading spinner, and it carries the idea: a
 * decision that has cleared every gate leaves the aperture along it.
 *
 * Supersedes the previous open-ring mark (docs/adr/0001-monogram.md), which
 * was designed for the QuantFlow name and deliberately avoided a letterform.
 * With the brand now literally "Quant", a Q that is still a geometric
 * instrument rather than a letter is the better answer — and it resolves that
 * ADR's original worry, since a ring crossed by a tail cannot be misread as a
 * prohibition sign the way a bare ring with a gap could.
 *
 * Pure stroke linework, single weight, one colour via currentColor, so it
 * inherits correctly in the nav, the footer and on paper. The orange signal
 * node belongs to the large-format hero poster only
 * (scripts/media/build-poster.mjs) — at 24px it would collapse into a blob.
 *
 * Geometry is shared with that script: ring −20°→−60°, tail at 45° spanning
 * 0.52r to 1.32r.
 */
export function Monogram(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Quant"
      {...props}
    >
      {/* Aperture — 320° ring, blade opening at upper right */}
      <path
        d="M 80.07 39.06 A 32 32 0 1 1 66 22.29"
        stroke="currentColor"
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Tail — crosses the ring's lower-right edge; the exit path */}
      <path
        d="M 61.77 61.77 L 79.87 79.87"
        stroke="currentColor"
        strokeWidth="9"
        strokeLinecap="round"
      />
    </svg>
  );
}
