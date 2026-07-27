import type { ComponentPropsWithoutRef } from "react";
import { TONE_STYLE, type StatusTone } from "@/lib/strategy-status";
import { cn } from "@/lib/utils";

interface StatusChipProps extends Omit<ComponentPropsWithoutRef<"span">, "children"> {
  tone: StatusTone;
  /** Always rendered. The dot is redundant reinforcement, never the meaning. */
  label: string;
  /** Secondary qualifier, e.g. "sandbox by default". */
  detail?: string;
  /**
   * `outline` is the fix for the Bybit/Finam collision.
   *
   * Both map to the `muted` tone, correctly — neither is production-ready, and
   * tinting one of them green would be a claim the adapter cannot support. But
   * that made a *partially working* integration and an *unimplemented stub*
   * chromatically identical, and status is the entire information content of
   * the brokers section. `solid` vs `outline` separates them without either one
   * reading as shipped.
   */
  variant?: "solid" | "outline";
  /**
   * Pulsing dot. Reserved for genuinely live telemetry.
   *
   * The footer's old "Systems operational" pulse had no telemetry behind it —
   * it was a live-status claim the page could not support. Do not reintroduce
   * it for static copy.
   */
  pulse?: boolean;
}

/**
 * Status chip with a coloured dot and an always-present text label.
 *
 * Supersedes `ui/status-pill.tsx`, adding only `variant`. The status word is
 * always text, so the page survives greyscale and colour-blindness and no
 * meaning is carried by hue alone.
 */
export function StatusChip({
  tone,
  label,
  detail,
  variant = "solid",
  pulse = false,
  className,
  style,
  ...props
}: StatusChipProps) {
  const s = TONE_STYLE[tone];
  const outline = variant === "outline";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-full)] px-2.5 py-1 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase",
        className,
      )}
      style={{
        color: s.color,
        // Outline drops the fill and keeps the border, so it reads as one step
        // *behind* the solid chip rather than as a different state entirely.
        background: outline ? "transparent" : s.bg,
        border: `1px ${outline ? "dashed" : "solid"} ${s.border}`,
        ...style,
      }}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 shrink-0 rounded-[var(--radius-full)]",
          pulse && "motion-safe:animate-[qf-blink_2s_ease-in-out_infinite]",
        )}
        style={
          outline
            ? { border: `1px solid ${s.color}` }
            : { backgroundColor: s.color }
        }
      />
      {label}
      {detail ? (
        <span className="font-normal tracking-normal normal-case opacity-80">· {detail}</span>
      ) : null}
    </span>
  );
}
