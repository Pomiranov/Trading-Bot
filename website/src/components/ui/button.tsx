import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group/button btn-liquid-glass inline-flex shrink-0 items-center justify-center gap-1.5 rounded-[var(--radius-md)] border border-transparent font-mono text-[13px] uppercase tracking-[0.1em] whitespace-nowrap transition-all duration-300 outline-none select-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: [
          "bg-[linear-gradient(135deg,#ff8a1e_0%,#d96a12_100%)]",
          "text-[#040404] font-semibold",
          "shadow-[0_0_0_1px_rgba(255,138,30,0.25),0_4px_20px_rgba(255,138,30,0.18),inset_0_1px_0_rgba(255,255,255,0.18)]",
          "hover:shadow-[0_0_0_1px_rgba(255,138,30,0.45),0_8px_32px_rgba(255,138,30,0.28),inset_0_1px_0_rgba(255,255,255,0.22)]",
          "hover:brightness-[1.08] hover:-translate-y-px",
        ].join(" "),
        outline: [
          "bg-[rgba(255,255,255,0.03)] backdrop-blur-[12px]",
          "border-[rgba(255,255,255,0.1)]",
          "text-[color:var(--color-text-primary)]",
          "shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]",
          "hover:bg-[rgba(255,255,255,0.06)] hover:border-[rgba(255,138,30,0.2)] hover:-translate-y-px",
          "hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.07),0_0_16px_rgba(255,138,30,0.07)]",
        ].join(" "),
        secondary: [
          "bg-[color:var(--color-surface)]",
          "text-[color:var(--color-text-secondary)]",
          "border-[color:var(--color-border)]",
          "hover:bg-[color:var(--color-panel)] hover:text-[color:var(--color-text-primary)]",
        ].join(" "),
        ghost: [
          "text-[color:var(--color-text-secondary)]",
          "hover:bg-[rgba(255,255,255,0.05)] hover:text-[color:var(--color-text-primary)]",
        ].join(" "),
        destructive: "bg-[color:var(--color-danger-dim)] text-[color:var(--color-danger)] hover:bg-[rgba(229,72,77,0.25)]",
        link: "text-[color:var(--color-accent)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-5",
        sm: "h-8 px-3.5 text-[11px]",
        lg: "h-12 px-8 text-[13px]",
        icon: "size-10",
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
