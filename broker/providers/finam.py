"""Finam broker adapter — ready for implementation via Finam Trade API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from broker.base import (
    BrokerAdapter,
    BrokerBalance,
    BrokerInfo,
    BrokerNotConfigured,
    BrokerOperation,
    BrokerOrder,
    BrokerPortfolio,
    BrokerPosition,
    BrokerTradingNotSupported,
    OrderDirection,
    OrderStatus,
)


class FinamBrokerAdapter(BrokerAdapter):
    """
    Finam broker adapter skeleton.

    Finam provides REST API via https://finamweb.github.io/trade-api-docs/
    Install: pip install finam-trade-api
    Authenticate via client_id + access_token from Finam cabinet.
    """

    def __init__(self, client_id: str = "", access_token: str = "") -> None:
        self._client_id = client_id
        self._access_token = access_token

    @property
    def broker_id(self) -> str:
        return "finam"

    @property
    def broker_name(self) -> str:
        return "Finam"

    def _require_credentials(self) -> None:
        if not self._client_id or not self._access_token:
            raise BrokerNotConfigured(
                "Finam: client_id и access_token не настроены. "
                "Получите токен в личном кабинете Finam."
            )

    async def get_info(self) -> BrokerInfo:
        is_configured = bool(self._client_id and self._access_token)
        return BrokerInfo(
            broker_id=self.broker_id,
            name=self.broker_name,
            description="Finam Trade API (MOEX, СПБ)",
            is_connected=False,
            is_configured=is_configured,
            error=None if is_configured else "Требуется настройка client_id и access_token",
        )

    async def get_portfolio(self) -> BrokerPortfolio:
        self._require_credentials()
        raise NotImplementedError(
            "Finam portfolio: реализация через Finam Trade API SecurityPortfolio endpoint"
        )

    async def get_positions(self) -> list[BrokerPosition]:
        self._require_credentials()
        raise NotImplementedError("Finam positions: реализация через GET /api/v1/portfolio")

    async def get_orders(
        self,
        status_filter: Optional[list[OrderStatus]] = None,
    ) -> list[BrokerOrder]:
        self._require_credentials()
        raise NotImplementedError("Finam orders: реализация через GET /api/v1/orders")

    async def get_operations(
        self,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[BrokerOperation]:
        self._require_credentials()
        raise NotImplementedError("Finam operations: реализация через GET /api/v1/events/trades")

    async def get_balance(self) -> list[BrokerBalance]:
        self._require_credentials()
        raise NotImplementedError("Finam balance: реализация через GET /api/v1/portfolio/money")

    async def place_market_order(
        self,
        figi: str,
        quantity: int,
        direction: OrderDirection,
    ) -> BrokerOrder:
        self._require_credentials()
        raise NotImplementedError("Finam market order: реализация через POST /api/v1/orders")

    async def place_limit_order(
        self,
        figi: str,
        quantity: int,
        price: float,
        direction: OrderDirection,
    ) -> BrokerOrder:
        self._require_credentials()
        raise NotImplementedError("Finam limit order: реализация через POST /api/v1/orders")

    async def cancel_order(self, order_id: str) -> bool:
        self._require_credentials()
        raise NotImplementedError("Finam cancel: реализация через DELETE /api/v1/orders/{orderId}")

    async def find_instrument(self, ticker: str) -> Optional[dict]:
        self._require_credentials()
        raise NotImplementedError(
            "Finam find_instrument: реализация через GET /api/v1/securities?ticker={ticker}"
        )
