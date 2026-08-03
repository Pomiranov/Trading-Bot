"""Долг №48, форма II: фильтр обязан считаться на БАРЕ РЕШЕНИЯ, а не на последней
строке выборки.

ПРЕДМЕТ. `TradingOrchestrator._check_structural_downtrend` читает свечи СВОИМ
запросом без верхней границы и берёт `.iloc[-1]` полной серии. Совпадает с бэктестом
(`dt_gate.iloc[i]`, значение НА баре решения) только тогда, когда последняя строка
выборки и есть бар решения. У форварда это редкость (слот 00:15 стоит до открытия
биржи), у живого контура — никогда: `main.py:222` передаёт `timeframe "1h"`, а запрос
фильтра жёстко берёт `timeframe='1d'`, то есть последняя дневная строка у него всегда
формирующийся бар сегодняшнего дня.

ИНВАРИАНТ: `skipped_signals.details.last_close` равен `close` ЦЕЛЕВОГО бара (бара
решения), а не последней строки выборки.

ЧЕМ ФЕЙК ЧЕСТЕН. `_FakeConn.fetch` применяет верхнюю границу **только если код её
передал**. До правки запрос идёт с одним параметром, границы нет, фейк возвращает всё
— и тест падает на настоящей причине, а не на подстроенной. Проверять «фильтр
получил границу» через мок вызова было бы проверкой формы вызова; здесь проверяется
результат.

ЧТО ЗДЕСЬ НЕ ПРОВЕРЯЕТСЯ. Паритет контуров с включённым фильтром — долг №49, он
остаётся открытым. Этот файл проверяет ОДИН контур (оркестратор) на ОДНОМ инварианте.
"""
import asyncio
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bot"))

from market_time import d1_bar_time                       # noqa: E402
from learning.trading_orchestrator import TradingOrchestrator  # noqa: E402

PARAMS = dict(sma_short=50, sma_long=200, lower_low_lookback=120, lower_low_window=20)
CFG = dict(enabled=True, apply_to="long", **PARAMS)

SESSIONS = 400
DECISION_SESSION = date(2026, 7, 31)      # бар решения — как в парном контроле
NEXT_SESSION = date(2026, 8, 1)           # синтетическая строка «сегодня»
DECISION_CLOSE = 525.90                   # close бара решения
NEXT_CLOSE_B = 526.50                     # прогон B: бар почти не сдвинулся
NEXT_CLOSE_C = 700.00                     # прогон C: бар выше SMA200


def _daily_rows(next_close: float | None):
    """Монотонный спад: на баре решения все три условия фильтра выполнены.

    Спад намеренно монотонный — тогда переворот условий не зависит от подбора пути,
    и тест не сломается от правки, не касающейся предмета.
    """
    first = DECISION_SESSION - timedelta(days=SESSIONS - 1)
    rows = []
    for k in range(SESSIONS):
        session = first + timedelta(days=k)
        # 900 -> DECISION_CLOSE линейно
        close = 900.0 - (900.0 - DECISION_CLOSE) * k / (SESSIONS - 1)
        rows.append({"time": d1_bar_time(session), "close": close})
    rows[-1]["close"] = DECISION_CLOSE
    if next_close is not None:
        rows.append({"time": d1_bar_time(NEXT_SESSION), "close": next_close})
    return rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, sql, *args):
        rows = self._rows
        # Границу применяем ТОЛЬКО если код её передал вторым параметром.
        if len(args) >= 2 and args[1] is not None:
            until = args[1]
            rows = [r for r in rows if r["time"] < until]
        return rows


class _FakePool:
    def __init__(self, rows):
        self._conn = _FakeConn(rows)

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool._conn

            async def __aexit__(self, *exc):
                return False
        return _Ctx()


class _FakeEvaluator:
    def __init__(self):
        self.skips = []

    async def log_skip(self, **kw):
        self.skips.append(kw)


