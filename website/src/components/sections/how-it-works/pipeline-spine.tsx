import type { ReactNode } from "react";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { Reveal } from "@/components/motion/reveal";
import { cn } from "@/lib/utils";
import type { PipelineStage } from "@/content-layer/types";

/**
 * The decision path as a connected pipeline.
 *
 * ── What this replaces, and the constraint that shapes it ──
 *
 * Two previous versions, both wrong in opposite directions.
 *
 * The first was a pinned GSAP ScrollTrigger horizontal track, and it produced
 * four separate defects: it over-panned by ~230px because `scrollWidth`
 * included the track's own page padding; it was simultaneously a native
 * `overflow-x-auto` scroller *and* a transformed element *and* carried
 * `scroll-snap-type`, so the browser changed `scrollLeft` underneath the
 * transform; it put a bare `data-lenis-prevent` on a full-viewport-width
 * element, so vertical wheel input over the whole section bypassed the
 * smooth-scroll driver and the page lurched backward; and pinning requires
 * every ancestor to avoid `overflow: hidden`, which constrained the section
 * shell for the rest of the page.
 *
 * The second — the reaction to that — was a plain 3-column card grid. It fixed
 * every defect and lost the entire point: seven cards in a grid say nothing
 * about being a *sequence*. It also needed `% 3` orphan-span logic so stage 07
 * would not sit alone beside two empty cells, which made the loop-closer the
 * visually heaviest card in the section and inverted the reading order.
 *
 * This is a spine, and it is **pure CSS layout plus IntersectionObserver**. No
 * ScrollTrigger. No pinning. No scroll-linked transform. No nested scroll
 * container. No `data-lenis-prevent` of any form. Those are hard constraints,
 * not preferences: every one of them maps to a defect that shipped.
 *
 * ── Layout ──
 *
 * At `lg` a three-column grid — `[1fr, spine, 1fr]` — where each stage occupies
 * one row and places its card in one side column, alternating. The spine is a
 * continuous 1px gradient in the centre column, drawn by the `::before` on the
 * grid rather than by an absolutely-positioned element, so it cannot desync
 * from the rows it runs beside.
 *
 * Below `lg` the same grid collapses to `[spine, 1fr]`: the rail moves left and
 * every card sits to its right. Same markup, same DOM order, no duplicated
 * mobile tree.
 *
 * The `% 3` orphan logic is gone. A spine has no orphans — adding an eighth
 * stage adds a row and nothing else.
 */

function StageCard({
  stage,
  techLabel,
  extra,
}: {
  stage: PipelineStage;
  techLabel: string;
  extra?: ReactNode;
}) {
  return (
    <Surface padding="md" className="flex w-full flex-col gap-4">
      <MonoLabel as="span" tone="signal">
        {stage.stepLabel}
      </MonoLabel>

      {/* Plain first — this is what a beginner reads. */}
      <p className="text-[length:var(--text-h2-sub)] leading-[var(--text-h2-sub--line-height)] font-medium tracking-[var(--text-h2-sub--letter-spacing)] text-[color:var(--color-text-primary)]">
        {stage.plain}
      </p>

      {/* Technical second — this is what a trader or a partner checks. */}
      <div className="mt-auto flex flex-col gap-2 border-t border-[color:var(--color-border)] pt-4">
        <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-secondary)] uppercase">
          <span className="sr-only">{techLabel}: </span>
          {stage.title}
        </p>
        <div className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
          {stage.description}
        </div>
        {/*
          ── Removed: the sourceRef line ──

          Every card used to close on an 11px mono symbol from the Python
          codebase — `loader.get_candles()`, `RulesEngine.evaluate()`,
          `TinkoffClient.place_market_order()` and so on.

          Owner direction, and the argument is register rather than accuracy:
          they are real symbols and they still resolve, but a landing page that
          ends each step on an internal call signature is showing the reader the
          workshop instead of the product. In a section whose whole design is
          "plain sentence first, technical name second", a third, smaller,
          dimmer line was one layer past where a first-time reader stops.

          Nothing is lost. The `sourceRef` frontmatter stays in
          `content/{ru,en}/engine-pipeline/*.mdx` and stays typed and parsed, as
          internal provenance — the same standing `PipelineStage.id` and
          `DataSource` already have (see content-layer/types.ts). Rendering it
          again is a one-line change if a technical audience ever needs it, and
          the docs are where it belongs meanwhile.
        */}
      </div>

      {extra}
    </Surface>
  );
}

