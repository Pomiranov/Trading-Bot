import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatNumber } from "@/components/ui/stat-number";
import { Reveal } from "@/components/motion/reveal";
import { ConfidenceTrajectoryChart } from "./confidence-trajectory-chart";

/**
 * Static pass: intro + real belief_updater.py constants + the trajectory
 * chart (illustrative shape, see confidence-trajectory-chart.tsx for what's
 * real vs reconstructed). The interactive drag slider is Phase 4 — same
 * numbers, added motion, not a different layout.
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
          <ConfidenceTrajectoryChart caption={t("confidenceChartCaption")} />
        </Reveal>
      </div>
    </section>
  );
}
