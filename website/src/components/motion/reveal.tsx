"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";

/** Distance a block travels on the way in. The brief's 24–40px range. */
const RISE_PX = 28;

/** Per-index delay. Small enough to read as one gesture, not a queue. */
const STAGGER_S = 0.08;

/**
 * Ceiling on the accumulated stagger. The delay exists to desync *siblings
 * arriving together*; an item that enters the viewport alone — the last card
 * of a grid reached by slow scrolling, after its siblings already revealed —
 * would otherwise still serve index × 80ms of queue for a group gesture that
 * is not happening. Four steps is where a delay stops reading as choreography
 * and starts reading as lag.
 */
const STAGGER_MAX_S = 0.32;

interface RevealProps extends HTMLMotionProps<"div"> {
  /** Stagger index — desyncs siblings by 80ms each. */
  index?: number;
  /**
   * Adds the 0.98 → 1 scale on the way in. On by default for cards, which is
   * what makes them read as *floating* into place rather than sliding.
   *
   * Turn it off for anything containing crisp small text that must not resample
   * mid-animation, and for full-width blocks where a scale reads as a glitch.
   */
  lift?: boolean;
}

/**
 * Scroll-into-view entrance for a block or a card.
 *
 * IntersectionObserver-based (`whileInView`), which is the load-bearing detail:
 * it reads no scroll events and drives no scroll position, so it cannot desync
 * from the Lenis scroll driver the way a scroll-linked GSAP tween can. This is
 * deliberately the *only* reveal mechanism on the page — the pinned GSAP
 * horizontal track that used to live in how-it-works was removed precisely
 * because it fought the smooth-scroll driver.
 *
 * `amount: 0.2` rather than a larger fraction: a tall card on a 390px viewport
 * may never have 25% of its height on screen at once, and the reveal would
 * simply never fire — which is how content ends up permanently invisible on
 * mobile.
 *
 * ── Why reduced motion is NOT handled with `initial={false}` ──
 *
 * It used to be, and that hid the entire page from reduced-motion users.
 *
 * `useReducedMotion()` reads the media query during the first render, so it is
 * `false` on the server and the user's real value on the client. With
 * `initial={reduce ? false : {opacity: 0, …}}` the server therefore always
 * emitted `opacity: 0` inline — and on a reduced-motion client `initial={false}`
 * means "adopt whatever is already in the DOM and do not animate", so that
 * `opacity: 0` was never cleared. Measured on the production build: all 32
 * cards stuck at opacity 0.
 *
 * The fix is to never branch the *markup* on the preference (the same rule
 * `ui/magnetic.tsx` documents). The props below are identical on the server and
 * on every client; only the transition *duration* collapses to zero, so a
 * reduced-motion user gets an instant appear rather than a fade. Belt and
 * braces, `globals.css` also force-resets `[data-reveal]` to its final state
 * under `prefers-reduced-motion: reduce`, so the content is visible even if the
 * IntersectionObserver never fires or JS fails outright.
 */
export function Reveal({ index = 0, lift = true, children, style, ...props }: RevealProps) {
  const reduce = useReducedMotion();

  return (
    <motion.div
      data-reveal=""
      initial={{ opacity: 0, y: RISE_PX, scale: lift ? 0.98 : 1 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={
        reduce
          ? { duration: 0 }
          : {
              duration: 0.7,
              delay: Math.min(index * STAGGER_S, STAGGER_MAX_S),
              ease: [0.22, 1, 0.36, 1],
            }
      }
      style={style}
      {...props}
    >
      {children}
    </motion.div>
  );
}
