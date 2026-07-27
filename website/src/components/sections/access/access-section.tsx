import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { ArrowLink } from "@/components/ui/arrow-link";
import { Reveal } from "@/components/motion/reveal";
import { AccessForm } from "./access-form";

/**
 * The single conversion point.
 *
 * Two distinct asks, deliberately unequal: the sandbox request is the primary
 * path and gets the form; live access is a secondary, gated conversation and
 * gets a link. The old page pointed every CTA on the site at one generic
 * "request access" form.
 */
export async function AccessSection({ locale }: { locale: string }) {
  const [t, form] = await Promise.all([
    getTranslations({ locale, namespace: "finalCta" }),
    getTranslations({ locale, namespace: "accessForm" }),
  ]);

  const trust = [t("trust1"), t("trust2"), t("trust3")];

  return (
    <Section
      id="access"
      rhythm="major"
      divider
      glow={
        <div
          className="absolute inset-x-0 bottom-0 h-[420px]"
          style={{
            background:
              "radial-gradient(ellipse 55% 100% at 50% 100%, var(--color-accent-glow), transparent 70%)",
          }}
        />
      }
    >
      <SectionHeader id="access" eyebrow={t("eyebrow")} heading={t("heading")} lead={t("lead")} />

      <div className="mt-12 grid gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-16">
        <Reveal className="flex min-w-0 flex-col gap-8">
          <AccessForm
            emailLabel={form("emailLabel")}
            emailPlaceholder={form("emailPlaceholder")}
            submitLabel={form("submit")}
            submittingLabel={form("submitting")}
            successMessage={form("success")}
            successDetail={form("successDetail")}
            successUndelivered={form("successUndelivered")}
            errorMessage={form("error")}
            networkErrorMessage={form("networkError")}
            consentNote={form("consentNote")}
          />

          <ul className="flex flex-col gap-2.5">
            {trust.map((item) => (
              <li
                key={item}
                className="flex items-center gap-2.5 text-[length:var(--text-body)] text-[color:var(--color-text-secondary)]"
              >
                <span
                  aria-hidden="true"
                  className="size-1.5 shrink-0 rounded-full bg-[color:var(--color-success)]"
                />
                {item}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal index={1} className="min-w-0">
          <Surface className="flex h-full flex-col gap-4 p-7">
            <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
              {t("liveHeading")}
            </h3>
            <p className="flex-1 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
              {t("liveBody")}
            </p>
            <ArrowLink
              href="#pricing"
              analytics={{ target: "live_access", location: "access" }}
            >
              {t("liveCta")}
            </ArrowLink>
          </Surface>
        </Reveal>
      </div>
    </Section>
  );
}
