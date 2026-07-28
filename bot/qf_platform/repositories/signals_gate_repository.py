"""Signals with their gate decision — the answer to "why was this rejected?".

``skipped_signals`` existed with a schema and zero rows because nothing ever
wrote to it, which made scenario 9 of the workflow audit unanswerable *from
data* rather than merely unrendered. This repository provides both halves:

* ``record_skip`` — the write the risk/learning gate now performs.
* ``timeline``    — accepted and rejected signals in one ordered stream, with the
  six outcomes distinguishable: filled, accepted-but-broker-failed, rejected by
  risk, skipped by a filter, duplicate-suppressed, errored.

A rejection reason is never synthesised on the frontend. If the gate did not
record one, the row reports ``UNKNOWN`` and says so.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from qf_platform.environment import Environment
from qf_platform.repositories.base import BaseRepository


class GateDecision:
    """What the gate concluded. Stored verbatim in ``trading_signals.gate_decision``."""

    PENDING = "pending"
    FILLED = "filled"
    ACCEPTED_UNFILLED = "accepted_unfilled"   # gate passed, broker refused
    REJECTED = "rejected"                      # risk gate said no
    SKIPPED = "skipped"                        # a filter said no
    DUPLICATE = "duplicate"                    # already have this position
    ERRORED = "errored"
    UNKNOWN = "unknown"


class GateStage:
    """Which gate made the call — the stage matters as much as the verdict."""

    RISK = "risk"
    LEARNING = "learning"
    FILTER = "filter"
    DUPLICATE = "duplicate"
    BROKER = "broker"
    MARKET_CLOSED = "market_closed"
    UNKNOWN = "unknown"


#: Human text per stage. Kept server-side so one vocabulary serves the UI, the
#: Telegram notifications and the event log.
STAGE_LABELS = {
    GateStage.RISK: "Риск-шлюз",
    GateStage.LEARNING: "Система обучения",
    GateStage.FILTER: "Фильтр сигналов",
    GateStage.DUPLICATE: "Дубликат позиции",
    GateStage.BROKER: "Брокер",
    GateStage.MARKET_CLOSED: "Рынок закрыт",
    GateStage.UNKNOWN: "Источник не записан",
}


class SignalsGateRepository(BaseRepository):
    # ── Reads ────────────────────────────────────────────────────────────────

    def timeline(
        self,
        *,
        limit: int = 100,
        environment: Optional[Environment] = None,
        decision: Optional[str] = None,
        ticker: Optional[str] = None,
        strategy_id: Optional[str] = None,
    ) -> list[dict]:
        """Accepted and rejected signals merged into one time-ordered stream.

        Both halves are selected with the same column list so the union is a
        single shape the client can render with one row renderer. ``origin``
        tells them apart for debugging; ``gate_decision`` is what the UI shows.
        """
        params: dict = {"lim": limit}
        sig_clauses = ["1=1"]
        skip_clauses = ["1=1"]

        if environment is not None:
            env = Environment.coerce(environment).value
            params["env"] = env
            sig_clauses.append("COALESCE(s.environment, 'sandbox') = :env")
            skip_clauses.append("COALESCE(k.environment, 'sandbox') = :env")
        if ticker:
            params["ticker"] = ticker.upper()
            sig_clauses.append("s.asset = :ticker")
            skip_clauses.append("k.ticker = :ticker")
        if strategy_id:
            params["sid"] = strategy_id
            sig_clauses.append("s.strategy_id = :sid")
            skip_clauses.append("k.strategy_id = :sid")

        rows = self._query(
            f"""
            SELECT * FROM (
                SELECT
                    'signal'                        AS origin,
                    CAST(s.id AS text)              AS row_id,
                    s.generated_at                  AS occurred_at,
                    s.asset                         AS ticker,
                    s.signal_type                   AS direction,
                    s.timeframe                     AS timeframe,
                    s.strategy_id                   AS strategy_id,
                    s.exchange                      AS exchange,
                    s.entry_price                   AS entry_price,
                    s.stop_loss                     AS stop_loss,
                    s.take_profit_1                 AS take_profit,
                    s.risk_reward                   AS risk_reward,
                    s.confidence                    AS confidence,
                    s.sample_size                   AS sample_size,
                    s.probability_pct               AS probability_pct,
                    COALESCE(s.gate_decision, CASE s.status
                        WHEN 'filled'    THEN 'filled'
                        WHEN 'executing' THEN 'pending'
                        WHEN 'new'       THEN 'pending'
                        ELSE 'unknown' END)         AS gate_decision,
                    COALESCE(s.gate_stage, 'unknown') AS gate_stage,
                    s.gate_reason                   AS gate_reason,
                    s.gate_decided_at               AS gate_decided_at,
                    s.resulting_trade_id            AS resulting_trade_id,
                    s.source_candle_at              AS source_candle_at,
                    s.status                        AS status,
                    COALESCE(s.environment, 'sandbox') AS environment
                FROM trading_signals s
                WHERE {' AND '.join(sig_clauses)}

                UNION ALL

                SELECT
                    'skip'                          AS origin,
                    CAST(k.skip_id AS text)         AS row_id,
                    k.skipped_at                    AS occurred_at,
                    k.ticker                        AS ticker,
                    k.direction                     AS direction,
                    k.timeframe                     AS timeframe,
                    k.strategy_id                   AS strategy_id,
                    NULL                            AS exchange,
                    NULL                            AS entry_price,
                    NULL                            AS stop_loss,
                    NULL                            AS take_profit,
                    NULL                            AS risk_reward,
                    k.confidence                    AS confidence,
                    k.sample_size                   AS sample_size,
                    NULL                            AS probability_pct,
                    CASE COALESCE(k.gate_stage, 'unknown')
                        WHEN 'duplicate' THEN 'duplicate'
                        WHEN 'filter'    THEN 'skipped'
                        WHEN 'broker'    THEN 'accepted_unfilled'
                        WHEN 'unknown'   THEN 'unknown'
                        ELSE 'rejected' END         AS gate_decision,
                    COALESCE(k.gate_stage, 'unknown') AS gate_stage,
                    COALESCE(k.reason_text, k.skip_reason) AS gate_reason,
                    k.skipped_at                    AS gate_decided_at,
                    NULL                            AS resulting_trade_id,
                    NULL                            AS source_candle_at,
                    k.skip_reason                   AS status,
                    COALESCE(k.environment, 'sandbox') AS environment
                FROM skipped_signals k
                WHERE {' AND '.join(skip_clauses)}
            ) merged
            {"WHERE merged.gate_decision = :decision" if decision else ""}
            ORDER BY occurred_at DESC NULLS LAST
            LIMIT :lim
            """,
            {**params, **({"decision": decision} if decision else {})},
        )
        return rows

    def decision_census(self, *, environment: Optional[Environment] = None) -> list[dict]:
        params: dict = {}
        clause = ""
        if environment is not None:
            params["env"] = Environment.coerce(environment).value
            clause = "WHERE COALESCE(environment, 'sandbox') = :env"
        return self._query(
            f"""
            SELECT COALESCE(gate_decision, 'unknown') AS gate_decision, COUNT(*) AS n
            FROM trading_signals {clause}
            GROUP BY 1 ORDER BY n DESC
            """,
            params,
        )

    def latest(self, *, environment: Optional[Environment] = None) -> Optional[dict]:
        rows = self.timeline(limit=1, environment=environment)
        return rows[0] if rows else None

    def skipped(
        self,
        *,
        limit: int = 50,
        environment: Optional[Environment] = None,
    ) -> list[dict]:
        params: dict = {"lim": limit}
        clause = ""
        if environment is not None:
            params["env"] = Environment.coerce(environment).value
            clause = "WHERE COALESCE(environment, 'sandbox') = :env"
        return self._query(
            f"""
            SELECT skip_id, skipped_at, strategy_id, ticker, timeframe, direction,
                   skip_reason, COALESCE(gate_stage, 'unknown') AS gate_stage,
                   reason_text, confidence, sample_size, details,
                   COALESCE(environment, 'sandbox') AS environment
            FROM skipped_signals {clause}
            ORDER BY skipped_at DESC
            LIMIT :lim
            """,
            params,
        )

    # ── Writes — performed by the engine's gate, never by a GET ──────────────

    def record_skip(
        self,
        *,
        strategy_id: str,
        ticker: Optional[str],
        direction: Optional[str],
        gate_stage: str,
        reason_code: str,
        reason_text: str,
        environment: Environment = Environment.SANDBOX,
        timeframe: Optional[str] = None,
        signal_id: Optional[int] = None,
        confidence: Optional[float] = None,
        sample_size: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Record one rejected/skipped signal.

        Swallows its own failure on purpose: the gate's job is to stop a trade,
        and an audit-table write must never be able to prevent that. The failure
        is logged, not raised.
        """
        try:
            self._execute(
                """
                INSERT INTO skipped_signals
                    (strategy_id, ticker, timeframe, direction, skip_reason,
                     gate_stage, reason_text, confidence, sample_size, details,
                     environment, signal_id, is_sandbox)
                VALUES
                    (:sid, :ticker, :tf, :dir, :code,
                     :stage, :text, :conf, :n, CAST(:details AS JSONB),
                     :env, :signal_id, :is_sandbox)
                """,
                {
                    "sid": (strategy_id or "unknown")[:50],
                    "ticker": (ticker or None) and ticker.upper()[:20],
                    "tf": (timeframe or None) and timeframe[:10],
                    "dir": (direction or None) and direction[:8],
                    "code": (reason_code or "unknown")[:50],
                    "stage": (gate_stage or GateStage.UNKNOWN)[:24],
                    "text": reason_text,
                    "conf": confidence,
                    "n": sample_size,
                    "details": json.dumps(details or {}, ensure_ascii=False),
                    "env": Environment.coerce(environment).value,
                    "signal_id": signal_id,
                    "is_sandbox": Environment.coerce(environment) is Environment.SANDBOX,
                },
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "Не удалось записать skipped_signal для %s/%s", strategy_id, ticker,
                exc_info=True,
            )

    def record_decision(
        self,
        signal_id: int,
        *,
        decision: str,
        stage: str = GateStage.UNKNOWN,
        reason: Optional[str] = None,
        resulting_trade_id: Optional[str] = None,
        confidence: Optional[float] = None,
        sample_size: Optional[int] = None,
    ) -> None:
        try:
            self._execute(
                """
                UPDATE trading_signals
                   SET gate_decision = :decision,
                       gate_stage    = :stage,
                       gate_reason   = COALESCE(:reason, gate_reason),
                       gate_decided_at = :now,
                       resulting_trade_id = COALESCE(:trade_id, resulting_trade_id),
                       confidence    = COALESCE(:conf, confidence),
                       sample_size   = COALESCE(:n, sample_size)
                 WHERE id = :id
                """,
                {
                    "id": signal_id,
                    "decision": (decision or GateDecision.UNKNOWN)[:24],
                    "stage": (stage or GateStage.UNKNOWN)[:24],
                    "reason": reason,
                    "trade_id": resulting_trade_id,
                    "conf": confidence,
                    "n": sample_size,
                    "now": datetime.now(timezone.utc),
                },
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "Не удалось записать gate decision для сигнала %s", signal_id, exc_info=True
            )
