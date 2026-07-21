import { getTranslations } from "next-intl/server";
import { HeroSignalFlow } from "./hero-signal-flow";

export async function HeroSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "hero" });

  return (
    <section
      aria-labelledby="hero-heading"
      className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden px-[var(--space-page-x)] pt-28 pb-20 md:flex-row md:justify-between md:gap-8"
    >
      {/* ── Ambient glow — single, purposeful ── */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute rounded-full"
          style={{
            width: "800px",
            height: "800px",
            left: "-10%",
            top: "0%",
            background: "radial-gradient(circle, rgba(255,138,30,0.07) 0%, transparent 65%)",
            filter: "blur(80px)",
          }}
        />
      </div>

      {/* ── Left column: headline + CTA ── */}
      <div className="relative z-10 flex flex-col items-start gap-7 md:max-w-[54%]" style={{ animation: "qf-hero-enter 0.8s cubic-bezier(0.22,1,0.36,1) both" }}>
        {/* Live status pill */}
        <div
          className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 max-w-full overflow-hidden"
          style={{
            borderColor: "rgba(255,138,30,0.2)",
            background: "rgba(255,138,30,0.06)",
            backdropFilter: "blur(12px)",
          }}
        >
          <span
            aria-hidden="true"
            className="size-1.5 shrink-0 rounded-full"
            style={{
              backgroundColor: "var(--color-accent)",
              boxShadow: "0 0 6px var(--color-accent)",
              animation: "qf-blink 2s ease-in-out infinite",
            }}
          />
          <span
            className="font-mono text-[10px] uppercase tracking-[0.18em] truncate"
            style={{ color: "var(--color-accent)" }}
          >
            {t("statusLive")} · {t("statusMarket")} · {t("statusStrategy")}
          </span>
        </div>

        {/* Main headline */}
        <h1
          id="hero-heading"
          className="max-w-[18ch]"
          style={{
            fontSize: "var(--text-hero)",
            lineHeight: "var(--text-hero--line-height)",
            letterSpacing: "var(--text-hero--letter-spacing)",
            fontWeight: 500,
            color: "var(--color-text-primary)",
          }}
        >
          {t("tagline1")}
          <br />
          <span
            style={{
              fontFamily: "var(--font-serif)",
              fontStyle: "italic",
              fontWeight: 400,
              display: "block",
              paddingBottom: "0.1em",
              background: "linear-gradient(135deg, #ffffff 0%, rgba(255,180,94,0.85) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {t("tagline2")}
          </span>
        </h1>

        {/* Subline */}
        <p
          className="max-w-[52ch]"
          style={{
            fontSize: "var(--text-lead)",
            lineHeight: "var(--text-lead--line-height)",
            color: "var(--color-text-secondary)",
          }}
        >
          {t("subline")}
        </p>

        {/* Stats row */}
        <div className="flex flex-wrap items-center gap-6 py-2">
          {[
            { value: "58.6%", label: "Win rate" },
            { value: "1.16×", label: "Profit factor" },
            { value: "29", label: "Trades tracked" },
          ].map(({ value, label }) => (
            <div key={label} className="flex flex-col gap-0.5">
              <span
                className="font-mono tabular-nums"
                style={{
                  fontSize: "clamp(1.25rem, 2vw, 1.75rem)",
                  fontWeight: 600,
                  letterSpacing: "-0.03em",
                  color: "var(--color-accent)",
                }}
              >
                {value}
              </span>
              <span
                className="font-mono uppercase"
                style={{
                  fontSize: "10px",
                  letterSpacing: "0.14em",
                  color: "var(--color-text-tertiary)",
                }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>

      </div>

      {/* ── Right column: signal flow visualization ── */}
      <div className="relative z-10 hidden md:flex flex-col items-end w-full max-w-[480px] shrink-0" style={{ animation: "qf-hero-enter 0.9s 0.15s cubic-bezier(0.22,1,0.36,1) both" }}>
        <div
          className="w-full rounded-2xl overflow-hidden"
          style={{
            background: "rgba(8,8,10,0.6)",
            border: "1px solid rgba(255,255,255,0.07)",
            backdropFilter: "blur(24px)",
            boxShadow: "0 24px 80px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
          }}
        >
          {/* Window chrome */}
          <div
            className="flex items-center gap-2 px-4 py-3"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
          >
            <div className="flex gap-1.5">
              <span className="size-2 rounded-full" style={{ background: "rgba(255,95,87,0.5)" }} />
              <span className="size-2 rounded-full" style={{ background: "rgba(254,188,46,0.5)" }} />
              <span className="size-2 rounded-full" style={{ background: "rgba(40,200,64,0.5)" }} />
            </div>
            <span
              className="font-mono text-[10px] uppercase tracking-[0.14em] ml-1"
              style={{ color: "rgba(255,255,255,0.2)" }}
            >
              signal propagation · live
            </span>
            <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em]" style={{ color: "var(--color-accent)" }}>
              <span className="size-1.5 rounded-full" style={{ backgroundColor: "var(--color-accent)", boxShadow: "0 0 5px var(--color-accent)", animation: "qf-blink 2s ease-in-out infinite" }} />
              running
            </span>
          </div>
          <div className="p-4">
            <HeroSignalFlow />
          </div>
        </div>
      </div>

      {/* ── Bottom scroll indicator ── */}
      <div
        aria-hidden="true"
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
        style={{ opacity: 0.4 }}
      >
        <span
          className="font-mono uppercase"
          style={{ fontSize: "9px", letterSpacing: "0.2em", color: "var(--color-text-tertiary)" }}
        >
          Scroll
        </span>
        <div
          className="h-8 w-px rounded-full"
          style={{
            background: "linear-gradient(to bottom, var(--color-accent), transparent)",
            animation: "qf-pulse-glow 2s ease-in-out infinite",
          }}
        />
      </div>
    </section>
  );
}
