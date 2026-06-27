"""Extended trading statistics service — computes all metrics from the trades DB."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from services.tinkoff.cache import TTLCache

logger = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(ttl_seconds=300)


@dataclass
class FullStatistics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float]

    pnl_today: Optional[float]
    pnl_yesterday: Optional[float]
    pnl_week: Optional[float]
    pnl_month: Optional[float]
    pnl_quarter: Optional[float]
    pnl_year: Optional[float]
    pnl_all_time: Optional[float]

    roi: Optional[float]
    avg_profit: Optional[float]
    avg_loss: Optional[float]
    profit_factor: Optional[float]
    max_drawdown: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    recovery_factor: Optional[float]

    best_day_pnl: Optional[float]
    best_day_date: Optional[date]
    worst_day_pnl: Optional[float]
    worst_day_date: Optional[date]

    max_single_win: Optional[float]
    max_single_loss: Optional[float]
    avg_hold_hours: Optional[float]

    has_data: bool


_EMPTY = FullStatistics(
    total_trades=0, winning_trades=0, losing_trades=0, win_rate=None,
    pnl_today=None, pnl_yesterday=None, pnl_week=None, pnl_month=None,
    pnl_quarter=None, pnl_year=None, pnl_all_time=None,
    roi=None, avg_profit=None, avg_loss=None, profit_factor=None,
    max_drawdown=None, sharpe_ratio=None, sortino_ratio=None, recovery_factor=None,
    best_day_pnl=None, best_day_date=None, worst_day_pnl=None, worst_day_date=None,
    max_single_win=None, max_single_loss=None, avg_hold_hours=None, has_data=False,
)


def _sharpe(returns: list[float]) -> Optional[float]:
    if len(returns) < 5:
        return None
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / max(n - 1, 1)
    std = math.sqrt(variance)
    return round(mean / std * math.sqrt(252), 2) if std > 0 else None


def _sortino(returns: list[float]) -> Optional[float]:
    if len(returns) < 5:
        return None
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return None
    downside_var = sum(r ** 2 for r in downside) / max(len(downside) - 1, 1)
    downside_std = math.sqrt(downside_var)
    return round(mean / downside_std * math.sqrt(252), 2) if downside_std > 0 else None


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


def compute(engine) -> FullStatistics:
    hit = _cache.get("full_stats")
    if hit is not None:
        return hit
    result = _compute(engine)
    _cache.set("full_stats", result)
    return result


def _compute(engine) -> FullStatistics:
    from sqlalchemy import text

    if engine is None:
        return _EMPTY

    try:
        with engine.connect() as conn:
            agg = conn.execute(text("""
                SELECT
                    COUNT(*)                                                 AS total,
                    COUNT(*) FILTER (WHERE pnl > 0)                         AS wins,
                    COUNT(*) FILTER (WHERE pnl <= 0)                        AS losses,
                    COALESCE(SUM(pnl), 0)                                   AS total_pnl,
                    AVG(pnl)                                                 AS avg_pnl,
                    AVG(pnl) FILTER (WHERE pnl > 0)                         AS avg_profit,
                    AVG(pnl) FILTER (WHERE pnl <= 0)                        AS avg_loss,
                    MAX(pnl)                                                 AS max_win,
                    MIN(pnl)                                                 AS max_loss,
                    AVG(EXTRACT(EPOCH FROM (exit_at - entry_at)) / 3600.0)  AS avg_hold_hours,
                    COALESCE(SUM(pnl) FILTER (WHERE DATE(exit_at) = CURRENT_DATE), 0)              AS pnl_today,
                    COALESCE(SUM(pnl) FILTER (WHERE DATE(exit_at) = CURRENT_DATE - 1), 0)          AS pnl_yesterday,
                    COALESCE(SUM(pnl) FILTER (WHERE exit_at >= NOW() - INTERVAL '7 days'), 0)      AS pnl_week,
                    COALESCE(SUM(pnl) FILTER (WHERE exit_at >= NOW() - INTERVAL '30 days'), 0)     AS pnl_month,
                    COALESCE(SUM(pnl) FILTER (WHERE exit_at >= NOW() - INTERVAL '90 days'), 0)     AS pnl_quarter,
                    COALESCE(SUM(pnl) FILTER (WHERE exit_at >= NOW() - INTERVAL '365 days'), 0)    AS pnl_year
                FROM trades
                WHERE status IN ('CLOSED', 'STOPPED') AND pnl IS NOT NULL AND exit_at IS NOT NULL
            """)).fetchone()

        if agg is None or (agg[0] or 0) == 0:
            return _EMPTY

        total = int(agg[0])
        wins = int(agg[1] or 0)
        losses = int(agg[2] or 0)
        total_pnl = float(agg[3] or 0)
        avg_profit = float(agg[5]) if agg[5] else None
        avg_loss = float(agg[6]) if agg[6] else None
        max_win = float(agg[7]) if agg[7] else None
        max_loss = float(agg[8]) if agg[8] else None
        avg_hold_hours = float(agg[9]) if agg[9] else None

        pnl_today = float(agg[10] or 0)
        pnl_yesterday = float(agg[11] or 0)
        pnl_week = float(agg[12] or 0)
        pnl_month = float(agg[13] or 0)
        pnl_quarter = float(agg[14] or 0)
        pnl_year = float(agg[15] or 0)

        profit_factor: Optional[float] = None
        if avg_loss and avg_loss != 0 and wins > 0:
            gross_profit = avg_profit * wins if avg_profit else 0
            gross_loss = abs(avg_loss) * losses if avg_loss else 0
            if gross_loss > 0:
                profit_factor = round(gross_profit / gross_loss, 2)

        win_rate = round(wins / total * 100, 1) if total > 0 else None

        with engine.connect() as conn:
            eq_rows = conn.execute(text("""
                SELECT 1000000 + SUM(pnl) OVER (ORDER BY exit_at) AS equity
                FROM trades
                WHERE status IN ('CLOSED', 'STOPPED') AND pnl IS NOT NULL AND exit_at IS NOT NULL
                ORDER BY exit_at
            """)).fetchall()

        equities = [float(r[0]) for r in eq_rows]

        returns: list[float] = []
        for i in range(1, len(equities)):
            if equities[i - 1] != 0:
                returns.append((equities[i] - equities[i - 1]) / equities[i - 1])

        max_dd = _max_drawdown(equities)
        sharpe = _sharpe(returns)
        sortino = _sortino(returns)

        recovery_factor: Optional[float] = None
        if max_dd and max_dd != 0 and total_pnl:
            recovery_factor = round(total_pnl / abs(max_dd), 2)

        roi: Optional[float] = round(total_pnl / 1_000_000 * 100, 2) if total_pnl else None

        with engine.connect() as conn:
            daily_rows = conn.execute(text("""
                SELECT DATE(exit_at) AS day, SUM(pnl) AS daily_pnl
                FROM trades
                WHERE status IN ('CLOSED', 'STOPPED') AND pnl IS NOT NULL AND exit_at IS NOT NULL
                GROUP BY DATE(exit_at)
                ORDER BY daily_pnl DESC
                LIMIT 1
            """)).fetchall()
            daily_asc = conn.execute(text("""
                SELECT DATE(exit_at) AS day, SUM(pnl) AS daily_pnl
                FROM trades
                WHERE status IN ('CLOSED', 'STOPPED') AND pnl IS NOT NULL AND exit_at IS NOT NULL
                GROUP BY DATE(exit_at)
                ORDER BY daily_pnl ASC
                LIMIT 1
            """)).fetchall()

        best_day_pnl = float(daily_rows[0][1]) if daily_rows else None
        best_day_date = daily_rows[0][0] if daily_rows else None
        worst_day_pnl = float(daily_asc[0][1]) if daily_asc else None
        worst_day_date = daily_asc[0][0] if daily_asc else None

        return FullStatistics(
            total_trades=total,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=win_rate,
            pnl_today=round(pnl_today, 2),
            pnl_yesterday=round(pnl_yesterday, 2),
            pnl_week=round(pnl_week, 2),
            pnl_month=round(pnl_month, 2),
            pnl_quarter=round(pnl_quarter, 2),
            pnl_year=round(pnl_year, 2),
            pnl_all_time=round(total_pnl, 2),
            roi=roi,
            avg_profit=round(avg_profit, 2) if avg_profit else None,
            avg_loss=round(avg_loss, 2) if avg_loss else None,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            recovery_factor=recovery_factor,
            best_day_pnl=round(best_day_pnl, 2) if best_day_pnl else None,
            best_day_date=best_day_date,
            worst_day_pnl=round(worst_day_pnl, 2) if worst_day_pnl else None,
            worst_day_date=worst_day_date,
            max_single_win=round(max_win, 2) if max_win else None,
            max_single_loss=round(max_loss, 2) if max_loss else None,
            avg_hold_hours=round(avg_hold_hours, 1) if avg_hold_hours else None,
            has_data=True,
        )

    except Exception as exc:
        logger.warning("FullStatistics computation failed: %s", exc)
        return _EMPTY


def invalidate() -> None:
    _cache.invalidate()
