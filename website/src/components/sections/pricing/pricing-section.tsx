import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { ButtonLink } from "@/components/ui/button-link";
import { Reveal } from "@/components/motion/reveal";

const PLANS = [1, 2, 3] as const;
const FEATS = [1, 2, 3, 4] as const;
const GATES = [1, 2, 3, 4, 5] as const;

/**
 * No "Recommended" badge. There is no payment code anywhere in the repository
 * (grep for stripe/billing/checkout returns only a Permissions-Policy header),
 * so highlighting one unpriced, unavailable tier over another is a conversion
 * pattern with nothing behind it.
 *
 * The Live column carries its gates inline rather than presenting itself as
 * unrestricted — live access requires a broker key without withdrawal rights,
 * configured risk limits, confirmed consent and a reachable stop.
 */
export async function PricingSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "pricing" });

  return (
    <Section
      id="pricing"
      rhythm="major"
      divider
      glow={<div className="section-glow [--glow-x:50%] [--glow-y:0%]" />}
    >
      <SectionHeader
        id="pricing"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      <ul className="mt-14 grid gap-5 md:grid-cols-3">
        {PLANS.map((p, i) => (
          <li key={p} className="flex">
            <Reveal index={i} className="flex w-full">
              <Surface className="flex w-full flex-col gap-6 p-7">
                <div className="flex flex-col gap-2">
                  <h3 className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
                    {t(`plan${p}Title`)}
                  </h3>
                  <p className="text-[length:var(--text-display-number)] leading-[var(--text-display-number--line-height)] font-medium tracking-[var(--text-display-number--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`plan${p}Price`)}
                  </p>
                  <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                    {t(`plan${p}Body`)}
                  </p>
                </div>

                <ul className="flex flex-1 flex-col gap-2.5 border-t border-[color:var(--color-border)] pt-5">
                  {FEATS.map((f) => (
                    <li
                      key={f}
                      className="flex items-start gap-2.5 text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-secondary)]"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-[0.45em] size-1 shrink-0 rounded-full bg-[color:var(--color-text-quaternary)]"
                      />
                      {t(`plan${p}Feat${f}`)}
                    </li>
                  ))}
                </ul>
              </Surface>
            </Reveal>
          </li>
        ))}
      </ul>

      {/* ── Live gates ── */}
      <Reveal index={3} className="mt-10 flex flex-col gap-5">
        <MonoLabel>{t("liveGatesHeading")}</MonoLabel>
        <ul className="flex flex-wrap gap-x-3 gap-y-2">
          {GATES.map((g) => (
            <li
              key={g}
              className="rounded-full border border-[color:var(--color-border)] px-3.5 py-1.5 text-[length:var(--text-caption)] text-[color:var(--color-text-secondary)]"
            >
              {t(`liveGate${g}`)}
            </li>
          ))}
        </ul>
      </Reveal>

      <Reveal index={4} className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3">
        <ButtonLink
          href="#access"
          size="lg"
          analytics={{ target: "sandbox_access", location: "pricing" }}
        >
          {t("cta")}
        </ButtonLink>
        <p className="text-[length:var(--text-caption)] text-[color:var(--color-text-quaternary)]">
          {t("ctaNote")}
        </p>
      </Reveal>
    </Section>
  );
}
