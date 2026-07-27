"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useTranslations } from "next-intl";
import { Surface } from "@/components/ui/surface";
import { MonoLabel } from "@/components/ui/mono-label";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/ui/status-pill";

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

  const filled = Math.round(EXAMPLE.confidence * BARS);

  const resolved =
    state === "accepted"
      ? { label: t("cardAccepted"), detail: t("cardAcceptedDetail"), tone: "success" as const }
      : state === "skipped"
        ? { label: t("cardSkipped"), detail: t("cardSkippedDetail"), tone: "muted" as const }
        : null;

  return (
    <div className="flex flex-col gap-4">
      <Surface variant="raised" className="flex flex-col gap-5 p-6">
        <MonoLabel>{t("cardTitle")}</MonoLabel>

        <p className="font-mono text-[length:var(--text-h3)] font-medium text-[color:var(--color-text-primary)]">
          {EXAMPLE.ticker} · {EXAMPLE.side}
        </p>

        <dl className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <dt className="min-w-[9ch] font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
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

          <div className="flex items-center gap-3">
            <dt className="min-w-[9ch] font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
              {t("cardRisk")}
            </dt>
            <dd className="text-[length:var(--text-caption)] text-[color:var(--color-success)]">
              {t("cardRiskValue")}
            </dd>
          </div>

          <div className="flex items-center gap-3">
            <dt className="min-w-[9ch] font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase">
              {t("cardStrategy")}
            </dt>
            <dd className="font-mono text-[length:var(--text-caption)] text-[color:var(--color-text-tertiary)]">
              {EXAMPLE.strategy}
            </dd>
          </div>
        </dl>

        <div className="flex flex-col gap-3 border-t border-[color:var(--color-border)] pt-4">
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
              {/* aria-live so a screen reader hears the outcome of the press
                  without the focus having to move anywhere. */}
              <div role="status" aria-live="polite" className="flex flex-col gap-2">
                <StatusPill tone={resolved.tone} label={resolved.label} />
                <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
                  {resolved.detail}
                </p>
              </div>

              <Button
                variant="ghost"
                size="sm"
                className="self-start"
                onClick={() => setState("idle")}
              >
                {t("cardReset")}
              </Button>
            </motion.div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button
                className="flex-1 whitespace-normal"
                size="sm"
                onClick={() => setState("accepted")}
              >
                {t("cardExecute")}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setState("skipped")}>
                {t("cardDismiss")}
              </Button>
            </div>
          )}
        </div>
      </Surface>

      <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
        {t("cardDemoHint")}
      </p>
    </div>
  );
}
