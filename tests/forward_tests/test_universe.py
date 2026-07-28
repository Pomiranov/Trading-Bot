"""Наборы тикеров: фиксация проверяема, а не обещана.

Требование 5 §7 PROJECT_STATE: портфель тикеров фиксируется ДО прогона, иначе
отбор инструментов сам становится оптимизацией. Обещание в документе этого не
обеспечивает, поэтому отпечатки наборов захардкожены ЗДЕСЬ: тихая правка любого
набора ломает тест.

Отдельно проверяется, что приколоченный 12-тикерный набор не изменился — на нём
посчитаны все опорные числа проекта (18/72.2%/1.64/+127 748 и
30/60.0%/1.20/+74 055), и его изменение сделало бы их невоспроизводимыми молча.
"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

from universe import (
    FORWARD_TICKERS,
    FORWARD_TICKERS_FIXED_AT,
    FORWARD_TICKERS_VERSION,
    MEASUREMENT_UNIVERSE_2026_07,
    MEASUREMENT_UNIVERSE_2026_07_EXT,
    MEASUREMENT_UNIVERSE_2026_07_EXT_VERSION,
    MEASUREMENT_UNIVERSE_2026_07_VERSION,
    universe_version,
)

# Захардкожены намеренно. Совпадают со значениями в docs/PROJECT_STATE.md:
# два места, и оба надо править сознательно.
EXPECTED_12 = "753d9f90fef9401e"
EXPECTED_20 = "0b2df2ce43ffaa25"

NEW_8 = ("AFLT", "FLOT", "MTLR", "MTSS", "OZON", "PHOR", "SMLT", "VKCO")


class TestPinnedUniverseUnchanged(unittest.TestCase):
    """Приколоченный набор — основание всех опорных чисел."""

    def test_fingerprint_matches_recorded(self):
        self.assertEqual(MEASUREMENT_UNIVERSE_2026_07_VERSION, EXPECTED_12,
                         "12-тикерный набор изменён: все прошлые PF стали "
                         "невоспроизводимыми. Если изменение намеренное — правьте "
                         "и этот тест, и PROJECT_STATE.")

    def test_still_twelve(self):
        self.assertEqual(len(MEASUREMENT_UNIVERSE_2026_07), 12)

    def test_exact_composition(self):
        self.assertEqual(MEASUREMENT_UNIVERSE_2026_07, (
            "ALRS", "CHMF", "GAZP", "LKOH", "MGNT", "MOEX",
            "NVTK", "PLZL", "ROSN", "SBER", "SNGS", "TATN"))


class TestExtendedUniverse(unittest.TestCase):

    def test_fingerprint_matches_recorded(self):
        self.assertEqual(MEASUREMENT_UNIVERSE_2026_07_EXT_VERSION, EXPECTED_20)

    def test_is_superset_of_pinned(self):
        """Расширение ДОБАВЛЯЕТ бумаги, а не заменяет: иначе прошлые и новые
        измерения нельзя было бы сопоставить даже качественно."""
        self.assertTrue(set(MEASUREMENT_UNIVERSE_2026_07) < set(MEASUREMENT_UNIVERSE_2026_07_EXT))

    def test_exactly_eight_new(self):
        added = tuple(sorted(set(MEASUREMENT_UNIVERSE_2026_07_EXT)
                             - set(MEASUREMENT_UNIVERSE_2026_07)))
        self.assertEqual(added, NEW_8)

    def test_two_universes_have_different_fingerprints(self):
        """Иначе отпечаток не различал бы прогоны — весь смысл в этом."""
        self.assertNotEqual(MEASUREMENT_UNIVERSE_2026_07_VERSION,
                            MEASUREMENT_UNIVERSE_2026_07_EXT_VERSION)


class TestForwardUniverse(unittest.TestCase):

    def test_forward_uses_twenty(self):
        self.assertEqual(len(FORWARD_TICKERS), 20)
        self.assertEqual(FORWARD_TICKERS_VERSION, EXPECTED_20)

    def test_fixation_date_recorded(self):
        self.assertEqual(FORWARD_TICKERS_FIXED_AT, "2026-07-28")


class TestFingerprintProperties(unittest.TestCase):

    def test_order_does_not_matter(self):
        """Отпечаток от СОСТАВА, не от порядка строк в файле."""
        a = ("SBER", "GAZP", "LKOH")
        self.assertEqual(universe_version(a), universe_version(tuple(reversed(a))))

    def test_one_ticker_changes_it(self):
        self.assertNotEqual(universe_version(("SBER", "GAZP")),
                            universe_version(("SBER", "GAZP", "LKOH")))


class TestConsumersUseTheRightUniverse(unittest.TestCase):
    """Измерительные скрипты — на приколоченном, форвард и сторож — на растущем.

    Это и есть механизм, из-за которого гейт выполним: перевод измерительных
    скриптов на растущий набор обязательно изменил бы опорные тройки.
    """

    MEASUREMENT = ("run_osc_oos_debug.py", "run_ab_tf_backtest.py",
                   "run_ab_swing_stop.py", "run_ab_trend_fix.py",
                   "run_wrd_backtest.py")

    def test_measurement_scripts_pinned(self):
        for name in self.MEASUREMENT:
            text = (_ROOT / "bot" / "backtest" / name).read_text(encoding="utf-8")
            self.assertIn("TICKERS = list(MEASUREMENT_UNIVERSE_2026_07)", text, name)
            self.assertNotIn("FORWARD_TICKERS", text,
                             f"{name}: измерительный скрипт не должен ходить по растущему набору")

    def test_forward_and_watchdog_growing(self):
        for rel in ("bot/run_forward_d1.py", "bot/forward_healthcheck.py"):
            text = (_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("TICKERS = list(FORWARD_TICKERS)", text, rel)

    def test_no_hardcoded_list_remains(self):
        """Девять копий списка были той же болезнью, что три копии 0.0003."""
        for rel in list(self.MEASUREMENT) + ["../run_forward_d1.py", "../forward_healthcheck.py"]:
            p = (_ROOT / "bot" / "backtest" / rel).resolve()
            self.assertNotIn('TICKERS = ["SBER"', p.read_text(encoding="utf-8"), str(p))



class TestUniverseStampedOnTrades(unittest.TestCase):
    """Отпечаток НАБОРА доезжает до строки trades (долг №33).

    Без него confidence у одной strategy_id смешивает эру 12 бумаг и эру 20:
    belief_system агрегирует по strategy_id, и скаляр перестаёт описывать один
    набор. Восстановимость по ticker+дате — это запрос, который надо догадаться
    написать.
    """

    def test_forward_trade_carries_forward_universe(self):
        from tests.forward_tests.test_forward_catchup import (
            FakeDB, StubRules, _bars, _make_runner, _run_sync, _smooth,
        )
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={"SBER": times[258]})
        runner, opened, _ = _make_runner(db, StubRules(buy_at=(closes[259],)))
        _run_sync(runner, db)
        self.assertEqual(len(opened), 1, "предусловие: один вход")
        self.assertEqual(opened[0].universe_version, FORWARD_TICKERS_VERSION)
        self.assertEqual(opened[0].origin, "forward")

    def test_backtest_engine_stamps_the_set_it_was_given(self):
        """Движок набора сам знать не может — его передаёт скрипт."""
        from backtest.engine import BacktestEngine
        eng = BacktestEngine(universe_version=MEASUREMENT_UNIVERSE_2026_07_VERSION)
        self.assertEqual(eng._universe_version, MEASUREMENT_UNIVERSE_2026_07_VERSION)
        self.assertNotEqual(eng._universe_version, FORWARD_TICKERS_VERSION,
                            "12-набор и 20-набор обязаны различаться")

    def test_measurement_scripts_pass_their_universe(self):
        for name in ("run_osc_oos_debug.py", "run_ab_tf_backtest.py",
                     "run_ab_swing_stop.py", "run_ab_trend_fix.py",
                     "run_wrd_backtest.py"):
            text = (_ROOT / "bot" / "backtest" / name).read_text(encoding="utf-8")
            self.assertIn("universe_version=MEASUREMENT_UNIVERSE_2026_07_VERSION", text, name)

    def test_trade_dataclass_has_the_field(self):
        from learning.memory_writer import Trade
        self.assertIn("universe_version", Trade.__dataclass_fields__)

    def test_insert_writes_the_column(self):
        text = (_ROOT / "bot" / "learning" / "memory_writer.py").read_text(encoding="utf-8")
        self.assertIn("universe_version", text.split("INSERT INTO trades")[1].split(") VALUES")[0],
                      "колонка обязана быть в списке INSERT, иначе поле никуда не доедет")
        self.assertIn("trade.universe_version", text)

if __name__ == "__main__":
    unittest.main()
