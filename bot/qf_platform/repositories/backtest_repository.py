"""Backtest run persistence."""

from __future__ import annotations

import json

from costs import COMMISSION_PCT
from qf_platform.repositories.base import BaseRepository


class BacktestRepository(BaseRepository):
    def save_run(self, params: dict, results: dict) -> int:
        result = self._execute(
            """
            INSERT INTO backtest_runs
                (strategy, exchange, ticker, period_start, period_end,
                 initial_capital, risk_pct, commission_pct, slippage_pct, leverage, results)
            VALUES
                (:strategy, :exchange, :ticker, :pstart, :pend,
                 :capital, :risk, :commission, :slippage, :leverage, :results)
            RETURNING id
            """,
            {
                "strategy": params.get("strategy", "rules_engine"),
                "exchange": params.get("exchange", "moex"),
                "ticker": params.get("ticker", "SBER"),
                "pstart": params.get("period_start"),
                "pend": params.get("period_end"),
                "capital": params.get("initial_capital", 1_000_000),
                "risk": params.get("risk_pct", 0.05),
                "commission": params.get("commission_pct", COMMISSION_PCT),
                "slippage": params.get("slippage_pct", 0.0001),
                "leverage": params.get("leverage", 1),
                "results": json.dumps(results),
            },
        )
        return int(result.fetchone()[0])

    def get_run(self, run_id: int) -> dict | None:
        rows = self._query("SELECT * FROM backtest_runs WHERE id = :id", {"id": run_id})
        return rows[0] if rows else None

    def list_runs(self, limit: int = 20) -> list[dict]:
        return self._query(
            "SELECT id, strategy, exchange, ticker, initial_capital, created_at FROM backtest_runs ORDER BY created_at DESC LIMIT :limit",
            {"limit": limit},
        )