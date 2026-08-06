import type { ComponentPropsWithoutRef, CSSProperties } from "react";
import { cn } from "@/lib/utils";

export type SurfaceVariant = "flat" | "raised" | "glass" | "featured";

const VARIANTS: Record<SurfaceVariant, string> = {
  /**
   * The default. A precise, calm panel: hairline border, solid surface, no
   * blur. Most cards should be this — glass is a material for floating over
   * something, and most cards float over nothing.
   */
  flat: "border border-[color:var(--color-border)]",

  /** Slightly lifted from the page — grouped content, nested panels. */
  raised: "border border-[color:var(--color-border)]",

  /** HUD over imagery only. */
  glass: "glass-premium",

  /** The one emphasised tier (pricing). Gradient border via mask-composite. */
  featured: "glass-premium-featured",
};

/**
 * Resting and hover background per variant, handed to `.card-premium` as custom
 * properties. Glass and featured own their own background, so they opt out.
 */
const VARIANT_BG: Partial<Record<SurfaceVariant, { rest: string; hover: string }>> = {
  flat: { rest: "var(--color-surface)", hover: "var(--color-panel)" },
  raised: { rest: "var(--color-panel)", hover: "var(--color-panel-raised)" },
};

/**
 * Card padding, so sections stop each picking their own.
 *
 * Census before this existed: `p-6` ×5, `p-7` ×18, `p-8` ×2, `p-7 md:p-8` ×3 —
 * four paddings for one kind of object, none of them chosen for a reason.
 */
const PADDING = {
  none: "",
  sm: "p-5",
  md: "p-7",
  lg: "p-7 md:p-9",
} as const;

interface SurfaceProps extends ComponentPropsWithoutRef<"div"> {
  variant?: SurfaceVariant;
  padding?: keyof typeof PADDING;
  /**
   * Opts the card into the shared premium hover/focus state: border highlight,
   * a lift, a soft white glow and a slightly lighter background.
   *
   * Defaults to `true`. The owner's direction is that *every* card on the
   * landing page highlights, so the primitive defaults to highlighting and a
   * surface that genuinely must stay inert passes `interactive={false}`.
   * `cursor: pointer` is deliberately NOT part of this — a card is only a
   * pointer target when it actually navigates, so that belongs to the caller.
   */
  interactive?: boolean;
}

/**
 * The single elevated-surface primitive, and the page's card primitive.
 *
 * This replaces eleven separate implementations: `ui/panel.tsx`,
 * `ui/glass-panel.tsx`, the raw `.glass-premium` class applied inline, and
 * nine hand-rolled blocks — two of which re-implemented the exact
 * `mask-composite: exclude` gradient border that `globals.css` already ships.
 *
 * Glass is deliberately not the default. The previous system reached for
 * backdrop-blur on ordinary cards sitting on a flat black page, which costs a
 * compositing layer to simulate depth against nothing.
 *
 * The hover/focus rules live in `.card-premium` in globals.css rather than in
 * Tailwind variants here, because they need `@media (hover: hover)` and
 * `:focus-within` — neither of which composes cleanly as a utility string, and
 * the hover-sticking-after-tap bug on touch is worth the one extra class.
 */
export function Surface({
  variant = "flat",
  interactive = true,
  padding = "none",
  className,
  style,
  ...props
}: SurfaceProps) {
  const bg = VARIANT_BG[variant];
  const usesCardPrimitive = bg !== undefined;

  return (
    <div
      data-slot="surface"
      className={cn(
        "rounded-[var(--radius-lg)]",
        PADDING[padding],
        VARIANTS[variant],
        usesCardPrimitive
          ? interactive
            ? "card-premium"
            : // Same resting paint, no state change.
              "bg-[color:var(--card-bg)]"
          : null,
        className,
      )}
      style={
        usesCardPrimitive
          ? ({
              "--card-bg": bg.rest,
              "--card-bg-hover": interactive ? bg.hover : bg.rest,
              ...style,
            } as CSSProperties)
          : style
      }
      {...props}
    />
  );
}
