"use client";

import { useActiveSection } from "@/hooks/use-active-section";
import { cn } from "@/lib/utils";

interface NavLinksProps {
  links: readonly { key: string; href: string; label: string }[];
  /** Localized landmark name — was a hardcoded English "Primary". */
  label: string;
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
 *
 * ── Why `lg` and not `md` ──
 *
 * The audit proposed showing these from 768px, on the reasoning that there was
 * "ample room for at least three links" in the 768–1023 band. Measurement says
 * otherwise in Russian: at 768 the page padding is 61px a side, leaving 646px,
 * and the wordmark + five Cyrillic labels + the locale toggle + the CTA need
 * roughly 750. The CTA ended at x=813 in a 768 viewport — 45px off-screen,
 * invisible only because `overflow-x: clip` on <html> was hiding it.
 *
 * English fits; Russian is the primary language and does not. Below lg the
 * hamburger carries everything, which is what it is for.
 */
export function NavLinks({ links, label }: NavLinksProps) {
  const ids = links.map((l) => l.href.slice(1));
  const active = useActiveSection(ids);

  return (
    <nav aria-label={label} className="hidden items-center gap-7 lg:flex">
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
