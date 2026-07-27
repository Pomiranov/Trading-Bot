import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { MonoLabel } from "@/components/ui/mono-label";
import { Reveal } from "@/components/motion/reveal";
import { StrategyTable } from "./strategy-table";
import { STRATEGY_STAGES, STRATEGY_STAGE_TONE, TONE_STYLE } from "@/lib/strategy-status";

/**
 * Strategy lab: a status ladder followed by the three real records.
 *
 * The ladder is rendered as a progression of definitions rather than as four
 * lanes with strategies dropped into them. Two of the four stages are
 * unoccupied right now, and a lane layout would have devoted most of the
 * section's area to two empty boxes — which reads as an unfinished page rather
 * than as discipline. Occupancy is shown as a small count on each stage
 * instead, so the empty ones are still honest without dominating.
 */
export async function StrategiesSection({ locale }: { locale: string }) {
  const [strategies, t, common] = await Promise.all([
    contentSource.getStrategies(locale),
    getTranslations({ locale, namespace: "strategyLab" }),
    getTranslations({ locale, namespace: "common" }),
  ]);

  const counts = Object.fromEntries(
    STRATEGY_STAGES.map((stage) => [stage, strategies.filter((s) => s.status === stage).length]),
  ) as Record<(typeof STRATEGY_STAGES)[number], number>;

  return (
    // `default`: continues the execution/honesty movement that `brokers` opened
    // rather than starting its own.
    <Section id="strategies" rhythm="default" divider>
      <SectionHeader
        id="strategies"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      {/* ── Status ladder ── */}
      <Reveal index={1} className="mt-14">
        <MonoLabel className="mb-6">{t("ladderHeading")}</MonoLabel>
        <ol className="grid gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--color-border)] bg-[color:var(--color-border)] md:grid-cols-4">
          {STRATEGY_STAGES.map((stage) => {
            const occupied = counts[stage] > 0;
            const tone = TONE_STYLE[STRATEGY_STAGE_TONE[stage]];
            return (
              <li
                key={stage}
                className="flex flex-col gap-3 bg-[color:var(--color-surface)] p-6"
                aria-current={occupied ? "step" : undefined}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    className="size-1.5 shrink-0 rounded-full"
                    style={{
                      backgroundColor: occupied ? tone.color : "transparent",
                      border: occupied ? undefined : "1px solid var(--color-border-strong)",
                    }}
                  />
                  <span
                    className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase"
                    style={{ color: occupied ? tone.color : "var(--color-text-quaternary)" }}
                  >
                    {common(`strategyStatus.${stage}`)}
                  </span>
                  <span className="ml-auto font-mono text-[length:var(--text-label)] tabular-nums text-[color:var(--color-text-quaternary)]">
                    {counts[stage]}
                  </span>
                </div>
                <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
                  {t(`${stage}Desc`)}
                </p>
              </li>
            );
          })}
        </ol>
      </Reveal>

      <Reveal index={2} className="mt-6">
        <p className="max-w-[80ch] border-l-2 border-[color:var(--color-border-strong)] pl-5 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
          {t("currentStateNote")}
        </p>
      </Reveal>

      {/* ── The register ── */}
      <div className="mt-12">
        <StrategyTable locale={locale} />
      </div>

      <Reveal index={3} className="mt-6 flex flex-col gap-2">
        <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
          {t("disclosure")}
        </p>
        <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
          {t("noMetricsNote")}
        </p>
      </Reveal>
    </Section>
  );
}
