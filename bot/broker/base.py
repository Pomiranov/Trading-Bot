"""Universal broker adapter interface and shared domain types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OperationType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    COUPON = "COUPON"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    COMMISSION = "COMMISSION"
    TAX = "TAX"
    CONVERSION = "CONVERSION"
    OTHER = "OTHER"


@dataclass
class BrokerPosition:
    broker_id: str
    figi: str
    ticker: str
    name: str
    instrument_type: str
    quantity: float
    quantity_lots: float
    average_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    current_value: float
    currency: str


@dataclass
class BrokerOrder:
    broker_id: str
    order_id: str
    ticker: str
    figi: str
    direction: OrderDirection
    order_type: OrderType
    status: OrderStatus
    quantity: int
    filled_quantity: int
    price: Optional[float]
    average_price: Optional[float]
    currency: str
    created_at: datetime
    updated_at: Optional[datetime] = None


@dataclass
class BrokerOperation:
    broker_id: str
    operation_id: str
    operation_type: OperationType
    ticker: Optional[str]
    figi: Optional[str]
    quantity: Optional[float]
    price: Optional[float]
    payment: float
    currency: str
    executed_at: datetime
    description: str = ""


@dataclass
class BrokerBalance:
    broker_id: str
    currency: str
    available: float
    blocked: float = 0.0

    @property
    def total(self) -> float:
        return self.available + self.blocked


@dataclass
class BrokerPortfolio:
    broker_id: str
    broker_name: str
    total_value: float
    total_yield: float
    total_yield_pct: float
    currency: str
    positions_count: int
    positions: list[BrokerPosition] = field(default_factory=list)


@dataclass
class BrokerInfo:
    broker_id: str
    name: str
    description: str
    is_connected: bool
    is_configured: bool
    supports_trading: bool = True
    last_sync: Optional[datetime] = None
    error: Optional[str] = None


class BrokerNotConfigured(ValueError):
    """Broker credentials or required settings are missing."""


class BrokerConnectionError(RuntimeError):
    """Failed to connect to the broker API."""


class BrokerTradingNotSupported(NotImplementedError):
    """This broker adapter does not support order placement."""


class BrokerAdapter(ABC):
    """
    Universal broker interface. All implementations must be safe for
    concurrent async calls. Blocking SDK operations must be wrapped
    with asyncio.to_thread().
    """

    @property
    @abstractmethod
    def broker_id(self) -> str:
        """Unique snake_case identifier (e.g., 'tinkoff', 'finam')."""

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Human-readable display name."""

    @abstractmethod
    async def get_info(self) -> BrokerInfo:
        """Broker metadata and live connection status."""

    @abstractmethod
    async def get_portfolio(self) -> BrokerPortfolio:
        """Full portfolio summary with enriched positions."""

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Current open positions."""

    @abstractmethod
    async def get_orders(
        self,
        status_filter: Optional[list[OrderStatus]] = None,
    ) -> list[BrokerOrder]:
        """Orders, optionally filtered by status list."""

    @abstractmethod
    async def get_operations(
        self,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[BrokerOperation]:
        """Operation history (trades, dividends, deposits, etc.)."""

    @abstractmethod
    async def get_balance(self) -> list[BrokerBalance]:
        """Balances for all available currencies."""

    @abstractmethod
    async def place_market_order(
        self,
        figi: str,
        quantity: int,
        direction: OrderDirection,
    ) -> BrokerOrder:
        """Place a market order. Raises BrokerConnectionError on failure."""

    @abstractmethod
    async def place_limit_order(
        self,
        figi: str,
        quantity: int,
        price: float,
        direction: OrderDirection,
    ) -> BrokerOrder:
        """Place a limit order. Raises BrokerConnectionError on failure."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID. Returns True on success."""

    @abstractmethod
    async def find_instrument(self, ticker: str) -> Optional[dict]:
        """Resolve ticker → instrument metadata (figi, lot, name, etc.)."""

    def supports_trading(self) -> bool:
        """Return False if this adapter is read-only."""
        return True
