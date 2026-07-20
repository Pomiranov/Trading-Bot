import { z } from "zod";

/**
 * Shared client/server schema. `company` is a honeypot: real users never
 * see or fill the field (visually hidden, tabindex -1), so any non-empty
 * value marks the submission as a bot.
 */
export const betaSignupSchema = z.object({
  email: z.string().trim().min(1).email(),
  company: z.string().optional(),
});

export type BetaSignupInput = z.infer<typeof betaSignupSchema>;
