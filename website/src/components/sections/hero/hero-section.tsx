import { getTranslations } from "next-intl/server";
import { ButtonLink } from "@/components/ui/button-link";
import { ArrowLink } from "@/components/ui/arrow-link";
import { MonoLabel } from "@/components/ui/mono-label";
import { Stat } from "@/components/ui/stat";
import { HeroVisual } from "./hero-visual";
import { PointerTilt } from "./pointer-tilt";

/**
 * Strong text block left, composed system object right, flat black behind.
 *
 * The video hero this replaces is gone from the homepage entirely — see
 * hero-visual.tsx for why, and docs/VIDEO_ASSET_GUIDE.md is retained as the
 * record of that experiment rather than as a live dependency.
 *
 * Nothing in this section is a result. The three tiles are *configured limits*,
 * verifiable in bot/config.py:66-71 and bot/learning/trading_orchestrator.py:63
 * — a cap the operator sets before the first trade, not an outcome it produced.
 * No win rate, profit factor, sample size, equity curve or return figure
 * appears here or anywhere else on the site.
 */
export async function HeroSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "hero" });

  const proof = [t("proof1"), t("proof2"), t("proof3"), t("proof4"), t("proof5")];

  const limits = [
    { value: t("limit1Value"), label: t("limit1Label") },
    { value: t("limit2Value"), label: t("limit2Label") },
    { value: t("limit3Value"), label: t("limit3Label") },
  ];

  const steps = [
    t("visualStep1"),
    t("visualStep2"),
    t("visualStep3"),
    t("visualStep4"),
    t("visualStep5"),
    t("visualStep6"),
  ] as const;

  return (
    <section
      id="hero"
      aria-labelledby="hero-heading"
      className="relative isolate flex min-h-dvh items-center px-[var(--space-page-x)] pt-32 pb-20"
    >
      {/* Depth behind the instrument, weighted to the right so the panel sits
          in the light and the headline stays on flat black. Clipped and
          aria-hidden; see `.section-glow`. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="section-glow [--glow-x:72%] [--glow-y:38%]" />
      </div>

      <div className="relative mx-auto grid w-full max-w-[var(--space-content-max)] items-center gap-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16">
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

          <p className="max-w-[54ch] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] tracking-[var(--text-lead--letter-spacing)] text-[color:var(--color-text-secondary)]">
            {t("subline")}
          </p>

          <div className="flex w-full flex-wrap items-center gap-x-7 gap-y-4">
            {/* Primary: white fill, black text. Secondary: outline, white text. */}
            <ButtonLink
              href="#access"
              size="lg"
              magnetic
              className="h-auto min-h-12 w-full justify-center py-3 text-center whitespace-normal sm:w-auto"
              analytics={{ target: "sandbox_access", location: "hero" }}
            >
              {t("ctaPrimary")}
            </ButtonLink>
            <ArrowLink href="#how-it-works" analytics={{ target: "how_it_works", location: "hero" }}>
              {t("ctaSecondary")}
            </ArrowLink>
          </div>

          <ul className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
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
        </div>

        {/* ── Right: the system object ──
            PointerTilt is a thin client shell; HeroVisual is passed through as
            children and stays server-rendered. */}
        <div className="flex min-w-0 flex-col gap-8">
          <PointerTilt>
            <HeroVisual
              title={t("visualTitle")}
              mode={t("visualMode")}
              steps={steps}
              caption={t("visualCaption")}
            />
          </PointerTilt>

          <div className="flex flex-col gap-5 border-t border-[color:var(--color-border)] pt-6">
            <MonoLabel>{t("limitsLabel")}</MonoLabel>
            <div className="grid grid-cols-3 gap-6">
              {limits.map((l) => (
                <Stat key={l.label} size="sm" value={l.value} label={l.label} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
