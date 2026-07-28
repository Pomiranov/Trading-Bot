"""Событийный бэктестер на дневных/часовых свечах.

Логика на каждой свече:
  1. Проверить стоп-лосс открытой позиции.
  2. Если позиция открыта — проверить exit_rules (evaluate_exit).
  3. Оценить основной сигнал (evaluate).
     BLOCK / HOLD — не открывать новую позицию.
     BUY при отсутствии позиции — открыть.
     SELL при наличии позиции — закрыть.
  4. Обновить trailing stop.
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pandas as pd

from costs import COMMISSION_PCT
from market_time import last_closed_index
from signals.indicators import IndicatorEngine, structural_downtrend_series
from signals.rules_engine import RulesEngine, Action, classify_regime
from risk.risk_manager import RiskManager
from learning.trading_orchestrator import TradingOrchestrator
from learning.memory_writer import (
    Trade as LearningTrade,
    Market,
    Direction,
    MarketRegime,
    ExitReasonType,
)

logger = logging.getLogger(__name__)

# Все сделки бэктеста относятся к трендовой стратегии MOEX
# (rules.yaml содержит только трендовые правила)
BACKTEST_STRATEGY_ID = "trend_moex"


@dataclass
class BacktestTrade:
    ticker: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    shares: int = 0
    stop_price: float = 0.0
    initial_risk: float = 0.0   # R = вход − первоначальный стоп (для целей 2R/безубытка)
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: str = "OPEN"   # OPEN / WIN / LOSS / STOPPED / TARGET
    entry_rules: str = ""  # имена правил, открывших сделку (для анализа)
    learning_trade: Optional[LearningTrade] = None   # зеркальная запись для learning/


@dataclass
class BacktestResult:
    ticker: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    profit_factor: float = 0.0
    cagr: float = 0.0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    trading_days: int = 0
    skipped_downtrend: int = 0   # BUY-сигналы, отклонённые фильтром структурного даунтренда
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.ticker}] Сделок: {self.total_trades} | "
            f"Win Rate: {self.win_rate:.1f}% | "
            f"PnL: {self.total_pnl:+,.0f} руб. | "
            f"Просадка: {self.max_drawdown:.1f}% | "
            f"Sharpe: {self.sharpe:.2f} | "
            f"PF: {self.profit_factor:.2f} | "
            f"CAGR: {self.cagr:+.1f}%"
        )


class BacktestEngine:
    """
    Событийный бэктестер.

    Принимает опциональный rules_engine для поддержки режима сравнения
    «до» (extended=False) и «после» (extended=True).
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        commission_pct: float = COMMISSION_PCT,   # см. bot/costs.py
        lot_size: int = 1,
        rules_engine: Optional[RulesEngine] = None,
        orchestrator: Optional[TradingOrchestrator] = None,
        strategy_id: str = BACKTEST_STRATEGY_ID,
        timeframe: str = "H1",
        breakeven_r: Optional[float] = None,   # прибыль ≥ N·R → стоп в безубыток (Швагер, гл. 15)
        target_r: Optional[float] = None,      # прибыль ≥ N·R → фиксация по цели
        use_stops: bool = True,                # False = чистый SAR (Швагер, гл. 18): стоп и
                                               # трейлинг не исполняются, выход только по сигналу;
                                               # сайзинг по стоп-дистанции сохраняется
    ):
        self.initial_capital = initial_capital
        self.commission_pct  = commission_pct
        self.lot_size        = lot_size
        self._rules          = rules_engine if rules_engine is not None else RulesEngine()
        # Параметры индикаторов: секция indicators (периоды EMA и т.п.)
        # + секция divergence (детектор расхождений) rules-файла
        self._indicators     = IndicatorEngine(**{
            **getattr(self._rules, "indicator_params", {}),
            **getattr(self._rules, "divergence_params", {}),
            **getattr(self._rules, "swing_stop_params", {}),
            **getattr(self._rules, "wrd_params", {}),
        })
        self._risk           = RiskManager()
        self._strategy_id    = strategy_id
        self._timeframe      = timeframe
        self._breakeven_r    = breakeven_r
        self._target_r       = target_r
        self._use_stops      = use_stops

        # Опциональный оркестратор обучения: каждая открытая/закрытая
        # сделка бэктеста зеркалируется в learning/ (sandbox-режим).
        self._orchestrator   = orchestrator
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._orch_connected = False

    # ── Мост sync-бэктест → async-оркестратор ────────────────────────

    def _learn(self, coro):
        """Выполнить корутину оркестратора из синхронного кода бэктеста."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)

    def _connect_orchestrator(self) -> None:
        if self._orchestrator is not None and not self._orch_connected:
            self._learn(self._orchestrator.connect())
            self._orch_connected = True

    def run_full_learning_cycle(self) -> dict:
        """Запустить полный цикл обучения после бэктеста."""
        if self._orchestrator is None:
            return {}
        self._connect_orchestrator()
        return self._learn(self._orchestrator.run_full_learning_cycle())

    def shutdown_learning(self) -> None:
        """Отключить оркестратор и закрыть служебный event loop."""
        if self._orchestrator is not None and self._orch_connected:
            self._learn(self._orchestrator.disconnect())
            self._orch_connected = False
        if self._loop is not None:
            self._loop.close()
            self._loop = None

    def run(self, ticker: str, df: pd.DataFrame) -> BacktestResult:
        """Запустить бэктест. df должен содержать: open, high, low, close, volume."""
        result = BacktestResult(ticker=ticker)
        df = self._drop_forming_bar(ticker, df)
        if df.empty or len(df) < 50:
            logger.warning("Недостаточно данных: %s (%d строк)", ticker, len(df))
            return result

        self._connect_orchestrator()

        df_ind = self._indicators.compute(df)
        # Отношение объёма к среднему за 20 свечей — для market_features
        vol_ma = df_ind["volume"].rolling(20).mean() if "volume" in df_ind.columns else None

        # Фильтр структурного даунтренда (из yaml стратегии; None = выключен).
        # apply_to: long — движок и так открывает только лонги.
        dt_gate = self._downtrend_gate(df, df_ind.index)

        capital      = self.initial_capital
        open_trade: Optional[BacktestTrade] = None
        equity: list[float] = [capital]

        for i in range(50, len(df_ind)):
            row   = df_ind.iloc[i]
            price = float(row["close"])
            _atr  = row.get("atr")
            atr   = float(_atr) if _atr is not None and pd.notna(_atr) else price * 0.01
            dt    = row.name if hasattr(row, "name") else datetime.now()

            # ── 1. Стоп-лосс ─────────────────────────────────────────
            if self._use_stops and open_trade and price <= open_trade.stop_price:
                pnl, capital = self._close(open_trade, price, capital, "STOPPED", exit_dt=dt)
                result.trades.append(open_trade)
                result.losing_trades += 1
                result.total_pnl += pnl
                open_trade = None

            # ── 1б. Ведение позиции по R (Швагер, гл. 15) ────────────
            if open_trade and open_trade.initial_risk > 0:
                r_mult = (price - open_trade.entry_price) / open_trade.initial_risk
                if self._target_r is not None and r_mult >= self._target_r:
                    pnl, capital = self._close(open_trade, price, capital, "TARGET", exit_dt=dt)
                    result.trades.append(open_trade)
                    result.winning_trades += 1
                    result.total_pnl += pnl
                    open_trade = None
                elif self._breakeven_r is not None and r_mult >= self._breakeven_r:
                    if open_trade.stop_price < open_trade.entry_price:
                        open_trade.stop_price = open_trade.entry_price

            # ── 2. Правила выхода (exit_rules) ───────────────────────
            if open_trade:
                window     = df_ind.iloc[max(0, i - 60): i + 1]
                iv         = self._indicators.latest_precomputed(window)
                exit_sig   = self._rules.evaluate_exit(iv, ticker)
                if exit_sig.action == Action.EXIT:
                    status = "WIN" if price > open_trade.entry_price else "LOSS"
                    pnl, capital = self._close(open_trade, price, capital, status, exit_dt=dt)
                    result.trades.append(open_trade)
                    result.winning_trades += (1 if pnl > 0 else 0)
                    result.losing_trades  += (0 if pnl > 0 else 1)
                    result.total_pnl += pnl
                    open_trade = None

            # ── 3. Основной сигнал ────────────────────────────────────
            window = df_ind.iloc[max(0, i - 60): i + 1]
            iv     = self._indicators.latest_precomputed(window)
            signal = self._rules.evaluate(iv, ticker)

            # BLOCK → не открываем новые позиции
            if (
                open_trade is None and signal.action == Action.BUY
                and dt_gate is not None and bool(dt_gate.iloc[i])
            ):
                result.skipped_downtrend += 1
            elif open_trade is None and signal.action == Action.BUY:
                pos = self._risk.calculate_position(
                    ticker=ticker,
                    entry_price=price,
                    atr=atr,
                    portfolio_value=capital,
                    lot_size=self.lot_size,
                )
                if pos and pos.position_value <= capital:
                    commission  = pos.position_value * self.commission_pct
                    capital    -= pos.position_value + commission
                    open_trade  = BacktestTrade(
                        ticker=ticker,
                        entry_date=dt,
                        entry_price=price,
                        shares=pos.shares,
                        stop_price=pos.stop_price,
                        initial_risk=max(price - pos.stop_price, 0.0),
                        entry_rules="+".join(sorted(
                            r.name for r in signal.triggered_rules
                            if r.action == Action.BUY
                        )),
                    )
                    result.total_trades += 1

                    # ── Обучение: зафиксировать открытие сделки ──────
                    if self._orchestrator is not None:
                        volume_ratio = None
                        if vol_ma is not None:
                            ma = vol_ma.iloc[i]
                            vol = row.get("volume")
                            if pd.notna(ma) and ma and vol is not None and pd.notna(vol):
                                volume_ratio = float(vol) / float(ma)
                        open_trade.learning_trade = self._build_learning_trade(
                            ticker=ticker,
                            row=row,
                            price=price,
                            shares=pos.shares,
                            stop_price=pos.stop_price,
                            capital=capital + pos.position_value + commission,
                            signal=signal,
                            volume_ratio=volume_ratio,
                            opened_at=dt,
                            iv=iv,
                        )
                        self._learn(
                            self._orchestrator.on_trade_opened(open_trade.learning_trade)
                        )

            elif open_trade is not None and signal.action == Action.SELL:
                status = "WIN" if price > open_trade.entry_price else "LOSS"
                pnl, capital = self._close(open_trade, price, capital, status, exit_dt=dt)
                result.trades.append(open_trade)
                result.winning_trades += (1 if pnl > 0 else 0)
                result.losing_trades  += (0 if pnl > 0 else 1)
                result.total_pnl += pnl
                open_trade = None

            # ── 4. Trailing stop ──────────────────────────────────────
            if self._use_stops and open_trade and atr > 0:
                new_stop = price - atr * self._risk.cfg.atr_stop_multiplier
                if new_stop > open_trade.stop_price:
                    open_trade.stop_price = new_stop

            # ── Equity curve ──────────────────────────────────────────
            cur_equity = capital
            if open_trade:
                unrealized  = (price - open_trade.entry_price) * open_trade.shares
                cur_equity += open_trade.entry_price * open_trade.shares + unrealized
            equity.append(cur_equity)

        # Принудительно закрыть открытую позицию на последней свече
        if open_trade:
            last_price = float(df_ind.iloc[-1]["close"])
            last_dt    = df_ind.index[-1] if len(df_ind.index) else None
            status = "WIN" if last_price > open_trade.entry_price else "LOSS"
            pnl, capital = self._close(open_trade, last_price, capital, status, exit_dt=last_dt)
            result.trades.append(open_trade)
            result.total_pnl += pnl
            result.winning_trades += (1 if pnl > 0 else 0)
            result.losing_trades  += (0 if pnl > 0 else 1)

        # ── Финальные метрики ─────────────────────────────────────────
        result.equity_curve  = equity
        total = result.total_trades
        result.win_rate      = result.winning_trades / total * 100 if total else 0.0
        result.avg_pnl       = result.total_pnl / total if total else 0.0
        result.max_drawdown  = self._max_drawdown(equity)
        result.sharpe        = self._sharpe(equity)
        result.profit_factor = self._profit_factor(result.trades)
        result.trading_days  = max(len(equity) // 8, 1)
        result.cagr          = self._cagr(equity[0], equity[-1], result.trading_days)

        logger.info(result.summary())
        return result

    # ── Незакрытая сессия ────────────────────────────────────────────

    def _drop_forming_bar(self, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
        """Обрезать бар сегодняшней (ещё формирующейся) московской сессии.

        Обрезка стоит ДО расчёта индикаторов — одним местом, потому что дальше
        от df зависят и индикаторы, и vol_ma, и фильтр даунтренда, и
        принудительное закрытие позиции на последнем баре. Значения на более
        ранних барах она изменить не может: все индикаторы причинные, что
        отдельно проверено тестом «нарезка окон ≡ пересчёт на префиксе»
        (tests/forward_tests/test_forward_catchup.py, T8).

        Почему это не косметика — см. market_time.last_closed_index: на
        частичном баре движок принудительно закрывал открытую позицию и писал
        её в n/WR/PF/PnL как состоявшуюся сделку по цене незакрытой сессии.
        Форвард от этого защищён с долга №14, бэктест — с 2026-07-28.

        Наивный индекс трактуется как UTC: так его отдают все скрипты
        бэктеста (`r["time"].replace(tzinfo=None)` над timestamptz из БД).
        """
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            return df
        index = df.index.tz_localize("UTC") if df.index.tz is None else df.index
        last = last_closed_index(list(index))
        if last == len(df) - 1:
            return df
        logger.info("[%s] Незакрытая сессия отброшена: %d бар(ов) из %d",
                    ticker, len(df) - 1 - last, len(df))
        return df.iloc[:last + 1]

    # ── Фильтр структурного даунтренда ───────────────────────────────

    def _downtrend_gate(self, df: pd.DataFrame, index: pd.Index) -> Optional[pd.Series]:
        """Булева серия «лонги запрещены» на индексе бэктеста.

        Конфиг берётся из rules-файла стратегии (filters.structural_downtrend);
        серия считается по D1 независимо от таймфрейма сигнала — не-D1
        данные ресемплируются в дневные.
        """
        cfg = getattr(self._rules, "structural_downtrend_filter", {}) or {}
        if not cfg:
            return None
        d1 = df
        if self._timeframe != "D1":
            d1 = df.resample("1D").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum",
            }).dropna(subset=["close"])
        params = {
            k: cfg[k]
            for k in ("sma_short", "sma_long", "lower_low_lookback", "lower_low_window")
            if k in cfg
        }
        series = structural_downtrend_series(d1, **params)
        return series.reindex(index, method="ffill").fillna(False).astype(bool)

    # ── Закрытие сделки ──────────────────────────────────────────────

    def _close(
        self,
        trade: BacktestTrade,
        exit_price: float,
        capital: float,
        status: str,
        exit_dt=None,
    ) -> tuple[float, float]:
        exit_comm     = trade.shares * exit_price * self.commission_pct
        proceeds      = trade.shares * exit_price - exit_comm
        capital      += proceeds
        # pnl вычитает ОБЕ стороны. Комиссия входа уже списана с capital при
        # открытии (строка 253 в run()), но в pnl не попадала, поэтому
        # initial_capital + Σpnl не сходился с траекторией капитала — а именно
        # на этом равенстве стоит потикерный бюджет форварда (_paper_capital).
        # Траектория capital здесь НЕ меняется: она была верна и до правки.
        entry_comm    = trade.entry_price * trade.shares * self.commission_pct
        commission    = entry_comm + exit_comm
        pnl           = (exit_price - trade.entry_price) * trade.shares - commission
        trade.exit_price = exit_price
        trade.exit_date  = exit_dt if exit_dt is not None else datetime.now()
        trade.pnl        = pnl
        trade.pnl_pct    = pnl / (trade.entry_price * trade.shares) if trade.entry_price * trade.shares else 0.0
        trade.status     = status

        # ── Обучение: закрыть сделку и запустить цикл обучения ────────
        if self._orchestrator is not None and trade.learning_trade is not None:
            lt = trade.learning_trade
            lt.exit_price       = self._dec(exit_price)
            lt.closed_at        = self._to_utc(trade.exit_date)
            lt.pnl              = self._dec(pnl)
            lt.commission       = self._dec(commission)
            lt.exit_reason_type = (
                ExitReasonType.STOP_LOSS if status == "STOPPED"
                else ExitReasonType.TAKE_PROFIT if status == "TARGET"
                else ExitReasonType.SIGNAL
            )
            lt.exit_reason = f"Бэктест: выход со статусом {status}"
            self._learn(self._orchestrator.on_trade_closed(lt))

        return pnl, capital

    # ── Зеркальная сделка для learning/ ──────────────────────────────

    @staticmethod
    def _dec(value: float) -> Decimal:
        """float → Decimal без артефактов двоичного представления."""
        return Decimal(str(round(float(value), 6)))

    @staticmethod
    def _to_utc(dt) -> datetime:
        """Свечная дата (pandas Timestamp, наивная) → tz-aware UTC."""
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()
        if not isinstance(dt, datetime):
            return datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _regime_from_adx(adx: Optional[float]) -> Optional[MarketRegime]:
        """Классификация режима рынка по ADX (общая с rules_engine)."""
        regime = classify_regime(adx)
        return MarketRegime(regime) if regime else None

    def _build_learning_trade(
        self,
        ticker: str,
        row,
        price: float,
        shares: int,
        stop_price: float,
        capital: float,
        signal,
        volume_ratio: Optional[float],
        opened_at,
        iv=None,
    ) -> LearningTrade:
        """Собрать learning-сделку из контекста бэктеста (sandbox).

        iv — IndicatorValues сигнального окна: оттуда берётся осцилляторный
        контекст (кворум расхождений), которого нет в колонках row."""

        def _feat(col: str) -> Optional[float]:
            val = row.get(col)
            if val is None or not pd.notna(val):
                return None
            val = float(val)
            return val if math.isfinite(val) else None

        entry  = self._dec(price)
        stop   = self._dec(stop_price)
        n      = Decimal(int(shares))
        risk   = (entry - stop) * n
        if risk <= 0:
            risk = entry * Decimal("0.01") * n   # запасной риск 1% от входа

        features = {
            "rsi":    _feat("rsi"),
            "atr":    _feat("atr"),
            "adx":    _feat("adx"),
            "bb_pct": _feat("bb_pct"),
            "volume_ratio": round(volume_ratio, 4) if volume_ratio is not None else None,
        }
        # Кворум расхождений сигнального окна (0-3) — чтобы hypothesis_engine
        # мог коррелировать исход сделки с силой дивергенции
        if iv is not None:
            for attr in ("bull_div_count", "bear_div_count"):
                val = getattr(iv, attr, float("nan"))
                if val is not None and math.isfinite(val):
                    features[attr] = float(val)
        features = {k: v for k, v in features.items() if v is not None}

        conf = getattr(signal, "confidence", None)
        confidence = (
            self._dec(min(max(conf, 0.0), 1.0))
            if conf is not None and math.isfinite(conf) else None
        )

        return LearningTrade(
            market          = Market.STOCKS,
            ticker          = ticker,
            direction       = Direction.BUY,
            strategy_id     = self._strategy_id,
            entry_price     = entry,
            stop_loss       = stop,
            position_size   = n,
            risk_amount     = risk,
            risk_percent    = (risk / self._dec(capital)).quantize(Decimal("0.0001"))
                              if capital > 0 else None,
            opened_at       = self._to_utc(opened_at),
            timeframe       = self._timeframe,
            market_regime   = self._regime_from_adx(_feat("adx")),
            market_features = features or None,
            confidence      = confidence,
            entry_reason    = getattr(signal, "reason", "") or "Сигнал BUY бэктеста",
            is_sandbox      = True,
        )

    # ── Статические метрики ──────────────────────────────────────────

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        if not equity:
            return 0.0
        peak   = equity[0]
        max_dd = 0.0
        for val in equity:
            peak   = max(peak, val)
            dd     = (peak - val) / peak * 100 if peak else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    @staticmethod
    def _sharpe(equity: list[float], risk_free: float = 0.16) -> float:
        """Приближённый Sharpe (безрисковая ставка 16% годовых)."""
        if len(equity) < 2:
            return 0.0
        returns = pd.Series(equity).pct_change().dropna()
        std = returns.std()
        if std == 0:
            return 0.0
        daily_rf = risk_free / 252
        return float((returns.mean() - daily_rf) / std * (252 ** 0.5))

    @staticmethod
    def _profit_factor(trades: list[BacktestTrade]) -> float:
        wins   = sum(t.pnl for t in trades if t.pnl > 0)
        losses = abs(sum(t.pnl for t in trades if t.pnl <= 0))
        if losses == 0:
            return float("inf") if wins > 0 else 0.0
        return round(wins / losses, 3)

    @staticmethod
    def _cagr(initial: float, final: float, trading_days: int) -> float:
        if initial <= 0 or final <= 0 or trading_days <= 0:
            return 0.0
        years = trading_days / 252
        return round(((final / initial) ** (1.0 / years) - 1) * 100, 2)


backtest_engine = BacktestEngine()
