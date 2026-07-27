"use client";

import { useActiveSection } from "@/hooks/use-active-section";
import { cn } from "@/lib/utils";

interface NavLinksProps {
  links: readonly { key: string; href: string; label: string }[];
}

/**
 * The primary nav row, with an underline on the section currently in view.
 *
 * On a page this long the active state is the single most useful affordance the
 * header can offer, and it was absent: all five links rendered identically at
 * `--color-text-tertiary` regardless of scroll position.
 *
 * The underline is a `scaleX` on a 1px pseudo-element rather than a
 * `border-bottom` toggle, so it grows from the centre instead of appearing —
 * and because it animates `transform`, it composites and never reflows the row.
 *
 * The active section comes from `useActiveSection`, which is IntersectionObserver
 * based. Nothing here reads scroll position; see that hook for why that is a
 * hard rule on this page.
 */
export function NavLinks({ links }: NavLinksProps) {
  const ids = links.map((l) => l.href.slice(1));
  const active = useActiveSection(ids);

  return (
    <nav aria-label="Primary" className="hidden items-center gap-6 md:flex lg:gap-7">
      {links.map(({ key, href, label }) => {
        const isActive = active === href.slice(1);
        return (
          <a
            key={key}
            href={href}
            aria-current={isActive ? "true" : undefined}
            className={cn(
              "group/nav relative -my-2.5 rounded-[var(--radius-sm)] py-2.5 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase no-underline transition-colors duration-[var(--duration-micro)]",
              "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--color-accent)]",
              isActive
                ? "text-[color:var(--color-text-primary)]"
                : "text-[color:var(--color-text-tertiary)] hover:text-[color:var(--color-text-primary)]",
            )}
          >
            {label}
            <span
              aria-hidden="true"
              className={cn(
                "absolute inset-x-0 -bottom-0.5 h-px origin-center bg-[color:var(--color-text-primary)] transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-expo)]",
                isActive ? "scale-x-100" : "scale-x-0 group-hover/nav:scale-x-100",
              )}
            />
          </a>
        );
      })}
    </nav>
  );
}
