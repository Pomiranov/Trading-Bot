"use client";

import { useEffect, useState } from "react";

/**
 * Which section currently occupies the viewport, for the header's active
 * underline.
 *
 * On a 13 000px single page this is the most useful nav affordance available,
 * and the header had none: all five links rendered identically at every scroll
 * position.
 *
 * ── IntersectionObserver, not a scroll listener ──
 *
 * Non-negotiable. Nothing on this page may read or write scroll position except
 * `motion/scroll-driver.ts`. A `scroll` handler here — even a passive,
 * rAF-throttled one calling `getBoundingClientRect` — puts a second reader on
 * the same value Lenis is animating, which is the exact coupling that produced
 * the backward-scroll bug. An observer is push-based and never asks where the
 * page is.
 *
 * ── The rootMargin ──
 *
 * `-45% 0px -50% 0px` collapses the viewport to a thin band just above the
 * middle. A section is "active" when it crosses that band, which is what a
 * reader intuits: the thing you are looking at, not the thing that has merely
 * begun to appear. Without it, a tall section entering at the bottom would win
 * over the short one filling the screen.
 *
 * Returns `null` until the first intersection, so nothing is underlined while
 * the hero is on screen — the hero is not a nav target and highlighting the
 * first link there would be a lie.
 */
export function useActiveSection(ids: readonly string[]): string | null {
  const [active, setActive] = useState<string | null>(null);

  /**
   * The dependency is the *contents* of `ids`, not the array identity.
   *
   * Callers build this list inline (`links.map(l => l.href.slice(1))`), so the
   * array is a fresh reference on every render. Depending on the array itself
   * gives: effect runs → observer fires → setActive → re-render → new array →
   * effect runs again, forever. That is not a subtle perf issue — it pegs the
   * renderer hard enough that the tab stops producing frames, which is exactly
   * how it was found.
   */
  const key = ids.join(",");

  useEffect(() => {
    const list = key ? key.split(",") : [];
    const elements = list
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);

    if (elements.length === 0) return;

    // Observer callbacks only report *changes*, so the running set has to be
    // kept here — otherwise scrolling out of the band clears the underline
    // until the next section arrives, and the header flickers.
    const visible = new Set<string>();

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        // Document order, so overlapping bands resolve to the earlier section
        // rather than to whichever one the observer happened to report last.
        const first = list.find((id) => visible.has(id)) ?? null;
        setActive((prev) => (prev === first ? prev : first));
      },
      { rootMargin: "-45% 0px -50% 0px", threshold: 0 },
    );

    elements.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [key]);

  return active;
}
