"use client";

import { type ReactNode, type Ref, useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useTranslations } from "next-intl";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";

/**
 * The Telegram signal card, with its two buttons wired as a local demo.
 *
 * ── Scope of the interaction ──
 *
 * Both buttons mutate one piece of React state and nothing else. There is no
 * fetch, no server action, no analytics side effect and no broker call, and the
 * resulting copy says so explicitly in both languages: "Демо-режим: ничего не
 * ушло брокеру". That wording is load-bearing — "Заявка отправлена в песочницу"
 * on its own would imply a sandbox order really was placed.
 *
 * The card mirrors bot/tg/handlers/signals.py:73-143, which builds a card with a
 * confidence bar. The real bot has one button ("Исполнить в Paper", :58) and no
 * Reject; the Skip button here is a demo affordance for the landing page, which
 * is why the reset control exists — a visitor can undo it and try the other
 * branch, and nothing is lost by doing so.
 *
 * The confidence figure is a plausible example of a *decision attribute*, not a
 * measured result. It is not a win rate and not a return.
 */

const EXAMPLE = {
  ticker: "SBER",
  side: "LONG",
  confidence: 0.71,
  strategy: "osc_range_moex_d1_fwd",
} as const;

const BARS = 10;

type CardState = "idle" | "accepted" | "skipped";

/**
 * The two resolved outcomes, as one table.
 *
 * It exists because the footer's height reserve renders both of them as sizing
 * ghosts (see the long note in the footer): the live layer and the ghosts must
 * read the *same* strings and tones, or the reserve is measuring something other
 * than what will be shown. A shared table makes that true by construction rather
 * than by two call sites agreeing.
 */
const OUTCOMES = {
  accepted: (t: (k: string) => string) => ({
    label: t("cardAccepted"),
    detail: t("cardAcceptedDetail"),
    tone: "success" as const,
  }),
  skipped: (t: (k: string) => string) => ({
    label: t("cardSkipped"),
    detail: t("cardSkippedDetail"),
    tone: "muted" as const,
  }),
} as const;

