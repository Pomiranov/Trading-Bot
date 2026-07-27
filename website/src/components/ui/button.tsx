import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group/button btn-liquid-glass inline-flex shrink-0 items-center justify-center gap-1.5 rounded-[var(--radius-md)] border border-transparent font-mono text-[length:var(--text-caption)] uppercase tracking-[0.1em] whitespace-nowrap transition-all duration-[var(--duration-base)] ease-[var(--ease-out-expo)] outline-none select-none focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[color:var(--color-accent)] active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        // Solid white, not a gradient. Black-on-white is 20.4:1.
        // Hover darkens the fill slightly rather than brightening it — white is
        // already at the ceiling, so `brightness(1.08)` was a no-op.
        default: [
          "bg-[color:var(--color-accent)]",
          "text-[color:var(--color-bg)] font-semibold",
          "hover:bg-[color:var(--color-accent-hover)] motion-safe:hover:-translate-y-px",
          "shadow-[var(--shadow-cta-rest)]",
          "hover:shadow-[var(--shadow-cta-hover)]",
        ].join(" "),
        outline: [
          "bg-[color:var(--color-fill-subtle)]",
          "border-[color:var(--color-border-strong)]",
          "text-[color:var(--color-text-primary)]",
          "hover:border-[color:var(--color-highlight-border)] hover:bg-[color:var(--color-highlight-bg)] motion-safe:hover:-translate-y-px",
          "hover:shadow-[var(--shadow-cta-hover)]",
        ].join(" "),
        secondary: [
          "bg-[color:var(--color-surface)]",
          "text-[color:var(--color-text-secondary)]",
          "border-[color:var(--color-border)]",
          "hover:bg-[color:var(--color-panel)] hover:text-[color:var(--color-text-primary)]",
        ].join(" "),
        ghost: [
          "text-[color:var(--color-text-secondary)]",
          "hover:bg-[color:var(--color-highlight-bg)] hover:text-[color:var(--color-text-primary)]",
        ].join(" "),
        destructive:
          "bg-[color:var(--color-danger-dim)] text-[color:var(--color-danger)] hover:bg-[rgba(255,77,109,0.26)]",
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
