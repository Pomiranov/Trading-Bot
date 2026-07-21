import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { DashboardMockup } from "./dashboard-mockup";

export async function DashboardPreviewSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "sections" });

  return (
    <section
      aria-labelledby="dashboard-preview-heading"
      className="relative flex flex-col gap-10 px-[var(--space-page-x)] py-[var(--space-section-y)] overflow-hidden"
    >
      {/* Section ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 60% 50% at 50% 80%, rgba(255,138,30,0.05), transparent)",
        }}
      />

      <div className="relative flex flex-col items-start gap-4 md:flex-row md:items-end md:justify-between">
        <Reveal>
          <SectionHeading id="dashboard-preview-heading" className="max-w-[22ch]">
            {t("dashboardPreview")}
          </SectionHeading>
        </Reveal>
        <Reveal index={1}>
          <p
            className="font-mono text-[11px] uppercase tracking-[0.1em] md:text-right md:max-w-[40ch]"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {t("dashboardPreviewNote")}
          </p>
        </Reveal>
      </div>

      <Reveal index={2} className="relative mx-auto w-full max-w-[960px]">
        {/* Glow behind the mockup */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -inset-8 rounded-3xl"
          style={{
            background: "radial-gradient(ellipse 80% 60% at 50% 50%, rgba(255,138,30,0.08), transparent)",
            filter: "blur(30px)",
          }}
        />
        <DashboardMockup />
      </Reveal>
    </section>
  );
}
