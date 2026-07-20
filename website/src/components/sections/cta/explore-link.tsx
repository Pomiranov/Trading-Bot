"use client";

import { track } from "@/lib/analytics/events";

export function ExploreLink({ label }: { label: string }) {
  return (
    <a
      href="#hero-heading"
      onClick={() =>
        track({ name: "cta_clicked", props: { target: "explore", location: "cta" } })
      }
      className="font-mono text-[13px] uppercase tracking-[0.06em] text-[color:var(--color-text-tertiary)] underline-offset-4 hover:text-[color:var(--color-text-secondary)] hover:underline"
    >
      {label}
    </a>
  );
}
