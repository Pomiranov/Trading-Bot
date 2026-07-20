import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { MonoLabel } from "@/components/ui/mono-label";
import { Reveal } from "@/components/motion/reveal";
import { SectionSceneMount } from "@/components/scene/section-scene-mount";
import { EnginePipelineScroller } from "./engine-pipeline-scroller";

/**
 * Mobile: plain vertical stack, no JS. Desktop: pinned horizontal-pan
 * track via EnginePipelineScroller (GSAP ScrollTrigger, matchMedia-gated
 * to md+, see that file for the pin mechanics). Same stage data renders
 * both — only the container differs.
 */
export async function EnginePipelineSection({ locale }: { locale: string }) {
  const [stages, t, tScene] = await Promise.all([
    contentSource.getPipelineStages(locale),
    getTranslations({ locale, namespace: "sections" }),
    getTranslations({ locale, namespace: "scene" }),
  ]);

  return (
    <section
      aria-labelledby="engine-pipeline-heading"
      className="flex flex-col gap-12 py-[var(--space-section-y)]"
    >
      <div className="flex items-start justify-between gap-8 px-[var(--space-page-x)]">
        <Reveal>
          <SectionHeading id="engine-pipeline-heading" className="max-w-[20ch]">
            {t("enginePipeline")}
          </SectionHeading>
        </Reveal>
        <Reveal index={1} className="hidden w-[140px] shrink-0 lg:block">
          <SectionSceneMount mode="quant-engine" caption={tScene("quantEngine.label")} />
        </Reveal>
      </div>

      {/* Mobile: vertical stack */}
      <ol className="flex flex-col divide-y divide-[color:var(--color-border)] px-[var(--space-page-x)] md:hidden">
        {stages.map((stage) => (
          <li key={stage.id} className="flex flex-col gap-2 py-6 first:pt-0">
            <MonoLabel as="span">{String(stage.order).padStart(2, "0")}</MonoLabel>
            <p className="font-medium text-[color:var(--color-text-primary)]">
              {stage.title}
            </p>
            <div className="text-[color:var(--color-text-secondary)]">
              {stage.description}
            </div>
            {stage.sourceRef ? (
              <p className="font-mono text-xs text-[color:var(--color-text-tertiary)]">
                {stage.sourceRef}
              </p>
            ) : null}
          </li>
        ))}
      </ol>

      {/* Desktop: pinned horizontal-pan track */}
      <EnginePipelineScroller>
        {stages.map((stage) => (
          <li
            key={stage.id}
            className="flex w-[300px] shrink-0 flex-col gap-3 border-l border-[color:var(--color-border)] pl-6 [scroll-snap-align:start]"
          >
            <MonoLabel as="span">{String(stage.order).padStart(2, "0")}</MonoLabel>
            <p className="font-medium text-[color:var(--color-text-primary)]">
              {stage.title}
            </p>
            <div className="text-[15px] text-[color:var(--color-text-secondary)]">
              {stage.description}
            </div>
            {stage.sourceRef ? (
              <p className="mt-auto pt-4 font-mono text-xs text-[color:var(--color-text-tertiary)]">
                {stage.sourceRef}
              </p>
            ) : null}
          </li>
        ))}
      </EnginePipelineScroller>
    </section>
  );
}