export function PipelineSpine({
  stages,
  techLabel,
  extras,
}: {
  stages: PipelineStage[];
  techLabel: string;
  /** Keyed by stage id — lets a stage carry section-specific content. */
  extras?: Record<string, ReactNode>;
}) {
  return (
    <div className="relative">
      {/*
        The spine, as a sibling of the list rather than a child of it — an <ol>
        may only contain <li>, and a decorative span inside it is both invalid
        and a grid participant that would open a phantom row.

        A single hairline behind the node column, fading at both ends so it has
        no hard start or stop. See `.pipeline-rail` in globals.css for the
        gradient and for why it is a class rather than utilities.

        `left` tracks the node column: 1.25rem (the centre of the 2.5rem rail)
        below lg, dead centre at lg where the grid becomes three columns.
      */}
      <span aria-hidden="true" className="pipeline-rail left-[1rem] lg:left-1/2" />

      {/*
        ── The rail column is narrower below `lg` ──

        It was `2.5rem` plus a `1rem` gap: 56px of the 328px available at 390px,
        which left the card 272px and its 13px description an ~28-character
        measure — under the 35 the guidelines put as the floor for body text on a
        phone, and visibly cramped beside the same card at `lg`.

        32px node in a 2rem column with a `0.75rem` gap gives the card 284px back
        without the node losing legibility — it holds an 11px two-digit number,
        and 32px is still four times its cap height.

        That is +12px, not a fix. The honest accounting is that the spine costs
        the card about 13% of a 390px viewport, and it buys the one thing the two
        previous versions of this section lost: the cards read as a *sequence*.
        Reclaiming the rest would mean dropping the rail on mobile, which is that
        same mistake again. `left` on the rail above tracks this column's centre —
        change both together or the hairline stops running through the nodes.
      */}
      <ol className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-3 gap-y-6 lg:grid-cols-[minmax(0,1fr)_4.5rem_minmax(0,1fr)] lg:gap-x-4 lg:gap-y-10">
      {stages.map((stage, i) => {
        // Alternate sides at lg. Odd stages left, even stages right — the
        // reference's rhythm, and it keeps the eye moving down the spine
        // rather than scanning a single column.
        const right = i % 2 === 1;
        // Explicit row placement, not auto-flow. `display: contents` on the
        // <li> drops its children straight into the parent grid, and mixing
        // auto-placement with explicit column starts lets the browser open a
        // new row whenever a column is already occupied — which silently
        // doubles the grid's height as soon as two consecutive cards land on
        // the same side. Pinning the row makes the layout deterministic.
        const row = i + 1;

        return (
          <li key={stage.id} className="contents">
            {/*
              Node. It gets its own grid cell rather than being absolutely
              positioned over the spine, so it stays registered with its row no
              matter how tall the card beside it grows.
            */}
            <div
              className="relative z-10 col-start-1 flex items-start justify-center pt-5 lg:col-start-2"
              style={{ gridRow: row }}
            >
              <span
                aria-hidden="true"
                className="flex size-8 items-center justify-center rounded-[var(--radius-full)] border border-[color:var(--color-border-strong)] bg-[color:var(--color-bg)] font-mono text-[length:var(--text-label)] tabular-nums text-[color:var(--color-text-secondary)] lg:size-10"
                style={{ boxShadow: "var(--glow-signal-sm)" }}
              >
                {String(stage.order).padStart(2, "0")}
              </span>
            </div>

            <Reveal
              // Capped at 4: past roughly four siblings a stagger stops reading
              // as one gesture and starts reading as a queue.
              index={Math.min(i, 4)}
              className={cn(
                "col-start-2 flex min-w-0",
                right ? "lg:col-start-3" : "lg:col-start-1",
              )}
              style={{ gridRow: row }}
            >
              <StageCard stage={stage} techLabel={techLabel} extra={extras?.[stage.id]} />
            </Reveal>
          </li>
        );
        })}
      </ol>
    </div>
  );
}
