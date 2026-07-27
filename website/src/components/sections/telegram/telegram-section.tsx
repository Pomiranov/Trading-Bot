import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { Reveal } from "@/components/motion/reveal";
import { SignalCard } from "./signal-card";

const FEATURES = ["f1", "f2", "f3", "f4"] as const;

/**
 * Telegram as the second interface onto the same state.
 *
 * The signal card is a client component so its two buttons can actually be
 * pressed — see signal-card.tsx, including why the demo copy is worded the way
 * it is. Previously the buttons were `aria-hidden` <span>s drawn to look like
 * controls, which is exactly the "raw" impression the owner flagged.
 */
export async function TelegramSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "telegram" });

  return (
    // `tight` is correct here and stays: Telegram is the *second interface onto
    // the same state* as the dashboard above, so the two belong to one movement.
    // What was missing is the `divider` — without it the two sections had
    // neither air nor a line between them and simply ran together, which is the
    // "glued" reading the owner flagged. Tight plus a hairline says "closely
    // related, still distinct".
    <Section id="telegram" rhythm="tight" divider>
      <SectionHeader id="telegram" eyebrow={t("eyebrow")} heading={t("heading")} lead={t("lead")} />

      <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)] lg:gap-14">
        {/* ── Features ── */}
        <ul className="grid gap-5 sm:grid-cols-2">
          {FEATURES.map((f, i) => (
            <li key={f} className="flex">
              <Reveal index={i} className="flex w-full">
                <Surface className="flex w-full flex-col gap-3 p-6">
                  <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {t(`${f}Title`)}
                  </h3>
                  <p className="text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                    {t(`${f}Body`)}
                  </p>
                </Surface>
              </Reveal>
            </li>
          ))}
        </ul>

        {/* ── Interactive example signal card ── */}
        <Reveal index={2} lift={false}>
          <SignalCard />
        </Reveal>
      </div>
    </Section>
  );
}
