import { getTranslations } from "next-intl/server";
import { ButtonLink } from "@/components/ui/button-link";
import { ArrowLink } from "@/components/ui/arrow-link";
import { MonoLabel } from "@/components/ui/mono-label";
import { GridBackplate } from "@/components/ui/grid-backplate";
import { SignalField } from "@/components/ui/signal-field";
import { SignalDot } from "@/components/ui/signal-dot";
import { QAperture } from "./q-aperture";
import { PointerTilt } from "./pointer-tilt";

/** The system-envelope row under the CTAs. See the note at its call site. */
const SYSTEM_FACTS = ["system1", "system2", "system3"] as const;

/**
 * The argument in one screen, inside a contained dark panel.
 *
 * ── Composition ──
 *
 * The reference does not run the hero full-bleed: it is a rounded panel inset
 * from the page edges, sitting on the page as an object. That containment is
 * what makes the rest of the page read as a document rather than a poster, and
 * it rhymes with the closing CTA panel so the page is bookended.
 *
 * Inside, and now that is all of it: eyebrow, headline, subline and two calls
 * to action on the left; the Q-aperture on the right. The recessed proof strip
 * that used to run across the panel's foot, and the caption under it, were
 * removed — see the note at the foot of the panel for what went and why the
 * honesty guarantee is unaffected.
 *
 * ── Honesty ──
 *
 * Nothing here is a result, and nothing here is a figure at all any more. The
 * aperture is orbital geometry: no chart, no plotted series, no counter, no
 * percentage. No win rate, profit factor, sample size, Sharpe, equity curve or
 * return figure appears here or anywhere else on the site, under any caption.
 *
 * ── LCP ──
 *
 * `qf-hero-enter` is transform-only and must stay that way. An entrance that
 * starts at `opacity: 0` with fill-mode `both` disqualifies its whole subtree
 * as an LCP candidate for the duration of the delay, which previously cost the
 * hero ~150ms for no visual gain. The <h1> is the LCP element and no ancestor
 * of it may start transparent.
 */
