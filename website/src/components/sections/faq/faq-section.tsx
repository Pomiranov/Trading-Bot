import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { RouteSpine } from "@/components/ui/route-spine";
import { Reveal } from "@/components/motion/reveal";

const QUESTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

/**
 * Native <details>/<summary>, contained in one card.
 *
 * ── Do not replace this with a JS accordion ──
 *
 * It was one once: the only client component among the sections, and it set
 * `outline: none` on the trigger with no replacement, making it simultaneously
 * the heaviest and the least accessible block on the page. Native disclosure
 * gives keyboard support, screen-reader semantics and find-in-page for free,
 * ships zero JavaScript, and cannot hydration-mismatch.
 *
 * The trade is height animation, which native disclosure cannot do portably.
 * That is an acceptable loss: an instant, crisp expand reads more like an
 * instrument than an easing panel, and Ctrl+F finding text inside a collapsed
 * answer is worth more than the ease-out.
 *
 * ── What changed ──
 *
 * The rows sat as bare hairline-separated text in a 68ch column inside a 1280
 * field — the narrowest block on the page by a wide margin, floating with
 * nothing around it, so it read as a different site. They are now inside one
 * `SurfaceCard`. The section also gains an eyebrow; it was the only one without
 * one.
 *
 * The disclosure indicator was a bare `+` rotating 45°. It is now a drawn
 * chevron rotating 180°, and each row has a hover and focus background so the
 * target is visible before it is hit.
 */
export async function FaqSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "faq" });

  return (
    /*
      No `divider`. The route line coming out of `#pricing`'s transition band now
      arrives here, and a hairline across the top of the section on top of that
      gave the join two competing horizontal edges — the line pointing in and a
      rule saying "new block". The connector is the better separator: it says the
      same thing and says it as continuity rather than as a cut.
    */
    <Section id="faq" rhythm="default" width="prose">
      {/* Arrives from pricing. `prose` width, so this is a 68ch column — the
          spine sits centred in it, directly above the heading it introduces. */}
      <RouteSpine size="sm" className="mb-10" />

      <SectionHeader id="faq" eyebrow={t("eyebrow")} heading={t("heading")} />

      <Reveal lift={false} className="mt-[var(--space-header-to-body)]">
        <Surface interactive={false} className="overflow-hidden">
          {QUESTIONS.map((q) => (
            <details
              key={q}
              className="group border-t border-[color:var(--color-border)] first:border-t-0"
            >
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 px-6 py-5 text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] text-[color:var(--color-text-primary)] transition-colors duration-[var(--duration-micro)] marker:hidden hover:bg-[color:var(--color-highlight-bg)] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[color:var(--color-accent)] [&::-webkit-details-marker]:hidden">
                {t(`q${q}`)}
                <svg
                  aria-hidden="true"
                  viewBox="0 0 16 16"
                  className="mt-1.5 size-4 shrink-0 text-[color:var(--color-text-tertiary)] transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-expo)] group-open:rotate-180"
                >
                  <path
                    d="M3 6 L8 11 L13 6"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </summary>
              <p className="px-6 pb-6 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                {t(`a${q}`)}
              </p>
            </details>
          ))}
        </Surface>
      </Reveal>
    </Section>
  );
}