export function SignalCard() {
  const t = useTranslations("telegram");
  const [state, setState] = useState<CardState>("idle");
  const reduce = useReducedMotion();

  // `floor`, not `round`: rounding paints an 8th bar for a 0.75, so the gauge
  // would read 0.80 beside the printed 0.75. Truncating can only understate,
  // and a confidence gauge must never overstate the number sitting next to it.
  const filled = Math.floor(EXAMPLE.confidence * BARS);

  const resolved = state === "idle" ? null : OUTCOMES[state](t);

  /*
    Focus hand-off between the two footer states.

    Pressing Execute/Skip unmounts the very button the visitor's focus is on,
    and Reset does the same in the other direction — focus fell to <body>, so
    the next Tab restarted from the top of the document. A ref + effect rather
    than `.focus()` inside the click handler, because the counterpart control
    does not exist until after the state change commits.

    `prevState` guards the initial mount: the effect must distinguish "the
    state just changed" from "the card just rendered", or it would yank focus
    to the Execute button (and scroll the page to it) on load.
  */
  const executeRef = useRef<HTMLButtonElement>(null);
  const resetRef = useRef<HTMLButtonElement>(null);
  const prevState = useRef<CardState>(state);

  useEffect(() => {
    if (prevState.current === state) return;
    prevState.current = state;
    if (state === "idle") {
      executeRef.current?.focus();
    } else {
      resetRef.current?.focus();
    }
  }, [state]);

  return (
    // No wrapper any more: the demo-hint paragraph that used to sit beside the
    // card in a `flex-col gap-4` moved into the card's own caption slot (see the
    // footer note below), so the wrapper had one child left and existed only to
    // put a gap under it.
    /* `padding="sm"`, not a hand-rolled `p-6` — the primitive's census note
       exists precisely because every card picking its own padding is drift.
       `sm` (p-5) is the nearest step for a compact nested card. */
    <Surface variant="raised" padding="sm" className="flex flex-col gap-5">
        <MonoLabel>{t("cardTitle")}</MonoLabel>

        <p className="font-mono text-[length:var(--text-h3)] font-medium text-[color:var(--color-text-primary)]">
          {EXAMPLE.ticker} · {EXAMPLE.side}
        </p>

        <dl className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <dt className="min-w-[9ch] shrink-0 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
              {t("cardConfidence")}
            </dt>
            <dd className="flex items-center gap-2">
              {/* The bars fill left-to-right on first reveal, 45ms apart, so
                  the gauge reads as *being measured* rather than as a value
                  that was always there. Only the filled bars animate — the
                  empty track is the scale and must be present from the start,
                  or the figure has nothing to be read against.

                  `whileInView` + `once`, matching the page's single reveal
                  mechanism; `scaleY` is compositor-only so ten of these cost
                  nothing. Under reduced motion the duration collapses to 0 and
                  they simply appear, exactly like `Reveal`. */}
              <span aria-hidden="true" className="flex gap-0.5">
                {Array.from({ length: BARS }, (_, i) => {
                  const isFilled = i < filled;
                  return (
                    <motion.span
                      key={i}
                      className="h-3 w-1 origin-bottom rounded-[1px]"
                      style={{
                        // Monochrome: filled bars are white, the rest are the
                        // interactive border grey. This was the orange bar.
                        backgroundColor: isFilled
                          ? "var(--color-accent)"
                          : "var(--color-border-strong)",
                      }}
                      initial={isFilled ? { scaleY: 0.25, opacity: 0.35 } : false}
                      whileInView={isFilled ? { scaleY: 1, opacity: 1 } : undefined}
                      viewport={{ once: true, amount: 0.6 }}
                      transition={
                        reduce
                          ? { duration: 0 }
                          : { duration: 0.4, delay: i * 0.045, ease: [0.22, 1, 0.36, 1] }
                      }
                    />
                  );
                })}
              </span>
              <span className="font-mono text-[length:var(--text-caption)] tabular-nums text-[color:var(--color-text-primary)]">
                {EXAMPLE.confidence.toFixed(2)}
              </span>
            </dd>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <dt className="min-w-[9ch] shrink-0 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
              {t("cardRisk")}
            </dt>
            <dd className="text-[length:var(--text-caption)] text-[color:var(--color-success)]">
              {t("cardRiskValue")}
            </dd>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <dt className="min-w-[9ch] shrink-0 font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
              {t("cardStrategy")}
            </dt>
            {/*
              `min-w-0` + `break-all`, because this is the one value on the card
              that has no spaces in it.

              At 390px the RU label "СТРАТЕГИЯ" plus `osc_range_moex_d1_fwd`
              exceeds the card's inner width. The row was `flex items-center`
              with a shrinkable <dt>, so the label was squeezed to its 9ch
              minimum, its letter-spaced uppercase text overflowed its own box
              and collided with the value — rendering as
              "СТРАТЕГИЯosc_range_moex_d1_fwd" — while the value itself ran past
              the card's right edge. Underscores are not break opportunities, so
              nothing wrapped on its own.

              `shrink-0` on the <dt> and `flex-wrap` on the row fix the collision;
              this fixes the overflow. `break-all` rather than `break-words`
              because a strategy id has no word boundaries to prefer.
            */}
            <dd className="min-w-0 font-mono text-[length:var(--text-caption)] break-all text-[color:var(--color-text-tertiary)]">
              {EXAMPLE.strategy}
            </dd>
          </div>
        </dl>

        {/*
          ── The footer, and why the reserve got cheap instead of going away ──

          The idle→resolved swap trades two buttons for a chip and a reset
          control, so without a reserve each press changes the card's height and
          shoves the whole Telegram panel around mid-interaction, under the
          visitor's own pointer. That anti-CLS requirement stands, and the
          mechanism that delivers it — both resolved variants rendered
          permanently as `invisible` sizing ghosts stacked into one grid cell, so
          the cell measures itself against the tallest state at the current width
          and locale — is still the right one. It has no constants in it and
          cannot go stale.

          What was wrong was the *shape* the reserve was measuring. The resolved
          state stacked four things vertically — chip, caption, gap, reset button
          — against an idle row of two buttons. Measured at 1440: 124px against
          44px. So the default state, the one in every screenshot, carried **80px
          of empty card** under its buttons, and ~70px at 390. The owner's review
          opened on that void, and it was not a layout bug: it was the reserve,
          rendered.

          So the two states were made the same shape instead:

            row 1 — controls.  idle: Execute + Skip.  resolved: status chip + Reset.
            row 2 — a caption. idle: the demo disclaimer. resolved: the outcome.

          Both states now fill both rows, and the reserve costs what the residual
          difference actually is. Re-measured across four widths in RU: 0px of idle
          slack at 320 (where the idle state is the taller of the two), 2px at 390
          and 430, 0px at 1440. The mechanism is unchanged; the geometry it was
          measuring is what was expensive.

          The demo disclaimer moved up into row 2 from below the card, where it
          used to sit as a separate paragraph. Two things follow, both wanted: the
          honesty note ("Кнопки — демонстрация интерфейса") now sits inside the
          card, immediately under the controls it is about, rather than outside the
          object it disclaims; and the Telegram block loses a stacked paragraph,
          which is part of why the section came down 72px.

          The live layer keeps the original mount/unmount swap for the controls,
          because the focus hand-off effect above depends on it and is measured to
          work. The ghosts never change state, never animate and never take focus,
          so they can race nothing.
        */}
        <div className="grid border-t border-[color:var(--color-border)] pt-4">
          {/* The live region is mounted with the card, not with the outcome.
              A `role="status"` element only announces *mutations inside a
              region the accessibility tree already knows about* — the previous
              version mounted region and content together, in one insertion,
              which real screen readers skip more often than not (WCAG 4.1.3).
              So an sr-only region sits here from first render and only its
              text swaps; it is `sr-only`, and therefore absolutely positioned,
              so it cannot open a grid track of its own. The visible chip below
              repeats the same words and animates freely, because it is no
              longer the live element. */}
          <div role="status" aria-live="polite" className="sr-only">
            {resolved ? `${resolved.label}. ${resolved.detail}` : null}
          </div>

          {/* ── A ghost per state, including the idle one ──
              Two ghosts was the obvious reading and it is measurably wrong. The
              grid cell resolves to the tallest of *everything in it*, and the idle
              layer is the live one — so with ghosts for the two outcomes only, the
              cell was max(live, accepted, skipped), which is constant while the
              live layer is the shortest and *collapses* the moment it is the
              tallest. Measured at 320 in RU, where the idle state's two stacked
              buttons and four-line disclaimer make it the tallest by 9px: pressing
              Execute shrank the card by exactly that and pulled the rest of the
              page up with it.

              Three ghosts makes the cell max(idle, accepted, skipped) in every
              state, i.e. genuinely invariant, and it costs nothing that two did
              not already cost. */}
          {(["idle", "accepted", "skipped"] as const).map((s) => (
            <div
              key={s}
              aria-hidden="true"
              inert
              className="invisible col-start-1 row-start-1 flex flex-col gap-3"
            >
              <ControlRow>
                {s === "idle" ? (
                  <IdleControls executeLabel={t("cardExecute")} dismissLabel={t("cardDismiss")} ghost />
                ) : (
                  <div className={OUTCOME_ROW}>
                    <Outcome
                      label={OUTCOMES[s](t).label}
                      tone={OUTCOMES[s](t).tone}
                      resetLabel={t("cardReset")}
                      ghost
                    />
                  </div>
                )}
              </ControlRow>
              <Caption>{s === "idle" ? t("cardDemoHint") : OUTCOMES[s](t).detail}</Caption>
            </div>
          ))}

          <div className="col-start-1 row-start-1 flex flex-col gap-3">
            <ControlRow>
              {resolved ? (
                // The animated box *is* the outcome row: `display: contents`
                // would be the tidier composition but generates no box, so
                // `opacity` and `y` would both be silently dropped.
                <motion.div
                  // Same rule as elsewhere: never branch `initial` on the
                  // reduced-motion preference, only the duration.
                  data-reveal=""
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={reduce ? { duration: 0 } : { duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                  className={OUTCOME_ROW}
                >
                  <Outcome
                    label={resolved.label}
                    tone={resolved.tone}
                    resetLabel={t("cardReset")}
                    resetRef={resetRef}
                    onReset={() => setState("idle")}
                  />
                </motion.div>
              ) : (
                <IdleControls
                  executeLabel={t("cardExecute")}
                  dismissLabel={t("cardDismiss")}
                  executeRef={executeRef}
                  onExecute={() => setState("accepted")}
                  onDismiss={() => setState("skipped")}
                />
              )}
            </ControlRow>

            <Caption>{resolved ? resolved.detail : t("cardDemoHint")}</Caption>
          </div>
        </div>
    </Surface>
  );
}

/**
 * Row 1 of the footer. `min-h-11` on the row rather than only on the controls:
 * the resolved state swaps a 44px button pair for a chip beside a `ghost` reset,
 * and without a floor here the row loses a few pixels on the swap even though
 * both of its children carry their own.
 */
function ControlRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-11 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      {children}
    </div>
  );
}

