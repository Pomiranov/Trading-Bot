import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { StatusPill } from "@/components/ui/status-pill";
import { Reveal } from "@/components/motion/reveal";
import { STRATEGY_STAGE_TONE } from "@/lib/strategy-status";

/**
 * The published strategy register.
 *
 * No metrics column. Every result figure — win rate, profit factor, sample
 * size, drawdown — has been removed from the site; the status is the
 * information.
 *
 * Mobile scroll fix: the border and background now live on the scrolling
 * element itself. Previously `overflow-x-auto` sat on the Reveal wrapper while
 * an inner `rounded-xl overflow-hidden` div wrapped a `min-w-[760px]` table —
 * so the inner div clipped the content and the outer wrapper had nothing left
 * to scroll (measured at 390px: clientW 326 / scrollW 760, 434px unreachable).
 *
 * Horizontal trackpad gestures need to reach this container, because Lenis'
 * smoothWheel calls preventDefault on wheel events it handles. Use
 * `data-lenis-prevent-horizontal`, NOT the bare `data-lenis-prevent`:
 *
 * The bare attribute opts the element out of Lenis on *both* axes, so vertical
 * wheel input over the table scrolls the page natively while Lenis' internal
 * `animatedScroll` stays where it was. Lenis only resyncs from a native scroll
 * when `isScrolling` is false or "native" (lenis.mjs onNativeScroll) — mid
 * smooth animation it does not — so the next wheel event animates from a stale
 * origin and the page lurches backward. The axis-scoped attribute keeps
 * vertical scrolling on the smooth path and only releases horizontal gestures.
 */
export async function StrategyTable({ locale }: { locale: string }) {
  const [strategies, t, common] = await Promise.all([
    contentSource.getStrategies(locale),
    getTranslations({ locale, namespace: "strategyLab" }),
    getTranslations({ locale, namespace: "common" }),
  ]);

  // Formatted server-side on purpose: Node and browser ICU can disagree on
  // separators, which is a classic hydration mismatch inside a client tree.
  const dateFormat = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const headers = [
    t("tableStrategy"),
    t("tableMarket"),
    t("tableTimeframe"),
    t("tableStatus"),
    t("tableUpdated"),
  ];

  return (
    <Reveal index={2}>
      <div
        data-lenis-prevent-horizontal
        className="overflow-x-auto rounded-[var(--radius-lg)] border border-[color:var(--color-border)] bg-[color:var(--color-surface)]"
      >
        <table className="w-full min-w-[680px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[color:var(--color-border)]">
              {headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-5 py-4 font-mono text-[length:var(--text-label)] font-normal tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {strategies.map((strategy, i) => (
              <tr
                key={strategy.id}
                className={
                  i < strategies.length - 1 ? "border-b border-[color:var(--color-border)]" : ""
                }
              >
                <td className="px-5 py-5 font-mono text-[length:var(--text-caption)] text-[color:var(--color-text-primary)]">
                  {strategy.id}
                </td>
                <td className="px-5 py-5 text-[length:var(--text-caption)] text-[color:var(--color-text-tertiary)]">
                  {strategy.market}
                </td>
                <td className="px-5 py-5 font-mono text-[length:var(--text-caption)] text-[color:var(--color-text-tertiary)]">
                  {strategy.timeframe}
                </td>
                <td className="px-5 py-5">
                  <div className="flex flex-col items-start gap-2">
                    <StatusPill
                      tone={STRATEGY_STAGE_TONE[strategy.status]}
                      label={common(`strategyStatus.${strategy.status}`)}
                    />
                    <span className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
                      {strategy.statusNote}
                    </span>
                  </div>
                </td>
                <td className="px-5 py-5 font-mono text-[length:var(--text-caption)] tabular-nums text-[color:var(--color-text-quaternary)]">
                  {dateFormat.format(new Date(strategy.lastUpdate))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Reveal>
  );
}
