"""Издержки: единственный источник ставки (P7) и комиссия ВХОДА в pnl (P4).

Предмет P4. `trades.pnl` в обоих контурах вычитал только комиссию ВЫХОДА, тогда
как траектория капитала бэктеста вычитала обе (`engine.py`, `run()` при входе и
`_close` при выходе). Из-за этого `initial_capital + Σpnl` не сходился с
`equity_curve[-1]` на сумму комиссий входа, а форвардный `_paper_capital`,
построенный на `Σpnl`, завышал бюджет — и после первой закрытой сделки сайзинг
разошёлся бы с бэктестом. Это предусловие потикерного бюджета, а не отдельная
опрятность: бэктест считает размер позиции от ЭВОЛЮЦИОНИРУЮЩЕГО capital
(`engine.py:248`), поэтому бюджет обязан повторять его формулу буквально.

Предмет P7. Ставка была продублирована в восьми местах, одно из них с
комментарием «must match engine/paper_engine.py» — ручная синхронизация уже
была признана. Тест держит инвариант «один объект», а не «равные значения»:
`from costs import COMMISSION_PCT` связывает ТОТ ЖЕ объект, поэтому `is`
отличает импорт от перепечатанного литерала.
"""

import inspect
import sys
import unittest
from decimal import Decimal
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import pandas as pd

import costs
import run_forward_d1 as fwd
from backtest.engine import BacktestEngine
from tests.forward_tests.test_forward_catchup import (
    FakeDB, StubRules, _bars, _make_runner, _run_sync, _seed_position, _smooth,
)

C = costs.COMMISSION_PCT


# ─────────────────────────────────────────────────────────────────────────────
# P7 — ставка комиссии живёт в одном месте
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleSourceOfCommission(unittest.TestCase):

    def test_forward_uses_the_shared_constant(self):
        self.assertIs(fwd.COMMISSION_PCT, costs.COMMISSION_PCT)

    def test_backtest_default_is_the_shared_constant(self):
        default = inspect.signature(BacktestEngine.__init__).parameters["commission_pct"].default
        self.assertIs(default, costs.COMMISSION_PCT)

    def test_paper_engine_uses_the_shared_constant(self):
        from engine import paper_engine
        self.assertIs(paper_engine.COMMISSION_PCT, costs.COMMISSION_PCT)

    def test_paper_trading_service_uses_the_shared_constant(self):
        from qf_platform.services import paper_trading_service
        self.assertIs(paper_trading_service.COMMISSION_PCT, costs.COMMISSION_PCT)

    def test_backtest_dto_default_is_the_shared_constant(self):
        from qf_platform.dto import BacktestRequestDTO
        self.assertIs(BacktestRequestDTO().commission_pct, costs.COMMISSION_PCT)

    def test_no_module_retypes_the_literal(self):
        """Литерал ставки не должен встречаться нигде, кроме costs.py и DDL.

        Тест структурный, потому что два места используют ставку как значение по
        умолчанию внутри тела функции (`.get("commission_pct", ...)`), и туда
        `is`-проверкой не добраться. `schema.py` — SQL DDL, импортировать
        costs.py он не может: значение уже применено к живой таблице, менять его
        нельзя, там остаётся комментарий-ссылка.
        """
        literal = repr(costs.COMMISSION_PCT).lstrip("0")   # ".0003"
        offenders = []
        for rel in ("run_forward_d1.py", "backtest/engine.py", "engine/paper_engine.py",
                    "qf_platform/services/paper_trading_service.py", "qf_platform/dto.py",
                    "ui/api/platform_routes.py",
                    "qf_platform/repositories/backtest_repository.py"):
            text = (_ROOT / "bot" / rel).read_text(encoding="utf-8")
            for n, line in enumerate(text.splitlines(), 1):
                if literal in line and "costs.py" not in line:
                    offenders.append(f"{rel}:{n}: {line.strip()}")
        self.assertEqual(offenders, [], "ставка перепечатана литералом:\n" + "\n".join(offenders))


# ─────────────────────────────────────────────────────────────────────────────
# P4 — pnl вычитает ОБЕ комиссии
# ─────────────────────────────────────────────────────────────────────────────

