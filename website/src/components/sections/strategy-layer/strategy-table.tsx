import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { StatusPill, type StrategyStatus } from "@/components/ui/status-pill";
import type { StrategyMetrics } from "@/content-layer/types";

const STATUS_LABEL: Record<StrategyStatus, string> = {
  live: "LIVE",
  frozen: "FROZEN",
  stabilized: "STABILIZED",
};

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
      className="flex flex-col gap-10 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <Reveal>
        <SectionHeading id="strategy-layer-heading" className="max-w-[20ch]">
          {t("strategyLayer")}
        </SectionHeading>
      </Reveal>

      <Reveal index={2} className="overflow-x-auto">
        <div
          className="rounded-xl overflow-hidden"
          style={{
            border: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(255,255,255,0.02)",
          }}
        >
          <table className="w-full min-w-[760px] border-collapse text-left">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
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
                    className="px-5 py-3.5 font-mono font-normal uppercase"
                    style={{
                      fontSize: "10px",
                      letterSpacing: "0.16em",
                      color: "rgba(255,255,255,0.3)",
                    }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {strategies.map((strategy, i) => {
                const metricLines = formatMetrics(strategy.metrics, locale);
                return (
                  <tr
                    key={strategy.id}
                    className="transition-colors duration-150 hover:bg-white/[0.02]"
                    style={{
                      borderBottom: i < strategies.length - 1 ? "1px solid rgba(255,255,255,0.04)" : undefined,
                      background: strategy.status === "live" ? "rgba(255,138,30,0.02)" : undefined,
                    }}
                  >
                    <td className="px-5 py-4 font-mono text-[13px]" style={{ color: "rgba(255,255,255,0.85)" }}>
                      {strategy.id}
                    </td>
                    <td className="px-5 py-4 text-[13px]" style={{ color: "rgba(255,255,255,0.5)" }}>
                      {strategy.market}
                    </td>
                    <td className="px-5 py-4 font-mono text-[13px]" style={{ color: "rgba(255,255,255,0.5)" }}>
                      {strategy.timeframe}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-col gap-1">
                        <StatusPill
                          status={strategy.status}
                          label={STATUS_LABEL[strategy.status]}
                        />
                        <span className="text-xs" style={{ color: "rgba(255,255,255,0.28)" }}>
                          {strategy.statusNote}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4 font-mono text-[13px] tabular-nums" style={{ color: "rgba(255,255,255,0.55)" }}>
                      {metricLines.length > 0 ? (
                        <div className="flex flex-col gap-0.5">
                          {metricLines.map((line) => (
                            <span key={line}>{line}</span>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: "rgba(255,255,255,0.25)" }}>
                          {t("strategyMetricsUnavailable")}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 font-mono text-[13px] tabular-nums" style={{ color: "rgba(255,255,255,0.45)" }}>
                      {dateFormat.format(new Date(strategy.lastUpdate))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Reveal>
    </section>
  );
}
