"""Data transfer objects for platform API responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


def to_dict(obj: Any) -> dict:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj


@dataclass
class BrokerStatusDTO:
    broker_id: str
    name: str
    connected: bool
    configured: bool
    error: Optional[str] = None


@dataclass
class PortfolioSummaryDTO:
    total_balance: float
    available_funds: float
    margin_used: float
    total_pnl: float
    pnl_day: float
    pnl_week: float
    pnl_month: float
    unrealized_pnl: float
    realized_pnl: float
    return_pct: float
    roi: float
    open_positions_count: int
    closed_trades_count: int
    avg_risk_pct: float
    avg_rr: float
    #: Signed mean of pnl_pct — the actual average profit. Was AVG(ABS(...)),
    #: which reported +16,07 % on an account with zero winning trades.
    avg_profit_pct: float
    currency: str
    source: str  # broker | paper | combined
    #: Sample size for avg_profit_pct. Mandatory: without it a 0,00 % from an
    #: empty sample is indistinguishable from a measured 0,00 % over 48 trades.
    avg_profit_pct_n: int = 0
    #: Mean absolute move — a different statistic, under its own name.
    avg_abs_move_pct: float = 0.0
    best_positions: list[dict] = field(default_factory=list)
    worst_positions: list[dict] = field(default_factory=list)
    asset_allocation: list[dict] = field(default_factory=list)
    currency_allocation: list[dict] = field(default_factory=list)
    instrument_allocation: list[dict] = field(default_factory=list)
    equity_history: list[dict] = field(default_factory=list)


@dataclass
class SignalDTO:
    id: int
    asset: str
    exchange: str
    timeframe: str
    signal_type: str
    entry_price: float
    stop_loss: Optional[float]
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    risk_reward: Optional[float]
    probability_pct: float
    generated_at: str
    status: str
    source: str
    asset_class: str
    metadata: dict = field(default_factory=dict)


@dataclass
class BacktestRequestDTO:
    strategy: str = "rules_engine"
    exchange: str = "moex"
    ticker: str = "SBER"
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    initial_capital: float = 1_000_000.0
    risk_pct: float = 0.05
    commission_pct: float = 0.0003
    slippage_pct: float = 0.0001
    leverage: float = 1.0


@dataclass
class BacktestResultDTO:
    run_id: Optional[int]
    ticker: str
    strategy: str
    exchange: str
    initial_capital: float
    final_balance: float
    total_pnl: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    total_trades: int
    max_profit: float
    max_loss: float
    avg_profit: float
    avg_loss: float
    avg_hold_bars: float
    equity_curve: list[dict]
    drawdown_curve: list[dict]
    heatmap: list[dict]
    return_calendar: list[dict]
    trades: list[dict]


@dataclass
class PlatformOverviewDTO:
    balance: float
    pnl_day: float
    open_trades: int
    closed_trades: int
    signals_new: int
    news_count: int
    brokers: list[BrokerStatusDTO]
    system: dict
    websocket_status: str
    recent_errors: list[dict]
    recent_trades: list[dict]
    recent_signals: list[dict]
    currency: str = "RUB"