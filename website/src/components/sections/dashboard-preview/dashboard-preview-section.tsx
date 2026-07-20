import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { DashboardMockup } from "./dashboard-mockup";

/**
 * Illustrative recreation of the real bot/ui/ operational dashboard —
 * same field names as the real /api/metrics response, real forward-test
 * tickers, illustrative values (see dashboardPreviewNote caption). Not a
 * live screenshot: the real dashboard has no seed/demo data to capture
 * without standing up TimescaleDB, which is out of this site's scope.
 */
export async function DashboardPreviewSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "sections" });

  return (
    <section
      aria-labelledby="dashboard-preview-heading"
      className="flex flex-col gap-8 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <Reveal>
        <SectionHeading id="dashboard-preview-heading" className="max-w-[20ch]">
          {t("dashboardPreview")}
        </SectionHeading>
      </Reveal>
      <Reveal index={1} className="mx-auto w-full max-w-[900px]">
        <DashboardMockup />
        <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.1em] text-[color:var(--color-text-tertiary)]">
          {t("dashboardPreviewNote")}
        </p>
      </Reveal>
    </section>
  );
}
