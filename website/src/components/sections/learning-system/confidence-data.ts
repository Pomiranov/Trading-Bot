/**
 * Illustrative trajectory: osc_range_moex_d1_fwd's real aggregate stats
 * (D1 OOS n=29, win rate 58.6%, PF 1.16 — see content/{locale}/strategies.json)
 * are real; the per-trade path between them is not logged anywhere we can
 * read, so this specific curve is a plausible reconstruction, not a query
 * result. Shape is grounded in the real belief_updater.py mechanics: flat
 * near neutral (0.5) below the 20-trade floor, then a deliberate move
 * toward the real aggregate signal after it — never near 0 or 1.
 */
export const CONFIDENCE_BY_TRADE = [
  0.5, 0.49, 0.51, 0.5, 0.52, 0.49, 0.51, 0.5, 0.48, 0.51, 0.5, 0.52, 0.49,
  0.51, 0.5, 0.53, 0.51, 0.5, 0.52, 0.51, 0.54, 0.56, 0.55, 0.58, 0.6, 0.59,
  0.62, 0.61, 0.63,
];

export const FLOOR_TRADE = 20;
export const MIN_CONFIDENCE = 0.05;
export const MAX_CONFIDENCE = 0.95;

export const CHART_WIDTH = 600;
export const CHART_HEIGHT = 200;
export const PAD_X = 8;
export const PAD_TOP = 16;
export const PAD_BOTTOM = 28;

export function tradeToX(trade: number) {
  const n = CONFIDENCE_BY_TRADE.length;
  return PAD_X + ((trade - 1) / (n - 1)) * (CHART_WIDTH - PAD_X * 2);
}

export function confidenceToY(confidence: number) {
  const usable = CHART_HEIGHT - PAD_TOP - PAD_BOTTOM;
  return PAD_TOP + (1 - confidence) * usable;
}
