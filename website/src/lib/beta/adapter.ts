import type { BetaSignupInput } from "./schema";

export interface BetaAdapter {
  submit(input: Pick<BetaSignupInput, "email">): Promise<void>;
}

/**
 * Dev/default adapter: logs server-side only, never claims delivery to a
 * real destination. Swap via BETA_ADAPTER once a real one (Resend,
 * Formspree, etc.) is chosen — the route and form never change.
 */
const consoleAdapter: BetaAdapter = {
  async submit(input) {
    console.log(
      `[beta-adapter:console] signup received (no destination configured): ${input.email}`,
    );
  },
};

export function getBetaAdapter(): BetaAdapter {
  return consoleAdapter;
}
