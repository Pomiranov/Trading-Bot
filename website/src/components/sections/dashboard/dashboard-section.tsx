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
    /*
      No `glow`, for the same reason `#how-it-works` lost its: a radial pool
      centred on the section's own top edge, directly under a hairline divider,
      reads as a seam rather than as depth. The hairline divider alone is the
      entrance, and it says everything the pool was trying to.
    */
    <Section id="dashboard" rhythm="major" divider>
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-14">
        {/* ── Left: the claim ──
            Deliberately not `lg:sticky`. A sticky column is a scroll-position
            read in disguise, and this page keeps exactly one of those — in the
            scroll driver. */}
        <div className="flex min-w-0 flex-col gap-8">
          {/*
            No `note`.

            `apiOnlyNote` explained that Risk is API-only and that two product
            areas are absent from the demo — three caveats about the *composition
            of a mock*, in the header of the section whose job is to make the
            product feel real. Removed on owner direction. What replaces it is
            nothing: the terminal is labelled a demo in its own chrome and by the
            caption under it, which is the honest part, and the rest was
            changelog.
          */}
          <SectionHeader
            id="dashboard"
            eyebrow={t("eyebrow")}
            heading={t("heading")}
            lead={t("lead")}
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
          {/* Trimmed to the disclaimer alone. Its first sentence repeated the
              section lead verbatim; what has to survive is the statement that
              the figures in the panel are illustrative, because that is the
              guarantee that stops them reading as results. */}
          <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
            {t("demoNote")}
          </p>
        </Reveal>
      </div>
    </Section>
  );
}
