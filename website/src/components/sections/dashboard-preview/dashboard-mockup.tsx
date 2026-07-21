"use client";

import { useState, useEffect, useRef } from "react";
import { DASHBOARD_COLORS } from "./dashboard-colors";

const TABS = ["Overview", "Positions", "Strategies", "Signals"] as const;
type Tab = (typeof TABS)[number];

const METRICS = [
  { label: "Portfolio Value", value: "₽1,048,230", sub: "+0.59% today", color: undefined as string | undefined },
  { label: "PnL Today", value: "+₽6,140", sub: "vs yesterday", color: DASHBOARD_COLORS.long },
  { label: "Max Drawdown", value: "−4.8%", sub: "within limits", color: undefined },
  { label: "Sharpe Ratio", value: "1.34", sub: "90-day rolling", color: undefined },
];

const POSITIONS = [
  { ticker: "SBER", side: "LONG" as const, confidence: 0.71, pnlPct: "+1.9%", size: "₽124,400", entry: "₽272.80" },
  { ticker: "LKOH", side: "LONG" as const, confidence: 0.58, pnlPct: "+0.4%", size: "₽88,200", entry: "₽6,812.00" },
  { ticker: "GAZP", side: "SHORT" as const, confidence: 0.42, pnlPct: "−0.6%", size: "₽42,100", entry: "₽162.30" },
];

const STRATEGIES = [
  { id: "osc_range_moex_d1_fwd", market: "MOEX", tf: "D1", status: "LIVE", conf: 0.71, trades: 29, wr: "58.6%" },
  { id: "ab_trend_moex_d1", market: "MOEX", tf: "D1", status: "LIVE", conf: 0.58, trades: 22, wr: "54.5%" },
  { id: "wrd_sar_moex_d1", market: "MOEX", tf: "D1", status: "FROZEN", conf: 0.28, trades: 31, wr: "41.9%" },
  { id: "ob_bybit_h4", market: "CRYPTO", tf: "H4", status: "PAPER", conf: 0.48, trades: 11, wr: "45.5%" },
];

const SIGNALS = [
  { time: "14:32:07", strategy: "osc_range_moex_d1_fwd", ticker: "SBER", dir: "LONG", conf: 0.71, status: "EXECUTED" },
  { time: "14:18:44", strategy: "ab_trend_moex_d1", ticker: "LKOH", dir: "LONG", conf: 0.58, status: "EXECUTED" },
  { time: "13:55:21", strategy: "wrd_sar_moex_d1", ticker: "GAZP", dir: "SHORT", conf: 0.28, status: "BLOCKED" },
  { time: "12:01:03", strategy: "osc_range_moex_d1_fwd", ticker: "SBER", dir: "LONG", conf: 0.66, status: "CLOSED" },
  { time: "09:32:00", strategy: "ab_trend_moex_d1", ticker: "VTBR", dir: "SHORT", conf: 0.41, status: "BLOCKED" },
];

const EQUITY_POINTS_RAW = [
  0, 1.2, -0.4, 2.1, 3.4, 2.8, 4.1, 5.6, 4.8, 6.3, 7.1, 6.4, 7.9, 7.2, 8.1, 8.3,
];

