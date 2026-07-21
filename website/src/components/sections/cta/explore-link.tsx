"use client";

import { track } from "@/lib/analytics/events";

export function ExploreLink({ label }: { label: string }) {
  return (
    <a
      href="#hero-heading"
      onClick={() =>
        track({ name: "cta_clicked", props: { target: "explore", location: "cta" } })
      }
      className="group inline-flex items-center gap-2 font-mono text-[12px] uppercase tracking-[0.1em] transition-all duration-200"
      style={{ color: "rgba(255,255,255,0.35)", textDecoration: "none" }}
      onMouseEnter={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.65)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(255,255,255,0.35)"; }}
    >
      {label}
      <span
        className="transition-transform duration-200 group-hover:translate-x-1"
        aria-hidden="true"
      >
        →
      </span>
    </a>
  );
}
