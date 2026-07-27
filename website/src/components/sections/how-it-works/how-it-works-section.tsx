import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { MonoLabel } from "@/components/ui/mono-label";
import { AsideNote } from "@/components/ui/aside-note";
import { Reveal } from "@/components/motion/reveal";
import { PipelineSpine } from "./pipeline-spine";

/**
 * The decision path, told twice: a plain sentence first, then the module that
 * performs it. Every `sourceRef` resolves to a real symbol in the Python
 * codebase — the most verifiable claim on the site, kept intact.
 *
 * The layout mechanics, and the two failed versions that produced them, are
 * documented in `pipeline-spine.tsx`. The short form: layout plus
 * IntersectionObserver only, because the pinned-ScrollTrigger version of this
 * section is where the backward-scroll bug lived.
 *
 * ── What left this section ──
 *
 * It used to carry three separate arguments in one 2 543px block — the
 * pipeline, the confidence bounds and the manifesto — which made it 1 286px
 * longer than anything else on the page and meant its own H2 was two screens
 * gone by the time a reader reached the third topic.
 *
 *   • The manifesto is now `#foundation`, its own titled section.
 *   • The confidence bounds now sit *inside the belief-gate node*, which is
 *     where they belong: they are literally that gate's parameters, and a
 *     reader now meets them at the moment the gate is being explained rather
 *     than as three unlabelled figures several hundred pixels further down.
 */
export async function HowItWorksSection({ locale }: { locale: string }) {
  const [stages, learning, t, common] = await Promise.all([
    contentSource.getPipelineStages(locale),
    contentSource.getLearningSystemCopy(locale),
    getTranslations({ locale, namespace: "how" }),
    getTranslations({ locale, namespace: "common" }),
  ]);

  const techLabel = common("technical");

  /**
   * System constants from the code, never results:
   * `MIN_TRADES_FOR_CONFIDENCE` and the MIN/MAX_CONFIDENCE clamps in
   * bot/learning/belief_updater.py:37,46-47.
   *
   * These are values an operator configures before the first trade, not
   * anything the system achieved. They stay under the section's own
   * "confidence bounds" label so they can never be skimmed as performance.
   */
  const bounds = [
    { value: String(learning.minTradesFloor), label: t("minTradesLabel") },
    { value: learning.minConfidence.toFixed(2), label: t("minConfidenceLabel") },
    { value: learning.maxConfidence.toFixed(2), label: t("maxConfidenceLabel") },
  ];

  // Keyed by id rather than by index, so reordering the MDX files cannot
  // silently attach the belief gate's parameters to a different stage.
  const beliefGate = stages.find((s) => s.id === "belief-gate");

  const extras = beliefGate
    ? {
        [beliefGate.id]: (
          <div className="flex flex-col gap-3 border-t border-[color:var(--color-border)] pt-4">
            <MonoLabel as="span">{t("constantsHeading")}</MonoLabel>
            <dl className="grid grid-cols-3 gap-3">
              {bounds.map((b) => (
                <div key={b.label} className="flex min-w-0 flex-col gap-1">
                  <dt className="sr-only">{b.label}</dt>
                  <dd className="font-mono text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-semibold tabular-nums tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                    {b.value}
                  </dd>
                  {/* aria-hidden: the <dt> above already carries this text for
                      assistive tech, and repeating it would read the label
                      twice per figure. */}
                  <p
                    aria-hidden="true"
                    className="font-mono text-[length:var(--text-label)] leading-[1.3] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-quaternary)] uppercase"
                  >
                    {b.label}
                  </p>
                </div>
              ))}
            </dl>
          </div>
        ),
      }
    : undefined;

  return (
    <Section
      id="how-it-works"
      rhythm="major"
      divider
      glow={<div className="section-glow [--glow-x:50%] [--glow-y:0%]" />}
      className="flex flex-col gap-[var(--space-header-to-body)]"
    >
      <SectionHeader
        id="how-it-works"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
        note={t("rulesNote")}
      />

      <PipelineSpine stages={stages} techLabel={techLabel} extras={extras} />

      {/* The loop closes below the last node, as a terminal element on the
          spine rather than a full-width card. Previously stage 07 was spanned
          across the whole grid to absorb this note, which made the loop-closer
          the visually heaviest card in the section and inverted the reading
          order of the seven stages. Indented to the spine's right-hand column
          at lg so it reads as hanging off the end of the line. */}
      <Reveal lift={false} className="lg:pl-[calc(50%+2.25rem)]">
        <AsideNote className="max-w-[62ch]">{t("loopNote")}</AsideNote>
      </Reveal>

      <Reveal lift={false}>
        <div className="max-w-[72ch] text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
          {learning.intro}
        </div>
      </Reveal>
    </Section>
  );
}
