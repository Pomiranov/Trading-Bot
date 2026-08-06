"use client";

import { useEffect } from "react";
import { initScrollDriver, getLenis, anchorOffsetFor } from "./scroll-driver";

function easeOutQuart(t: number) {
  return 1 - Math.pow(1 - t, 4);
}

/** Mounted once in the locale root layout. */
export function LenisProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const cleanup = initScrollDriver();

    // Intercept all in-page anchor clicks and apply smooth scroll with the nav
    // offset. Routed through Lenis rather than native smooth scrolling so the
    // two never drive the scroll position at the same time — competing
    // animations were one of the suspected causes of the backward-jump bug.
    function handleAnchorClick(e: MouseEvent) {
      // Let the browser handle modified clicks (new tab, download, etc.).
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
        return;
      }

      const anchor = (e.target as HTMLElement).closest<HTMLAnchorElement>("a[href^='#']");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href === "#") return;

      let target: Element | null = null;
      try {
        target = document.querySelector(href);
      } catch {
        return; // not a valid selector
      }
      if (!target) return;

      e.preventDefault();

      const el = target as HTMLElement;
      const offset = anchorOffsetFor(el);

      const lenis = getLenis();
      if (lenis) {
        /*
          A number, not the element. Handing Lenis the element delegates the
          position maths to its own resolution, and measured landings came out
          −52…+116px off the intent per section — enough to clip the
          how-it-works heading under the header pill on the primary hero CTA
          journey, while the document itself was verified stable during the
          flight (the drift is in the resolution, not the layout). One
          explicit read at click time is exact, and this handler runs on a
          user gesture between animations, so it does not race the scroll
          value Lenis animates — the same reasoning the fallback branch below
          already relies on.
        */
        const top = el.getBoundingClientRect().top + window.scrollY - offset;
        lenis.scrollTo(top, {
          duration: 1.1,
          easing: easeOutQuart,
        });
      } else {
        // Lenis is never instantiated under reduced motion, so this branch is
        // exactly the reduced-motion path — and an explicit behavior:"smooth"
        // is not suppressed by the global `scroll-behavior: auto` reset. Jump.
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const top = el.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({ top, behavior: reduce ? "auto" : "smooth" });
      }

      // Keep the URL shareable without letting the browser also jump to the
      // anchor, which would land at the wrong offset and fight the animation.
      if (history.replaceState) history.replaceState(null, "", href);

      // Native fragment navigation moves the sequential focus point to the
      // target; `preventDefault` above cancels that too, so a keyboard user
      // activating a nav link would scroll the page while their focus stayed
      // in the header — the next Tab would go to the wrong end of the page.
      // Restore the native behaviour by hand. `preventScroll` because Lenis
      // (or the fallback) owns the scroll; sections are not natively
      // focusable, so they get the -1 tabindex a fragment target effectively
      // has.
      if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
      el.focus({ preventScroll: true });
    }

    document.addEventListener("click", handleAnchorClick);
    return () => {
      cleanup();
      document.removeEventListener("click", handleAnchorClick);
    };
  }, []);

  return children;
}
