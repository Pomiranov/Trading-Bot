import {
  CONFIDENCE_BY_TRADE,
  FLOOR_TRADE,
  MIN_CONFIDENCE,
  MAX_CONFIDENCE,
  CHART_WIDTH,
  CHART_HEIGHT,
  PAD_X,
  PAD_TOP,
  PAD_BOTTOM,
  tradeToX,
  confidenceToY,
} from "./confidence-data";

/**
 * Static base chart — axis lines, floor marker, full trajectory. Reused
 * as-is by ConfidenceSlider (adds the draggable handle on top) and as the
 * reduced-motion fallback (no drag affordance, still fully legible).
 */
export function ConfidenceTrajectoryChart({ caption }: { caption: string }) {
  const points = CONFIDENCE_BY_TRADE.map((c, i) => `${tradeToX(i + 1)},${confidenceToY(c)}`).join(
    " ",
  );

  return (
    <figure className="flex flex-col gap-3">
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="h-[200px] w-full"
        role="img"
        aria-label={caption}
      >
        {/* Bounds */}
        <line
          x1={PAD_X}
          x2={CHART_WIDTH - PAD_X}
          y1={confidenceToY(MAX_CONFIDENCE)}
          y2={confidenceToY(MAX_CONFIDENCE)}
          stroke="var(--color-border)"
          strokeDasharray="2 4"
        />
        <line
          x1={PAD_X}
          x2={CHART_WIDTH - PAD_X}
          y1={confidenceToY(MIN_CONFIDENCE)}
          y2={confidenceToY(MIN_CONFIDENCE)}
          stroke="var(--color-border)"
          strokeDasharray="2 4"
        />
        <text
          x={CHART_WIDTH - PAD_X}
          y={confidenceToY(MAX_CONFIDENCE) - 6}
          textAnchor="end"
          className="font-mono text-[9px] fill-[var(--color-text-tertiary)]"
        >
          0.95 ceiling
        </text>
        <text
          x={CHART_WIDTH - PAD_X}
          y={confidenceToY(MIN_CONFIDENCE) + 12}
          textAnchor="end"
          className="font-mono text-[9px] fill-[var(--color-text-tertiary)]"
        >
          0.05 floor
        </text>

        {/* 20-trade threshold */}
        <line
          x1={tradeToX(FLOOR_TRADE)}
          x2={tradeToX(FLOOR_TRADE)}
          y1={PAD_TOP}
          y2={CHART_HEIGHT - PAD_BOTTOM}
          stroke="var(--color-border)"
        />
        <text
          x={tradeToX(FLOOR_TRADE)}
          y={CHART_HEIGHT - 8}
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
