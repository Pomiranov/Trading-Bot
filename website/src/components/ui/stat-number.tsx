import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

interface StatNumberProps extends Omit<ComponentPropsWithoutRef<"div">, "children"> {
  value: number | string;
  label?: string;
  prefix?: string;
  suffix?: string;
  locale?: string;
  accent?: boolean;
}

export function StatNumber({
  value,
  label,
  prefix,
  suffix,
  locale = "en",
  accent = false,
  className,
  ...props
}: StatNumberProps) {
  const formatted =
    typeof value === "number" ? new Intl.NumberFormat(locale).format(value) : value;

  return (
    <div className={cn("flex flex-col gap-1.5", className)} {...props}>
      <p
        className="font-mono tabular-nums leading-none"
        style={{
          fontSize: "clamp(1.75rem, 3vw, 2.75rem)",
          fontWeight: 600,
          letterSpacing: "-0.04em",
          color: accent ? "var(--color-accent)" : "var(--color-text-primary)",
          ...(accent && {
            textShadow: "0 0 30px rgba(255,138,30,0.3)",
          }),
        }}
      >
        {prefix}
        {formatted}
        {suffix}
      </p>
      {label ? (
        <p
          className="font-mono uppercase"
          style={{
            fontSize: "10px",
            letterSpacing: "0.16em",
            color: "rgba(255,255,255,0.35)",
          }}
        >
          {label}
        </p>
      ) : null}
    </div>
  );
}
