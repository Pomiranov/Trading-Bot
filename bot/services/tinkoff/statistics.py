"""
Bot trading statistics computed from the local PostgreSQL trade log.

All fields are Optional — they are set to None when data is insufficient
rather than returning fabricated values.
"""
from __future__ import annotations

import logging
from typing import Optional

from .cache import TTLCache
from .types import BotStatistics

logger = logging.getLogger(__name__)

_stats_cache: TTLCache = TTLCache(ttl_seconds=300)

_MIN_TRADES_FOR_SHARPE = 5


def _sharpe(equities: list[float]) -> Optional[float]:
    if len(equities) < _MIN_TRADES_FOR_SHARPE:
        return None
    returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] != 0
    ]
    if not returns:
        return None
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / max(n - 1, 1)
    std = variance ** 0.5
    return round(mean / std * (252 ** 0.5), 2) if std > 0 else None


def _max_drawdown(equities: list[float]) -> Optional[float]:
    if len(equities) < 2:
        return None
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
    return round(max_dd, 2)


def compute_from_db(engine) -> BotStatistics:
    """
    Query the local trades table and return statistics.

    Never raises — returns a BotStatistics with has_sufficient_data=False
    when the DB is unavailable or the trades table is empty.
    """
    cache_key = "bot_stats"
    hit = _stats_cache.get(cache_key)
    if hit is not None:
        return hit

    result = _compute(engine)
    _stats_cache.set(cache_key, result)
    return result


def _compute(engine) -> BotStatistics:
    from sqlalchemy import text

    _empty = BotStatistics(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        win_rate=None,
        sharpe_ratio=None,
        max_drawdown=None,
        avg_trade_pnl=None,
        total_pnl=0.0,
        has_sufficient_data=False,
    )

    try:
        with engine.connect() as conn:
            agg = conn.execute(text("""
                SELECT
                    COUNT(*)                                              AS total,
                    COUNT(*) FILTER (WHERE pnl > 0)                      AS wins,
                    COUNT(*) FILTER (WHERE pnl <= 0 AND pnl IS NOT NULL) AS losses,
                    COALESCE(SUM(pnl), 0)                                AS total_pnl,
                    AVG(pnl)                                             AS avg_pnl
                FROM trades
                WHERE closed_at IS NOT NULL
                  AND pnl IS NOT NULL
            """)).fetchone()

        if agg is None or (agg[0] or 0) == 0:
            return _empty

        total = int(agg[0])
        wins = int(agg[1] or 0)
        losses = int(agg[2] or 0)
        total_pnl = float(agg[3] or 0)
        avg_pnl = float(agg[4]) if agg[4] is not None else None
        win_rate = round(wins / total * 100, 1) if total > 0 else None

        with engine.connect() as conn:
            eq_rows = conn.execute(text("""
                SELECT 1000000 + SUM(pnl) OVER (ORDER BY closed_at) AS equity
                FROM trades
                WHERE closed_at IS NOT NULL
                  AND pnl IS NOT NULL
                ORDER BY closed_at
            """)).fetchall()

        equities = [float(r[0]) for r in eq_rows]

        return BotStatistics(
            total_trades=total,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=win_rate,
            sharpe_ratio=_sharpe(equities),
            max_drawdown=_max_drawdown(equities),
            avg_trade_pnl=round(avg_pnl, 2) if avg_pnl is not None else None,
            total_pnl=round(total_pnl, 2),
            has_sufficient_data=total >= _MIN_TRADES_FOR_SHARPE,
        )

    except Exception as exc:
        logger.warning("Cannot compute bot statistics: %s", exc)
        return BotStatistics(
            total_trades=None,
            winning_trades=None,
            losing_trades=None,
            win_rate=None,
            sharpe_ratio=None,
            max_drawdown=None,
            avg_trade_pnl=None,
            total_pnl=None,
            has_sufficient_data=False,
        )


def invalidate() -> None:
    _stats_cache.invalidate()
