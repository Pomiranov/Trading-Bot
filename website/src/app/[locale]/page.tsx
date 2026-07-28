import { SiteHeader } from "@/components/sections/nav/site-header";
import { HeroSection } from "@/components/sections/hero/hero-section";
import { AudienceSection } from "@/components/sections/audience/audience-section";
import { HowItWorksSection } from "@/components/sections/how-it-works/how-it-works-section";
import { FoundationSection } from "@/components/sections/foundation/foundation-section";
import { DashboardSection } from "@/components/sections/dashboard/dashboard-section";
import { TelegramSection } from "@/components/sections/telegram/telegram-section";
import { SafetySection } from "@/components/sections/safety/safety-section";
import { PricingSection } from "@/components/sections/pricing/pricing-section";
import { FaqSection } from "@/components/sections/faq/faq-section";
import { AccessSection } from "@/components/sections/access/access-section";
import { Footer } from "@/components/sections/footer/footer";
import { BandTransition } from "@/components/ui/band-transition";
import { ScrollAnalytics } from "@/components/analytics/scroll-analytics";

/**
 * The page as an argument, in order: what it does → who it is for → how it
 * decides → what it rests on → what you operate → where else you operate it →
 * what protects you → what it costs → what you asked → how to start.
 *
 * `#foundation` sits directly after `#how-it-works` because it is the answer to
 * the question that section raises: having shown the mechanism, state the
 * principles it was built under. It used to be a sub-block *inside* that
 * section, arriving ~2 200px after its own H2.
 *
 * ── Two sections were removed, and this is the list of what went with them ──
 *
 * `#brokers` ("Исполнение") and `#strategies` ("Лаборатория стратегий"), 2 951px
 * of the page between them, on owner direction: both were internal-facing detail
 * on a marketing landing page — a per-broker status grid, a four-stage status
 * ladder in which two stages were empty by design, and a strategy register
 * table.
 *
 * Anything that leaves this page has to be accounted for, because both sections
 * carried real disclosures. Where each one now lives:
 *
 *   • "live execution is T-Invest only today" — `#pricing`, in the Live tier's
 *     own feature list ("Маршрут T-Invest"), which is the place a visitor is
 *     deciding whether the route they need exists.
 *   • "sandbox by default" — the hero eyebrow and `#safety`.
 *   • "frozen strategies are published alongside working ones" — `#audience`,
 *     cards 2 and 4, in both locales.
 *   • "no metrics are published for any strategy" — `#audience` card 4, which is
 *     built entirely out of that position.
 *   • Bybit being read-only and Finam being unimplemented are no longer stated
 *     anywhere, and that is a deliberate narrowing rather than a claim: the page
 *     no longer says either broker is supported, so there is nothing left to
 *     qualify. If a broker list ever returns, the per-adapter status must return
 *     with it — see the trade-off note in docs/LANDING_COPY_REMOVALS.md.
 *
 * The deleted components are in git history at aee38bd if any of this has to be
 * reinstated; `lib/strategy-status.ts`, the per-locale `strategies.json` files
 * under `content/` and `contentSource.getStrategies` all survive, so a rebuild
 * would not start from nothing.
 *
 * ── The paper bands are entered and left through a blend ──
 *
 * `BandTransition` sits on both sides of each `tone="paper"` section.
 * `tone="paper"` flips the tokens at a hard edge — #030303 meeting #f4f2ec on one
 * pixel row — which read as two sites stacked. The band ramps black → graphite →
 * paper across 176–256px, with the page's 64px grid crossing it and changing ink
 * as the ground does. Direction matters and is not symmetric: `into-paper`
 * before, `into-dark` after. A `.band-blend + .section-paper` rule in globals.css
 * then takes the following section's top padding away, so the blend is the
 * section's lead-in rather than a preface to 232px of empty paper.
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

        <BandTransition direction="into-paper" />
        <FoundationSection locale={locale} />
        <BandTransition direction="into-dark" />

        <DashboardSection locale={locale} />
        <TelegramSection locale={locale} />
        <SafetySection locale={locale} />

        <BandTransition direction="into-paper" />
        <PricingSection locale={locale} />
        <BandTransition direction="into-dark" />

        <FaqSection locale={locale} />
        <AccessSection locale={locale} />
      </main>
      <Footer locale={locale} />
      <ScrollAnalytics />
    </>
  );
}
