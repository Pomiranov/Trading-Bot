import { getTranslations } from "next-intl/server";
import { HeroSceneMount } from "./hero-scene-mount";

/**
 * 3D belief network center-right, editorial headline center-left (brief
 * spec). Final motion polish (magnetic scroll cue, scroll-driven camera
 * dolly) lands in Phase 4 — this is the structural + 3D pass.
 */
export async function HeroSection({ locale }: { locale: string }) {
  const [t, tScene] = await Promise.all([
    getTranslations({ locale, namespace: "hero" }),
    getTranslations({ locale, namespace: "scene" }),
  ]);

  return (
    <section
      aria-labelledby="hero-heading"
      className="flex min-h-dvh flex-col items-center justify-center gap-10 px-[var(--space-page-x)] md:flex-row md:justify-between md:gap-6"
    >
      <div className="flex flex-col items-start gap-6 md:max-w-[52%]">
        <p className="font-mono text-[length:var(--text-label)] uppercase tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)]">
          {t("statusLive")} · {t("statusMarket")} · {t("statusStrategy")}
        </p>
        <h1
          id="hero-heading"
          className="max-w-[20ch] text-[length:var(--text-hero)] font-medium leading-[var(--text-hero--line-height)] tracking-[var(--text-hero--letter-spacing)] text-[color:var(--color-text-primary)]"
        >
          {t("tagline1")}
          <br />
          <span className="mb-1 block font-serif italic font-normal leading-[1.1] pb-1">
            {t("tagline2")}
          </span>
        </h1>
        <p className="max-w-[480px] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] text-[color:var(--color-text-secondary)]">
          {t("subline")}
        </p>
      </div>
      <HeroSceneMount caption={tScene("hero.caption")} />
    </section>
  );
}
