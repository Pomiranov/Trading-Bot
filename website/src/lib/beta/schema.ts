import { z } from "zod";

/**
 * Shared client/server schema. `company` is a honeypot: real users never
 * see or fill the field (visually hidden, tabindex -1), so any non-empty
 * value marks the submission as a bot.
 */
export const betaSignupSchema = z.object({
  // 254 is the RFC 5321 ceiling for a deliverable address. Without a cap the
  // regex happily passes an arbitrarily long string, which would then be
  // forwarded to the webhook and written to the server log verbatim.
  email: z.string().trim().min(1).max(254).email(),
  company: z.string().max(200).optional(),
});

export type BetaSignupInput = z.infer<typeof betaSignupSchema>;
