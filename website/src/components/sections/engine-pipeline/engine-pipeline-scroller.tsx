"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useReducedMotion } from "motion/react";

gsap.registerPlugin(ScrollTrigger);

/**
 * Pinned horizontal-pan track, desktop only (taste-skill canonical
 * skeleton, Section 5.B) — gated by ScrollTrigger.matchMedia so the pin
 * logic is entirely absent below md, not just visually hidden (matters
 * for the mobile performance budget and avoids a pinned-but-invisible
 * container eating scroll). Reduced motion skips GSAP setup entirely;
 * the track still renders as a plain scrollable row (overflow-x-auto in
 * the className below), just without the pin/scrub choreography.
 */
export function EnginePipelineScroller({ children }: { children: ReactNode }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLOListElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (reduce || !wrapRef.current || !trackRef.current) return;

    const ctx = gsap.context(() => {
      ScrollTrigger.matchMedia({
        "(min-width: 768px)": () => {
          const track = trackRef.current;
          const wrap = wrapRef.current;
          if (!track || !wrap) return;

          const distance = track.scrollWidth - wrap.clientWidth;
          if (distance <= 0) return;

          gsap.to(track, {
            x: -distance,
            ease: "none",
            scrollTrigger: {
              trigger: wrap,
              start: "top top",
              end: () => `+=${distance}`,
              pin: true,
              scrub: 1,
              invalidateOnRefresh: true,
            },
          });
        },
      });
    }, wrapRef);

    return () => ctx.revert();
  }, [reduce]);

  return (
    <div ref={wrapRef} className="relative hidden md:block">
      <ol
        ref={trackRef}
        className="flex gap-6 overflow-x-auto px-[var(--space-page-x)] pb-4 [scroll-snap-type:x_mandatory]"
      >
        {children}
      </ol>
    </div>
  );
}
