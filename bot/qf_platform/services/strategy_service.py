"""Strategy board — the strategy is the object, learning is its evidence.

Renamed from "Learning" because the entity an operator reasons about is a
strategy. Four rules the audit makes binding, enforced here rather than trusted
to each caller:

1. Confidence renders only as ``0,61 · выборка 12``. Both fields always travel
   together and the client has no code path that draws one without the other.
2. Below n=30 the strategy is marked immature and **excluded from rankings**.
3. Win rate carries its numerator and denominator, so «н/д (0 сделок)» and
   «0,0 % (0 из 14)» cannot render identically.
4. Lifecycle state is *derived*, and the derivation is declared. There is no
   ``frozen`` column, so «Заморожена» is never invented — a strategy that has not
   traded is a ``candidate``, and one that stopped is ``dormant``.
"""

from __future__ import annotations

import logging
from typing import Optional

from qf_platform.contracts import (
    EmptyReason,
    Freshness,
    MIN_SAMPLE_FOR_RANKING,
    Units,
    age_seconds,
    is_mature_sample,
    safe_float,
    to_display,
)
from qf_platform.environment import Environment
from qf_platform.repositories.strategies_repository import StrategiesRepository, StrategyState

logger = logging.getLogger(__name__)

STATE_LABELS = {
    StrategyState.ACTIVE: "Активна",
    StrategyState.CANDIDATE: "Кандидат",
    StrategyState.DORMANT: "Не торговала",
    StrategyState.RETIRED: "Выведена",
    StrategyState.UNKNOWN: "Состояние неизвестно",
}

#: Silence beyond this is "dormant" rather than "active".
DORMANT_AFTER_SECONDS = 14 * 86400

BELIEF_STALE_AFTER_SECONDS = 24 * 3600


