import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { StatusPill } from "@/components/ui/status-pill";
import { Reveal } from "@/components/motion/reveal";
import { BROKER_STATUS_TONE, type BrokerStatus } from "@/lib/strategy-status";

/**
 * Status per broker is derived from the actual state of its adapter, not from
 * intent. Previously all three rendered an identical green "Integrated" badge,
 * which was true for exactly one of them.
 *
 *   T-Invest — registered in bot/broker/registry.py:48; real order path at
 *              bot/broker/tinkoff_client.py:173,215; sandbox by default
 *              (bot/config.py:32)
 *   Bybit    — NOT in registry.py:46-52; order code exists but is unreachable;
 *              used only for balances/positions in
 *              bot/qf_platform/services/portfolio_service.py:80-107
 *   Finam    — nine NotImplementedError at bot/broker/providers/finam.py:63-118,
 *              is_connected=False hardcoded at :56
 */
const BROKERS = [
  { key: "tinvest", status: "active", detailKey: "tinvestDetail", market: "MOEX" },
  { key: "bybit", status: "beta", detailKey: "bybitDetail", market: "Crypto" },
  { key: "finam", status: "planned", detailKey: null, market: "MOEX" },
] as const satisfies readonly {
  key: string;
  status: BrokerStatus;
  detailKey: string | null;
  market: string;
}[];

export async function BrokersSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "brokers" });
  const common = await getTranslations({ locale, namespace: "common" });

  return (
    // Promoted from `tight` to `major`: this opens a new movement — the page
    // stops describing what Quant *is* and starts stating where it actually
    // executes and what it refuses to claim. It was previously the second of two
    // consecutive tight, divider-less sections, which is what collapsed the
    // middle of the page.
    <Section
      id="brokers"
      rhythm="major"
      divider
      glow={<div className="section-glow [--glow-x:50%] [--glow-y:0%]" />}
    >
      <SectionHeader
        id="brokers"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
        note={t("disclosure")}
      />

      <ul className="mt-12 grid gap-5 md:grid-cols-3">
        {BROKERS.map((broker, i) => (
          <li key={broker.key} className="flex">
            <Reveal index={i} className="flex w-full">
              <Surface className="flex w-full flex-col gap-5 p-7">
                <StatusPill
                  className="self-start"
                  tone={BROKER_STATUS_TONE[broker.status]}
                  label={common(`brokerStatus.${broker.status}`)}
                  detail={broker.detailKey ? t(broker.detailKey) : undefined}
                />

                <div className="flex flex-col gap-1.5">
                  <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`${broker.key}Name`)}
                  </h3>
                  <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase">
                    {broker.market}
                  </p>
                </div>

                <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {t(`${broker.key}Body`)}
                </p>
              </Surface>
            </Reveal>
          </li>
        ))}
      </ul>
    </Section>
  );
}
