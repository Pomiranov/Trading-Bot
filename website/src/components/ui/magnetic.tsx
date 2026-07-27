"use client";

import { useRef, type ReactNode } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "motion/react";

const SPRING = { stiffness: 300, damping: 20, mass: 0.5 };

interface MagneticProps {
  children: ReactNode;
  /** Maximum displacement in px. */
  radius?: number;
  className?: string;
}

/**
 * Pointer-relative displacement, capped at `radius` and spring-eased.
 *
 * Consolidates three near-identical copies of this maths that differed only in
 * their radius constant (12 / 10 / 14): `ui/magnetic-button.tsx`,
 * `nav/header-cta.tsx` and `hero/hero-cta.tsx`.
 *
 * The transform lives on a MotionValue rather than React state, so the wrapped
 * child never re-renders on pointer move.
 *
 * Under reduced motion the pointer handlers no-op — but the *markup* is
 * identical either way. This matters: `motion/react`'s `useReducedMotion` reads
 * the preference during the first render, so it is `false` on the server and
 * the user's real value on the client. Branching markup on it — which
 * `hero-cta.tsx` did — is a hydration mismatch for every reduced-motion user.
 * Branching only the behaviour is safe.
 *
 * That rule applies to `style` too, which is what the previous version missed:
 * `style={reduce ? undefined : {x, y}}` looks like a behaviour branch but is a
 * markup branch, because Motion serialises the MotionValue style to
 * `transform: none` on the server and omits it on a reduced-motion client.
 * React reported it as a real hydration error ("A tree hydrated but some
 * attributes of the server rendered HTML didn't match") on every page load with
 * the preference set, for all 5 Magnetic instances. The style is now
 * unconditional; under reduced motion the MotionValues simply never leave 0,
 * because `onPointerMove` returns early.
 */
export function Magnetic({ children, radius = 12, className }: MagneticProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, SPRING);
  const springY = useSpring(y, SPRING);

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (reduce) return;
    // Coarse pointers get no magnetism — it fights with tap targets.
    if (e.pointerType !== "mouse") return;
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const relX = (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
    const relY = (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2);
    x.set(Math.max(-1, Math.min(1, relX)) * radius);
    y.set(Math.max(-1, Math.min(1, relY)) * radius);
  }

  function reset() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.div
      ref={ref}
      className={className ?? "inline-block"}
      style={{ x: springX, y: springY }}
      onPointerMove={onPointerMove}
      onPointerLeave={reset}
      onBlur={reset}
    >
      {children}
    </motion.div>
  );
}
