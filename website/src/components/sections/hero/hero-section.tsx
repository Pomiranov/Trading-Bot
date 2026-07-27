import { getTranslations } from "next-intl/server";
import { ButtonLink } from "@/components/ui/button-link";
import { ArrowLink } from "@/components/ui/arrow-link";
import { MonoLabel } from "@/components/ui/mono-label";
import { GridBackplate } from "@/components/ui/grid-backplate";
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
 * Inside: headline left, the Q-aperture right, and the proof strip as a
 * contained darker bar across the panel's full width at the foot. That strip
 * was previously five items separated by "·" floating in the left column at the
 * readability floor.
 *
 * ── Honesty ──
 *
 * Nothing here is a result. The three figures in the proof strip are
 * *configured limits*, verifiable in bot/config.py:66-71 — a cap the operator
 * sets before the first trade, not an outcome the system produced. No win rate,
 * profit factor, sample size, Sharpe, equity curve or return figure appears
 * here or anywhere else on the site, under any caption.
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

  const proof = [t("proof1"), t("proof2"), t("proof3"), t("proof4"), t("proof5")];

  const limits = [
    { value: t("limit1Value"), label: t("limit1Label") },
    { value: t("limit2Value"), label: t("limit2Label") },
    { value: t("limit3Value"), label: t("limit3Label") },
  ];

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
        {/* ── The panel ── */}
        <div className="relative isolate overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--color-border)] bg-[color:var(--color-bg-elevated)] shadow-[var(--shadow-panel)]">
          <GridBackplate />

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
            ── Proof strip ──

            A contained, recessed bar across the panel's foot, per the
            reference. It carries the five proof items and the three configured
            limits as one row. Previously those were two unrelated stacks: the
            panel, a hairline, then a 3-up stat grid that read as a footnote to
            the visual rather than as part of the composition.

            `--color-bg` rather than a new token — it is the page's own black,
            one step below the panel's ground, so the strip reads as recessed
            into the panel rather than as a second panel stacked under it.
          */}
          <div className="relative border-t border-[color:var(--color-border)] bg-[color:var(--color-bg)]">
            <div className="flex flex-col gap-4 px-6 py-4 sm:px-10 lg:flex-row lg:items-center lg:justify-between lg:gap-10 lg:px-14">
              <ul className="flex flex-wrap items-center gap-x-3 gap-y-2">
                {proof.map((item, i) => (
                  <li
                    key={item}
                    className="flex items-center gap-3 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase"
                  >
                    {i > 0 ? <span aria-hidden="true">·</span> : null}
                    {item}
                  </li>
                ))}
              </ul>

              {/*
                The configured limits as a compact inline row rather than three
                display-size figures. At --text-display-number they competed
                with the headline; at this size they read as instrument
                readouts, which is what they are.

                A <dl> so every value keeps its label programmatically attached
                — the label is the thing that makes these unambiguously limits
                rather than results, and it must never become decoration that a
                later layout change can drop.
              */}
              <dl className="flex shrink-0 items-center gap-6">
                {limits.map((l) => (
                  <div key={l.label} className="flex flex-col gap-1">
                    <dt className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase">
                      {l.label}
                    </dt>
                    <dd className="font-mono text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-semibold tabular-nums text-[color:var(--color-text-primary)]">
                      {l.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </div>

        {/* The schematic disclaimer. Outside the panel deliberately: it is a
            statement *about* the object, not part of it. */}
        <p className="mt-4 text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
          {t("visualCaption")}
        </p>
      </div>
    </section>
  );
}
