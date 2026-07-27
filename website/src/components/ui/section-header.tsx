import type { ReactNode } from "react";
import { Reveal } from "@/components/motion/reveal";
import { MonoLabel } from "./mono-label";
import { SectionHeading } from "./section-heading";
import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  /** Section slug. The <h2> gets `{id}-heading`, matching Section's aria-labelledby. */
  id: string;
  eyebrow?: string;
  heading: ReactNode;
  lead?: ReactNode;
  /** Disclosure / caveat line, rendered below the lead in caption type. */
  note?: ReactNode;
  align?: "start" | "center";
  className?: string;
}

/**
 * Eyebrow + heading + lead + optional disclosure.
 *
 * Replaces eight inline copies of this block — including one in
 * `faq-section.tsx` that re-implemented `SectionHeading` from scratch with the
 * same five CSS variables, and eight eyebrows hand-set at 10px/0.18em while
 * `MonoLabel`'s token said 11px/0.14em.
 *
 * The `note` slot exists because this product needs it: several sections carry
 * a caveat that is part of the claim, not decoration around it (statuses are
 * hand-maintained; the dashboard is illustrative; pricing is not live). Giving
 * it a first-class slot stops it being appended as an afterthought in a dimmer
 * grey each time.
 */
export function SectionHeader({
  id,
  eyebrow,
  heading,
  lead,
  note,
  align = "start",
  className,
}: SectionHeaderProps) {
  return (
    <Reveal
      // No scale on a heading: the section title is the largest type on screen
      // and scaling it resamples the glyphs mid-animation. The lift belongs to
      // cards, which are what should read as floating.
      lift={false}
      className={cn(
        "flex flex-col gap-4",
        align === "center" ? "items-center text-center" : "items-start",
        className,
      )}
    >
      {eyebrow ? <MonoLabel>{eyebrow}</MonoLabel> : null}

      <SectionHeading id={`${id}-heading`} className="max-w-[20ch]">
        {heading}
      </SectionHeading>

      {lead ? (
        <p
          className={cn(
            "max-w-[58ch] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] tracking-[var(--text-lead--letter-spacing)] text-[color:var(--color-text-secondary)]",
            align === "center" && "mx-auto",
          )}
        >
          {lead}
        </p>
      ) : null}

      {note ? (
        <p
          className={cn(
            "max-w-[62ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]",
            align === "center" && "mx-auto",
          )}
        >
          {note}
        </p>
      ) : null}
    </Reveal>
  );
}
