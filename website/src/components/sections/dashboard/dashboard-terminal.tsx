"use client";

import { useId, useRef, useState, type ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useTranslations } from "next-intl";
import { Surface } from "@/components/ui/surface";
import { StatusChip } from "@/components/ui/status-chip";
import { BrandMark } from "@/components/ui/brand-mark";
import { MonoLabel } from "@/components/ui/mono-label";
import { cn } from "@/lib/utils";

/**
 * The operator terminal as an interactive product section.
 *
 * ── What is and is not real here ──
 *
 * This is a *frontend demo*. Nothing in this file calls the backend, and no
 * value below is a measurement. That constraint shapes what each panel is
 * allowed to show: the panels carry decision *state* (a ticker, a side, a gate
 * verdict, a configured limit) and never an outcome. There is no P&L column, no
 * equity curve, no win rate, no profit factor and no return figure anywhere —
 * a chart that climbs to the right would be a performance claim even under a
 * disclaimer, which is what the earlier version of this section was corrected
 * for.
 *
 * The six sections are the ones the owner asked for. Two honest caveats are
 * stated in the section's own note rather than papered over: "Риск" is served
 * over the API and is not a separate page in the product yet, and the product
 * additionally has Learning and Settings sections that this demo omits.
 *
 * ── Accessibility ──
 *
 * Implemented as a real tablist: `role="tab"` + `aria-selected` +
 * `aria-controls`, with a single tab in the focus order and Arrow/Home/End
 * moving between them, which is the WAI-ARIA pattern. `aria-selected` on a tab
 * is the correct state here rather than `aria-pressed` — the latter is for
 * toggle buttons, and a screen reader would announce six independent toggles
 * instead of one 6-way choice. Panels are always rendered in the DOM order
 * after their tablist and are labelled by it.
 */

/** Demo rows. Structure is real; the values are illustrative and labelled so. */
const POSITIONS = [
  { ticker: "SBER", side: "LONG", qty: "40", entry: "284.10" },
  { ticker: "LKOH", side: "LONG", qty: "6", entry: "7 012" },
  { ticker: "GAZP", side: "LONG", qty: "120", entry: "128.44" },
] as const;

const SIGNALS = [
  { ticker: "SBER", side: "LONG", strategy: "osc_range_moex_d1_fwd", state: "executed" },
  { ticker: "LKOH", side: "LONG", strategy: "osc_range_moex_d1_fwd", state: "paper" },
  { ticker: "VTBR", side: "SHORT", strategy: "osc_range_moex_d1_fwd", state: "blocked" },
] as const;

const BACKTESTS = [
  { strategy: "osc_range_moex_d1_fwd", period: "2023-01 — 2025-12", tf: "D1", state: "done" },
  { strategy: "wrd_moex_d1_cand", period: "2022-01 — 2025-12", tf: "D1", state: "done" },
  { strategy: "osc_range_moex_h4", period: "2024-01 — 2025-12", tf: "H4", state: "running" },
] as const;

/** Signal counts per regime — decision volume, deliberately not profit. */
const REGIMES = [
  { regime: "range", signals: 34 },
  { regime: "trend_up", signals: 21 },
  { regime: "trend_down", signals: 12 },
  { regime: "undefined", signals: 5 },
] as const;

const STATE_TONE = { executed: "success", paper: "muted", blocked: "danger" } as const;

const TAB_COUNT = 6;

function Th({ children }: { children: ReactNode }) {
  return (
    <th
      scope="col"
      className="px-5 py-3 font-mono text-[length:var(--text-label)] font-normal tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase"
    >
      {children}
    </th>
  );
}

function Td({ children, dim = false }: { children: ReactNode; dim?: boolean }) {
  return (
    <td
      className={cn(
        "px-5 py-4 font-mono text-[length:var(--text-caption)]",
        dim
          ? "text-[color:var(--color-text-tertiary)]"
          : "text-[color:var(--color-text-primary)]",
      )}
    >
      {children}
    </td>
  );
}

