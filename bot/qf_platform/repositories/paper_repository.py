"""Paper trading account persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from qf_platform.repositories.base import BaseRepository

DEFAULT_BALANCES = {
    "usdt": (100_000.0, "USDT"),
    "rub": (10_000_000.0, "RUB"),
}


class PaperRepository(BaseRepository):
    def get_or_create_account(self, user_id: str = "default", mode: str = "rub") -> dict:
        rows = self._query(
            "SELECT * FROM paper_accounts WHERE user_id = :uid AND mode = :mode",
            {"uid": user_id, "mode": mode},
        )
        if rows:
            return rows[0]
        initial, currency = DEFAULT_BALANCES.get(mode, DEFAULT_BALANCES["rub"])
        self._execute(
            """
            INSERT INTO paper_accounts
                (user_id, mode, initial_balance, balance, available_balance, currency)
            VALUES (:uid, :mode, :initial, :initial, :initial, :currency)
            """,
            {"uid": user_id, "mode": mode, "initial": initial, "currency": currency},
        )
        return self.get_or_create_account(user_id, mode)

    def update_account_balances(
        self,
        account_id: int,
        balance: float,
        available: float,
        margin_used: float,
    ) -> None:
        self._execute(
            """
            UPDATE paper_accounts
            SET balance = :balance, available_balance = :available,
                margin_used = :margin, updated_at = NOW()
            WHERE id = :id
            """,
            {"id": account_id, "balance": balance, "available": available, "margin": margin_used},
        )

    def list_positions(self, account_id: int) -> list[dict]:
        return self._query(
            "SELECT * FROM paper_positions WHERE account_id = :aid ORDER BY opened_at DESC",
            {"aid": account_id},
        )

    def get_position(self, position_id: int) -> Optional[dict]:
        rows = self._query("SELECT * FROM paper_positions WHERE id = :id", {"id": position_id})
        return rows[0] if rows else None

    def insert_position(self, account_id: int, data: dict) -> int:
        result = self._execute(
            """
            INSERT INTO paper_positions
                (account_id, ticker, exchange, direction, quantity, entry_price,
                 stop_loss, take_profit, unrealized_pnl)
            VALUES
                (:aid, :ticker, :exchange, :direction, :qty, :entry,
                 :sl, :tp, 0)
            RETURNING id
            """,
            {
                "aid": account_id,
                "ticker": data["ticker"],
                "exchange": data.get("exchange", "paper"),
                "direction": data["direction"],
                "qty": data["quantity"],
                "entry": data["entry_price"],
                "sl": data.get("stop_loss"),
                "tp": data.get("take_profit"),
            },
        )
        return int(result.fetchone()[0])

    def update_position_pnl(self, position_id: int, unrealized_pnl: float) -> None:
        self._execute(
            "UPDATE paper_positions SET unrealized_pnl = :pnl WHERE id = :id",
            {"id": position_id, "pnl": unrealized_pnl},
        )

    def delete_position(self, position_id: int) -> None:
        self._execute("DELETE FROM paper_positions WHERE id = :id", {"id": position_id})

    def insert_trade(self, account_id: int, data: dict) -> int:
        result = self._execute(
            """
            INSERT INTO paper_trades
                (account_id, position_id, ticker, exchange, direction,
                 entry_price, exit_price, quantity, pnl, pnl_pct, opened_at)
            VALUES
                (:aid, :pid, :ticker, :exchange, :direction,
                 :entry, :exit, :qty, :pnl, :pnl_pct, :opened)
            RETURNING id
            """,
            {
                "aid": account_id,
                "pid": data.get("position_id"),
                "ticker": data["ticker"],
                "exchange": data.get("exchange", "paper"),
                "direction": data["direction"],
                "entry": data["entry_price"],
                "exit": data["exit_price"],
                "qty": data["quantity"],
                "pnl": data["pnl"],
                "pnl_pct": data["pnl_pct"],
                "opened": data.get("opened_at", datetime.utcnow()),
            },
        )
        return int(result.fetchone()[0])

    def list_trades(self, account_id: int, limit: int = 100) -> list[dict]:
        return self._query(
            """
            SELECT * FROM paper_trades
            WHERE account_id = :aid
            ORDER BY closed_at DESC LIMIT :limit
            """,
            {"aid": account_id, "limit": limit},
        )

    def pnl_periods(self, account_id: int) -> dict:
        rows = self._query(
            """
            SELECT
                COALESCE(SUM(pnl) FILTER (WHERE closed_at >= CURRENT_DATE), 0) AS pnl_day,
                COALESCE(SUM(pnl) FILTER (WHERE closed_at >= CURRENT_DATE - INTERVAL '7 days'), 0) AS pnl_week,
                COALESCE(SUM(pnl) FILTER (WHERE closed_at >= CURRENT_DATE - INTERVAL '30 days'), 0) AS pnl_month,
                COALESCE(SUM(pnl), 0) AS realized_pnl,
                COUNT(*) AS closed_count
            FROM paper_trades WHERE account_id = :aid
            """,
            {"aid": account_id},
        )
        return rows[0] if rows else {}

    def record_equity_snapshot(self, account_id: int, source: str, equity: float) -> None:
        self._execute(
            "INSERT INTO equity_snapshots (account_id, source, equity) VALUES (:aid, :src, :eq)",
            {"aid": account_id, "src": source, "eq": equity},
        )

    def equity_history(self, account_id: int, limit: int = 90) -> list[dict]:
        return self._query(
            """
            SELECT snapshot_at AS ts, equity
            FROM equity_snapshots
            WHERE account_id = :aid
            ORDER BY snapshot_at DESC LIMIT :limit
            """,
            {"aid": account_id, "limit": limit},
        )