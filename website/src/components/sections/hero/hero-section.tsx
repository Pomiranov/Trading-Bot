import { getTranslations } from "next-intl/server";
import { ButtonLink } from "@/components/ui/button-link";
import { GridBackplate } from "@/components/ui/grid-backplate";
import { SignalField } from "@/components/ui/signal-field";
import { SignalDot } from "@/components/ui/signal-dot";
import { QAperture } from "./q-aperture";
import { PointerTilt } from "./pointer-tilt";

/**
 * The argument in one screen, inside a contained dark panel.
 *
 * ── Composition ──
 *
 * The reference does not run the hero full-bleed: it is a rounded panel inset
 * from the page edges, sitting on the page as an object. That containment is
 * what makes the rest of the page read as a document rather than a poster, and
 * it rhymes with the closing CTA panel so the page is bookended.
 *
 * Inside, and this is now all of it: a status pill, a two-line headline, one
 * subline and one call to action on the left; the Q-aperture on the right.
 *
 * ── What the polish pass removed, and why ──
 *
 * Four things, all owner direction, all the same note in different places: the
 * hero was arguing five times and should argue once.
 *
 *   • the three-clause eyebrow ("Закрытое тестирование · MOEX · песочница по
 *     умолчанию") — a metadata line where a status marker belongs. MOEX and
 *     sandbox-by-default are both stated at full weight in `#safety` and in the
 *     subline; what the eyebrow is actually for is the programme's state, so
 *     that is all it says now, as a pill rather than as running text.
 *   • the system-envelope row across the panel's foot ("MOEX + Bybit ·
 *     Пределы риска до заявки · Ручное подтверждение доступно") — three mono
 *     items that read as furniture rather than as a value proposition. Each is
 *     load-bearing somewhere else: risk limits before the order and manual
 *     confirmation in `#safety` and in the belief-gate node of `#how-it-works`,
 *     the venue in the subline directly above.
 *   • the secondary "Посмотреть как работает →" arrow link, which is now the
 *     primary button's own label.
 *   • the white pool behind the aperture. `.section-glow` was pinned at
 *     74%/34% while the aperture's own cold pool sits at its centre, so the
 *     panel had two unrelated light sources overlapping — a grey smudge up and
 *     left of the instrument. One light, and it belongs to the object making
 *     it.
 *
 * Anything added back here has to clear the same bar the removed proof strip
 * did: no results and no figures of any kind, and nothing whose only home is
 * this panel.
 *
 * ── Honesty ──
 *
 * Nothing here is a result, and nothing here is a figure at all any more. The
 * aperture is orbital geometry: no chart, no plotted series, no counter, no
 * percentage. No win rate, profit factor, sample size, Sharpe, equity curve or
 * return figure appears here or anywhere else on the site, under any caption.
 *
 * ── LCP ──
 *
 * `qf-hero-enter` is transform-only and must stay that way. An entrance that
 * starts at `opacity: 0` with fill-mode `both` disqualifies its whole subtree
 * as an LCP candidate for the duration of the delay, which previously cost the
 * hero ~150ms for no visual gain. The <h1> is the LCP element and no ancestor
 * of it may start transparent.
 */
