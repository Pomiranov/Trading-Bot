"use client";

import { useState } from "react";
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

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<BetaSignupInput>({
    resolver: zodResolver(betaSignupSchema),
    defaultValues: { email: "", company: "" },
  });

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

  if (status === "sent") {
    return (
      <div
        role="status"
        className="flex max-w-[52ch] flex-col gap-2 rounded-[var(--radius-lg)] border p-5"
        style={{
          borderColor: delivered ? "rgba(34,229,139,0.28)" : "var(--color-border-strong)",
          background: delivered ? "var(--color-success-dim)" : "var(--color-surface)",
        }}
      >
        <p
          className="font-mono text-[length:var(--text-caption)]"
          style={{ color: delivered ? "var(--color-success)" : "var(--color-text-primary)" }}
        >
          {successMessage}
        </p>
        <p className="text-[length:var(--text-caption)] leading-[var(--text-caption--line-height)] text-[color:var(--color-text-secondary)]">
          {delivered ? successDetail : successUndelivered}
        </p>
      </div>
    );
  }

  return (
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

              Do not quote a rejected utility literally in a comment here, even
              to document it: Tailwind scans this file for class candidates and
              would compile the example into real CSS. That is the failure mode
              recorded at the top of globals.css, where a placeholder in a lint
              script's hint string became a font-size and took the dev server to
              a 500. It would also re-trip the grep gate from the comment alone.
            */
            className="h-12 w-full min-w-0 rounded-[var(--radius-md)] border border-[color:var(--color-border-strong)] bg-[color:var(--color-fill-subtle)] px-4 font-mono text-[length:var(--text-caption)] text-[color:var(--color-text-primary)] outline-none transition-[border-color,background-color,box-shadow] duration-[var(--duration-base)] ease-[var(--ease-out-expo)] placeholder:text-[color:var(--color-text-quaternary)] hover:bg-[color:var(--color-highlight-bg)] hover:shadow-[var(--btn-glow-hover)] focus-visible:border-[color:var(--color-accent)] focus-visible:shadow-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
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

        {errors.email ? (
          <p
            id="access-email-error"
            className="font-mono text-[length:var(--text-label)] text-[color:var(--color-danger)]"
          >
            {errorMessage}
          </p>
        ) : null}

        {status === "error" ? (
          <p
            role="alert"
            className="font-mono text-[length:var(--text-label)] text-[color:var(--color-danger)]"
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
  );
}
