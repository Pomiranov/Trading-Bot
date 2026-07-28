"""Технические индикаторы с использованием библиотеки ta."""

import logging
import math
from dataclasses import dataclass

import numpy as np
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

    # ── Осцилляторный блок (Швагер/Бировиц, гл. 15) ──
    rsi9: float = float("nan")          # RSI(9) — параметр Бировица
    stoch_k: float = float("nan")       # медленный стохастик %K (14-3)
    stoch_d: float = float("nan")       # медленный %D (SMA3 от %K)
    mac_high: float = float("nan")      # КСС: EMA(High, 28) — верхняя граница
    mac_low: float = float("nan")       # КСС: EMA(Low, 28) — нижняя граница
    bull_div_count: float = float("nan")  # на скольких из 3 осц. бычье расхождение
    bear_div_count: float = float("nan")  # ... медвежье расхождение
    micro_w_trigger: float = float("nan") # максимум пары «бар вверх+вниз» после бычьего расх.
    micro_m_trigger: float = float("nan") # минимум пары «бар вниз+вверх» после медвежьего расх.
    div_low: float = float("nan")       # минимум цены в точке бычьего расхождения (для стопа)
    div_high: float = float("nan")      # максимум цены в точке медвежьего расхождения

    # ── Трейлинг по относительным минимумам (Швагер, гл. 9, метод 5) ──
    swing_low: float = float("nan")     # последний подтверждённый свинг-минимум

    # ── Система ШД-дня (Швагер, гл. 18, стр. 651-661) ──
    ptr_high: float = float("nan")      # верхняя граница действующего PTR
    ptr_low: float = float("nan")       # нижняя граница действующего PTR

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


# ── Структурный даунтренд (фильтр для mean-reversion лонгов) ──────────────
#
# Осцилляторная стратегия покупает «перепроданность»; в многолетнем
# даунтренде (GAZP −46% за 2023-2026) это книжная «катастрофа в тренде»
# (Швагер, гл. 15). Фильтр отличает структурный даунтренд от обычной
# просадки внутри диапазона: нужны ВСЕ ТРИ условия одновременно.

def structural_downtrend_series(
    df_d1: pd.DataFrame,
    sma_short: int = 50,
    sma_long: int = 200,
    lower_low_lookback: int = 120,
    lower_low_window: int = 20,
) -> pd.Series:
    """Булева серия «бар находится в структурном даунтренде» по D1-данным.

    Условия (все одновременно):
      1. close < SMA(close, sma_long)                 — цена под долгосрочной средней
      2. SMA(close, sma_short) < SMA(close, sma_long) — мёртвый крест средних
      3. close < min(close за lower_low_window дней,
                     закончившихся lower_low_lookback дней назад)
                                                      — обновлён минимум полугодовой давности

    Считается ТОЛЬКО по D1 независимо от таймфрейма сигнала.
    NaN (недостаточно истории) трактуется как False — фильтр не активен.
    """
    close = df_d1["close"]
    sma_l = close.rolling(sma_long).mean()
    sma_s = close.rolling(sma_short).mean()
    # окно из lower_low_window баров, заканчивающееся lower_low_lookback баров назад
    ref_min = close.rolling(lower_low_window).min().shift(
        lower_low_lookback - lower_low_window + 1
    )
    mask = (close < sma_l) & (sma_s < sma_l) & (close < ref_min)
    return mask.fillna(False)


def is_structural_downtrend(df_d1: pd.DataFrame, **params) -> bool:
    """Структурный даунтренд на последней D1-свече (для live-проверки сигнала)."""
    if df_d1.empty or len(df_d1) < params.get("sma_long", 200):
        return False
    return bool(structural_downtrend_series(df_d1, **params).iloc[-1])


# ── Окно сигнала ──────────────────────────────────────────────────────────

# Окно latest_precomputed по умолчанию: 61 бар = iloc[i-60 : i+1] бэктеста.
SIGNAL_WINDOW_BARS = 61


