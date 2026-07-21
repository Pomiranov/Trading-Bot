"""Analytics service — equity curve, monthly/daily PnL, trade statistics."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Engine

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, engine: Engine):
        self._engine = engine

    # ------------------------------------------------------------------
    # Internal query helper
    # ------------------------------------------------------------------

    def _query(self, sql: str, params: dict | None = None) -> list[dict]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            cols = list(result.keys())
            return [dict(zip(cols, row)) for row in result.fetchall()]

    def _get_account_id(self, mode: str = "rub") -> int | None:
        rows = self._query(
            "SELECT id FROM paper_accounts WHERE user_id = 'default' AND mode = :mode",
            {"mode": mode},
        )
        return int(rows[0]["id"]) if rows else None

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    def equity_curve(self, limit: int = 200) -> list[dict]:
        """Return list of {ts, equity} snapshots ordered by time ascending."""
        aid = self._get_account_id()
        if aid is None:
            return []
        rows = self._query(
            """
            SELECT snapshot_at AS ts, equity
            FROM equity_snapshots
            WHERE account_id = :aid
            ORDER BY snapshot_at DESC
            LIMIT :lim
            """,
            {"aid": aid, "lim": limit},
        )
        result = [
            {"ts": str(r["ts"]), "equity": float(r["equity"])}
            for r in reversed(rows)
        ]
        return result

    # ------------------------------------------------------------------
    # Monthly PnL
    # ------------------------------------------------------------------

    def monthly_pnl(self) -> list[dict]:
        """Return monthly PnL grouped by month."""
        aid = self._get_account_id()
        if aid is None:
            return []
        rows = self._query(
            """
            SELECT
                TO_CHAR(closed_at, 'YYYY-MM') AS month,
                SUM(pnl) AS pnl,
                COUNT(*) AS trades,
                COUNT(*) FILTER (WHERE pnl > 0) AS wins
            FROM paper_trades
            WHERE account_id = :aid
            GROUP BY month
            ORDER BY month DESC
            """,
            {"aid": aid},
        )
        result = []
        for r in rows:
            trades = int(r["trades"]) if r["trades"] else 0
            wins = int(r["wins"]) if r["wins"] else 0
            result.append({
                "month": str(r["month"]),
                "pnl": round(float(r["pnl"]) if r["pnl"] else 0, 2),
                "trades": trades,
                "wins": wins,
                "win_rate": round(wins / trades * 100, 2) if trades else 0.0,
            })
        return result

    # ------------------------------------------------------------------
    # Daily PnL
    # ------------------------------------------------------------------

    def daily_pnl(self, days: int = 30) -> list[dict]:
        """Return daily PnL for the last N days."""
        aid = self._get_account_id()
        if aid is None:
            return []
        rows = self._query(
            """
            SELECT
                DATE(closed_at) AS day,
                SUM(pnl) AS pnl,
                COUNT(*) AS trades
            FROM paper_trades
            WHERE account_id = :aid
              AND closed_at >= NOW() - INTERVAL '1 day' * :days
            GROUP BY day
            ORDER BY day DESC
            """,
            {"aid": aid, "days": days},
        )
        return [
            {
                "day": str(r["day"]),
                "pnl": round(float(r["pnl"]) if r["pnl"] else 0, 2),
                "trades": int(r["trades"]) if r["trades"] else 0,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Trade stats
    # ------------------------------------------------------------------

    def trade_stats(self) -> dict:
        """Full trading statistics."""
        aid = self._get_account_id()
        if aid is None:
            return _empty_stats()

        trades = self._query(
            "SELECT pnl, pnl_pct, opened_at, closed_at FROM paper_trades WHERE account_id = :aid",
            {"aid": aid},
        )
        if not trades:
            return _empty_stats()

        pnls = [float(t["pnl"]) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        total_trades = len(pnls)
        win_rate = len(wins) / total_trades if total_trades else 0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss else float("inf")

        total_pnl = sum(pnls)

        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        # Average hold time in hours
        hold_times = []
        for t in trades:
            try:
                opened = t["opened_at"]
                closed = t["closed_at"]
                if opened and closed:
                    if hasattr(opened, "timestamp"):
                        delta = (closed - opened).total_seconds() / 3600
                    else:
                        delta = 0
                    hold_times.append(delta)
            except Exception:
                pass
        avg_hold_time = sum(hold_times) / len(hold_times) if hold_times else 0.0

        returns = self._daily_equity_returns(aid)
        sharpe = self._sharpe_from_returns(returns)
        sortino = self._sortino_from_returns(returns)
        max_dd = self._compute_max_drawdown(aid)

        # ROI
        account_rows = self._query(
            "SELECT initial_balance, balance FROM paper_accounts WHERE id = :aid",
            {"aid": aid},
        )
        roi_pct = 0.0
        if account_rows:
            initial = float(account_rows[0]["initial_balance"])
            balance = float(account_rows[0]["balance"])
            roi_pct = (balance - initial) / initial * 100 if initial else 0.0

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd, 4),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_hold_time_hours": round(avg_hold_time, 2),
            "roi_pct": round(roi_pct, 4),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
        }

    def _daily_equity_returns(self, account_id: int) -> list[float]:
        """Daily equity returns from equity_snapshots (shared by Sharpe/Sortino)."""
        rows = self._query(
            """
            SELECT DATE(snapshot_at) AS day, AVG(equity) AS eq
            FROM equity_snapshots
            WHERE account_id = :aid
            GROUP BY day
            ORDER BY day ASC
            """,
            {"aid": account_id},
        )
        if len(rows) < 2:
            return []
        equities = [float(r["eq"]) for r in rows]
        return [(equities[i] - equities[i - 1]) / equities[i - 1] for i in range(1, len(equities))]

    def _sharpe_from_returns(self, returns: list[float]) -> float:
        if not returns:
            return 0.0
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std_r = math.sqrt(variance)
        if std_r == 0:
            return 0.0
        return (mean_r / std_r) * math.sqrt(252)

    def _sortino_from_returns(self, returns: list[float]) -> float:
        if not returns:
            return 0.0
        mean_r = sum(returns) / len(returns)
        downside = [r for r in returns if r < 0]
        if not downside:
            return float("inf")
        downside_var = sum(r ** 2 for r in downside) / len(downside)
        downside_std = math.sqrt(downside_var)
        if downside_std == 0:
            return 0.0
        return (mean_r / downside_std) * math.sqrt(252)

    def _compute_sharpe(self, account_id: int) -> float:
        return self._sharpe_from_returns(self._daily_equity_returns(account_id))

    def _compute_sortino(self, account_id: int) -> float:
        return self._sortino_from_returns(self._daily_equity_returns(account_id))

    def _compute_max_drawdown(self, account_id: int) -> float:
        """Return max drawdown as a fraction (e.g. 0.15 = 15%)."""
        rows = self._query(
            """
            SELECT equity FROM equity_snapshots
            WHERE account_id = :aid
            ORDER BY snapshot_at ASC
            """,
            {"aid": account_id},
        )
        if not rows:
            return 0.0
        equities = [float(r["equity"]) for r in rows]
        peak = equities[0]
        max_dd = 0.0
        for eq in equities:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    # ------------------------------------------------------------------
    # Best / worst trades
    # ------------------------------------------------------------------

    def best_worst_trades(self, n: int = 5) -> dict:
        """Return N best and N worst closed trades by PnL."""
        aid = self._get_account_id()
        if aid is None:
            return {"best": [], "worst": []}

        best = self._query(
            """
            SELECT ticker, direction, entry_price, exit_price, quantity, pnl, pnl_pct, closed_at
            FROM paper_trades WHERE account_id = :aid
            ORDER BY pnl DESC LIMIT :n
            """,
            {"aid": aid, "n": n},
        )
        worst = self._query(
            """
            SELECT ticker, direction, entry_price, exit_price, quantity, pnl, pnl_pct, closed_at
            FROM paper_trades WHERE account_id = :aid
            ORDER BY pnl ASC LIMIT :n
            """,
            {"aid": aid, "n": n},
        )

        def _fmt(rows):
            return [
                {
                    "ticker": r["ticker"],
                    "direction": r["direction"],
                    "entry_price": float(r["entry_price"]),
                    "exit_price": float(r["exit_price"]),
                    "quantity": float(r["quantity"]),
                    "pnl": round(float(r["pnl"]), 2),
                    "pnl_pct": round(float(r["pnl_pct"]) * 100, 4),
                    "closed_at": str(r["closed_at"]),
                }
                for r in rows
            ]

        return {"best": _fmt(best), "worst": _fmt(worst)}

    # ------------------------------------------------------------------
    # Strategy breakdown
    # ------------------------------------------------------------------

    def strategy_breakdown(self) -> list[dict]:
        """PnL grouped by signal source where position was linked to a signal."""
        aid = self._get_account_id()
        if aid is None:
            return []
        try:
            rows = self._query(
                """
                SELECT
                    COALESCE(ts.source, 'manual') AS source,
                    COUNT(pt.id) AS trades,
                    SUM(pt.pnl) AS total_pnl,
                    COUNT(pt.id) FILTER (WHERE pt.pnl > 0) AS wins
                FROM paper_trades pt
                LEFT JOIN paper_positions pp ON pt.position_id = pp.id
                LEFT JOIN trading_signals ts ON pp.signal_id = ts.id
                WHERE pt.account_id = :aid
                GROUP BY source
                ORDER BY total_pnl DESC
                """,
                {"aid": aid},
            )
            return [
                {
                    "source": r["source"] or "manual",
                    "trades": int(r["trades"]) if r["trades"] else 0,
                    "total_pnl": round(float(r["total_pnl"]) if r["total_pnl"] else 0, 2),
                    "wins": int(r["wins"]) if r["wins"] else 0,
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("strategy_breakdown error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def full_report(self) -> dict:
        """Combine all analytics into a single response."""
        return {
            "stats": self.trade_stats(),
            "equity_curve": self.equity_curve(limit=200),
            "monthly_pnl": self.monthly_pnl(),
            "daily_pnl": self.daily_pnl(days=30),
            "best_worst": self.best_worst_trades(n=5),
            "strategy_breakdown": self.strategy_breakdown(),
        }


def _empty_stats() -> dict:
    return {
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": None,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown": 0.0,
        "total_pnl": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "avg_hold_time_hours": 0.0,
        "roi_pct": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "winning_trades": 0,
        "losing_trades": 0,
    }
