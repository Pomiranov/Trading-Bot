import { HeroSection } from "@/components/sections/hero/hero-section";
import { PhilosophySection } from "@/components/sections/philosophy/philosophy-section";
import { EnginePipelineSection } from "@/components/sections/engine-pipeline/engine-pipeline-section";
import { LearningSystemSection } from "@/components/sections/learning-system/learning-system-section";
import { DashboardPreviewSection } from "@/components/sections/dashboard-preview/dashboard-preview-section";
import { StrategyTable } from "@/components/sections/strategy-layer/strategy-table";
import { CtaSection } from "@/components/sections/cta/cta-section";
import { Footer } from "@/components/sections/footer/footer";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <main className="flex flex-col divide-y divide-[color:var(--color-border)]">
      <HeroSection locale={locale} />
      <PhilosophySection locale={locale} />
      <EnginePipelineSection locale={locale} />
      <LearningSystemSection locale={locale} />
      <DashboardPreviewSection locale={locale} />
      <StrategyTable locale={locale} />
      <CtaSection locale={locale} />
      <Footer locale={locale} />
    </main>
  );
}
