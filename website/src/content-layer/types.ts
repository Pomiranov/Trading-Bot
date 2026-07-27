import type { ReactNode } from "react";
import type { StrategyStage } from "@/lib/strategy-status";

/** Internal provenance marker. Since no result figures are published any more,
 * this drives no visible badge — it exists so the origin of a record stays
 * traceable in the content files. */
export type DataSource = "real-forward-test" | "illustrative";

export interface PipelineStage {
  /** Matches the real module/stage name in bot/main.py::_process_ticker() —
   * internal only, not rendered, kept for traceability. */
  id:
    | "candle-loader"
    | "indicator-engine"
    | "rules-engine"
    | "belief-gate"
    | "risk-manager"
    | "broker"
    | "memory-writer";
  order: number;
  title: string;
  description: ReactNode;
  /** One-line plain-language explanation, shown above the technical body. */
  plain: string;
  /** Step name in the flow: Observe / Context / Strategy / Confidence / … */
  stepLabel: string;
  /** e.g. "IndicatorEngine.latest()" — shown as a small mono caption. */
  sourceRef?: string;
}

export interface StrategyRecord {
  /** Real strategy id, e.g. "osc_range_moex_d1_fwd". */
  id: string;
  market: "MOEX" | "Bybit";
  timeframe: string;
  /**
   * Lifecycle stage. Maintained by hand in the research journal under
   * `knowledge/` — there is no status column in the database and no
   * auto-freeze. The UI must not imply this is live telemetry.
   */
  status: StrategyStage;
  /** Localized short status note — the only field allowed to differ per locale. */
  statusNote: string;
  lastUpdate: string;
  source: DataSource;
}

export interface PhilosophyBlock {
  id: string;
  heading: string;
  body: ReactNode;
  /**
   * Small technical note pinned to the foot of the card — the symbol or
   * constant in `bot/` that makes the principle checkable rather than a claim.
   * Optional: a principle with nothing concrete to point at shows no note
   * rather than an invented one.
   */
  sourceRef?: string;
}

export interface LearningSystemCopy {
  intro: ReactNode;
  sliderCaption: string;
  minTradesFloor: number;
  minConfidence: number;
  maxConfidence: number;
}

export interface ContentSource {
  getPipelineStages(locale: string): Promise<PipelineStage[]>;
  getStrategies(locale: string): Promise<StrategyRecord[]>;
  getPhilosophyBlocks(locale: string): Promise<PhilosophyBlock[]>;
  getLearningSystemCopy(locale: string): Promise<LearningSystemCopy>;
}
