import posthog from "posthog-js";

/**
 * Every event payload is scalar/enum only, never free text a user typed
 * (no email, no form values) — keeps PostHog's person_profiles:
 * 'identified_only' setup honest even if a profile ever gets linked.
 */
export type AnalyticsEvent =
  | { name: "cta_clicked"; props: { target: "beta_form" | "explore"; location: string } }
  | { name: "beta_submitted"; props: { result: "success" | "error" | "invalid" } }
  | { name: "scroll_depth"; props: { milestone: 25 | 50 | 75 | 100 } }
  | {
      name: "scene_interaction";
      props: {
        mode: string;
        state: "mounted" | "pointer_engaged" | "fallback_shown";
      };
    }
  | { name: "journey_step"; props: { section: string } };

export function track(event: AnalyticsEvent) {
  if (typeof window === "undefined") return;
  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return;
  posthog.capture(event.name, event.props);
}
