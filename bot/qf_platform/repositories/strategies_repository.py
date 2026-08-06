"""Strategy state from ``belief_system`` — the real strategy entity.

The old UI called this "Learning" and rendered a confidence number with no
sample size, computing win rate from a 2-row table while the account had executed
35 trades. Two rules are enforced at this layer so no caller can break them:

* ``confidence`` and ``total_trades`` are always selected together. There is no
  method that returns one without the other.
* The strategy list comes from the database. A hardcoded Python list of
  strategy ids (``['default_moex', 'osc_range_moex', …]``) cannot include a
  strategy the engine created, and cannot drop one that was retired.
"""

from __future__ import annotations

from typing import Optional

from qf_platform.repositories.base import BaseRepository


class StrategyState:
    """Lifecycle state. Derived, because no ``frozen`` column exists yet.

    Deriving is honest as long as the derivation is stated: a strategy that has
    never traded is ``candidate``, not ``frozen``, and «Заморожена» is never
    invented for a strategy whose freeze the database never recorded.
    """

    ACTIVE = "active"
    CANDIDATE = "candidate"      # exists, has not traded enough to judge
    DORMANT = "dormant"          # traded once, silent for a long time
    RETIRED = "retired"
    UNKNOWN = "unknown"


class StrategiesRepository(BaseRepository):
    def list_strategies(self) -> list[dict]:
        """Every strategy with its statistics and its sample size.

        ``last_trade_at`` and ``updated_at`` are both returned: "the belief was
        recomputed" and "the strategy traded" are different events, and the
        difference is what distinguishes a dormant strategy from a stale belief.
        """
        return self._query(
            """
            SELECT b.strategy_id,
                   b.strategy_name,
                   b.market,
                   b.description,
                   b.total_trades,
                   b.winning_trades,
                   b.losing_trades,
                   b.win_rate,
                   b.profit_factor,
                   b.expectancy,
                   b.sharpe_ratio,
                   b.avg_win_r,
                   b.avg_loss_r,
                   b.max_consecutive_losses,
                   b.confidence,
                   b.best_regime,
                   b.best_timeframe,
                   b.created_at,
                   b.updated_at,
                   b.last_trade_at,
                   t.observed_trades,
                   t.observed_pnl,
                   t.observed_wins,
                   t.last_observed_at,
                   t.environments
            FROM belief_system b
            LEFT JOIN LATERAL (
                SELECT COUNT(*)                          AS observed_trades,
                       COALESCE(SUM(pnl), 0)             AS observed_pnl,
                       COUNT(*) FILTER (WHERE pnl > 0)   AS observed_wins,
                       MAX(closed_at)                    AS last_observed_at,
                       ARRAY_AGG(DISTINCT COALESCE(environment,
                           CASE WHEN is_sandbox IS TRUE  THEN 'sandbox'
                                WHEN is_sandbox IS FALSE THEN 'live'
                                ELSE 'unknown' END))     AS environments
                FROM trades
                WHERE trades.strategy_id = b.strategy_id
                  AND trades.closed_at IS NOT NULL
            ) t ON true
            ORDER BY b.total_trades DESC, b.strategy_id
            """
        )

    def get_strategy(self, strategy_id: str) -> Optional[dict]:
        rows = self._query(
            """
            SELECT strategy_id, strategy_name, market, description,
                   total_trades, winning_trades, losing_trades, win_rate,
                   profit_factor, expectancy, sharpe_ratio, avg_win_r, avg_loss_r,
                   max_consecutive_losses, confidence, best_regime, best_timeframe,
                   created_at, updated_at, last_trade_at
            FROM belief_system WHERE strategy_id = :sid
            """,
            {"sid": strategy_id},
        )
        return rows[0] if rows else None

    def confidence_history(self, strategy_id: str, limit: int = 60) -> list[dict]:
        """Confidence over time, reconstructed from closed trades.

        There is no ``belief_history`` table, so this is the closest honest
        approximation: the confidence value stamped on each trade at the moment
        it closed. It is labelled as trade-stamped in the API, and the missing
        table is reported as a gap rather than papered over with an interpolation.
        """
        rows = self._query(
            """
            SELECT closed_at AS ts, confidence AS value, trade_id, pnl
            FROM trades
            WHERE strategy_id = :sid
              AND closed_at IS NOT NULL
              AND confidence IS NOT NULL
            ORDER BY closed_at DESC
            LIMIT :lim
            """,
            {"sid": strategy_id, "lim": limit},
        )
        return list(reversed(rows))

    def regime_breakdown(self, strategy_id: Optional[str] = None) -> list[dict]:
        clause = "AND strategy_id = :sid" if strategy_id else ""
        return self._query(
            f"""
            SELECT COALESCE(market_regime, 'unknown') AS regime,
                   strategy_id,
                   COUNT(*)                        AS n,
                   COUNT(*) FILTER (WHERE pnl > 0) AS wins,
                   COALESCE(SUM(pnl), 0)           AS total_pnl,
                   AVG(pnl)                        AS avg_pnl
            FROM trades
            WHERE closed_at IS NOT NULL {clause}
            GROUP BY regime, strategy_id
            ORDER BY n DESC
            """,
            {"sid": strategy_id} if strategy_id else {},
        )

    def decision_quality(self, *, limit: int = 100) -> list[dict]:
        return self._query(
            """
            SELECT trade_id, ticker, strategy_id, closed_at, pnl, pnl_r,
                   decision_quality, randomness_factor, strategy_followed,
                   exit_reason_type, market_regime, confidence,
                   COALESCE(environment,
                            CASE WHEN is_sandbox IS TRUE  THEN 'sandbox'
                                 WHEN is_sandbox IS FALSE THEN 'live' END) AS environment
            FROM trades
            WHERE decision_quality IS NOT NULL AND closed_at IS NOT NULL
            ORDER BY closed_at DESC
            LIMIT :lim
            """,
            {"lim": limit},
        )

    def hypotheses(self, stage: Optional[str] = None) -> list[dict]:
        """Hypothesis lifecycle. Currently zero rows — the API reports that as
        an explicit empty reason rather than shipping an empty dedicated screen."""
        return self._query(
            """
            SELECT hypothesis_id, description, market, stage,
                   conditions->>'strategy_id' AS strategy_id, conditions,
                   total_trades AS sample_size, winning_trades, win_rate,
                   profit_factor, expectancy, confidence,
                   stat_test_result->>'rejection_reason' AS rejection_reason,
                   created_at, promoted_at, rejected_at, updated_at
            FROM hypotheses
            WHERE (:stage IS NULL OR stage = :stage)
            ORDER BY
                CASE stage WHEN 'active' THEN 0 WHEN 'candidate' THEN 1
                           WHEN 'observation' THEN 2 ELSE 3 END,
                total_trades DESC
            """,
            {"stage": stage},
        )

    def hypothesis_stage_counts(self) -> dict[str, int]:
        rows = self._query("SELECT stage, COUNT(*) AS n FROM hypotheses GROUP BY stage")
        return {str(r["stage"]): int(r["n"]) for r in rows}
