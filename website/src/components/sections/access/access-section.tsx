import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { InteractiveCard } from "@/components/ui/interactive-card";
import { GridBackplate } from "@/components/ui/grid-backplate";
import { SignalField } from "@/components/ui/signal-field";
import { RouteSpine } from "@/components/ui/route-spine";
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
      {/* The route arrives from the FAQ and terminates *on* the panel below —
          flush, with no margin, so the line meets the panel's top edge instead of
          stopping 40px short of it. A connector that ends in mid-air is the
          "lines end abruptly" note this pass was correcting.

          No node on the leading edge: this is the end of the route, and a
          junction dot at the top of the last connector implies another follows. */}
      <RouteSpine size="md" node={false} />

      {/* Same pointer-lit field as the hero, on the panel that rhymes with it —
          the page is bookended by the two objects that respond to the cursor. */}
      <SignalField className="relative isolate overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--color-border)] bg-[color:var(--color-bg-elevated)] px-6 py-12 shadow-[var(--shadow-panel)] sm:px-10 sm:py-14 lg:px-14 lg:py-16">
        <GridBackplate signal />

        {/* A soft white pool rising from the panel's foot. Well under a "glow"
            at this alpha — the point is only that the black is not flat. */}
        <div
          aria-hidden="true"
          className="section-glow pointer-events-none [--glow-x:50%] [--glow-y:100%]"
        />

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
