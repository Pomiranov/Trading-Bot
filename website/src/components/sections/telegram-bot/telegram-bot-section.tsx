import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";

const FEATURE_ICONS = ["⚡", "⌨", "⚖"];

export async function TelegramBotSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "telegramBot" });

  const features = [
    { title: t("feature1Title"), body: t("feature1Body"), icon: FEATURE_ICONS[0] },
    { title: t("feature2Title"), body: t("feature2Body"), icon: FEATURE_ICONS[1] },
    { title: t("feature3Title"), body: t("feature3Body"), icon: FEATURE_ICONS[2] },
  ];

  return (
    <section
      id="telegram-bot"
      aria-labelledby="telegram-bot-heading"
      className="flex flex-col gap-12 px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      <div className="mx-auto flex max-w-[860px] flex-col gap-4 text-center">
        <Reveal>
          <SectionHeading id="telegram-bot-heading" className="mx-auto max-w-[26ch]">
            {t("heading")}
          </SectionHeading>
        </Reveal>
        <Reveal index={1}>
          <p
            className="mx-auto max-w-[58ch] text-[15px] leading-relaxed"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {t("intro")}
          </p>
        </Reveal>
      </div>

      <div className="mx-auto grid w-full max-w-[1040px] grid-cols-1 gap-4 md:grid-cols-3">
        {features.map((feature, i) => (
          <Reveal key={feature.title} index={i}>
            <div className="glass-premium flex h-full flex-col gap-5 p-7">
              {/* Icon mark */}
              <div
                className="flex size-10 items-center justify-center rounded-lg text-[20px]"
                style={{
                  background: "rgba(255,138,30,0.08)",
                  border: "1px solid rgba(255,138,30,0.12)",
                }}
              >
                {feature.icon}
              </div>

              <div className="flex flex-col gap-2">
                <h3
                  className="font-medium text-[16px]"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {feature.title}
                </h3>
                <p
                  className="text-[14px] leading-relaxed"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  {feature.body}
                </p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
