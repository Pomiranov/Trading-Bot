import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { MonoLabel } from "@/components/ui/mono-label";

/**
 * Static horizontal scroll-snap track on desktop (mobile stays a plain
 * vertical stack — brief spec). This is the Phase 3 static shape; Phase 4
 * adds the GSAP pin/scrub on the exact same DOM via ScrollTrigger.matchMedia,
 * no restructuring needed then.
 */
export async function EnginePipelineSection({ locale }: { locale: string }) {
  const [stages, t] = await Promise.all([
    contentSource.getPipelineStages(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="engine-pipeline-heading"
      className="flex flex-col gap-12 py-[var(--space-section-y)]"
    >
      <SectionHeading
        id="engine-pipeline-heading"
        className="max-w-[20ch] px-[var(--space-page-x)]"
      >
        {t("enginePipeline")}
      </SectionHeading>

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

      {/* Desktop: horizontal scroll-snap track */}
      <ol className="hidden gap-6 overflow-x-auto px-[var(--space-page-x)] pb-4 [scroll-snap-type:x_mandatory] md:flex">
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
      </ol>
    </section>
  );
}
