"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * A very slight pointer-follow for the hero instrument.
 *
 * ── Why this is a wrapper and not a prop on QAperture ──
 *
 * `QAperture` is server-rendered and has no client JS, which is a property
 * worth keeping: it is the hero, and it is an LCP candidate. Passing the panel
 * in as `children` keeps it a server component — only this ~40-line shell
 * hydrates, and the markup it wraps is still streamed as HTML.
 *
 * ── Restraint ──
 *
 * The maximum displacement is 7px (`.hero-tilt` in globals.css) across a full
 * sweep of the viewport, with a 500ms trailing transition. It should be
 * noticeable only as a sense that the panel is *aware* of the cursor, never as
 * an element that follows it. There is no rotation: tilting a panel containing
 * 11px mono labels resamples the text, and the labels are the content.
 *
 * ── Why the markup never branches on the preference ──
 *
 * Same rule as `motion/reveal.tsx`. The wrapper renders identically on the
 * server and on every client; the preference only decides whether the effect
 * *listener* is installed. Branching the element or its class on a media query
 * read during render is what produced the "all 32 cards stuck at opacity 0"
 * bug, and the fix there was to stop branding markup on preferences at all.
 *
 * Guards, in order: reduced motion, coarse pointer (a touch device has no
 * hover, and a stale transform would stick after a tap), and rAF coalescing so
 * a high-frequency pointer stream still writes at most once per frame.
 */
export function PointerTilt({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    if (reduce.matches || !fine.matches) return;

    let frame = 0;

    function onPointerMove(e: PointerEvent) {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const node = ref.current;
        if (!node) return;
        // Normalised to [-1, 1] against the viewport, not the element: the
        // panel should respond to where the cursor is on the *page*, so it
        // keeps drifting while the pointer is over the headline beside it.
        const x = (e.clientX / window.innerWidth) * 2 - 1;
        const y = (e.clientY / window.innerHeight) * 2 - 1;
        node.style.setProperty("--tilt-x", x.toFixed(3));
        node.style.setProperty("--tilt-y", y.toFixed(3));
      });
    }

    function reset() {
      const node = ref.current;
      if (!node) return;
      node.style.setProperty("--tilt-x", "0");
      node.style.setProperty("--tilt-y", "0");
    }

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    // The pointer leaving the document would otherwise freeze the panel
    // off-centre until it comes back.
    document.addEventListener("pointerleave", reset);

    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerleave", reset);
      reset();
    };
  }, []);

  return (
    <div ref={ref} className="hero-tilt">
      {children}
    </div>
  );
}
