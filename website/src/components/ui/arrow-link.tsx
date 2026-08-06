"use client";

import { track, type CtaTarget } from "@/lib/analytics/events";
import { cn } from "@/lib/utils";

interface ArrowLinkProps extends Omit<React.ComponentPropsWithoutRef<"a">, "onClick"> {
  href: string;
  analytics?: { target: CtaTarget; location: string };
}

/**
 * Secondary inline link with a travelling arrow.
 *
 * Consolidates `hero-cta.tsx`'s secondary link and `cta/explore-link.tsx`,
 * which were byte-for-byte the same idea implemented twice — and fixes three
 * defects both of them shared:
 *
 *  - they mutated colour via onMouseEnter/onMouseLeave, so the hover state was
 *    unreachable by keyboard; this uses CSS group-hover *and* group-focus
 *  - they had no visible focus indicator of their own
 *  - their hit area was ~20px tall, well under the WCAG 2.2 target-size floor
 *
 * ── The padding that was supposed to fix that was 3px short ──
 *
 * `py-2.5` with `-my-2.5` was the right shape and the wrong number: 13px of
 * caption at 1.5 line-height is 19.5px, plus 20px of padding, is 39.5 — measured
 * at 41px against a 44px floor, on every secondary link on the page. Stated as a
 * `min-h-11` floor rather than recomputed, so it survives a change to the type
 * scale; `py-3`/`-my-3` still carries the horizontal rhythm.
 */
export function ArrowLink({ href, analytics, className, children, ...props }: ArrowLinkProps) {
  return (
    <a
      href={href}
      className={cn(
        "group/arrow -my-3 inline-flex min-h-11 items-center gap-2 py-3 font-mono text-[length:var(--text-caption)] tracking-[0.08em] uppercase no-underline",
        "text-[color:var(--color-text-secondary)] transition-colors duration-[var(--duration-micro)]",
        "hover:text-[color:var(--color-text-primary)] focus-visible:text-[color:var(--color-text-primary)]",
        "rounded-[var(--radius-sm)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--color-accent)]",
        className,
      )}
      onClick={analytics ? () => track({ name: "cta_clicked", props: analytics }) : undefined}
      {...props}
    >
      {children}
      <span
        aria-hidden="true"
        className="transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-expo)] motion-safe:group-hover/arrow:translate-x-1 motion-safe:group-focus-visible/arrow:translate-x-1"
      >
        →
      </span>
    </a>
  );
}
