import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * ── The press, and why the numbers moved ──
 *
 * `active:scale-[0.97]` was a 3% collapse running on `transition-all` at
 * `--duration-base` (300ms). Both halves of that were wrong for a press.
 *
 * 3% on a 44px control is 1.3px of vertical travel *and* a resample of every
 * glyph in a letter-spaced mono label — measured, the label visibly softens on
 * the way down, which is the "дёргание текста" the brief rules out. 1.5% is the
 * smallest displacement that still registers as tactile and it lands inside the
 * 0.98–0.99 band the reference reads at.
 *
 * 300ms is worse than the scale. The whole value of an active state is that it
 * arrives in the same frame as the finger; at 300ms the button is still on its
 * way down when a fast click has already released. `--motion-fast` (120ms) on
 * `:active` only, so the press is immediate and the release still eases back over
 * `--motion-soft` — asymmetric on purpose, the same call the header's retraction
 * documents.
 *
 * `--motion-soft` (240ms) replaces `--duration-base` for the hover as well: an
 * edge lighting up is an acknowledgement and has to feel prompt. See the note on
 * the token in styles/tokens/motion.css.
 */
const buttonVariants = cva(
  "group/button btn-liquid-glass inline-flex shrink-0 items-center justify-center gap-1.5 rounded-[var(--radius-md)] border border-transparent font-mono text-[length:var(--text-caption)] uppercase tracking-[0.1em] whitespace-nowrap transition-all duration-[var(--motion-soft)] ease-[var(--ease-out-expo)] outline-none select-none focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[color:var(--color-accent)] active:duration-[var(--motion-fast)] motion-safe:active:scale-[0.985] disabled:pointer-events-none disabled:opacity-40 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // Solid white, not a gradient. Black-on-white is 20.4:1.
        // Hover darkens the fill slightly rather than brightening it — white is
        // already at the ceiling, so `brightness(1.08)` was a no-op.
        //
        // No `.btn-lens-dark`: a cold ring inside a white fill is either a grey
        // line or nothing. Its rim arrives from outside the fill instead, via
        // `--shadow-cta-hover` — see the note on that token in tokens/color.css.
        default: [
          "btn-lens-face",
          "bg-[color:var(--color-accent)]",
          "text-[color:var(--color-bg)] font-semibold",
          "hover:bg-[color:var(--color-accent-hover)] motion-safe:hover:-translate-y-px",
          "shadow-[var(--shadow-cta-rest)]",
          "hover:shadow-[var(--shadow-cta-hover)]",
        ].join(" "),
        // Dark-faced, so this is where the reference's cold rim and travelling
        // arc actually live. `hover:shadow-[var(--shadow-cta-hover)]` was the
        // *white* CTA's bloom on a transparent button — a white glow around a
        // near-black control, which is the smear the palette doctrine removed
        // from the cards. It carries `--btn-glow-hover` now: a 3px cold shelf and
        // a 16px bloom, sized to the rim rather than to a filled pill.
        outline: [
          "btn-lens-face btn-lens-dark",
          "bg-[color:var(--color-fill-subtle)]",
          "border-[color:var(--color-border-strong)]",
          "text-[color:var(--color-text-primary)]",
          "hover:border-[color:var(--color-highlight-border)] hover:bg-[color:var(--color-highlight-bg)] motion-safe:hover:-translate-y-px",
          "hover:shadow-[var(--btn-glow-hover)]",
        ].join(" "),
        secondary: [
          "btn-lens-face btn-lens-dark",
          "bg-[color:var(--color-surface)]",
          "text-[color:var(--color-text-secondary)]",
          "border-[color:var(--color-border)]",
          "hover:bg-[color:var(--color-panel)] hover:text-[color:var(--color-text-primary)]",
          "hover:shadow-[var(--btn-glow-hover)]",
        ].join(" "),
        // No lens: `ghost` has no face at rest, so there is no edge to light and
        // nothing for a rim to sit on. It stays a text target that gains a fill.
        ghost: [
          "text-[color:var(--color-text-secondary)]",
          "hover:bg-[color:var(--color-highlight-bg)] hover:text-[color:var(--color-text-primary)]",
        ].join(" "),
        destructive:
          "btn-lens-face bg-[color:var(--color-danger-dim)] text-[color:var(--color-danger)] hover:bg-[rgba(255,77,109,0.26)]",
        link: "text-[color:var(--color-text-primary)] underline-offset-4 hover:underline",
      },
      size: {
        // Heights meet the WCAG 2.2 24px target-size floor with room to spare.
        default: "h-11 px-5",
        sm: "h-9 px-4 text-[length:var(--text-label)]",
        lg: "h-12 px-8",
        icon: "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
