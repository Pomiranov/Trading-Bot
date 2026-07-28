"""Open positions — read-only, with distance to stop and per-quote freshness.

Three changes from what this replaced:

* **No writes.** ``PaperTradingService.refresh_positions`` updated every position
  row, updated the account and inserted an ``equity_snapshots`` row — and it sat
  on the path of four GET endpoints. Viewing the dashboard therefore wrote 6–27
  rows a minute. Everything here is computed in memory from a read.
* **Distance to stop.** The single most useful derived number on a position row,
  and it was absent: the old UI showed entry and current price and left the trader
  to subtract.
* **Per-cell staleness.** The mark price carries its own quote timestamp. A price
  32 days old must be impossible to mistake for live, and it is the *cell* that is
  stale, not the panel.
"""

from __future__ import annotations

import logging
from typing import Optional

from qf_platform.contracts import EmptyReason, Freshness, Units, age_seconds, safe_float, to_display
from qf_platform.environment import Environment
from qf_platform.repositories.market_repository import MarketRepository
from qf_platform.repositories.trades_repository import TradesRepository
from qf_platform.services.environment_service import stale_threshold

logger = logging.getLogger(__name__)

#: A mark price older than this is stale for a position row. Tighter than the
#: feed-level threshold because an open position is the thing most sensitive to it.
QUOTE_STALE_AFTER_SECONDS = 300


