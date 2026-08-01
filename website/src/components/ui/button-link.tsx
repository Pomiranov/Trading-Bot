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
  /**
   * Classes for the `Magnetic` wrapper, and the only way to make a magnetic
   * button full-width.
   *
   * `Magnetic` renders an `inline-block` span, which is shrink-to-fit — so
   * `className="w-full"` on the anchor resolves against the wrapper's *content*
   * width and silently does nothing. The hero's primary CTA carried `w-full` for
   * exactly that reason and was never full-width; it merely looked like it while
   * its label happened to be long enough to fill the row. Ignored when
   * `magnetic` is false, where `w-full` on the anchor already works.
   */
  wrapperClassName?: string;
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
  wrapperClassName,
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

  return magnetic ? <Magnetic className={wrapperClassName}>{anchor}</Magnetic> : anchor;
}
