"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Gives the header its two states: transparent over the hero, then a compact
 * glass pill once the page has moved.
 *
 * The old header was fully opaque `rgba(6,6,7,0.86)` from pixel zero, so the
 * hero never got a clean top edge — the first thing a visitor saw was a bar
 * sitting on the artwork. The reference shows the pill materialising only after
 * the page starts moving, which is the device Apple and OpenAI both use.
 *
 * ── Why an IntersectionObserver on a sentinel, not a scroll listener ──
 *
 * Same rule as everywhere else on this page: nothing may read scroll position
 * except `motion/scroll-driver.ts`. A `scroll` handler here would put a second
 * reader on the value Lenis is animating, which is the coupling that produced
 * the backward-scroll bug.
 *
 * So instead a zero-height sentinel is placed at the top of the document, and
 * the header goes compact exactly when that sentinel leaves the viewport. That
 * is a push-based signal, it costs nothing per frame, and it never asks the
 * document where it is. `rootMargin` moves the trigger to the reference's
 * ~100px rather than firing at 1px.
 *
 * ── The height must not change ──
 *
 * `NAV_OFFSET` (104) and the `scroll-margin-top` in globals.css are a single
 * number shared by the anchor interceptor and the no-JS path. If the header's
 * height changed between states, no single offset could be correct for both,
 * and every deep link would land wrong in one of them. So the two states differ
 * in background, border, blur and shadow — paint only. The pill's box is
 * identical in both, and the CLS contribution is zero.
 */
export function HeaderShell({ children }: { children: ReactNode }) {
  const [compact, setCompact] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;

    const io = new IntersectionObserver(
      // The sentinel sits at y=100px in the document. While it is on screen the
      // page has not scrolled past 100px, so the header stays transparent; once
      // it leaves through the top, the header goes compact.
      ([entry]) => setCompact(!entry.isIntersecting),
      { threshold: 0 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <>
      {/*
        Observer target, parked at the scroll depth where the header should
        change — *not* at y=0 with a negative rootMargin. That was the first
        attempt and it is inverted: a -100px top margin also excludes the top
        100px of the viewport, so a sentinel at y=0 reads as "not intersecting"
        while the page is still at the top, and the header rendered compact
        over the hero — the exact thing this state exists to avoid.

        Absolute and 1px, so it takes no space and cannot affect layout.
      */}
      <div
        ref={sentinel}
        aria-hidden="true"
        className="pointer-events-none absolute top-[100px] left-0 h-px w-px"
      />

      <header
        data-compact={compact}
        className="fixed inset-x-0 top-0 z-[var(--z-nav)] flex justify-center px-[var(--space-page-x)] pt-4"
      >
        {/* Fades the page to black above the pill so content dissolves on
            approach rather than sliding under a hard edge. Only meaningful
            once the header is compact — over the hero there is nothing to
            dissolve, and the scrim would darken the artwork. */}
        <div
          aria-hidden="true"
          className={cn(
            "nav-scrim transition-opacity duration-[var(--duration-base)] ease-[var(--ease-out-expo)]",
            compact ? "opacity-100" : "opacity-0",
          )}
        />

        <div
          className={cn(
            "relative flex w-full max-w-[var(--space-content-max)] items-center justify-between gap-6 rounded-[var(--radius-xl)] px-5 py-3",
            "transition-[background-color,border-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-expo)]",
            compact
              ? "nav-glass border border-[color:var(--color-border)] shadow-[var(--shadow-panel)]"
              : "border border-transparent bg-transparent",
          )}
        >
          {children}
        </div>
      </header>
    </>
  );
}
