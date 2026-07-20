import Lenis from "lenis";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

/**
 * The single scroll-driver module for the whole site (per the plan's
 * highest-risk-integration flag). Exactly one RAF loop, owned by
 * gsap.ticker — Lenis and ScrollTrigger both subscribe to it instead of
 * each running their own requestAnimationFrame loop, which is the classic
 * "scroll feels janky / pinned sections misbehave" bug when Lenis and
 * native-scroll-reading libraries (ScrollTrigger) desync.
 *
 * Under prefers-reduced-motion, Lenis is never instantiated at all —
 * native scroll takes over, and ScrollTrigger still works fine off native
 * scroll events.
 */
let lenisInstance: Lenis | null = null;
let tickerFn: ((time: number) => void) | null = null;

export function initScrollDriver(): () => void {
  if (typeof window === "undefined") return () => {};
  if (lenisInstance || tickerFn) return () => {}; // already initialized

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return () => {};
  }

  const lenis = new Lenis({
    duration: 1.2,
    easing: (t: number) => 1 - Math.pow(1 - t, 3),
    smoothWheel: true,
  });
  lenisInstance = lenis;

  lenis.on("scroll", ScrollTrigger.update);

  const tick = (time: number) => {
    lenis.raf(time * 1000);
  };
  tickerFn = tick;
  gsap.ticker.add(tick);
  gsap.ticker.lagSmoothing(0);

  if (process.env.NODE_ENV === "development") {
    // TEMP debug hook — verifying the pin/scrub tween via ScrollTrigger's
    // own API since this session's browser-automation tool can't reliably
    // dispatch trusted wheel events to test real scrolling. Remove before
    // shipping; dev-only guard keeps it out of the production bundle
    // either way.
    (window as unknown as { __gsap: typeof gsap; __ScrollTrigger: typeof ScrollTrigger; __lenis: Lenis }).__gsap = gsap;
    (window as unknown as { __gsap: typeof gsap; __ScrollTrigger: typeof ScrollTrigger; __lenis: Lenis }).__ScrollTrigger = ScrollTrigger;
    (window as unknown as { __gsap: typeof gsap; __ScrollTrigger: typeof ScrollTrigger; __lenis: Lenis }).__lenis = lenis;
  }

  return () => {
    if (tickerFn) gsap.ticker.remove(tickerFn);
    lenis.destroy();
    lenisInstance = null;
    tickerFn = null;
  };
}

export function getLenis() {
  return lenisInstance;
}
