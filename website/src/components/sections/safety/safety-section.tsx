import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { Reveal } from "@/components/motion/reveal";

/**
 * The section that matters most, because Quant can place orders in someone's
 * brokerage account.
 *
 * Every claim here is backed by code, and the two places where the guarantee
 * is *incomplete* are stated rather than omitted:
 *
 *   item4 — there is no automatic kill switch. Drawdown is alert-only
 *           (bot/ui/telegram_bot.py:860); the stop is manual
 *           (bot/services/bot_engine.py:91-102).
 *   caveat — the credential vault is opt-in via SECRETS_MASTER_KEY; without it
 *           credentials fall back to a plain .env
 *           (bot/security/credential_store.py:50-57).
 *
 * The strongest claim is item1, and it is verified by absence: BrokerAdapter
 * (bot/broker/base.py:141-219) declares no withdraw or transfer method at all.
 */
const ITEMS = ["item1", "item2", "item3", "item4", "item5", "item6"] as const;

export async function SafetySection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "safety" });

  return (
    <Section id="safety" rhythm="default" divider>
      <SectionHeader id="safety" eyebrow={t("eyebrow")} heading={t("heading")} lead={t("lead")} />

      <ul className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {ITEMS.map((item, i) => (
          <li key={item} className="flex">
            <Reveal index={i} className="flex w-full">
              <Surface className="flex w-full flex-col gap-3 p-7">
                <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                  {t(`${item}Title`)}
                </h3>
                <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {t(`${item}Body`)}
                </p>
              </Surface>
            </Reveal>
          </li>
        ))}
      </ul>

      <Reveal className="mt-8">
        <p className="max-w-[80ch] border-l-2 border-[color:var(--color-border-strong)] pl-5 text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-tertiary)]">
          {t("keysCaveat")}
        </p>
      </Reveal>
    </Section>
  );
}
