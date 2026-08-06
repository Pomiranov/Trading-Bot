import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { InteractiveCard } from "@/components/ui/interactive-card";
import { GridBackplate } from "@/components/ui/grid-backplate";
import { SignalField } from "@/components/ui/signal-field";
import { Reveal } from "@/components/motion/reveal";
import { AccessForm } from "./access-form";

/**
 * The single conversion point, as a contained closing panel.
 *
 * ── Composition ──
 *
 * A rounded panel on `--color-bg-elevated`, inset from the page edges,
 * deliberately rhyming with the hero panel so the page reads as bookended. This
 * is the reference's closing block.
 *
 * Two distinct asks, and they must look unequal, because they are: the sandbox
 * request is the primary path and gets the form; live access is a secondary,
 * gated conversation and gets a card. The previous `1.1fr / 0.9fr` split read
 * as near-equal for two deliberately unequal things.
 *
 * ── The form is not touched ──
 *
 * `access-form.tsx` -> `/api/beta` -> `lib/beta/{schema,adapter}` keeps its
 * react-hook-form + zod validation, all of its states, and its error handling.
 * Styling only. In particular the `successUndelivered` state stays: it tells
 * the truth when the adapter fails, and it is the single most honest state on
 * the site.
 */
export async function AccessSection({ locale }: { locale: string }) {
  const [t, form] = await Promise.all([
    getTranslations({ locale, namespace: "finalCta" }),
    getTranslations({ locale, namespace: "accessForm" }),
  ]);

  const trust = [t("trust1"), t("trust2"), t("trust3")];

  return (
    <Section id="access" rhythm="major">
      {/* Same pointer-lit field as the hero, on the panel that rhymes with it —
          the page is bookended by the two objects that respond to the cursor. */}
      <SignalField className="relative isolate overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--color-border)] bg-[color:var(--color-bg-elevated)] px-6 py-12 shadow-[var(--shadow-panel)] sm:px-10 sm:py-14 lg:px-14 lg:py-16">
        {/*
          `mask="panel"`, not the hero's default ellipse.

          This panel is ~1210×740 at 1440px, and the `pool` mask is a centred
          ellipse covering x 10–90% and y 10–80% of whatever it is applied to.
          On a near-square panel that reaches all four edges at about the same
          rate; on this one it left every vertical line stopping ~110px short of
          the panel's foot and every horizontal one ~120px short of its right
          edge. Measured, that is what the "random floating lines" in the closing
          block actually were — not stray elements, but a grid whose falloff was
          tuned for a different aspect ratio, cut off mid-line with nothing to
          explain the terminus.

          `panel` fades each axis independently over a long ramp, so the lines
          dissolve instead of ending. See EDGE_FADE in ui/grid-backplate.tsx.
        */}
        <GridBackplate signal mask="panel" />

        {/*
          ── Removed: the white pool at the panel's foot ──

          A `.section-glow` at `--glow-y: 100%`, i.e. a radial centred on the
          bottom edge. On the hero the same layer works because it is offset to
          one side and reads as the aperture sitting in light; here it was
          centred under the form, so the panel had a bright base and dark
          shoulders with no object to justify the gradient. Against the grid it
          also washed out the middle rows while leaving the outer ones visible,
          which is the second half of why the block read as "random glow".

          Removed on owner direction: the closing block should be clean and
          quiet. The panel's own `--color-bg-elevated` fill already lifts it off
          the page, and the pointer field is now the only light in it — which
          means the one thing that glows here is the one thing responding to the
          reader.
        */}

        <div className="relative">
          <SectionHeader
            id="access"
            eyebrow={t("eyebrow")}
            heading={t("heading")}
            lead={t("lead")}
          />

          {/*
            `items-stretch` (the grid default, restated by not overriding it) plus
            `h-full` on the card's own wrapper below. Without both, the Live card
            sized to its content and stopped ~140px short of the form column,
            which is what made the panel look bottom-heavy on the left.

            The 1.25 / 0.75 split stays. The two asks are deliberately unequal —
            the sandbox request is the primary path and gets the form; live access
            is a gated conversation and gets a card — and evening them to 1fr each
            would say they are the same size of decision.
          */}
          <div className="mt-[var(--space-header-to-body)] grid gap-10 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)] lg:gap-16">
            <Reveal lift={false} className="flex min-w-0 flex-col gap-8">
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
                    {/*
                      Re-toned away from --color-success.

                      Green is trade semantics on this site — a confirmed or
                      healthy trade state — and this was the only place it
                      appeared decoratively. Using it for three reassurance
                      bullets quietly weakened the rule everywhere else, which
                      matters because green is load-bearing in the broker and
                      strategy statuses.
                    */}
                    <span
                      aria-hidden="true"
                      className="size-1.5 shrink-0 rounded-[var(--radius-full)] bg-[color:var(--color-text-quaternary)]"
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </Reveal>

            {/* The secondary ask. A route card, so the whole surface navigates —
                this was the last of the four cards on the page that contained a
                link and still computed `cursor: default`. `h-full` is what makes
                it reach the foot of the form column beside it. */}
            <Reveal index={1} lift={false} className="flex h-full min-w-0">
              <InteractiveCard
                href="#pricing"
                label={t("liveCta")}
                analytics={{ target: "live_access", location: "access" }}
              >
                <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                  {t("liveHeading")}
                </h3>
                <p className="flex-1 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {t("liveBody")}
                </p>
              </InteractiveCard>
            </Reveal>
          </div>
        </div>
      </SignalField>
    </Section>
  );
}
