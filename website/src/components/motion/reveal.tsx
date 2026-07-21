"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";

interface RevealProps extends HTMLMotionProps<"div"> {
  /** Stagger index — desyncs siblings by 60ms each (taste-skill spec). */
  index?: number;
}

/**
 * Scroll-into-view entrance for section headings/content. Not a global
 * per-section fade reflex — apply where the reveal earns its place, not
 * to every single element. whileInView is IntersectionObserver-based and
 * does not touch scroll events, so it never conflicts with the Lenis/GSAP
 * scroll-driver.
 */
export function Reveal({ index = 0, children, style, ...props }: RevealProps) {
  const reduce = useReducedMotion();

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{
        duration: 0.7,
        delay: index * 0.07,
        ease: [0.22, 1, 0.36, 1],
      }}
      style={style}
      {...props}
    >
      {children}
    </motion.div>
  );
}
