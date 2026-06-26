"""Простой событийный бэктестер на дневных/часовых свечах."""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd

from signals.indicators import IndicatorEngine
from signals.rules_engine import RulesEngine, Action
from risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    ticker: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    shares: int = 0
    stop_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: str = "OPEN"  # OPEN / WIN / LOSS / STOPPED


@dataclass
class BacktestResult:
    ticker: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.ticker}] Сделок: {self.total_trades} | "
            f"Win Rate: {self.win_rate:.1f}% | "
            f"PnL: {self.total_pnl:+.2f} руб. | "
            f"Просадка: {self.max_drawdown:.2f}% | "
            f"Sharpe: {self.sharpe:.2f}"
        )


class BacktestEngine:
    """
    Событийный бэктестер.

    На каждой свече:
    1. Проверяет стоп-лосс открытой позиции.
    2. Вычисляет индикаторы и прогоняет через движок правил.
    3. Если есть сигнал и позиция не открыта — открывает позицию.
    4. Если сигнал противоположный — закрывает позицию.
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        commission_pct: float = 0.0003,  # 0.03% за сторону
        lot_size: int = 1,
    ):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.lot_size = lot_size
        self._indicators = IndicatorEngine()
        self._rules = RulesEngine()
        self._risk = RiskManager()

    def run(self, ticker: str, df: pd.DataFrame) -> BacktestResult:
        """
        Запустить бэктест на переданном DataFrame.

        df должен содержать колонки: open, high, low, close, volume.
        """
        result = BacktestResult(ticker=ticker)
        if df.empty or len(df) < 50:
            logger.warning("Недостаточно данных для бэктеста %s: %d строк", ticker, len(df))
            return result

        df_ind = self._indicators.compute(df)
        capital = self.initial_capital
        peak_capital = capital
        open_trade: Optional[BacktestTrade] = None

        equity: list[float] = [capital]

        for i in range(50, len(df_ind)):
            row = df_ind.iloc[i]
            price = float(row["close"])
            _atr_raw = row.get("atr")
            atr = float(_atr_raw) if _atr_raw is not None and pd.notna(_atr_raw) else price * 0.01

            # Проверка стоп-лосса
            if open_trade and price <= open_trade.stop_price:
                pnl, capital = self._close_trade(open_trade, price, capital, "STOPPED")
                result.trades.append(open_trade)
                result.losing_trades += 1
                result.total_pnl += pnl
                open_trade = None

            # Вычислить сигнал для текущей свечи
            window = df_ind.iloc[max(0, i - 60): i + 1]
            iv = self._indicators.latest(window)
            signal = self._rules.evaluate(iv)

            if open_trade is None and signal.action == Action.BUY:
                pos = self._risk.calculate_position(
                    ticker=ticker,
                    entry_price=price,
                    atr=atr,
                    portfolio_value=capital,
                    lot_size=self.lot_size,
                )
                if pos and pos.position_value <= capital:
                    commission = pos.position_value * self.commission_pct
                    capital -= pos.position_value + commission
                    open_trade = BacktestTrade(
                        ticker=ticker,
                        entry_date=row.name if hasattr(row, "name") else datetime.now(),
                        entry_price=price,
                        shares=pos.shares,
                        stop_price=pos.stop_price,
                    )
                    result.total_trades += 1

            elif open_trade is not None and signal.action == Action.SELL:
                pnl, capital = self._close_trade(open_trade, price, capital, "WIN" if price > open_trade.entry_price else "LOSS")
                result.trades.append(open_trade)
                if pnl > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1
                result.total_pnl += pnl
                open_trade = None

            # Скользящий стоп для открытой позиции
            if open_trade and atr > 0:
                new_stop = price - atr * self._risk.cfg.atr_stop_multiplier
                if new_stop > open_trade.stop_price:
                    open_trade.stop_price = new_stop

            # Учёт нереализованного PnL для equity curve
            current_equity = capital
            if open_trade:
                unrealized = (price - open_trade.entry_price) * open_trade.shares
                current_equity += open_trade.entry_price * open_trade.shares + unrealized
            equity.append(current_equity)
            peak_capital = max(peak_capital, current_equity)

        # Принудительно закрыть открытую позицию на последней свече
        if open_trade:
            last_price = float(df_ind.iloc[-1]["close"])
            pnl, capital = self._close_trade(open_trade, last_price, capital, "WIN" if last_price > open_trade.entry_price else "LOSS")
            result.trades.append(open_trade)
            result.total_pnl += pnl
            if pnl > 0:
                result.winning_trades += 1
            else:
                result.losing_trades += 1

        result.equity_curve = equity
        result.win_rate = (
            result.winning_trades / result.total_trades * 100
            if result.total_trades else 0.0
        )
        result.avg_pnl = (
            result.total_pnl / result.total_trades
            if result.total_trades else 0.0
        )
        result.max_drawdown = self._calc_max_drawdown(equity)
        result.sharpe = self._calc_sharpe(equity)

        logger.info(result.summary())
        return result

    def _close_trade(
        self,
        trade: BacktestTrade,
        exit_price: float,
        capital: float,
        status: str,
    ) -> tuple[float, float]:
        commission = trade.shares * exit_price * self.commission_pct
        proceeds = trade.shares * exit_price - commission
        capital += proceeds
        pnl = (exit_price - trade.entry_price) * trade.shares - commission
        trade.exit_price = exit_price
        trade.exit_date = datetime.now()
        trade.pnl = pnl
        trade.pnl_pct = pnl / (trade.entry_price * trade.shares)
        trade.status = status
        return pnl, capital

    @staticmethod
    def _calc_max_drawdown(equity: list[float]) -> float:
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100 if peak else 0
            max_dd = max(max_dd, dd)
        return max_dd

    @staticmethod
    def _calc_sharpe(equity: list[float], risk_free: float = 0.16) -> float:
        """Приближённый коэффициент Шарпа (дневная безрисковая ставка 16% годовых)."""
        if len(equity) < 2:
            return 0.0
        returns = pd.Series(equity).pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        daily_rf = risk_free / 252
        excess = returns.mean() - daily_rf
        return float(excess / returns.std() * (252 ** 0.5))


backtest_engine = BacktestEngine()
