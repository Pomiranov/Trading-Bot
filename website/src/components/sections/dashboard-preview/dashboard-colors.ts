/**
 * This mockup deliberately borrows the REAL operational dashboard's own
 * accent (bot/ui/static/design-system.css: --qf-accent #F7931A, --qf-long
 * #00c076, --qf-short #f6465d) rather than our marketing site's Signal
 * Amber — the point of this section is an honest representation of the
 * actual product's interface, not a reskin of it. Scoped to this
 * component only, not a global token.
 */
export const DASHBOARD_COLORS = {
  accent: "#f7931a",
  long: "#00c076",
  short: "#f6465d",
} as const;
