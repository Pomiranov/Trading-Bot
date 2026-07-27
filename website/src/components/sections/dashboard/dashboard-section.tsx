import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Reveal } from "@/components/motion/reveal";
import { DashboardTerminal } from "./dashboard-terminal";

/**
 * Server shell for the operator terminal. The interaction — and every honesty
 * constraint on what the panels may display — lives in dashboard-terminal.tsx.
 *
 * The previous version of this section rendered a static seven-item list beside
 * a single fixed table, which is what read as "raw". It is now a real tabbed
 * product surface with a preview per section.
 */
export async function DashboardSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "dashboard" });

  return (
    <Section
      id="dashboard"
      rhythm="major"
      divider
      glow={<div className="section-glow [--glow-x:50%] [--glow-y:0%]" />}
    >
      <SectionHeader
        id="dashboard"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
        note={t("apiOnlyNote")}
      />

      <Reveal lift={false} className="mt-14">
        <DashboardTerminal />
      </Reveal>
    </Section>
  );
}
