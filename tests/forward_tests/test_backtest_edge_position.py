"""Долг №25: позиция, открытая на краю данных, вне n/WR/PF/PnL.

Предмет. `backtest/engine.py` закрывал такую позицию по последней цене и писал
результат в статистику наравне с выходами по правилу. Последний бар каждый день
другой, поэтому число дрейфовало САМО, без единой правки кода. Замерено 30.07 на
живых данных, одна позиция SBER, разрез osc_range D1 OOS без фильтра:

    окно по сессию 27.07 → pnl фантома +21 117.22 → PnL разреза +74 054.52
    окно по сессию 28.07 → pnl фантома +14 809.73 → PnL разреза +67 747.03
    окно по сессию 29.07 → pnl фантома +24 914.27 → PnL разреза +77 851.57

Остальные 205 сделок разреза во всех трёх прогонах побайтово идентичны: весь
разброс +67 747…+77 852 создавала ОДНА незакрытая позиция.

Главный тест здесь — не «поле заполнено», а ИНВАРИАНТНОСТЬ ПРЕФИКСА: обрезка серии
не имеет права менять сделки, закрытые до точки обрезки. Это конструкционное
свойство, из которого дрейф невозможен; проверка полей — лишь его следствие.

Стенд общий с test_forward_catchup / test_costs_and_commission. Там вход и выход
специально уводили ВНУТРЬ серии, чтобы принудительное закрытие в кейс не попало —
здесь наоборот, оно и есть предмет.
"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import pandas as pd

import costs
from backtest.engine import BacktestEngine
from tests.forward_tests.test_forward_catchup import StubRules, _bars, _smooth

C = costs.COMMISSION_PCT
CAPITAL = 1_000_000.0

# Индексы подобраны так, чтобы позиция ДОЖИЛА до конца серии: стоп и трейлинг
# работают, и вход слишком рано их бы задел. Проверяется предусловиями в каждом
# тесте (assert на len), а не предполагается.
N_BARS = 300
BUY_CLOSED = 260      # эта сделка закрывается по правилу внутри серии
SELL_CLOSED = 270
PREFIX_CUT = 285      # обрезка ПОСЛЕ закрытой сделки, но ВНУТРИ открытой


def _frame(closes) -> pd.DataFrame:
    rows = _bars(closes)
    return pd.DataFrame(
        {k: [r[k] for r in rows] for k in ("open", "high", "low", "close", "volume")},
        index=pd.DatetimeIndex([r["time"].replace(tzinfo=None) for r in rows],
                               name="datetime"),
    )


def _engine(rules) -> BacktestEngine:
    return BacktestEngine(initial_capital=CAPITAL, lot_size=1, timeframe="D1",
                          rules_engine=rules)


class TestOpenPositionIsOutOfStatistics(unittest.TestCase):
    """Одна закрытая сделка + одна открытая на последнем баре."""

    def setUp(self):
        self.closes = _smooth(N_BARS)
        self.df = _frame(self.closes)
        rules = StubRules(buy_at=(self.closes[BUY_CLOSED], self.closes[-1]),
                          sell_at=(self.closes[SELL_CLOSED],))
        self.res = _engine(rules).run("SBER", self.df)
        self.assertEqual(len(self.res.trades), 1,
                         "предусловие: ровно одна ЗАКРЫТАЯ сделка")
        self.assertEqual(len(self.res.open_trades_at_end), 1,
                         "предусловие: ровно одна позиция открыта на краю данных")

    def test_n_counts_closed_trades_only(self):
        """n = закрытые. Раньше счётчик инкрементировался на ВХОДЕ, то есть
        незакрытая попадала и в n, и в знаменатель WR."""
        self.assertEqual(self.res.total_trades, 1)
        self.assertEqual(self.res.total_trades,
                         self.res.winning_trades + self.res.losing_trades,
                         "n обязано быть тождественно сумме побед и потерь")

    def test_total_pnl_excludes_the_open_position(self):
        self.assertAlmostEqual(self.res.total_pnl, self.res.trades[0].pnl, places=6)

    def test_profit_factor_is_built_on_closed_trades_only(self):
        closed = self.res.trades[0]
        expected = float("inf") if closed.pnl > 0 else 0.0
        if closed.pnl > 0:
            self.assertEqual(self.res.profit_factor, expected)
        self.assertNotIn(self.res.open_trades_at_end[0], self.res.trades)

    def test_open_trade_keeps_status_open(self):
        """Статус OPEN, а не WIN/LOSS: в CSV фантом был помечен `WIN` и не
        отличался от закрытого по правилу ничем."""
        self.assertEqual(self.res.open_trades_at_end[0].status, "OPEN")
        self.assertIsNone(self.res.open_trades_at_end[0].exit_price)
        self.assertIsNone(self.res.open_trades_at_end[0].exit_date)

    def test_unrealized_subtracts_both_commissions(self):
        t = self.res.open_trades_at_end[0]
        last_price = float(self.df["close"].iloc[-1])
        entry_comm = t.entry_price * t.shares * C
        exit_comm = t.shares * last_price * C
        expected = (last_price - t.entry_price) * t.shares - entry_comm - exit_comm
        self.assertAlmostEqual(self.res.unrealized_pnl, expected, places=6)

    def test_unrealized_is_not_added_to_pnl_by_the_old_convention(self):
        """Страховка от теста, который прошёл бы на дефекте.

        На старом коде эта же серия дала бы n=2 и PnL, включающий нереализованное.
        """
        self.assertNotAlmostEqual(
            self.res.total_pnl,
            self.res.trades[0].pnl + self.res.unrealized_pnl, places=6)
        self.assertNotEqual(self.res.total_trades, 2)

    def test_summary_names_the_open_position(self):
        """Тихо выбросить позицию было бы хуже дефекта: дрейф хотя бы виден в
        числах, а пропавшая позиция — ни в чём."""
        self.assertIn("открыто на краю: 1", self.res.summary())

    def test_equity_curve_identity_with_an_open_position(self):
        """equity[-1] == C0 + Σpnl + нереализованное + КОМИССИЯ ВЫХОДА.

        Последнее слагаемое — не мелочь: комиссия выхода не уплачена, потому что
        выхода не было. Прежнее равенство `equity[-1] == C0 + Σpnl` держалось только
        потому, что принудительное закрытие платило её. На нём стоит потикерный
        бюджет форварда, поэтому условие записано явно.
        """
        t = self.res.open_trades_at_end[0]
        last_price = float(self.df["close"].iloc[-1])
        exit_comm = t.shares * last_price * C
        self.assertAlmostEqual(
            self.res.equity_curve[-1],
            CAPITAL + self.res.total_pnl + self.res.unrealized_pnl + exit_comm,
            places=6)


class TestNoOpenPositionMeansEmptyList(unittest.TestCase):
    """«Открытых: 0» получается из пустого списка само, без отдельной ветки."""

    def setUp(self):
        closes = _smooth(N_BARS)
        rules = StubRules(buy_at=(closes[BUY_CLOSED],), sell_at=(closes[SELL_CLOSED],))
        self.res = _engine(rules).run("SBER", _frame(closes))

    def test_list_is_empty_and_unrealized_is_zero(self):
        self.assertEqual(self.res.open_trades_at_end, [])
        self.assertEqual(self.res.unrealized_pnl, 0.0)

    def test_summary_says_nothing_about_open_positions(self):
        self.assertNotIn("открыто на краю", self.res.summary())

    def test_old_equity_identity_still_holds_when_flat_at_the_end(self):
        """Ровно то, что проверяет P4 в test_costs_and_commission: на плоском конце
        равенство `equity[-1] == C0 + Σpnl` не изменилось."""
        self.assertAlmostEqual(self.res.equity_curve[-1],
                               CAPITAL + self.res.total_pnl, places=6)


class _PrefixCase(unittest.TestCase):
    """Общий стенд: один и тот же стаб на полной серии и на её префиксе."""

    BUY = SELL = None   # задаются наследником

    def setUp(self):
        if self.BUY is None:
            self.skipTest("базовый класс")
        self.closes = _smooth(N_BARS)
        self.df = _frame(self.closes)
        self.cut_at = self.df.index[PREFIX_CUT]
        # Отдельный движок и отдельный стаб на каждый прогон: состояние не должно
        # перетекать между сериями, иначе тест проверял бы не то, что заявлено.
        self.full = _engine(self._rules()).run("SBER", self.df)
        self.prefix = _engine(self._rules()).run("SBER", self.df.iloc[:PREFIX_CUT + 1])

    def _rules(self):
        return StubRules(buy_at=(self.closes[self.BUY],),
                         sell_at=(self.closes[self.SELL],))

    @staticmethod
    def _key(t):
        return (t.ticker, t.entry_date, t.exit_date, round(t.pnl, 6), t.status)

    def _retained(self):
        """Сделки полного прогона, закрытые не позже точки обрезки."""
        return [self._key(t) for t in self.full.trades if t.exit_date <= self.cut_at]


class TestPrefixCutInsideAnOpenPosition(_PrefixCase):
    """ГЛАВНЫЙ тест: обрезка ВНУТРИ открытой позиции ничего не выдумывает.

    Из этого свойства дрейф невозможен по построению — а не «сегодня не наблюдается».
    На старом коде падает: позиция, открытая до обрезки, принудительно закрывалась по
    последнему бару префикса и появлялась в статистике как состоявшаяся сделка,
    которой в полном прогоне НЕТ.

    Вход 260, выход по правилу 290, обрезка 285 — то есть точка обрезки заведомо
    попадает в середину сделки. Предусловие проверяется, а не предполагается.
    """

    BUY, SELL = BUY_CLOSED, 290

    def test_precondition_position_is_open_at_the_cut(self):
        self.assertEqual(len(self.prefix.open_trades_at_end), 1)
        self.assertEqual(len(self.full.trades), 1,
                         "в полном прогоне та же сделка закрыта по правилу")

    def test_prefix_invents_no_closed_trade(self):
        """Именно это ломал долг №25."""
        self.assertEqual([self._key(t) for t in self.prefix.trades], self._retained())
        self.assertEqual(self.prefix.trades, [],
                         "до обрезки ни одна сделка не закрылась — значит и в префиксе"
                         " закрытых быть не может")

    def test_prefix_statistics_are_empty_not_fabricated(self):
        self.assertEqual(self.prefix.total_trades, 0)
        self.assertEqual(self.prefix.total_pnl, 0.0)
        self.assertEqual(self.prefix.win_rate, 0.0)

    def test_no_closed_trade_exits_on_the_cut_bar(self):
        """Прямая проверка признака дефекта: выход ровно на последнем баре серии.

        На старом коде у префикса была ровно такая сделка — статус WIN/LOSS, отличить
        от выхода по правилу нечем.
        """
        self.assertEqual([t for t in self.prefix.trades if t.exit_date == self.cut_at], [])

    def test_the_same_position_is_still_open_and_marked_to_market(self):
        t = self.prefix.open_trades_at_end[0]
        self.assertEqual(t.entry_date, self.full.trades[0].entry_date,
                         "это та же самая сделка, просто ещё не завершённая")
        self.assertNotEqual(self.prefix.unrealized_pnl, self.full.trades[0].pnl,
                            "нереализованное на баре обрезки не равно итогу сделки — "
                            "именно поэтому его нельзя складывать в PnL")


class TestPrefixCutAfterTheTradeClosed(_PrefixCase):
    """Вторая половина инварианта: закрытая до обрезки сделка совпадает ДО КОПЕЙКИ."""

    BUY, SELL = BUY_CLOSED, SELL_CLOSED

    def test_precondition_trade_closed_before_the_cut(self):
        self.assertEqual(len(self.full.trades), 1)
        self.assertLess(self.full.trades[0].exit_date, self.cut_at)
        self.assertEqual(self.prefix.open_trades_at_end, [],
                         "на конце префикса позиции нет")

    def test_retained_trade_is_identical(self):
        self.assertEqual([self._key(t) for t in self.prefix.trades], self._retained())

    def test_pnl_is_identical_to_the_kopeck(self):
        self.assertAlmostEqual(self.prefix.total_pnl, self.full.total_pnl, places=6)


if __name__ == "__main__":
    unittest.main()
