"use client";

import { useRef } from "react";
import { useReducedMotion } from "motion/react";
import { ConfidenceTrajectoryChart } from "./confidence-trajectory-chart";
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

const LAST_INDEX = CONFIDENCE_BY_TRADE.length - 1;

/**
 * Drag along the real trajectory shape to see confidence at each trade —
 * "the confidence bar barely moves until the 20-trade floor, then adjusts"
 * (brief spec), demonstrated interactively rather than just described.
 *
 * Handle position + readout update imperatively (direct style/textContent
 * writes inside the pointer handler), not via useState/re-render, per the
 * continuous-value rule — this is a drag gesture, the canonical case it
 * exists for.
 */
export function ConfidenceSlider({
  caption,
  dragHint,
  tradeLabel,
  confidenceLabel,
  ceilingLabel = "0.95 ceiling",
  floorLabel = "0.05 floor",
  tradeFloorLabel = "trade 20",
}: {
  caption: string;
  dragHint: string;
  tradeLabel: string;
  confidenceLabel: string;
  ceilingLabel?: string;
  floorLabel?: string;
  tradeFloorLabel?: string;
}) {
  const reduce = useReducedMotion();
  const svgRef = useRef<SVGSVGElement>(null);
  const handleRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLParagraphElement>(null);
  const draggingRef = useRef(false);

  function setToIndex(idx: number) {
    const clamped = Math.min(LAST_INDEX, Math.max(0, idx));
    const cx = tradeToX(clamped + 1);
    const cy = confidenceToY(CONFIDENCE_BY_TRADE[clamped]);
    if (handleRef.current) {
      handleRef.current.style.left = `${(cx / CHART_WIDTH) * 100}%`;
      handleRef.current.style.top = `${(cy / CHART_HEIGHT) * 100}%`;
      handleRef.current.setAttribute("aria-valuenow", String(clamped + 1));
    }
    if (labelRef.current) {
      labelRef.current.textContent = `${tradeLabel} ${clamped + 1}: ${confidenceLabel} ${CONFIDENCE_BY_TRADE[clamped].toFixed(2)}`;
    }
  }

  function updateFromClientX(clientX: number) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const fraction = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const idx = Math.round(fraction * LAST_INDEX);
    setToIndex(idx);
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    draggingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    updateFromClientX(e.clientX);
  }
  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!draggingRef.current) return;
    updateFromClientX(e.clientX);
  }
  function onPointerUp() {
    draggingRef.current = false;
  }
  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    const current = Number(handleRef.current?.getAttribute("aria-valuenow") ?? "1") - 1;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      e.preventDefault();
      setToIndex(current - 1);
    } else if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      e.preventDefault();
      setToIndex(current + 1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setToIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setToIndex(LAST_INDEX);
    }
  }

  if (reduce) {
    return (
      <ConfidenceTrajectoryChart
        caption={caption}
        ceilingLabel={ceilingLabel}
        floorLabel={floorLabel}
        tradeFloorLabel={tradeFloorLabel}
      />
    );
  }

  const points = CONFIDENCE_BY_TRADE.map((c, i) => `${tradeToX(i + 1)},${confidenceToY(c)}`).join(
    " ",
  );

  return (
    <figure className="flex flex-col gap-3">
      <div
        className="relative touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
          className="h-[200px] w-full cursor-pointer"
          role="img"
          aria-label={caption}
        >
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
            {ceilingLabel}
          </text>
          <text
            x={CHART_WIDTH - PAD_X}
            y={confidenceToY(MIN_CONFIDENCE) + 12}
            textAnchor="end"
            className="font-mono text-[9px] fill-[var(--color-text-tertiary)]"
          >
            {floorLabel}
          </text>
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
            {tradeFloorLabel}
          </text>
          <polyline
            points={points}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </svg>
        <div
          ref={handleRef}
          role="slider"
          tabIndex={0}
          aria-label={dragHint}
          aria-valuemin={1}
          aria-valuemax={CONFIDENCE_BY_TRADE.length}
          aria-valuenow={CONFIDENCE_BY_TRADE.length}
          onKeyDown={onKeyDown}
          className="absolute size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[color:var(--color-bg)] bg-[color:var(--color-accent)] shadow-[0_0_0_1px_var(--color-accent)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[color:var(--color-accent)]"
          style={{
            left: `${(tradeToX(CONFIDENCE_BY_TRADE.length) / CHART_WIDTH) * 100}%`,
            top: `${(confidenceToY(CONFIDENCE_BY_TRADE[LAST_INDEX]) / CHART_HEIGHT) * 100}%`,
          }}
        />
      </div>
      <p ref={labelRef} className="font-mono text-[13px] text-[color:var(--color-text-secondary)] tabular-nums">
        {`${tradeLabel} ${CONFIDENCE_BY_TRADE.length}: ${confidenceLabel} ${CONFIDENCE_BY_TRADE[LAST_INDEX].toFixed(2)}`}
      </p>
      <figcaption className="font-mono text-[11px] uppercase tracking-[0.1em] text-[color:var(--color-text-tertiary)]">
        {caption}
      </figcaption>
    </figure>
  );
}
