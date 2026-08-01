import { Surface } from "./surface";
import { ButtonLink } from "./button-link";

interface PricingCardProps {
  tier: string;
  /**
   * Pre-formatted and locale-owned. "Бесплатно" / "5 000 ₽" in RU, "Free" /
   * "≈ $55" in EN — the message catalogue is the pricing config, so a currency
   * never has to be assembled at render time and the approximation marker on
   * the dollar figures is part of the string a translator owns.
   */
  price: string;
  /** "в месяц" / "per month" / "7 дней". Sits under the price, never beside it. */
  period: string;
  body: string;
  features: readonly string[];
  cta: { href: string; label: string };
}

/**
 * One pricing tier.
 *
 * ── All three cards are identical, and that is the design ──
 *
 * The previous version emphasised one card with the `featured` Surface variant
 * — a lighter graphite fill and a gradient hairline — deriving the emphasis
 * from which tier was actually purchasable. That was the right answer to the
 * old question: two of the three tiers said "Планируется" and had no CTA, so
 * something had to say which one was real.
 *
 * All three are real now, all three are priced, and all three end in the same
 * ask. With nothing left to disambiguate, a lighter card is just a thumb on the
 * scale — and read across the row it made the other two look dimmed rather than
 * equal, which was the note this pass was opened on. Three identical objects,
 * differing only in what they say, is both the more honest arrangement and the
 * more expensive-looking one.
 *
 * So: one variant, one padding, one radius, one hover. The grid is
 * `items-stretch` and each card is `w-full` inside a flex `li`, so they resolve
 * to the tallest and the row sits on one baseline top and bottom.
 *
 * If a tier ever should carry focus again, do it with a hairline or a label —
 * not by making its neighbours darker.
 */
export function PricingCard({
  tier,
  price,
  period,
  body,
  features,
  cta,
}: PricingCardProps) {
  return (
    <Surface padding="md" className="flex w-full flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h3 className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
          {tier}
        </h3>

        {/*
          Price and period on one baseline.

          `items-baseline` rather than a stacked block: "5 000 ₽" and "в месяц"
          are one statement, and putting the qualifier on its own line under a
          40px figure opens a gap the eye reads as a missing element. The period
          is the only thing between the price and the body copy, so it also has
          to carry the vertical rhythm — hence `gap-2` above rather than a
          margin here.

          The `min-h` on the row is what keeps the three cards aligned: the
          tokens' `--text-display-number--line-height` is 1, so a price's line
          box is exactly `--text-display-number` tall, and reserving that as a
          floor means the body copy, the feature list and the CTA all start on
          the same line in all three cards regardless of how the strings wrap.
        */}
        <div className="flex min-h-[var(--text-display-number)] flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <p className="text-[length:var(--text-display-number)] leading-[var(--text-display-number--line-height)] font-medium tracking-[var(--text-display-number--letter-spacing)] text-[color:var(--color-text-primary)]">
            {price}
          </p>
          <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
            {period}
          </p>
        </div>

        <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
          {body}
        </p>
      </div>

      <ul className="flex flex-1 flex-col gap-2.5 border-t border-[color:var(--color-border)] pt-5">
        {features.map((f) => (
          <li
            key={f}
            className="flex items-start gap-2.5 text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-secondary)]"
          >
            {/*
              Centred on the first line by arithmetic rather than by eye.

              `mt-[0.45em]` was 5.85px at this 13px size, and the centre of a
              19.5px line box minus a 4px dot is 7.75px — so every marker in
              every tier sat ~2px high, which at this scale reads as the bullets
              floating above their own text. Visible in the row, hard to name.

              Derived from the same tokens that set the line box and the dot, so
              it cannot drift if either changes: half of (line-height − dot).
            */}
            <span
              aria-hidden="true"
              className="mt-[calc((var(--text-caption--line-height)*1em-0.25rem)/2)] size-1 shrink-0 rounded-[var(--radius-full)] bg-[color:var(--color-text-quaternary)]"
            />
            {f}
          </li>
        ))}
      </ul>

      {/* Required, not optional. Every tier is purchasable now, so a card
          without an ask would be the odd one out — and the reason the prop used
          to be optional (a button on a tier that cannot be bought is the same
          false affordance as a fake price) no longer applies to any of them. */}
      <ButtonLink
        href={cta.href}
        className="w-full justify-center"
        analytics={{ target: "sandbox_access", location: "pricing_card" }}
      >
        {cta.label}
      </ButtonLink>
    </Surface>
  );
}
