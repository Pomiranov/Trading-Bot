"""Потикерный бюджет форварда: форвард измеряет ПРАВИЛА, а не счёт.

Предмет. Форвард держал один общий бумажный капитал на 12 тикеров, а бэктест
давал каждому тикеру независимый 1 млн. При одной позиции в 37–75% капитала
после первого входа второй чаще всего не проходил, `max_open_positions=5` был
недостижим, а порядок списка TICKERS решал, кто войдёт. Сравнение
форвард↔бэктест — основа эпистемики проекта, и оно мерило конкуренцию за
капитал вместо правил.

Главный тест здесь — P3, паритет сделка-в-сделку против настоящего
BacktestEngine. Остальные фиксируют, что снят именно КЛАСС ограничения
(порядок TICKERS, глобальный лимит), а не отдельный симптом, и что портфельный
режим сохранён работоспособным под долг №17.
"""

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import pandas as pd

import run_forward_d1 as fwd
from backtest.engine import BacktestEngine
from tests.forward_tests.test_forward_catchup import (
    FakeDB, StubRules, _bars, _make_runner, _run_sync, _smooth,
)


class FakeDBWithPnl(FakeDB):
    """Стенд, который ПОМНИТ pnl закрытых сделок.

    Без этого многодневный паритет проверить нельзя: базовый стенд пишет при
    закрытии только closed_at, поэтому реализованный PnL всегда выходил нулём и
    бюджет второго дня не отличался от первого — то есть ровно то, что P3
    проверяет, оставалось непроверенным.
    """

    def record_pnl(self, trade) -> None:
        rec = self.trades.get(trade.trade_id)
        if rec is not None:
            rec["pnl"] = float(trade.pnl)


def _runner_with_pnl(db, rules):
    """_make_runner + сохранение pnl в запись сделки при закрытии."""
    runner, opened, closed = _make_runner(db, rules)
    original = runner.orch.on_trade_closed.side_effect

    async def _on_close(trade):
        await original(trade)
        db.record_pnl(trade)

    runner.orch.on_trade_closed.side_effect = _on_close
    return runner, opened, closed


