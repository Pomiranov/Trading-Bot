import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Reveal } from "@/components/motion/reveal";

const QUESTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

/**
 * Native <details>/<summary> rather than a JS accordion.
 *
 * This was previously the only section that was a client component reading
 * useTranslations directly, and it set `outline: "none"` on the trigger with
 * no replacement — so it was both the heaviest and the least accessible block
 * on the page. Native disclosure gives keyboard support, screen-reader
 * semantics and find-in-page for free, ships zero JavaScript, and cannot
 * hydration-mismatch.
 *
 * The trade is height animation, which native disclosure cannot do portably.
 * That is an acceptable loss here: the brief asks for motion discipline, and
 * an instant, crisp expand reads more like an instrument than an easing panel.
 */
export async function FaqSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "faq" });

  return (
    <Section id="faq" rhythm="default" width="prose" divider>
      <SectionHeader id="faq" heading={t("heading")} />

      <div className="mt-12 flex flex-col">
        {QUESTIONS.map((q, i) => (
          <Reveal key={q} index={Math.min(i, 4)}>
            <details className="group border-b border-[color:var(--color-border)]">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 py-5 text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] text-[color:var(--color-text-primary)] marker:hidden focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] [&::-webkit-details-marker]:hidden">
                {t(`q${q}`)}
                <span
                  aria-hidden="true"
                  className="mt-1 shrink-0 text-[color:var(--color-text-tertiary)] transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-expo)] group-open:rotate-45"
                >
                  +
                </span>
              </summary>
              <p className="pb-6 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                {t(`a${q}`)}
              </p>
            </details>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
