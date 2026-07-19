import { Monogram } from "@/components/ui/monogram";
import { Button } from "@/components/ui/button";
import { MonoLabel } from "@/components/ui/mono-label";
import { SectionHeading, HeadingAccent } from "@/components/ui/section-heading";
import { Panel } from "@/components/ui/panel";
import { StatNumber } from "@/components/ui/stat-number";
import { StatusPill } from "@/components/ui/status-pill";

const colors = [
  { name: "--color-bg", label: "Background" },
  { name: "--color-surface", label: "Surface" },
  { name: "--color-border", label: "Border (hairline)" },
  { name: "--color-text-primary", label: "Text / primary" },
  { name: "--color-text-secondary", label: "Text / secondary" },
  { name: "--color-text-tertiary", label: "Text / tertiary" },
  { name: "--color-accent", label: "Signal Amber (accent)" },
  { name: "--color-live", label: "Status / live" },
  { name: "--color-frozen", label: "Status / frozen" },
];

const typeSteps = [
  { token: "--text-label", sample: "SECTION LABEL", className: "font-mono uppercase" },
  { token: "--text-body", sample: "Body copy sets the baseline for every paragraph on the site." },
  { token: "--text-lead", sample: "Lead copy: hero sub-lines, section intros." },
  { token: "--text-section-heading", sample: "Section heading" },
  { token: "--text-hero", sample: "Hero" },
];

const spacingSteps = [4, 8, 16, 24, 32, 48, 64, 96, 120];

const motionTokens = [
  { token: "--duration-micro", value: "150ms" },
  { token: "--duration-base", value: "300ms" },
  { token: "--duration-reveal", value: "600ms" },
  { token: "--duration-count-up", value: "700ms" },
  { token: "--ease-out-expo", value: "cubic-bezier(0.16, 1, 0.3, 1)" },
  { token: "--ease-out-quart", value: "cubic-bezier(0.25, 1, 0.5, 1)" },
];