function EquityChart({ animated }: { animated: boolean }) {
  const N = EQUITY_POINTS_RAW.length;
  const minV = Math.min(...EQUITY_POINTS_RAW);
  const maxV = Math.max(...EQUITY_POINTS_RAW);
  const range = maxV - minV || 1;
  const W = 600;
  const H = 80;
  const PAD = 4;

  const pts = EQUITY_POINTS_RAW.map((v, i) => ({
    x: PAD + (i / (N - 1)) * (W - PAD * 2),
    y: H - PAD - ((v - minV) / range) * (H - PAD * 2),
  }));

  const polyline = pts.map((p) => `${p.x},${p.y}`).join(" ");
  const area = `M${pts[0].x},${H} ` + pts.map((p) => `L${p.x},${p.y}`).join(" ") + ` L${pts[N - 1].x},${H} Z`;
  const totalLen = 680;

  return (
    <div className="px-5 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em]" style={{ color: "rgba(255,255,255,0.28)" }}>
          Equity curve · 29-trade fwd test
        </span>
        <span className="font-mono text-[11px]" style={{ color: DASHBOARD_COLORS.long }}>
          +8.3% total
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[72px] w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={DASHBOARD_COLORS.accent} stopOpacity="0.2" />
            <stop offset="100%" stopColor={DASHBOARD_COLORS.accent} stopOpacity="0" />
          </linearGradient>
          <filter id="lineglow">
            <feGaussianBlur stdDeviation="1.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <path d={area} fill="url(#eqGrad)" />
        <polyline
          points={polyline}
          fill="none"
          stroke={DASHBOARD_COLORS.accent}
          strokeWidth="1.5"
          strokeLinejoin="round"
          filter="url(#lineglow)"
          style={animated ? {
            strokeDasharray: totalLen,
            strokeDashoffset: 0,
            animation: "eq-draw 1.4s cubic-bezier(0.16,1,0.3,1) forwards",
          } : undefined}
        />
        <circle cx={pts[N - 1].x} cy={pts[N - 1].y} r="3" fill={DASHBOARD_COLORS.accent} />
        <circle cx={pts[N - 1].x} cy={pts[N - 1].y} r="6" fill={DASHBOARD_COLORS.accent} opacity="0.18" />
      </svg>
    </div>
  );
}

function ConfBar({ value, max = 1, color }: { value: number; max?: number; color: string }) {
  return (
    <div className="h-1 w-16 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.08)" }}>
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${(value / max) * 100}%`, background: color }} />
    </div>
  );
}

function NotificationToast({ msg, onDone }: { msg: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3200);
    return () => clearTimeout(t);
  }, [onDone]);

  return (
    <div
      className="flex items-center gap-2 rounded-lg px-3 py-2 font-mono text-[11px] pointer-events-none"
      style={{
        background: "rgba(12,12,14,0.92)",
        border: "1px solid rgba(255,138,30,0.25)",
        backdropFilter: "blur(16px)",
        color: "rgba(255,255,255,0.75)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
        animation: "toast-in 0.35s cubic-bezier(0.16,1,0.3,1) forwards",
      }}
    >
      <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: DASHBOARD_COLORS.accent, boxShadow: `0 0 4px ${DASHBOARD_COLORS.accent}` }} />
      {msg}
    </div>
  );
}

export function DashboardMockup() {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [mounted, setMounted] = useState(false);
  const [hoveredRow, setHoveredRow] = useState<number | null>(null);
  const [notification, setNotification] = useState<string | null>(null);
  const [stratFilter, setStratFilter] = useState<"all" | "live" | "frozen">("all");
  const notifQueue = useRef([
    "Signal: SBER LONG · conf 0.71",
    "Strategy osc_range frozen · conf below 0.30",
    "Position LKOH closed · +0.4%",
    "New signal: VTBR SHORT · blocked",
  ]);
  const notifIdx = useRef(0);

  useEffect(() => {
    setMounted(true);
    const interval = setInterval(() => {
      const msg = notifQueue.current[notifIdx.current % notifQueue.current.length];
      setNotification(msg);
      notifIdx.current++;
    }, 6000);
    return () => clearInterval(interval);
  }, []);

  const filteredStrats = STRATEGIES.filter((s) => {
    if (stratFilter === "live") return s.status === "LIVE";
    if (stratFilter === "frozen") return s.status === "FROZEN";
    return true;
  });

  return (
    <>
      <style>{`
        @keyframes eq-draw {
          from { stroke-dashoffset: 680; }
          to { stroke-dashoffset: 0; }
        }
        @keyframes toast-in {
          from { opacity: 0; transform: translateY(-8px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes row-pulse {
          0%, 100% { background: transparent; }
          50% { background: rgba(255,138,30,0.03); }
        }
      `}</style>

      <div
        className="overflow-hidden rounded-xl relative"
        style={{
          background: "#080808",
          border: "1px solid rgba(255,255,255,0.07)",
          boxShadow: "0 32px 100px rgba(0,0,0,0.7), 0 4px 16px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)",
        }}
      >
        {/* Notification toast */}
        {notification && (
          <div className="absolute top-14 right-4 z-20">
            <NotificationToast msg={notification} onDone={() => setNotification(null)} />
          </div>
        )}

        {/* ── Window chrome ── */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.015)" }}
        >
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <span className="size-2.5 rounded-full" style={{ background: "#ff5f57" }} />
              <span className="size-2.5 rounded-full" style={{ background: "#febc2e" }} />
              <span className="size-2.5 rounded-full" style={{ background: "#28c840" }} />
            </div>
            <span className="font-mono text-[11px] uppercase tracking-[0.14em]" style={{ color: "rgba(255,255,255,0.28)" }}>
              QuantFlow / Dashboard
            </span>
          </div>
          <span className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.1em]" style={{ color: DASHBOARD_COLORS.accent }}>
            <span className="size-1.5 rounded-full" style={{ backgroundColor: DASHBOARD_COLORS.accent, boxShadow: `0 0 5px ${DASHBOARD_COLORS.accent}`, animation: "qf-blink 2.5s ease-in-out infinite" }} />
            bot_status: running
          </span>
        </div>

        {/* ── Tab bar ── */}
        <div
          className="flex items-center gap-0 px-5"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.01)" }}
        >
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="relative px-4 py-2.5 font-mono text-[11px] uppercase tracking-[0.1em] transition-colors duration-150 cursor-pointer"
              style={{
                color: activeTab === tab ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.28)",
                background: "none",
                border: "none",
                borderBottom: activeTab === tab ? `2px solid ${DASHBOARD_COLORS.accent}` : "2px solid transparent",
                outline: "none",
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* ── OVERVIEW TAB ── */}
        {activeTab === "Overview" && (
          <>
            {/* Metric tiles */}
            <div className="grid grid-cols-2 sm:grid-cols-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              {METRICS.map((m, i) => (
                <div
                  key={m.label}
                  className="flex flex-col gap-1.5 px-5 py-4 transition-colors duration-200"
                  style={{
                    borderRight: i < 3 ? "1px solid rgba(255,255,255,0.06)" : undefined,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                >
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em]" style={{ color: "rgba(255,255,255,0.28)" }}>
                    {m.label}
                  </span>
                  <span
                    className="font-mono text-[18px] tabular-nums font-semibold"
                    style={{ letterSpacing: "-0.02em", color: m.color ?? "rgba(255,255,255,0.9)" }}
                  >
                    {m.value}
                  </span>
                  {m.sub && (
                    <span className="font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.22)" }}>
                      {m.sub}
                    </span>
                  )}
                </div>
              ))}
            </div>

            {/* Equity chart */}
            <EquityChart animated={mounted} />

            {/* Strategy status */}
            <div className="px-5 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em]" style={{ color: "rgba(255,255,255,0.28)" }}>
                Active strategies
              </span>
              <div className="mt-2 flex flex-col gap-1.5">
                {STRATEGIES.filter((s) => s.status !== "FROZEN").map((s) => (
                  <div key={s.id} className="flex items-center gap-3 rounded-md px-2 py-1 transition-colors duration-150" style={{ cursor: "default" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                  >
                    <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: s.status === "LIVE" ? DASHBOARD_COLORS.accent : "rgba(255,255,255,0.15)", boxShadow: s.status === "LIVE" ? `0 0 4px ${DASHBOARD_COLORS.accent}` : undefined }} />
                    <span className="font-mono text-[11px] flex-1" style={{ color: "rgba(255,255,255,0.55)" }}>{s.id}</span>
                    <span className="font-mono text-[10px] uppercase" style={{ color: s.status === "LIVE" ? DASHBOARD_COLORS.accent : "rgba(255,255,255,0.22)" }}>{s.status}</span>
                    <ConfBar value={s.conf} color={DASHBOARD_COLORS.accent} />
                    <span className="font-mono text-[10px] w-8 text-right tabular-nums" style={{ color: "rgba(255,255,255,0.32)" }}>{Math.round(s.conf * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Positions */}
            <div className="px-5 py-3">
              {POSITIONS.map((p, i) => (
                <div
                  key={p.ticker}
                  className="flex items-center justify-between py-2.5 font-mono text-[12px] rounded-md px-2 -mx-2 transition-colors duration-150"
                  style={{ borderBottom: i < POSITIONS.length - 1 ? "1px solid rgba(255,255,255,0.04)" : undefined, cursor: "default" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.02)"; setHoveredRow(i); }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; setHoveredRow(null); }}
                >
                  <span className="w-12 font-semibold" style={{ color: "rgba(255,255,255,0.9)" }}>{p.ticker}</span>
                  <span className="w-14 text-center rounded px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em]" style={{ color: p.side === "LONG" ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short, background: p.side === "LONG" ? "rgba(0,192,118,0.1)" : "rgba(246,70,93,0.1)" }}>{p.side}</span>
                  <span style={{ color: "rgba(255,255,255,0.28)" }}>conf {p.confidence.toFixed(2)}</span>
                  <ConfBar value={p.confidence} color={p.side === "LONG" ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short} />
                  <span style={{ color: p.pnlPct.startsWith("+") ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short, fontWeight: 600 }}>{p.pnlPct}</span>
                  {hoveredRow === i && (
                    <span className="font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.28)" }}>{p.size}</span>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {/* ── POSITIONS TAB ── */}
        {activeTab === "Positions" && (
          <div className="px-5 py-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em]" style={{ color: "rgba(255,255,255,0.28)" }}>
                Open positions · MOEX
              </span>
              <span className="font-mono text-[10px]" style={{ color: DASHBOARD_COLORS.long }}>+₽6,140 today</span>
            </div>
            <div className="flex flex-col gap-1">
              {/* Table header */}
              <div className="grid grid-cols-6 gap-2 pb-2 font-mono text-[9px] uppercase tracking-[0.12em]" style={{ color: "rgba(255,255,255,0.2)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                <span>Ticker</span><span>Side</span><span>Entry</span><span>Size</span><span className="col-span-1">Conf</span><span className="text-right">PnL</span>
              </div>
              {POSITIONS.map((p, i) => (
                <div
                  key={p.ticker}
                  className="grid grid-cols-6 gap-2 py-2.5 font-mono text-[11px] rounded-md px-2 -mx-2 transition-all duration-150"
                  style={{ borderBottom: i < POSITIONS.length - 1 ? "1px solid rgba(255,255,255,0.04)" : undefined, cursor: "default" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.025)"; e.currentTarget.style.borderLeft = `2px solid ${p.side === "LONG" ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short}`; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; e.currentTarget.style.borderLeft = ""; }}
                >
                  <span className="font-semibold" style={{ color: "rgba(255,255,255,0.9)" }}>{p.ticker}</span>
                  <span className="rounded px-1.5 py-0.5 h-fit text-[9px] uppercase tracking-[0.08em] self-center" style={{ color: p.side === "LONG" ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short, background: p.side === "LONG" ? "rgba(0,192,118,0.1)" : "rgba(246,70,93,0.1)" }}>{p.side}</span>
                  <span style={{ color: "rgba(255,255,255,0.55)" }}>{p.entry}</span>
                  <span style={{ color: "rgba(255,255,255,0.42)" }}>{p.size}</span>
                  <span style={{ color: DASHBOARD_COLORS.accent }}>{Math.round(p.confidence * 100)}%</span>
                  <span className="text-right font-semibold" style={{ color: p.pnlPct.startsWith("+") ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short }}>{p.pnlPct}</span>
                </div>
              ))}
            </div>
            {/* Summary */}
            <div className="mt-4 rounded-lg px-4 py-3 flex items-center justify-between" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em]" style={{ color: "rgba(255,255,255,0.28)" }}>Total exposure</span>
              <span className="font-mono text-[13px] tabular-nums" style={{ color: "rgba(255,255,255,0.75)" }}>₽254,700</span>
            </div>
          </div>
        )}

        {/* ── STRATEGIES TAB ── */}
        {activeTab === "Strategies" && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-3">
              {(["all", "live", "frozen"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setStratFilter(f)}
                  className="font-mono text-[10px] uppercase tracking-[0.1em] px-2.5 py-1 rounded-md transition-all duration-150"
                  style={{
                    background: stratFilter === f ? "rgba(255,138,30,0.1)" : "rgba(255,255,255,0.04)",
                    border: `1px solid ${stratFilter === f ? "rgba(255,138,30,0.3)" : "rgba(255,255,255,0.07)"}`,
                    color: stratFilter === f ? DASHBOARD_COLORS.accent : "rgba(255,255,255,0.35)",
                    cursor: "pointer",
                  }}
                >
                  {f}
                </button>
              ))}
              <span className="ml-auto font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.22)" }}>{filteredStrats.length} strategies</span>
            </div>
            <div className="flex flex-col gap-0">
              <div className="grid grid-cols-5 gap-2 pb-2 font-mono text-[9px] uppercase tracking-[0.12em]" style={{ color: "rgba(255,255,255,0.2)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                <span className="col-span-2">Strategy</span><span>Status</span><span>Trades</span><span className="text-right">Confidence</span>
              </div>
              {filteredStrats.map((s, i) => (
                <div
                  key={s.id}
                  className="grid grid-cols-5 gap-2 py-2.5 font-mono text-[11px] rounded-md px-2 -mx-2 transition-all duration-150"
                  style={{ borderBottom: i < filteredStrats.length - 1 ? "1px solid rgba(255,255,255,0.04)" : undefined, cursor: "default", opacity: s.status === "FROZEN" ? 0.55 : 1 }}
                  onMouseEnter={(e) => { if (s.status !== "FROZEN") e.currentTarget.style.background = "rgba(255,255,255,0.025)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                >
                  <span className="col-span-2 truncate" style={{ color: "rgba(255,255,255,0.7)" }}>{s.id}</span>
                  <span style={{ color: s.status === "LIVE" ? DASHBOARD_COLORS.accent : s.status === "PAPER" ? "rgba(255,255,255,0.45)" : "rgba(255,255,255,0.25)" }}>
                    {s.status}
                  </span>
                  <span style={{ color: "rgba(255,255,255,0.42)" }}>{s.trades}</span>
                  <div className="flex items-center gap-2 justify-end">
                    <ConfBar value={s.conf} color={s.status === "LIVE" ? DASHBOARD_COLORS.accent : "rgba(255,255,255,0.2)"} />
                    <span className="w-8 text-right tabular-nums" style={{ color: "rgba(255,255,255,0.35)" }}>{Math.round(s.conf * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── SIGNALS TAB ── */}
        {activeTab === "Signals" && (
          <div className="px-5 py-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em]" style={{ color: "rgba(255,255,255,0.28)" }}>Signal log · today</span>
              <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase" style={{ color: DASHBOARD_COLORS.accent }}>
                <span className="size-1.5 rounded-full" style={{ backgroundColor: DASHBOARD_COLORS.accent, animation: "qf-blink 2s ease-in-out infinite" }} />
                live
              </span>
            </div>
            <div className="flex flex-col gap-0">
              {SIGNALS.map((sig, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 py-2.5 font-mono text-[11px] rounded-md px-2 -mx-2 transition-all duration-150"
                  style={{ borderBottom: i < SIGNALS.length - 1 ? "1px solid rgba(255,255,255,0.04)" : undefined, cursor: "default" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.025)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                >
                  <span style={{ color: "rgba(255,255,255,0.2)", flexShrink: 0 }}>{sig.time}</span>
                  <span className="flex-1 truncate" style={{ color: "rgba(255,255,255,0.45)" }}>{sig.strategy}</span>
                  <span className="font-semibold" style={{ color: "rgba(255,255,255,0.8)" }}>{sig.ticker}</span>
                  <span className="text-[9px] uppercase tracking-[0.08em] rounded px-1.5 py-0.5" style={{ color: sig.dir === "LONG" ? DASHBOARD_COLORS.long : DASHBOARD_COLORS.short, background: sig.dir === "LONG" ? "rgba(0,192,118,0.1)" : "rgba(246,70,93,0.1)" }}>{sig.dir}</span>
                  <span className="text-[10px]" style={{ color: "rgba(255,255,255,0.28)" }}>{Math.round(sig.conf * 100)}%</span>
                  <span
                    className="text-[9px] uppercase tracking-[0.08em] rounded px-1.5 py-0.5"
                    style={{
                      color: sig.status === "EXECUTED" ? DASHBOARD_COLORS.long : sig.status === "BLOCKED" ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.45)",
                      background: sig.status === "EXECUTED" ? "rgba(0,192,118,0.08)" : "rgba(255,255,255,0.04)",
                    }}
                  >
                    {sig.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
