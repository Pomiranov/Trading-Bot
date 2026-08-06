import type { SVGProps } from "react";
import { cn } from "@/lib/utils";

const SIZE = {
  xs: "size-4",
  sm: "size-5",
  md: "size-6",
  lg: "size-10",
} as const;

interface BrandMarkProps extends Omit<SVGProps<SVGSVGElement>, "size"> {
  size?: keyof typeof SIZE;
  /**
   * Cold-blue bloom behind the mark. Hero aperture only.
   *
   * A glowing logo in the nav or the footer is what a crypto landing page does.
   * Here the glow means "this is the instrument", so it appears exactly once.
   */
  glow?: boolean;
}

/**
 * The Quant mark — a decision aperture.
 *
 * A 320° ring with a 40° blade opening at upper right, and a straight tail
 * crossing the ring's lower-right edge. The tail is what makes the form read as
 * a Q rather than a dial or a loading spinner, and it carries the idea: a
 * decision that has cleared every gate leaves the aperture along it.
 *
 * ── The geometry is frozen ──
 *
 * Ring −20°→−60°, tail at 45° spanning 0.52r to 1.32r. These exact numbers are
 * duplicated in `scripts/media/build-poster.mjs`, which renders the large-format
 * poster. Changing them here silently desyncs the poster from the site mark —
 * change both together or neither.
 *
 * Single-weight stroke in `currentColor`, so the mark inherits correctly in the
 * nav, in the footer, and on a paper band without a variant for each.
 *
 * Supersedes `ui/monogram.tsx`, adding only `size` and `glow`.
 */
export function BrandMark({ size = "sm", glow = false, className, ...props }: BrandMarkProps) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Quant"
      className={cn(SIZE[size], className)}
      style={glow ? { filter: "drop-shadow(var(--glow-signal-md))" } : undefined}
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
