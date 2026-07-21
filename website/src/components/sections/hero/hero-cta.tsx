"use client";

import { useRef } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "motion/react";
import { buttonVariants } from "@/components/ui/button";
import { track } from "@/lib/analytics/events";

const RADIUS = 14;
const SPRING = { stiffness: 280, damping: 20, mass: 0.5 };

export function HeroCta({
  label,
  secondaryLabel,
}: {
  label: string;
  secondaryLabel: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, SPRING);
  const springY = useSpring(y, SPRING);

  const primaryClass = buttonVariants({ variant: "default", size: "lg" });

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const relX = (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
    const relY = (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
    x.set(Math.max(-1, Math.min(1, relX)) * RADIUS);
    y.set(Math.max(-1, Math.min(1, relY)) * RADIUS);
  }

  function onPointerLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <div className="flex flex-wrap items-center gap-5 pt-1">
      {reduce ? (
        <a
          href="#cta-heading"
          className={primaryClass}
          style={{ textDecoration: "none" }}
          onClick={() => track({ name: "cta_clicked", props: { target: "beta_form", location: "hero" } })}
        >
          {label}
        </a>
      ) : (
        <motion.div
          ref={ref}
          className="inline-block"
          style={{ x: springX, y: springY }}
          onPointerMove={onPointerMove}
          onPointerLeave={onPointerLeave}
        >
          <a
            href="#cta-heading"
            className={primaryClass}
            style={{ textDecoration: "none" }}
            onClick={() => track({ name: "cta_clicked", props: { target: "beta_form", location: "hero" } })}
          >
            {label}
          </a>
        </motion.div>
      )}

      <a
        href="#engine-pipeline-heading"
        className="group inline-flex items-center gap-2 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-200"
        style={{ color: "rgba(255,255,255,0.35)", textDecoration: "none" }}
        onMouseEnter={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.65)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.35)"; }}
        onClick={() => track({ name: "cta_clicked", props: { target: "explore", location: "hero" } })}
      >
        {secondaryLabel}
        <span
          className="transition-transform duration-200 group-hover:translate-x-1"
          aria-hidden="true"
        >
          →
        </span>
      </a>
    </div>
  );
}
