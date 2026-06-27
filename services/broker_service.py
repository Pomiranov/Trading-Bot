"""Multi-broker facade — the single entry point for all broker data in the service layer."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from broker.base import (
    BrokerBalance,
    BrokerConnectionError,
    BrokerInfo,
    BrokerNotConfigured,
    BrokerOperation,
    BrokerOrder,
    BrokerPortfolio,
    BrokerPosition,
    OrderDirection,
    OrderStatus,
)
from broker.registry import broker_registry

logger = logging.getLogger(__name__)


async def get_all_broker_info() -> list[BrokerInfo]:
    tasks = [adapter.get_info() for adapter in broker_registry.all()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    infos = []
    for adapter, result in zip(broker_registry.all(), results):
        if isinstance(result, Exception):
            logger.warning("get_info failed for %s: %s", adapter.broker_id, result)
            from broker.base import BrokerInfo
            infos.append(BrokerInfo(
                broker_id=adapter.broker_id,
                name=adapter.broker_name,
                description="",
                is_connected=False,
                is_configured=False,
                error=str(result),
            ))
        else:
            infos.append(result)
    return infos


async def get_broker_portfolio(broker_id: str) -> BrokerPortfolio:
    adapter = broker_registry.get(broker_id)
    return await adapter.get_portfolio()


async def get_all_portfolios() -> list[BrokerPortfolio]:
    adapters = broker_registry.all()
    tasks = [a.get_portfolio() for a in adapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    portfolios = []
    for adapter, result in zip(adapters, results):
        if isinstance(result, Exception):
            logger.warning("Portfolio fetch failed for %s: %s", adapter.broker_id, result)
        else:
            portfolios.append(result)
    return portfolios


async def get_all_positions() -> list[BrokerPosition]:
    portfolios = await get_all_portfolios()
    return [pos for p in portfolios for pos in p.positions]


async def get_broker_orders(
    broker_id: str,
    status_filter: Optional[list[OrderStatus]] = None,
) -> list[BrokerOrder]:
    adapter = broker_registry.get(broker_id)
    return await adapter.get_orders(status_filter=status_filter)


async def get_broker_operations(
    broker_id: str,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    limit: int = 50,
) -> list[BrokerOperation]:
    adapter = broker_registry.get(broker_id)
    return await adapter.get_operations(from_dt=from_dt, to_dt=to_dt, limit=limit)


async def get_broker_balance(broker_id: str) -> list[BrokerBalance]:
    adapter = broker_registry.get(broker_id)
    return await adapter.get_balance()


async def get_all_balances() -> dict[str, list[BrokerBalance]]:
    adapters = broker_registry.all()
    tasks = [a.get_balance() for a in adapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    balances: dict[str, list[BrokerBalance]] = {}
    for adapter, result in zip(adapters, results):
        if isinstance(result, Exception):
            logger.warning("Balance fetch failed for %s: %s", adapter.broker_id, result)
        else:
            balances[adapter.broker_id] = result
    return balances


async def find_instrument(broker_id: str, ticker: str) -> Optional[dict]:
    adapter = broker_registry.get(broker_id)
    return await adapter.find_instrument(ticker)
