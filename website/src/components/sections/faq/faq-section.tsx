import { getTranslations } from "next-intl/server";
import { Section } from "@/components/ui/section";
import { SectionHeader } from "@/components/ui/section-header";
import { Surface } from "@/components/ui/surface";
import { Reveal } from "@/components/motion/reveal";

const QUESTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

/**
 * Native <details>/<summary>, contained in one card.
 *
 * ── Do not replace this with a JS accordion ──
 *
 * It was one once: the only client component among the sections, and it set
 * `outline: none` on the trigger with no replacement, making it simultaneously
 * the heaviest and the least accessible block on the page. Native disclosure
 * gives keyboard support, screen-reader semantics and find-in-page for free,
 * ships zero JavaScript, and cannot hydration-mismatch.
 *
 * The height animation this used to trade away is back, and it cost none of
 * that: `::details-content` is a stylable UA box, so the expansion is pure CSS
 * on unmodified markup. See `.faq-row` in globals.css for the mechanism and for
 * what a browser without it falls back to.
 *
 * ── aria-expanded / aria-controls are deliberately absent ──
 *
 * Not an oversight. <details> exposes its own expanded state to assistive
 * technology, and the summary is its own control — the ARIA disclosure pattern
 * exists to *simulate* what this element already is. Hand-written attributes
 * here would be strictly worse: with no JavaScript to keep them in sync,
 * `aria-expanded="false"` would go on lying the moment a reader opened a row,
 * and a static value that contradicts the element's real state is a defect a
 * screen-reader user actually hits. If a future change moves this to JS-driven
 * open state, they come back at the same time as the code that updates them.
 *
 * ── What changed ──
 *
 * The rows sat as bare hairline-separated text in a 68ch column inside a 1280
 * field — the narrowest block on the page by a wide margin, floating with
 * nothing around it, so it read as a different site. They are now inside one
 * `SurfaceCard`.
 *
 * The disclosure indicator was a bare `+` rotating 45°, then a chevron rotating
 * 180°. It is now a chevron that turns into a cold-lit diamond on open, and
 * each row has a hover and focus background so the target is visible before it
 * is hit.
 */
export async function FaqSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "faq" });

  return (
    /*
      No `divider`. This section is entered out of `#pricing`'s transition band,
      and a hairline across the top of it directly under that blend gives the
      join two competing horizontal edges. The tone change is the separator.
    */
    /*
      `width="content"`, not `prose`.

      The card fixed the "bare text floating in a 1280 field" problem noted below,
      but it kept the 68ch column — and `prose` centres it. Measured at 1440 that
      put the FAQ's left edge at x=358 while every other section on the page
      starts at x=116, so the block still stepped out of the grid at the one point
      where a reader is scanning for a specific line. A centred island is exactly
      as much of a different site as an uncontained one; the containment just made
      it look deliberate.

      The reading measure is preserved where it is actually needed — on the
      answers, which are the only long-form text here — rather than by narrowing
      the whole component. Questions are one line each and want the full row.
    */
    <Section id="faq" rhythm="default">
      {/*
        No eyebrow.

        Every other section has one because its heading is a *claim* and the
        eyebrow names the topic. Here the heading already is the topic, so the
        eyebrow was the same word twice, at two sizes, 12px apart — "ВОПРОСЫ"
        over "Вопросы". Removed on owner direction; the heading takes the
        eyebrow's uppercase treatment so nothing is lost from the register.

        Uppercased in CSS rather than in the message files: the source strings
        stay natural-cased for both locales, so RU/EN parity is unaffected and a
        translator never has to remember the convention.
      */}
      <SectionHeader
        id="faq"
        heading={<span className="uppercase">{t("heading")}</span>}
      />

      <Reveal lift={false} className="mt-[var(--space-header-to-body)]">
        <Surface interactive={false} className="overflow-hidden">
          {QUESTIONS.map((q) => (
            <details
              key={q}
              // `faq-row` carries the disclosure motion; `group` is what the
              // marker's open state below reads. Both on the <details> itself,
              // so `[open]` and `group-open:` resolve against the same element.
              className="faq-row group border-t border-[color:var(--color-border)] first:border-t-0"
            >
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 px-6 py-5 text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] text-[color:var(--color-text-primary)] transition-colors duration-[var(--duration-micro)] marker:hidden hover:bg-[color:var(--color-highlight-bg)] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[color:var(--color-accent)] [&::-webkit-details-marker]:hidden">
                {t(`q${q}`)}

                {/*
                  Closed: a chevron. Open: a cold-lit diamond.

                  Two shapes stacked in one 16×16 box and cross-faded through a
                  rotation, rather than one path morphing — SMIL path morphing is
                  not reliably interpolable between a 3-point polyline and a
                  4-point closed rhombus, and the CSS `d` property that would do
                  it is Chromium-only.

                  Stacked with `grid` + `[grid-area:1/1]`: both children occupy
                  the same cell, so the box is exactly one glyph tall in both
                  states and the row cannot reflow when a question is opened. The
                  transition is `opacity` + `transform` only, both compositor
                  properties.

                  The open state is not carried by colour: the shape itself
                  changes, and <details> exposes `open` to assistive tech
                  regardless. The cyan is a drop-shadow on decorative geometry,
                  which is the permitted use — see the doctrine in
                  tokens/color.css and `.faq-marker-open` in globals.css.
                */}
                <span
                  aria-hidden="true"
                  className="mt-1.5 grid size-4 shrink-0 place-items-center"
                >
                  <svg
                    viewBox="0 0 16 16"
                    className="size-4 [grid-area:1/1] text-[color:var(--color-text-tertiary)] transition-[opacity,transform] duration-[var(--duration-base)] ease-[var(--ease-out-expo)] group-open:scale-75 group-open:rotate-180 group-open:opacity-0"
                  >
                    <path
                      d="M3 6 L8 11 L13 6"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>

                  <svg
                    viewBox="0 0 16 16"
                    className="faq-marker-open size-4 scale-50 rotate-45 opacity-0 [grid-area:1/1] transition-[opacity,transform] duration-[var(--duration-base)] ease-[var(--ease-out-expo)] group-open:scale-100 group-open:rotate-0 group-open:opacity-100"
                  >
                    <path
                      d="M8 2.5 L13.5 8 L8 13.5 L2.5 8 Z"
                      fill="none"
                      stroke="var(--color-signal)"
                      strokeWidth="1.5"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              </summary>
              {/*
                The answer needs its own element between `::details-content` and
                the text: the content box is the grid whose row collapses, and
                this is the item inside it that gets crushed. Putting the
                padding on the <p> rather than on the row is what keeps the
                closed state at exactly zero height — padding on the animated
                box itself would leave 48px of empty card showing under every
                closed question.
              */}
              <div className="faq-answer">
                {/* The measure the section used to get from `width="prose"`, now
                    applied to the only text that needs it. */}
                <p className="max-w-[var(--space-prose-max)] px-6 pb-6 text-[length:var(--text-body)] leading-[var(--text-body--line-height)] text-[color:var(--color-text-secondary)]">
                  {t(`a${q}`)}
                </p>
              </div>
            </details>
          ))}
        </Surface>
      </Reveal>
    </Section>
  );
}
