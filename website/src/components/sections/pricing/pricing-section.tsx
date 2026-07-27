import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { PricingCard } from "@/components/ui/pricing-card";
import { MonoLabel } from "@/components/ui/mono-label";
import { Reveal } from "@/components/motion/reveal";

const PLANS = [1, 2, 3] as const;
const FEATS = [1, 2, 3, 4] as const;
const GATES = [1, 2, 3, 4, 5] as const;

/**
 * Three tiers, five Live gates, one CTA.
 *
 * ── Prices ──
 *
 * `Бесплатно / Планируется / Планируется`, and they stay that way. The
 * reference shows $10 / $30 / $50 with the middle card emphasised; copying
 * those would be fabricating a commercial offer. There is no payment code
 * anywhere in the repository — grep for stripe|billing|checkout returns a
 * Permissions-Policy header and nothing else. The *composition* is taken from
 * the reference; the numbers are not.
 *
 * ── The focal card ──
 *
 * The reference needs one card to carry focus, and the previous version
 * deliberately had none — reasonably, since highlighting an unpriced,
 * unavailable tier is a conversion pattern with nothing behind it.
 *
 * The resolution is to emphasise the tier that is *actually available*, which is
 * Explore. That satisfies the composition and is more honest than the
 * reference's own arrangement, because the card drawing the eye is the one a
 * visitor can act on today. `PricingCard` derives emphasis from `available`
 * rather than taking it as a flag, so the arrangement self-corrects when
 * billing ships instead of relying on someone to remember.
 *
 * ── The Live gates ──
 *
 * They were pill-shaped <li>s — they looked like filter chips and were not
 * interactive. A false affordance in the middle of the most consequential
 * section on the page. They are a checklist now, which is what they always
 * were: requirements for Live access, not options.
 */
export async function PricingSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "pricing" });

  // Explore is the only tier that exists today. Availability is read from the
  // product's real state, never set to steer the eye.
  const plans = PLANS.map((p) => ({
    id: p,
    tier: t(`plan${p}Title`),
    price: t(`plan${p}Price`),
    available: p === 1,
    body: t(`plan${p}Body`),
    features: FEATS.map((f) => t(`plan${p}Feat${f}`)),
  }));

  return (
    /*
      The second — and last — inverted band on the page.

      Two is the cap. The reference makes five sections light; the deep black
      base is this brand's identity, and paper is punctuation rather than a
      second theme. Foundation and Pricing are the two that earn it: the
      manifesto, and the commercial ask. Both are moments where the page should
      change register, and both sit far enough apart (~5 000px) that the page
      still reads as black with two breaths in it.

      No `glow` here: the section-glow is a white radial pool, which on #f4f2ec
      is invisible at best and a grey smudge at worst.
    */
    <Section id="pricing" rhythm="major" tone="paper">
      <SectionHeader
        id="pricing"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      {/* The focal card is first in DOM order, so on mobile — where the grid
          collapses to one column — the actionable tier is the one a visitor
          reaches first rather than the one they scroll past two placeholders
          to find. */}
      <ul className="mt-[var(--space-header-to-body)] grid items-stretch gap-[var(--space-card-gap)] md:grid-cols-3">
        {plans.map((plan, i) => (
          <li key={plan.id} className="flex">
            <Reveal index={i} className="flex w-full">
              <PricingCard
                tier={plan.tier}
                price={plan.price}
                available={plan.available}
                body={plan.body}
                features={plan.features}
                cta={plan.available ? { href: "#access", label: t("cta") } : undefined}
              />
            </Reveal>
          </li>
        ))}
      </ul>

      {/* ── Live gates, as requirements ── */}
      <Reveal index={3} className="mt-[var(--space-block)] flex flex-col gap-5">
        <MonoLabel>{t("liveGatesHeading")}</MonoLabel>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {GATES.map((g) => (
            <li
              key={g}
              className="flex items-start gap-3 text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-secondary)]"
            >
              {/* An empty checkbox glyph, not a tick: these are requirements a
                  visitor has yet to meet, and a tick would imply they already
                  have. */}
              <span
                aria-hidden="true"
                className="mt-[0.15em] size-3.5 shrink-0 rounded-[var(--radius-xs)] border border-[color:var(--color-border-strong)]"
              />
              {t(`liveGate${g}`)}
            </li>
          ))}
        </ul>
        <p className="max-w-[72ch] text-[length:var(--text-caption)] text-[color:var(--color-text-quaternary)]">
          {t("ctaNote")}
        </p>
      </Reveal>
    </Section>
  );
}
