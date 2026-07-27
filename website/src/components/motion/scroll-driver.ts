import Lenis from "lenis";

/**
 * The single scroll-driver module for the whole site.
 *
 * ── The backward-scroll bug this fixes ──
 *
 * Symptom: while scrolling, the page would lurch *backward* — up to ~700px in
 * one frame — and then continue forward.
 *
 * Cause: `history.scrollRestoration` was left at its default of `"auto"`. On a
 * reload or a back-navigation the browser restores the previous scroll offset
 * *asynchronously*, after the first paint. Lenis is constructed inside a React
 * effect, which runs before that restore lands, so it captured `scrollY` at or
 * near 0 as its internal `animatedScroll`. The document was then sitting at,
 * say, 11 000px while Lenis believed it was at 10 300px. The first wheel event
 * animated from Lenis' stale origin, which yanked the page back by the size of
 * the discrepancy before resuming.
 *
 * Reproduced at 1440×900: scroll to 12 262 → reload → restored to 11 014 → one
 * downward wheel tick → the page dropped to 10 324 before settling. Measured
 * backward jump: −690px on purely downward input.
 *
 * Fix, in three parts:
 *   1. Take scroll restoration off `auto`. The browser no longer moves the
 *      document behind Lenis' back. A landing page whose height depends on
 *      lazily-revealed content cannot be restored accurately anyway — the old
 *      restore was already landing 1 248px off its own target.
 *   2. Honour a hash on first load ourselves, once layout has settled, so
 *      deep links still work with the header offset applied.
 *   3. Resync Lenis to the real offset after `load` and after any resize, so a
 *      programmatic scroll from anywhere else can never leave it stale.
 *
 * GSAP is deliberately no longer part of this file. It used to host the RAF loop
 * and receive `ScrollTrigger.update` on every Lenis tick, but the only
 * ScrollTrigger on the site was the pinned horizontal track in how-it-works,
 * which has been replaced by an IntersectionObserver reveal grid. With no
 * triggers left, keeping the bridge meant maintaining a Lenis↔ScrollTrigger
 * synchronisation path with nothing on the far side of it — the exact coupling
 * that makes this class of bug hard to reason about. Every reveal on the page is
 * now IntersectionObserver-based, so nothing except this module reads or writes
 * scroll position.
 *
 * Under prefers-reduced-motion, Lenis is never instantiated at all — native
 * scroll takes over and IntersectionObserver reveals still work fine.
 */

/**
 * Clearance to leave above an anchor target.
 *
 * This is the header's own height (78px: `pt-4` plus a 62px glass pill) *plus*
 * breathing room, not the header height itself. At the previous value of 80 the
 * arithmetic was technically correct and the result still looked wrong: a
 * section eyebrow landed 2px under the pill's bottom edge, touching it. Reading
 * as "the nav is sitting on the content" does not require actual overlap.
 *
 * 104 puts ~26px of black between the pill and the first line of a section,
 * which is the same order as the gap the header keeps from the top of the
 * viewport. Mirrored by the `scroll-margin-top` in globals.css, which is the
 * no-JS/keyboard-focus path to the same position — change both together.
 *
 * Exported so the anchor interceptor in lenis-provider.tsx uses the same
 * number: these were two separate literals, which is how a header resize
 * silently breaks deep links while in-page anchors keep working.
 */
export const NAV_OFFSET = 104;

let lenisInstance: Lenis | null = null;

export function initScrollDriver(): () => void {
  if (typeof window === "undefined") return () => {};
  if (lenisInstance) return () => {}; // already initialized

  /**
   * Off `auto` even in the reduced-motion branch. Native smooth scrolling and
   * an async restore fight each other in the same way, just less visibly, and
   * keeping the two paths consistent means one behaviour to reason about.
   */
  const previousRestoration = history.scrollRestoration;
  if ("scrollRestoration" in history) {
    history.scrollRestoration = "manual";
  }

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /**
   * A hash deep-link has to be applied by us now that the browser is not
   * restoring anything. Deferred to the next frame after `load` so it measures
   * against settled layout rather than pre-font-swap layout.
   */
  function applyInitialHash() {
    const { hash } = window.location;
    if (!hash || hash === "#") return;
    let target: Element | null = null;
    try {
      target = document.querySelector(hash);
    } catch {
      return; // not a valid selector, e.g. "#!"
    }
    if (!target) return;
    const top =
      (target as HTMLElement).getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
    if (lenisInstance) lenisInstance.scrollTo(top, { immediate: true });
    else window.scrollTo({ top, behavior: "auto" });
  }

  let rafId = 0;

  if (!reduce) {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t: number) => 1 - Math.pow(1 - t, 3),
      smoothWheel: true,
    });
    lenisInstance = lenis;

    const raf = (time: number) => {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);
  }

  /**
   * Belt and braces: if anything at all moves the document without going
   * through Lenis, snap Lenis' internal position to the truth rather than
   * letting it animate from a stale origin.
   */
  function resync() {
    lenisInstance?.scrollTo(window.scrollY, { immediate: true, force: true });
  }

  function onLoad() {
    applyInitialHash();
    // Layout can still shift as fonts swap in; re-measure once more.
    requestAnimationFrame(() => {
      lenisInstance?.resize();
      resync();
    });
  }

  if (document.readyState === "complete") onLoad();
  else window.addEventListener("load", onLoad);

  let resizeTimer: number | undefined;
  function onResize() {
    // Debounced: a resize storm otherwise calls resize()/resync() per frame,
    // and resync() during an in-flight animation reads as a stutter.
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      lenisInstance?.resize();
    }, 150);
  }
  window.addEventListener("resize", onResize);

  return () => {
    if (rafId) cancelAnimationFrame(rafId);
    window.clearTimeout(resizeTimer);
    window.removeEventListener("load", onLoad);
    window.removeEventListener("resize", onResize);
    lenisInstance?.destroy();
    lenisInstance = null;
    if ("scrollRestoration" in history) {
      history.scrollRestoration = previousRestoration;
    }
  };
}

export function getLenis() {
  return lenisInstance;
}
