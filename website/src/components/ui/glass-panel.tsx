"use client";

import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Liquid Glass surface — translucent + blurred backdrop, animated border
 * on hover, soft ambient glow on featured variant.
 * `strong` = higher opacity for panels that need legibility over busy backgrounds.
 * `featured` = animated orange border gradient treatment for hero cards / pricing.
 * `glow` = subtle orange ambient glow (use max once per section viewport).
 */
export function GlassPanel({
  className,
  strong = false,
  featured = false,
  glow = false,
  style,
  ...props
}: ComponentPropsWithoutRef<"div"> & {
  strong?: boolean;
  featured?: boolean;
  glow?: boolean;
}) {
  if (featured) {
    return (
      <div
        className={cn("glass-premium-featured", className)}
        style={{
          padding: "1px",
          ...style,
        }}
        {...props}
      />
    );
  }

  return (
    <div
      className={cn(
        "glass-premium",
        strong && "!bg-[color:var(--color-glass-surface-strong)]",
        className,
      )}
      style={{
        ...(glow && {
          boxShadow: `
            inset 0 1px 0 var(--color-glass-highlight),
            0 4px 24px rgba(0,0,0,0.4),
            0 1px 4px rgba(0,0,0,0.3),
            0 0 60px rgba(255,138,30,0.06)
          `,
        }),
        ...style,
      }}
      {...props}
    />
  );
}
