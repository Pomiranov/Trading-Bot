import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

interface StatNumberProps extends Omit<ComponentPropsWithoutRef<"div">, "children"> {
  value: number | string;
  label?: string;
  prefix?: string;
  suffix?: string;
  /** BCP-47 locale for number formatting; defaults to the ambient page locale via the caller. */
  locale?: string;
}

/**
 * Static numeric display for now — tabular figures, mono, locale-aware
 * formatting. Count-up-on-scroll motion is wired in Phase 4 (Framer
 * useMotionValue), this component's DOM shape stays the same then.
 */
export function StatNumber({
  value,
  label,
  prefix,
  suffix,
  locale = "en",
  className,
  ...props
}: StatNumberProps) {
  const formatted =
    typeof value === "number" ? new Intl.NumberFormat(locale).format(value) : value;

  return (
    <div className={cn("flex flex-col gap-1", className)} {...props}>
      <p className="font-mono text-[clamp(1.5rem,3vw,2.5rem)] tabular-nums leading-none text-[color:var(--color-text-primary)]">
        {prefix}
        {formatted}
        {suffix}
      </p>
      {label ? (
        <p className="font-mono text-[length:var(--text-label)] uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
          {label}
        </p>
      ) : null}
    </div>
  );
}
