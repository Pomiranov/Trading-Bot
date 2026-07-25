import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export type StrategyStatus = "live" | "frozen" | "stabilized";

const STATUS_STYLES: Record<StrategyStatus, { color: string; bg: string; border: string; glow?: string }> = {
  live: {
    color: "var(--color-accent)",
    bg: "rgba(255,138,30,0.08)",
    border: "rgba(255,138,30,0.2)",
    glow: "0 0 8px rgba(255,138,30,0.2)",
  },
  frozen: {
    color: "rgba(255,255,255,0.32)",
    bg: "rgba(255,255,255,0.04)",
    border: "rgba(255,255,255,0.08)",
  },
  stabilized: {
    color: "rgba(255,255,255,0.55)",
    bg: "rgba(255,255,255,0.05)",
    border: "rgba(255,255,255,0.1)",
  },
};

interface StatusPillProps extends Omit<ComponentPropsWithoutRef<"span">, "children"> {
  status: StrategyStatus;
  label: string;
}

export function StatusPill({ status, label, className, style, ...props }: StatusPillProps) {
  const s = STATUS_STYLES[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.1em]",
        className,
      )}
      style={{
        color: s.color,
        background: s.bg,
        border: `1px solid ${s.border}`,
        boxShadow: s.glow,
        ...style,
      }}
      {...props}
    >
      <span
        aria-hidden
        className="size-1.5 rounded-full"
        style={{
          backgroundColor: s.color,
          boxShadow: s.glow ? `0 0 4px ${s.color}` : undefined,
        }}
      />
      {label}
    </span>
  );
}
