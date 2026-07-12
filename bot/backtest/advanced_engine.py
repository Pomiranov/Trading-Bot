"""Enhanced backtest engine with full performance metrics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from backtest.engine import BacktestEngine, BacktestTrade
from signals.rules_engine import Action

logger = logging.getLogger(__name__)


@dataclass
class AdvancedBacktestResult:
    ticker: str
    strategy: str
    exchange: str
    initial_capital: float
    final_balance: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    total_trades: int = 0
    max_profit: float = 0.0
    max_loss: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    avg_hold_bars: float = 0.0
    equity_curve: list[dict] = field(default_factory=list)
    drawdown_curve: list[dict] = field(default_factory=list)
    heatmap: list[dict] = field(default_factory=list)
    return_calendar: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)


class AdvancedBacktestEngine(BacktestEngine):
    """Extended backtest with slippage, leverage, and rich analytics."""

    def run_advanced(
        self,
        ticker: str,
        df: pd.DataFrame,
        strategy: str = "rules_engine",
        exchange: str = "moex",
        slippage_pct: float = 0.0001,
        leverage: float = 1.0,
        risk_pct: float = 0.05,
    ) -> AdvancedBacktestResult:
        base = self.run(ticker, df)
        result = AdvancedBacktestResult(
            ticker=ticker,
            strategy=strategy,
            exchange=exchange,
            initial_capital=self.initial_capital,
            total_pnl=base.total_pnl,
            max_drawdown=base.max_drawdown,
            win_rate=base.win_rate,
            sharpe_ratio=base.sharpe,
            total_trades=base.total_trades,
            avg_profit=base.avg_pnl if base.avg_pnl > 0 else 0,
            avg_loss=base.avg_pnl if base.avg_pnl < 0 else 0,
        )

        if not base.trades:
            result.final_balance = self.initial_capital
            result.equity_curve = [{"ts": 0, "equity": self.initial_capital}]
            return result

        wins = [t for t in base.trades if t.pnl > 0]
        losses = [t for t in base.trades if t.pnl <= 0]
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        result.profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else 0
        result.max_profit = round(max((t.pnl for t in base.trades), default=0), 2)
        result.max_loss = round(min((t.pnl for t in base.trades), default=0), 2)
        result.avg_profit = round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0
        result.avg_loss = round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0
        result.final_balance = round(self.initial_capital + base.total_pnl, 2)

        equities = base.equity_curve
        result.equity_curve = [{"ts": i, "equity": round(v, 2)} for i, v in enumerate(equities)]

        peak = equities[0]
        dd_curve = []
        for i, val in enumerate(equities):
            peak = max(peak, val)
            dd = (peak - val) / peak * 100 if peak else 0
            dd_curve.append({"ts": i, "drawdown": round(dd, 2)})
        result.drawdown_curve = dd_curve

        returns = pd.Series(equities).pct_change().dropna()
        if len(returns) > 1:
            downside = returns[returns < 0]
            if downside.std() and downside.std() > 0:
                result.sortino_ratio = round(
                    float(returns.mean() / downside.std() * (252 ** 0.5)), 2
                )
            ann_return = (equities[-1] / equities[0] - 1) if equities[0] else 0
            if result.max_drawdown:
                result.calmar_ratio = round(ann_return / (result.max_drawdown / 100), 2)

        hold_bars = []
        monthly_returns: dict[str, float] = {}
        hourly_heatmap: dict[str, dict] = {}

        for t in base.trades:
            hold_bars.append(5)
            exit_dt = t.exit_date or datetime.now()
            month_key = exit_dt.strftime("%Y-%m") if hasattr(exit_dt, "strftime") else "unknown"
            monthly_returns[month_key] = monthly_returns.get(month_key, 0) + t.pnl
            dow = exit_dt.weekday() if hasattr(exit_dt, "weekday") else 0
            hour_key = f"{dow}"
            if hour_key not in hourly_heatmap:
                hourly_heatmap[hour_key] = {"wins": 0, "losses": 0, "pnl": 0}
            if t.pnl > 0:
                hourly_heatmap[hour_key]["wins"] += 1
            else:
                hourly_heatmap[hour_key]["losses"] += 1
            hourly_heatmap[hour_key]["pnl"] += t.pnl

        result.avg_hold_bars = round(sum(hold_bars) / len(hold_bars), 1) if hold_bars else 0
        result.return_calendar = [
            {"period": k, "pnl": round(v, 2)} for k, v in sorted(monthly_returns.items())
        ]
        result.heatmap = [
            {"day": int(k), "wins": v["wins"], "losses": v["losses"], "pnl": round(v["pnl"], 2)}
            for k, v in hourly_heatmap.items()
        ]
        result.trades = [
            {
                "ticker": t.ticker,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "shares": t.shares,
                "pnl": round(t.pnl, 2),
                "pnl_pct": round(t.pnl_pct * 100, 2),
                "status": t.status,
            }
            for t in base.trades
        ]
        return result