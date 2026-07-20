"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { betaSignupSchema, type BetaSignupInput } from "@/lib/beta/schema";
import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics/events";

export function BetaForm({
  emailLabel,
  emailPlaceholder,
  submitLabel,
  successMessage,
  errorMessage,
}: {
  emailLabel: string;
  emailPlaceholder: string;
  submitLabel: string;
  successMessage: string;
  errorMessage: string;
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
      <p
        role="status"
        className="font-mono text-[13px] text-[color:var(--color-accent)]"
      >
        {successMessage}
      </p>
    );
  }

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
          className="h-10 w-64 rounded-[var(--radius-md)] border border-[color:var(--color-border)] bg-transparent px-3.5 font-mono text-[13px] text-[color:var(--color-text-primary)] outline-none placeholder:text-[color:var(--color-text-tertiary)] focus-visible:border-[color:var(--color-accent)]"
          {...register("email")}
        />
        {/* Honeypot: visually and semantically hidden from real users, left for bots that fill every field. */}
        <input
          type="text"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          className="sr-only"
          {...register("company")}
        />
        {errors.email ? (
          <p className="font-mono text-[11px] text-[color:var(--color-danger)]">
            {errorMessage}
          </p>
        ) : null}
        {status === "error" ? (
          <p role="alert" className="font-mono text-[11px] text-[color:var(--color-danger)]">
            {errorMessage}
          </p>
        ) : null}
      </div>
      <Button type="submit" disabled={isSubmitting}>
        {submitLabel}
      </Button>
    </form>
  );
}
