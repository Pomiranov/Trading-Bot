import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { SectionSceneMount } from "@/components/scene/section-scene-mount";
import { BetaForm } from "./beta-form";
import { ExploreLink } from "./explore-link";

export async function CtaSection({ locale }: { locale: string }) {
  const [t, tNav, tBeta, tScene] = await Promise.all([
    getTranslations({ locale, namespace: "sections" }),
    getTranslations({ locale, namespace: "nav" }),
    getTranslations({ locale, namespace: "beta" }),
    getTranslations({ locale, namespace: "scene" }),
  ]);

  return (
    <section
      aria-labelledby="cta-heading"
      className="flex flex-col items-start gap-10 px-[var(--space-page-x)] py-[var(--space-section-y)] lg:flex-row lg:items-center lg:justify-between"
    >
      <Reveal className="flex flex-col items-start gap-6">
        <SectionHeading id="cta-heading" className="max-w-[20ch]">
          {t("ctaHeading")}
        </SectionHeading>
        <BetaForm
          emailLabel={tBeta("emailLabel")}
          emailPlaceholder={tBeta("emailPlaceholder")}
          submitLabel={tBeta("submit")}
          successMessage={tBeta("success")}
          errorMessage={tBeta("error")}
        />
        <ExploreLink label={tNav("explore")} />
      </Reveal>
      <Reveal index={1} className="hidden w-[180px] shrink-0 lg:block">
        <SectionSceneMount mode="final-cta" caption={tScene("finalCta.label")} />
      </Reveal>
    </section>
  );
}
