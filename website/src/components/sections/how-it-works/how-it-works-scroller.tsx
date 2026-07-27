"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useReducedMotion } from "motion/react";

gsap.registerPlugin(ScrollTrigger);

/**
 * Pinned horizontal-pan track, desktop only.
 *
 * Cards stagger in cinematically on enter, then the track pans horizontally
 * as the user scrolls. The section fades out gracefully rather than snapping
 * away — no abrupt release, no excessive scroll distance.
 *
 * Cards are ALWAYS visible (natural state). GSAP only adds a visual
 * enhancement — if the trigger doesn't fire, nothing breaks.
 *
 * Reduced-motion: standard overflow-x scroll, no GSAP at all.
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

          const cards = Array.from(track.querySelectorAll<HTMLElement>("li"));

          // Cinematic stagger: animate FROM hidden state so cards are always
          // visible by default — immediateRender: false prevents the from-state
          // from being applied until the trigger actually fires.
          ScrollTrigger.create({
            trigger: wrap,
            start: "top 82%",
            once: true,
            onEnter: () => {
              gsap.from(cards, {
                autoAlpha: 0,
                y: 20,
                duration: 0.65,
                stagger: 0.08,
                ease: "power3.out",
                immediateRender: false,
              });
            },
          });

          // Horizontal pan — faster scrub, graceful exit fade
          gsap.to(track, {
            x: -distance,
            ease: "none",
            scrollTrigger: {
              trigger: wrap,
              start: "top top",
              end: () => `+=${distance}`,
              pin: true,
              pinSpacing: true,
              scrub: 0.9,
              invalidateOnRefresh: true,
              onUpdate(self) {
                // Begin fade at 80% progress, complete at 100%
                if (self.progress > 0.80) {
                  const p = (self.progress - 0.80) / 0.20;
                  wrap!.style.opacity = String(Math.max(0, 1 - p * p));
                } else {
                  wrap!.style.opacity = "1";
                }
              },
            },
          });
        },
      });
    }, wrapRef);

    return () => ctx.revert();
  }, [reduce]);

  return (
    <div ref={wrapRef} className="relative hidden md:block" style={{ zIndex: 1 }}>
      <ol
        ref={trackRef}
        className="flex gap-6 overflow-x-auto px-[var(--space-page-x)] pb-4 [scroll-snap-type:x_mandatory]"
        style={{ willChange: "transform" }}
      >
        {children}
      </ol>
    </div>
  );
}
