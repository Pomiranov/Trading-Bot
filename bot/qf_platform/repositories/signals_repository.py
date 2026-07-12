"""Trading signals persistence."""

from __future__ import annotations

import json
from typing import Optional

from qf_platform.repositories.base import BaseRepository


class SignalsRepository(BaseRepository):
    def insert(self, data: dict) -> int:
        result = self._execute(
            """
            INSERT INTO trading_signals
                (asset, exchange, timeframe, signal_type, entry_price, stop_loss,
                 take_profit_1, take_profit_2, take_profit_3, risk_reward,
                 probability_pct, status, source, asset_class, metadata)
            VALUES
                (:asset, :exchange, :tf, :stype, :entry, :sl,
                 :tp1, :tp2, :tp3, :rr, :prob, :status, :source, :aclass, :meta)
            RETURNING id
            """,
            {
                "asset": data["asset"],
                "exchange": data["exchange"],
                "tf": data.get("timeframe", "1d"),
                "stype": data["signal_type"],
                "entry": data.get("entry_price"),
                "sl": data.get("stop_loss"),
                "tp1": data.get("take_profit_1"),
                "tp2": data.get("take_profit_2"),
                "tp3": data.get("take_profit_3"),
                "rr": data.get("risk_reward"),
                "prob": data.get("probability_pct", 50),
                "status": data.get("status", "new"),
                "source": data.get("source", "indicators"),
                "aclass": data.get("asset_class", "stocks"),
                "meta": json.dumps(data.get("metadata") or {}),
            },
        )
        return int(result.fetchone()[0])

    def list_signals(
        self,
        exchange: Optional[str] = None,
        asset_class: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["1=1"]
        params: dict = {"limit": limit}
        if exchange:
            clauses.append("exchange = :exchange")
            params["exchange"] = exchange
        if asset_class:
            clauses.append("asset_class = :aclass")
            params["aclass"] = asset_class
        if status:
            clauses.append("status = :status")
            params["status"] = status
        where = " AND ".join(clauses)
        return self._query(
            f"""
            SELECT * FROM trading_signals
            WHERE {where}
            ORDER BY generated_at DESC LIMIT :limit
            """,
            params,
        )

    def update_status(self, signal_id: int, status: str) -> None:
        self._execute(
            "UPDATE trading_signals SET status = :status WHERE id = :id",
            {"id": signal_id, "status": status},
        )

    def count_by_status(self, status: str = "new") -> int:
        rows = self._query(
            "SELECT COUNT(*) AS cnt FROM trading_signals WHERE status = :status",
            {"status": status},
        )
        return int(rows[0]["cnt"]) if rows else 0