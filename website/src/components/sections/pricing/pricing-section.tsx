import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { buttonVariants } from "@/components/ui/button";

interface PlanFeature {
  text: string;
  included: boolean;
}

interface Plan {
  title: string;
  price: string;
  body: string;
  features: PlanFeature[];
  featured: boolean;
  badge?: string;
}

export async function PricingSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "pricing" });

  const plans: Plan[] = [
    {
      title: t("planFreeTitle"),
      price: t("planFreePrice"),
      body: t("planFreeBody"),
      featured: false,
      features: [
        { text: "Dashboard read access", included: true },
        { text: "Strategy layer visibility", included: true },
        { text: "Philosophy & engine docs", included: true },
        { text: "Paper trading", included: false },
        { text: "Telegram bot", included: false },
        { text: "Live broker connection", included: false },
      ],
    },
    {
      title: t("planCoreTitle"),
      price: t("planCorePrice"),
      body: t("planCoreBody"),
      featured: true,
      badge: "Most popular",
      features: [
        { text: "Everything in Research", included: true },
        { text: "Paper trading engine", included: true },
        { text: "Telegram bot & alerts", included: true },
        { text: "Full notification stream", included: true },
        { text: "Menu-driven control", included: true },
        { text: "Live broker connection", included: false },
      ],
    },
    {
      title: t("planLiveTitle"),
      price: t("planLivePrice"),
      body: t("planLiveBody"),
      featured: false,
      features: [
        { text: "Everything in Operator", included: true },
        { text: "Live broker connection", included: true },
        { text: "T-Invest & Bybit routing", included: true },
        { text: "Real capital deployment", included: true },
        { text: "Manual review gated", included: true },
        { text: "Priority support", included: true },
      ],
    },
  ];

  return (
    <section
      aria-labelledby="pricing-heading"
      className="relative flex flex-col gap-12 px-[var(--space-page-x)] py-[var(--space-section-y)] overflow-hidden"
    >
      {/* Ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 50% 40% at 50% 0%, rgba(255,138,30,0.06), transparent)",
        }}
      />

      <div className="relative mx-auto flex max-w-[680px] flex-col items-center gap-3 text-center">
        <Reveal>
          <SectionHeading id="pricing-heading" className="mx-auto">
            {t("heading")}
          </SectionHeading>
        </Reveal>
        <Reveal index={1}>
          <p
            className="font-mono text-[11px] uppercase tracking-[0.1em] max-w-[50ch]"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {t("note")}
          </p>
        </Reveal>
      </div>

      <div className="relative mx-auto grid w-full max-w-[1040px] grid-cols-1 gap-4 md:grid-cols-3 md:items-stretch">
        {plans.map((plan, i) => (
          <Reveal key={plan.title} index={i + 2}>
            {plan.featured ? (
              /* Featured plan — animated orange border */
              <div
                className="relative rounded-xl h-full"
                style={{
                  background: "rgba(10,10,12,0.85)",
                  backdropFilter: "blur(24px)",
                  boxShadow: "0 8px 40px rgba(0,0,0,0.5), 0 0 80px rgba(255,138,30,0.08)",
                }}
              >
                {/* Animated border */}
                <div
                  className="absolute inset-0 rounded-xl pointer-events-none"
                  style={{
                    padding: "1px",
                    background: "linear-gradient(135deg, rgba(255,138,30,0.6) 0%, rgba(255,180,94,0.2) 40%, rgba(255,255,255,0.05) 60%, rgba(255,138,30,0.4) 100%)",
                    WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
                    WebkitMaskComposite: "xor",
                    maskComposite: "exclude",
                  }}
                />
                <div className="relative flex h-full flex-col gap-6 p-7">
                  {plan.badge && (
                    <span
                      className="self-start rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em]"
                      style={{
                        background: "rgba(255,138,30,0.15)",
                        color: "var(--color-accent)",
                        border: "1px solid rgba(255,138,30,0.2)",
                      }}
                    >
                      {plan.badge}
                    </span>
                  )}
                  <div className="flex flex-col gap-1.5">
                    <h3
                      className="font-medium text-[17px]"
                      style={{ color: "var(--color-text-primary)" }}
                    >
                      {plan.title}
                    </h3>
                    <p
                      className="font-mono text-[13px] uppercase tracking-[0.06em]"
                      style={{ color: "var(--color-accent)" }}
                    >
                      {plan.price}
                    </p>
                  </div>
                  <p className="flex-1 text-[14px] leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                    {plan.body}
                  </p>
                  <ul className="flex flex-col gap-2">
                    {plan.features.map((f) => (
                      <li key={f.text} className="flex items-center gap-2.5 text-[13px]">
                        <span
                          className="shrink-0 font-mono text-[12px]"
                          style={{ color: f.included ? "var(--color-accent)" : "rgba(255,255,255,0.2)" }}
                        >
                          {f.included ? "✓" : "○"}
                        </span>
                        <span style={{ color: f.included ? "var(--color-text-secondary)" : "rgba(255,255,255,0.25)" }}>
                          {f.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              /* Standard plan */
              <div
                className="glass-premium flex h-full flex-col gap-6 p-7"
              >
                <div className="flex flex-col gap-1.5">
                  <h3
                    className="font-medium text-[17px]"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {plan.title}
                  </h3>
                  <p
                    className="font-mono text-[13px] uppercase tracking-[0.06em]"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    {plan.price}
                  </p>
                </div>
                <p className="flex-1 text-[14px] leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                  {plan.body}
                </p>
                <ul className="flex flex-col gap-2">
                  {plan.features.map((f) => (
                    <li key={f.text} className="flex items-center gap-2.5 text-[13px]">
                      <span
                        className="shrink-0 font-mono text-[12px]"
                        style={{ color: f.included ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.15)" }}
                      >
                        {f.included ? "✓" : "○"}
                      </span>
                      <span style={{ color: f.included ? "var(--color-text-secondary)" : "rgba(255,255,255,0.2)" }}>
                        {f.text}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Reveal>
        ))}
      </div>

      <Reveal index={6} className="relative flex justify-center">
        <a href="#cta-heading" className={buttonVariants({ variant: "outline", size: "lg" })}>
          {t("cta")}
        </a>
      </Reveal>
    </section>
  );
}
