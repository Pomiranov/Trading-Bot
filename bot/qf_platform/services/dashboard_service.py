"""Platform overview — main dashboard aggregation."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import Engine

from config import config
from qf_platform.dto import BrokerStatusDTO, PlatformOverviewDTO, to_dict
from qf_platform.repositories.events_repository import EventsRepository
from qf_platform.repositories.signals_repository import SignalsRepository
from qf_platform.services.portfolio_service import PortfolioService
from qf_platform.services.system_health_service import SystemHealthService

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(self, engine: Engine):
        self._engine = engine
        self._portfolio = PortfolioService(engine)
        self._signals_repo = SignalsRepository(engine)
        self._events = EventsRepository(engine)
        self._health = SystemHealthService(engine)

    def _broker_statuses(self) -> list[BrokerStatusDTO]:
        statuses = []
        tinkoff_ok = bool(config.tinkoff.token and config.tinkoff.account_id)
        statuses.append(BrokerStatusDTO(
            broker_id="tinkoff",
            name="Т-Банк Инвестиции",
            connected=tinkoff_ok,
            configured=bool(config.tinkoff.token),
        ))
        bybit_ok = bool(config.bybit.api_key and config.bybit.api_secret)
        statuses.append(BrokerStatusDTO(
            broker_id="bybit",
            name="Bybit",
            connected=bybit_ok,
            configured=bybit_ok,
        ))
        statuses.append(BrokerStatusDTO(
            broker_id="finam",
            name="Finam",
            connected=False,
            configured=False,
            error="Адаптер в разработке",
        ))
        return statuses

    def get_overview(self) -> PlatformOverviewDTO:
        summary = self._portfolio.get_summary()
        signals_new = self._signals_repo.count_by_status("new")

        recent_trades = self._events._query(
            """
            SELECT ticker, direction, pnl, opened_at, closed_at, status
            FROM trades ORDER BY opened_at DESC LIMIT 10
            """,
        )
        if not recent_trades:
            account = self._portfolio._paper_repo.get_or_create_account()
            recent_trades = self._portfolio._paper_repo.list_trades(int(account["id"]), limit=10)

        recent_signals_rows = self._signals_repo.list_signals(limit=10)
        recent_signals = [
            {
                "id": r["id"],
                "asset": r["asset"],
                "signal_type": r["signal_type"],
                "exchange": r["exchange"],
                "status": r["status"],
                "generated_at": str(r["generated_at"])[:19],
            }
            for r in recent_signals_rows
        ]

        errors = [
            {
                "ts": str(e["created_at"])[:19],
                "level": e["level"],
                "source": e["source"],
                "message": e["message"],
            }
            for e in self._events.recent_errors(10)
        ]

        return PlatformOverviewDTO(
            balance=summary.total_balance,
            pnl_day=summary.pnl_day,
            open_trades=summary.open_positions_count,
            closed_trades=summary.closed_trades_count,
            signals_new=signals_new,
            news_count=self._events.news_count(),
            brokers=self._broker_statuses(),
            system=self._health.get_health(),
            websocket_status="connected",
            recent_errors=errors,
            recent_trades=[
                {
                    "ticker": t.get("ticker", t.get("asset", "")),
                    "direction": t.get("direction", ""),
                    "pnl": float(t.get("pnl") or 0),
                    "status": t.get("status", "closed"),
                    "opened_at": str(t.get("opened_at", ""))[:19],
                }
                for t in recent_trades
            ],
            recent_signals=recent_signals,
            currency=summary.currency,
        )