export default function StyleTilePage() {
  return (
    <main className="mx-auto max-w-[var(--space-content-max)] px-[var(--space-page-x)] py-16 text-[color:var(--color-text-primary)]">
      <header className="mb-16 flex items-center gap-4">
        <Monogram className="h-10 w-10 text-[color:var(--color-accent)]" />
        <div>
          <h1 className="text-[color:var(--color-text-primary)] font-mono text-sm uppercase tracking-[0.18em]">
            QuantFlow · Style Tile
          </h1>
          <p className="text-[color:var(--color-text-tertiary)] font-mono text-xs">
            Phase 0 · design tokens in context
          </p>
        </div>
      </header>

      {/* Color */}
      <section className="mb-20">
        <h2 className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
          Color
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-3">
          {colors.map((c) => (
            <div
              key={c.name}
              className="rounded-md border border-[color:var(--color-border)] p-4"
            >
              <div
                className="mb-3 h-16 w-full rounded"
                style={{
                  background: `var(${c.name})`,
                  border: "1px solid var(--color-border)",
                }}
              />
              <p className="font-mono text-xs text-[color:var(--color-text-secondary)]">
                {c.name}
              </p>
              <p className="text-xs text-[color:var(--color-text-tertiary)]">
                {c.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Typography */}
      <section className="mb-20">
        <h2 className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
          Typography
        </h2>
        <div className="flex flex-col gap-6 divide-y divide-[color:var(--color-border)]">
          {typeSteps.map((t) => (
            <div key={t.token} className="pt-6 first:pt-0">
              <p
                className={`text-[color:var(--color-text-primary)] ${t.className ?? ""}`}
                style={{ fontSize: `var(${t.token})` }}
              >
                {t.sample}
              </p>
              <p className="mt-2 font-mono text-xs text-[color:var(--color-text-tertiary)]">
                {t.token}
              </p>
            </div>
          ))}
          <div className="pt-6">
            <p
              className="font-serif italic leading-[1.1] pb-1"
              style={{ fontSize: "var(--text-section-heading)" }}
            >
              Knowledge is frozen. Trust is fluid.
            </p>
            <p className="mt-2 font-mono text-xs text-[color:var(--color-text-tertiary)]">
              --font-serif · Cormorant Garamond · one accent use only
            </p>
          </div>
        </div>
      </section>

      {/* Spacing */}
      <section className="mb-20">
        <h2 className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
          Spacing (4px rhythm)
        </h2>
        <div className="flex flex-col gap-2">
          {spacingSteps.map((s) => (
            <div key={s} className="flex items-center gap-4">
              <span className="w-12 shrink-0 font-mono text-xs text-[color:var(--color-text-tertiary)]">
                {s}px
              </span>
              <div
                className="h-3 bg-[color:var(--color-accent)]"
                style={{ width: `${s}px` }}
              />
            </div>
          ))}
        </div>
      </section>

      {/* Motion */}
      <section className="mb-20">
        <h2 className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
          Motion
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {motionTokens.map((m) => (
            <div
              key={m.token}
              className="flex items-center justify-between rounded-md border border-[color:var(--color-border)] px-4 py-3"
            >
              <span className="font-mono text-xs text-[color:var(--color-text-secondary)]">
                {m.token}
              </span>
              <span className="font-mono text-xs text-[color:var(--color-text-tertiary)]">
                {m.value}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Monogram in context */}
      <section>
        <h2 className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
          Monogram
        </h2>
        <div className="flex flex-wrap items-end gap-8">
          {[16, 24, 32, 48, 96].map((size) => (
            <div key={size} className="flex flex-col items-center gap-2">
              <Monogram
                style={{ width: size, height: size }}
                className="text-[color:var(--color-accent)]"
              />
              <span className="font-mono text-[10px] text-[color:var(--color-text-tertiary)]">
                {size}px
              </span>
            </div>
          ))}
          <div className="flex flex-col items-center gap-2 rounded-md bg-[color:var(--color-text-primary)] p-3">
            <Monogram className="h-8 w-8 text-[color:var(--color-bg)]" />
            <span className="font-mono text-[10px] text-[color:var(--color-bg)]">
              on light
            </span>
          </div>
        </div>
      </section>

      {/* Primitives */}
      <section className="mt-20">
        <h2 className="mb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
          Primitives
        </h2>

        <div className="mb-10">
          <MonoLabel className="mb-4">Buttons</MonoLabel>
          <div className="flex flex-wrap items-center gap-3">
            <Button>Request Private Access</Button>
            <Button variant="outline">Explore QuantFlow</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="link">Link</Button>
            <Button disabled>Disabled</Button>
          </div>
        </div>

        <div className="mb-10">
          <MonoLabel className="mb-4">Section heading</MonoLabel>
          <SectionHeading>
            Trust <HeadingAccent>architecture</HeadingAccent>
          </SectionHeading>
        </div>

        <div className="mb-10">
          <MonoLabel className="mb-4">Status pills</MonoLabel>
          <div className="flex flex-wrap gap-3">
            <StatusPill status="live" label="LIVE" />
            <StatusPill status="frozen" label="FROZEN" />
            <StatusPill status="stabilized" label="STABILIZED" />
          </div>
        </div>

        <div className="mb-10">
          <MonoLabel className="mb-4">Stat numbers</MonoLabel>
          <div className="flex flex-wrap gap-10">
            <StatNumber value={0.586} label="Win rate" suffix="" />
            <StatNumber value={1.16} label="Profit factor" />
            <StatNumber value={29} label="Sample size (n)" />
            <StatNumber value={20} label="Min trades for confidence" />
          </div>
        </div>

        <div>
          <MonoLabel className="mb-4">Panel</MonoLabel>
          <Panel className="max-w-sm p-6">
            <p className="text-[color:var(--color-text-secondary)]">
              Elevated surface, used sparingly, only where elevation
              communicates real hierarchy.
            </p>
          </Panel>
        </div>
      </section>
    </main>
  );
}
