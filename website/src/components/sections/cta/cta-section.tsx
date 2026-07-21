import { getTranslations } from "next-intl/server";
import { SectionHeading } from "@/components/ui/section-heading";
import { Reveal } from "@/components/motion/reveal";
import { BetaForm } from "./beta-form";
import { ExploreLink } from "./explore-link";

export async function CtaSection({ locale }: { locale: string }) {
  const [t, tNav, tBeta] = await Promise.all([
    getTranslations({ locale, namespace: "sections" }),
    getTranslations({ locale, namespace: "nav" }),
    getTranslations({ locale, namespace: "beta" }),
  ]);

  return (
    <section
      aria-labelledby="cta-heading"
      className="relative overflow-hidden px-[var(--space-page-x)] py-[var(--space-section-y)]"
    >
      {/* Single, purposeful ambient glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 60% 50% at 50% 100%, rgba(255,138,30,0.08), transparent)",
        }}
      />

      <div className="relative mx-auto flex max-w-[900px] flex-col gap-10 lg:flex-row lg:items-center lg:justify-between lg:gap-20">
        <Reveal className="flex flex-col items-start gap-7">
          {/* Badge */}
          <span
            className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em]"
            style={{
              background: "rgba(255,138,30,0.08)",
              border: "1px solid rgba(255,138,30,0.18)",
              color: "var(--color-accent)",
            }}
          >
            <span
              className="size-1.5 rounded-full"
              style={{ backgroundColor: "var(--color-accent)", boxShadow: "0 0 6px var(--color-accent)" }}
            />
            Private beta · Limited access
          </span>

          <SectionHeading id="cta-heading" className="max-w-[20ch]">
            {t("ctaHeading")}
          </SectionHeading>

          {/* Trust signals */}
          <div className="flex flex-col gap-2">
            {[
              "No credit card required",
              "Manual review — not self-serve",
              "MOEX & Crypto market access",
            ].map((item) => (
              <div key={item} className="flex items-center gap-2.5">
                <span
                  className="size-1.5 rounded-full shrink-0"
                  style={{ backgroundColor: "var(--color-success)" }}
                />
                <span
                  className="text-[14px]"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  {item}
                </span>
              </div>
            ))}
          </div>

          <BetaForm
            emailLabel={tBeta("emailLabel")}
            emailPlaceholder={tBeta("emailPlaceholder")}
            submitLabel={tBeta("submit")}
            successMessage={tBeta("success")}
            errorMessage={tBeta("error")}
            networkErrorMessage={tBeta("networkError")}
          />
          <ExploreLink label={tNav("explore")} />
        </Reveal>

        {/* Right side: metrics block */}
        <Reveal index={1} className="hidden lg:flex lg:flex-col lg:gap-4 lg:min-w-[220px]">
          {[
            { label: "Win rate", value: "58.6%", highlight: true },
            { label: "Profit factor", value: "1.16×", highlight: false },
            { label: "Strategies tracked", value: "3 active", highlight: false },
            { label: "Markets", value: "MOEX + Crypto", highlight: false },
          ].map(({ label, value, highlight }) => (
            <div
              key={label}
              className="flex flex-col gap-1 rounded-xl p-4"
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <span
                className="font-mono text-[10px] uppercase tracking-[0.14em]"
                style={{ color: "rgba(255,255,255,0.3)" }}
              >
                {label}
              </span>
              <span
                className="font-mono text-[20px] tabular-nums font-semibold"
                style={{
                  letterSpacing: "-0.02em",
                  color: highlight ? "var(--color-accent)" : "rgba(255,255,255,0.85)",
                }}
              >
                {value}
              </span>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