/**
 * Row 2 of the footer. Both states fill it, so its height difference between them
 * is only ever a line count — which the ghosts above measure. One component so a
 * ghost caption and a live caption cannot drift into different type, which would
 * make the reserve wrong in a way nothing would catch.
 */
function Caption({ children }: { children: ReactNode }) {
  return (
    <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
      {children}
    </p>
  );
}

/**
 * The class list for the resolved row's own box, applied by the caller so the live
 * layer can put it on a `motion.div` and the ghosts on a plain `div` while both
 * still lay out identically. A shared constant rather than a duplicated string:
 * if the ghost's box differs from the live one, the reserve is measuring the wrong
 * geometry and nothing catches it.
 */
const OUTCOME_ROW = "flex flex-wrap items-center gap-x-4 gap-y-2";

/**
 * The two controls a visitor is invited to press. Shared by the live layer and the
 * idle ghost, for the same reason `Outcome` and `Caption` are shared.
 *
 * ── Two fixes live in these class lists, both for 390px ──
 *
 * `h-auto min-h-11 py-2` alongside `whitespace-normal`: `size="sm"` is a fixed
 * `h-9` and the base button style is `whitespace-nowrap`. Overriding only the
 * wrapping lets the label break to two lines inside a box still locked to 36px, so
 * the RU "Исполнить в песочнице" rendered spilling out through the top and bottom
 * edges of its own button. Either the height follows the content or the text must
 * not wrap; for a CTA whose Russian label is 21 characters, growing is the right
 * one.
 *
 * `w-full` below `sm`, `flex-1` above it: sharing a ~265px row with the Skip
 * button still forced the label onto three lines, which made a 96px-tall button
 * beside a 36px one. Stacked, each takes a line or two at full width.
 *
 * `min-h-11`, not `min-h-9`: at 36px both sat under the 44px touch floor. The
 * floor is a minimum, so a label that needs two lines still grows past it — which
 * is the same reason `h-auto` is here.
 */
