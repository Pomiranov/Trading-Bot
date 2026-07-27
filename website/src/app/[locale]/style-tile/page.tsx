import { BrandMark } from "@/components/ui/brand-mark";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { ArrowLink } from "@/components/ui/arrow-link";
import { MonoLabel } from "@/components/ui/mono-label";
import { SectionHeading } from "@/components/ui/section-heading";
import { Surface } from "@/components/ui/surface";
import { Stat } from "@/components/ui/stat";
import { StatusChip } from "@/components/ui/status-chip";
import { STRATEGY_STAGES, STRATEGY_STAGE_TONE } from "@/lib/strategy-status";

/**
 * Internal design reference. Not linked from the site; it exists so the token
 * set can be reviewed in one place and so every primitive has at least one
 * call site outside a section (which is how MonoLabel and SectionHeading
 * previously drifted out of use while sections hand-rolled their own).
 */
const colors = [
  { name: "--color-bg", label: "Background" },
  { name: "--color-surface", label: "Surface" },
  { name: "--color-panel", label: "Panel" },
  { name: "--color-paper", label: "Paper (inverted band)" },
  { name: "--color-border", label: "Border · hairline" },
  { name: "--color-border-strong", label: "Border · interactive (3.0:1)" },
  { name: "--color-text-primary", label: "Text · primary (20.4:1)" },
  { name: "--color-text-secondary", label: "Text · secondary (10.4:1)" },
  { name: "--color-text-tertiary", label: "Text · tertiary (6.5:1)" },
  { name: "--color-text-quaternary", label: "Text · floor (4.9:1)" },
  { name: "--color-panel-raised", label: "Panel · raised / hover" },
  { name: "--color-accent", label: "Accent · action (white, 20.4:1)" },
  { name: "--color-success", label: "Success · healthy (11.6:1)" },
  { name: "--color-danger", label: "Danger · risk (8.9:1)" },
  { name: "--color-neutral", label: "Neutral · inactive (5.6:1)" },
];

const typeSteps = [
  { token: "--text-label", sample: "SECTION LABEL", className: "font-mono uppercase" },
  { token: "--text-caption", sample: "Caption: table cells, metadata, disclosure lines." },
  { token: "--text-body", sample: "Body copy sets the baseline for every paragraph." },
  { token: "--text-lead", sample: "Lead copy: hero sublines and section intros." },
  { token: "--text-h3", sample: "Card heading" },
  { token: "--text-section-heading", sample: "Section heading" },
  { token: "--text-hero", sample: "Hero" },
];

const rhythm = [
  { token: "--space-section-y-tight", label: "tight · bound sections" },
  { token: "--space-section-y", label: "default" },
  { token: "--space-section-y-major", label: "major · new movement" },
];

const motionTokens = [
  { token: "--duration-micro", value: "150ms" },
  { token: "--duration-base", value: "300ms" },
  { token: "--duration-reveal", value: "600ms" },
  { token: "--ease-out-expo", value: "cubic-bezier(0.16, 1, 0.3, 1)" },
  { token: "--ease-out-quart", value: "cubic-bezier(0.25, 1, 0.5, 1)" },
];

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-6 border-t border-[color:var(--color-border)] pt-10">
      <MonoLabel>{title}</MonoLabel>
      {children}
    </section>
  );
}

export default function StyleTilePage() {
  return (
    <main className="mx-auto flex max-w-[var(--space-content-max)] flex-col gap-14 px-[var(--space-page-x)] py-16 text-[color:var(--color-text-primary)]">
      <header className="flex items-center gap-4">
        <BrandMark size="lg" className="text-[color:var(--color-accent)]" />
        <div className="flex flex-col gap-1">
          <h1 className="font-mono text-[length:var(--text-caption)] tracking-[0.18em] uppercase">
            Quant · Style Tile
          </h1>
          <p className="font-mono text-[length:var(--text-label)] text-[color:var(--color-text-tertiary)]">
            design tokens in context
          </p>
        </div>
      </header>

      <Block title="Colour">
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {colors.map((c) => (
            <li key={c.name} className="flex items-center gap-3">
              <span
                className="size-10 shrink-0 rounded-[var(--radius-md)] border border-[color:var(--color-border)]"
                style={{ background: `var(${c.name})` }}
              />
              <span className="flex flex-col">
                <code className="font-mono text-[length:var(--text-label)] text-[color:var(--color-text-secondary)]">
                  {c.name}
                </code>
                <span className="text-[length:var(--text-caption)] text-[color:var(--color-text-quaternary)]">
                  {c.label}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Typography">
        <ul className="flex flex-col gap-6">
          {typeSteps.map((step) => (
            <li key={step.token} className="flex flex-col gap-1.5">
              <code className="font-mono text-[length:var(--text-label)] text-[color:var(--color-text-quaternary)]">
                {step.token}
              </code>
              <p
                className={step.className}
                style={{ fontSize: `var(${step.token})`, lineHeight: 1.2 }}
              >
                {step.sample}
              </p>
            </li>
          ))}
          <li>
            <SectionHeading>Section heading</SectionHeading>
          </li>
        </ul>
      </Block>

      <Block title="Vertical rhythm">
        <ul className="flex flex-col gap-3">
          {rhythm.map((r) => (
            <li key={r.token} className="flex items-center gap-4">
              <span
                className="block bg-[color:var(--color-accent)]"
                style={{ height: `var(${r.token})`, width: "3px" }}
              />
              <span className="flex flex-col">
                <code className="font-mono text-[length:var(--text-label)] text-[color:var(--color-text-secondary)]">
                  {r.token}
                </code>
                <span className="text-[length:var(--text-caption)] text-[color:var(--color-text-quaternary)]">
                  {r.label}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Surfaces">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {(["flat", "raised", "glass", "featured"] as const).map((variant) => (
            <Surface key={variant} variant={variant} className="p-6">
              <code className="font-mono text-[length:var(--text-label)] text-[color:var(--color-text-secondary)]">
                {variant}
              </code>
            </Surface>
          ))}
        </div>
      </Block>

      <Block title="Controls">
        <div className="flex flex-wrap items-center gap-4">
          <Button>Primary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button size="sm">Small</Button>
          <ButtonLink href="#">Link as button</ButtonLink>
          <ArrowLink href="#">Arrow link</ArrowLink>
        </div>
      </Block>

      <Block title="Status">
        <div className="flex flex-wrap items-center gap-3">
          {STRATEGY_STAGES.map((stage) => (
            <StatusChip key={stage} tone={STRATEGY_STAGE_TONE[stage]} label={stage} />
          ))}
          <StatusChip tone="danger" label="blocked" />
          <StatusChip tone="success" label="active" detail="sandbox by default" />
        </div>
      </Block>

      <Block title="Figures">
        {/* Only configured limits and system constants are ever shown as
            figures on this site — never performance results. */}
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <Stat value="5%" label="per position" />
          <Stat value="2%" label="daily loss" />
          <Stat value="0.20" label="signal floor" />
          <Stat value="0.95" label="upper bound" size="sm" />
        </div>
      </Block>

      <Block title="Motion">
        <ul className="flex flex-col gap-2">
          {motionTokens.map((m) => (
            <li key={m.token} className="flex flex-wrap gap-x-4 font-mono text-[length:var(--text-caption)]">
              <code className="text-[color:var(--color-text-secondary)]">{m.token}</code>
              <span className="text-[color:var(--color-text-quaternary)]">{m.value}</span>
            </li>
          ))}
        </ul>
      </Block>
    </main>
  );
}
