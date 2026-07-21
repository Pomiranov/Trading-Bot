"use client";

import { MagneticButton } from "@/components/ui/magnetic-button";
import { track } from "@/lib/analytics/events";

export function HeaderCta({ label }: { label: string }) {
  return (
    <MagneticButton
      size="sm"
      render={
        <a
          href="#cta-heading"
          onClick={() =>
            track({ name: "cta_clicked", props: { target: "beta_form", location: "nav" } })
          }
        />
      }
    >
      {label}
    </MagneticButton>
  );
}
