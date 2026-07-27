import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { PricingCard } from "@/components/ui/pricing-card";
import { RouteSpine } from "@/components/ui/route-spine";
import { Reveal } from "@/components/motion/reveal";

const PLANS = [1, 2, 3] as const;
const FEATS = [1, 2, 3, 4] as const;

/**
 * Three tiers, one CTA.
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
 * ── The dark-card defect ──
 *
 * The focal card used the `featured` Surface variant, whose `.glass-premium-*`
 * classes hard-code a dark translucent fill and a white gradient border. On this
 * paper band that rendered the one actionable tier as a near-black panel with
 * `.section-paper`'s dark body text on top of it — unreadable, and the single
 * worst thing on the page. Fixed at the surface, in globals.css, rather than by
 * threading a `tone` prop through the card: see the note there for why that is
 * the prescribed repair.
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

      {/* The route arrives from the transition band and fans out to the three
          tiers, then gathers below and continues into `#faq`. Graphite here, not
          cold blue — `.section-paper` re-points the stroke. */}
      <RouteSpine variant="fan" lanes={3} size="md" node={false} className="mt-8" />

      {/* The focal card is first in DOM order, so on mobile — where the grid
          collapses to one column — the actionable tier is the one a visitor
          reaches first rather than the one they scroll past two placeholders
          to find. */}
      <ul className="mt-6 grid items-stretch gap-[var(--space-card-gap)] md:grid-cols-3">
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

      {/*
        ── Removed: the Live-gate checklist and its footnote ──

        Five requirements ("действующий ключ брокера", "без прав на вывод
        средств", "заданные пределы риска", "подтверждённое согласие", "доступная
        остановка") rendered as a 5-up checkbox list, plus a line stating that
        none of it is currently billed.

        Removed on owner direction. Two reasons it was the right thing to cut
        rather than restyle: it put a *form-shaped* block with five empty
        checkboxes directly under the commercial ask, which reads as something to
        fill in; and every item on it was already stated where it is load-bearing
        rather than decorative —

          • no withdrawal rights, risk limits, manual stop → `#safety`, as
            guarantees and limits, at more weight than they had here
          • a live broker key and explicit consent → the Live card in `#access`,
            which is where a visitor actually asks for live access
          • "nothing here is currently billed" → the section lead already says
            payment is not connected and that this is a planned structure

        The honesty position is unchanged: Explore is the only tier with a price
        and the only one with a CTA, and the two planned tiers say "Планируется"
        rather than a number. `PricingCard` derives that from `available`, so it
        self-corrects when billing ships instead of relying on someone to
        remember.
      */}

      <RouteSpine variant="gather" lanes={3} size="md" className="mt-[var(--space-block)]" />
    </Section>
  );
}
