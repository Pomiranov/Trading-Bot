import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";

/**
 * Phase 1 skeleton: stacked blocks in document order. The brief's
 * three-column contrast layout (or a single long-form alternative) is a
 * Phase 3 art-direction decision, not decided here.
 */
export async function PhilosophySection({ locale }: { locale: string }) {
  const [blocks, t] = await Promise.all([
    contentSource.getPhilosophyBlocks(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="philosophy-heading"
      className="flex flex-col gap-12 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <SectionHeading id="philosophy-heading" className="max-w-[20ch]">
        {t("philosophy")}
      </SectionHeading>
      <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
        {blocks.map((block) => (
          <div key={block.id} className="flex flex-col gap-3">
            <h3 className="font-mono text-[length:var(--text-label)] uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
              {block.heading}
            </h3>
            <div className="max-w-[60ch] text-[color:var(--color-text-secondary)]">
              {block.body}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