class TestForwardPnlSubtractsBothCommissions(unittest.TestCase):
    """Стоп на догоняемом баре с известными ценой, входом и размером.

    Дискриминатор: старый код даёт −1503.15 (только выход), новый −1506.75
    (обе стороны). Разница 3.60 = 120·100·0.0003 — комиссия входа.
    """

    ENTRY, STOP, SHARES = 120.0, 110.0, 100

    def setUp(self):
        closes = _smooth(260)
        closes[256] = 115.0
        closes[257] = 105.0      # ← пробитие стопа, здесь выход
        closes[258] = 100.0
        closes[259] = 130.0
        self.exit_price = closes[257]
        self.times = [r["time"] for r in _bars(closes)]

        db = FakeDB(_bars(closes), state={"SBER": self.times[255]})
        _seed_position(db, "SBER", entry=self.ENTRY, stop=self.STOP,
                       opened_at=self.times[252], shares=self.SHARES)
        runner, _, self.closed = _make_runner(db, StubRules())
        _run_sync(runner, db)
        self.assertEqual(len(self.closed), 1, "предусловие: ровно одно закрытие")

    def _expected(self) -> tuple[float, float]:
        entry_comm = self.ENTRY * self.SHARES * C
        exit_comm = self.SHARES * self.exit_price * C
        pnl = (self.exit_price - self.ENTRY) * self.SHARES - entry_comm - exit_comm
        return pnl, entry_comm + exit_comm

    def test_pnl_subtracts_entry_and_exit_commission(self):
        pnl, _ = self._expected()
        self.assertEqual(self.closed[0].pnl, fwd._dec(pnl))

    def test_commission_field_holds_both_sides(self):
        _, commission = self._expected()
        self.assertEqual(self.closed[0].commission, fwd._dec(commission))

    def test_old_convention_is_actually_rejected(self):
        """Страховка от теста, который прошёл бы и на дефекте."""
        old = (self.exit_price - self.ENTRY) * self.SHARES - self.SHARES * self.exit_price * C
        self.assertNotEqual(self.closed[0].pnl, fwd._dec(old))


class TestBacktestPnlSubtractsBothCommissions(unittest.TestCase):
    """Тот же инвариант в бэктесте, плюс главное следствие.

    `equity_curve[-1] == initial_capital + Σpnl` — ровно то равенство, на
    котором стоит потикерный бюджет форварда. До правки оно нарушалось на
    сумму комиссий входа, и именно поэтому правка комиссии обязана идти
    ПЕРЕД сменой режима сайзинга.
    """

    CAPITAL = 1_000_000.0

    def setUp(self):
        closes = _smooth(300)
        rows = _bars(closes)
        self.df = pd.DataFrame(
            {k: [r[k] for r in rows] for k in ("open", "high", "low", "close", "volume")},
            index=pd.DatetimeIndex([r["time"].replace(tzinfo=None) for r in rows],
                                   name="datetime"),
        )
        # Вход на баре 260, выход по SELL на 270: оба внутри серии, поэтому
        # принудительное закрытие на последнем баре в кейс не попадает.
        self.engine = BacktestEngine(
            initial_capital=self.CAPITAL, lot_size=1, timeframe="D1",
            rules_engine=StubRules(buy_at=(closes[260],), sell_at=(closes[270],)),
        )
        self.result = self.engine.run("SBER", self.df)
        self.assertEqual(len(self.result.trades), 1, "предусловие: ровно одна сделка")

    def test_pnl_subtracts_entry_and_exit_commission(self):
        t = self.result.trades[0]
        entry_comm = t.entry_price * t.shares * C
        exit_comm = t.shares * t.exit_price * C
        expected = (t.exit_price - t.entry_price) * t.shares - entry_comm - exit_comm
        self.assertAlmostEqual(t.pnl, expected, places=6)

    def test_equity_curve_agrees_with_sum_of_pnl(self):
        self.assertAlmostEqual(self.result.equity_curve[-1],
                               self.CAPITAL + self.result.total_pnl, places=6)

    def test_capital_trajectory_itself_did_not_change(self):
        """Траектория капитала была верна и до правки — она меняться не должна.

        Проверяется независимо от pnl: конечный капитал = вход·(−1) + выход,
        обе комиссии, посчитанные напрямую из цен сделки.
        """
        t = self.result.trades[0]
        spent = t.entry_price * t.shares * (1 + C)
        got = t.shares * t.exit_price * (1 - C)
        self.assertAlmostEqual(self.result.equity_curve[-1],
                               self.CAPITAL - spent + got, places=6)


if __name__ == "__main__":
    unittest.main()
