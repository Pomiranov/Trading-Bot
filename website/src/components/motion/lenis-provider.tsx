"use client";

import { useEffect } from "react";
import { initScrollDriver, getLenis } from "./scroll-driver";

// Matches the visual height of the fixed site header
const NAV_OFFSET = 80;

function easeOutQuart(t: number) {
  return 1 - Math.pow(1 - t, 4);
}

/** Mounted once in the locale root layout. */
export function LenisProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const cleanup = initScrollDriver();

    // Intercept all anchor clicks and apply smooth scroll with nav offset
    function handleAnchorClick(e: MouseEvent) {
      const anchor = (e.target as HTMLElement).closest<HTMLAnchorElement>(
        "a[href^='#']"
      );
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href === "#") return;
      const target = document.querySelector(href);
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
        // Reduced-motion fallback
        const top =
          (target as HTMLElement).getBoundingClientRect().top +
          window.scrollY -
          NAV_OFFSET;
        window.scrollTo({ top, behavior: "smooth" });
      }
    }

    document.addEventListener("click", handleAnchorClick);
    return () => {
      cleanup();
      document.removeEventListener("click", handleAnchorClick);
    };
  }, []);

  return children;
}
