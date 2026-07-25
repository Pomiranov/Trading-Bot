import { createElement, type ElementType, type ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Section label / eyebrow / metadata strip. Rationed by design (see
 * taste-skill's EYEBROW RESTRAINT rule: max 1 per 3 sections) — this
 * component only provides the visual treatment, the calling section
 * decides whether it has earned one.
 */
export function MonoLabel<T extends ElementType = "p">({
  as,
  className,
  ...props
}: { as?: T } & ComponentPropsWithoutRef<T>) {
  // createElement, not JSX, for the polymorphic tag: TS can't verify an
  // arbitrary generic ElementType's props against JSX.IntrinsicElements,
  // this is the standard escape hatch for the "as" prop pattern.
  return createElement(as ?? "p", {
    className: cn(
      "font-mono text-[length:var(--text-label)] uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]",
      className,
    ),
    ...props,
  });
}
