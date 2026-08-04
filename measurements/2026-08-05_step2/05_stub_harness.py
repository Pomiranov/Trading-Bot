"""Подставной движок правил: BUY ровно на заданных барах, всё остальное — БОЕВОЕ.

ЗАЧЕМ. Исход отвергнутого сигнала (шаг 2) и нуль-модель (часть D) требуют подать
вход извне. Шов существует и он единственный: параметр rules_engine
(engine.py:138). Своей формулы входа, выхода или издержек здесь НЕТ ни одной.

КОНВЕНЦИЯ ВХОДА взята ИЗ КОДА, не изобретена: движок открывает позицию по цене
ЗАКРЫТИЯ сигнального бара (engine.py:273 price = float(row["close"]),
:362-363 entry_price=price, entry_date=dt, где dt = row.name).

ПОЧЕМУ ПО НОМЕРУ ВЫЗОВА, а не по дате: IndicatorValues метки времени не несёт
(замерено — в нём 30+ полей, ни одного временного). evaluate() зовётся движком
РОВНО ОДИН РАЗ на бар в цикле range(_warmup_bars, len(df_ind)), поэтому N-й вызов
соответствует бару с индексом _warmup_bars + N - 1. Индекс целевого бара считается
МЕТОДАМИ САМОГО ДВИЖКА (_drop_forming_bar + _indicators.compute), а не повторной
реализацией его подготовки.

ФИЛЬТР ДАУНТРЕНДА ВЫКЛЮЧАЕТСЯ НАМЕРЕННО и только он: structural_downtrend_filter
отдаёт {}, из-за чего _downtrend_gate возвращает None. Без этого контрфактный вход
отвергнутого сигнала был бы отвергнут повторно — тем самым фильтром. Больше гейт
нигде не участвует: dt_gate читается только в ветке входа.
"""
import sys

import pandas as pd
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bot"))

from signals.rules_engine import RulesEngine, Action, SignalResult   # noqa: E402
from backtest.engine import BacktestEngine                            # noqa: E402


class ForcedEntryRules:
    """Восемь членов интерфейса. Семь ДЕЛЕГИРУЮТСЯ, один подменён."""

    def __init__(self, real: RulesEngine, fire_at: set[int]):
        self._real = real
        self._fire_at = set(fire_at)   # порядковые номера вызовов evaluate, с 0
        self._n = -1
        self.fired: list[int] = []

    # ── подменён РОВНО ОДИН член ──────────────────────────────────────────
    def evaluate(self, iv, ticker: str = "") -> SignalResult:
        self._n += 1
        if self._n in self._fire_at:
            self.fired.append(self._n)
            return SignalResult(action=Action.BUY, score=0.0, triggered_rules=[])
        return SignalResult(action=Action.HOLD, score=0.0, triggered_rules=[])

    # ── делегируются боевому движку ───────────────────────────────────────
    def evaluate_exit(self, iv, ticker: str = ""):
        return self._real.evaluate_exit(iv, ticker)

    @property
    def indicator_params(self):   return getattr(self._real, "indicator_params", {})
    @property
    def divergence_params(self):  return getattr(self._real, "divergence_params", {})
    @property
    def swing_stop_params(self):  return getattr(self._real, "swing_stop_params", {})
    @property
    def wrd_params(self):         return getattr(self._real, "wrd_params", {})
    @property
    def rules_version(self):      return self._real.rules_version

    # ВЫКЛЮЧЕН НАМЕРЕННО — см. докстринг модуля
    @property
    def structural_downtrend_filter(self):  return {}


def bar_index(engine: BacktestEngine, ticker: str, df, ts):
    """Индекс целевого бара в кадре, по которому идёт цикл движка.

    Подготовка берётся МЕТОДАМИ ДВИЖКА, чтобы не разойтись с ним молча.
    """
    d = engine._drop_forming_bar(ticker, df)
    di = engine._indicators.compute(d)
    # Метка приводится к ВИДУ ИНДЕКСА, а не наоборот: какой он — свойство кадра,
    # и угадывать его нельзя. Замерено: индекс кадра tz-naive, а метки в
    # замороженных CSV и в БД приходят tz-aware.
    ts = pd.Timestamp(ts)
    if di.index.tz is None and ts.tz is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    elif di.index.tz is not None and ts.tz is None:
        ts = ts.tz_localize(di.index.tz)
    return di.index.get_loc(ts), len(di)


def run_forced(rules_file: Path, ticker: str, df, entry_ts, capital=1_000_000.0):
    """Один изолированный прогон: один принудительный вход, боевые выход и издержки."""
    real = RulesEngine(rules_file=rules_file)
    probe = BacktestEngine(rules_engine=real, timeframe="D1", initial_capital=capital)
    i, _ = bar_index(probe, ticker, df, entry_ts)
    call = i - probe._warmup_bars
    if call < 0:
        raise SystemExit(f"ОТКАЗ ФОРМЫ: бар {entry_ts} внутри разогрева ({i} < {probe._warmup_bars})")
    stub = ForcedEntryRules(real, {call})
    eng = BacktestEngine(rules_engine=stub, timeframe="D1", initial_capital=capital)
    res = eng.run(ticker, df)
    if not stub.fired:
        raise SystemExit(f"ОТКАЗ ФОРМЫ: заглушка не сработала ни разу для {ticker} {entry_ts}")
    return res
