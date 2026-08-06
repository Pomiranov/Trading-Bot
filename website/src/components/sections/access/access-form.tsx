"use client";

import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { betaSignupSchema, type BetaSignupInput } from "@/lib/beta/schema";
import { Button } from "@/components/ui/button";
import { Magnetic } from "@/components/ui/magnetic";
import { track } from "@/lib/analytics/events";

interface AccessFormProps {
  emailLabel: string;
  emailPlaceholder: string;
  submitLabel: string;
  submittingLabel: string;
  successMessage: string;
  successDetail: string;
  successUndelivered: string;
  errorMessage: string;
  networkErrorMessage: string;
  consentNote: string;
}

/**
 * Sandbox access request.
 *
 * The success state is driven by `delivered` from the API, not by HTTP 200.
 * When no destination is configured the address is genuinely discarded, and
 * the form says so and points the user elsewhere rather than promising a
 * follow-up that will never come. Wire a real destination by setting
 * BETA_ADAPTER=webhook and BETA_WEBHOOK_URL — see lib/beta/adapter.ts.
 */
export function AccessForm({
  emailLabel,
  emailPlaceholder,
  submitLabel,
  submittingLabel,
  successMessage,
  successDetail,
  successUndelivered,
  errorMessage,
  networkErrorMessage,
  consentNote,
}: AccessFormProps) {
  const [status, setStatus] = useState<"idle" | "sent" | "error">("idle");
  const [delivered, setDelivered] = useState(false);

  /*
    Where focus goes when the form unmounts. Submitting from the keyboard
    leaves focus on the submit button; on success that button ceases to exist,
    focus falls to <body>, and a keyboard or screen-reader user is silently
    returned to the top of the page with no cue that anything happened. The
    effect below moves focus onto the confirmation instead, so the next Tab
    continues from the message the user actually needs to read.
  */
  const confirmationRef = useRef<HTMLDivElement>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<BetaSignupInput>({
    resolver: zodResolver(betaSignupSchema),
    defaultValues: { email: "", company: "" },
  });

  useEffect(() => {
    if (status === "sent") confirmationRef.current?.focus();
  }, [status]);

  async function onSubmit(data: BetaSignupInput) {
    setStatus("idle");
    track({ name: "cta_clicked", props: { target: "sandbox_access", location: "access_form" } });
    try {
      const res = await fetch("/api/beta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("request failed");
      const json: { delivered?: boolean } = await res.json().catch(() => ({}));
      setDelivered(json.delivered === true);
      setStatus("sent");
      track({ name: "beta_submitted", props: { result: "success" } });
      reset();
    } catch {
      setStatus("error");
      track({ name: "beta_submitted", props: { result: "error" } });
    }
  }

  return (
    <>
      {status !== "sent" ? (
        <form
          onSubmit={handleSubmit(onSubmit, () =>
            track({ name: "beta_submitted", props: { result: "invalid" } }),
          )}
          noValidate
          // Was `max-w-[52ch]`, which was the cause of the misaligned button rather
          // than anything in the button itself. 52ch is a *reading* measure; this row
          // is a 288px input plus a button whose Russian label is 27 characters, and
          // the two could not fit, so the button wrapped to two lines and grew past
          // the input's height. The measure now applies only to the prose below.
          className="flex w-full min-w-0 flex-col gap-4"
        >
          <div className="flex flex-col gap-2">
            {/* Visible label — the previous form's only label was sr-only. */}
            <label
              htmlFor="access-email"
              className="font-mono text-[length:var(--text-label)] tracking-[var(--text-label--letter-spacing)] text-[color:var(--color-text-tertiary)] uppercase"
            >
              {emailLabel}
            </label>

            {/*
              A grid, not a flex row, and `items-stretch` rather than `items-start`.

              Flex with `items-start` let the two controls take different heights and
              then aligned their *tops*, so a two-line button hung 18px below the
              input. Stretching in a grid makes both exactly one row tall by
              construction, which is the only arrangement that cannot come apart when
              the label is translated.

              `minmax(0,1fr) auto` gives the input the slack and sizes the button to
              its text, so the label sets the button's width instead of being forced
              to wrap into a fixed one.
            */}
            <div className="grid w-full min-w-0 grid-cols-1 items-stretch gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <input
                id="access-email"
                type="email"
                placeholder={emailPlaceholder}
                autoComplete="email"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? "access-email-error" : undefined}
                /*
                  Hover was the one control in the closing panel that did not
                  acknowledge the pointer: the CTA beside it lifts, the card next to
                  it lifts and glows, and the input — the field a visitor actually
                  has to use — computed identically whether the cursor was on it or
                  not.

                  A barely-raised fill and a soft cold glow.

                  ── Why the border is not part of it ──

                  Two earlier attempts both got this wrong, in opposite directions,
                  and the reason is worth recording because the tokens make it easy
                  to repeat.

                  The first put the signal-line token in a Tailwind arbitrary
                  `border-` value. The `cyan-as-ink` gate in check-design-tokens.mjs
                  rejected it, correctly: an arbitrary colour value is
                  indistinguishable from painting with the hue, and the cold blue is
                  light — `box-shadow`, `radial-gradient` or an SVG stroke, never a
                  colour utility.

                  The second reached for `--color-highlight-border`, the page's
                  standard hover edge. On a card that works, because a card rests on
                  `--color-border` (0.10 alpha) and 0.28 is a step up. This input
                  rests on `--color-border-strong` (0.35) — it is an interactive
                  control, so it already carries the strong edge — and 0.28 is a step
                  *down*. Measured: the border got dimmer on hover, which is a
                  regression dressed as a hover state, and it is invisible enough to
                  survive review.

                  So hover is carried by the two channels that have somewhere to go
                  from here: the fill lifts and a cold glow appears. Focus still
                  wins outright — white accent border plus a real outline, glow
                  dropped — so hover can never be mistaken for focus.

                  ── The fill made the same mistake the border did ──

                  And it survived the review that recorded the border version. The
                  resting fill was a raw 0.04 white while the hover token is 0.03, so
                  the "fill lifts" above was measurably false: hovering the field made
                  it 0.01 *darker*. The glow masked it, which is why it read as
                  working.

                  Both ends are tokens now and they are ordered: the field rests on
                  the subtle fill and hovers to the standard highlight (0.03 → 0.045).
                  Same direction as every card on the page, and one fewer raw alpha
                  for the design-token gate to tolerate. If either token moves, they
                  must keep that order — the whole point of this state is that it goes
                  up.

                  ── Why the font-size is two arbitrary properties, not the token ──

                  iOS Safari zooms the whole page into any focused input whose
                  computed font-size is under 16px, and the caption token is 13px —
                  so every tap on this field cost a zoom-in and a manual pinch back
                  out. The base size is therefore 1rem, and the caption token is
                  restored from the md: breakpoint up, where that zoom behaviour
                  does not exist. It is written as arbitrary font-size *properties*
                  because the type roles have no 16px step and the
                  arbitrary-font-size gate bans pixel-literal text utilities. The
                  family is font-mono in both states; only the size is
                  viewport-dependent.

                  Do not quote a rejected utility literally in a comment here, even
                  to document it: Tailwind scans this file for class candidates and
                  would compile the example into real CSS. That is the failure mode
                  recorded at the top of globals.css, where a placeholder in a lint
                  script's hint string became a font-size and took the dev server to
                  a 500. It would also re-trip the grep gate from the comment alone.
                */
                className="h-12 w-full min-w-0 rounded-[var(--radius-md)] border border-[color:var(--color-border-strong)] bg-[color:var(--color-fill-subtle)] px-4 font-mono [font-size:1rem] text-[color:var(--color-text-primary)] outline-none transition-[border-color,background-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-expo)] placeholder:text-[color:var(--color-text-quaternary)] hover:bg-[color:var(--color-highlight-bg)] hover:shadow-[var(--btn-glow-hover)] focus-visible:border-[color:var(--color-accent)] focus-visible:shadow-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] md:[font-size:var(--text-caption)]"
                {...register("email")}
              />

              {/* Honeypot — real users never see or reach this. */}
              <input
                type="text"
                tabIndex={-1}
                autoComplete="off"
                aria-hidden="true"
                className="sr-only"
                {...register("company")}
              />

              <Magnetic className="w-full sm:w-auto">
                {/* `h-12` to match the input exactly, and `whitespace-nowrap` so the
                    label sets the width rather than wrapping inside a box it cannot
                    fit. The 44px minimum touch target is comfortably met at 48px. */}
                <Button
                  type="submit"
                  size="lg"
                  disabled={isSubmitting}
                  className="h-12 w-full justify-center px-6 whitespace-nowrap"
                >
                  {isSubmitting ? submittingLabel : submitLabel}
                </Button>
              </Magnetic>
            </div>

            {/* Caption size with its paired line-height, not the label role: these
                two lines are the recovery path, and the label role is the smallest
                type on the page — reserved for uppercase micro-labels, not for the
                one message a failing visitor has to read. Caption matches the
                consent note and success detail, the same register of supporting
                text. */}
            {errors.email ? (
              <p
                id="access-email-error"
                className="font-mono text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-danger)]"
              >
                {errorMessage}
              </p>
            ) : null}

            {status === "error" ? (
              <p
                role="alert"
                className="font-mono text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-danger)]"
              >
                {networkErrorMessage}
              </p>
            ) : null}
          </div>

          {/* The reading measure lives here now, on the one element that is prose. */}
          <p className="max-w-[62ch] text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-quaternary)]">
            {consentNote}
          </p>
        </form>
      ) : null}

      {/*
        One live region, mounted for the whole life of the component.

        The success state used to unmount the form and return a brand-new
        `role="status"` element in its place. A live region that enters the DOM
        already containing its message is exactly the shape screen readers are
        allowed to skip: announcements come from mutations *inside* a region
        the reader already knows about, so the region has to exist before its
        content does. It therefore renders in every state — sr-only and empty
        while the form is up, swapping to the visible confirmation box on
        success. sr-only rather than an empty in-flow div because the parent
        column lays this component out with a gap, and an empty flex item
        would open a phantom gap under the form while idle; sr-only is
        absolutely positioned, so the region costs nothing until it has
        something to say.

        `tabIndex={-1}` makes the box a valid target for the focus move in the
        effect above without putting it in the tab order, and `outline-none`
        keeps that programmatic focus from painting a ring on a block that is
        not interactive.
      */}
      <div
        ref={confirmationRef}
        role="status"
        aria-live="polite"
        tabIndex={-1}
        className={
          status === "sent"
            ? "flex max-w-[52ch] flex-col gap-2 rounded-[var(--radius-lg)] border p-5 outline-none"
            : "sr-only"
        }
        style={
          status === "sent"
            ? {
                // Derived from the token the sibling text paints with, not a
                // restated literal: the old raw value was #22e58b at 0.28 alpha
                // while --color-success is #7fd8a8, so the border and the text
                // it framed were two different greens — and a hardcoded channel
                // triple cannot follow the token if it moves again.
                borderColor: delivered
                  ? "color-mix(in srgb, var(--color-success) 28%, transparent)"
                  : "var(--color-border-strong)",
                background: delivered ? "var(--color-success-dim)" : "var(--color-surface)",
              }
            : undefined
        }
      >
        {status === "sent" ? (
          <>
            <p
              className="font-mono text-[length:var(--text-caption)]"
              style={{ color: delivered ? "var(--color-success)" : "var(--color-text-primary)" }}
            >
              {successMessage}
            </p>
            <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-secondary)]">
              {delivered ? successDetail : successUndelivered}
            </p>
          </>
        ) : null}
      </div>
    </>
  );
}
