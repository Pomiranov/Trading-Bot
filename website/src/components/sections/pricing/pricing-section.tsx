import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { PricingCard } from "@/components/ui/pricing-card";
import { PaperField } from "@/components/ui/paper-field";
import { Reveal } from "@/components/motion/reveal";

const PLANS = [1, 2, 3] as const;
/** Five per tier, in all three. An uneven row is a comparison table with a hole
 *  in it — if a tier genuinely has less to say, say it in fewer words, not in
 *  fewer lines. */
const FEATS = [1, 2, 3, 4, 5] as const;

/**
 * Three tiers: Sandbox, Live, Premium.
 *
 * ── Prices ──
 *
 * Sandbox is free for 7 days, Live is 5 000 ₽/month, Premium is 10 000 ₽/month.
 * Owner-set, and the message catalogue is the pricing config — a currency is
 * never assembled at render time.
 *
 * The EN catalogue carries "≈ $55" / "≈ $110", and the approximation marker is
 * load-bearing rather than decorative: billing is in roubles, there is no FX
 * feed anywhere in this repository, and a bare "$55" would be asserting a rate
 * the page cannot honour. The section lead says so in words in EN. If a real
 * rate ever exists, it belongs in a locale pricing config with a timestamp, not
 * in a string that quietly ages.
 *
 * ── What this replaces ──
 *
 * `Explore / Sandbox / Live` at `Бесплатно / Планируется / Планируется`, where
 * two of three tiers were placeholders with no CTA and the composition had to
 * work around them: the free tier carried the `featured` surface so that
 * *something* in the row was actionable, and a five-item Live-gate checklist sat
 * underneath. All of that scaffolding is gone with the thing it was propping up.
 *
 * ── What has not changed ──
 *
 * There is still no payment code in the repository — grep for
 * stripe|billing|checkout returns a Permissions-Policy header and nothing else
 * — so every CTA goes to `#access`, which is a request form, and the lead says
 * in both locales that the programme is in closed testing and access is opened
 * by hand. Stating a price is a commitment about what a subscription costs; it
 * is not a claim that a card can be charged today, and the copy must keep those
 * apart.
 *
 * The claim floor is unchanged too. `plan3Feat5` says Bybit and Finam are
 * *planned*, because that is what `#faq` q9 says and what the adapters support:
 * Bybit reads balances and positions, Finam is not implemented. Live is the
 * T-Invest route and says so. No tier promises a return, and no tier carries a
 * figure that is not a price or a document count.
 */
export async function PricingSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "pricing" });

  const plans = PLANS.map((p) => ({
    id: p,
    tier: t(`plan${p}Title`),
    price: t(`plan${p}Price`),
    period: t(`plan${p}Period`),
    body: t(`plan${p}Body`),
    features: FEATS.map((f) => t(`plan${p}Feat${f}`)),
    cta: t(`plan${p}Cta`),
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

      The `glow` slot carries `PaperField`, not `.section-glow`. The latter is a
      white radial pool, which on #f4f2ec is invisible at best and a grey smudge
      at worst; the former is the page's grid at full band height plus a
      cold-white pool that follows the pointer, which is what a light ground can
      actually show. Identical to `#foundation`, so the two bands stay one
      composition.
    */
    <Section id="pricing" rhythm="major" tone="paper" field glow={<PaperField />}>
      <SectionHeader
        id="pricing"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      {/* Ascending order, and on mobile — where the grid collapses to one
          column — that puts the free tier first, which is the one a visitor can
          start on without deciding anything.

          `on-paper-graphite`, the same treatment `#foundation` uses, so the
          page's two paper bands are one composition rather than two: dark
          objects on warm paper, in both. See the note there for how the class
          works and why the cards invert rather than the band. */}
      <ul className="on-paper-graphite mt-[var(--space-header-to-body)] grid items-stretch gap-[var(--space-card-gap)] md:grid-cols-3">
        {plans.map((plan, i) => (
          <li key={plan.id} className="flex">
            <Reveal index={i} className="flex w-full">
              <PricingCard
                tier={plan.tier}
                price={plan.price}
                period={plan.period}
                body={plan.body}
                features={plan.features}
                cta={{ href: "#access", label: plan.cta }}
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
          • the conditions Live opens under → `#faq` q10, in one sentence

        Nothing goes back below the cards. The section is a heading, a lead and
        three tiers, and the next thing after it should be the next section.
      */}
    </Section>
  );
}
