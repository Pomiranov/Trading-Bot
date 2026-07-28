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
   * Live-signal dot: a white core inside a cold halo, with a ring expanding out
   * of it. See `.status-dot-live` in globals.css for the geometry and for why
   * only the *light* around the dot is cold blue.
   *
   * Reserved for a genuine live state, or for the depiction of one inside an
   * explicitly labelled demo. The footer's old "Systems operational" pulse had
   * no telemetry behind it — it was a live-status claim the page could not
   * support — and that is still the line. Do not put this on static copy.
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
      {/* `relative` only on the live variant — the expanding ring is an
          absolutely-positioned pseudo-element and needs this as its containing
          block. It is out of flow, so the chip's box is identical in both
          variants and turning the pulse on cannot move anything. */}
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 shrink-0 rounded-[var(--radius-full)]",
          pulse && "status-dot-live relative",
        )}
        style={
          outline
            ? { border: `1px solid ${s.color}` }
            : // The live dot's core is white, not the tone colour: at 1.5 units
              // across, a grey core inside a cold halo reads as smudged rather
              // than as lit. The tone still carries in the chip's border, fill
              // and text, and the label states the status in words regardless.
              { backgroundColor: pulse ? "var(--color-text-primary)" : s.color }
        }
      />
      {label}
      {detail ? (
        <span className="font-normal tracking-normal normal-case opacity-80">· {detail}</span>
      ) : null}
    </span>
  );
}
