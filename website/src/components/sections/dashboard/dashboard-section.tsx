import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { ButtonLink } from "@/components/ui/button-link";
import { Reveal } from "@/components/motion/reveal";
import { DashboardTerminal } from "./dashboard-terminal";

/**
 * Server shell for the operator terminal. The interaction — and every honesty
 * constraint on what the panels may display — lives in dashboard-terminal.tsx.
 *
 * ── Composition ──
 *
 * Inverted from the previous version, to match the reference.
 *
 * Before: a six-item tablist in the left column and the panel on the right, so
 * the section opened with a control surface before the reader knew what they
 * were looking at, and the section's own claim sat above the whole thing with
 * no relationship to the artefact.
 *
 * Now: the claim, the caveat and a CTA on the left; one terminal panel on the
 * right, wider, with its tabs inside its own chrome. The honesty line sits
 * beside the claim instead of orphaned under the panel, and the section has a
 * conversion path — it previously had none at all.
 */
export async function DashboardSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "dashboard" });

  return (
    <Section
      id="dashboard"
      rhythm="major"
      divider
      glow={<div className="section-glow [--glow-x:50%] [--glow-y:0%]" />}
    >
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-14">
        {/* ── Left: the claim ──
            Deliberately not `lg:sticky`. A sticky column is a scroll-position
            read in disguise, and this page keeps exactly one of those — in the
            scroll driver. */}
        <div className="flex min-w-0 flex-col gap-8">
          <SectionHeader
            id="dashboard"
            eyebrow={t("eyebrow")}
            heading={t("heading")}
            lead={t("lead")}
            note={t("apiOnlyNote")}
          />

          <Reveal lift={false}>
            <ButtonLink
              href="#access"
              analytics={{ target: "sandbox_access", location: "dashboard" }}
            >
              {t("cta")}
            </ButtonLink>
          </Reveal>
        </div>

        {/* ── Right: the artefact ──
            `lift={false}`: a scale on a panel full of 11px tabular text
            resamples every glyph on the way in. */}
        <Reveal lift={false} className="flex min-w-0 flex-col gap-4">
          <DashboardTerminal />
          <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
            {t("demoNote")}
          </p>
        </Reveal>
      </div>
    </Section>
  );
}
