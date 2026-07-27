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
 *  - their hit area was ~20px tall, well under the WCAG 2.2 target-size floor;
 *    py-2.5 with -my-2.5 gives ≥44px without changing the visual rhythm
 */
export function ArrowLink({ href, analytics, className, children, ...props }: ArrowLinkProps) {
  return (
    <a
      href={href}
      className={cn(
        "group/arrow -my-2.5 inline-flex items-center gap-2 py-2.5 font-mono text-[length:var(--text-caption)] tracking-[0.08em] uppercase no-underline",
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
