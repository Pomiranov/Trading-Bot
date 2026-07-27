import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

interface StatProps extends Omit<ComponentPropsWithoutRef<"div">, "children"> {
  /**
   * Pre-formatted string. Deliberately not `number`.
   *
   * The previous component ran `Intl.NumberFormat` inside itself, which is a
   * hydration hazard the moment it lands in a client component — Node and
   * browser ICU can disagree on separators. Format on the server and pass the
   * string in.
   */
  value: string;
  label: string;
  /** Second line under the label — units, source, qualifier. */
  hint?: string;
  size?: "lg" | "sm";
  tone?: "default" | "signal";
}

/**
 * A single figure with its label.
 *
 * Replaces five hand-rolled stat treatments (`ui/stat-number.tsx` plus inline
 * copies in the hero, sandbox, CTA and dashboard mockup), which between them
 * used four different label sizes and three different label opacities — one of
 * them `rgba(255,255,255,0.35)`, well below the readable floor.
 *
 * What this component shows is now always a *configured limit or system
 * constant* — never a performance result. No win rate, profit factor, sample
 * size, Sharpe or P&L appears anywhere on the site.
 */
export function Stat({
  value,
  label,
  hint,
  size = "lg",
  tone = "default",
  className,
  ...props
}: StatProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)} {...props}>
      <p
        className={cn(
          "font-mono font-semibold tabular-nums",
          size === "lg"
            ? "text-[length:var(--text-display-number)] leading-[var(--text-display-number--line-height)] tracking-[var(--text-display-number--letter-spacing)]"
            : "text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] tracking-[var(--text-h3--letter-spacing)]",
          tone === "signal"
            ? "text-[color:var(--color-accent)]"
            : "text-[color:var(--color-text-primary)]",
        )}
      >
        {value}
      </p>
      <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase text-[color:var(--color-text-tertiary)]">
        {label}
      </p>
      {hint ? (
        <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