def _run(next_close, *, pass_boundary: bool):
    """Прогнать проверку фильтра. Возвращает (причина_отказа, записанные skip'ы)."""
    orch = TradingOrchestrator(dsn="postgresql://unused/unused")
    orch._pool = _FakePool(_daily_rows(next_close))
    orch.evaluator = _FakeEvaluator()
    orch._structural_filter_config = lambda _sid: dict(CFG)

    signal = {
        "strategy_id": "osc_range_moex_d1_fwd",
        "ticker": "TATN",
        "direction": "BUY",
        "timeframe": "D1",
        "is_sandbox": True,
    }
    if pass_boundary:
        # Начало сессии, В КОТОРОЙ принимается решение: сессия бара решения уже
        # закрыта, поэтому её фильтр видеть обязан, а следующую — нет.
        signal["filter_until"] = d1_bar_time(DECISION_SESSION + timedelta(days=1))
    reason = asyncio.run(orch._check_structural_downtrend(signal))
    return reason, orch.evaluator.skips


class DowntrendFilterBoundary(unittest.TestCase):

    # ── 0. Синтетика нетривиальна ─────────────────────────────────────────

    def test_decision_bar_is_in_downtrend_and_next_bar_is_not(self):
        """Без этого различия прогон C ничего не показывал бы."""
        from signals.indicators import structural_downtrend_series
        rows = _daily_rows(NEXT_CLOSE_C)
        s = structural_downtrend_series(
            pd.DataFrame({"close": [r["close"] for r in rows]},
                         index=pd.DatetimeIndex([r["time"] for r in rows])), **PARAMS)
        self.assertTrue(bool(s.iloc[-2]), "на баре решения даунтренд обязан быть")
        self.assertFalse(bool(s.iloc[-1]),
                         "на синтетическом баре close=700 даунтренда быть не должно")

    # ── 1. Главный инвариант. ДО правки падает ────────────────────────────

    def test_last_close_is_the_decision_bar_not_the_last_row(self):
        """Прогон B: `last_close` обязан быть 525.90, а не 526.50."""
        reason, skips = _run(NEXT_CLOSE_B, pass_boundary=True)
        self.assertIsNotNone(reason, "отказ обязан состояться: даунтренд есть")
        self.assertEqual(len(skips), 1)
        self.assertAlmostEqual(skips[0]["details"]["last_close"], DECISION_CLOSE, places=2,
                               msg="фильтр посчитан по последней строке выборки, "
                                   "а не по бару решения")

    def test_bar_of_a_forming_session_cannot_cancel_the_filter(self):
        """Прогон C, НЕСУЩИЙ: сегодня дефект открывает сделку, которой быть не должно.

        Синтетический бар `close 700` уводит цену выше SMA200; фильтр по `.iloc[-1]`
        говорит «даунтренда нет» и вход разрешается — хотя на баре решения даунтренд
        есть. После правки отказ обязан состояться.
        """
        reason, skips = _run(NEXT_CLOSE_C, pass_boundary=True)
        self.assertIsNotNone(reason, "формирующийся бар отменил фильтр — вход разрешён")
        self.assertEqual(len(skips), 1)
        self.assertAlmostEqual(skips[0]["details"]["last_close"], DECISION_CLOSE, places=2)

    def test_night_case_unchanged(self):
        """Прогон A: строки за следующую сессию нет — было и остаётся 525.90."""
        reason, skips = _run(None, pass_boundary=True)
        self.assertIsNotNone(reason)
        self.assertAlmostEqual(skips[0]["details"]["last_close"], DECISION_CLOSE, places=2)

    # ── 2. Живой контур: границы не передаёт, чинится запасным путём ──────

    def test_live_caller_without_boundary_still_excludes_forming_session(self):
        """`main.py` не правится: границу он не передаёт.

        Запасной путь берёт начало ТЕКУЩЕЙ московской сессии. Синтетическая строка
        сессии 2026-08-01 в прошлом относительно сегодняшней даты, поэтому этот тест
        НЕ доказывает поведение живого контура на свежих данных — он доказывает
        только, что путь без границы не падает и отказ по бару решения состоится.
        Живой контур доказывается прогоном (Г2), а не здесь; см. оговорку в шапке.
        """
        reason, skips = _run(NEXT_CLOSE_B, pass_boundary=False)
        self.assertIsNotNone(reason, "без границы отказ всё равно обязан состояться")
        self.assertEqual(len(skips), 1)


if __name__ == "__main__":
    unittest.main()