def _df_from_rows(rows) -> pd.DataFrame:
    return pd.DataFrame(
        {k: [r[k] for r in rows] for k in ("open", "high", "low", "close", "volume")},
        index=pd.DatetimeIndex([r["time"].replace(tzinfo=None) for r in rows],
                               name="datetime"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# P0 — флаг режима
# ─────────────────────────────────────────────────────────────────────────────

class TestModeFlag(unittest.TestCase):

    def _flag(self, value=None):
        env = {} if value is None else {"FORWARD_PER_TICKER_CAPITAL": value}
        with patch.dict("os.environ", env, clear=False):
            import os
            if value is None:
                os.environ.pop("FORWARD_PER_TICKER_CAPITAL", None)
            return fwd._per_ticker_capital()

    def test_default_is_per_ticker(self):
        self.assertEqual(self._flag(), (True, None))

    def test_explicit_true_is_per_ticker_without_a_note(self):
        for value in ("true", "1", "yes", "on", "TRUE"):
            self.assertEqual(self._flag(value), (True, None), value)

    def test_portfolio_requires_an_explicit_false_and_is_announced(self):
        for value in ("false", "0", "no", "off", "FALSE"):
            per_ticker, note = self._flag(value)
            self.assertFalse(per_ticker, value)
            self.assertIsNotNone(note, "переход в портфельный режим обязан быть виден")

    def test_typo_does_not_silently_switch_to_portfolio(self):
        """Опечатка не имеет права молча вернуть дефект, который флаг закрывает."""
        per_ticker, note = self._flag("flase")
        self.assertTrue(per_ticker)
        self.assertIsNotNone(note, "нераспознанное значение обязано быть видно")


# ─────────────────────────────────────────────────────────────────────────────
# P1, P2, P5, P6 — снят КЛАСС ограничения
# ─────────────────────────────────────────────────────────────────────────────

class _TwoTickerCase(unittest.TestCase):
    """Два тикера, одинаковая серия, BUY на свежем баре у обоих."""

    TICKERS = ("AAA", "BBB")

    def _run(self, per_ticker: bool, tickers=None):
        tickers = tickers or self.TICKERS
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={t: times[258] for t in tickers})
        env = {"FORWARD_PER_TICKER_CAPITAL": "true" if per_ticker else "false"}
        with patch.dict("os.environ", env, clear=False):
            runner, opened, closed = _make_runner(db, StubRules(buy_at=(closes[259],)))
        _run_sync(runner, db, tickers=tickers)
        return runner, opened, db


class TestPerTickerRemovesCapitalCompetition(_TwoTickerCase):

    def test_per_ticker_lets_both_tickers_in(self):
        runner, opened, _ = self._run(per_ticker=True)
        self.assertEqual(sorted(t.ticker for t in opened), ["AAA", "BBB"])

    def test_portfolio_admits_only_one_and_says_why(self):
        runner, opened, _ = self._run(per_ticker=False)
        self.assertEqual(len(opened), 1, "на общем счёте второй вход не проходит")
        self.assertTrue(any("не хватает капитала" in e for e in runner.events),
                        f"события: {runner.events}")

    def test_ticker_order_no_longer_decides(self):
        """P2: множество открытых сделок не зависит от порядка TICKERS."""
        def fingerprint(opened):
            return sorted((t.ticker, str(t.entry_price), str(t.position_size),
                           str(t.stop_loss)) for t in opened)

        _, fwd_order, _ = self._run(True, tickers=("AAA", "BBB"))
        _, rev_order, _ = self._run(True, tickers=("BBB", "AAA"))
        self.assertEqual(fingerprint(fwd_order), fingerprint(rev_order))
        self.assertEqual(len(fwd_order), 2)

    def test_portfolio_mode_still_depends_on_order(self):
        """Контроль: в портфельном режиме зависимость от порядка сохраняется —
        значит предыдущий тест проверяет снятие ограничения, а не совпадение."""
        _, a, _ = self._run(False, tickers=("AAA", "BBB"))
        _, b, _ = self._run(False, tickers=("BBB", "AAA"))
        self.assertEqual([t.ticker for t in a], ["AAA"])
        self.assertEqual([t.ticker for t in b], ["BBB"])


class TestGlobalPositionLimit(unittest.TestCase):

    TICKERS = ("T01", "T02", "T03", "T04", "T05", "T06",
               "T07", "T08", "T09", "T10", "T11", "T12")

    def test_twelve_tickers_hold_positions_despite_limit_of_five(self):
        """P5: глобальный max_open_positions не связывает потикерный режим."""
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={t: times[258] for t in self.TICKERS})
        with patch.dict("os.environ", {"FORWARD_PER_TICKER_CAPITAL": "true"}, clear=False), \
             patch.object(fwd.config.risk, "max_open_positions", 5):
            runner, opened, _ = _make_runner(db, StubRules(buy_at=(closes[259],)))
            _run_sync(runner, db, tickers=self.TICKERS)
        self.assertEqual(len(opened), 12)

    def test_portfolio_mode_still_enforces_the_limit(self):
        """P6: лимит остаётся рабочим там, где он осмыслен.

        Бюджета хватает на одну позицию, поэтому лимит проверяется отдельно —
        на пяти уже открытых позициях, введённых в состояние стенда.
        """
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={t: times[258] for t in self.TICKERS})
        for k in range(5):                       # пять открытых позиций
            db.trades[f"seed-{k}"] = {
                "trade_id": f"seed-{k}", "ticker": f"T0{k + 1}",
                "entry_price": Decimal("1"), "stop_loss": Decimal("0.5"),
                "position_size": Decimal("1"), "risk_amount": Decimal("1"),
                "opened_at": times[100], "closed_at": None,
            }
        with patch.dict("os.environ", {"FORWARD_PER_TICKER_CAPITAL": "false"}, clear=False), \
             patch.object(fwd.config.risk, "max_open_positions", 5):
            runner, opened, _ = _make_runner(db, StubRules(buy_at=(closes[259],)))
            _run_sync(runner, db, tickers=self.TICKERS)
        self.assertEqual(opened, [], "лимит позиций обязан отклонить вход")
        self.assertTrue(any("лимит позиций" in e for e in runner.events),
                        f"события: {runner.events}")


