import type { ComponentPropsWithoutRef, CSSProperties } from "react";
import { TONE_STYLE, type StatusTone } from "@/lib/strategy-status";
import { SignalDot } from "@/components/ui/signal-dot";
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
  /**
   * The closed-testing beacon: a white core in a cold halo, breathing slowly.
   *
   * Distinct from `pulse`, and the distinction is the honesty boundary rather
   * than a style choice. `pulse` depicts a *live system* and needs telemetry (or
   * an explicitly labelled demo) behind it. `beacon` marks the *programme's*
   * state — the product is in closed testing — which is a fact about how access
   * is granted, stated in words in the label right beside it.
   *
   * Owner direction is that every "closed testing" badge on the site carries it.
   * See `ui/signal-dot.tsx`. Mutually exclusive with `pulse`; `pulse` wins if
   * both are somehow set, since a live claim is the stronger assertion and
   * should not be silently downgraded.
   */
  beacon?: boolean;
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
  beacon = false,
  className,
  style,
  ...props
}: StatusChipProps) {
  const s = TONE_STYLE[tone];
  const outline = variant === "outline";
  // A live claim outranks a programme marker, so it is never downgraded.
  const isBeacon = beacon && !pulse;

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
      {isBeacon ? (
        // `SignalDot` owns its own well, rim and halo — passing the tone colour
        // through would defeat the point, since the beacon's interior is cold on
        // every tone by design (see the note in that file).
        <SignalDot />
      ) : (
        <span
          aria-hidden="true"
          className={cn(
            "size-2 shrink-0 rounded-[var(--radius-full)]",
            /*
              ── Which dots are lenses, and which are not ──

              `.signal-lens` gives a dot the page's shared marker construction: a
              well lit from above, a conic rim masked to a 1px annulus, volume.
              See the `--lens-*` block in styles/tokens/color.css.

              Two of the three cases here take it:

                • `pulse` — the live dot, on the cold lens, plus `.status-dot-live`
                  for the sonar ring. `relative` comes from `.signal-lens`, which
                  the expanding ring needs as its containing block; it is out of
                  flow, so turning the pulse on still cannot move the chip.
                • solid — the tone lens, which derives its well and rim from
                  `--lens-tone` with `color-mix`. Hue is never normalised: green
                  still means confirmed and red still means risk.

              `outline` does not, and that is the one deliberate exception. It
              exists to separate a partially-working integration from an
              unimplemented stub (see the `variant` prop above), and it does that
              by being *hollow*. A lens has an interior by definition, so filling
              the outline dot with one would erase the distinction the variant was
              added for.
            */
            pulse && "signal-lens status-dot-live",
            !pulse && !outline && "signal-lens signal-lens--tone",
          )}
          style={
            outline
              ? { border: `1px solid ${s.color}` }
              : // `backgroundColor` is the floor, not the paint: `.signal-lens`
                // overrides it with a gradient wherever `color-mix` resolves. On
                // an engine that drops the mix, this flat tone fill is what shows
                // — which is exactly the appearance the dot had before the lens.
                // The live dot's floor is white rather than its tone, because a
                // grey core inside a cold halo reads as smudged rather than lit.
                {
                  backgroundColor: pulse ? "var(--color-text-primary)" : s.color,
                  ...({ "--lens-tone": s.color } as CSSProperties),
                }
          }
        />
      )}
      {label}
      {detail ? (
        <span className="font-normal tracking-normal normal-case opacity-80">· {detail}</span>
      ) : null}
    </span>
  );
}
