import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { DeviceFrame } from "@/components/ui/device-frame";
import { Reveal } from "@/components/motion/reveal";
import { SignalCard } from "./signal-card";

const FEATURES = ["f1", "f2", "f3", "f4"] as const;

/**
 * Telegram as the second interface onto the same state.
 *
 * ── The emphasis is inverted from the previous version ──
 *
 * It used to give four static text cards more area than the one thing on this
 * page a visitor can actually press: `lg:grid-cols-[1fr_0.8fr]`, features left
 * and larger, the interactive card right and smaller. And by this point in the
 * page a reader has met roughly twenty identically-treated bordered boxes, so
 * four more added nothing except length.
 *
 * Now the features are a hairline-separated list — they are four facts, and a
 * fact does not need a card — and the signal card sits in a phone frame at
 * equal weight. The device is what makes "оператор в кармане" read instantly
 * rather than having to be explained.
 *
 * ── Do not regress the card to a mock ──
 *
 * `SignalCard` is a client component so its two buttons can genuinely be
 * pressed. A previous version drew `aria-hidden` <span>s styled to look like
 * controls, which is exactly the "raw" impression this section was corrected
 * for. The frame around it is `aria-hidden` scaffolding only; nothing about the
 * card's behaviour changes.
 */
export async function TelegramSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "telegram" });

  return (
    // `tight` and it stays: Telegram is the second interface onto the *same
    // state* as the dashboard above, so the two belong to one movement. The
    // divider is what keeps them distinct without adding a full section gap.
    <Section id="telegram" rhythm="tight" divider>
      <SectionHeader id="telegram" eyebrow={t("eyebrow")} heading={t("heading")} lead={t("lead")} />

      <div className="mt-[var(--space-header-to-body)] grid items-start gap-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)] lg:gap-16">
        {/* ── Features, as a list ──
            No hover state on the rows: a hover on something that does not
            navigate is a false affordance, and these do not. */}
        <Reveal lift={false}>
          <ul className="flex flex-col">
            {FEATURES.map((f) => (
              <li
                key={f}
                className="flex flex-col gap-2 border-t border-[color:var(--color-border)] py-5 first:border-t-0 first:pt-0"
              >
                <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                  {t(`${f}Title`)}
                </h3>
                <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {t(`${f}Body`)}
                </p>
              </li>
            ))}
          </ul>
        </Reveal>

        {/* ── The artefact ── */}
        <Reveal index={1} lift={false} className="min-w-0">
          <DeviceFrame>
            <SignalCard />
          </DeviceFrame>
        </Reveal>
      </div>
    </Section>
  );
}
