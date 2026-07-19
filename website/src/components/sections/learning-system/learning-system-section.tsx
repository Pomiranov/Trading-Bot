import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatNumber } from "@/components/ui/stat-number";

/**
 * Phase 1 skeleton: intro copy + the three real belief_updater.py
 * constants as static numbers. The interactive confidence slider and the
 * osc_range_moex_d1_fwd trajectory chart are Phase 4 work.
 */
export async function LearningSystemSection({ locale }: { locale: string }) {
  const [copy, t] = await Promise.all([
    contentSource.getLearningSystemCopy(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="learning-system-heading"
      className="flex flex-col gap-10 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <SectionHeading id="learning-system-heading" className="max-w-[20ch]">
        {t("learningSystem")}
      </SectionHeading>
      <div className="max-w-[60ch] text-[color:var(--color-text-secondary)]">
        {copy.intro}
      </div>
      <div className="flex flex-wrap gap-10">
        <StatNumber
          value={copy.minTradesFloor}
          label={t("minTradesFloorLabel")}
          locale={locale}
        />
        <StatNumber
          value={copy.minConfidence}
          label={t("minConfidenceLabel")}
          locale={locale}
        />
        <StatNumber
          value={copy.maxConfidence}
          label={t("maxConfidenceLabel")}
          locale={locale}
        />
      </div>
    </section>
  );
}
