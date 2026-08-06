"use client";

import { useEffect } from "react";
import { track } from "@/lib/analytics/events";

const DEPTH_MILESTONES = [25, 50, 75, 100] as const;

/**
 * One mount per page, no props: observes every `<section
 * aria-labelledby>` for journey_step (fired once per section id) and
 * tracks window scroll percentage for scroll_depth milestones (fired
 * once each, ascending only).
 */
export function ScrollAnalytics() {
  useEffect(() => {
    const seenSections = new Set<string>();
    const sections = document.querySelectorAll<HTMLElement>(
      "section[aria-labelledby]",
    );

    const sectionObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const id = entry.target.getAttribute("aria-labelledby");
          if (!id || seenSections.has(id)) continue;
          seenSections.add(id);
          track({ name: "journey_step", props: { section: id } });
        }
      },
      { threshold: 0.5 },
    );
    sections.forEach((section) => sectionObserver.observe(section));

    const seenDepths = new Set<number>();
    function onScroll() {
      const doc = document.documentElement;
      const scrolled = doc.scrollTop + window.innerHeight;
      const pct = (scrolled / doc.scrollHeight) * 100;
      for (const milestone of DEPTH_MILESTONES) {
        if (pct >= milestone && !seenDepths.has(milestone)) {
          seenDepths.add(milestone);
          track({ name: "scroll_depth", props: { milestone } });
        }
      }
    }
    window.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      sectionObserver.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  return null;
}
