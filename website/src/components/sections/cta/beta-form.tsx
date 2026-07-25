"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { betaSignupSchema, type BetaSignupInput } from "@/lib/beta/schema";
import { MagneticButton } from "@/components/ui/magnetic-button";
import { track } from "@/lib/analytics/events";

export function BetaForm({
  emailLabel,
  emailPlaceholder,
  submitLabel,
  successMessage,
  errorMessage,
  networkErrorMessage,
}: {
  emailLabel: string;
  emailPlaceholder: string;
  submitLabel: string;
  successMessage: string;
  errorMessage: string;
  networkErrorMessage: string;
}) {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
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
    track({ name: "cta_clicked", props: { target: "beta_form", location: "cta" } });
    try {
      const res = await fetch("/api/beta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("request failed");
      setStatus("success");
      track({ name: "beta_submitted", props: { result: "success" } });
      reset();
    } catch {
      setStatus("error");
      track({ name: "beta_submitted", props: { result: "error" } });
    }
  }

  function onInvalid() {
    track({ name: "beta_submitted", props: { result: "invalid" } });
  }

  if (status === "success") {
    return (
      <div
        className="inline-flex items-center gap-2 rounded-xl px-4 py-3 font-mono text-[13px]"
        role="status"
        style={{
          background: "rgba(44,233,123,0.08)",
          border: "1px solid rgba(44,233,123,0.2)",
          color: "var(--color-success)",
        }}
      >
        <span className="size-1.5 rounded-full" style={{ backgroundColor: "var(--color-success)" }} />
        {successMessage}
      </div>
    );
  }

  const emailRegistration = register("email");

  return (
    <form
      onSubmit={handleSubmit(onSubmit, onInvalid)}
      noValidate
      className="flex flex-col gap-3 sm:flex-row sm:items-start"
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor="beta-email" className="sr-only">
          {emailLabel}
        </label>
        <input
          id="beta-email"
          type="email"
          placeholder={emailPlaceholder}
          autoComplete="email"
          aria-invalid={!!errors.email}
          className="h-12 w-64 rounded-[var(--radius-md)] px-4 font-mono text-[13px] outline-none transition-all duration-200"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: errors.email
              ? "1px solid rgba(229,72,77,0.5)"
              : "1px solid rgba(255,255,255,0.1)",
            backdropFilter: "blur(12px)",
            color: "var(--color-text-primary)",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
          }}
          {...emailRegistration}
          onFocus={(e) => {
            e.currentTarget.style.border = "1px solid rgba(255,138,30,0.4)";
            e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.04), 0 0 0 3px rgba(255,138,30,0.08)";
          }}
          onBlur={(e) => {
            emailRegistration.onBlur(e);
            e.currentTarget.style.border = "1px solid rgba(255,255,255,0.1)";
            e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.04)";
          }}
        />
        {/* Honeypot */}
        <input
          type="text"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          className="sr-only"
          {...register("company")}
        />
        {errors.email ? (
          <p className="font-mono text-[11px]" style={{ color: "var(--color-danger)" }}>
            {errorMessage}
          </p>
        ) : null}
        {status === "error" ? (
          <p role="alert" className="font-mono text-[11px]" style={{ color: "var(--color-danger)" }}>
            {networkErrorMessage}
          </p>
        ) : null}
      </div>
      <MagneticButton type="submit" size="lg" disabled={isSubmitting}>
        {submitLabel}
      </MagneticButton>
    </form>
  );
}
