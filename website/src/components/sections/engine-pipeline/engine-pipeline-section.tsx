import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { EnginePipelineScroller } from "./engine-pipeline-scroller";

export async function EnginePipelineSection({ locale }: { locale: string }) {
  const [stages, t] = await Promise.all([
    contentSource.getPipelineStages(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  return (
    <section
      aria-labelledby="engine-pipeline-heading"
      className="relative flex flex-col gap-12 py-[var(--space-section-y)]"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute right-0 top-0 w-[500px] h-[500px] rounded-full"
        style={{
          background: "radial-gradient(circle, rgba(255,138,30,0.04) 0%, transparent 60%)",
          filter: "blur(80px)",
        }}
      />

      <div className="px-[var(--space-page-x)]">
        <Reveal>
          <SectionHeading id="engine-pipeline-heading" className="max-w-[22ch]">
            {t("enginePipeline")}
          </SectionHeading>
        </Reveal>
      </div>

      {/* Mobile: vertical stack */}
      <ol className="flex flex-col px-[var(--space-page-x)] md:hidden">
        {stages.map((stage) => (
          <li
            key={stage.id}
            className="flex flex-col gap-2.5 py-6"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
          >
            <span
              className="font-mono tabular-nums text-[10px] uppercase tracking-[0.16em]"
              style={{ color: "var(--color-accent)", opacity: 0.7 }}
            >
              {String(stage.order).padStart(2, "0")}
            </span>
            <p className="font-medium" style={{ color: "var(--color-text-primary)" }}>
              {stage.title}
            </p>
            <div className="text-[14px]" style={{ color: "var(--color-text-secondary)" }}>
              {stage.description}
            </div>
            {stage.sourceRef ? (
              <p className="font-mono text-xs" style={{ color: "rgba(255,255,255,0.25)" }}>
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
            className="group flex w-[340px] shrink-0 flex-col gap-5 rounded-2xl p-7 [scroll-snap-align:start] transition-all duration-300 hover:border-white/[0.11]"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.08)",
              backdropFilter: "blur(16px)",
            }}
          >
            <div className="flex items-center gap-3">
              <span
                className="size-6 rounded-md flex items-center justify-center font-mono tabular-nums text-[9px] tracking-[0.08em] shrink-0"
                style={{
                  color: "var(--color-accent)",
                  background: "rgba(255,138,30,0.08)",
                  border: "1px solid rgba(255,138,30,0.12)",
                }}
              >
                {String(stage.order).padStart(2, "0")}
              </span>
              <div
                className="h-px flex-1"
                style={{ background: "rgba(255,255,255,0.05)" }}
              />
            </div>
            <p
              className="text-[15px] font-medium leading-snug"
              style={{ color: "rgba(255,255,255,0.92)", letterSpacing: "-0.01em" }}
            >
              {stage.title}
            </p>
            <div
              className="flex-1 text-[14px] leading-relaxed"
              style={{ color: "rgba(255,255,255,0.58)" }}
            >
              {stage.description}
            </div>
            {stage.sourceRef ? (
              <p
                className="mt-auto pt-4 font-mono text-[10px] uppercase tracking-[0.1em]"
                style={{
                  color: "rgba(255,255,255,0.18)",
                  borderTop: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                {stage.sourceRef}
              </p>
            ) : null}
          </li>
        ))}
      </EnginePipelineScroller>
    </section>
  );
}
