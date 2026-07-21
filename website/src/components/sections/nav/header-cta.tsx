"use client";

import { useRef } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "motion/react";
import { buttonVariants } from "@/components/ui/button";
import { track } from "@/lib/analytics/events";

const RADIUS = 10;
const SPRING = { stiffness: 300, damping: 20, mass: 0.5 };

export function HeaderCta({ label }: { label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, SPRING);
  const springY = useSpring(y, SPRING);

  const anchorClass = buttonVariants({ variant: "default", size: "sm" });

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

  if (reduce) {
    return (
      <a
        href="#cta-heading"
        className={anchorClass}
        style={{ textDecoration: "none" }}
        onClick={() => track({ name: "cta_clicked", props: { target: "beta_form", location: "nav" } })}
      >
        {label}
      </a>
    );
  }

  return (
    <motion.div
      ref={ref}
      className="inline-block"
      style={{ x: springX, y: springY }}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
    >
      <a
        href="#cta-heading"
        className={anchorClass}
        style={{ textDecoration: "none" }}
        onClick={() => track({ name: "cta_clicked", props: { target: "beta_form", location: "nav" } })}
      >
        {label}
      </a>
    </motion.div>
  );
}
