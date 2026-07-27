import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { StatusChip } from "@/components/ui/status-chip";
import { MonoLabel } from "@/components/ui/mono-label";
import { Reveal } from "@/components/motion/reveal";
import { RouteDiagram } from "./route-diagram";
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
 *
 * ── beta vs planned ──
 *
 * Both map to the `muted` tone, and that is correct: neither is
 * production-ready, and tinting either one green would be a claim the adapter
 * cannot support. But it also made a partially-working integration and an
 * unimplemented stub chromatically identical, in a section where status is the
 * entire information content. `StatusChip`'s `outline` variant separates them —
 * `beta` solid, `planned` dashed outline — without either reading as shipped.
 *
 * ── Logos ──
 *
 * The reference shows broker marks. They are deliberately not used here:
 * third-party trademarks carry usage questions that are not resolved, and a
 * Finam logo beside `planned` would overstate a relationship that is nine
 * NotImplementedError. Text-only until usage rights are confirmed, and never
 * beside a planned route.
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

  const routeSteps = [
    t("routeStep1"),
    t("routeStep2"),
    t("routeStep3"),
    t("routeStep4"),
  ] as const;

  return (
    // `major`: this opens a new movement — the page stops describing what Quant
    // *is* and starts stating where it actually executes and what it refuses to
    // claim.
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

      {/* ── Route diagram ──
          Topology only. See route-diagram.tsx for what it deliberately does
          not claim. */}
      <Reveal lift={false} className="mt-[var(--space-header-to-body)] flex flex-col gap-5">
        <MonoLabel>{t("routeHeading")}</MonoLabel>
        <RouteDiagram steps={routeSteps} />
        <p className="max-w-[72ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
          {t("routeNote")}
        </p>
      </Reveal>

      {/* sm:grid-cols-2 added — at 768px three cards were ~230px wide holding a
          chip whose `detail` suffix wrapped to three lines. */}
      <ul className="mt-[var(--space-block)] grid gap-[var(--space-card-gap)] sm:grid-cols-2 lg:grid-cols-3">
        {BROKERS.map((broker, i) => (
          <li key={broker.key} className="flex">
            <Reveal index={i} className="flex w-full">
              <Surface padding="md" className="flex w-full flex-col gap-5">
                <StatusChip
                  className="self-start"
                  tone={BROKER_STATUS_TONE[broker.status]}
                  variant={broker.status === "planned" ? "outline" : "solid"}
                  label={common(`brokerStatus.${broker.status}`)}
                  detail={broker.detailKey ? t(broker.detailKey) : undefined}
                />

                <div className="flex flex-col gap-1.5">
                  <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`${broker.key}Name`)}
                  </h3>
                  {/* Promoted out of --color-text-quaternary: which market a
                      route reaches is the second-most-useful fact in this
                      section and it was rendered at the dimmest level on the
                      page. */}
                  <p className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
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
