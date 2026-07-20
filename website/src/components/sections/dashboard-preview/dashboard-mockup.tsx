import { DASHBOARD_COLORS } from "./dashboard-colors";

interface Metric {
  label: string;
  value: string;
  positive?: boolean;
}

interface Position {
  ticker: string;
  side: "LONG" | "SHORT";
  confidence: number;
  pnlPct: string;
}

// Real /api/metrics field labels from bot/ui/dashboard.py — illustrative
// values only (no live DB in a static site build). Real tickers from the
// forward-test universe (run_forward_d1.py), illustrative positions.
const METRICS: Metric[] = [
  { label: "PORTFOLIO_VALUE", value: "₽1,048,230" },
  { label: "PNL_TODAY", value: "+₽6,140", positive: true },
  { label: "DRAWDOWN_PCT", value: "-4.8%" },
  { label: "SHARPE_RATIO", value: "1.34" },
];

const POSITIONS: Position[] = [
  { ticker: "SBER", side: "LONG", confidence: 0.71, pnlPct: "+1.9%" },
  { ticker: "GAZP", side: "SHORT", confidence: 0.42, pnlPct: "-0.6%" },
  { ticker: "LKOH", side: "LONG", confidence: 0.58, pnlPct: "+0.4%" },
];

// Fixed points, not generated per-render — a static, honest illustration,
// not a live chart. Straight segments (polyline), not smoothed beziers —
// instrument readout, not marketing curve.
const EQUITY_POINTS =
  "0,96 54,88 108,92 162,68 216,74 270,48 324,58 378,32 432,40 486,14 540,22 600,8";

export function DashboardMockup() {
  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--color-border)] bg-[#0a0a0b]">
      {/* Chrome bar */}
      <div className="flex items-center justify-between border-b border-[color:var(--color-border)] px-5 py-3">
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-[color:var(--color-text-tertiary)]">
          QuantFlow / Dashboard
        </span>
        <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.1em] text-[color:var(--color-text-tertiary)]">
          <span
            aria-hidden
            className="size-1.5 rounded-full"
            style={{ backgroundColor: DASHBOARD_COLORS.accent }}
          />
          bot_status: running
        </span>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-2 divide-x divide-y divide-[color:var(--color-border)] border-b border-[color:var(--color-border)] sm:grid-cols-4 sm:divide-y-0">
        {METRICS.map((m) => (
          <div key={m.label} className="flex flex-col gap-1 px-5 py-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[color:var(--color-text-tertiary)]">
              {m.label}
            </span>
            <span
              className="font-mono text-lg tabular-nums"
              style={{
                color: m.positive ? DASHBOARD_COLORS.long : "#f5f5f7",
              }}
            >
              {m.value}
            </span>
          </div>
        ))}
      </div>

      {/* Equity curve */}
      <div className="border-b border-[color:var(--color-border)] px-5 py-4">
        <svg viewBox="0 0 600 110" className="h-24 w-full" preserveAspectRatio="none">
          <polyline
            points={EQUITY_POINTS}
            fill="none"
            stroke={DASHBOARD_COLORS.accent}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Positions */}
      <div className="px-5 py-2">
        {POSITIONS.map((p) => (
          <div
            key={p.ticker}
            className="flex items-center justify-between border-b border-[color:var(--color-border)] py-2.5 font-mono text-[12px] last:border-none"
          >
            <span className="text-[color:var(--color-text-primary)]">{p.ticker}</span>
            <span
              style={{
                color: p.side === "LONG" ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short,
              }}
            >
              {p.side}
            </span>
            <span className="text-[color:var(--color-text-tertiary)]">
              conf {p.confidence.toFixed(2)}
            </span>
            <span
              style={{
                color: p.pnlPct.startsWith("+")
                  ? DASHBOARD_COLORS.long
                  : DASHBOARD_COLORS.short,
              }}
            >
              {p.pnlPct}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
