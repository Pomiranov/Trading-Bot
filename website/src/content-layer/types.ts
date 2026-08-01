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
  /**
   * e.g. "IndicatorEngine.latest()" — the symbol in `bot/` this stage is.
   *
   * Internal provenance, not rendered: the pipeline cards used to close on it
   * and no longer do (see the note in how-it-works/pipeline-spine.tsx). It is
   * kept parsed and typed so the origin of a stage stays traceable in the
   * content files, and so re-exposing it for a technical audience is a one-line
   * change rather than a content migration.
   */
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
   * The symbol or constant in `bot/` that makes the principle checkable rather
   * than a claim.
   *
   * Internal provenance, not rendered — same standing as `PipelineStage.
   * sourceRef`, and removed from the card for the same reason (see the note in
   * sections/foundation/foundation-section.tsx). The figures it cited are
   * stated in the body copy of the principles themselves, so nothing a reader
   * can act on depends on this being visible.
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
