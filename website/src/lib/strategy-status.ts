/**
 * Status vocabularies for strategies and brokers, plus the tone each maps to.
 *
 * This lives in lib/, not in a component, because the content layer needs the
 * types too — previously `content-layer/types.ts` imported a domain type from
 * `@/components/ui/status-pill`, which had the data layer depending on the UI
 * layer.
 *
 * Colour discipline, enforced here so it cannot drift per-component:
 *   signal  (white)  — an action, a live signal, a validated decision
 *   success (green)  — healthy / confirmed trade state
 *   danger  (red)    — risk / negative trade state
 *   muted   (grey)   — inactive, planned, not yet earned
 *
 * `signal` is white, not a brand hue: the palette is strictly monochrome and
 * emphasis is carried by luminance. Green and red survive only because they
 * are trade semantics, and both are desaturated so they read as data. Every
 * pill also renders its status as text, so none of this is colour-only.
 *
 * Note what is NOT red: `frozen`. A frozen strategy is the outcome of a
 * working process, not a failure state — publishing it is a discipline signal.
 * It reads muted, never as an error.
 */

export type StatusTone = "signal" | "success" | "danger" | "muted";

/**
 * Strategy lifecycle.
 *
 * IMPORTANT — these are maintained by hand in the research journal under
 * `knowledge/`. There is no status column in the database and no auto-freeze
 * mechanism. Copy must never imply this is a live field.
 */
export type StrategyStage = "active" | "forward" | "candidate" | "frozen";

export const STRATEGY_STAGES: readonly StrategyStage[] = [
  "active",
  "forward",
  "candidate",
  "frozen",
] as const;

export const STRATEGY_STAGE_TONE: Record<StrategyStage, StatusTone> = {
  // Granted by hand, only after a forward run and Live admission.
  active: "signal",
  // Running on live data, executing in the sandbox — healthy, not yet admitted.
  forward: "success",
  candidate: "muted",
  frozen: "muted",
};

/**
 * Broker integration maturity. Each value is assigned from the actual state of
 * the adapter in `bot/broker/`, not from intent:
 *
 *   active     — registered, real order path exercised end to end
 *   sandbox    — secondary badge: a *mode*, not a connection state
 *   beta       — connected but partial (e.g. read-only)
 *   validation — implemented, undergoing verification
 *   planned    — adapter scaffolded, methods not implemented
 */
export type BrokerStatus = "active" | "sandbox" | "beta" | "validation" | "planned";

export const BROKER_STATUS_TONE: Record<BrokerStatus, StatusTone> = {
  active: "success",
  sandbox: "muted",
  beta: "muted",
  validation: "muted",
  planned: "muted",
};

export const TONE_STYLE: Record<StatusTone, { color: string; bg: string; border: string }> = {
  signal: {
    color: "var(--color-accent)",
    bg: "rgba(255,255,255,0.10)",
    border: "rgba(255,255,255,0.32)",
  },
  success: {
    color: "var(--color-success)",
    bg: "var(--color-success-dim)",
    border: "rgba(127,216,168,0.28)",
  },
  danger: {
    color: "var(--color-danger)",
    bg: "var(--color-danger-dim)",
    border: "rgba(240,138,156,0.28)",
  },
  muted: {
    color: "var(--color-neutral)",
    bg: "rgba(255,255,255,0.05)",
    border: "rgba(255,255,255,0.12)",
  },
};
