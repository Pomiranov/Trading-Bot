import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";

function IconSignal() {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className="size-5">
      <circle cx="10" cy="10" r="2.5" fill="currentColor" />
      <path d="M5.6 14.4a6.4 6.4 0 0 1 0-8.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M14.4 5.6a6.4 6.4 0 0 1 0 8.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M3 17a9.9 9.9 0 0 1 0-14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M17 3a9.9 9.9 0 0 1 0 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconMenu() {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className="size-5">
      <rect x="3" y="4" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="4" width="5.5" height="5.5" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="3" y="12" width="5.5" height="4" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="12" width="5.5" height="4" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function IconSync() {
  return (
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className="size-5">
      <path d="M3.5 10A6.5 6.5 0 0 1 10 3.5a6.5 6.5 0 0 1 5.5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16.5 10A6.5 6.5 0 0 1 10 16.5a6.5 6.5 0 0 1-5.5-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M13.5 6.5 16 9l2.5-2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6.5 13.5 4 11l-2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const FEATURE_ICONS = [IconSignal, IconMenu, IconSync];

export async function TelegramBotSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "telegramBot" });

  const features = [
    { title: t("feature1Title"), body: t("feature1Body"), Icon: FEATURE_ICONS[0] },
    { title: t("feature2Title"), body: t("feature2Body"), Icon: FEATURE_ICONS[1] },
    { title: t("feature3Title"), body: t("feature3Body"), Icon: FEATURE_ICONS[2] },
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
                className="flex size-10 items-center justify-center rounded-lg"
                style={{
                  background: "rgba(255,138,30,0.08)",
                  border: "1px solid rgba(255,138,30,0.12)",
                  color: "var(--color-accent)",
                }}
              >
                <feature.Icon />
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
