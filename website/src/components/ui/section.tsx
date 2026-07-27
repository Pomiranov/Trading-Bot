import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Rhythm = "hero" | "major" | "default" | "tight";
type Width = "content" | "prose";
export type SectionTone = "dark" | "paper";

const RHYTHM: Record<Rhythm, string> = {
  // The hero owns its own vertical sizing (min-h-dvh + header clearance).
  hero: "",
  major: "py-[var(--space-section-y-major)]",
  default: "py-[var(--space-section-y)]",
  tight: "py-[var(--space-section-y-tight)]",
};

/**
 * Tone works by *re-pointing the section's colour variables*, not by giving
 * every component a `tone` prop.
 *
 * `section-paper` (globals.css) reassigns --color-text-*, --color-border*,
 * --card-bg and --card-bg-hover on the section element itself. Because every
 * descendant already reads those variables, the whole subtree inverts without
 * a single card, heading or status chip learning that paper exists. That is
 * also what makes reverting a band a one-word change rather than a refactor.
 *
 * The rule this enforces: no component may hard-code a colour. If a card looks
 * wrong on paper it is because it bypassed a token, and the fix is the token,
 * not a `tone` prop on that card.
 */
const TONE: Record<SectionTone, string> = {
  dark: "",
  paper: "section-paper bg-[color:var(--color-paper)]",
};

interface SectionProps {
  /**
   * Slug for the section. Becomes the element id and, by convention, points
   * aria-labelledby at `{id}-heading` — so the heading inside must carry that
   * id. Nav anchors target `#{id}`, never `#{id}-heading`.
   */
  id: string;
  rhythm?: Rhythm;
  width?: Width;
  /**
   * Inverted light band. Capped at two per page by owner decision — the deep
   * black base is the identity, and paper is punctuation rather than a second
   * theme. Adding a third is a design decision, not a styling one.
   */
  tone?: SectionTone;
  /** Hairline top border. Replaces the old positional nth-child rule. */
  divider?: boolean;
  /** Decorative background. Rendered into a clipped, aria-hidden layer. */
  glow?: ReactNode;
  /** Escape hatch for a section whose heading id differs from the convention. */
  labelledBy?: string;
  className?: string;
  children: ReactNode;
}

/**
 * The one section shell. Every homepage section uses it, which is what gives
 * the page a single container width and a single left edge — previously there
 * were seven of each.
 *
 * Three structural rules, each fixing a defect that actually shipped:
 *
 *  1. `overflow-hidden` is NEVER set on the <section> element. An
 *     overflow-hidden ancestor silently disables GSAP ScrollTrigger pinning —
 *     no error, the animation just doesn't happen. Sections used to set it in
 *     order to clip their glow, and the one section that happened not to is
 *     the only one whose pin works. Clipping therefore lives on the glow layer
 *     instead, so a glow can neither leak nor break a pin.
 *
 *  2. One inner container, `max-w-[var(--space-content-max)]`. At 1280px this
 *     matches the header's own max width, so header and content share an edge
 *     at every viewport.
 *
 *  3. Dividers are a prop, not a CSS sibling selector. The old
 *     `main > *:not(:first-child):not(:nth-child(2))` rule broke as soon as
 *     the header moved out of <main>, and again whenever GSAP injected a
 *     pin-spacer wrapper.
 */
export function Section({
  id,
  rhythm = "default",
  width = "content",
  tone = "dark",
  divider = false,
  glow,
  labelledBy,
  className,
  children,
}: SectionProps) {
  return (
    <section
      id={id}
      // Read by the anchor-landing rules in globals.css and by the offset
      // calculation in motion/lenis-provider.tsx. A section's rhythm determines
      // its top padding, and its top padding is exactly how much dead space an
      // anchor would otherwise land the reader in — see the note beside
      // `--anchor-clearance`.
      data-rhythm={rhythm}
      aria-labelledby={labelledBy ?? `${id}-heading`}
      className={cn(
        "relative isolate px-[var(--space-page-x)]",
        RHYTHM[rhythm],
        TONE[tone],
        // A hairline between two dark sections is the separator. Between a dark
        // section and a paper one the tone change *is* the separator, and a
        // white line on top of it just reads as a seam artefact.
        divider && tone === "dark" && "border-t border-[color:var(--color-border)]",
        className,
      )}
    >
      {glow ? (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
          {glow}
        </div>
      ) : null}
      <div
        className={cn(
          "relative mx-auto w-full",
          width === "prose"
            ? "max-w-[var(--space-prose-max)]"
            : "max-w-[var(--space-content-max)]",
        )}
      >
        {children}
      </div>
    </section>
  );
}

/**
 * Escapes the section's horizontal page padding for children that must run
 * wider than the text column — the pinned pipeline track, the strategy table's
 * mobile scroll container.
 *
 * Deliberately escapes the padding only, not to full viewport width: a
 * `100vw` bleed disagrees with the vertical scrollbar and introduces a
 * horizontal scrollbar on exactly the desktop widths this page cares about.
 */
export function SectionBleed({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("relative -mx-[var(--space-page-x)]", className)}>{children}</div>
  );
}
