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
            className="h-12 w-full min-w-0 rounded-[var(--radius-md)] border border-[color:var(--color-border-strong)] bg-[rgba(255,255,255,0.04)] px-4 font-mono text-[length:var(--text-caption)] text-[color:var(--color-text-primary)] outline-none placeholder:text-[color:var(--color-text-quaternary)] focus-visible:border-[color:var(--color-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)]"
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
