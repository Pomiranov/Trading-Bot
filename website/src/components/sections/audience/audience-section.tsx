import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { InteractiveCard } from "@/components/ui/interactive-card";
import { Reveal } from "@/components/motion/reveal";
import type { CtaTarget } from "@/lib/analytics/events";

/**
 * Route selection: four audiences, four destinations.
 *
 * ── What changed, and why it mattered ──
 *
 * This was the weakest-designed block on the page and the one the reference
 * invests most in. Three flat boxes with identical treatment — h3, paragraph,
 * arrow link — no numbering, no differentiation, nothing to say these are a
 * *choice* rather than a list.
 *
 * It also rendered as 2 + 1 on every desktop width, which is what made it read
 * as lopsided. That was not the card count: `lg:grid-cols-3` was being beaten by
 * `sm:grid-cols-2` because of the breakpoint registration-order bug documented
 * in globals.css. Both are fixed — the grid is honest now, and a fourth card
 * makes it a 2×2 rather than a 3-up with a hole in it.
 *
 * Worse, measured on the live build: all three computed `cursor: default`. The
 * card is the route selector, and only the 12-word arrow link inside it
 * actually navigated — a reader aims at a card-sized target and the card
 * swallows the click. `InteractiveCard` fixes that: the whole surface is the
 * link, with one tab stop and one focus ring.
 *
 * The row used to end in a drawn bracket descending into the pipeline. That
 * whole family of decorative connectors was removed on owner direction — they
 * read as accidental once the sections around them settled. The relationship is
 * carried by order and by the section rhythm instead, which is what the rest of
 * the page already relies on.
 */
export async function AudienceSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "audience" });

  /**
   * Four audiences, four distinct destinations — no two cards route to the same
   * place, which is what makes the row a selector rather than a list.
   *
   * card1 and card3 were re-pointed: card1 went to `#safety`, which card3 now
   * owns, and card3 went to `#brokers`, which no longer exists. Every `href`
   * here must resolve to a live section id in `app/[locale]/page.tsx` — a stale
   * anchor fails silently, because the Lenis interceptor simply finds nothing.
   */
  const cards = [
    {
      title: t("card1Title"),
      body: t("card1Body"),
      link: t("card1Link"),
      href: "#dashboard",
      target: "explore",
      where: "audience_product",
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
      href: "#safety",
      target: "explore",
      where: "audience_safety",
    },
    {
      title: t("card4Title"),
      body: t("card4Body"),
      link: t("card4Link"),
      href: "#faq",
      target: "explore",
      where: "audience_faq",
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

      {/*
        A 2×2 at `sm` and above, which is what the fourth card is for.

        Three cards could only ever be 2 + 1 or a 3-up that squeezed Cyrillic
        into ~230px columns at 768px. Four cards give the row a shape: two equal
        columns, two equal rows, and the same 20px gutter in both axes, so the
        block reads as one object rather than as a list that ran out.

        It deliberately stops at two columns — a 4-up at `lg` would put each card
        back into a ~300px column, and these bodies are 3–4 lines of Russian.
      */}
      <ul className="mt-[var(--space-header-to-body)] grid gap-[var(--space-card-gap)] sm:grid-cols-2">
        {cards.map((card, i) => (
          <li key={card.title} className="flex">
            <Reveal index={i} className="flex w-full">
              {/* Un-padded, matching the pipeline's numbering: the spine dropped
                  its zero-padding on owner direction, with the argument that
                  padding is wrong for any set that will never exceed nine —
                  which applies with more force to a set of four. Two numbering
                  conventions for one page is one too many. */}
              <InteractiveCard
                href={card.href}
                label={card.link}
                eyebrow={String(i + 1)}
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
    </Section>
  );
}
