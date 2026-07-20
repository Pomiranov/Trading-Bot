import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatusPill, type StrategyStatus } from "@/components/ui/status-pill";
import type { StrategyMetrics } from "@/content-layer/types";

const STATUS_LABEL: Record<StrategyStatus, string> = {
  live: "LIVE",
  frozen: "FROZEN",
  stabilized: "STABILIZED",
};

/** Returns each metric on its own line (not dot-joined — a metadata strip
 * with 3 middle dots would exceed the "max 1 per line" separator rule). */
function formatMetrics(metrics: StrategyMetrics | undefined, locale: string): string[] {
  if (!metrics) return [];
  const parts: string[] = [];
  if (metrics.winRate !== undefined) {
    parts.push(
      new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 }).format(
        metrics.winRate,
      ),
    );
  }
  if (metrics.profitFactor !== undefined) {
    parts.push(`PF ${metrics.profitFactor.toFixed(2)}`);
  }
  if (metrics.sampleSize !== undefined) {
    parts.push(`n${metrics.sampleSize}`);
  }
  return parts;
}

/**
 * The honest inventory table — three real strategies, real status, no
 * fabricated precision. Radical honesty is the differentiator: FROZEN
 * strategies are shown here, not hidden, and the OOS metrics column
 * surfaces the same numbers content-layer already carries (previously
 * only partially shown in Learning System).
 */
export async function StrategyTable({ locale }: { locale: string }) {
  const [strategies, t] = await Promise.all([
    contentSource.getStrategies(locale),
    getTranslations({ locale, namespace: "sections" }),
  ]);

  const dateFormat = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <section
      aria-labelledby="strategy-layer-heading"
      className="flex flex-col gap-8 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <SectionHeading id="strategy-layer-heading" className="max-w-[20ch]">
        {t("strategyLayer")}
      </SectionHeading>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[color:var(--color-border)]">
              {[
                t("strategyTableHeaders.strategy"),
                t("strategyTableHeaders.market"),
                t("strategyTableHeaders.timeframe"),
                t("strategyTableHeaders.status"),
                t("strategyTableHeaders.metrics"),
                t("strategyTableHeaders.lastUpdate"),
              ].map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="py-3 pr-4 font-mono text-[length:var(--text-label)] font-normal uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]">
            {strategies.map((strategy) => {
              const metricLines = formatMetrics(strategy.metrics, locale);
              return (
              <tr key={strategy.id}>
                <td className="py-4 pr-4 font-mono text-[color:var(--color-text-primary)]">
                  {strategy.id}
                </td>
                <td className="py-4 pr-4 text-[color:var(--color-text-secondary)]">
                  {strategy.market}
                </td>
                <td className="py-4 pr-4 font-mono text-[color:var(--color-text-secondary)]">
                  {strategy.timeframe}
                </td>
                <td className="py-4 pr-4">
                  <div className="flex flex-col gap-1">
                    <StatusPill
                      status={strategy.status}
                      label={STATUS_LABEL[strategy.status]}
                    />
                    <span className="text-xs text-[color:var(--color-text-tertiary)]">
                      {strategy.statusNote}
                    </span>
                  </div>
                </td>
                <td className="py-4 pr-4 font-mono text-[13px] text-[color:var(--color-text-secondary)] tabular-nums">
                  {metricLines.length > 0 ? (
                    <div className="flex flex-col gap-0.5">
                      {metricLines.map((line) => (
                        <span key={line}>{line}</span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-[color:var(--color-text-tertiary)]">
                      {t("strategyMetricsUnavailable")}
                    </span>
                  )}
                </td>
                <td className="py-4 font-mono text-[color:var(--color-text-secondary)] tabular-nums">
                  {dateFormat.format(new Date(strategy.lastUpdate))}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
