import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { AsideNote } from "@/components/ui/aside-note";
import { Reveal } from "@/components/motion/reveal";

/**
 * The section that matters most, because Quant can place orders in someone's
 * brokerage account.
 *
 * Every claim here is backed by code, and the places where the guarantee is
 * *incomplete* are stated rather than omitted:
 *
 *   item4  — there is no automatic kill switch. Drawdown is alert-only
 *            (bot/ui/telegram_bot.py:860); the stop is manual
 *            (bot/services/bot_engine.py:91-102).
 *   item6  — confidence is clamped to 0.05–0.95 and never becomes certainty.
 *   caveat — the credential vault is opt-in via SECRETS_MASTER_KEY; without it
 *            credentials fall back to a plain .env
 *            (bot/security/credential_store.py:50-57).
 *
 * The strongest claim is item1, and it is verified by absence: BrokerAdapter
 * (bot/broker/base.py:141-219) declares no withdraw or transfer method at all.
 *
 * ── Why the six cards are now two groups ──
 *
 * They used to be one uniform `md:2 lg:3` grid, which meant the two items that
 * describe *limits* looked exactly like the four that describe reassurances.
 * The honesty was present in the copy and invisible in the design — and on a
 * page about letting software touch a brokerage account, the caveats are the
 * differentiator and the part most worth reading.
 *
 * So they are split, and the limits group is deliberately given *more* weight:
 * a raised surface, wider cards, larger padding, a left rule, body copy at full
 * primary contrast rather than secondary, and the vault caveat beneath it in
 * the `caveat` tone. These must never be softened or equalised upward.
 */
const GUARANTEES = ["item1", "item2", "item3", "item5"] as const;
const LIMITS = ["item4", "item6"] as const;

export async function SafetySection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "safety" });

  return (
    <Section id="safety" rhythm="default" divider>
      <SectionHeader id="safety" eyebrow={t("eyebrow")} heading={t("heading")} lead={t("lead")} />

      {/* ── Guarantees ── */}
      <div className="mt-[var(--space-header-to-body)] flex flex-col gap-5">
        <MonoLabel>{t("guaranteesHeading")}</MonoLabel>
        <ul className="grid gap-[var(--space-card-gap)] sm:grid-cols-2 lg:grid-cols-4">
          {GUARANTEES.map((item, i) => (
            <li key={item} className="flex">
              <Reveal index={i} className="flex w-full">
                <Surface padding="md" className="flex w-full flex-col gap-3">
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
      </div>

      {/* ── Where the guarantee stops ──
          Two cards spanning the width the four above occupy, raised, with more
          padding and a left rule. Heavier than the guarantees, on purpose. */}
      <div className="mt-[var(--space-block)] flex flex-col gap-5">
        <MonoLabel>{t("limitsHeading")}</MonoLabel>
        <ul className="grid gap-[var(--space-card-gap)] md:grid-cols-2">
          {LIMITS.map((item, i) => (
            <li key={item} className="flex">
              <Reveal index={i} className="flex w-full">
                <Surface
                  variant="raised"
                  padding="lg"
                  className="flex w-full flex-col gap-3 border-l-2 border-l-[color:var(--color-text-secondary)]"
                >
                  <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`${item}Title`)}
                  </h3>
                  <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-primary)]">
                    {t(`${item}Body`)}
                  </p>
                </Surface>
              </Reveal>
            </li>
          ))}
        </ul>

        <Reveal lift={false}>
          <AsideNote tone="caveat" className="max-w-[80ch]">
            {t("keysCaveat")}
          </AsideNote>
        </Reveal>
      </div>
    </Section>
  );
}
