"use client";

import type { VariantProps } from "class-variance-authority";
import { buttonVariants } from "./button";
import { Magnetic } from "./magnetic";
import { track, type CtaTarget } from "@/lib/analytics/events";
import { cn } from "@/lib/utils";

interface ButtonLinkProps
  extends Omit<React.ComponentPropsWithoutRef<"a">, "onClick">,
    VariantProps<typeof buttonVariants> {
  href: string;
  /** Fires cta_clicked when set. Omit for links that are not conversions. */
  analytics?: { target: CtaTarget; location: string };
  /** Desktop magnetic hover. Off by default — earn it. */
  magnetic?: boolean;
}

/**
 * The single CTA anchor.
 *
 * Replaces four separate implementations that each re-derived the same
 * behaviour — `nav/header-cta.tsx`, `hero/hero-cta.tsx`'s primary,
 * `pricing-section.tsx`'s bare `buttonVariants` anchor, and `mobile-nav.tsx`'s
 * hand-rolled gradient anchor — and with them four separate copies of the
 * tracking call and the reduced-motion fork.
 *
 * In-page navigation uses a plain <a href="#slug">, not next-intl's Link:
 * `typedRoutes` rejects hash-only hrefs, and LenisProvider already intercepts
 * these clicks to apply the smooth-scroll offset.
 */
export function ButtonLink({
  href,
  variant,
  size,
  analytics,
  magnetic = false,
  className,
  children,
  ...props
}: ButtonLinkProps) {
  const anchor = (
    <a
      href={href}
      className={cn(buttonVariants({ variant, size }), "no-underline", className)}
      onClick={analytics ? () => track({ name: "cta_clicked", props: analytics }) : undefined}
      {...props}
    >
      {children}
    </a>
  );

  return magnetic ? <Magnetic>{anchor}</Magnetic> : anchor;
}
