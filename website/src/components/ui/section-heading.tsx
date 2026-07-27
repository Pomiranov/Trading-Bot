import { createElement, type ElementType, type ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Section-level heading (h2 by default). Not for the hero — that owns its
 * own --text-hero scale.
 */
export function SectionHeading<T extends ElementType = "h2">({
  as,
  className,
  ...props
}: { as?: T } & ComponentPropsWithoutRef<T>) {
  // createElement, not JSX — see mono-label.tsx for why the "as" pattern
  // needs this escape hatch.
  return createElement(as ?? "h2", {
    className: cn(
      "text-[length:var(--text-section-heading)] leading-[var(--text-section-heading--line-height)] tracking-[var(--text-section-heading--letter-spacing)] font-medium text-[color:var(--color-text-primary)]",
      className,
    ),
    ...props,
  });
}
