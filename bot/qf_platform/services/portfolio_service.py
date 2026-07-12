"""Unified portfolio aggregation — brokers + paper trading."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import Engine

from config import config
from qf_platform.dto import PortfolioSummaryDTO
from qf_platform.repositories.paper_repository import PaperRepository
from qf_platform.services.paper_trading_service import PaperTradingService

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=15)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class PortfolioService:
    def __init__(self, engine: Engine):
        self._engine = engine
        self._paper_repo = PaperRepository(engine)
        self._paper = PaperTradingService(engine)

    def _broker_connected(self) -> dict[str, bool]:
        return {
            "tinkoff": bool(config.tinkoff.token and config.tinkoff.account_id),
            "bybit": bool(config.bybit.api_key and config.bybit.api_secret),
            "finam": bool(getattr(config, "finam", None) and getattr(config.finam, "token", "")),
        }

    def _fetch_tinkoff_portfolio(self) -> Optional[dict]:
        if not self._broker_connected()["tinkoff"]:
            return None
        try:
            from services.tinkoff import get_portfolio_summary
            summary = get_portfolio_summary()
            positions = []
            for p in summary.positions:
                positions.append({
                    "ticker": p.ticker,
                    "name": p.name,
                    "quantity": p.quantity,
                    "entry_price": p.average_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.expected_yield,
                    "unrealized_pnl_pct": p.expected_yield_pct,
                    "current_value": p.current_value,
                    "currency": p.currency or "RUB",
                })
            return {
                "total_balance": summary.total_value,
                "available_funds": summary.total_value * 0.1,  # estimate
                "margin_used": 0,
                "unrealized_pnl": summary.total_yield,
                "currency": summary.currency or "RUB",
                "positions": positions,
                "source": "tinkoff",
            }
        except Exception as exc:
            logger.warning("Tinkoff portfolio fetch failed: %s", exc)
            return None

    def _fetch_bybit_portfolio(self) -> Optional[dict]:
        if not self._broker_connected()["bybit"]:
            return None
        try:
            from broker.bybit_client import BybitClient
            client = BybitClient()
            bal = client.get_wallet_balance()
            coins = bal.get("coins", [])
            total = sum(c.get("wallet_balance", 0) for c in coins)
            usdt = next((c for c in coins if c.get("coin") == "USDT"), {})
            positions_raw = client.get_positions() or []
            positions = []
            for p in positions_raw:
                positions.append({
                    "ticker": p.get("symbol", ""),
                    "quantity": float(p.get("size", 0)),
                    "entry_price": float(p.get("avgPrice", 0)),
                    "current_price": float(p.get("markPrice", 0)),
                    "unrealized_pnl": float(p.get("unrealisedPnl", 0)),
                    "unrealized_pnl_pct": 0,
                    "current_value": float(p.get("positionValue", 0)),
                    "currency": "USDT",
                })
            return {
                "total_balance": total,
                "available_funds": float(usdt.get("available", 0)),
                "margin_used": total - float(usdt.get("available", 0)),
                "unrealized_pnl": sum(float(c.get("unrealized_pnl", 0)) for c in coins),
                "currency": "USDT",
                "positions": positions,
                "source": "bybit",
            }
        except Exception as exc:
            logger.warning("Bybit portfolio fetch failed: %s", exc)
            return None

    def _paper_portfolio(self, mode: str = "rub") -> dict:
        account = self._paper.get_account(mode=mode)
        account_id = int(account["id"])
        positions = self._paper.refresh_positions(account_id)
        periods = self._paper_repo.pnl_periods(account_id)
        initial = float(account["initial_balance"])
        realized = float(periods.get("realized_pnl") or 0)
        unrealized = sum(float(p.get("unrealized_pnl", 0)) for p in positions)
        balance = initial + realized + unrealized

        paper_positions = []
        for p in positions:
            paper_positions.append({
                "ticker": p["ticker"],
                "quantity": float(p["quantity"]),
                "entry_price": float(p["entry_price"]),
                "current_price": float(p.get("current_price", p["entry_price"])),
                "unrealized_pnl": float(p.get("unrealized_pnl", 0)),
                "unrealized_pnl_pct": float(p.get("pnl_pct", 0)),
                "current_value": float(p.get("current_price", p["entry_price"])) * float(p["quantity"]),
                "currency": account["currency"],
            })

        history = self._paper_repo.equity_history(account_id)
        history = list(reversed(history))

        return {
            "total_balance": balance,
            "available_funds": float(account["available_balance"]),
            "margin_used": float(account["margin_used"]),
            "unrealized_pnl": unrealized,
            "realized_pnl": realized,
            "pnl_day": float(periods.get("pnl_day") or 0),
            "pnl_week": float(periods.get("pnl_week") or 0),
            "pnl_month": float(periods.get("pnl_month") or 0),
            "currency": account["currency"],
            "positions": paper_positions,
            "closed_trades_count": int(periods.get("closed_count") or 0),
            "equity_history": [{"ts": str(h["ts"])[:10], "equity": float(h["equity"])} for h in history],
            "source": "paper",
            "initial_balance": initial,
        }

    def get_summary(self, mode: str = "rub") -> PortfolioSummaryDTO:
        brokers = self._broker_connected()
        broker_data = self._fetch_tinkoff_portfolio() or self._fetch_bybit_portfolio()
        use_paper = broker_data is None

        if use_paper:
            data = self._paper_portfolio(mode)
        else:
            data = broker_data
            data.setdefault("realized_pnl", 0)
            data.setdefault("pnl_day", 0)
            data.setdefault("pnl_week", 0)
            data.setdefault("pnl_month", 0)
            data.setdefault("closed_trades_count", 0)
            data.setdefault("equity_history", [])
            data.setdefault("initial_balance", data["total_balance"])

        positions = data.get("positions", [])
        initial = float(data.get("initial_balance", data["total_balance"]))
        total = float(data["total_balance"])
        total_pnl = total - initial if use_paper else float(data.get("unrealized_pnl", 0))

        sorted_pos = sorted(positions, key=lambda p: p.get("unrealized_pnl", 0), reverse=True)
        best = sorted_pos[:3]
        worst = sorted(positions, key=lambda p: p.get("unrealized_pnl", 0))[:3]

        total_value = sum(abs(p.get("current_value", 0)) for p in positions) or total
        asset_alloc = []
        currency_map: dict[str, float] = {}
        instrument_map: dict[str, float] = {}

        for p in positions:
            val = abs(p.get("current_value", 0))
            ticker = p.get("ticker", "?")
            cur = p.get("currency", data.get("currency", "RUB"))
            pct = round(val / total_value * 100, 2) if total_value else 0
            asset_alloc.append({"label": ticker, "value": val, "pct": pct})
            currency_map[cur] = currency_map.get(cur, 0) + val
            instrument_map[ticker] = instrument_map.get(ticker, 0) + val

        currency_alloc = [
            {"label": k, "value": v, "pct": round(v / total_value * 100, 2) if total_value else 0}
            for k, v in currency_map.items()
        ]
        instrument_alloc = [
            {"label": k, "value": v, "pct": round(v / total_value * 100, 2) if total_value else 0}
            for k, v in instrument_map.items()
        ]

        closed = int(data.get("closed_trades_count", 0))
        trades_stats = self._paper_repo._query(
            """
            SELECT AVG(ABS(pnl_pct)) AS avg_profit_pct FROM paper_trades
            WHERE account_id = (SELECT id FROM paper_accounts LIMIT 1)
            """,
        ) if use_paper else self._paper_repo._query(
            """
            SELECT AVG(ABS(pnl_pct)) AS avg_profit_pct,
                   COUNT(*) AS closed_count
            FROM trades WHERE closed_at IS NOT NULL
            """,
        )
        avg_profit = float(trades_stats[0].get("avg_profit_pct") or 0) * 100 if trades_stats else 0
        if not use_paper and trades_stats:
            closed = int(trades_stats[0].get("closed_count") or closed)

        roi = round(total_pnl / initial * 100, 4) if initial else 0

        return PortfolioSummaryDTO(
            total_balance=round(total, 2),
            available_funds=round(float(data.get("available_funds", 0)), 2),
            margin_used=round(float(data.get("margin_used", 0)), 2),
            total_pnl=round(total_pnl, 2),
            pnl_day=round(float(data.get("pnl_day", 0)), 2),
            pnl_week=round(float(data.get("pnl_week", 0)), 2),
            pnl_month=round(float(data.get("pnl_month", 0)), 2),
            unrealized_pnl=round(float(data.get("unrealized_pnl", 0)), 2),
            realized_pnl=round(float(data.get("realized_pnl", 0)), 2),
            return_pct=roi,
            roi=roi,
            open_positions_count=len(positions),
            closed_trades_count=closed,
            avg_risk_pct=5.0,
            avg_rr=2.0,
            avg_profit_pct=round(avg_profit, 2),
            currency=data.get("currency", "RUB"),
            source="paper" if use_paper else data.get("source", "broker"),
            best_positions=best,
            worst_positions=worst,
            asset_allocation=asset_alloc,
            currency_allocation=currency_alloc,
            instrument_allocation=instrument_alloc,
            equity_history=data.get("equity_history", []),
        )