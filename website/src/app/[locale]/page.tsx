import { SiteHeader } from "@/components/sections/nav/site-header";
import { HeroSection } from "@/components/sections/hero/hero-section";
import { PhilosophySection } from "@/components/sections/philosophy/philosophy-section";
import { EnginePipelineSection } from "@/components/sections/engine-pipeline/engine-pipeline-section";
import { LearningSystemSection } from "@/components/sections/learning-system/learning-system-section";
import { DashboardPreviewSection } from "@/components/sections/dashboard-preview/dashboard-preview-section";
import { TelegramBotSection } from "@/components/sections/telegram-bot/telegram-bot-section";
import { BrokerIntegrationsSection } from "@/components/sections/broker-integrations/broker-integrations-section";
import { SandboxSection } from "@/components/sections/sandbox/sandbox-section";
import { StrategyTable } from "@/components/sections/strategy-layer/strategy-table";
import { PricingSection } from "@/components/sections/pricing/pricing-section";
import { FaqSection } from "@/components/sections/faq/faq-section";
import { CtaSection } from "@/components/sections/cta/cta-section";
import { Footer } from "@/components/sections/footer/footer";
import { ScrollAnalytics } from "@/components/analytics/scroll-analytics";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <main className="flex flex-col">
      <SiteHeader locale={locale} />
      <HeroSection locale={locale} />
      <PhilosophySection locale={locale} />
      <EnginePipelineSection locale={locale} />
      <LearningSystemSection locale={locale} />
      <DashboardPreviewSection locale={locale} />
      <TelegramBotSection locale={locale} />
      <BrokerIntegrationsSection locale={locale} />
      <SandboxSection locale={locale} />
      <StrategyTable locale={locale} />
      <PricingSection locale={locale} />
      <FaqSection />
      <CtaSection locale={locale} />
      <Footer locale={locale} />
      <ScrollAnalytics />
    </main>
  );
}
