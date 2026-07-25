import { createElement, type ElementType, type ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Section-level heading (h2 by default). Not for the hero — that owns its
 * own --text-hero scale. Accepts a serif italic accent word via the
 * <Accent> sub-component when the brief calls for one (used sparingly).
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

/** One-word/phrase serif italic accent inside a heading — see the italic
 * descender clearance rule; always paired with leading/pb reserve. */
export function HeadingAccent({
  className,
  ...props
}: ComponentPropsWithoutRef<"span">) {
  return (
    <span
      className={cn(
        "font-serif italic font-normal leading-[1.1] pb-1 inline-block",
        className,
      )}
      {...props}
    />
  );
}