function IdleControls({
  executeLabel,
  dismissLabel,
  executeRef,
  onExecute,
  onDismiss,
  ghost,
}: {
  executeLabel: string;
  dismissLabel: string;
  executeRef?: Ref<HTMLButtonElement>;
  onExecute?: () => void;
  onDismiss?: () => void;
  ghost?: boolean;
}) {
  return (
    <>
      <Button
        ref={executeRef}
        className="h-auto min-h-11 w-full py-2 whitespace-normal sm:w-auto sm:flex-1"
        size="sm"
        onClick={onExecute}
        tabIndex={ghost ? -1 : undefined}
      >
        {executeLabel}
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-auto min-h-11 w-full sm:w-auto"
        onClick={onDismiss}
        tabIndex={ghost ? -1 : undefined}
      >
        {dismissLabel}
      </Button>
    </>
  );
}

/**
 * The resolved controls: a status chip and the reset. Shared by the live layer and
 * both ghosts for the same reason `Caption` is — a ghost that renders different
 * markup from the thing it is measuring is a reserve that is quietly wrong.
 *
 * `min-h-11` on the reset for the reason the two idle controls carry it: at
 * `size="sm"`'s own h-9 it sat at 36px, and it was the last control on the page
 * under the 44px touch floor.
 */
function Outcome({
  label,
  tone,
  resetLabel,
  resetRef,
  onReset,
  ghost,
}: {
  label: string;
  tone: "success" | "muted";
  resetLabel: string;
  resetRef?: Ref<HTMLButtonElement>;
  onReset?: () => void;
  ghost?: boolean;
}) {
  return (
    <>
      <StatusChip tone={tone} label={label} />
      <Button
        ref={resetRef}
        variant="ghost"
        size="sm"
        className="min-h-11"
        onClick={onReset}
        tabIndex={ghost ? -1 : undefined}
      >
        {resetLabel}
      </Button>
    </>
  );
}
