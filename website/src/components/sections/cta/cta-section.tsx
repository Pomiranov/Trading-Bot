import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Button } from "@/components/ui/button";

/**
 * Phase 1 skeleton: static buttons, no form yet. The real
 * app/api/beta/route.ts + validated email field lands in Phase 4.
 */
export async function CtaSection({ locale }: { locale: string }) {
  const [t, tNav] = await Promise.all([
    getTranslations({ locale, namespace: "sections" }),
    getTranslations({ locale, namespace: "nav" }),
  ]);

  return (
    <section
      aria-labelledby="cta-heading"
      className="flex flex-col items-start gap-6 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <SectionHeading id="cta-heading" className="max-w-[20ch]">
        {t("ctaHeading")}
      </SectionHeading>
      <div className="flex flex-wrap gap-3">
        <Button>{tNav("requestAccess")}</Button>
        <Button variant="outline">{tNav("explore")}</Button>
      </div>
    </section>
  );
}
