import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatNumber } from "@/components/ui/stat-number";
import { Reveal } from "@/components/motion/reveal";
import { ConfidenceSlider } from "./confidence-slider";

export async function LearningSystemSection({ locale }: { locale: string }) {
  const [copy, t] = await Promise.all([
    contentSource.getLearningSystemCopy(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="learning-system-heading"
      className="relative px-[var(--space-page-x)] py-[var(--space-section-y)] overflow-hidden"
    >
      {/* Ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/4 top-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(255,138,30,0.05) 0%, transparent 65%)",
          filter: "blur(80px)",
        }}
      />

      <Reveal>
        <SectionHeading id="learning-system-heading" className="mb-12 max-w-[20ch]">
          {t("learningSystem")}
        </SectionHeading>
      </Reveal>

      <div className="relative grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-20">
        <Reveal index={1} className="flex flex-col gap-10">
          <p
            className="max-w-[56ch] text-[15px] leading-relaxed"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {copy.intro}
          </p>

          {/* Stat trio */}
          <div
            className="flex flex-wrap gap-0 divide-x rounded-xl overflow-hidden"
            style={{
              borderColor: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.06)",
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <div className="flex flex-col gap-1.5 px-6 py-5 flex-1">
              <StatNumber
                value={copy.minTradesFloor}
                label={t("minTradesFloorLabel")}
                locale={locale}
                accent
              />
            </div>
            <div
              className="flex flex-col gap-1.5 px-6 py-5 flex-1"
              style={{ borderColor: "rgba(255,255,255,0.06)" }}
            >
              <StatNumber
                value={copy.minConfidence}
                label={t("minConfidenceLabel")}
                locale={locale}
              />
            </div>
            <div
              className="flex flex-col gap-1.5 px-6 py-5 flex-1"
              style={{ borderColor: "rgba(255,255,255,0.06)" }}
            >
              <StatNumber
                value={copy.maxConfidence}
                label={t("maxConfidenceLabel")}
                locale={locale}
              />
            </div>
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