def signal_window(computed: pd.DataFrame, i: int, bars: int = SIGNAL_WINDOW_BARS) -> pd.DataFrame:
    """Окно сигнала, заканчивающееся РОВНО на баре i: iloc[max(0, i-bars+1) : i+1].

    Окно ОБЯЗАНО заканчиваться на текущем баре. `_oscillator_context` считает
    пивоты и микро-триггеры относительно КОНЦА окна (pivots → range(k, n-k),
    divergence → n-1-p2, micro_trigger → closes[i+2:n-1]), поэтому окно,
    заканчивающееся позже бара i, молча даёт заглядывание в будущее, а
    заканчивающееся раньше — считает сигнал не по тому бару.

    Сами индикаторы `compute()` строго причинные (rolling/ewm назад,
    swing_low через .shift(n), ШД-ATR через .shift(1), PTR с eff = i+n2+1),
    поэтому посчитать их один раз по всей истории и затем нарезать окна —
    то же самое, что пересчитывать на каждом префиксе, но за O(n) вместо
    O(n²). Ровно так делает бэктест (backtest/engine.py:220, 233).
    """
    return computed.iloc[max(0, i - bars + 1): i + 1]


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
        pivot_strength: int = 3,
        pivot_max_age: int = 25,
        pair_search_max: int = 20,
        swing_stop_window: int = 0,
        wrd_k: float = 0.0,
        wrd_atr_n: int = 10,
        wrd_n1: int = 0,
        wrd_n2: int = 0,
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
        # Детектор расхождений (Швагер/Бировиц, гл. 15) — см.
        # knowledge/processed/technical/oscillator_divergence.md;
        # значения обычно приходят из секции divergence rules-файла стратегии
        self.pivot_strength  = pivot_strength
        self.pivot_max_age   = pivot_max_age
        self.pair_search_max = pair_search_max
        # Трейлинг по свинг-минимумам (Швагер, гл. 9, метод 5, N=5..15);
        # 0 = выключен (колонка swing_low не считается) — задаётся секцией
        # swing_stop rules-файла стратегии
        self.swing_stop_window = swing_stop_window
        # Система ШД-дня (Швагер, гл. 18): k — порог VR, atr_n — период
        # среднего истинного диапазона в знаменателе VR, n1/n2 — границы
        # сигнального диапазона PTR вокруг ШД-дня. k=0 — выключено
        # (колонки wrd_day/ptr_high/ptr_low не считаются) — задаётся
        # секцией wrd rules-файла стратегии
        self.wrd_k     = wrd_k
        self.wrd_atr_n = wrd_atr_n
        self.wrd_n1    = wrd_n1
        self.wrd_n2    = wrd_n2

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

        # ── Осцилляторный блок (Швагер/Бировиц, гл. 15) ──

        # RSI(9)
        out["rsi9"] = RSIIndicator(close=out["close"], window=9).rsi()

        # Медленный стохастик 14-3-3: fast %K → SMA3 = slow %K → SMA3 = slow %D
        stoch = StochasticOscillator(
            high=out["high"], low=out["low"], close=out["close"],
            window=14, smooth_window=3,
        )
        slow_k = stoch.stoch_signal()          # сглаженный %K
        out["stoch_k"] = slow_k
        out["stoch_d"] = slow_k.rolling(3).mean()

        # Коридор скользящих средних (КСС): EMA28 максимумов и минимумов
        out["mac_high"] = EMAIndicator(close=out["high"], window=28).ema_indicator()
        out["mac_low"]  = EMAIndicator(close=out["low"],  window=28).ema_indicator()

        # ── Свинг-минимумы (Швагер, гл. 9, метод 5) ──
        # Пивот = минимум среди ±N соседних баров; подтверждается лишь
        # через N баров после экстремума (сноска стр. 168) — сдвиг shift(N)
        # публикует уровень только на баре подтверждения (без lookahead).
        if self.swing_stop_window > 0:
            n = self.swing_stop_window
            lows = out["low"]
            is_pivot = lows == lows.rolling(2 * n + 1, center=True).min()
            out["swing_low"] = lows.where(is_pivot).shift(n).ffill()

        # ── Система ШД-дня (Швагер, гл. 18, стр. 651-661) ──
        # Считается по ПОЛНОЙ истории: PTR живёт до следующего ШД-дня
        # (у автора — до полугода), 60-барное окно бэктеста его не покрывает.
        if self.wrd_k > 0:
            prev_close = out["close"].shift(1)
            # истинные max/min/диапазон (гл. 3; сноски стр. 114, 651)
            true_high  = pd.concat([out["high"], prev_close], axis=1).max(axis=1)
            true_low   = pd.concat([out["low"],  prev_close], axis=1).min(axis=1)
            true_range = true_high - true_low
            # ШД-день: VR = TR дня / средний TR ПРЕДШЕСТВУЮЩИХ atr_n дней > k.
            # Знаменатель — средний истинный диапазон (≈ATR), а не диапазон
            # периода целиком: развилка перевода стр. 652 зафиксирована так
            # в processed/strategies/systems_ch18_schwager.md.
            atr_prev = true_range.rolling(self.wrd_atr_n).mean().shift(1)
            out["wrd_day"] = (true_range / atr_prev) > self.wrd_k
            # PTR: max истинных максимумов / min истинных минимумов на
            # [ШД−n1; ШД+n2]. Определяется спустя n2 дней после ШД-дня,
            # причём сигналы дня определения проверяются по СТАРОМУ PTR
            # (порядок стр. 653) → новый PTR действует со СЛЕДУЮЩЕГО бара.
            th = true_high.to_numpy(dtype=float)
            tl = true_low.to_numpy(dtype=float)
            ptr_high = np.full(len(out), np.nan)
            ptr_low  = np.full(len(out), np.nan)
            for i in np.flatnonzero(out["wrd_day"].to_numpy()):
                eff = i + self.wrd_n2 + 1
                if eff >= len(out):
                    continue
                lo_edge = max(0, i - self.wrd_n1)
                ptr_high[eff:] = th[lo_edge: i + self.wrd_n2 + 1].max()
                ptr_low[eff:]  = tl[lo_edge: i + self.wrd_n2 + 1].min()
            out["ptr_high"] = ptr_high
            out["ptr_low"]  = ptr_low

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
        """Вернуть значения индикаторов для последней свечи (со счётом с нуля)."""
        return self.latest_precomputed(self.compute(df))

    def latest_precomputed(self, computed: pd.DataFrame) -> IndicatorValues:
        """То же, но по уже посчитанному compute()-DataFrame (без пересчёта).

        Используется бэктестом: индикаторы считаются один раз по всей серии,
        а per-bar остаётся только осцилляторный контекст (расхождения)."""
        if computed.empty:
            return IndicatorValues()

        row = computed.iloc[-1]

        def _get(col: str) -> float:
            return float(row[col]) if col in row.index else float("nan")

        osc = self._oscillator_context(computed)

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
            rsi9=_get("rsi9"),
            stoch_k=_get("stoch_k"),
            stoch_d=_get("stoch_d"),
            mac_high=_get("mac_high"),
            mac_low=_get("mac_low"),
            swing_low=_get("swing_low"),
            ptr_high=_get("ptr_high"),
            ptr_low=_get("ptr_low"),
            **osc,
        )

    # ── Расхождения и микро-паттерны (Швагер/Бировиц, гл. 15) ──────────

    # Осцилляторы, участвующие в кворуме расхождений «2 из 3»
    DIVERGENCE_OSCILLATORS = ("macd", "rsi9", "stoch_k")
    # Параметры поиска свингов/пар — инстанс-атрибуты pivot_strength,
    # pivot_max_age, pair_search_max (задаются в __init__)

    def _oscillator_context(self, computed: pd.DataFrame) -> dict:
        """Посчитать расхождения и триггеры микро-M/W по окну данных."""
        result = {
            "bull_div_count":  float("nan"),
            "bear_div_count":  float("nan"),
            "micro_w_trigger": float("nan"),
            "micro_m_trigger": float("nan"),
            "div_low":         float("nan"),
            "div_high":        float("nan"),
        }
        need = {"low", "high", "close"} | set(self.DIVERGENCE_OSCILLATORS)
        if not need.issubset(computed.columns) or len(computed) < 20:
            return result

        lows   = computed["low"].to_numpy(dtype=float)
        highs  = computed["high"].to_numpy(dtype=float)
        closes = computed["close"].to_numpy(dtype=float)
        n = len(computed)
        k = self.pivot_strength

        def pivots(values, is_low: bool) -> list:
            """Индексы локальных экстремумов (кроме последних k баров)."""
            found = []
            for i in range(k, n - k):
                seg = values[i - k: i + k + 1]
                if is_low and values[i] == seg.min():
                    found.append(i)
                elif not is_low and values[i] == seg.max():
                    found.append(i)
            return found

        def divergence(price_pivots: list, is_bull: bool):
            """Кворум расхождений по двум последним пивотам цены."""
            if len(price_pivots) < 2:
                return None
            p1, p2 = price_pivots[-2], price_pivots[-1]
            if n - 1 - p2 > self.pivot_max_age:
                return None    # расхождение устарело
            if is_bull and not lows[p2] < lows[p1]:
                return None    # нет более низкого минимума цены
            if not is_bull and not highs[p2] > highs[p1]:
                return None    # нет более высокого максимума цены
            count = 0
            for osc_col in self.DIVERGENCE_OSCILLATORS:
                osc = computed[osc_col].to_numpy(dtype=float)
                v1, v2 = osc[p1], osc[p2]
                if math.isnan(v1) or math.isnan(v2):
                    continue
                if is_bull and v2 > v1:
                    count += 1     # осциллятор сделал более высокий минимум
                elif not is_bull and v2 < v1:
                    count += 1     # осциллятор сделал более низкий максимум
            return (p2, count) if count > 0 else None

        def micro_trigger(pivot_idx: int, is_w: bool):
            """Микро-W: первая пара «закрытие вверх, затем вниз» после пивота
            (микро-M: «вниз, затем вверх»). Возвращает уровень триггера, если
            он ещё не пробит закрытием (пробитый ранее сигнал израсходован)."""
            for i in range(pivot_idx + 1, min(pivot_idx + self.pair_search_max, n - 1)):
                if is_w:
                    if closes[i] > closes[i - 1] and closes[i + 1] < closes[i]:
                        trigger = max(highs[i], highs[i + 1])
                        later = closes[i + 2: n - 1]
                        if later.size and (later > trigger).any():
                            return None    # уже пробивался раньше текущего бара
                        return trigger
                else:
                    if closes[i] < closes[i - 1] and closes[i + 1] > closes[i]:
                        trigger = min(lows[i], lows[i + 1])
                        later = closes[i + 2: n - 1]
                        if later.size and (later < trigger).any():
                            return None
                        return trigger
            return None

        bull = divergence(pivots(lows, is_low=True), is_bull=True)
        if bull:
            p2, count = bull
            result["bull_div_count"] = float(count)
            result["div_low"] = float(lows[p2])
            trig = micro_trigger(p2, is_w=True)
            if trig is not None:
                result["micro_w_trigger"] = float(trig)

        bear = divergence(pivots(highs, is_low=False), is_bull=False)
        if bear:
            p2, count = bear
            result["bear_div_count"] = float(count)
            result["div_high"] = float(highs[p2])
            trig = micro_trigger(p2, is_w=False)
            if trig is not None:
                result["micro_m_trigger"] = float(trig)

        return result


indicator_engine = IndicatorEngine()
