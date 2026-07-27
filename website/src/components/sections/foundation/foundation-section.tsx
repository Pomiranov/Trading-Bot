import { getTranslations } from "next-intl/server";
import { contentSource } from "@/content-layer/source";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { RouteSpine } from "@/components/ui/route-spine";
import { Reveal } from "@/components/motion/reveal";

/**
 * The manifesto — three numbered principles, each sourced from
 * `content/{ru,en}/philosophy/*.mdx` and most of them carrying a `sourceRef`
 * into the Python codebase.
 *
 * ── Why this is now its own section ──
 *
 * It used to be the *third* topic inside `#how-it-works`, opening with an 11px
 * mono label roughly 2 200px below that section's own H2. Measured: the parent
 * section was 2 543px tall — 1 286px longer than anything else on the page —
 * and by the time a reader reached this block the heading it supposedly
 * belonged to had been off-screen for two full screens.
 *
 * A file comment in the old implementation put it exactly right: "this is a
 * manifesto, not a footnote to the paragraph above it". The fix applied at the
 * time was a rule and 96px of padding, which did not change the fact that the
 * page's strongest positioning argument had no title.
 *
 * Extracting it fixes four things at once: the section-length outlier, the
 * uneven rhythm around it, the missing anchor target, and the reference's own
 * Foundation fragment, which is a titled section with an eyebrow, an H2 and
 * three numbered cards.
 *
 * ── Paper ──
 *
 * One of the two inverted bands on the page. This is the strongest candidate
 * for it: the contrast flip gives the manifesto the weight the copy already
 * claims, and it breaks up ~7 000px of unrelieved black at the point where the
 * argument shifts from mechanism to principle. Reverting is `tone="dark"`.
 */
export async function FoundationSection({ locale }: { locale: string }) {
  const [principles, t] = await Promise.all([
    contentSource.getPhilosophyBlocks(locale),
    getTranslations({ locale, namespace: "foundation" }),
  ]);

  return (
    <Section id="foundation" rhythm="major" tone="paper">
      <SectionHeader
        id="foundation"
        eyebrow={t("eyebrow")}
        heading={t("heading")}
        lead={t("lead")}
      />

      {/* The route arrives from the transition band above, then fans out to the
          three principles — so the cards read as *what the line leads to* rather
          than as a grid that happens to sit here. Graphite rather than cold blue,
          automatically: `.section-paper` re-points `--color-route-stroke`. */}
      <RouteSpine variant="fan" lanes={3} size="md" node={false} className="mt-8" />

      <ol className="mt-6 grid gap-[var(--space-card-gap)] md:grid-cols-3">
        {principles.map((block, i) => (
          <li key={block.id} className="flex">
            <Reveal index={i} className="flex w-full">
              <Surface padding="lg" className="flex w-full flex-col gap-5">
                {/*
                  The numeral is the design here, not an ornament: three
                  principles that build on each other need their order to read
                  at a glance. Previously it was an 11px `aria-hidden` label in
                  the corner — the smallest, dimmest element in a card whose
                  entire point is ordered argument.

                  Still aria-hidden, because <ol> already conveys the order to
                  assistive tech and reading "01" aloud before every heading is
                  noise.
                */}
                <span
                  aria-hidden="true"
                  className="font-mono text-[length:var(--text-numeral)] leading-[var(--text-numeral--line-height)] tabular-nums tracking-[var(--text-numeral--letter-spacing)] text-[color:var(--color-text-quaternary)]"
                >
                  {String(i + 1).padStart(2, "0")}
                </span>

                <h3 className="text-[length:var(--text-h3)] leading-[var(--text-h3--line-height)] font-medium tracking-[var(--text-h3--letter-spacing)] text-[color:var(--color-text-primary)]">
                  {block.heading}
                </h3>

                <div className="flex-1 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {block.body}
                </div>

                {/* Every sourceRef is preserved: they resolve to real symbols
                    and are the most verifiable claim on the site. */}
                {block.sourceRef ? (
                  <code className="mt-auto border-t border-[color:var(--color-border)] pt-4 font-mono text-[length:var(--text-label)] break-all text-[color:var(--color-text-quaternary)]">
                    {block.sourceRef}
                  </code>
                ) : null}
              </Surface>
            </Reveal>
          </li>
        ))}
      </ol>

      {/* Gathers the three principles back into one line, which then continues
          out through the transition band below and into `#dashboard`. */}
      <RouteSpine variant="gather" lanes={3} size="md" className="mt-8" />
    </Section>
  );
}
