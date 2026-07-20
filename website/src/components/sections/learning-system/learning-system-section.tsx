import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatNumber } from "@/components/ui/stat-number";
import { Reveal } from "@/components/motion/reveal";
import { ConfidenceSlider } from "./confidence-slider";

/**
 * Intro + real belief_updater.py constants + the interactive confidence
 * slider (see confidence-slider.tsx for the drag mechanics, and
 * confidence-data.ts for what's real vs reconstructed in the trajectory
 * shape itself).
 */
export async function LearningSystemSection({ locale }: { locale: string }) {
  const [copy, t] = await Promise.all([
    contentSource.getLearningSystemCopy(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="learning-system-heading"
      className="px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <Reveal>
        <SectionHeading id="learning-system-heading" className="mb-10 max-w-[20ch]">
          {t("learningSystem")}
        </SectionHeading>
      </Reveal>
      <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-16">
        <Reveal index={1} className="flex flex-col gap-10">
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
        </Reveal>
        <Reveal index={2} className="flex items-center">
          <ConfidenceSlider
            caption={t("confidenceChartCaption")}
            dragHint={t("confidenceSliderDragHint")}
          />
        </Reveal>
      </div>
    </section>
  );
}
