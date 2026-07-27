import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { MonoLabel } from "@/components/ui/mono-label";
import { AsideNote } from "@/components/ui/aside-note";
import { Reveal } from "@/components/motion/reveal";
import { StrategyTable } from "./strategy-table";
import { STRATEGY_STAGES, STRATEGY_STAGE_TONE, TONE_STYLE } from "@/lib/strategy-status";

/**
 * Strategy lab: a status ladder followed by the three real records.
 *
 * ── The ladder is a progression, not four adjacent boxes ──
 *
 * It used to be a `gap-px` strip of four equal cells, which reads as a table
 * header rather than as a sequence — no direction, no connector, nothing to say
 * a strategy moves through these one way. Each stage now carries an arrow into
 * the next at md and up.
 *
 * ── Empty stages ──
 *
 * Two of the four are unoccupied, and they used to render a bare `0`. A zero in
 * a cell reads as missing data — as though the page failed to load a number —
 * when what it actually means is "nothing has earned this yet", which is the
 * discipline the section exists to demonstrate. They now say so in words.
 *
 * A lane layout with strategies dropped into it was considered and rejected for
 * the same reason: it would give most of the section's area to two empty boxes.
 *
 * ── What must not appear ──
 *
 * No metrics column, in the ladder or the register. No win rate, drawdown,
 * profit factor or sample size. The status *is* the information, and `frozen`
 * renders muted rather than red — a frozen strategy is the outcome of a working
 * process, and publishing it is a signal rather than a failure.
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
      <Reveal index={1} className="mt-[var(--space-header-to-body)]">
        <MonoLabel className="mb-6">{t("ladderHeading")}</MonoLabel>
        <ol className="grid gap-[var(--space-card-gap)] sm:grid-cols-2 md:grid-cols-4 md:gap-0">
          {STRATEGY_STAGES.map((stage, i) => {
            const occupied = counts[stage] > 0;
            const tone = TONE_STYLE[STRATEGY_STAGE_TONE[stage]];
            const last = i === STRATEGY_STAGES.length - 1;

            return (
              <li
                key={stage}
                className="relative flex flex-col gap-3 rounded-[var(--radius-md)] border border-[color:var(--color-border)] bg-[color:var(--color-surface)] p-6 md:rounded-none md:border-r-0 md:first:rounded-l-[var(--radius-md)] md:last:rounded-r-[var(--radius-md)] md:last:border-r"
                aria-current={occupied ? "step" : undefined}
              >
                {/* Direction. A chevron sitting on the shared edge, so the four
                    cells read as one movement left-to-right instead of as four
                    independent boxes. Hidden on the last stage and below md,
                    where the cells stack and the arrow would point sideways
                    into nothing. */}
                {!last ? (
                  <span
                    aria-hidden="true"
                    className="absolute top-1/2 -right-2 z-10 hidden size-4 -translate-y-1/2 items-center justify-center rounded-[var(--radius-full)] bg-[color:var(--color-bg)] font-mono text-[length:var(--text-label)] text-[color:var(--color-text-quaternary)] md:flex"
                  >
                    ›
                  </span>
                ) : null}

                <div className="flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    className="size-1.5 shrink-0 rounded-[var(--radius-full)]"
                    style={{
                      backgroundColor: occupied ? tone.color : "transparent",
                      border: occupied ? undefined : "1px solid var(--color-border-strong)",
                    }}
                  />
                  <span
                    className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase"
                    style={{ color: occupied ? tone.color : "var(--color-text-tertiary)" }}
                  >
                    {common(`strategyStatus.${stage}`)}
                  </span>
                </div>

                {/* Occupancy in words. `0` read as a data-loading failure; "не
                    занято" reads as the deliberate state it is. */}
                <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase">
                  {occupied ? t("stageOccupied", { n: counts[stage] }) : t("stageEmpty")}
                </p>

                <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
                  {t(`${stage}Desc`)}
                </p>
              </li>
            );
          })}
        </ol>
      </Reveal>

      <Reveal index={2} className="mt-6">
        <AsideNote className="max-w-[80ch]">{t("currentStateNote")}</AsideNote>
      </Reveal>

      {/* ── The register ── */}
      <div className="mt-[var(--space-block)]">
        <StrategyTable locale={locale} />
      </div>

      {/* The two disclosures were previously two stacked paragraphs in
          near-identical quaternary grey, which read as one wall of small print.
          One block, one measure. */}
      <Reveal index={3} className="mt-6 flex max-w-[80ch] flex-col gap-2">
        <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
          {t("disclosure")}
        </p>
        <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
          {t("noMetricsNote")}
        </p>
      </Reveal>
    </Section>
  );
}
