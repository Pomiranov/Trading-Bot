"""Signals with their gate decision.

Six outcomes must be visually distinct, and none of them were: accepted-and-filled,
accepted-but-broker-refused, rejected by risk, skipped by a filter,
duplicate-suppressed, and errored. This service returns the decision, the stage
that made it and the human reason, all from the database.

Where the gate never recorded a reason, the row says ``unknown`` and the UI shows
«причина не записана». A plausible reason is never synthesised on the client —
that would be indistinguishable from a real one.
"""

from __future__ import annotations

import logging
from typing import Optional

from qf_platform.contracts import EmptyReason, Freshness, Units, age_seconds, safe_float, to_display
from qf_platform.environment import Environment
from qf_platform.repositories.signals_gate_repository import (
    STAGE_LABELS,
    GateDecision,
    GateStage,
    SignalsGateRepository,
)
from qf_platform.services.environment_service import stale_threshold

logger = logging.getLogger(__name__)

DECISION_LABELS = {
    GateDecision.PENDING: "Ожидает",
    GateDecision.FILLED: "Исполнен",
    GateDecision.ACCEPTED_UNFILLED: "Принят, брокер отказал",
    GateDecision.REJECTED: "Отклонён",
    GateDecision.SKIPPED: "Пропущен фильтром",
    GateDecision.DUPLICATE: "Дубликат подавлен",
    GateDecision.ERRORED: "Ошибка",
    GateDecision.UNKNOWN: "Решение не записано",
}

#: Whether the outcome is a success, a refusal or a fault. Drives the *shape*, so
#: the six outcomes survive greyscale.
DECISION_TONE = {
    GateDecision.FILLED: "positive",
    GateDecision.PENDING: "neutral",
    GateDecision.REJECTED: "negative",
    GateDecision.SKIPPED: "neutral",
    GateDecision.DUPLICATE: "neutral",
    GateDecision.ACCEPTED_UNFILLED: "warning",
    GateDecision.ERRORED: "negative",
    GateDecision.UNKNOWN: "unknown",
}

SIGNALS_STALE_AFTER_SECONDS = 900


class GateService:
    def __init__(self, engine):
        self._repo = SignalsGateRepository(engine)

    def timeline(
        self,
        *,
        limit: int = 100,
        environment: Optional[Environment] = None,
        decision: Optional[str] = None,
        ticker: Optional[str] = None,
        strategy_id: Optional[str] = None,
    ) -> dict:
        rows = self._repo.timeline(
            limit=limit, environment=environment, decision=decision,
            ticker=ticker, strategy_id=strategy_id,
        )

        signals = []
        newest = None
        for row in rows:
            occurred = row.get("occurred_at")
            if occurred and (newest is None or occurred > newest):
                newest = occurred

            decision_value = str(row.get("gate_decision") or GateDecision.UNKNOWN)
            stage = str(row.get("gate_stage") or GateStage.UNKNOWN)
            candle_at = row.get("source_candle_at")
            confidence = safe_float(row.get("confidence"))
            sample_size = row.get("sample_size")

            signals.append({
                "id": row.get("row_id"),
                "origin": row.get("origin"),
                "occurred_at": to_display(occurred),
                "age_seconds": age_seconds(occurred),
                "ticker": row.get("ticker"),
                "direction": (row.get("direction") or "").upper() or None,
                "timeframe": row.get("timeframe"),
                "strategy_id": row.get("strategy_id"),
                "exchange": row.get("exchange"),
                "entry_price": safe_float(row.get("entry_price")),
                "stop_loss": safe_float(row.get("stop_loss")),
                "take_profit": safe_float(row.get("take_profit")),
                "risk_reward": safe_float(row.get("risk_reward")),
                "gate_decision": decision_value,
                "gate_decision_label": DECISION_LABELS.get(decision_value, decision_value),
                "gate_tone": DECISION_TONE.get(decision_value, "unknown"),
                "gate_stage": stage,
                "gate_stage_label": STAGE_LABELS.get(stage, stage),
                "gate_reason": row.get("gate_reason"),
                "gate_reason_missing": not bool(row.get("gate_reason")),
                "gate_decided_at": to_display(row.get("gate_decided_at")),
                "resulting_trade_id": row.get("resulting_trade_id"),
                # Confidence is never shown without its sample size, so both
                # travel together and the client renders «0,61 · выборка 12».
                "confidence": None if confidence is None else round(confidence, 2),
                "sample_size": None if sample_size is None else int(sample_size),
                "confidence_is_mature": bool(sample_size and int(sample_size) >= 30),
                "source_candle_at": to_display(candle_at),
                "source_candle_age_seconds": age_seconds(candle_at) if candle_at else None,
                "source_candle_stale": (
                    None if candle_at is None
                    else (age_seconds(candle_at) or 0) > stale_threshold(row.get("timeframe"))
                ),
                "environment": row.get("environment") or Environment.UNKNOWN.value,
            })

        census = {
            str(row["gate_decision"]): int(row["n"])
            for row in self._repo.decision_census(environment=environment)
        }

        return {
            "signals": signals,
            "count": len(signals),
            "empty_reason": None if signals else EmptyReason.NO_SIGNALS,
            "census": census,
            "decisions": [
                {"value": key, "label": DECISION_LABELS[key], "tone": DECISION_TONE[key]}
                for key in DECISION_LABELS
            ],
            "_source_as_of": newest,
            "units": {
                "entry_price": Units.PRICE,
                "confidence": Units.RATIO,
                "risk_reward": Units.RATIO,
            },
        }

    def latest(self, *, environment: Optional[Environment] = None) -> Optional[dict]:
        payload = self.timeline(limit=1, environment=environment)
        return payload["signals"][0] if payload["signals"] else None

    @staticmethod
    def freshness(payload: dict) -> Freshness:
        return Freshness(
            source_as_of=payload.get("_source_as_of"),
            source="trading_signals + skipped_signals",
            stale_after_seconds=SIGNALS_STALE_AFTER_SECONDS,
        )

    def gate_summary(self, *, environment: Optional[Environment] = None) -> dict:
        """Counts per decision, for the Signals screen's header strip.

        Reports whether the gate has recorded anything at all: a zero-row
        ``skipped_signals`` means rejection reasons are unavailable, and that is
        a data gap the UI must state rather than render as "no rejections".
        """
        census = {
            str(row["gate_decision"]): int(row["n"])
            for row in self._repo.decision_census(environment=environment)
        }
        skipped = self._repo.skipped(limit=1, environment=environment)
        return {
            "census": census,
            "gate_recording": bool(skipped) or bool(
                census.get(GateDecision.REJECTED) or census.get(GateDecision.SKIPPED)
            ),
            "gate_recording_note": (
                None if skipped
                else "Шлюз ещё не записал ни одного отклонения — причины отказов недоступны."
            ),
        }