# ─────────────────────────────────────────────────────────────────────────────
# P3 — паритет сделка-в-сделку с настоящим BacktestEngine
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeByTradeParityWithBacktest(unittest.TestCase):
    """Цель ремонта: те же правила на той же серии → те же сделки.

    Условия корректности кейса:
      - серия 300 баров, сверка с бара 250: префикс >= MIN_HISTORY_BARS;
      - сигналы только на индексах >= 250 — тогда у бэктеста на баре 250
        капитал ровно FORWARD_CAPITAL и стартовые условия совпадают;
      - STALE_DAYS патчится: проверка протухания не предмет этого теста, а на
        обрезанных префиксах она снимала бы тикер;
      - разрывов нет, поэтому расхождение догона в кейс не попадает;
      - принудительное закрытие бэктеста на последнем баре исключается из
        сравнения выходов (у форварда позиция просто остаётся открытой);
      - допуска «±несколько акций» нет: position_size сверяется ТОЧНО, иначе
        тест перестаёт ловить регрессии сайзинга.
    """

    N_BARS = 300
    FIRST = 250

    @classmethod
    def setUpClass(cls):
        closes = _smooth(cls.N_BARS)
        # Две полных сделки: вход 255 → выход 262, вход 270 → выход 280.
        cls.buy_at = (closes[255], closes[270])
        cls.sell_at = (closes[262], closes[280])
        cls.closes = closes
        cls.rows = _bars(closes)
        cls.times = [r["time"] for r in cls.rows]

        # ── Бэктест: один прогон на всей серии ──
        engine = BacktestEngine(
            initial_capital=fwd.FORWARD_CAPITAL, lot_size=1, timeframe="D1",
            rules_engine=StubRules(buy_at=cls.buy_at, sell_at=cls.sell_at),
        )
        cls.bt = engine.run("SBER", _df_from_rows(cls.rows))

        # ── Форвард: N последовательных прогонов по одному свежему бару ──
        cls.fwd_opened, cls.fwd_closed = [], []
        db = FakeDBWithPnl(cls.rows, state={"SBER": cls.times[cls.FIRST - 1]})
        env = {"FORWARD_PER_TICKER_CAPITAL": "true"}
        for i in range(cls.FIRST, cls.N_BARS):
            # Каждый прогон видит историю только до бара i включительно.
            db.candles = cls.rows[:i + 1]
            with patch.dict("os.environ", env, clear=False), \
                 patch.object(fwd, "STALE_DAYS", 10 ** 6):
                runner, opened, closed = _runner_with_pnl(
                    db, StubRules(buy_at=cls.buy_at, sell_at=cls.sell_at))
                _run_sync(runner, db)
            cls.fwd_opened += opened
            cls.fwd_closed += closed

    def test_same_number_of_entries(self):
        self.assertEqual(len(self.fwd_opened), self.bt.total_trades)
        self.assertEqual(len(self.fwd_opened), 2, "предусловие кейса: две сделки")

    def test_entries_match_bar_price_size_and_stop(self):
        for k, (f, b) in enumerate(zip(self.fwd_opened, self.bt.trades)):
            self.assertEqual(f.opened_at.replace(tzinfo=None), b.entry_date,
                             f"бар входа сделки {k}")
            self.assertEqual(float(f.entry_price), b.entry_price, f"цена входа {k}")
            self.assertEqual(int(f.position_size), b.shares, f"размер позиции {k}")
            # Сверять с b.stop_price НЕЛЬЗЯ: трейлинг мутирует его на каждом
            # последующем баре (engine.py:302-305), поэтому к концу прогона там
            # лежит стоп на момент ВЫХОДА. Стоп при ВХОДЕ бэктест сохраняет
            # только в initial_risk = entry − stop (engine.py:260).
            self.assertAlmostEqual(float(f.stop_loss), b.entry_price - b.initial_risk,
                                   places=6, msg=f"стоп при входе {k}")

    def test_exits_match_bar_and_price(self):
        closed_bt = [t for t in self.bt.trades if t.exit_date is not None]
        for k, (f, b) in enumerate(zip(self.fwd_closed, closed_bt)):
            self.assertEqual(f.closed_at.replace(tzinfo=None), b.exit_date,
                             f"бар выхода сделки {k}")
            self.assertEqual(float(f.exit_price), b.exit_price, f"цена выхода {k}")

    def test_pnl_matches_trade_by_trade(self):
        for k, (f, b) in enumerate(zip(self.fwd_closed, self.bt.trades)):
            self.assertAlmostEqual(float(f.pnl), b.pnl, places=4, msg=f"pnl сделки {k}")

    def test_second_entry_is_sized_from_capital_that_absorbed_the_first_pnl(self):
        """Смысловой центр P3: бюджет второй сделки унёс результат первой.

        Если бы потикерный бюджет игнорировал реализованный PnL (или считал его
        по старой конвенции комиссии), размеры совпали бы только у ПЕРВОЙ
        сделки. Тест требует, чтобы вторая сделка отличалась по размеру и всё
        равно совпадала с бэктестом.
        """
        first, second = self.fwd_opened[0], self.fwd_opened[1]
        self.assertNotEqual(int(first.position_size), int(second.position_size),
                            "кейс выродился: размеры совпали, проверять нечего")
        self.assertEqual(int(second.position_size), self.bt.trades[1].shares)


if __name__ == "__main__":
    unittest.main()
