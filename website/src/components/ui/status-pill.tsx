import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export type StrategyStatus = "live" | "frozen" | "stabilized";

const STATUS_COLOR: Record<StrategyStatus, string> = {
  live: "var(--color-live)",
  frozen: "var(--color-frozen)",
  stabilized: "var(--color-stabilized)",
};

interface StatusPillProps extends Omit<ComponentPropsWithoutRef<"span">, "children"> {
  status: StrategyStatus;
  /** Localized label text, e.g. "LIVE" / "ЗАМОРОЖЕНО". */
  label: string;
}

/**
 * FROZEN/LIVE encoded by presence-of-color, not a second hue (see
 * tokens/color.css): live renders in Signal Amber, frozen/stabilized in
 * grayscale text tones. A dot + label, never color alone — the label text
 * itself always states the status (color-not-only accessibility rule).
 */
export function StatusPill({ status, label, className, ...props }: StatusPillProps) {
  const color = STATUS_COLOR[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-[color:var(--color-border)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.1em]",
        className,
      )}
      style={{ color }}
      {...props}
    >
      <span
        aria-hidden
        className="size-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
