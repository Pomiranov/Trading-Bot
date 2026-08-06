import type { BetaSignupInput } from "./schema";

/**
 * The result of a submission attempt.
 *
 * `delivered` is the important field. The UI uses it to decide what it is
 * allowed to promise: only a destination that actually stored or forwarded the
 * address may produce copy saying we will be in touch.
 */
export interface BetaSubmitResult {
  delivered: boolean;
}

export interface BetaAdapter {
  submit(input: Pick<BetaSignupInput, "email">): Promise<BetaSubmitResult>;
}

/**
 * Dev/default adapter: logs server-side only and stores nothing.
 *
 * It reports `delivered: false` so the form cannot claim we received the
 * request. Previously this adapter console.log'd the address while the UI
 * rendered "Request received. We follow up if it's a fit." — a false statement
 * on the only conversion path on the site.
 */
const consoleAdapter: BetaAdapter = {
  async submit(input) {
    // Masked, not verbatim: this is the *default* adapter, so on a deployment
    // where nobody configured a webhook the full address would land in the
    // hosting provider's logs with unknown retention. `a***@domain` is enough
    // to see signups arriving without turning the log into a PII store.
    const at = input.email.indexOf("@");
    const masked = at > 0 ? `${input.email[0]}***${input.email.slice(at)}` : "***";
    console.log(
      `[beta-adapter:console] signup received, NOT stored (no destination configured): ${masked}`,
    );
    return { delivered: false };
  },
};

/**
 * Forwards the address to an HTTPS endpoint — Formspree, a webhook, an
 * automation, whatever the owner picks — and reports `delivered: true` only
 * when that endpoint accepts it.
 *
 * Configure with:
 *   BETA_ADAPTER=webhook
 *   BETA_WEBHOOK_URL=https://…
 */
function webhookAdapter(url: string): BetaAdapter {
  return {
    async submit(input) {
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ email: input.email, source: "quant-website" }),
        });
        if (!res.ok) {
          console.error(`[beta-adapter:webhook] destination returned ${res.status}`);
          return { delivered: false };
        }
        return { delivered: true };
      } catch (error) {
        console.error("[beta-adapter:webhook] request failed", error);
        return { delivered: false };
      }
    },
  };
}

export function getBetaAdapter(): BetaAdapter {
  const url = process.env.BETA_WEBHOOK_URL;
  if (process.env.BETA_ADAPTER === "webhook" && url) return webhookAdapter(url);
  return consoleAdapter;
}
