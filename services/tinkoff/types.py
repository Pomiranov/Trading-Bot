"""Domain types for the Tinkoff Invest service layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    figi: str
    ticker: str
    name: str
    instrument_type: str
    quantity: float
    quantity_lots: float
    average_price: float
    current_price: float
    expected_yield: float       # absolute unrealized PnL in account currency
    expected_yield_pct: float   # relative PnL vs cost basis
    current_value: float        # current_price × quantity
    currency: str


@dataclass
class PortfolioSummary:
    total_value: float
    total_yield: float          # sum of expected_yield across non-currency positions
    total_yield_pct: float      # total_yield / cost_basis × 100
    positions_count: int
    currency: str = "rub"
    positions: list[Position] = field(default_factory=list)


@dataclass
class BotStatistics:
    total_trades: Optional[int]
    winning_trades: Optional[int]
    losing_trades: Optional[int]
    win_rate: Optional[float]       # None when no closed trades
    sharpe_ratio: Optional[float]   # None when < 5 trades
    max_drawdown: Optional[float]   # None when < 2 trades
    avg_trade_pnl: Optional[float]
    total_pnl: Optional[float]
    has_sufficient_data: bool       # True when >= 5 closed trades
