import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { InteractiveCard } from "@/components/ui/interactive-card";
import { SignalLine } from "@/components/ui/signal-line";
import { Reveal } from "@/components/motion/reveal";
import type { CtaTarget } from "@/lib/analytics/events";

/**
 * Route selection: three audiences, three destinations.
 *
 * ── What changed, and why it mattered ──
 *
 * This was the weakest-designed block on the page and the one the reference
 * invests most in. Three flat boxes with identical treatment — h3, paragraph,
 * arrow link — no numbering, no differentiation, nothing to say these are a
 * *choice* rather than a list.
 *
 * Worse, measured on the live build: all three computed `cursor: default`. The
 * card is the route selector, and only the 12-word arrow link inside it
 * actually navigated — a reader aims at a card-sized target and the card
 * swallows the click. `InteractiveCard` fixes that: the whole surface is the
 * link, with one tab stop and one focus ring.
 *
 * The bracket connector is the other half. The reference draws a line
 * descending from the card row into the pipeline, so the audience choice
 * visibly *routes into* how it works. Previously: three cards, a 347px gap, and
 * an unrelated H2.
 */
export async function AudienceSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "audience" });

  const cards = [
    {
      title: t("card1Title"),
      body: t("card1Body"),
      link: t("card1Link"),
      href: "#safety",
      target: "explore",
      where: "audience_safety",
    },
    {
      title: t("card2Title"),
      body: t("card2Body"),
      link: t("card2Link"),
      href: "#how-it-works",
      target: "how_it_works",
      where: "audience_pipeline",
    },
    {
      title: t("card3Title"),
      body: t("card3Body"),
      link: t("card3Link"),
      href: "#brokers",
      target: "explore",
      where: "audience_brokers",
    },
  ] as const satisfies readonly {
    title: string;
    body: string;
    link: string;
    href: string;
    /** Constrained by the CtaTarget union; the specific route lives in `where`
        so tracking stays useful without widening a typed analytics contract. */
    target: CtaTarget;
    where: string;
  }[];

  return (
    // `default`, not `major`: the hero already trails a screenful of space into
    // this section, and stacking a major step on top of that double-counted the
    // same gap.
    <Section id="audience" rhythm="default" divider>
      <SectionHeader
        id="audience"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      {/* sm:grid-cols-2 added. The old 1 -> 3 jump at md put three Cyrillic
          cards into ~230px columns at 768px, which is where the RU copy breaks
          worst. */}
      <ul className="mt-[var(--space-header-to-body)] grid gap-[var(--space-card-gap)] sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card, i) => (
          <li key={card.title} className="flex">
            <Reveal index={i} className="flex w-full">
              <InteractiveCard
                href={card.href}
                label={card.link}
                eyebrow={String(i + 1).padStart(2, "0")}
                analytics={{ target: card.target, location: card.where }}
              >
                <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                  {card.title}
                </h3>
                <p className="flex-1 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {card.body}
                </p>
              </InteractiveCard>
            </Reveal>
          </li>
        ))}
      </ul>

      {/*
        The bracket down into the pipeline.

        In flow, and owned by *this* section's bottom edge — not absolutely
        positioned across the section boundary. A cross-section connector has to
        be re-derived at every breakpoint and misaligns the moment a card grows
        a line; this one cannot, and removing the section below leaves no
        floating line behind. Hidden under md, where the layout is one column
        and there is nothing to gather.
      */}
      <SignalLine orientation="bracket" className="mt-8" />
    </Section>
  );
}
