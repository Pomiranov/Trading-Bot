import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";

/**
 * Not three equal cards — an escalating single column. The content is a
 * rhetorical arc (what others do -> what we reject -> what we actually
 * do), so typographic weight escalates block to block instead of
 * flattening all three into identical grid cells. Hairline dividers
 * between blocks, not borders around them.
 */
export async function PhilosophySection({ locale }: { locale: string }) {
  const [blocks, t] = await Promise.all([
    contentSource.getPhilosophyBlocks(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  const weight = [
    "text-[color:var(--color-text-tertiary)] text-[15px] leading-relaxed",
    "text-[color:var(--color-text-secondary)] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)]",
    "text-[color:var(--color-text-primary)] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] font-medium",
  ];

  return (
    <section
      aria-labelledby="philosophy-heading"
      className="px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <div className="mx-auto flex max-w-[900px] flex-col gap-16">
        <Reveal>
          <SectionHeading id="philosophy-heading" className="max-w-[20ch]">
            {t("philosophy")}
          </SectionHeading>
        </Reveal>
        <div className="flex flex-col divide-y divide-[color:var(--color-border)]">
          {blocks.map((block, i) => (
            <Reveal
              key={block.id}
              index={i}
              className="flex flex-col gap-4 py-8 first:pt-0 last:pb-0"
            >
              <h3 className="font-mono text-[length:var(--text-label)] uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
                {block.heading}
              </h3>
              <div className={`max-w-[62ch] ${weight[i] ?? weight[weight.length - 1]}`}>
                {block.body}
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
