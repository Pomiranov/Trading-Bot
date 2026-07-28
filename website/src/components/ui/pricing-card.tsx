import { Surface } from "./surface";
import { ButtonLink } from "./button-link";
import { cn } from "@/lib/utils";

interface PricingCardProps {
  tier: string;
  /** Pre-formatted. "Бесплатно" / "Планируется" — never a number we invented. */
  price: string;
  /**
   * Whether this tier can actually be used today.
   *
   * This — not a marketing decision — is what drives emphasis. The reference
   * emphasises its middle card, and copying that would mean highlighting an
   * unpriced, unavailable tier: a conversion pattern with nothing behind it.
   * There is no payment code in the repository at all (grep for
   * stripe|billing|checkout returns a Permissions-Policy header and nothing
   * else), so the only tier that can honestly carry focus is the one that
   * exists. Today that is Explore.
   *
   * Deriving emphasis from availability also means the composition self-corrects
   * the moment billing ships, rather than needing someone to remember.
   */
  available: boolean;
  body: string;
  features: readonly string[];
  cta?: { href: string; label: string };
}

/**
 * One pricing tier.
 *
 * Uses the `featured` Surface variant for the focal card — a gradient border
 * via `mask-composite` that was already built in globals.css for exactly this
 * and used nowhere.
 *
 * ── The focal card is no longer a different size ──
 *
 * It used to carry `md:-my-2 md:py-9`, making it 16px taller than its two
 * siblings and giving it 4px more vertical padding. Measured at 1440 the row
 * came out as 420px / 402px / 402px with three different top edges, which read
 * as one card having slipped rather than as one card being chosen — and it put
 * the three tiers on two baselines in a section whose whole job is a
 * side-by-side comparison.
 *
 * All three now share one radius, one padding and one height (the grid is
 * `items-stretch` and each card is `w-full` inside a flex `li`, so they resolve
 * to the tallest). Emphasis is carried entirely by the `featured` surface: a
 * lighter graphite fill, a gradient hairline border and a deeper lift. That is
 * enough — it is the only card in the row with a price and the only one with a
 * CTA — and it costs nothing in symmetry to say so.
 */
export function PricingCard({
  tier,
  price,
  available,
  body,
  features,
  cta,
}: PricingCardProps) {
  return (
    <Surface
      variant={available ? "featured" : "flat"}
      padding="md"
      className="flex w-full flex-col gap-6"
    >
      <div className="flex flex-col gap-2">
        <h3 className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
          {tier}
        </h3>
        <p
          className={cn(
            "text-[length:var(--text-display-number)] leading-[var(--text-display-number--line-height)] font-medium tracking-[var(--text-display-number--letter-spacing)]",
            // An unavailable tier's "price" is the word "Планируется", and at
            // full primary contrast twice over it became the loudest typography
            // in the section — a repeated placeholder shouting. Dimmed, so the
            // one real price reads first.
            available
              ? "text-[color:var(--color-text-primary)]"
              : "text-[color:var(--color-text-tertiary)]",
          )}
        >
          {price}
        </p>
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
            <span
              aria-hidden="true"
              className="mt-[0.45em] size-1 shrink-0 rounded-[var(--radius-full)] bg-[color:var(--color-text-quaternary)]"
            />
            {f}
          </li>
        ))}
      </ul>

      {/* Only the available tier gets a CTA. A button on a tier that cannot be
          bought is the same false affordance as a fake price. */}
      {cta ? (
        <ButtonLink
          href={cta.href}
          className="w-full justify-center"
          analytics={{ target: "sandbox_access", location: "pricing_card" }}
        >
          {cta.label}
        </ButtonLink>
      ) : null}
    </Surface>
  );
}
