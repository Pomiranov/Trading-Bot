import { SiteHeader } from "@/components/sections/nav/site-header";
import { HeroSection } from "@/components/sections/hero/hero-section";
import { AudienceSection } from "@/components/sections/audience/audience-section";
import { HowItWorksSection } from "@/components/sections/how-it-works/how-it-works-section";
import { FoundationSection } from "@/components/sections/foundation/foundation-section";
import { DashboardSection } from "@/components/sections/dashboard/dashboard-section";
import { TelegramSection } from "@/components/sections/telegram/telegram-section";
import { BrokersSection } from "@/components/sections/brokers/brokers-section";
import { StrategiesSection } from "@/components/sections/strategies/strategies-section";
import { SafetySection } from "@/components/sections/safety/safety-section";
import { PricingSection } from "@/components/sections/pricing/pricing-section";
import { FaqSection } from "@/components/sections/faq/faq-section";
import { AccessSection } from "@/components/sections/access/access-section";
import { Footer } from "@/components/sections/footer/footer";
import { ScrollAnalytics } from "@/components/analytics/scroll-analytics";

/**
 * The page as an argument, in order: what it does → who it is for → how it
 * decides → what it rests on → what you operate → where it executes → what it
 * refuses to claim → what protects you → what it costs → what you asked → how
 * to start.
 *
 * `#foundation` sits directly after `#how-it-works` because it is the answer to
 * the question that section raises: having shown the mechanism, state the
 * principles it was built under. It used to be a sub-block *inside* that
 * section, arriving ~2 200px after its own H2.
 *
 * SiteHeader sits outside <main> because a banner landmark must not be a
 * descendant of main.
 */
export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <>
      <SiteHeader locale={locale} />
      <main className="flex flex-col">
        <HeroSection locale={locale} />
        <AudienceSection locale={locale} />
        <HowItWorksSection locale={locale} />
        <FoundationSection locale={locale} />
        <DashboardSection locale={locale} />
        <TelegramSection locale={locale} />
        <BrokersSection locale={locale} />
        <StrategiesSection locale={locale} />
        <SafetySection locale={locale} />
        <PricingSection locale={locale} />
        <FaqSection locale={locale} />
        <AccessSection locale={locale} />
      </main>
      <Footer locale={locale} />
      <ScrollAnalytics />
    </>
  );
}
