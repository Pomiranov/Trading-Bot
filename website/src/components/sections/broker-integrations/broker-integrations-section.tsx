import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";

const BROKER_ICONS: Record<string, string> = {
  "T-INVEST": "T",
  "BYBIT": "B",
  "FINAM": "F",
};

const BROKER_COLORS: Record<string, string> = {
  "T-INVEST": "#ffcc00",
  "BYBIT": "#f7931a",
  "FINAM": "#e05c29",
};

export async function BrokerIntegrationsSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "brokerIntegrations" });

  const brokers = [
    { id: "T-INVEST", title: t("tinkoffTitle"), body: t("tinkoffBody"), market: "MOEX" },
    { id: "BYBIT", title: t("bybitTitle"), body: t("bybitBody"), market: "Crypto" },
    { id: "FINAM", title: t("finamTitle"), body: t("finamBody"), market: "MOEX" },
  ];

  return (
    <section
      aria-labelledby="broker-integrations-heading"
      className="flex flex-col gap-12 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <Reveal>
          <SectionHeading id="broker-integrations-heading" className="max-w-[22ch]">
            {t("heading")}
          </SectionHeading>
        </Reveal>
        <Reveal index={1}>
          <p
            className="max-w-[52ch] text-[15px] leading-relaxed md:text-right"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {t("intro")}
          </p>
        </Reveal>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {brokers.map((broker, i) => (
          <Reveal key={broker.id} index={i + 2}>
            <div
              className="glass-premium flex h-full flex-col gap-5 p-6"
              style={{ position: "relative" }}
            >
              {/* Broker logo mark */}
              <div className="flex items-start justify-between">
                <div
                  className="flex size-10 items-center justify-center rounded-lg font-mono text-[15px] font-bold"
                  style={{
                    background: `rgba(${BROKER_COLORS[broker.id]
                      .match(/[\da-f]{2}/gi)!
                      .map((h) => parseInt(h, 16))
                      .join(",")}, 0.12)`,
                    color: BROKER_COLORS[broker.id],
                    border: `1px solid ${BROKER_COLORS[broker.id]}22`,
                  }}
                >
                  {BROKER_ICONS[broker.id]}
                </div>
                <span
                  className="font-mono text-[10px] uppercase tracking-[0.14em] rounded-full px-2.5 py-1"
                  style={{
                    color: "rgba(255,255,255,0.4)",
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  {broker.market}
                </span>
              </div>

              <div className="flex flex-col gap-1.5">
                <span
                  className="font-mono text-[10px] uppercase tracking-[0.14em]"
                  style={{ color: "rgba(255,255,255,0.3)" }}
                >
                  {broker.id}
                </span>
                <h3
                  className="font-medium text-[16px]"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {broker.title}
                </h3>
              </div>

              <p
                className="text-[14px] leading-relaxed"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {broker.body}
              </p>

              {/* Connected indicator */}
              <div className="flex items-center gap-2 mt-auto pt-2">
                <span
                  className="size-1.5 rounded-full"
                  style={{
                    backgroundColor: "var(--color-success)",
                    boxShadow: "0 0 5px var(--color-success)",
                  }}
                />
                <span
                  className="font-mono text-[10px] uppercase tracking-[0.12em]"
                  style={{ color: "rgba(255,255,255,0.3)" }}
                >
                  Integrated
                </span>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
