import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { ArrowLink } from "@/components/ui/arrow-link";
import { Reveal } from "@/components/motion/reveal";

export async function AudienceSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "audience" });

  const cards = [
    { title: t("card1Title"), body: t("card1Body"), link: t("card1Link"), href: "#safety" },
    { title: t("card2Title"), body: t("card2Body"), link: t("card2Link"), href: "#how-it-works" },
    { title: t("card3Title"), body: t("card3Body"), link: t("card3Link"), href: "#brokers" },
  ] as const;

  return (
    // `default`, not `major`: the hero is `min-h-dvh` with its content centred,
    // so it already trails a screenful of space into this section. Stacking a
    // major on top of that was double-counting the same gap.
    <Section id="audience" rhythm="default" divider>
      <SectionHeader
        id="audience"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      <ul className="mt-14 grid gap-5 md:grid-cols-3">
        {cards.map((card, i) => (
          <li key={card.title} className="flex">
            <Reveal index={i} className="flex w-full">
              {/* `interactive` is the Surface default now — every card on the
                  page highlights, so it no longer needs opting in per card. */}
              <Surface className="flex w-full flex-col gap-4 p-7">
                <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                  {card.title}
                </h3>
                <p className="flex-1 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {card.body}
                </p>
                <ArrowLink href={card.href} className="mt-1">
                  {card.link}
                </ArrowLink>
              </Surface>
            </Reveal>
          </li>
        ))}
      </ul>
    </Section>
  );
}
