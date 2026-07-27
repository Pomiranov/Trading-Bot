import type { ComponentPropsWithoutRef } from "react";
import { TONE_STYLE, type StatusTone } from "@/lib/strategy-status";
import { cn } from "@/lib/utils";

interface StatusPillProps extends Omit<ComponentPropsWithoutRef<"span">, "children"> {
  tone: StatusTone;
  label: string;
  /** Secondary qualifier, e.g. "read-only" or "sandbox by default". */
  detail?: string;
  /** Pulsing dot. Only for genuinely live telemetry — see the note below. */
  pulse?: boolean;
}

/**
 * Status pill with a coloured dot.
 *
 * Replaces five hand-rolled status indicators (broker "integrated" dot, footer
 * "systems operational" dot, hero live pill, hero window-chrome pill, CTA
 * badge).
 *
 * The status word is always rendered as text; the dot is redundant
 * reinforcement, never the sole carrier of meaning. That is what keeps this
 * readable in greyscale and for colour-blind users.
 *
 * On `pulse`: a pulsing dot reads as "this is live right now". Never use it
 * for static copy. The old header pill and the footer's "Systems operational"
 * dot both pulsed with no telemetry behind them — a claim the page could not
 * support.
 */
export function StatusPill({
  tone,
  label,
  detail,
  pulse = false,
  className,
  style,
  ...props
}: StatusPillProps) {
  const s = TONE_STYLE[tone];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-2.5 py-1 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase",
        className,
      )}
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.border}`, ...style }}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          pulse && "motion-safe:animate-[qf-blink_2s_ease-in-out_infinite]",
        )}
        style={{ backgroundColor: s.color }}
      />
      {label}
      {detail ? (
        <span className="font-normal tracking-normal normal-case opacity-80">· {detail}</span>
      ) : null}
    </span>
  );
}
