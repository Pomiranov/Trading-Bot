import type { ReactNode } from "react";
import { Reveal } from "@/components/motion/reveal";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { SignalField } from "@/components/ui/signal-field";
import type { PipelineStage } from "@/content-layer/types";
import { cn } from "@/lib/utils";

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
 *
 * ── The cards are always visible ──
 *
 * There was a version in which each node was a <button> that stowed its card
 * into itself, with the motion in `.stage-collapse` in globals.css. It is gone
 * on owner direction: the seven steps *are* the section's argument, and a
 * section whose content has to be clicked back into existence is one where a
 * reader can land on six empty rows.
 *
 * Removed with it: the `useState` and the `./pipeline-stage.tsx` client
 * component that held it, `aria-expanded` / `aria-controls` / `inert`, the node's
 * 44px hit area, the third (`stowed`) node aura, and the `how.stageToggle`
 * message in both locales. The whole section is server-rendered again.
 *
 * What survives is what was always the better half of that pass:
 *
 *   • **The nodes are lit markers.** Each carries `.signal-lens` — a dark well, a
 *     conic rim masked to 1px with a specular arc that sweeps once every 24s, and
 *     a tight aura. Drawn from `~/Downloads/Button.mp4`; see the `--lens-*` block
 *     in styles/tokens/color.css. They mark position in the sequence and take no
 *     input.
 *
 *   • **The rail lights where the pointer is**, via the same `SignalField` the
 *     hero uses. See `.pipeline-rail--lit`.
 *
 *   • **The step numbers are 1–7, not 01–07.** Owner direction. Two-digit
 *     zero-padding is a convention for a set that will exceed nine or for a
 *     fixed-width column; this is seven nodes in a 32–40px circle, where the
 *     leading zero is half the glyphs saying nothing. The numeral moved up one
 *     type role with the change — a single digit at `--text-label` (11px) in a
 *     40px disc reads as an artefact rather than as a step number — and
 *     `tabular-nums` stays, so the digits are still on one width.
 *
 * The hard constraints from the two failed versions are unchanged and none of
 * the above touches them: no ScrollTrigger, no pinning, no scroll-linked
 * transform, no nested scroll container, no `data-lenis-prevent`. This is a CSS
 * grid and one IntersectionObserver-driven entrance; it reads no scroll position
 * at all.
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
    /*
      `SignalField` wraps the spine so the rail can be lit where the pointer is
      — see `.pipeline-rail--lit` in globals.css for what that buys and why a
      travelling highlight rather than a hover state.

      It is the same ~60-line client shell the hero and the two paper bands
      already use: it writes `--signal-x/y/on` and nothing else, so everything
      inside it — including all seven MDX-rendered cards — stays server-
      rendered. With no pointer, a coarse pointer, or reduced motion it installs
      no listener, the variables stay unset, and the lit rail is fully
      transparent.
    */
    <SignalField className="pipeline-field relative">
      {/*
        The spine, as a sibling of the list rather than a child of it — an <ol>
        may only contain <li>, and a decorative span inside it is both invalid
        and a grid participant that would open a phantom row.

        A single hairline behind the node column, fading at both ends so it has
        no hard start or stop. See `.pipeline-rail` in globals.css for the
        gradient and for why it is a class rather than utilities.

        `left` tracks the node column: 1rem below lg, dead centre at lg where the
        grid becomes three columns. The lit copy is a second element rather than
        a pseudo-element on the first, because it needs its own mask and its own
        `filter`, and stacking those on one element would put the bloom on the
        resting hairline too.
      */}
      <span aria-hidden="true" className="pipeline-rail left-[1rem] lg:left-1/2" />
      <span
        aria-hidden="true"
        className="pipeline-rail pipeline-rail--lit left-[1rem] lg:left-1/2"
      />

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
          /*
            `right`: alternate sides at lg. Odd stages left, even stages right —
            the reference's rhythm, and it keeps the eye moving down the spine
            rather than scanning a single column.
          */
          const right = i % 2 === 1;
          /*
            `row`: explicit placement, not auto-flow. `display: contents` on the
            <li> drops its children straight into the parent grid, and mixing
            auto-placement with explicit column starts lets the browser open a
            new row whenever a column is already occupied — which silently
            doubles the grid's height as soon as two consecutive cards land on
            the same side. Pinning the row makes the layout deterministic.
          */
          const row = i + 1;

          return (
            /*
              ── This used to be `<PipelineStageRow>`, a client component ──

              That file existed for one reason: it held the `useState` for the
              card collapse. With the collapse removed on owner direction, the row
              is layout and nothing else, so it is inlined here and the file is
              gone — which also takes a client boundary out of the section. The
              whole spine is server-rendered again, MDX included.

              `pipeline-stage` is the hook the row-level node/card highlight in
              globals.css selects on. It is the only element that contains both
              halves of the pair, and `display: contents` does not prevent it
              being matched.
            */
            <li key={stage.id} className="pipeline-stage contents">
              <div
                className="relative z-10 col-start-1 flex items-start justify-center pt-5 lg:col-start-2"
                style={{ gridRow: row }}
              >
                {/*
                  ── The node is decoration again ──

                  It was a <button> carrying `aria-expanded` / `aria-controls`
                  that stowed its card into itself. The cards are now always
                  visible, so there is nothing to expand and nothing to name: a
                  control that does nothing is worse than a mark, because it takes
                  a tab stop and promises an action.

                  `aria-hidden` because the step number is already carried in
                  reading order — each card opens on its own `stepLabel`, and the
                  cards are in DOM order — so announcing a bare digit before it
                  would be a duplicate. The 44px hit-area pseudo-element went with
                  the button; a marker does not need a touch target.
                */}
                <span
                  aria-hidden="true"
                  className="signal-lens signal-node size-8 font-mono text-[length:var(--text-caption)] tabular-nums text-[color:var(--color-text-secondary)] lg:size-10"
                >
                  <span>{stage.order}</span>
                </span>
              </div>

              <Reveal
                // Capped at 4: past roughly four siblings a stagger stops reading
                // as one gesture and starts reading as a queue.
                index={Math.min(row - 1, 4)}
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
    </SignalField>
  );
}
