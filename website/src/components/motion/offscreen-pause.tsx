"use client";

import { useEffect, useRef } from "react";

/**
 * Parks a section's decorative CSS loops while it is off-screen.
 *
 * The hero already does this: `pointer-tilt.tsx` toggles `data-qf-offscreen`
 * on its wrapper and the doubled-attribute rule in globals.css pauses every
 * descendant animation. This component is that observer extracted for sections
 * that have no client shell of their own — today `#how-it-works`, whose seven
 * pipeline nodes each run a 24s conic rim sweep. A registered-custom-property
 * animation repaints its gradient every frame on the main thread, so seven of
 * them running behind a scrolled-away section is pure cost — and, like the
 * aperture before it, it kept `document.getAnimations()` from ever settling,
 * which is what makes automated captures of this page hang.
 *
 * Renders one `hidden` <span> (display: none — no box, no grid item) and
 * attaches the observer to its *parent*, so a server component can adopt the
 * behaviour by dropping this in as a child instead of re-wrapping its markup.
 * `animation-play-state: paused` holds phase: scrolling back resumes the
 * sweeps where they were rather than snapping them to 0%.
 */
export function OffscreenPause() {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const host = ref.current?.parentElement;
    if (!host || typeof IntersectionObserver === "undefined") return;

    const io = new IntersectionObserver(
      ([entry]) => {
        host.toggleAttribute("data-qf-offscreen", !entry.isIntersecting);
      },
      // Resumes just before the section is visible, so it is never caught
      // frozen — the same 200px margin the hero's observer uses.
      { rootMargin: "200px 0px" },
    );

    io.observe(host);
    return () => {
      io.disconnect();
      host.removeAttribute("data-qf-offscreen");
    };
  }, []);

  return <span ref={ref} hidden aria-hidden="true" />;
}
