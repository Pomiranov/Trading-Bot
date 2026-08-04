"use client";

import { useEffect, useRef, useState } from "react";
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

export function SignalCard() {
  const t = useTranslations("telegram");
  const [state, setState] = useState<CardState>("idle");
  const reduce = useReducedMotion();

  // `floor`, not `round`: rounding paints an 8th bar for a 0.75, so the gauge
  // would read 0.80 beside the printed 0.75. Truncating can only understate,
  // and a confidence gauge must never overstate the number sitting next to it.
  const filled = Math.floor(EXAMPLE.confidence * BARS);

  const resolved =
    state === "accepted"
      ? { label: t("cardAccepted"), detail: t("cardAcceptedDetail"), tone: "success" as const }
      : state === "skipped"
        ? { label: t("cardSkipped"), detail: t("cardSkippedDetail"), tone: "muted" as const }
        : null;

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
    <div className="flex flex-col gap-4">
      {/* `padding="sm"`, not a hand-rolled `p-6` — the primitive's census note
          exists precisely because every card picking its own padding is drift.
          `sm` (p-5) is the nearest step for a compact nested card. */}
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
          ── The footer's height is reserved, so the demo cannot reflow the page ──

          The idle→resolved swap trades two buttons for a chip, a caption and a
          reset control, so each press used to change the card's height and shove
          the whole Telegram panel around mid-interaction, under the visitor's
          own pointer.

          This used to be a hand-measured `min-h` pixel ladder — six breakpoints
          of RU-measured constants that were wrong the moment any copy or
          translation changed length, and that left a visible strip of empty
          card under the idle buttons at most widths. The reserve is
          self-measuring instead: both resolved variants render permanently as
          *sizing ghosts* — plain, `invisible`, `aria-hidden`, `inert` — stacked
          into the same grid cell as the live layer, so the cell is always
          exactly as tall as the tallest state at the current width and locale,
          and the constants are gone. The live layer keeps the original
          mount/unmount swap untouched, because the focus hand-off effect above
          depends on it and is measured to work. The ghosts never change state,
          never animate and never take focus, so they can race nothing. The
          anti-CLS property is preserved by construction.
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

          {(["accepted", "skipped"] as const).map((s) => {
            const variant =
              s === "accepted"
                ? { label: t("cardAccepted"), detail: t("cardAcceptedDetail"), tone: "success" as const }
                : { label: t("cardSkipped"), detail: t("cardSkippedDetail"), tone: "muted" as const };
            return (
              <div
                key={s}
                aria-hidden="true"
                inert
                className="invisible col-start-1 row-start-1 flex flex-col gap-3"
              >
                <div className="flex flex-col gap-2">
                  <StatusChip tone={variant.tone} label={variant.label} />
                  <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
                    {variant.detail}
                  </p>
                </div>
                <Button variant="ghost" size="sm" className="min-h-11 self-start" tabIndex={-1}>
                  {t("cardReset")}
                </Button>
              </div>
            );
          })}

          <div className="col-start-1 row-start-1">
          {resolved ? (
            <motion.div
              // Same rule as elsewhere: never branch `initial` on the
              // reduced-motion preference, only the duration.
              data-reveal=""
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduce ? { duration: 0 } : { duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="flex flex-col gap-3"
            >
              <div className="flex flex-col gap-2">
                <StatusChip tone={resolved.tone} label={resolved.label} />
                <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
                  {resolved.detail}
                </p>
              </div>

              {/* `min-h-11` for the same reason the two controls below carry it:
                  at `size="sm"`'s own h-9 this sat at 36px, and it was the last
                  control on the page under the 44px touch floor. */}
              <Button
                ref={resetRef}
                variant="ghost"
                size="sm"
                className="min-h-11 self-start"
                onClick={() => setState("idle")}
              >
                {t("cardReset")}
              </Button>
            </motion.div>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-start">
            {/*
              Two fixes here, both for 390px.

              `h-auto min-h-9 py-2` alongside `whitespace-normal`: `size="sm"` is
              a fixed `h-9` and the base button style is `whitespace-nowrap`.
              Overriding only the wrapping — which this did — lets the label
              break to two lines inside a box still locked to 36px, so the RU
              "Исполнить в песочнице" rendered spilling out through the top and
              bottom edges of its own button. Either the height follows the
              content or the text must not wrap; for a CTA whose Russian label is
              21 characters, growing is the right one.

              `w-full` below `sm`, `flex-1` above it: sharing a ~265px row with
              the Skip button still forced the label onto three lines, which
              made a 96px-tall button beside a 36px one. Stacked, each takes a
              line or two at full width.

              `min-h-11`, not `min-h-9`: these are the only two controls a
              visitor is invited to press inside the demo card, and at 36px both
              sat under the 44px touch floor. The floor is a minimum, so a label
              that needs two lines still grows past it — which is the same
              reason `h-auto` is here.
            */}
            <Button
              ref={executeRef}
              className="h-auto min-h-11 w-full py-2 whitespace-normal sm:w-auto sm:flex-1"
              size="sm"
              onClick={() => setState("accepted")}
            >
              {t("cardExecute")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-auto min-h-11 w-full sm:w-auto"
              onClick={() => setState("skipped")}
            >
              {t("cardDismiss")}
            </Button>
          </div>
          )}
          </div>
        </div>
      </Surface>

      <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
        {t("cardDemoHint")}
      </p>
    </div>
  );
}
