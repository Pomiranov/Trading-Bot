import { getTranslations } from "next-intl/server";
import { ButtonLink } from "@/components/ui/button-link";
import { ArrowLink } from "@/components/ui/arrow-link";
import { MonoLabel } from "@/components/ui/mono-label";
import { GridBackplate } from "@/components/ui/grid-backplate";
import { SignalField } from "@/components/ui/signal-field";
import { QAperture } from "./q-aperture";
import { PointerTilt } from "./pointer-tilt";

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
      className="relative isolate px-[var(--space-page-x)] pt-24 pb-12 md:min-h-dvh md:items-center md:pt-32 md:pb-20 lg:flex"
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
          <GridBackplate signal />

          {/* Depth, weighted right so the aperture sits in the light and the
              headline stays on flat black. Clipped by the panel. */}
          <div
            aria-hidden="true"
            className="section-glow pointer-events-none [--glow-x:74%] [--glow-y:34%]"
          />

          <div className="relative grid items-center gap-8 px-6 pt-10 pb-8 sm:px-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-14 lg:px-14 lg:pt-16 lg:pb-14">
            {/* ── Left: the argument ── */}
            <div className="flex min-w-0 flex-col items-start gap-7">
              <MonoLabel>{t("eyebrow")}</MonoLabel>

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
                <QAperture />
              </PointerTilt>
            </div>
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
