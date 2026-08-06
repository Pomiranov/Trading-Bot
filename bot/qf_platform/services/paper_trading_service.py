"""Paper Trading Engine — virtual account with real market prices."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import Engine

from qf_platform.repositories.paper_repository import PaperRepository

logger = logging.getLogger(__name__)

COMMISSION_PCT = 0.0003   # 0.03% per side (must match engine/paper_engine.py)
SLIPPAGE_PCT   = 0.0001   # 0.01% slippage


class PaperTradingService:
    def __init__(self, engine: Engine):
        self._repo = PaperRepository(engine)

    def get_account(self, mode: str = "rub") -> dict:
        return self._repo.get_or_create_account(mode=mode)

    def _get_market_price(self, ticker: str, engine: Engine) -> Optional[float]:
        rows = self._repo._query(
            """
            SELECT close FROM candles
            WHERE ticker = :ticker AND timeframe = '1d'
            ORDER BY time DESC LIMIT 1
            """,
            {"ticker": ticker.upper()},
        )
        if rows:
            return float(rows[0]["close"])
        return None

    def compute_positions(self, account_id: int) -> tuple[list[dict], dict]:
        """Read-only valuation. Returns `(positions, account_totals)`.

        This is the half of the old ``refresh_positions`` that a GET is allowed to
        do. The other half — updating position PnL, updating the account and
        inserting an ``equity_snapshots`` row — sat on the path of four GET
        endpoints and wrote 6–27 rows a minute purely because a tab was open. That
        produced 16 123 snapshots holding 44 distinct values, and the equity chart
        then read its own polling frequency back as a time axis.

        One deliberate behaviour change: when there is no quote, ``current_price``
        is ``None`` and ``unrealized_pnl`` is ``None``. The old code substituted the
        entry price, which yields a measured-looking 0,00 ₽ that is
        indistinguishable from a genuinely flat position.
        """
        positions = self._repo.list_positions(account_id)
        total_unrealized = 0.0
        margin_used = 0.0
        priced = 0

        for pos in positions:
            price = self._get_market_price(pos["ticker"], self._repo._engine)
            qty = float(pos["quantity"])
            entry = float(pos["entry_price"])
            direction = (pos["direction"] or "long").lower()

            if price is None:
                pos["current_price"] = None
                pos["unrealized_pnl"] = None
                pos["pnl_pct"] = None
            else:
                unrealized = (entry - price) * qty if direction == "short" else (price - entry) * qty
                pos["current_price"] = price
                pos["unrealized_pnl"] = unrealized
                pos["pnl_pct"] = round(unrealized / (entry * qty) * 100, 4) if entry * qty else 0
                total_unrealized += unrealized
                priced += 1
            margin_used += entry * qty

        rows = self._repo._query(
            "SELECT * FROM paper_accounts WHERE id = :id", {"id": account_id}
        )
        account = rows[0] if rows else {}
        initial = float(account.get("initial_balance") or 0)
        realized = float(self._repo.pnl_periods(account_id).get("realized_pnl") or 0)

        return positions, {
            "initial_balance": initial,
            "realized_pnl": realized,
            "unrealized_pnl": total_unrealized,
            "balance": initial + realized + total_unrealized,
            "available_balance": float(account.get("available_balance") or 0),
            "margin_used": margin_used,
            "priced_positions": priced,
            "unpriced_positions": len(positions) - priced,
        }

    def refresh_positions(self, account_id: int, *, record_snapshot: bool = True) -> list[dict]:
        """Valuation **plus** persistence. Engine-only.

        Never call this from a request handler. ``record_snapshot`` exists so the
        engine can update state on a monitor tick without adding a snapshot on
        every one — equity snapshots belong on their own cadence.
        """
        positions, totals = self.compute_positions(account_id)
        for pos in positions:
            if pos.get("unrealized_pnl") is not None:
                self._repo.update_position_pnl(int(pos["id"]), pos["unrealized_pnl"])

        self._repo.update_account_balances(
            account_id,
            totals["balance"],
            totals["available_balance"],
            totals["margin_used"],
        )
        if record_snapshot:
            self._repo.record_equity_snapshot(account_id, "paper", totals["balance"])
        return positions

    def open_position(
        self,
        account_id: int,
        ticker: str,
        direction: str = "long",
        quantity: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        exchange: str = "paper",
    ) -> dict:
        account = self._repo._query(
            "SELECT * FROM paper_accounts WHERE id = :id", {"id": account_id}
        )[0]
        price = self._get_market_price(ticker, self._repo._engine)
        if price is None:
            raise ValueError(f"Нет рыночных данных для {ticker}")

        available = float(account["available_balance"])
        # Apply slippage (worse fill for the trader)
        fill_price = price * (1 + SLIPPAGE_PCT) if direction == "long" else price * (1 - SLIPPAGE_PCT)

        if quantity is None:
            risk_capital = available * 0.05
            quantity = max(1, int(risk_capital / fill_price))
        cost = fill_price * quantity
        commission = cost * COMMISSION_PCT

        if cost + commission > available:
            raise ValueError("Недостаточно средств на paper-счёте")

        if stop_loss is None and fill_price > 0:
            stop_loss = round(fill_price * 0.97, 4) if direction == "long" else round(fill_price * 1.03, 4)
        if take_profit is None:
            take_profit = round(fill_price * 1.06, 4) if direction == "long" else round(fill_price * 0.94, 4)

        pos_id = self._repo.insert_position(account_id, {
            "ticker": ticker.upper(),
            "exchange": exchange,
            "direction": direction,
            "quantity": quantity,
            "entry_price": fill_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        })

        new_available = available - cost - commission
        balance = float(account["balance"])  # total balance unchanged until close
        margin = float(account["margin_used"]) + cost
        self._repo.update_account_balances(account_id, balance, new_available, margin)

        logger.info(
            "Paper position opened: %s %s qty=%s @ %.4f (commission=%.2f)",
            ticker, direction, quantity, fill_price, commission,
        )
        return {"position_id": pos_id, "entry_price": fill_price, "quantity": quantity}

    def close_position(self, position_id: int) -> dict:
        pos = self._repo.get_position(position_id)
        if not pos:
            raise ValueError("Позиция не найдена")

        exit_price = self._get_market_price(pos["ticker"], self._repo._engine) or float(pos["entry_price"])
        qty = float(pos["quantity"])
        entry = float(pos["entry_price"])
        direction = (pos["direction"] or "long").lower()
        account_id = int(pos["account_id"])

        # Apply slippage on exit (worse fill)
        fill_exit = exit_price * (1 - SLIPPAGE_PCT) if direction == "long" else exit_price * (1 + SLIPPAGE_PCT)
        commission = fill_exit * qty * COMMISSION_PCT

        if direction == "short":
            pnl = (entry - fill_exit) * qty - commission
        else:
            pnl = (fill_exit - entry) * qty - commission
        pnl_pct = pnl / (entry * qty) if entry * qty else 0

        self._repo.insert_trade(account_id, {
            "position_id": position_id,
            "ticker": pos["ticker"],
            "exchange": pos["exchange"],
            "direction": direction,
            "entry_price": entry,
            "exit_price": fill_exit,
            "quantity": qty,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "opened_at": pos["opened_at"],
        })
        self._repo.delete_position(position_id)

        account = self._repo._query(
            "SELECT * FROM paper_accounts WHERE id = :id", {"id": account_id}
        )[0]
        proceeds = fill_exit * qty - commission
        new_available = float(account["available_balance"]) + proceeds
        margin = max(0, float(account["margin_used"]) - entry * qty)
        realized = float(self._repo.pnl_periods(account_id).get("realized_pnl") or 0)
        initial = float(account["initial_balance"])
        positions = self.refresh_positions(account_id)
        unrealized = sum(float(p.get("unrealized_pnl", 0)) for p in positions)
        balance = initial + realized + unrealized
        self._repo.update_account_balances(account_id, balance, new_available, margin)

        return {"pnl": round(pnl, 2), "exit_price": fill_exit}

    def execute_from_signal(self, signal: dict) -> dict:
        account = self.get_account()
        account_id = int(account["id"])
        signal_type = (signal.get("signal_type") or "BUY").upper()
        direction = "short" if signal_type in ("SELL", "SHORT") else "long"
        return self.open_position(
            account_id=account_id,
            ticker=signal["asset"],
            direction=direction,
            stop_loss=float(signal["stop_loss"]) if signal.get("stop_loss") else None,
            take_profit=float(signal["take_profit_1"]) if signal.get("take_profit_1") else None,
            exchange=signal.get("exchange", "paper"),
        )