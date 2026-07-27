import { Monogram } from "@/components/ui/monogram";
import { MonoLabel } from "@/components/ui/mono-label";
import { StatusPill } from "@/components/ui/status-pill";

interface HeroVisualProps {
  /** Panel title — names what the object is, e.g. "Путь решения". */
  title: string;
  /** Mode badge. Honest: the product starts in the sandbox. */
  mode: string;
  /** The six pipeline stages, in order. */
  steps: readonly string[];
  /** Caption stating plainly that this is a schematic. */
  caption: string;
}

/**
 * The hero's right-hand visual: a live, monochrome system object.
 *
 * This replaces the generated-video hero. The video was rejected as too raw,
 * and it also cost a 1.9 MB gitignored asset that resolved to nothing on CI —
 * meaning the poster was the real hero everywhere except one developer's
 * machine. A composed static object is both what the owner asked for and the
 * only version that is identical in every environment.
 *
 * Deliberately claim-free. There is no chart, no curve, no figure and no
 * percentage anywhere in here: the composition is the aperture mark plus the
 * *names* of the six pipeline stages, each of which is a real module in
 * bot/. A rising line or a win-rate readout would be a performance claim even
 * captioned as illustrative, which is exactly what the previous hero was
 * corrected for.
 *
 * Pure CSS/SVG, server-rendered, no client JS, no external asset — so it also
 * cannot regress LCP the way an autoplaying video source selection could.
 *
 * ── Motion ──
 *
 * The panel is animated, but every loop is CSS on an SVG child: the rings
 * breathe, the exit vector's dashes flow outward, the exit node pings, and one
 * faint trace crosses the aperture every 14s. All four are compositor-only
 * (`opacity` / `transform` / `stroke-dashoffset`), so this component still
 * renders as pure HTML with zero client JS and cannot shift layout.
 *
 * Deliberately absent: anything that would turn the instrument into a chart.
 * No rising line, no plotted series, no counter, no figure. A moving line on a
 * trading site is a performance claim regardless of the caption under it.
 *
 * Keyframes and the reduced-motion contract live beside each other in
 * globals.css under "Hero instrument motion".
 */
export function HeroVisual({ title, mode, steps, caption }: HeroVisualProps) {
  return (
    <figure className="m-0 flex min-w-0 flex-col gap-4">
      <div className="relative overflow-hidden rounded-[var(--radius-lg)] border border-[color:var(--color-border)] bg-[color:var(--color-panel)] shadow-[0_24px_80px_-32px_rgba(0,0,0,0.9)]">
        {/* ── Chrome ── */}
        <div className="flex items-center gap-3 border-b border-[color:var(--color-border)] px-5 py-3.5">
          <Monogram className="size-4 shrink-0 text-[color:var(--color-text-secondary)]" />
          <MonoLabel as="span">{title}</MonoLabel>
          <span className="ml-auto">
            <StatusPill tone="muted" label={mode} />
          </span>
        </div>

        {/* ── Aperture ── */}
        <div className="relative isolate flex aspect-[16/11] items-center justify-center">
          {/* A single soft white pool, well under the "no sci-fi glow" line. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10"
            style={{
              background:
                "radial-gradient(ellipse 60% 60% at 50% 45%, rgba(255,255,255,0.055), transparent 72%)",
            }}
          />

          <svg
            viewBox="0 0 320 220"
            className="h-full w-full"
            role="presentation"
            aria-hidden="true"
          >
            {/* Concentric measurement rings — the instrument, not decoration.
                `.hero-ring` breathes them on desynced 9/11/13s cycles; the
                stroke opacities below are the resting values the reduced-motion
                path reverts to. */}
            <g fill="none" stroke="#ffffff">
              <circle className="hero-ring" cx="160" cy="104" r="88" strokeOpacity="0.06" />
              <circle className="hero-ring" cx="160" cy="104" r="66" strokeOpacity="0.09" />
              <circle className="hero-ring" cx="160" cy="104" r="44" strokeOpacity="0.13" />
              {/* Tick marks at the quadrants. Static: these are the fixed
                  reference of the instrument, so they are the one thing that
                  must not move. */}
              <g strokeOpacity="0.22" strokeLinecap="round">
                <path d="M160 6 v10" />
                <path d="M160 192 v10" />
                <path d="M62 104 h10" />
                <path d="M248 104 h10" />
              </g>
              {/* The exit vector the aperture's tail implies. The dashes flow
                  outward along it — the one piece of directional motion in the
                  panel, and the only one that carries meaning: a decision
                  leaving the instrument. */}
              <path
                className="hero-vector"
                d="M160 104 L 268 190"
                strokeOpacity="0.14"
                strokeDasharray="2 6"
              />
            </g>

            {/* A single faint trace crossing the aperture, clipped to the rings
                so it reads as internal instrumentation rather than a line drawn
                over the panel. */}
            <defs>
              <clipPath id="hero-aperture-clip">
                <circle cx="160" cy="104" r="88" />
              </clipPath>
            </defs>
            <g clipPath="url(#hero-aperture-clip)">
              <line
                className="hero-scan"
                x1="72"
                y1="104"
                x2="248"
                y2="104"
                stroke="#ffffff"
                strokeOpacity="0.07"
              />
            </g>

            {/* One white node where the aperture's tail exits. Monochrome; this
                is the position the old poster gave an orange dot. */}
            <circle cx="268" cy="190" r="3.5" fill="#ffffff" />
            <circle cx="268" cy="190" r="9" fill="none" stroke="#ffffff" strokeOpacity="0.28" />
            {/* The ping. Purely decorative, so it is the one element allowed to
                end its cycle invisible. */}
            <circle
              className="hero-node-ping"
              cx="268"
              cy="190"
              r="9"
              fill="none"
              stroke="#ffffff"
              strokeOpacity="0.5"
            />
          </svg>

          {/* The mark sits on top as its own element rather than nested inside
              the SVG above: a nested <svg> inherits the parent's viewBox scaling
              in ways that differ between engines, and Monogram is also used at
              16px in the nav, so it must stay a standalone component.

              top-[47%] matches the ring centre at cy=104 in the 320×220 viewBox. */}
          <Monogram
            aria-hidden="true"
            className="pointer-events-none absolute top-[47%] left-1/2 w-[25%] -translate-x-1/2 -translate-y-1/2 text-[color:var(--color-text-primary)] opacity-90"
          />
        </div>

        {/* ── Decision rail: the six stages, named, in order ── */}
        <ol className="grid grid-cols-3 gap-px border-t border-[color:var(--color-border)] bg-[color:var(--color-border)] sm:grid-cols-6">
          {steps.map((step, i) => (
            <li
              key={step}
              className="flex flex-col gap-1.5 bg-[color:var(--color-panel)] px-3 py-3"
            >
              <span
                aria-hidden="true"
                className="font-mono text-[length:var(--text-label)] tabular-nums text-[color:var(--color-text-quaternary)]"
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="font-mono text-[length:var(--text-label)] leading-[1.35] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-secondary)] uppercase">
                {step}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <figcaption className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
        {caption}
      </figcaption>
    </figure>
  );
}
