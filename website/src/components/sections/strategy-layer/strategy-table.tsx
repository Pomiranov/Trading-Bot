import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { SectionHeading } from "@/components/ui/section-heading";
import { StatusPill, type StrategyStatus } from "@/components/ui/status-pill";

const STATUS_LABEL: Record<StrategyStatus, string> = {
  live: "LIVE",
  frozen: "FROZEN",
  stabilized: "STABILIZED",
};

/**
 * The honest inventory table — three real strategies, real status, no
 * fabricated precision. Radical honesty is the differentiator: FROZEN
 * strategies are shown here, not hidden.
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
        <table className="w-full min-w-[640px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[color:var(--color-border)]">
              {[
                t("strategyTableHeaders.strategy"),
                t("strategyTableHeaders.market"),
                t("strategyTableHeaders.timeframe"),
                t("strategyTableHeaders.status"),
                t("strategyTableHeaders.lastUpdate"),
              ].map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="py-3 font-mono text-[length:var(--text-label)] font-normal uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--color-border)]">
            {strategies.map((strategy) => (
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
                <td className="py-4 font-mono text-[color:var(--color-text-secondary)] tabular-nums">
                  {dateFormat.format(new Date(strategy.lastUpdate))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
