"""QuantFlow — форвард-контур osc_range_moex на D1 (бумажная торговля + обучение).

Запуск:
    python run_forward_d1.py        # ежедневно после закрытия MOEX (пн-пт ~19:15 МСК)

Один прогон: догрузить D1-свечи → для каждого тикера обработать ВСЕ
необработанные закрытые бары зеркально бэктесту (backtest/engine.py):
стоп-лосс → exit_rules → SELL-сигнал → трейлинг; вход — через
orchestrator.check_signal() (внутри фильтр структурного даунтренда, отказ
пишется в skipped_signals), закрытие — через on_trade_closed() (запускает
цикл обучения).

Догон пропущенных баров (техдолг №14). Прогон может не состояться — сервер
выключен, Docker не поднялся, триггер пропущен. Раньше пропущенные бары
перескакивались НАВСЕГДА: решение принималось только по rows[-1], и стоп,
который должен был сработать на пропущенном баре, не срабатывал никогда.
Теперь:
  - идёт цикл по всем необработанным барам от forward_state.last_candle_time
    до последнего ЗАКРЫТОГО бара;
  - на пропущенных (исторических) барах разрешены ТОЛЬКО выходы: стоп,
    трейлинг, exit_rules, SELL-сигнал;
  - входы — только на самом свежем баре, задним числом НИКОГДА. Это не
    вкусовщина: check_signal → _check_structural_downtrend читает .iloc[-1]
    ПОЛНОЙ серии, то есть всегда считает фильтр по новейшему бару. Вход
    задним числом был бы отфильтрован заглядывающим вперёд фильтром;
  - last_candle_time продвигается по КАЖДОМУ обработанному бару, поэтому
    падение посреди догона не теряет прогресс;
  - глубина ретроспективных выходов ограничена CATCHUP_MAX_BARS (см. ниже),
    разрыв от CATCHUP_FLAG_BARS баров флагается человеку, а каждый догон
    пишется в forward_catchup_log.

Порядок фаз в run(): все исторические бары всех тикеров (только выходы),
затем свежий бар всех тикеров (выходы и входы). Разделение сохраняется ради
ПОРТФЕЛЬНОГО режима: на общем счёте вход по первому тикеру оценивался бы
против капитала ДО того, как догон последнего освободил его несколько баров
назад, и результат зависел бы от порядка TICKERS. Фаза 1 порядко-независима по
построению — входы там запрещены, а единственный эффект на капитал
(book.credit при закрытии) монотонно возрастает, поэтому перерасход невозможен.
В потикерном режиме порядок TICKERS не влияет вообще: бюджеты тикеров
независимы, а внутри тикера исторические бары и так идут раньше свежего.

Паритет с бэктестом: окно индикаторов 61 бар, сделки по ценам закрытия,
комиссия costs.COMMISSION_PCT за сторону (вычитается из pnl с ОБЕИХ сторон, как
в бэктесте), ATR-трейлинг (config.risk.atr_stop_multiplier), незакрытая
сегодняшняя сессия не судится в обоих контурах (market_time.last_closed_index),
и — с 28.07 — потикерный бюджет: каждый тикер получает независимые
FORWARD_CAPITAL, как в потикерном бэктесте. Решение: форвард измеряет ПРАВИЛА,
а не счёт; сравнение форвард↔бэктест не должно мерить конкуренцию за капитал.
Портфельное поведение сохранено под будущий портфельный контур и включается
FORWARD_PER_TICKER_CAPITAL=false (долг №17).

Сознательные отличия от бэктеста:
  - position_size_multiplier из check_signal логируется, но НЕ применяется
    (сначала валидируем бэктест-конфигурацию как есть);
  - во время догона последовательность сделок расходится с бэктестом: после
    выбивания стопа движок бэктеста может войти на следующем баре, форвард —
    только на свежем. Поэтому закрытия догона помечаются в exit_reason, и
    сравнение форвард↔бэктест может исключить эти окна по LIKE.

Состояние — только в БД: открытые позиции в trades (closed_at IS NULL,
strategy_id = osc_range_moex_d1_fwd), идемпотентность через forward_state,
журнал догонов в forward_catchup_log. Повторный запуск в тот же день — no-op.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
import json
import logging
import math
import os
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import asyncpg
import pandas as pd

from config import config
from costs import COMMISSION_PCT
from data.loader import save_candles_to_db
from market_time import MSK, last_closed_index, session_date
from signals.indicators import IndicatorEngine, SIGNAL_WINDOW_BARS, signal_window
from signals.rules_engine import RulesEngine, Action, classify_regime
from risk.risk_manager import RiskManager
from learning.trading_orchestrator import TradingOrchestrator
from learning.memory_writer import (
    Trade,
    Market,
    Direction,
    MarketRegime,
    ExitReasonType,
)
# ui.telegram_bot импортируется лениво в run(): его импорт тянет легаси
# feedback_store, который при загрузке модуля ходит в БД со старой схемой.

logger = logging.getLogger("quantflow.forward")

STRATEGY_ID        = "osc_range_moex_d1_fwd"
SEED_FROM_STRATEGY = "osc_range_moex_d1"     # belief-строка-источник (бэктест)

TICKERS = ["SBER", "GAZP", "LKOH", "NVTK", "ROSN", "TATN",
           "MGNT", "MOEX", "PLZL", "CHMF", "ALRS", "SNGS"]

RULES_FILE = config.rules_dir / "rules_osc_range.yaml"

WINDOW_BARS      = SIGNAL_WINDOW_BARS   # окно latest_precomputed = iloc[i-60:i+1]
MIN_HISTORY_BARS = 250       # SMA200 фильтра + запас
WARMUP_BARS      = 50        # паритет с range(50, len(df_ind)) бэктеста
STALE_DAYS       = 5         # свеча старше — данные протухли, тикер не обрабатываем
REFRESH_DAYS     = 10        # окно перекрытия при догрузке свечей

# Предел ГЛУБИНЫ ретроспективных выходов. Причина ограничения одна, и она не
# календарная: за длинный разрыв цены в БД могли быть перезаписаны
# корпоративным событием (сплит, крупный дивиденд, переименование), и тогда
# задним числом сработает стоп по цене, которой не было.
#
# ВНИМАНИЕ: 7 — НЕ эмпирическая величина. Измеренное 28.07 распределение
# разрывов двугорбое: безобидные <=2 бара (календарь; бары идут ~0.96 на
# календарный день, выходные торгуются с 2025Q2, новогодний провал даёт 0
# баров), реальный сбой — 13 баров. Между 3 и 12 наблюдений НЕТ НИ ОДНОГО,
# поэтому 5, 7 и 10 дают на всей накопленной истории идентичное поведение, и
# выбор между ними на данных неразрешим. Длина каждого разрыва пишется в
# forward_catchup_log — через полгода предел выбирается по данным, а не
# аргументом.
#
# Временная мера: когда появится список корпоративных событий по тикерам (он
# нужен и ISS-загрузчику), длину заменить прямой проверкой «событие внутри
# разрыва → исторические бары не обрабатывать вообще, независимо от длины».
CATCHUP_MAX_BARS_DEFAULT = 7
CATCHUP_MAX_BARS_CEILING = 7    # .env может только УЖЕСТОЧИТЬ

# Порог ФЛАГА — отдельное число, и вот оно измеренное: календарь не даёт
# разрывов >=3 баров. Не путать с пределом догона: предел ограничивает
# глубину ретроспективных выходов, порог флага — когда звать человека.
# Разрыв 4 бара: выходы догоняем И флагаем.
CATCHUP_FLAG_BARS = 3

# База бумажного капитала. В потикерном режиме (по умолчанию) — на КАЖДЫЙ
# тикер независимо, как в потикерном бэктесте.
FORWARD_CAPITAL = float(os.getenv("FORWARD_CAPITAL", "1000000"))


def _dec(value: float) -> Decimal:
    """float → Decimal без артефактов двоичного представления (как в бэктесте)."""
    return Decimal(str(round(float(value), 6)))


def _catchup_max_bars() -> tuple[int, Optional[str]]:
    """(действующий предел догона, пометка для сообщения или None).

    Пометка возвращается наружу, а не только логируется: попытка ослабить
    ограничение должна быть видна в Telegram, иначе она потеряется ровно
    тогда, когда важна — см. forward_healthcheck.py:70-75.
    """
    raw = os.getenv("FWD_CATCHUP_MAX_BARS")
    if raw is None or raw.strip() == "":
        return CATCHUP_MAX_BARS_DEFAULT, None
    try:
        value = int(raw)
    except ValueError:
        return (CATCHUP_MAX_BARS_DEFAULT,
                f"⚠ FWD_CATCHUP_MAX_BARS={raw!r} — не число, "
                f"взят дефолт {CATCHUP_MAX_BARS_DEFAULT}")
    if value > CATCHUP_MAX_BARS_CEILING:
        return (CATCHUP_MAX_BARS_CEILING,
                f"⚠ предел догона из .env ({value}) проигнорирован, "
                f"взят жёсткий предел {CATCHUP_MAX_BARS_CEILING}")
    if value < 1:
        return 1, f"⚠ FWD_CATCHUP_MAX_BARS={value} поднято до 1"
    return value, None


def _per_ticker_capital() -> tuple[bool, Optional[str]]:
    """(потикерный режим?, пометка для сообщения или None).

    Разбор НЕ по шаблону `== "true"`: тогда опечатка в .env молча вернула бы
    портфельный режим, то есть молча вернула бы дефект, который этот флаг
    закрывает. Портфельный включается только явным false/0/no/off, всё
    остальное — потикерный, а нераспознанное значение вдобавок возвращает
    пометку, которая уходит в сводку и Telegram наравне с catchup_note.
    """
    raw = os.getenv("FORWARD_PER_TICKER_CAPITAL")
    if raw is None or raw.strip() == "":
        return True, None
    value = raw.strip().lower()
    if value in ("false", "0", "no", "off"):
        return False, ("⚠ FORWARD_PER_TICKER_CAPITAL=%s — ПОРТФЕЛЬНЫЙ режим: "
                       "общий капитал на все тикеры, паритета с бэктестом нет" % raw)
    if value in ("true", "1", "yes", "on"):
        return True, None
    return True, (f"⚠ FORWARD_PER_TICKER_CAPITAL={raw!r} не распознано — "
                  f"оставлен потикерный режим")


class CapitalBook:
    """Бюджеты бумажного капитала.

    Потикерный режим (по умолчанию): независимый счёт на тикер — паритет с
    бэктестом, где `capital` это локальная переменная run() и каждый тикер
    получает свой FORWARD_CAPITAL (`backtest/engine.py:186`).
    Портфельный: один общий счёт на все тикеры (см. долг №17).

    Класс, а не россыпь `if self.per_ticker`, по той же причине, по которой
    `allow_entry` сделан параметром фазы: инвариант становится свойством типа,
    а не проверкой, которую легко потерять при следующей правке.
    """

    def __init__(self, per_ticker: bool, budgets: dict, portfolio: float):
        self.per_ticker = per_ticker
        self._budgets = budgets        # тикер → свободно (потикерный режим)
        self._portfolio = portfolio    # общий счёт (портфельный режим)

    def available(self, ticker: str) -> float:
        if self.per_ticker:
            return self._budgets.get(ticker, FORWARD_CAPITAL)
        return self._portfolio

    def debit(self, ticker: str, amount: float) -> None:
        if self.per_ticker:
            self._budgets[ticker] = self.available(ticker) - amount
        else:
            self._portfolio -= amount

    def credit(self, ticker: str, amount: float) -> None:
        if self.per_ticker:
            self._budgets[ticker] = self.available(ticker) + amount
        else:
            self._portfolio += amount

    def describe(self, open_count: int) -> str:
        """Строка для сводки.

        В потикерном режиме единого числа «свободно» здесь НЕТ намеренно:
        именно его прочитали бы как остаток счёта, а решение 28.07 состоит в
        обратном — форвард измеряет правила, а не счёт. Потикерные остатки
        уходят в logger.info.
        """
        if self.per_ticker:
            return (f"бюджеты потикерно (база {FORWARD_CAPITAL:,.0f} руб. × "
                    f"{len(TICKERS)}), занято {open_count}")
        return f"свободно {self._portfolio:,.0f} руб."

    def detail(self) -> str:
        return ", ".join(f"{t}={v:,.0f}" for t, v in sorted(self._budgets.items()))


def _duplicate_sessions(raw_times: list) -> list:
    """Бары, попавшие на одну московскую сессию (дубли конвенции времени).

    Измерено 28.07: 12 таких пар в БД, по одной на тикер — сессия 2026-06-25
    записана и как 2026-06-24 21:00+00 (московская полночь), и как
    2026-06-25 00:00+00 (наивная полночь как UTC), OHLCV идентичны.
    UNIQUE (ticker, timeframe, time) их не ловит: мгновения разные.

    Цикл догона к ним устойчив — каждая СТРОКА обходится ровно один раз, и
    состояние продвигается на её собственную метку, поэтому легитимный бар не
    теряется, а повторная оценка той же сессии no-op (позиция уже закрыта либо
    рэтчет трейлинга отклоняет тот же уровень). Но фантомный бар сдвигает
    каждое rolling-окно, поэтому факт обязан быть виден.
    """
    by_date: dict = {}
    for t in raw_times:
        by_date.setdefault(session_date(t), []).append(t)
    return [{"date": str(d), "times": [t.isoformat() for t in ts]}
            for d, ts in sorted(by_date.items()) if len(ts) > 1]


def signal_for_bar(
    rules: RulesEngine,
    ind_engine: IndicatorEngine,
    df_ind: pd.DataFrame,
    i: int,
    ticker: str = "",
):
    """Индикаторы и сигнал по бару i уже посчитанного df_ind — как в бэктесте.

    Возвращает (iv, signal). Окно берётся через signal_window(), то есть
    заканчивается ровно на баре i — доступа к будущим барам нет.
    """
    iv = ind_engine.latest_precomputed(signal_window(df_ind, i))
    return iv, rules.evaluate(iv, ticker)


def signal_for_last_bar(
    rules: RulesEngine,
    ind_engine: IndicatorEngine,
    df: pd.DataFrame,
    ticker: str = "",
):
    """Индикаторы и сигнал по последней свече — ровно как в бэктесте.

    Возвращает (df_ind, iv, signal). Вынесено в модульную функцию, чтобы
    паритет-тесты могли прогнать ту же логику на обрезанной истории.
    """
    df_ind = ind_engine.compute(df)
    iv, signal = signal_for_bar(rules, ind_engine, df_ind, len(df_ind) - 1, ticker)
    return df_ind, iv, signal


@dataclass
class TickerPlan:
    """Подготовленный к обработке тикер: свечи, индикаторы, границы догона."""

    ticker:       str
    raw_times:    list            # tz-aware метки из БД — ЕДИНСТВЕННАЯ ось времени
    df_ind:       pd.DataFrame    # индикаторы по всей истории, считаны один раз
    first_hist:   int             # первый ДОГОНЯЕМЫЙ исторический бар
    last_closed:  int             # свежий (последний закрытый) бар
    gap_bars:     int             # исторических баров в разрыве ДО ограничения
    discarded:    int             # из них признано потерянными
    duplicates:   list
    state_before: Optional[datetime]
    exits:        list = field(default_factory=list)   # для журнала
    failed:       bool = False    # фаза 1 упала → фазу 2 не пускать

    @property
    def historical(self) -> range:
        """Догоняемые исторические бары. Здесь разрешены ТОЛЬКО выходы."""
        return range(self.first_hist, self.last_closed)

    @property
    def fresh(self) -> range:
        """Свежий бар. Единственное место, где разрешён вход."""
        return range(self.last_closed, self.last_closed + 1)

    @property
    def processed(self) -> int:
        return self.last_closed - self.first_hist

    @property
    def flagged(self) -> bool:
        return self.gap_bars >= CATCHUP_FLAG_BARS or self.discarded > 0


class ForwardRunner:
    """Однопроходный дневной прогон форвард-контура."""

    def __init__(self):
        self.rules      = RulesEngine(rules_file=RULES_FILE)
        self.indicators = IndicatorEngine(**getattr(self.rules, "divergence_params", {}))
        self.risk       = RiskManager()
        self.orch       = TradingOrchestrator()
        self._db: Optional[asyncpg.Connection] = None
        self.events: list[str] = []     # сводка дня для консоли и Telegram
        self.book: Optional[CapitalBook] = None   # бюджеты, см. _paper_capital
        self.catchup_max, self.catchup_note = _catchup_max_bars()
        self.per_ticker, self.per_ticker_note = _per_ticker_capital()

    # ── Инфраструктура ────────────────────────────────────────────────

    @staticmethod
    def _dsn() -> str:
        return config.db.dsn

    def _event(self, msg: str) -> None:
        self.events.append(msg)
        logger.info(msg)

    async def _seed_belief(self) -> None:
        """Создать belief-строку форвард-стратегии (однократно, идемпотентно)."""
        exists = await self._db.fetchval(
            "SELECT 1 FROM belief_system WHERE strategy_id = $1", STRATEGY_ID)
        if exists:
            return
        await self._db.execute("""
            INSERT INTO belief_system (strategy_id, strategy_name, market, description,
                                       confidence, best_regime, best_timeframe)
            SELECT $1, strategy_name || ' (форвард)', market, description,
                   confidence, best_regime, best_timeframe
            FROM belief_system WHERE strategy_id = $2
            ON CONFLICT (strategy_id) DO NOTHING
        """, STRATEGY_ID, SEED_FROM_STRATEGY)
        exists = await self._db.fetchval(
            "SELECT 1 FROM belief_system WHERE strategy_id = $1", STRATEGY_ID)
        if not exists:   # источника нет — минимальная строка с дефолтами
            await self._db.execute("""
                INSERT INTO belief_system (strategy_id, strategy_name, market, description)
                VALUES ($1, 'Осцилляторы боковика D1 (форвард)', 'stocks',
                        'Форвард-контур osc_range_moex, D1, бумажное исполнение')
                ON CONFLICT (strategy_id) DO NOTHING
            """, STRATEGY_ID)
        self._event(f"Belief-строка {STRATEGY_ID} создана")

    async def _load_open_trades(self) -> dict:
        """Открытые форвард-позиции из БД: ticker → изменяемый dict записи trades.

        dict(r), а не сам asyncpg.Record: Record не поддерживает __setitem__, а
        цикл по барам ОБЯЗАН видеть ужесточённый трейлингом стоп на следующем
        баре. С Record рэтчет перезапускался бы с исходного стопа, и стоп,
        который должен сработать на баре i+2, не сработал бы — тот же дефект
        №14 на уровень ниже. _try_open уже кладёт обычный dict.
        """
        rows = await self._db.fetch("""
            SELECT trade_id, ticker, entry_price, stop_loss, position_size,
                   risk_amount, opened_at
            FROM trades
            WHERE strategy_id = $1 AND closed_at IS NULL AND is_sandbox
            ORDER BY opened_at
        """, STRATEGY_ID)
        open_trades: dict = {}
        for r in rows:
            if r["ticker"] in open_trades:
                # Не logger.warning: это молча НЕУПРАВЛЯЕМАЯ позиция, её стоп
                # не сработает никогда, потому что форвард её не видит.
                self._event(f"🚨 {r['ticker']}: несколько открытых позиций — "
                            f"использую первую, {str(r['trade_id'])[:8]} "
                            f"остаётся без управления")
                continue
            open_trades[r["ticker"]] = dict(r)
        return open_trades

    async def _paper_capital(self, open_trades: dict) -> CapitalBook:
        """Бюджеты: база + реализованный PnL − стоимость открытых.

        Это буквально формула капитала бэктеста. Там сайзинг считается от
        ЭВОЛЮЦИОНИРУЮЩЕЙ переменной `capital` (`engine.py:248`), а не от
        initial_capital, поэтому реализованный PnL в бюджет входить обязан:
        когда по тикеру нет позиции, `capital` бэктеста равен
        `initial + Σ[(exit−entry)·shares − обе комиссии]`, то есть
        `FORWARD_CAPITAL + Σpnl` — но только с той конвенцией pnl, где
        вычтены ОБЕ комиссии. Поэтому правка комиссии предшествовала этой.

        Остаточная неточность, зафиксированная сознательно: пока позиция
        открыта, вычитается entry·shares, а бэктест вычитал ещё и комиссию
        входа. На сайзинг это повлиять не может — тикер считает размер позиции
        только когда позиции по нему нет, то есть когда этот член равен нулю.
        В портфельном режиме общий бюджет завышен на 0.03% номинала открытых
        (≈180 руб. на позицию 600k) — известный остаток портфельной ветки.
        """
        rows = await self._db.fetch("""
            SELECT ticker, COALESCE(SUM(pnl), 0) AS realized FROM trades
            WHERE strategy_id = $1 AND closed_at IS NOT NULL
            GROUP BY ticker
        """, STRATEGY_ID)
        realized = {r["ticker"]: float(r["realized"]) for r in rows}
        open_value: dict = {}
        for r in open_trades.values():
            open_value[r["ticker"]] = open_value.get(r["ticker"], 0.0) + (
                float(r["entry_price"]) * float(r["position_size"]))

        budgets = {
            t: FORWARD_CAPITAL + realized.get(t, 0.0) - open_value.get(t, 0.0)
            for t in set(TICKERS) | set(realized) | set(open_value)
        }
        portfolio = (FORWARD_CAPITAL + sum(realized.values())
                     - sum(open_value.values()))
        return CapitalBook(self.per_ticker, budgets, portfolio)

    async def _advance_state(self, ticker: str, dt) -> None:
        """Зафиксировать обработанный бар. Вызывается на КАЖДОМ баре догона."""
        await self._db.execute("""
            INSERT INTO forward_state (strategy_id, ticker, last_candle_time, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (strategy_id, ticker)
            DO UPDATE SET last_candle_time = EXCLUDED.last_candle_time, updated_at = NOW()
        """, STRATEGY_ID, ticker, dt)

    # ── Подготовка тикера ─────────────────────────────────────────────

    async def _prepare_ticker(self, ticker: str) -> Optional[TickerPlan]:
        """Свечи, границы догона, индикаторы. None = тикер снят с обработки."""
        rows = await self._db.fetch("""
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE ticker = $1 AND timeframe = '1d'
            ORDER BY time
        """, ticker)
        if len(rows) < MIN_HISTORY_BARS:
            self._event(f"⚠ {ticker}: мало истории D1 ({len(rows)} баров) — пропуск")
            return None

        raw_times = [r["time"] for r in rows]        # tz-aware, как в БД

        last_closed = last_closed_index(raw_times)
        if last_closed < 0:
            self._event(f"⚠ {ticker}: нет ни одного закрытого бара D1 — пропуск")
            return None
        last_raw = raw_times[last_closed]

        state_time = await self._db.fetchval("""
            SELECT last_candle_time FROM forward_state
            WHERE strategy_id = $1 AND ticker = $2
        """, STRATEGY_ID, ticker)

        if state_time is None:
            # Bootstrap: первый прогон тикера (или строку состояния удалили).
            # Отличить эти два случая нельзя, поэтому берём безопасное
            # схлопывание — только свежий бар, как и было до догона. Три года
            # истории задним числом не переигрываем.
            first_raw = last_closed
            self._event(f"ℹ {ticker}: forward_state пуст — "
                        f"только свежий бар {session_date(last_raw)}")
        elif state_time > last_raw:
            # Строки свечей удалены (DELETE прошёл, INSERT упал) или откат часов.
            # Сторож это тоже не увидит: A1 сравнивает свечи НОВЕЕ обработанного
            # (пусто), A3 нужен предыдущий снимок. Слепое пятно обоих процессов.
            self._event(f"⚠ {ticker}: состояние {session_date(state_time)} опережает свечи "
                        f"{session_date(last_raw)} — пропуск, состояние не двигаю")
            return None
        elif state_time == last_raw:
            logger.info("[%s] Свежих свечей нет (последняя %s) — пропуск",
                        ticker, session_date(last_raw))
            return None
        else:
            first_raw = bisect_right(raw_times, state_time)

        # Протухшие данные: решение по старой свече опаснее, чем его отсутствие.
        # Проверяется ТОЛЬКО по свежему бару и НИКОГДА побарно: в разрыве из 7
        # баров каждый исторический старше STALE_DAYS, и проверка внутри цикла
        # сделала бы догон невозможным по построению.
        age_days = (datetime.now(timezone.utc) - last_raw).days
        if age_days > STALE_DAYS:
            self._event(f"⚠ {ticker}: последняя свеча {session_date(last_raw)} "
                        f"({age_days} дн. назад) — пропуск")
            return None

        gap_bars   = last_closed - first_raw
        first_hist = max(first_raw + max(0, gap_bars - self.catchup_max), WARMUP_BARS)
        discarded  = first_hist - first_raw

        duplicates = _duplicate_sessions(raw_times[first_hist:last_closed + 1])
        if duplicates:
            dates = ", ".join(d["date"] for d in duplicates)
            self._event(f"⚠ {ticker}: бары-двойники на одну сессию ({dates}) — "
                        f"окна индикаторов сдвинуты, данные требуют ремонта")

        df = pd.DataFrame(
            {
                "open":   [float(r["open"]) for r in rows],
                "high":   [float(r["high"]) for r in rows],
                "low":    [float(r["low"]) for r in rows],
                "close":  [float(r["close"]) for r in rows],
                "volume": [int(r["volume"]) for r in rows],
            },
            index=pd.DatetimeIndex(
                [t.replace(tzinfo=None) for t in raw_times], name="datetime"
            ),
        )

        return TickerPlan(
            ticker=ticker, raw_times=raw_times,
            df_ind=self.indicators.compute(df),
            first_hist=first_hist, last_closed=last_closed,
            gap_bars=gap_bars, discarded=discarded,
            duplicates=duplicates, state_before=state_time,
        )

    # ── Обработка баров ──────────────────────────────────────────────

    async def _run_bars(self, plan: TickerPlan, open_trades: dict,
                        bars, allow_entry: bool) -> None:
        """Прогнать бары plan'а. Шаги пронумерованы как в backtest/engine.py.

        allow_entry — параметр ФАЗЫ, не бара: «входы только на свежем баре»
        становится свойством графа вызовов, а не проверкой внутри цикла,
        которую легко потерять при следующей правке.
        """
        for i in bars:
            dt    = plan.raw_times[i]
            row   = plan.df_ind.iloc[i]
            price = float(row["close"])
            _atr  = row.get("atr")
            atr   = float(_atr) if _atr is not None and pd.notna(_atr) else price * 0.01

            iv, signal = signal_for_bar(
                self.rules, self.indicators, plan.df_ind, i, plan.ticker)

            pos = open_trades.get(plan.ticker)
            # Бар, предшествующий входу, не судим. Достижимо: _try_open пишет
            # сделку через orch (своё соединение), а состояние пишется отдельно,
            # поэтому падение между ними оставляет состояние на баре N−3 при
            # позиции с opened_at = бар N. Иначе догон закрыл бы позицию по
            # цене, которой она ещё не существовала.
            manage = pos is not None and dt > pos["opened_at"]

            # ── 1. Стоп-лосс ───────────────────────────────── engine.py:197
            if manage and price <= float(pos["stop_loss"]):
                await self._close_position(
                    pos, price, dt, ExitReasonType.STOP_LOSS,
                    f"Форвард: стоп-лосс {float(pos['stop_loss']):.2f}",
                    open_trades, plan, i)
                pos, manage = None, False

            # ── 1б. Ведение позиции по R (Швагер, гл. 15) ─── engine.py:205
            # Для osc_range НЕ включено: target_r/breakeven_r на IS ухудшают H4
            # и не меняют D1 (rules_osc_range.yaml:30-31). Шаг оставлен пустым
            # намеренно, чтобы нумерация совпадала с бэктестом.

            # ── 2. Правила выхода (exit_rules) ─────────────── engine.py:218
            if manage:
                exit_sig = self.rules.evaluate_exit(iv, plan.ticker)
                if exit_sig.action == Action.EXIT:
                    await self._close_position(
                        pos, price, dt, ExitReasonType.SIGNAL, exit_sig.reason,
                        open_trades, plan, i)
                    pos, manage = None, False

            # ── 3. Основной сигнал ─────────────────────────── engine.py:232
            if manage and signal.action == Action.SELL:
                await self._close_position(
                    pos, price, dt, ExitReasonType.SIGNAL, signal.reason,
                    open_trades, plan, i)
                pos = None
            elif pos is None and allow_entry and signal.action == Action.BUY:
                await self._try_open(plan.ticker, plan.df_ind, i, iv, signal,
                                     price, atr, dt, open_trades)
                pos = open_trades.get(plan.ticker)

            # ── 4. Трейлинг + продвижение состояния ────────── engine.py:301
            new_stop = None
            if pos is not None and atr > 0 and dt > pos["opened_at"]:
                cand = price - atr * self.risk.cfg.atr_stop_multiplier
                if cand > float(pos["stop_loss"]):
                    new_stop = cand

            # Одной транзакцией: иначе падение между UPDATE и записью состояния
            # оставило бы состояние продвинутым за бар, чей рэтчет не сохранён —
            # молчаливая потеря ужесточённого стопа без следов.
            async with self._db.transaction():
                if new_stop is not None:
                    await self._db.execute(
                        "UPDATE trades SET stop_loss = $2 WHERE trade_id = $1",
                        pos["trade_id"], _dec(new_stop))
                    pos["stop_loss"] = _dec(new_stop)   # см. _load_open_trades
                    logger.info("[%s] Трейлинг-стоп: %.2f", plan.ticker, new_stop)
                await self._advance_state(plan.ticker, dt)

    async def _try_open(self, ticker, df_ind, i, iv, signal, price, atr, dt,
                        open_trades) -> None:
        """BUY-сигнал: check_signal (фильтры, confidence) → сайзинг → открытие."""

        def _feat(col: str) -> Optional[float]:
            val = df_ind.iloc[i].get(col)
            if val is None or not pd.notna(val):
                return None
            val = float(val)
            return val if math.isfinite(val) else None

        volume_ratio = None
        vol_ma = df_ind["volume"].rolling(20).mean().iloc[i]
        vol    = df_ind["volume"].iloc[i]
        if pd.notna(vol_ma) and vol_ma:
            volume_ratio = round(float(vol) / float(vol_ma), 4)

        features = {
            "rsi": _feat("rsi"), "atr": _feat("atr"), "adx": _feat("adx"),
            "bb_pct": _feat("bb_pct"), "volume_ratio": volume_ratio,
        }
        # Кворум расхождений сигнального окна — как в бэктесте, для learning
        for attr in ("bull_div_count", "bear_div_count"):
            val = getattr(iv, attr, float("nan"))
            if val is not None and math.isfinite(val):
                features[attr] = float(val)
        features = {k: v for k, v in features.items() if v is not None}
        regime = classify_regime(_feat("adx"))

        decision = await self.orch.check_signal({
            "strategy_id":     STRATEGY_ID,
            "ticker":          ticker,
            "direction":       "BUY",
            "timeframe":       "D1",
            "market_regime":   regime,
            "market_features": features,
            "is_sandbox":      True,
        })
        if not decision["approved"]:
            self._event(f"⛔ {ticker}: BUY-сигнал отклонён — {decision['reason']}")
            return

        # Лимит числа позиций — величина ПОРТФЕЛЬНАЯ, поэтому проверяется только
        # в портфельном режиме. В потикерном «одна позиция на тикер» держится
        # структурно: _load_open_trades кладёт dict по тикеру, вход возможен
        # только при `pos is None` (шаг 3 _run_bars), а бэктест держит тот же
        # инвариант единственным слотом `open_trade` (engine.py:187, 239, 243).
        if not self.book.per_ticker and len(open_trades) >= config.risk.max_open_positions:
            self._event(f"⛔ {ticker}: BUY-сигнал, но лимит позиций "
                        f"({config.risk.max_open_positions}) исчерпан")
            return

        available = self.book.available(ticker)
        pos = self.risk.calculate_position(
            ticker=ticker, entry_price=price, atr=atr,
            portfolio_value=available, lot_size=1,
        )
        if pos is None or pos.position_value > available:
            self._event(f"⛔ {ticker}: BUY-сигнал, но не хватает капитала "
                        f"(доступно {available:,.0f})")
            return

        entry = _dec(price)
        stop  = _dec(pos.stop_price)
        n     = Decimal(int(pos.shares))
        risk  = (entry - stop) * n
        if risk <= 0:
            risk = entry * Decimal("0.01") * n

        conf = getattr(signal, "confidence", None)
        trade = Trade(
            market          = Market.STOCKS,
            ticker          = ticker,
            direction       = Direction.BUY,
            strategy_id     = STRATEGY_ID,
            entry_price     = entry,
            stop_loss       = stop,
            position_size   = n,
            risk_amount     = risk,
            risk_percent    = (risk / _dec(available)).quantize(Decimal("0.0001"))
                              if available > 0 else None,
            opened_at       = dt,
            timeframe       = "D1",
            market_regime   = MarketRegime(regime) if regime else None,
            market_features = features or None,
            confidence      = _dec(min(max(conf, 0.0), 1.0))
                              if conf is not None and math.isfinite(conf) else None,
            entry_reason    = (signal.reason or "Сигнал BUY форварда")
                              + f" | size_mult={float(decision['position_size_multiplier']):.2f} (не применён)",
            is_sandbox      = True,
        )
        await self.orch.on_trade_opened(trade)

        commission = pos.position_value * COMMISSION_PCT
        self.book.debit(ticker, pos.position_value + commission)
        open_trades[ticker] = {
            "trade_id": trade.trade_id, "ticker": ticker,
            "entry_price": entry, "stop_loss": stop,
            "position_size": n, "risk_amount": risk, "opened_at": dt,
        }
        self._event(f"🟢 {ticker}: BUY {pos.shares} акц. @ {price:.2f}, "
                    f"стоп {pos.stop_price:.2f} ({signal.reason[:80]})")

    async def _close_position(self, rec, price: float, dt, reason_type,
                              reason_text: str, open_trades: dict,
                              plan: TickerPlan, i: int) -> None:
        """Бумажное закрытие по цене закрытия свечи (PnL как в бэктесте)."""
        if plan.discarded > 0 and reason_type == ExitReasonType.STOP_LOSS:
            # Часть баров признана потерянной, поэтому НАСТОЯЩЕЕ пробитие могло
            # случиться на выброшенном баре по цене, которой мы не видели.
            # Отдельный тип, а не STOP_LOSS: иначе в статистику и
            # decision_quality попадёт чистый стоп на уровне, которого не было.
            # И не MANUAL: тот занят paper-движком под «человек закрыл вручную».
            gap_from = plan.raw_times[plan.first_hist - plan.discarded]
            gap_to   = plan.raw_times[plan.last_closed - 1]
            reason_type = ExitReasonType.GAP_FORCED
            reason_text = (f"Вынужденный выход после разрыва ({plan.gap_bars} баров "
                           f"{session_date(gap_from)}–{session_date(gap_to)}, "
                           f"выброшено {plan.discarded}): стоп "
                           f"{float(rec['stop_loss']):.2f} пробит ценой {price:.2f}")
        elif i < plan.last_closed:
            # Закрытие на догнанном историческом баре. Помечаем, чтобы
            # последующее сравнение форвард↔бэктест могло исключить окна догона:
            # во время догона форвард не может переоткрыться, а бэктест может.
            reason_text = (f"{reason_text} | догон: бар {session_date(dt)} "
                           f"({i - plan.first_hist + 1} из {plan.processed})")

        shares     = float(rec["position_size"])
        entry      = float(rec["entry_price"])
        # Обе стороны, как в бэктесте (engine.py:_close). Двойного учёта правка
        # не создаёт: до неё комиссия входа существовала только в оперативном
        # счёте одного прогона и в БД не сохранялась. Теперь формула капитала
        # форварда буквально бэктестовая — см. _paper_capital.
        entry_comm = entry * shares * COMMISSION_PCT
        exit_comm  = shares * price * COMMISSION_PCT
        commission = entry_comm + exit_comm
        pnl        = (price - entry) * shares - commission

        trade = Trade(
            market           = Market.STOCKS,
            ticker           = rec["ticker"],
            direction        = Direction.BUY,
            strategy_id      = STRATEGY_ID,
            entry_price      = Decimal(str(rec["entry_price"])),
            stop_loss        = Decimal(str(rec["stop_loss"])),
            position_size    = Decimal(str(rec["position_size"])),
            risk_amount      = Decimal(str(rec["risk_amount"])),
            opened_at        = rec["opened_at"],
            timeframe        = "D1",
            exit_price       = _dec(price),
            closed_at        = dt,
            pnl              = _dec(pnl),
            commission       = _dec(commission),
            exit_reason_type = reason_type,
            exit_reason      = reason_text,
            is_sandbox       = True,
            trade_id         = str(rec["trade_id"]),
        )
        await self.orch.on_trade_closed(trade)
        open_trades.pop(rec["ticker"], None)
        # Только комиссия ВЫХОДА: входную уже списал _try_open. `commission`
        # выше — сумма обеих (для записи в trades), в оперативный счёт она
        # войти не может, иначе вход оплачивается дважды.
        self.book.credit(rec["ticker"], shares * price - exit_comm)
        plan.exits.append({
            "bar": dt.isoformat(), "price": round(float(price), 6),
            "reason_type": reason_type.value, "reason": reason_text,
            "trade_id": str(rec["trade_id"]),
        })
        emoji = "🔴" if pnl <= 0 else "💰"
        self._event(f"{emoji} {rec['ticker']}: EXIT @ {price:.2f}, "
                    f"PnL {pnl:+,.0f} руб. ({reason_text[:100]})")

    # ── Разрывы: флаг и журнал ───────────────────────────────────────

    def _flag_gap(self, plan: TickerPlan, open_trades: dict) -> None:
        """Позвать человека. Система флагает — решает человек."""
        gap_from = plan.raw_times[plan.first_hist - plan.discarded]
        gap_to   = plan.raw_times[plan.last_closed - 1]
        msg = (f"🚨 {plan.ticker}: разрыв {plan.gap_bars} баров "
               f"({session_date(gap_from)}–{session_date(gap_to)}) — догоняю выходами "
               f"{plan.processed}, выброшено {plan.discarded} "
               f"(предел {self.catchup_max})")
        pos = open_trades.get(plan.ticker)
        if pos is not None:
            msg += (f"\n   Открыта позиция {str(pos['trade_id'])[:8]}: вход "
                    f"{float(pos['entry_price']):.2f}, стоп "
                    f"{float(pos['stop_loss']):.2f}")
        self._event(msg)

    async def _log_catchup(self, plan: TickerPlan) -> None:
        """Постоянная запись догона. Сторож — сигнализация, а не запись."""
        if plan.gap_bars < 1 and not plan.duplicates:
            return
        await self._db.execute("""
            INSERT INTO forward_catchup_log
                (strategy_id, ticker, state_before, gap_bars, bars_processed,
                 bars_discarded, first_bar, last_bar, flagged, exits, duplicates)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            STRATEGY_ID, plan.ticker, plan.state_before, plan.gap_bars,
            plan.processed, plan.discarded,
            plan.raw_times[plan.first_hist] if plan.processed else None,
            plan.raw_times[plan.last_closed - 1] if plan.processed else None,
            plan.flagged,
            json.dumps(plan.exits, ensure_ascii=False) if plan.exits else None,
            json.dumps(plan.duplicates, ensure_ascii=False) if plan.duplicates else None,
        )

    # ── Главный цикл ─────────────────────────────────────────────────

    async def run(self) -> None:
        started = datetime.now(timezone.utc)

        # 1. Догрузка свечей: сбой не фатален — идемпотентность и проверка
        #    протухания не дадут решать по старым данным.
        try:
            saved = save_candles_to_db(TICKERS, interval="1d", days=REFRESH_DAYS, verbose=False)
            logger.info("Догрузка свечей: %d строк", saved)
        except Exception as exc:
            self._event(f"⚠ Догрузка свечей с MOEX ISS не удалась: {exc}")

        await self.orch.connect()
        self._db = await asyncpg.connect(self._dsn())
        try:
            await self._seed_belief()
            open_trades = await self._load_open_trades()
            self.book   = await self._paper_capital(open_trades)
            logger.info("Открытых позиций: %d | режим капитала: %s | %s",
                        len(open_trades),
                        "потикерный" if self.book.per_ticker else "портфельный",
                        self.book.detail() if self.book.per_ticker
                        else self.book.describe(len(open_trades)))
            if self.catchup_note:
                self._event(self.catchup_note)
            if self.per_ticker_note:
                self._event(self.per_ticker_note)

            # ── Подготовка: свечи, границы догона, индикаторы ─────────
            plans: dict[str, TickerPlan] = {}
            for ticker in TICKERS:
                try:
                    plan = await self._prepare_ticker(ticker)
                    if plan is not None:      # None = тикер снят с обработки
                        plans[ticker] = plan
                except Exception as exc:
                    self._event(f"⚠ {ticker}: ошибка подготовки — {exc}")
                    logger.exception("[%s] Ошибка подготовки", ticker)

            # ── ФАЗА 0: разрывы — флаг человеку и продвижение через
            #    выброшенные бары (они признаны потерянными осознанно) ──
            for ticker, plan in plans.items():
                try:
                    if plan.flagged:
                        self._flag_gap(plan, open_trades)
                    if plan.discarded:
                        await self._advance_state(
                            ticker, plan.raw_times[plan.first_hist - 1])
                except Exception as exc:
                    self._event(f"⚠ {ticker}: ошибка отметки разрыва — {exc}")
                    logger.exception("[%s] Ошибка отметки разрыва", ticker)
                    plan.failed = True

            # ── ФАЗА 1 — исторические бары ВСЕХ тикеров, только выходы.
            #    ФАЗА 2 — свежий бар ВСЕХ тикеров, выходы и входы.
            #    Разделение нужно ПОРТФЕЛЬНОМУ режиму: все исторические бары
            #    хронологически раньше любого свежего, поэтому одним проходом
            #    вход первого тикера оценивался бы против общего капитала ДО
            #    того, как догон последнего его освободил, и результат зависел
            #    бы от порядка TICKERS — а это не свойство стратегии.
            #    В потикерном режиме порядок не влияет (бюджеты независимы),
            #    но фазы оставлены едиными: одна ветка кода на оба режима.
            phases = (
                ("ФАЗА 1: исторические бары (только выходы)",
                 lambda p: p.historical, False),
                ("ФАЗА 2: свежий бар (выходы и входы)",
                 lambda p: p.fresh, True),
            )
            for title, bars_of, allow_entry in phases:
                logger.info(title)
                for ticker, plan in plans.items():
                    if plan.failed:
                        # Фаза 1 упала посреди догона: состояние стоит на
                        # последнем успешном баре. Пустить фазу 2 значило бы
                        # продвинуть его на свежий бар и перескочить остаток
                        # разрыва навсегда — ровно дефект №14.
                        continue
                    try:
                        await self._run_bars(plan, open_trades,
                                             bars_of(plan), allow_entry)
                    except Exception as exc:
                        self._event(f"⚠ {ticker}: ошибка обработки — {exc}")
                        logger.exception("[%s] Ошибка обработки", ticker)
                        plan.failed = True

            # ── Журнал догонов (после обеих фаз: exits собраны из обеих) ──
            for ticker, plan in plans.items():
                try:
                    await self._log_catchup(plan)
                except Exception as exc:
                    logger.exception("[%s] Журнал догона не записан: %s", ticker, exc)

            caught = sum(p.processed for p in plans.values())
            summary = (f"Форвард D1 {session_date(started)}: позиций {len(open_trades)}, "
                       f"{self.book.describe(len(open_trades))}, "
                       f"догнано баров {caught}, событий {len(self.events)}")
            if self.book.per_ticker:
                logger.info("Бюджеты потикерно: %s", self.book.detail())
            print("\n" + "═" * 64)
            print(f"  {summary}")
            for e in self.events:
                print(f"  {e}")
            print("═" * 64)

            if self.events:
                from ui.telegram_bot import send_notification
                await send_notification("📊 " + summary + "\n" + "\n".join(self.events))
        finally:
            await self._db.close()
            await self.orch.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(ForwardRunner().run())


if __name__ == "__main__":
    main()