class StrategyService:
    def __init__(self, engine):
        self._repo = StrategiesRepository(engine)

    def _derive_state(self, row: dict) -> tuple[str, Optional[str]]:
        """`(state, reason)` — and the reason names the evidence used."""
        total = int(row.get("total_trades") or 0)
        observed = int(row.get("observed_trades") or 0)
        last_trade = row.get("last_trade_at") or row.get("last_observed_at")
        idle = age_seconds(last_trade) if last_trade else None

        if total == 0 and observed == 0:
            return StrategyState.CANDIDATE, "Ни одной закрытой сделки."
        if idle is not None and idle > DORMANT_AFTER_SECONDS:
            return StrategyState.DORMANT, f"Последняя сделка {idle // 86400} дн назад."
        if idle is None:
            return StrategyState.UNKNOWN, "Нет отметки времени последней сделки."
        return StrategyState.ACTIVE, None

    def board(self, *, environment: Optional[Environment] = None) -> dict:
        try:
            rows = self._repo.list_strategies()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Strategy board query failed: %s", exc)
            raise

        strategies = []
        newest_update = None
        for row in rows:
            updated = row.get("updated_at")
            if updated and (newest_update is None or updated > newest_update):
                newest_update = updated

            total = int(row.get("total_trades") or 0)
            wins = int(row.get("winning_trades") or 0)
            losses = int(row.get("losing_trades") or 0)
            observed = int(row.get("observed_trades") or 0)
            confidence = safe_float(row.get("confidence"))
            # belief_system stores win_rate as a fraction.
            wr_fraction = safe_float(row.get("win_rate"))
            state, state_reason = self._derive_state(row)
            mature = is_mature_sample(total)

            environments = [
                env for env in (row.get("environments") or []) if env
            ]

            strategies.append({
                "strategy_id": row["strategy_id"],
                "name": row.get("strategy_name") or row["strategy_id"],
                "market": row.get("market"),
                "description": row.get("description"),

                "state": state,
                "state_label": STATE_LABELS[state],
                "state_reason": state_reason,
                "state_basis": "выведено из total_trades и last_trade_at (колонки frozen нет)",

                # Confidence and its sample size, inseparable.
                "confidence": None if confidence is None else round(confidence, 2),
                "sample_size": total,
                "confidence_is_mature": mature,
                "min_sample_for_ranking": MIN_SAMPLE_FOR_RANKING,
                "confidence_note": None if mature else "мало данных",

                "win_rate_pct": None if (wr_fraction is None or total == 0)
                                else round(wr_fraction * 100.0, 1),
                "wins": wins,
                "losses": losses,
                "win_rate_n": total,

                "profit_factor": _round(row.get("profit_factor"), 2),
                "expectancy": _round(row.get("expectancy"), 4),
                "sharpe_ratio": _round(row.get("sharpe_ratio"), 2) if mature else None,
                "avg_win_r": _round(row.get("avg_win_r"), 2),
                "avg_loss_r": _round(row.get("avg_loss_r"), 2),
                "max_consecutive_losses": int(row.get("max_consecutive_losses") or 0),

                "best_regime": row.get("best_regime"),
                "best_timeframe": row.get("best_timeframe"),

                "updated_at": to_display(updated),
                "updated_age_seconds": age_seconds(updated) if updated else None,
                "last_trade_at": to_display(row.get("last_trade_at")),
                "observed_trades": observed,
                "observed_pnl": _round(row.get("observed_pnl"), 2),
                # A belief computed over environments that were merged is not a
                # usable statistic. Reporting the set lets the UI flag it.
                "environments": environments,
                "environments_mixed": len([e for e in environments if e != "unknown"]) > 1,
                # Ranked strategies exclude immature samples entirely (§16).
                "ranked": mature,
            })

        # Rank only the mature ones; the rest keep rank None rather than being
        # sorted to the bottom of a list they should not be in.
        ranked = sorted(
            [s for s in strategies if s["ranked"]],
            key=lambda s: (-(s["confidence"] or 0), -(s["sample_size"] or 0)),
        )
        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
        for item in strategies:
            item.setdefault("rank", None)

        strategies.sort(
            key=lambda s: (s["rank"] is None, s["rank"] or 0, -(s["sample_size"] or 0))
        )

        return {
            "strategies": strategies,
            "count": len(strategies),
            "ranked_count": len(ranked),
            "immature_count": len(strategies) - len(ranked),
            "empty_reason": None if strategies else EmptyReason.STRATEGY_NEVER_RAN,
            "_source_as_of": newest_update,
            "units": {
                "confidence": Units.RATIO,
                "win_rate_pct": Units.PERCENT,
                "profit_factor": Units.RATIO,
                "expectancy": Units.R_MULTIPLE,
            },
        }

    @staticmethod
    def freshness(payload: dict) -> Freshness:
        return Freshness(
            source_as_of=payload.get("_source_as_of"),
            source="belief_system",
            stale_after_seconds=BELIEF_STALE_AFTER_SECONDS,
        )

    def detail(self, strategy_id: str) -> Optional[dict]:
        row = self._repo.get_strategy(strategy_id)
        if row is None:
            return None
        history = self._repo.confidence_history(strategy_id)
        regimes = self._repo.regime_breakdown(strategy_id)
        total = int(row.get("total_trades") or 0)

        return {
            "strategy_id": strategy_id,
            "name": row.get("strategy_name") or strategy_id,
            "confidence": _round(row.get("confidence"), 2),
            "sample_size": total,
            "confidence_is_mature": is_mature_sample(total),
            "history": [
                {
                    "ts": to_display(item["ts"]),
                    "value": _round(item.get("value"), 3),
                    "trade_id": item.get("trade_id"),
                    "pnl": _round(item.get("pnl"), 2),
                }
                for item in history
            ],
            # A step chart, not a smooth curve: confidence updates discretely,
            # and interpolating between updates would imply values it never had.
            "history_shape": "step",
            "history_source": "trades.confidence на момент закрытия сделки",
            "history_gap": (
                "Таблицы belief_history нет — история восстановлена по сделкам, "
                "поэтому пересчёты без сделок в ней не видны."
            ),
            "regimes": [
                {
                    "regime": item["regime"],
                    "n": int(item["n"]),
                    "wins": int(item["wins"] or 0),
                    "total_pnl": _round(item.get("total_pnl"), 2),
                    "avg_pnl": _round(item.get("avg_pnl"), 2),
                    "mature": is_mature_sample(int(item["n"])),
                }
                for item in regimes
            ],
        }

    def decision_quality(self, *, limit: int = 100) -> dict:
        rows = self._repo.decision_quality(limit=limit)
        values = [safe_float(r.get("decision_quality")) for r in rows]
        values = [v for v in values if v is not None]
        return {
            "decisions": [
                {
                    "trade_id": row.get("trade_id"),
                    "ticker": row.get("ticker"),
                    "strategy_id": row.get("strategy_id"),
                    "closed_at": to_display(row.get("closed_at")),
                    "pnl": _round(row.get("pnl"), 2),
                    "pnl_r": _round(row.get("pnl_r"), 2),
                    "decision_quality": _round(row.get("decision_quality"), 3),
                    "randomness_factor": _round(row.get("randomness_factor"), 3),
                    "strategy_followed": row.get("strategy_followed"),
                    "exit_reason_type": row.get("exit_reason_type"),
                    "market_regime": row.get("market_regime"),
                    "environment": row.get("environment") or Environment.UNKNOWN.value,
                }
                for row in rows
            ],
            "n": len(values),
            "avg_quality": round(sum(values) / len(values), 3) if values else None,
            # A histogram of two points is not a distribution.
            "distribution_shown": len(values) >= 20,
            "distribution_note": (
                None if len(values) >= 20
                else f"Выборка {len(values)} — распределение не строится."
            ),
            "empty_reason": None if rows else EmptyReason.NO_TRADES_EVER,
        }

    def hypotheses(self, *, stage: Optional[str] = None) -> dict:
        rows = self._repo.hypotheses(stage)
        counts = self._repo.hypothesis_stage_counts()
        return {
            "hypotheses": [
                {
                    "id": str(row.get("hypothesis_id")),
                    "description": row.get("description"),
                    "market": row.get("market"),
                    "stage": row.get("stage"),
                    "strategy_id": row.get("strategy_id"),
                    "sample_size": int(row.get("sample_size") or 0),
                    "win_rate_pct": (
                        None if safe_float(row.get("win_rate")) is None
                        else round(safe_float(row["win_rate"]) * 100.0, 1)
                    ),
                    "profit_factor": _round(row.get("profit_factor"), 2),
                    "confidence": _round(row.get("confidence"), 2),
                    "rejection_reason": row.get("rejection_reason"),
                    "created_at": to_display(row.get("created_at")),
                    "promoted_at": to_display(row.get("promoted_at")),
                    "rejected_at": to_display(row.get("rejected_at")),
                }
                for row in rows
            ],
            "stage_counts": counts,
            "total": sum(counts.values()),
            # Shown inside the Strategies screen rather than as a dedicated
            # screen: a section for an empty table is a promise the product
            # cannot keep.
            "empty_reason": None if rows else EmptyReason.NO_EVENTS,
            "note": (
                None if rows
                else "Гипотез пока нет — раздел появится, когда движок обучения их создаст."
            ),
        }


def _round(value, digits: int):
    number = safe_float(value)
    return None if number is None else round(number, digits)
