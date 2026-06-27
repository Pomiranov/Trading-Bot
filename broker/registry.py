"""Broker registry — single source of truth for all configured broker adapters."""
from __future__ import annotations

import logging
from typing import Optional

from broker.base import BrokerAdapter, BrokerNotConfigured

logger = logging.getLogger(__name__)


class BrokerRegistry:
    """
    Registry of all available broker adapters.

    Adapters are registered once at startup. The registry is a module-level
    singleton — import `broker_registry` from this module.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapter] = {}

    def register(self, adapter: BrokerAdapter) -> None:
        self._adapters[adapter.broker_id] = adapter
        logger.info("Broker registered: %s", adapter.broker_name)

    def get(self, broker_id: str) -> BrokerAdapter:
        adapter = self._adapters.get(broker_id)
        if adapter is None:
            raise BrokerNotConfigured(f"Брокер '{broker_id}' не зарегистрирован")
        return adapter

    def all(self) -> list[BrokerAdapter]:
        return list(self._adapters.values())

    def ids(self) -> list[str]:
        return list(self._adapters.keys())

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, broker_id: str) -> bool:
        return broker_id in self._adapters


def _build_registry() -> BrokerRegistry:
    registry = BrokerRegistry()
    from broker.providers.tinkoff import TinkoffBrokerAdapter
    registry.register(TinkoffBrokerAdapter())
    from broker.providers.finam import FinamBrokerAdapter
    registry.register(FinamBrokerAdapter())
    return registry


broker_registry: BrokerRegistry = _build_registry()
