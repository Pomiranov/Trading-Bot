"use client";

import { useRef } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "motion/react";
import { Button } from "./button";

const RADIUS = 12;
const SPRING = { stiffness: 300, damping: 20, mass: 0.5 };

/**
 * Pointer-relative displacement on the wrapping div, capped at RADIUS px
 * and spring-eased — Button itself never re-renders on pointer move (the
 * transform lives outside React state), so this stays cheap even on a
 * page with the R3F scene mounted alongside it. Falls back to a plain
 * Button under reduced motion, no listeners attached at all.
 */
export function MagneticButton({
  className,
  ...props
}: React.ComponentProps<typeof Button>) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, SPRING);
  const springY = useSpring(y, SPRING);

  if (reduce) {
    return <Button className={className} {...props} />;
  }

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
    <motion.div
      ref={ref}
      className="inline-block"
      style={{ x: springX, y: springY }}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
    >
      <Button className={className} {...props} />
    </motion.div>
  );
}
