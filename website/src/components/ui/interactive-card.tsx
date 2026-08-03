"use client";

import type { ReactNode } from "react";
import { Surface } from "./surface";
import { track, type CtaTarget } from "@/lib/analytics/events";
import { cn } from "@/lib/utils";

interface InteractiveCardProps {
  href: string;
  /** Visible affordance text at the foot of the card. */
  label: string;
  analytics?: { target: CtaTarget; location: string };
  /** Route identity — "01", a glyph, a status chip. */
  eyebrow?: ReactNode;
  className?: string;
  children: ReactNode;
}

/**
 * A card whose *whole surface* is one link.
 *
 * ── The defect this fixes ──
 *
 * Measured on the live build: 32 cards carry the shared hover state, and four
 * of them contain a navigation link while still computing `cursor: default` —
 * all three Audience cards and the Access "Live" card. In each of those four
 * the card *is* the route selector, so the reader sees a card-sized target,
 * aims at it, and only the 12-word arrow link actually navigates. The rest of
 * the card swallows the click.
 *
 * ── The pattern, and why this one ──
 *
 * One `<a>` inside the card, carrying an `::after` overlay pinned to the card's
 * padding box. Consequences, all of them deliberate:
 *
 *   - one tab stop per card, not one per interactive-looking element
 *   - the focus ring lands on the *card*: `.card-premium` highlights on
 *     `:focus-within`, and `.card-route:has(a:focus-visible)` adds a real
 *     accent ring for keyboard focus (see globals.css) — the anchor itself
 *     stays `outline-none` so there are never two rings
 *   - body text is *not* selectable — the `::after` overlay captures the
 *     pointer across the whole surface, which is the price of the whole-card
 *     target. Stated plainly because an earlier version of this comment
 *     claimed otherwise: selection would require raising the text above the
 *     overlay, which would carve dead zones out of the click target
 *   - the markup stays valid: block content never sits inside the `<a>`, which
 *     wrapping the whole card in an anchor would force
 *   - `cursor: pointer` covers the whole surface via `.card-route`
 *
 * The alternative — an absolutely positioned transparent `<a>` layered over the
 * card — was rejected: it puts the accessible name at the top of the DOM order
 * with no relationship to the content underneath, so a screen reader announces
 * a bare link followed by unattached text.
 *
 * ── Hover ──
 *
 * The shared `.card-premium` state — lift, cold hairline, background, shadow and
 * the masked-conic rim — at `.card-route`'s hotter intensity. Route cards are the
 * one place on the page where a card means "go here" rather than "read this", and
 * they should not feel identical to a safety fact.
 *
 * That difference used to be a *mechanism*: route cards were the only cards with a
 * cold edge at all. Every card carries one now, so the distinction is intensity —
 * a hotter rim scale and a wider bloom, no extra layer. The blue is still a 1px
 * edge and a shadow, decorative geometry and never ink; see the doctrine in
 * tokens/color.css and the rim block in globals.css.
 */
export function InteractiveCard({
  href,
  label,
  analytics,
  eyebrow,
  className,
  children,
}: InteractiveCardProps) {
  return (
    <Surface
      className={cn("card-route group/route relative flex w-full flex-col gap-4 p-7", className)}
    >
      {eyebrow ? (
        <span
          aria-hidden="true"
          className="font-mono text-[length:var(--text-label)] tabular-nums tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase"
        >
          {eyebrow}
        </span>
      ) : null}

      {children}

      {/*
        The affordance. `::after` is what makes the whole card clickable, so the
        anchor itself only has to look like the call to action.

        No `focus-visible:outline` here on purpose: the ring belongs on the card
        (via .card-premium's :focus-within), and two rings — one on the card and
        one on a link stretched across it — read as a rendering bug.
      */}
      <a
        href={href}
        onClick={analytics ? () => track({ name: "cta_clicked", props: analytics }) : undefined}
        className="mt-auto inline-flex items-center gap-2 font-mono text-[length:var(--text-caption)] tracking-[0.1em] text-[color:var(--color-text-secondary)] uppercase no-underline transition-colors duration-[var(--duration-micro)] outline-none after:absolute after:inset-0 after:content-[''] group-hover/route:text-[color:var(--color-text-primary)] group-focus-within/route:text-[color:var(--color-text-primary)]"
      >
        {label}
        <span
          aria-hidden="true"
          className="transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-expo)] motion-safe:group-hover/route:translate-x-1 motion-safe:group-focus-within/route:translate-x-1"
        >
          →
        </span>
      </a>
    </Surface>
  );
}
