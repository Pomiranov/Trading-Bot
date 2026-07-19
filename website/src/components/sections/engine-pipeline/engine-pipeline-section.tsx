import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { MonoLabel } from "@/components/ui/mono-label";

/**
 * Phase 1 skeleton: a plain vertical list, real stage order from
 * bot/main.py::_process_ticker(). The pinned horizontal scroll (desktop)
 * / stepped vertical (mobile) treatment is Phase 4 motion work.
 */
export async function EnginePipelineSection({ locale }: { locale: string }) {
  const [stages, t] = await Promise.all([
    contentSource.getPipelineStages(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="engine-pipeline-heading"
      className="flex flex-col gap-12 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <SectionHeading id="engine-pipeline-heading" className="max-w-[20ch]">
        {t("enginePipeline")}
      </SectionHeading>
      <ol className="flex flex-col divide-y divide-[color:var(--color-border)]">
        {stages.map((stage) => (
          <li
            key={stage.id}
            className="grid grid-cols-1 gap-2 py-6 md:grid-cols-[80px_1fr_1fr] md:items-baseline md:gap-6"
          >
            <MonoLabel as="span">{String(stage.order).padStart(2, "0")}</MonoLabel>
            <p className="font-medium text-[color:var(--color-text-primary)]">
              {stage.title}
            </p>
            <div className="max-w-[60ch] text-[color:var(--color-text-secondary)]">
              {stage.description}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