function DataTable({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    // Axis-scoped so vertical wheel still goes through the smooth-scroll driver;
    // see strategy-table.tsx for why the bare data-lenis-prevent is a bug.
    <div data-lenis-prevent-horizontal className="overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse text-left">
        <thead>
          <tr className="border-b border-[color:var(--color-border)]">
            {head.map((h, i) => (
              <Th key={i}>{h}</Th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Row({ children, last = false }: { children: ReactNode; last?: boolean }) {
  return (
    <tr className={last ? "" : "border-b border-[color:var(--color-border)]"}>{children}</tr>
  );
}

/** Key/value rows — used by Overview and Risk. */
function DefinitionRows({
  rows,
}: {
  rows: readonly { label: string; value: ReactNode; hint?: string }[];
}) {
  return (
    <dl className="flex flex-col">
      {rows.map((r, i) => (
        <div
          key={r.label}
          className={cn(
            "flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-5 py-4",
            i < rows.length - 1 && "border-b border-[color:var(--color-border)]",
          )}
        >
          <dt className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
            {r.label}
          </dt>
          <dd className="flex flex-col items-end gap-0.5 text-right">
            <span className="font-mono text-[length:var(--text-caption)] tabular-nums text-[color:var(--color-text-primary)]">
              {r.value}
            </span>
            {r.hint ? (
              <span className="text-[length:var(--text-label)] text-[color:var(--color-text-quaternary)]">
                {r.hint}
              </span>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function DashboardTerminal() {
  const t = useTranslations("dashboard");
  const [active, setActive] = useState(0);
  const reduce = useReducedMotion();
  const baseId = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const tabId = (i: number) => `${baseId}-tab-${i}`;
  const panelId = (i: number) => `${baseId}-panel-${i}`;

  const tabs = Array.from({ length: TAB_COUNT }, (_, i) => ({
    label: t(`tab${i + 1}Label`),
    desc: t(`tab${i + 1}Desc`),
  }));

  const stateLabel = {
    executed: t("mockStateExecuted"),
    paper: t("mockStatePaper"),
    blocked: t("mockStateBlocked"),
  } as const;

  const gateLabel = {
    executed: t("mockGatePassed"),
    paper: t("mockGatePassed"),
    blocked: t("mockGateBelowFloor"),
  } as const;

  /** Roving focus, per the WAI-ARIA tabs pattern. */
  function onTabKeyDown(e: React.KeyboardEvent, i: number) {
    const move = (next: number) => {
      e.preventDefault();
      const clamped = (next + TAB_COUNT) % TAB_COUNT;
      setActive(clamped);
      tabRefs.current[clamped]?.focus();
    };
    if (e.key === "ArrowDown" || e.key === "ArrowRight") move(i + 1);
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft") move(i - 1);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(TAB_COUNT - 1);
  }

  const maxRegime = Math.max(...REGIMES.map((r) => r.signals));

  function panelBody(index: number) {
    switch (index) {
      case 0:
        return (
          <DefinitionRows
            rows={[
              { label: t("ovEngineLabel"), value: t("ovEngineValue") },
              { label: t("ovModeLabel"), value: t("mockModeValue") },
              { label: t("ovQueueLabel"), value: "12" },
              { label: t("ovEventLabel"), value: t("ovEventValue") },
            ]}
          />
        );

      case 1:
        return (
          <DataTable
            head={[t("mockColTicker"), t("mockColSide"), t("colQty"), t("colEntry")]}
          >
            {POSITIONS.map((p, i) => (
              <Row key={p.ticker} last={i === POSITIONS.length - 1}>
                <Td>{p.ticker}</Td>
                <Td dim>{p.side}</Td>
                <Td dim>{p.qty}</Td>
                <Td dim>{p.entry}</Td>
              </Row>
            ))}
          </DataTable>
        );

      case 2:
        return (
          <DataTable
            head={[
              t("mockColTicker"),
              t("mockColSide"),
              t("mockColStrategy"),
              t("mockColGate"),
              t("mockColState"),
            ]}
          >
            {SIGNALS.map((s, i) => (
              <Row key={s.ticker} last={i === SIGNALS.length - 1}>
                <Td>{s.ticker}</Td>
                <Td dim>{s.side}</Td>
                <Td dim>{s.strategy}</Td>
                <Td dim>{gateLabel[s.state]}</Td>
                <td className="px-5 py-4">
                  <StatusChip tone={STATE_TONE[s.state]} label={stateLabel[s.state]} />
                </td>
              </Row>
            ))}
          </DataTable>
        );

      case 3:
        return (
          <DataTable
            head={[t("mockColStrategy"), t("colPeriod"), t("colTimeframe"), t("colStatus")]}
          >
            {BACKTESTS.map((b, i) => (
              <Row key={b.strategy} last={i === BACKTESTS.length - 1}>
                <Td>{b.strategy}</Td>
                <Td dim>{b.period}</Td>
                <Td dim>{b.tf}</Td>
                <td className="px-5 py-4">
                  <StatusChip
                    tone={b.state === "done" ? "success" : "muted"}
                    label={b.state === "done" ? t("btDone") : t("btRunning")}
                  />
                </td>
              </Row>
            ))}
          </DataTable>
        );

      case 4:
        return (
          <div className="flex flex-col gap-5 px-5 py-5">
            <ul className="flex flex-col gap-3.5">
              {REGIMES.map((r) => (
                <li key={r.regime} className="flex items-center gap-4">
                  <span className="w-[11ch] shrink-0 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
                    {r.regime}
                  </span>
                  {/* Bar length encodes signal count, not profit. */}
                  <span
                    aria-hidden="true"
                    className="h-1.5 min-w-px rounded-full bg-[color:var(--color-text-secondary)]"
                    style={{ width: `${(r.signals / maxRegime) * 100}%` }}
                  />
                  <span className="ml-auto shrink-0 font-mono text-[length:var(--text-caption)] tabular-nums text-[color:var(--color-text-primary)]">
                    {r.signals}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
              {t("anNote")}
            </p>
          </div>
        );

      case 5:
        return (
          <div className="flex flex-col">
            <DefinitionRows
              rows={[
                { label: t("rkPerPosition"), value: "5%", hint: `${t("colLimit")} · config` },
                { label: t("rkDailyLoss"), value: "2%", hint: `${t("colLimit")} · config` },
                { label: t("rkOpenPositions"), value: "3", hint: t("colLimit") },
                { label: t("rkAtrStop"), value: "2.0 × ATR", hint: t("colLimit") },
              ]}
            />
            <p className="border-t border-[color:var(--color-border)] px-5 py-4 text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
              {t("rkApiNote")}
            </p>
          </div>
        );

      default:
        return null;
    }
  }

  return (
    /*
      One terminal frame, not a two-column layout.

      The previous version put a six-item vertical tablist in its own column
      beside the panel, which front-loaded a control surface before the reader
      knew what they were looking at — and at 390px produced 6 x ~76px = 456px
      of navigation before any content. The reference shows a narrative and a
      CTA on the left of the *section* and one panel on the right, with no tab
      chrome exposed outside it.

      So the tabs move inside the frame as a horizontal segmented control, and
      dashboard-section.tsx owns the narrative column.

      The WAI-ARIA tablist moves across unchanged: role="tab", aria-selected,
      aria-controls, one tab in the focus order, Arrow/Home/End roving focus,
      panels in DOM order after the tablist. Only `aria-orientation` flips, and
      the key handler already accepted both axes.
    */
    <Surface variant="raised" interactive={false} className="overflow-hidden">
      {/* ── Chrome ──
          The three grey dots that used to sit here were a monochrome macOS
          traffic-light imitation: the single most generic "this is a fake app
          screenshot" device available, and it undercut the claim that this is a
          real instrument. Replaced with the mark, the panel name and the mode
          the product actually runs in. */}
      <div className="flex flex-wrap items-center gap-3 border-b border-[color:var(--color-border)] px-5 py-3.5">
        <BrandMark size="xs" className="shrink-0 text-[color:var(--color-text-secondary)]" />
        <span className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
          {t("mockChrome")} · {tabs[active].label}
        </span>
        <span className="ml-auto flex items-center gap-2">
          <MonoLabel as="span">{t("mockModeLabel")}</MonoLabel>
          <StatusChip tone="muted" label={t("mockModeValue")} />
        </span>
      </div>

      {/* ── Tabs, inside the chrome ──
          Axis-scoped Lenis opt-out on the scroller: the bare data-lenis-prevent
          would release vertical wheel too and reintroduce the backward lurch.
          See strategy-table.tsx for the full account. */}
      <div
        data-lenis-prevent-horizontal
        className="overflow-x-auto border-b border-[color:var(--color-border)]"
      >
        <div
          role="tablist"
          aria-orientation="horizontal"
          aria-label={t("tabsLabel")}
          className="flex min-w-max"
        >
          {tabs.map((tab, i) => {
            const selected = i === active;
            return (
              <button
                key={tab.label}
                ref={(el) => {
                  tabRefs.current[i] = el;
                }}
                type="button"
                role="tab"
                id={tabId(i)}
                aria-selected={selected}
                aria-controls={panelId(i)}
                tabIndex={selected ? 0 : -1}
                onClick={() => setActive(i)}
                onKeyDown={(e) => onTabKeyDown(e, i)}
                title={tab.desc}
                className={cn(
                  "group relative shrink-0 cursor-pointer px-5 py-3.5 text-left font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] uppercase outline-none",
                  "transition-colors duration-[var(--duration-base)] ease-[var(--ease-out-expo)]",
                  "focus-visible:z-10 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[color:var(--color-accent)]",
                  selected
                    ? "bg-[color:var(--color-panel-raised)] text-[color:var(--color-text-primary)]"
                    : "text-[color:var(--color-text-tertiary)] hover:bg-[color:var(--color-panel)] hover:text-[color:var(--color-text-primary)]",
                )}
              >
                {tab.label}
                {/* Selected marker: a solid white rail on the bottom edge, not a
                    colour. Was a left rail when the list was vertical. */}
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute inset-x-0 bottom-0 h-[2px] transition-opacity duration-[var(--duration-base)]",
                    selected
                      ? "bg-[color:var(--color-accent)] opacity-100"
                      : "bg-[color:var(--color-border-strong)] opacity-0 group-hover:opacity-100",
                  )}
                />
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Panels ── */}
      {tabs.map((tab, i) => (
        <div
          key={tab.label}
          role="tabpanel"
          id={panelId(i)}
          aria-labelledby={tabId(i)}
          hidden={i !== active}
          // A tabpanel with no focusable child still needs to be reachable, so
          // a keyboard user can read it after Tab-ing off the tablist.
          tabIndex={i === active ? 0 : -1}
          className="outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
        >
          {i === active ? (
            <motion.div
              // Re-keyed per tab so the entrance replays on every switch.
              key={i}
              // `initial` must NOT branch on the reduced-motion preference: it
              // is false on the server and the user's real value on the client,
              // and `initial={false}` there would strand the server-rendered
              // opacity: 0 forever. Collapse the duration instead. See
              // motion/reveal.tsx for the full account.
              data-reveal=""
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduce ? { duration: 0 } : { duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            >
              {panelBody(i)}
            </motion.div>
          ) : null}
        </div>
      ))}
    </Surface>
  );
}
