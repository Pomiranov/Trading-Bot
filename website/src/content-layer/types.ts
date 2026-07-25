import type { ReactNode } from "react";
import type { StrategyStatus } from "@/components/ui/status-pill";

/** How a numeric claim on the site is backed — drives the visual treatment
 * (e.g. an "illustrative" label). No fabricated precision ships unlabeled. */
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
  /** e.g. "IndicatorEngine.latest()" — shown as a small mono caption. */
  sourceRef?: string;
}

export interface StrategyMetrics {
  winRate?: number;
  profitFactor?: number;
  sampleSize?: number;
  oos?: boolean;
  drawdown?: number;
}

export interface StrategyRecord {
  /** Real strategy id, e.g. "osc_range_moex_d1_fwd". */
  id: string;
  market: "MOEX" | "Bybit";
  timeframe: string;
  status: StrategyStatus;
  /** Localized short status note, e.g. "Forward-deployed" / "Frozen — not forward-tested". */
  statusNote: string;
  lastUpdate: string;
  metrics?: StrategyMetrics;
  source: DataSource;
}

export interface PhilosophyBlock {
  id: string;
  heading: string;
  body: ReactNode;
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
