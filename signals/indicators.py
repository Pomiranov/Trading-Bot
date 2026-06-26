"""Технические индикаторы с использованием библиотеки ta."""

import logging
from dataclasses import dataclass

import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, ADXIndicator, CCIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice

logger = logging.getLogger(__name__)


@dataclass
class IndicatorValues:
    """Снимок значений всех индикаторов для одной свечи."""
    rsi: float = float("nan")
    macd: float = float("nan")
    macd_signal: float = float("nan")
    macd_hist: float = float("nan")
    ema_fast: float = float("nan")
    ema_slow: float = float("nan")
    atr: float = float("nan")
    bb_upper: float = float("nan")
    bb_middle: float = float("nan")
    bb_lower: float = float("nan")
    bb_pct: float = float("nan")
    adx: float = float("nan")
    adx_pos: float = float("nan")
    adx_neg: float = float("nan")
    vwap: float = float("nan")
    close: float = float("nan")

    @property
    def macd_bullish_cross(self) -> bool:
        return self.macd > self.macd_signal and self.macd_hist > 0

    @property
    def macd_bearish_cross(self) -> bool:
        return self.macd < self.macd_signal and self.macd_hist < 0

    @property
    def price_above_ema_fast(self) -> bool:
        return self.close > self.ema_fast

    @property
    def price_above_ema_slow(self) -> bool:
        return self.close > self.ema_slow

    @property
    def trend_strong(self) -> bool:
        return self.adx > 25

    @property
    def rsi_oversold(self) -> bool:
        return self.rsi < 30

    @property
    def rsi_overbought(self) -> bool:
        return self.rsi > 70


class IndicatorEngine:
    """Вычисляет технические индикаторы для переданного DataFrame OHLCV."""

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        ema_fast: int = 9,
        ema_slow: int = 21,
        atr_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        adx_period: int = 14,
    ):
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal_period = macd_signal
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.adx_period = adx_period

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Добавить все индикаторы в DataFrame.

        Входной DataFrame должен содержать колонки: open, high, low, close, volume.
        """
        if df.empty or len(df) < self.macd_slow + self.macd_signal_period:
            logger.warning("Слишком мало данных для расчёта индикаторов: %d строк", len(df))
            return df

        out = df.copy()

        # RSI
        rsi = RSIIndicator(close=out["close"], window=self.rsi_period)
        out["rsi"] = rsi.rsi()

        # MACD
        macd = MACD(
            close=out["close"],
            window_fast=self.macd_fast,
            window_slow=self.macd_slow,
            window_sign=self.macd_signal_period,
        )
        out["macd"] = macd.macd()
        out["macd_signal"] = macd.macd_signal()
        out["macd_hist"] = macd.macd_diff()

        # EMA
        out["ema_fast"] = EMAIndicator(close=out["close"], window=self.ema_fast).ema_indicator()
        out["ema_slow"] = EMAIndicator(close=out["close"], window=self.ema_slow).ema_indicator()

        # ATR
        atr = AverageTrueRange(
            high=out["high"],
            low=out["low"],
            close=out["close"],
            window=self.atr_period,
        )
        out["atr"] = atr.average_true_range()

        # Bollinger Bands
        bb = BollingerBands(close=out["close"], window=self.bb_period, window_dev=self.bb_std)
        out["bb_upper"] = bb.bollinger_hband()
        out["bb_middle"] = bb.bollinger_mavg()
        out["bb_lower"] = bb.bollinger_lband()
        out["bb_pct"] = bb.bollinger_pband()

        # ADX
        adx = ADXIndicator(
            high=out["high"],
            low=out["low"],
            close=out["close"],
            window=self.adx_period,
        )
        out["adx"] = adx.adx()
        out["adx_pos"] = adx.adx_pos()
        out["adx_neg"] = adx.adx_neg()

        # VWAP (требует datetime-индекс)
        if "volume" in out.columns and hasattr(out.index, "hour"):
            try:
                vwap = VolumeWeightedAveragePrice(
                    high=out["high"],
                    low=out["low"],
                    close=out["close"],
                    volume=out["volume"],
                )
                out["vwap"] = vwap.volume_weighted_average_price()
            except Exception as exc:
                logger.debug("VWAP не вычислен: %s", exc)
                out["vwap"] = float("nan")
        else:
            out["vwap"] = float("nan")

        return out

    def latest(self, df: pd.DataFrame) -> IndicatorValues:
        """Вернуть значения индикаторов для последней свечи."""
        computed = self.compute(df)
        if computed.empty:
            return IndicatorValues()

        row = computed.iloc[-1]

        def _get(col: str) -> float:
            return float(row[col]) if col in row.index else float("nan")

        return IndicatorValues(
            rsi=_get("rsi"),
            macd=_get("macd"),
            macd_signal=_get("macd_signal"),
            macd_hist=_get("macd_hist"),
            ema_fast=_get("ema_fast"),
            ema_slow=_get("ema_slow"),
            atr=_get("atr"),
            bb_upper=_get("bb_upper"),
            bb_middle=_get("bb_middle"),
            bb_lower=_get("bb_lower"),
            bb_pct=_get("bb_pct"),
            adx=_get("adx"),
            adx_pos=_get("adx_pos"),
            adx_neg=_get("adx_neg"),
            vwap=_get("vwap"),
            close=_get("close"),
        )


indicator_engine = IndicatorEngine()