export async function HeroSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "hero" });

  return (
    <section
      id="hero"
      aria-labelledby="hero-heading"
      // No min-h-dvh below md. At 390px the old hero measured 1 479px — 1.75
      // viewports before the CTA came into view — and on iOS a dvh re-measures
      // when the toolbar collapses, so it also jumped on first scroll. Desktop
      // keeps the full-height composition.
      className="relative isolate px-[var(--space-page-x)] pt-24 pb-12 md:min-h-dvh md:items-center md:pt-32 md:pb-16 lg:flex"
    >
      <div className="relative mx-auto w-full max-w-[var(--space-content-max)]">
        {/* ── The panel ──
            `SignalField` is a ~60-line client shell that writes the pointer's
            position to three custom properties; everything inside it, including
            the headline and the aperture, stays server-rendered. It wraps the
            panel rather than the section so the light is bounded by the object it
            belongs to — a field the width of the whole section would light grid
            lines the reader is nowhere near. */}
        <SignalField className="relative isolate overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--color-border)] bg-[color:var(--color-bg-elevated)] shadow-[var(--shadow-panel)]">
          {/* `panel`, for the same reason `#access` uses it: this panel is
              ~1208×750 at 1440px, and the default `pool` ellipse is tuned for a
              near-square host. On this aspect ratio it stopped every vertical
              line well short of the panel's foot. See EDGE_FADE in
              ui/grid-backplate.tsx. */}
          <GridBackplate signal mask="panel" />

          {/* Depth, weighted right so the aperture sits in the light and the
              headline stays on flat black. Clipped by the panel. */}
          <div
            aria-hidden="true"
            className="section-glow pointer-events-none [--glow-x:74%] [--glow-y:34%]"
          />

          {/* Row and column gaps are set separately from `lg`. They used to be
              one `gap-14`, which was right when the grid had a single row — but
              the system-envelope row below makes a second one, and 56px between
              the composition and a single 11px mono line is a gap looking for a
              third element. 32px reads as a foot; the column gap stays at 56. */}
          <div className="relative grid items-center gap-8 px-6 pt-10 pb-8 sm:px-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-x-14 lg:gap-y-8 lg:px-14 lg:pt-16 lg:pb-10">
            {/* ── Left: the argument ── */}
            <div className="flex min-w-0 flex-col items-start gap-7">
              {/* The closed-testing beacon. This eyebrow opens with "Closed
                  testing" in both locales, and owner direction is that every
                  badge saying so carries the same cold dot — see
                  ui/signal-dot.tsx for why this is not the live-status pulse.
                  `items-center` on a mono line whose cap height is 11px puts the
                  1.5-unit dot on the optical centre without a nudge. */}
              <MonoLabel className="flex items-center gap-2.5">
                <SignalDot />
                {t("eyebrow")}
              </MonoLabel>

              <h1
                id="hero-heading"
                className="text-[length:var(--text-hero)] leading-[var(--text-hero--line-height)] font-medium tracking-[var(--text-hero--letter-spacing)] text-balance text-[color:var(--color-text-primary)]"
              >
                {t("headline1")}
                <br />
                {t("headline2")}
              </h1>

              <p className="max-w-[52ch] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] tracking-[var(--text-lead--letter-spacing)] text-[color:var(--color-text-secondary)]">
                {t("subline")}
              </p>

              <div className="flex w-full flex-wrap items-center gap-x-7 gap-y-4">
                <ButtonLink
                  href="#access"
                  size="lg"
                  magnetic
                  className="h-auto min-h-12 w-full justify-center py-3 text-center whitespace-normal sm:w-auto"
                  analytics={{ target: "sandbox_access", location: "hero" }}
                >
                  {t("ctaPrimary")}
                </ButtonLink>
                <ArrowLink
                  href="#how-it-works"
                  analytics={{ target: "how_it_works", location: "hero" }}
                >
                  {t("ctaSecondary")}
                </ArrowLink>
              </div>

            </div>

            {/* ── Right: the instrument ──
                PointerTilt is a thin client shell; QAperture is passed through
                as children and stays server-rendered.

                A plain block, NOT a flex row. `.hero-tilt` is a bare <div>, so
                as a flex item it sizes to its content — and QAperture is
                `w-full` inside it, which makes the width self-referential and
                collapses the instrument to ~300px at every breakpoint.
                Block-level, the wrapper fills the column and QAperture's own
                `mx-auto` + max-width do the centring. */}
            <div className="min-w-0">
              <PointerTilt>
                <QAperture
                  labels={[t("apertureRule"), t("apertureIn"), t("apertureOut")]}
                />
              </PointerTilt>
            </div>

            {/*
                ── The system envelope ──

                Three facts about how the operator is configured, on one line
                across the panel's foot.

                ── Why it spans both columns ──

                It began under the calls to action, inside the left column, and
                that was wrong twice over. The column is ~510px at `lg`, so three
                mono items wrapped to two lines — and the wrap put the panel 54px
                past the fold on a 900px viewport, breaking the one thing the
                hero is for, which is making the argument in one screen. It also
                left the panel's lower *right* — under the aperture — as the one
                genuinely empty region, which is the emptiness this row was added
                to answer in the first place.

                Full width fits all three on one line at every breakpoint from
                `sm` up, fills the foot rather than one corner of it, and gives
                the panel a base to sit on.

                Read the removal note at the foot of this panel before touching
                this. A five-item proof strip and a three-figure <dl> were cut
                from exactly here, and this is deliberately not a reinstatement
                of either: it is a later owner direction to fill the panel's
                lower-left, and it is held to the terms that made the old strip
                wrong in the first place.

                What that means concretely, and what any future addition here
                has to satisfy:

                  • **No results, and no figures at all.** Not a win rate, profit
                    factor, sample size, Sharpe, equity curve or return, under
                    any caption. Each item is a *capability or a constraint* —
                    which venues are wired, when risk is evaluated, whether a
                    human can intervene — and none of them is a number.
                  • **Three, not five.** The old strip's failure was quantity as
                    much as content: it made the hero argue four things at once.
                  • **Nothing duplicated from the eyebrow.** Closed testing,
                    MOEX and sandbox-by-default are stated 200px above; repeating
                    them here is what turned the old strip into furniture.
                  • **Every claim is load-bearing elsewhere.** Risk limits before
                    the order and manual confirmation are both stated at full
                    weight in `#safety` and in the belief-gate node of
                    `#how-it-works`; the venue pair is in the subline directly
                    above. Nothing here is the only place a reader can learn it.

                Presentation is a mono row on the panel's own ground, with no
                fill, no border and no rule above it. The strip that was removed
                had a fill and a border, which is what made it read as a second
                UI inside the panel — and a hairline over it is worse still on
                this page specifically: it would span the left column only,
                stopping mid-panel with nothing to join, which is precisely the
                "line hanging in space" artefact this whole pass exists to
                remove. The grid's own `gap` is the separation.
              */}
            <ul className="flex flex-wrap items-center gap-x-7 gap-y-2 lg:col-span-2">
              {SYSTEM_FACTS.map((key) => (
                <li
                  key={key}
                  className="flex items-center gap-2 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase"
                >
                  <span
                    aria-hidden="true"
                    className="size-1 shrink-0 rounded-[var(--radius-full)] bg-[color:var(--color-text-quaternary)]"
                  />
                  {t(key)}
                </li>
              ))}
            </ul>
          </div>

          {/*
            ── Removed: the proof strip and the schematic caption ──

            The panel's foot used to carry a recessed bar holding five proof
            items ("Песочница · Telegram · Dashboard · MOEX + Bybit · Пределы
            риска") and the three configured limits as a <dl>, with a caption
            below the panel restating that the visual contains no results.

            All three are gone on owner direction: the hero should make one
            argument, and a five-item meta row plus three numeric readouts plus
            a disclaimer is four. The eyebrow above the headline still carries
            the closed-testing / MOEX / sandbox framing, which is the part that
            actually qualified the claim.

            ── This does not weaken the honesty guarantee ──

            Nothing removed here was a *result*; they were configured limits and
            a disclaimer about a visual that has no data in it. The load-bearing
            statements survive elsewhere in full:

              • the risk limits are stated in `#safety` and in the belief-gate
                node of `#how-it-works`, both with their labels attached
              • "sandbox by default" is in the hero eyebrow and in `#safety`
              • the aperture is orbits — no chart, no series, no counter — so
                there is nothing left for a "this is not performance" caption to
                disclaim

            The rule stands unchanged: no win rate, profit factor, sample size,
            Sharpe, equity curve or return figure appears anywhere on this site
            under any caption. Removing a caption is not permission to add a
            figure. `hero.proof1-5`, `hero.limit*` and `hero.visualCaption` were
            deleted from both message catalogues.
          */}
        </SignalField>
      </div>
    </section>
  );
}
