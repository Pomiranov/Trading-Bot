"""Backtest orchestration service."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import Engine

from backtest.advanced_engine import AdvancedBacktestEngine
from qf_platform.dto import BacktestRequestDTO, BacktestResultDTO, to_dict
from qf_platform.repositories.backtest_repository import BacktestRepository

logger = logging.getLogger(__name__)


class BacktestService:
    def __init__(self, engine: Engine):
        self._engine = engine
        self._repo = BacktestRepository(engine)

    def _load_candles(
        self,
        ticker: str,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> pd.DataFrame:
        clauses = ["ticker = :ticker", "timeframe = '1d'"]
        params: dict = {"ticker": ticker.upper()}
        if period_start:
            clauses.append("time >= :pstart")
            params["pstart"] = period_start
        if period_end:
            clauses.append("time <= :pend")
            params["pend"] = period_end
        where = " AND ".join(clauses)
        rows = self._repo._query(
            f"""
            SELECT time, open, high, low, close, volume FROM candles
            WHERE {where} ORDER BY time ASC
            """,
            params,
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.set_index("time", inplace=True)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        return df

    def run(self, request: BacktestRequestDTO) -> BacktestResultDTO:
        df = self._load_candles(request.ticker, request.period_start, request.period_end)
        if df.empty or len(df) < 55:
            raise ValueError(f"Недостаточно данных для {request.ticker}")

        engine = AdvancedBacktestEngine(
            initial_capital=request.initial_capital,
            commission_pct=request.commission_pct,
        )
        result = engine.run_advanced(
            ticker=request.ticker,
            df=df,
            strategy=request.strategy,
            exchange=request.exchange,
            slippage_pct=request.slippage_pct,
            leverage=request.leverage,
            risk_pct=request.risk_pct,
        )

        dto = BacktestResultDTO(
            run_id=None,
            ticker=result.ticker,
            strategy=result.strategy,
            exchange=result.exchange,
            initial_capital=result.initial_capital,
            final_balance=result.final_balance,
            total_pnl=result.total_pnl,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            profit_factor=result.profit_factor,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            calmar_ratio=result.calmar_ratio,
            total_trades=result.total_trades,
            max_profit=result.max_profit,
            max_loss=result.max_loss,
            avg_profit=result.avg_profit,
            avg_loss=result.avg_loss,
            avg_hold_bars=result.avg_hold_bars,
            equity_curve=result.equity_curve,
            drawdown_curve=result.drawdown_curve,
            heatmap=result.heatmap,
            return_calendar=result.return_calendar,
            trades=result.trades,
        )

        run_id = self._repo.save_run(to_dict(request), to_dict(dto))
        dto.run_id = run_id
        return dto

    def list_runs(self, limit: int = 20) -> list[dict]:
        return self._repo.list_runs(limit)

    def export_run(self, run_id: int) -> dict | None:
        run = self._repo.get_run(run_id)
        if not run:
            return None
        return dict(run)