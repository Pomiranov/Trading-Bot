import posthog from "posthog-js";

/**
 * Every event payload is scalar/enum only, never free text a user typed
 * (no email, no form values) — keeps PostHog's person_profiles:
 * 'identified_only' setup honest even if a profile ever gets linked.
 *
 * NOTE — taxonomy break. This redesign renames every section slug, so
 * `journey_step.section` values all change (e.g. `philosophy-heading` ->
 * `how-it-works`), and `scene_interaction` is gone along with the Three.js
 * scene it described. Any saved funnel keyed on the old strings will go blank
 * silently rather than error. Deliberate hard cut — recorded in
 * docs/REDESIGN_QA_REPORT.md.
 */
export type CtaTarget = "sandbox_access" | "live_access" | "how_it_works" | "explore";

export type AnalyticsEvent =
  | { name: "cta_clicked"; props: { target: CtaTarget; location: string } }
  | { name: "beta_submitted"; props: { result: "success" | "error" | "invalid" } }
  | { name: "scroll_depth"; props: { milestone: 25 | 50 | 75 | 100 } }
  | { name: "journey_step"; props: { section: string } };

export function track(event: AnalyticsEvent) {
  if (typeof window === "undefined") return;
  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return;
  posthog.capture(event.name, event.props);
}
