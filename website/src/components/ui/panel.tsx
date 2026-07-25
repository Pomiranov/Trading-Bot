import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Elevated surface. Per impeccable's "cards are the lazy answer" rule, use
 * only when elevation communicates real hierarchy (dashboard mockup frame,
 * the confidence-slider panel) — not as a default wrapper for every block.
 * Group unrelated content with spacing/dividers instead.
 */
export function Panel({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-[color:var(--color-border)] bg-[color:var(--color-surface)]",
        className,
      )}
      {...props}
    />
  );
}
