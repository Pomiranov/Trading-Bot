/**
 * Illustrative trajectory: osc_range_moex_d1_fwd's real aggregate stats
 * (D1 OOS n=29, win rate 58.6%, PF 1.16 — see content/{locale}/strategies.json)
 * are real; the per-trade path between them is not logged anywhere we can
 * read, so this specific curve is a plausible reconstruction, not a query
 * result. Shape is grounded in the real belief_updater.py mechanics: flat
 * near neutral (0.5) below the 20-trade floor, then a deliberate move
 * toward the real aggregate signal after it — never near 0 or 1.
 */
const CONFIDENCE_BY_TRADE = [
  0.5, 0.49, 0.51, 0.5, 0.52, 0.49, 0.51, 0.5, 0.48, 0.51, 0.5, 0.52, 0.49,
  0.51, 0.5, 0.53, 0.51, 0.5, 0.52, 0.51, 0.54, 0.56, 0.55, 0.58, 0.6, 0.59,
  0.62, 0.61, 0.63,
];

const FLOOR_TRADE = 20;
const MIN_CONFIDENCE = 0.05;
const MAX_CONFIDENCE = 0.95;

const WIDTH = 600;
const HEIGHT = 200;
const PAD_X = 8;
const PAD_TOP = 16;
const PAD_BOTTOM = 28;

function x(trade: number) {
  const n = CONFIDENCE_BY_TRADE.length;
  return PAD_X + ((trade - 1) / (n - 1)) * (WIDTH - PAD_X * 2);
}

function y(confidence: number) {
  const usable = HEIGHT - PAD_TOP - PAD_BOTTOM;
  return PAD_TOP + (1 - confidence) * usable;
}

export function ConfidenceTrajectoryChart({ caption }: { caption: string }) {
  const points = CONFIDENCE_BY_TRADE.map((c, i) => `${x(i + 1)},${y(c)}`).join(" ");

  return (
    <figure className="flex flex-col gap-3">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-[200px] w-full"
        role="img"
        aria-label={caption}
      >
        {/* Bounds */}
        <line
          x1={PAD_X}
          x2={WIDTH - PAD_X}
          y1={y(MAX_CONFIDENCE)}
          y2={y(MAX_CONFIDENCE)}
          stroke="var(--color-border)"
          strokeDasharray="2 4"
        />
        <line
          x1={PAD_X}
          x2={WIDTH - PAD_X}
          y1={y(MIN_CONFIDENCE)}
          y2={y(MIN_CONFIDENCE)}
          stroke="var(--color-border)"
          strokeDasharray="2 4"
        />
        <text
          x={WIDTH - PAD_X}
          y={y(MAX_CONFIDENCE) - 6}
          textAnchor="end"
          className="font-mono text-[9px] fill-[var(--color-text-tertiary)]"
        >
          0.95 ceiling
        </text>
        <text
          x={WIDTH - PAD_X}
          y={y(MIN_CONFIDENCE) + 12}
          textAnchor="end"
          className="font-mono text-[9px] fill-[var(--color-text-tertiary)]"
        >
          0.05 floor
        </text>

        {/* 20-trade threshold */}
        <line
          x1={x(FLOOR_TRADE)}
          x2={x(FLOOR_TRADE)}
          y1={PAD_TOP}
          y2={HEIGHT - PAD_BOTTOM}
          stroke="var(--color-border)"
        />
        <text
          x={x(FLOOR_TRADE)}
          y={HEIGHT - 8}
          textAnchor="middle"
          className="font-mono text-[9px] fill-[var(--color-text-tertiary)]"
        >
          trade 20
        </text>

        {/* Trajectory */}
        <polyline
          points={points}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      <figcaption className="font-mono text-[11px] uppercase tracking-[0.1em] text-[color:var(--color-text-tertiary)]">
        {caption}
      </figcaption>
    </figure>
  );
}