class PositionsService:
    def __init__(self, engine):
        self._trades = TradesRepository(engine)
        self._market = MarketRepository(engine)

    def _account(self, account_id: Optional[int], mode: str) -> Optional[dict]:
        aid = account_id or self._trades.default_account_id(mode=mode)
        return self._trades.account(aid) if aid else None

    def open_positions(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        environment: Environment = Environment.SANDBOX,
    ) -> dict:
        account = self._account(account_id, mode)
        if account is None:
            return {
                "positions": [], "count": 0, "empty_reason": EmptyReason.NOT_CONFIGURED,
                "totals": _empty_totals(), "currency": "RUB",
                "environment": Environment.coerce(environment).value,
                "quote_freshness": None,
            }

        env = Environment.coerce(environment)
        currency = account.get("currency") or "RUB"
        rows = self._trades.open_paper_positions(int(account["id"]), environment=env)

        if not rows:
            return {
                "positions": [], "count": 0, "empty_reason": EmptyReason.NO_POSITIONS,
                "totals": _empty_totals(), "currency": currency,
                "environment": env.value, "quote_freshness": None,
            }

        # One query for every instrument — the old code opened a connection per
        # position inside a loop over a five-connection pool.
        quotes = self._market.latest_quotes([r["ticker"] for r in rows])

        positions: list[dict] = []
        total_value = 0.0
        total_unrealized = 0.0
        total_risk = 0.0
        oldest_quote = None
        stale_count = 0

        for row in rows:
            ticker = row["ticker"]
            quote = quotes.get(ticker)
            entry = safe_float(row["entry_price"]) or 0.0
            quantity = safe_float(row["quantity"]) or 0.0
            direction = (row.get("direction") or "long").lower()
            stop = safe_float(row.get("stop_loss"))
            take = safe_float(row.get("take_profit"))

            mark = quote["price"] if quote else None
            quote_at = quote["as_of"] if quote else None
            quote_age = age_seconds(quote_at) if quote_at else None
            quote_stale = None if quote_age is None else quote_age > QUOTE_STALE_AFTER_SECONDS
            if quote_stale:
                stale_count += 1
            if quote_at and (oldest_quote is None or quote_at < oldest_quote):
                oldest_quote = quote_at

            # Unrealized PnL needs a mark. Without one it is unknown — not zero.
            # The old code substituted the entry price, which renders as a
            # measured 0,00 ₽ and is indistinguishable from a flat position.
            if mark is None:
                unrealized = None
                unrealized_pct = None
            elif direction == "short":
                unrealized = (entry - mark) * quantity
                unrealized_pct = ((entry - mark) / entry * 100.0) if entry else None
            else:
                unrealized = (mark - entry) * quantity
                unrealized_pct = ((mark - entry) / entry * 100.0) if entry else None

            reference = mark if mark is not None else entry
            distance_to_stop_pct = None
            distance_to_stop_abs = None
            if stop and reference:
                if direction == "short":
                    distance_to_stop_abs = stop - reference
                else:
                    distance_to_stop_abs = stop - reference
                distance_to_stop_pct = distance_to_stop_abs / reference * 100.0

            distance_to_take_pct = None
            if take and reference:
                distance_to_take_pct = (take - reference) / reference * 100.0

            # Capital at risk: what the stop actually costs if it fills.
            risk_amount = None
            if stop and entry and quantity:
                risk_amount = abs(entry - stop) * quantity
                total_risk += risk_amount

            position_value = (reference or 0.0) * quantity
            total_value += position_value
            if unrealized is not None:
                total_unrealized += unrealized

            positions.append({
                "id": int(row["id"]),
                "ticker": ticker,
                "exchange": row.get("exchange"),
                "direction": direction,
                "quantity": quantity,
                "entry_price": round(entry, 4),
                "mark_price": None if mark is None else round(mark, 4),
                "mark_as_of": to_display(quote_at),
                "mark_age_seconds": quote_age,
                "mark_is_stale": quote_stale,
                "mark_timeframe": quote.get("timeframe") if quote else None,
                "stop_loss": stop,
                "take_profit": take,
                "distance_to_stop_pct": (
                    None if distance_to_stop_pct is None else round(distance_to_stop_pct, 2)
                ),
                "distance_to_stop_abs": (
                    None if distance_to_stop_abs is None else round(distance_to_stop_abs, 4)
                ),
                "distance_to_take_pct": (
                    None if distance_to_take_pct is None else round(distance_to_take_pct, 2)
                ),
                "risk_amount": None if risk_amount is None else round(risk_amount, 2),
                "unrealized_pnl": None if unrealized is None else round(unrealized, 2),
                "unrealized_pnl_pct": (
                    None if unrealized_pct is None else round(unrealized_pct, 2)
                ),
                "position_value": round(position_value, 2),
                "strategy_id": row.get("strategy_id"),
                "entry_reason": row.get("entry_reason"),
                "opened_at": to_display(row.get("opened_at")),
                "opened_age_seconds": age_seconds(row.get("opened_at")),
                "environment": row.get("environment") or env.value,
                # Present so the client never has to guess whether the absence of
                # a PnL means zero or unknown.
                "missing": None if mark is not None else {"mark_price": "нет котировки"},
            })

        equity = safe_float(account.get("balance")) or 0.0
        return {
            "positions": positions,
            "count": len(positions),
            "empty_reason": None,
            "currency": currency,
            "environment": env.value,
            "stale_quote_count": stale_count,
            "quote_freshness": {
                "source_as_of": to_display(oldest_quote),
                "data_age_seconds": age_seconds(oldest_quote) if oldest_quote else None,
                "stale_after_seconds": QUOTE_STALE_AFTER_SECONDS,
                "source": "candles",
            },
            "totals": {
                "exposure_abs": round(total_value, 2),
                "exposure_pct": round(total_value / equity * 100.0, 2) if equity else None,
                "unrealized_pnl": round(total_unrealized, 2),
                "capital_at_risk_abs": round(total_risk, 2) if total_risk else None,
                "capital_at_risk_pct": (
                    round(total_risk / equity * 100.0, 2) if equity and total_risk else None
                ),
                "largest_position_pct": (
                    round(max(p["position_value"] for p in positions) / total_value * 100.0, 2)
                    if total_value else None
                ),
            },
            "units": {
                "exposure_abs": Units.MONEY,
                "exposure_pct": Units.PERCENT,
                "unrealized_pnl": Units.MONEY,
                "distance_to_stop_pct": Units.PERCENT,
                "mark_price": Units.PRICE,
                "quantity": Units.SHARES,
            },
        }

    def freshness(self, payload: dict) -> Freshness:
        info = payload.get("quote_freshness") or {}
        return Freshness(
            source_as_of=None,
            source=info.get("source") or "candles",
            stale_after_seconds=info.get("stale_after_seconds") or QUOTE_STALE_AFTER_SECONDS,
        )

    def position(self, position_id: int, *, mode: str = "rub") -> Optional[dict]:
        payload = self.open_positions(mode=mode)
        for item in payload["positions"]:
            if item["id"] == position_id:
                return item
        return None


def _empty_totals() -> dict:
    return {
        "exposure_abs": 0.0,
        "exposure_pct": 0.0,
        "unrealized_pnl": 0.0,
        "capital_at_risk_abs": None,
        "capital_at_risk_pct": None,
        "largest_position_pct": None,
    }
