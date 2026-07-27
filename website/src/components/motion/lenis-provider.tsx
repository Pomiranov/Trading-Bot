"use client";

import { useEffect } from "react";
import { initScrollDriver, getLenis, NAV_OFFSET } from "./scroll-driver";

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

      const lenis = getLenis();
      if (lenis) {
        lenis.scrollTo(target as HTMLElement, {
          offset: -NAV_OFFSET,
          duration: 1.1,
          easing: easeOutQuart,
        });
      } else {
        // Reduced-motion fallback — Lenis is never instantiated in that mode.
        const top =
          (target as HTMLElement).getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
        window.scrollTo({ top, behavior: "smooth" });
      }

      // Keep the URL shareable without letting the browser also jump to the
      // anchor, which would land at the wrong offset and fight the animation.
      if (history.replaceState) history.replaceState(null, "", href);
    }

    document.addEventListener("click", handleAnchorClick);
    return () => {
      cleanup();
      document.removeEventListener("click", handleAnchorClick);
    };
  }, []);

  return children;
}
