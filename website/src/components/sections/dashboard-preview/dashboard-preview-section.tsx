import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Panel } from "@/components/ui/panel";

/**
 * Phase 1 skeleton only. Per the plan's flagged decision: this asset
 * should be a real screenshot/capture of the operational bot/ui/ Flask
 * dashboard (sanitized data), not a div-based fake screenshot — resolved
 * and populated in Phase 3.
 */
export async function DashboardPreviewSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "sections" });

  return (
    <section
      aria-labelledby="dashboard-preview-heading"
      className="flex flex-col gap-8 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <SectionHeading id="dashboard-preview-heading" className="max-w-[20ch]">
        {t("dashboardPreview")}
      </SectionHeading>
      <Panel className="flex min-h-[320px] items-center justify-center p-6">
        <p className="font-mono text-[length:var(--text-label)] uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
          {t("dashboardPreviewNote")}
        </p>
      </Panel>
    </section>
  );
}
