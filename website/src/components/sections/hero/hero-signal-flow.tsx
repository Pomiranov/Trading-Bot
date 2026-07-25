"use client";

import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";


const CONFIDENCE_POINTS = [
  { t: 0, c: 0.5 }, { t: 1, c: 0.52 }, { t: 2, c: 0.48 }, { t: 3, c: 0.55 },
  { t: 4, c: 0.60 }, { t: 5, c: 0.57 }, { t: 6, c: 0.64 }, { t: 7, c: 0.68 },
  { t: 8, c: 0.63 }, { t: 9, c: 0.71 }, { t: 10, c: 0.74 }, { t: 11, c: 0.70 },
  { t: 12, c: 0.75 }, { t: 13, c: 0.72 }, { t: 14, c: 0.77 }, { t: 15, c: 0.80 },
];

export function HeroSignalFlow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const DPR = window.devicePixelRatio || 1;
    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    ctx.scale(DPR, DPR);

    const ORANGE = "#ff8a1e";
    const WHITE_DIM = "rgba(255,255,255,0.06)";
    const WHITE_MED = "rgba(255,255,255,0.35)";
    const WHITE_LOW = "rgba(255,255,255,0.18)";

    const PIPELINE_X = 56;
    const PIPELINE_Y_START = 40;
    const STEP = (H - 80) / 5;
    const NODE_R = 4;

    const stages = [
      { label: "MARKET DATA", sub: "OHLCV · live" },
      { label: "INDICATORS", sub: "RSI · ATR · SAR" },
      { label: "RULES ENGINE", sub: "Schwager rulebook" },
      { label: "BELIEF GATE", sub: "Bayesian bounds" },
      { label: "RISK MANAGER", sub: "Position sizing" },
      { label: "EXECUTE", sub: "T-Invest · Bybit" },
    ];

    const chartLeft = W * 0.42;
    const chartRight = W - 20;
    const chartTop = 20;
    const chartBottom = H - 20;
    const chartW = chartRight - chartLeft;
    const chartH = chartBottom - chartTop;

    let phase = 0; // 0–5 which node is active
    let phaseT = 0; // 0–1 progress within current phase
    let pulseT = 0; // 0–1 for the dot traveling along the edge
    const PHASE_DUR = reduce ? 0 : 2.4; // seconds per stage
    let lastTime = 0;

    function yForNode(i: number) {
      return PIPELINE_Y_START + i * STEP;
    }

    function drawFrame(ts: number) {
      if (!ctx) return;
      const dt = lastTime ? Math.min((ts - lastTime) / 1000, 0.05) : 0;
      lastTime = ts;

      if (!reduce) {
        phaseT += dt / PHASE_DUR;
        if (phaseT >= 1) {
          phaseT = 0;
          phase = (phase + 1) % stages.length;
        }
        pulseT = phaseT;
      }

      ctx.clearRect(0, 0, W, H);

      // Background panel
      ctx.fillStyle = "rgba(8,8,10,0.0)";
      ctx.fillRect(0, 0, W, H);

      // Draw chart area (right side)
      const confMaxY = 0.8;
      const confMinY = 0.2;

      // Chart grid lines
      ctx.strokeStyle = WHITE_DIM;
      ctx.lineWidth = 0.5;
      const gridLevels = [0.2, 0.4, 0.6, 0.8];
      for (const level of gridLevels) {
        const gy = chartTop + chartH * (1 - (level - confMinY) / (confMaxY - confMinY));
        ctx.beginPath();
        ctx.moveTo(chartLeft, gy);
        ctx.lineTo(chartRight, gy);
        ctx.stroke();
      }

      // Chart axis labels
      ctx.fillStyle = "rgba(255,255,255,0.2)";
      ctx.font = "9px 'SF Mono', 'Fira Code', monospace";
      ctx.textAlign = "right";
      for (const level of [0.2, 0.5, 0.8]) {
        const gy = chartTop + chartH * (1 - (level - confMinY) / (confMaxY - confMinY));
        ctx.fillText(`${Math.round(level * 100)}%`, chartLeft - 6, gy + 3);
      }

      // Chart label
      ctx.fillStyle = "rgba(255,255,255,0.18)";
      ctx.font = "8px 'SF Mono', 'Fira Code', monospace";
      ctx.textAlign = "left";
      ctx.fillText("CONFIDENCE · osc_range_moex_d1_fwd", chartLeft, chartTop - 6);

      // Confidence path
      const pts = CONFIDENCE_POINTS.map((p) => ({
        px: chartLeft + (p.t / (CONFIDENCE_POINTS.length - 1)) * chartW,
        py: chartTop + chartH * (1 - (p.c - confMinY) / (confMaxY - confMinY)),
      }));

      // Area fill
      ctx.beginPath();
      ctx.moveTo(pts[0].px, chartBottom);
      pts.forEach((p) => ctx.lineTo(p.px, p.py));
      ctx.lineTo(pts[pts.length - 1].px, chartBottom);
      ctx.closePath();
      const areaGrad = ctx.createLinearGradient(0, chartTop, 0, chartBottom);
      areaGrad.addColorStop(0, "rgba(255,138,30,0.12)");
      areaGrad.addColorStop(1, "rgba(255,138,30,0)");
      ctx.fillStyle = areaGrad;
      ctx.fill();

      // Line
      ctx.beginPath();
      pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.px, p.py) : ctx.lineTo(p.px, p.py)));
      ctx.strokeStyle = ORANGE;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.stroke();

      // Trade dots
      pts.forEach((p, i) => {
        const isWin = CONFIDENCE_POINTS[i].c > (i > 0 ? CONFIDENCE_POINTS[i - 1].c : 0.5);
        ctx.beginPath();
        ctx.arc(p.px, p.py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = isWin ? "rgba(44,233,123,0.8)" : "rgba(229,72,77,0.7)";
        ctx.fill();
      });

      // End glow dot
      const last = pts[pts.length - 1];
      ctx.beginPath();
      ctx.arc(last.px, last.py, 5, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,138,30,0.15)";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(last.px, last.py, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = ORANGE;
      ctx.fill();

      // ─── Pipeline (left side) ───
      stages.forEach((stage, i) => {
        const y = yForNode(i);
        const isActive = phase === i;
        const isPast = phase > i;

        // Vertical connector line
        if (i < stages.length - 1) {
          const nextY = yForNode(i + 1);
          const lineAlpha = isPast || isActive ? 0.35 : 0.1;
          ctx.beginPath();
          ctx.moveTo(PIPELINE_X, y + NODE_R + 3);
          ctx.lineTo(PIPELINE_X, nextY - NODE_R - 3);
          ctx.strokeStyle = isPast || isActive ? "rgba(255,138,30," + lineAlpha + ")" : WHITE_DIM;
          ctx.lineWidth = 1;
          ctx.stroke();

          // Animated pulse dot on active connection
          if (isActive && !reduce) {
            const dotY = y + NODE_R + 3 + pulseT * (nextY - y - (NODE_R + 3) * 2);
            ctx.beginPath();
            ctx.arc(PIPELINE_X, dotY, 2.5, 0, Math.PI * 2);
            ctx.fillStyle = ORANGE;
            ctx.fill();
            // Glow
            ctx.beginPath();
            ctx.arc(PIPELINE_X, dotY, 5, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(255,138,30,0.2)";
            ctx.fill();
          }
        }

        // Node circle
        ctx.beginPath();
        ctx.arc(PIPELINE_X, y, NODE_R, 0, Math.PI * 2);
        if (isActive) {
          ctx.fillStyle = ORANGE;
          // Glow ring
          ctx.shadowColor = ORANGE;
          ctx.shadowBlur = 12;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else if (isPast) {
          ctx.fillStyle = "rgba(255,138,30,0.45)";
          ctx.fill();
        } else {
          ctx.strokeStyle = WHITE_LOW;
          ctx.lineWidth = 1;
          ctx.fillStyle = "rgba(255,255,255,0.04)";
          ctx.fill();
          ctx.stroke();
        }

        // Label text
        ctx.textAlign = "left";
        ctx.fillStyle = isActive ? "#ffffff" : isPast ? WHITE_MED : "rgba(255,255,255,0.22)";
        ctx.font = `${isActive ? "600" : "400"} 10px 'SF Mono', 'Fira Code', monospace`;
        ctx.fillText(stage.label, PIPELINE_X + 14, y + 3);

        // Sub label
        ctx.fillStyle = isActive ? "rgba(255,138,30,0.7)" : "rgba(255,255,255,0.14)";
        ctx.font = "8px 'SF Mono', 'Fira Code', monospace";
        ctx.fillText(stage.sub, PIPELINE_X + 14, y + 14);
      });

      rafRef.current = requestAnimationFrame(drawFrame);
    }

    rafRef.current = requestAnimationFrame(drawFrame);
    return () => cancelAnimationFrame(rafRef.current);
  }, [reduce]);

  return (
    <div
      className="relative w-full"
      style={{ aspectRatio: "4/3" }}
      aria-hidden="true"
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ borderRadius: "12px" }}
      />
    </div>
  );
}