export async function HeroSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "hero" });

  return (
    <section
      id="hero"
      aria-labelledby="hero-heading"
      // No min-h-dvh below md. At 390px the old hero measured 1 479px — 1.75
      // viewports before the CTA came into view — and on iOS a dvh re-measures
      // when the toolbar collapses, so it also jumped on first scroll. Desktop
      // keeps the full-height composition.
      className="relative isolate px-[var(--space-page-x)] pt-24 pb-12 md:min-h-dvh md:items-center md:pt-32 md:pb-16 lg:flex"
    >
      <div className="relative mx-auto w-full max-w-[var(--space-content-max)]">
        {/* ── The panel ──
            `SignalField` is a ~60-line client shell that writes the pointer's
            position to three custom properties; everything inside it, including
            the headline and the aperture, stays server-rendered. It wraps the
            panel rather than the section so the light is bounded by the object it
            belongs to — a field the width of the whole section would light grid
            lines the reader is nowhere near. */}
        <SignalField className="relative isolate overflow-hidden rounded-[var(--radius-2xl)] border border-[color:var(--color-border)] bg-[color:var(--color-bg-elevated)] shadow-[var(--shadow-panel)]">
          {/* `panel`, for the same reason `#access` uses it: this panel is
              ~1208×750 at 1440px, and the default `pool` ellipse is tuned for a
              near-square host. On this aspect ratio it stopped every vertical
              line well short of the panel's foot. See EDGE_FADE in
              ui/grid-backplate.tsx. */}
          <GridBackplate signal mask="panel" />

          {/*
            ── Removed: the panel's own white pool ──

            A `.section-glow` at `[--glow-x:74%] [--glow-y:34%]`, added to keep
            the aperture "in the light". The aperture already carries its own
            cold pool at its exact centre (`--glow-aperture`), so the panel had
            two overlapping light sources with different colours and different
            centres — which is not depth, it is a smudge, and it sat up and to
            the left of the instrument where nothing needed lighting.

            One light source, owned by the object that emits it. If the panel
            ever needs more depth than the grid and the aperture give it, the
            fix is the aperture's own pool, not a second gradient over the top.
          */}

          {/* One row now that the system-envelope strip is gone, so `gap-y` no
              longer has a second row to separate — the column gap is the only
              one doing work at `lg`.

              ── The columns swapped weight, and the headline is why ──

              It was `[1fr, 1.05fr]` with a 56px gap, which gave the text column
              504px at 1440. "Больше контроля." sets at 554px there (66px type,
              -0.03em), so the second line of a two-line headline wrapped — and
              a headline that wraps mid-phrase is a headline nobody chose.

              `[1.2fr, 1fr]` with a 48px gap takes the text column to ~569px,
              which clears it with room, and costs the aperture 45px of its 520.
              That is the right trade: the instrument is decoration and reads at
              any size above ~400px, the headline is the argument.

              At exactly `lg` (1024px) the text column is ~382px against the
              393px the line needs there, so the headline takes three lines in
              that one narrow band before the `xl` widths resolve it. Left as
              is: it is a clean break between two words, not a defect, and
              buying it back would cost the aperture another 40px at every
              width above it. */}
          <div className="relative grid items-center gap-10 px-5 pt-10 pb-10 sm:px-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-x-12 lg:px-14 lg:py-16">
            {/* ── Left: the argument ── */}
            <div className="flex min-w-0 flex-col items-start gap-7">
              {/*
                ── The status pill ──

                Two words and a lit dot, inside a hairline capsule.

                It replaces a three-clause mono line that ran 47 characters
                across the top of the hero and read as a build stamp. The pill
                states one thing — the programme is in closed testing — which is
                the part that buys trust; the venue and sandbox-by-default are
                stated where a reader is actually deciding about them.

                Not `StatusChip`: that component is driven by `StatusTone`,
                which is the *strategy/broker* status vocabulary, and borrowing
                a tone for page furniture is how a vocabulary stops meaning
                anything. This is a bare capsule with the page's own border and
                fill tokens.

                The dot is `SignalDot` — the same cold beacon every
                "closed testing" badge on the site carries, breathing on a 3.6s
                cycle. Deliberately *not* `.status-dot-live`'s expanding sonar
                ring, which is reserved for a genuine live state or a labelled
                demo of one: a programme marker that pings like telemetry is a
                claim about a running system. See ui/signal-dot.tsx.
              */}
              <span className="inline-flex items-center gap-2.5 rounded-[var(--radius-full)] border border-[color:var(--color-border)] bg-[color:var(--color-fill-subtle)] py-1.5 pr-3.5 pl-3 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-secondary)] uppercase">
                <SignalDot />
                {t("eyebrow")}
              </span>

              <h1
                id="hero-heading"
                className="text-[length:var(--text-hero)] leading-[var(--text-hero--line-height)] font-medium tracking-[var(--text-hero--letter-spacing)] text-balance text-[color:var(--color-text-primary)]"
              >
                {t("headline1")}
                <br />
                {t("headline2")}
              </h1>

              <p className="max-w-[52ch] text-[length:var(--text-lead)] leading-[var(--text-lead--line-height)] tracking-[var(--text-lead--letter-spacing)] text-[color:var(--color-text-secondary)]">
                {t("subline")}
              </p>

              {/*
                ── One call to action ──

                It points at `#how-it-works`, not at `#access`. Owner direction,
                and it is the right ask for this screen: a first-time reader has
                just been told the product is quieter and more controllable than
                what they know, and the honest next step is to show them the
                mechanism rather than to ask for their email in the same breath.

                The route to `#access` is not lost — the header CTA carries it at
                every scroll position, all three pricing tiers end in it, and
                `#access` closes the page. Nothing that used to be reachable from
                the hero has become unreachable.

                The secondary arrow link that used to sit beside this button said
                exactly this button's new label, so it went with the change: one
                screen, one ask.

                The two-label `sm:hidden` / `hidden sm:inline` pair went with it
                too, and this is why it can: the old label ("Получить доступ к
                песочнице") needed 246px inside a 208px text box at 390px, which
                is what the split was working around. "Посмотреть как работает"
                measures ~187px in the same box, so one label fits at every width
                and there is no second wording to keep in step.
              */}
              <ButtonLink
                href="#how-it-works"
                size="lg"
                magnetic
                // `wrapperClassName` is what makes the `w-full` below real —
                // see the note on that prop in ui/button-link.tsx.
                wrapperClassName="block w-full sm:inline-block sm:w-auto"
                // `px-6` below `sm`, against `size="lg"`'s own `px-8`. Measured
                // at 390px: the button is 272px wide and the RU label sets at
                // ~209px, which clears 64px of padding by 1px and therefore
                // does not — so the page's primary control opened on a
                // two-line, letter-spaced label. 48px of padding gives it 15px
                // of room instead of −1. Desktop keeps the full `lg` padding.
                className="h-auto min-h-12 w-full justify-center px-6 py-3 text-center whitespace-normal sm:w-auto sm:px-8"
                analytics={{ target: "how_it_works", location: "hero" }}
              >
                {t("ctaPrimary")}
              </ButtonLink>
            </div>

            {/* ── Right: the instrument ──
                PointerTilt is a thin client shell; QAperture is passed through
                as children and stays server-rendered.

                A plain block, NOT a flex row. `.hero-tilt` is a bare <div>, so
                as a flex item it sizes to its content — and QAperture is
                `w-full` inside it, which makes the width self-referential and
                collapses the instrument to ~300px at every breakpoint.
                Block-level, the wrapper fills the column and QAperture's own
                `mx-auto` + max-width do the centring. */}
            <div className="min-w-0">
              <PointerTilt>
                <QAperture />
              </PointerTilt>
            </div>
          </div>

          {/*
            ── Removed: the proof strip and the schematic caption ──

            The panel's foot used to carry a recessed bar holding five proof
            items ("Песочница · Telegram · Dashboard · MOEX + Bybit · Пределы
            риска") and the three configured limits as a <dl>, with a caption
            below the panel restating that the visual contains no results.

            All three are gone on owner direction: the hero should make one
            argument, and a five-item meta row plus three numeric readouts plus
            a disclaimer is four.

            ── This does not weaken the honesty guarantee ──

            Nothing removed here was a *result*; they were configured limits and
            a disclaimer about a visual that has no data in it. The load-bearing
            statements survive elsewhere in full:

              • the risk limits are stated in `#safety` and in the belief-gate
                node of `#how-it-works`, both with their labels attached, and
                "risk is checked before the order" is in the subline above
              • "sandbox by default" is in `#safety`, and the sandbox is the
                first pricing tier and the only free one
              • closed testing is the hero's status pill, the footer chip and
                the access form's own copy
              • the aperture is orbits — no chart, no series, no counter — so
                there is nothing left for a "this is not performance" caption to
                disclaim

            The rule stands unchanged: no win rate, profit factor, sample size,
            Sharpe, equity curve or return figure appears anywhere on this site
            under any caption. Removing a caption is not permission to add a
            figure. `hero.proof1-5`, `hero.limit*` and `hero.visualCaption` were
            deleted from both message catalogues.
          */}
        </SignalField>
      </div>
    </section>
  );
}
