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

from datetime import date

from universe import (
    SAMPLE_START_2026_07,
    SAMPLE_START_2026_07_VERSION,
    sample_version,
    FORWARD_TICKERS,
    FORWARD_TICKERS_ENTERED_AT,
    FORWARD_TICKERS_FIXED_AT,
    FORWARD_TICKERS_PENDING,
    FORWARD_TICKERS_PENDING_ENTERS_AT,
    FORWARD_TICKERS_PENDING_FIXED_AT,
    FORWARD_TICKERS_PENDING_VERSION,
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
# Отпечаток ОКНА выборки (долг №37). Литерал, как EXPECTED_12/20:
# приколоченное значение, а не вычисленное из данных.
EXPECTED_WINDOW = "03d19a4525d7d6c5"

NEW_8 = ("AFLT", "FLOT", "MTLR", "MTSS", "OZON", "PHOR", "SMLT", "VKCO")


def _top_level_imports(code: str) -> set[str]:
    """Модули верхнего уровня, которые импортирует исходник."""
    import re
    mods = set()
    for m in re.finditer(r"^(?:import|from)\s+([A-Za-z_][\w.]*)", code, re.M):
        mods.add(m.group(1).split(".")[0])
    return mods


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
    """Форвард расширен до 20 бумаг 2026-07-30.

    ⚠ ВСЕ утверждения этого класса ЗАВИСЯТ ОТ СОСТАВА набора (правило 2 §8
    PROJECT_STATE). Они падают ЗАКОННО при следующем расширении форварда и
    НЕ означают дефекта. Признак законного падения: изменился
    FORWARD_TICKERS_VERSION вместе с len(FORWARD_TICKERS). Признак дефекта:
    разошлись длина и отпечаток, либо тронут MEASUREMENT_UNIVERSE_2026_07.
    """

    def test_forward_expanded_to_twenty(self):
        self.assertEqual(len(FORWARD_TICKERS), 20)
        self.assertEqual(FORWARD_TICKERS_VERSION, EXPECTED_20)

    def test_active_fixation_date_is_now_the_preregistered_one(self):
        """Утверждение ПЕРЕВЕРНУЛОСЬ 30.07, и это не дефект.

        До расширения тест требовал обратного: FIXED_AT == 2026-07-12 и !=
        _PENDING_FIXED_AT, потому что 28.07 был зафиксирован состав на 20, а не
        действующий. С вводом 30.07 действующим стал именно тот состав, поэтому
        даты обязаны СОВПАСТЬ. Оставить прежнее утверждение значило бы, что поле
        FIXED_AT врёт про свой собственный состав.
        """
        self.assertEqual(FORWARD_TICKERS_FIXED_AT, "2026-07-28")
        self.assertEqual(FORWARD_TICKERS_FIXED_AT, FORWARD_TICKERS_PENDING_FIXED_AT)

    def test_planned_and_actual_entry_dates_both_kept(self):
        """Плановая дата ввода 29.07 НЕ затирается фактической 30.07.

        29.07 ввод не состоялся: прогон 00:15 не запустился, машина была
        выключена. Расхождение планового и фактического само есть факт, и
        затирать его нельзя — иначе через полгода прочтётся, что всё шло по плану.
        """
        self.assertEqual(FORWARD_TICKERS_PENDING_ENTERS_AT, "2026-07-29")
        self.assertEqual(FORWARD_TICKERS_ENTERED_AT, "2026-07-30")
        self.assertNotEqual(FORWARD_TICKERS_PENDING_ENTERS_AT,
                            FORWARD_TICKERS_ENTERED_AT)

    def test_preregistration_record_survived_the_switch(self):
        """Факт фиксации ДО прогона — единственное, что отличает
        пре-регистрацию от подгонки, и он обязан быть виден после ввода."""
        self.assertEqual(len(FORWARD_TICKERS_PENDING), 20)
        self.assertEqual(FORWARD_TICKERS_PENDING_VERSION, EXPECTED_20)
        self.assertEqual(FORWARD_TICKERS_PENDING_FIXED_AT, "2026-07-28")
        self.assertEqual(FORWARD_TICKERS_PENDING, FORWARD_TICKERS,
                         "введён обязан быть ровно зафиксированный состав")

    def test_measurement_universe_12_untouched_by_the_switch(self):
        """Приколоченный набор расширением НЕ затронут — на нём посчитаны все
        опорные числа проекта."""
        self.assertEqual(len(MEASUREMENT_UNIVERSE_2026_07), 12)
        self.assertEqual(MEASUREMENT_UNIVERSE_2026_07_VERSION, EXPECTED_12)
        self.assertEqual(MEASUREMENT_UNIVERSE_2026_07_EXT_VERSION, EXPECTED_20)


class TestUniverseVersionIsNoLongerASoleDiscriminator(unittest.TestCase):
    """Оговорка к долгу №33, закодированная тестом (PROJECT_STATE раздел 3).

    Тест утверждает СОВПАДЕНИЕ отпечатков — не для того чтобы поймать дефект, а
    чтобы оговорку нельзя было забыть при чтении кода.
    """

    def test_forward_and_ext_fingerprints_now_coincide(self):
        """FORWARD == _EXT, поэтому universe_version в одиночку НЕ различает
        форвардную сделку от бэктестовой.

        Различает только пара (origin, universe_version). Запрос «сделки на
        наборе 20» без origin смешает два контура МОЛЧА — а `is_sandbox`
        различителем не является, форвард тоже бумажный (долг №30).
        """
        self.assertEqual(FORWARD_TICKERS_VERSION,
                         MEASUREMENT_UNIVERSE_2026_07_EXT_VERSION)
        self.assertEqual(FORWARD_TICKERS_VERSION, EXPECTED_20)

    def test_forward_eras_remain_separable(self):
        """Что оговорка НЕ отменяет: эры форварда различимы отпечатком.

        Ради этого долг №33 и заводился — confidence агрегируется по
        strategy_id и смешал бы эру 12 бумаг с эрой 20.
        """
        self.assertNotEqual(EXPECTED_12, EXPECTED_20)
        self.assertEqual(MEASUREMENT_UNIVERSE_2026_07_VERSION, EXPECTED_12,
                         "эра 12 бумаг обязана остаться адресуемой отпечатком")


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
        # Сравнивать с FORWARD_TICKERS_VERSION нельзя, но причина с 30.07 ДРУГАЯ.
        # Было (после отката 28.07): форвард на 12 бумагах, совпадали FORWARD и
        # MEASUREMENT_12. Стало (расширение 30.07): форвард на 20, и совпадают
        # FORWARD и _EXT. То есть сравнение бессмысленно в обе эпохи, но раньше
        # оно бы ложно ПРОШЛО как «наборы совпали», а теперь ложно прошло бы как
        # «набор бэктеста отличается от форвардного». Инвариант «наборы различимы»
        # проверяется отдельно — на 12 против 20.
        ext = BacktestEngine(universe_version=MEASUREMENT_UNIVERSE_2026_07_EXT_VERSION)
        self.assertNotEqual(eng._universe_version, ext._universe_version)

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


class TestSampleWindowIsPinned(unittest.TestCase):
    """Окно выборки приколочено и обязательно (долг №37).

    До 30.07 дата НАЧАЛА выборки не фиксировалась нигде: все семь измерительных
    скриптов брали из БД всё, что лежит. Опорная тройка воспроизводилась ровно
    потому, что у 12 действующих первый бар оказался 2023-07-12, — а не потому,
    что это записано. Докачай кто-нибудь историю глубже, и число изменилось бы
    МОЛЧА.

    ⚠ Утверждения про литерал отпечатка ЗАВИСЯТ ОТ ЗНАЧЕНИЯ окна (правило 2 §8):
    падают законно при сознательном сдвиге окна, и тогда обязаны быть обновлены
    вместе с перемером всех опорных чисел.
    """

    def test_window_start_is_a_pinned_literal(self):
        self.assertEqual(SAMPLE_START_2026_07, date(2023, 7, 12))
        self.assertEqual(SAMPLE_START_2026_07_VERSION, EXPECTED_WINDOW)

    def test_window_is_not_computed_from_data(self):
        """Авторасчёт из max(first_bar) запрещён: он молча меняется при догрузке.

        Проверяется по исходнику, потому что предмет — именно способ получения
        значения, а не само значение: вычисленное из БД окно дало бы сегодня ту же
        дату и тест по значению прошёл бы.

        Утверждение СТРУКТУРНОЕ, а не текстовое, и это важно: искать подстроки
        «max(first_bar» или «config» нельзя — они законно стоят в комментарии и
        докстринге, объясняющих запрет и четвёртый набор. Обе первые версии этого
        теста упали именно на них. Настоящая гарантия одна: universe.py физически
        НЕ УМЕЕТ ходить в данные, потому что не импортирует ничего, кроме stdlib.
        """
        src = (_ROOT / "bot" / "universe.py").read_text(encoding="utf-8")
        self.assertIn("SAMPLE_START_2026_07 = date(2023, 7, 12)", src,
                      "окно обязано быть литералом")
        self.assertEqual(_top_level_imports(src), {"hashlib", "datetime"},
                         "импорт-бюджет universe.py: только stdlib. Появление "
                         "asyncpg/psycopg2/config означает, что окно стало "
                         "вычисляемым — то есть молча меняющимся при догрузке")

    def test_fingerprint_namespaces_do_not_collide(self):
        """Отпечаток окна и отпечаток набора живут в РАЗНЫХ пространствах.

        Иначе набор из одного тикера с именем «2023-07-12» дал бы тот же
        отпечаток, что окно, — безвредно ровно до дня, когда кто-то сравнит их
        напрямую.
        """
        self.assertNotEqual(sample_version(SAMPLE_START_2026_07),
                            universe_version(("2023-07-12",)))

    def test_one_day_shift_changes_the_fingerprint(self):
        self.assertNotEqual(sample_version(date(2023, 7, 12)),
                            sample_version(date(2023, 7, 13)))


class TestMeasurementScriptsPassTheWindow(unittest.TestCase):
    """Fail-loud: окно — обязательный аргумент, а не дисциплина.

    Дефолт превратил бы механизм обратно в дисциплину: скрипт, забывший окно,
    молча получил бы более широкую выборку и напечатал бы правдоподобный, но
    невоспроизводимый результат.
    """

    SCRIPTS = ("run_osc_oos_debug.py", "run_ab_tf_backtest.py",
               "run_ab_swing_stop.py", "run_ab_trend_fix.py",
               "run_wrd_backtest.py")

    def test_each_script_passes_the_window_explicitly(self):
        for name in self.SCRIPTS:
            src = (_ROOT / "bot" / "backtest" / name).read_text(encoding="utf-8")
            self.assertIn("SAMPLE_START_2026_07", src,
                          f"{name}: окно выборки не передаётся")
            self.assertIn("from backtest.candles import", src,
                          f"{name}: обязан брать общий загрузчик, а не свою копию")

    def test_no_script_keeps_its_own_loader(self):
        """Пять копий одного запроса были той же болезнью, что девять копий
        списка тикеров."""
        for name in self.SCRIPTS:
            src = (_ROOT / "bot" / "backtest" / name).read_text(encoding="utf-8")
            self.assertNotIn("async def load_candles_db", src,
                             f"{name}: своя копия загрузчика вернулась")

    def test_shared_loader_requires_the_window(self):
        import asyncio
        from backtest.candles import load_candles_db
        with self.assertRaises(TypeError):
            asyncio.run(load_candles_db("1d", ["SBER"]))       # окна нет

    def test_shared_loader_rejects_a_non_date_window(self):
        import asyncio
        from backtest.candles import load_candles_db
        with self.assertRaises(TypeError):
            asyncio.run(load_candles_db("1d", ["SBER"], "2023-07-12"))   # строка

    def test_query_filters_on_the_window(self):
        src = (_ROOT / "bot" / "backtest" / "candles.py").read_text(encoding="utf-8")
        self.assertIn("time >= $3", src,
                      "без фильтра в запросе обязательный аргумент бесполезен")
        self.assertIn("d1_bar_time", src,
                      "граница обязана быть МОСКОВСКОЙ полуночью: с UTC-полуночью "
                      "первый бар окна отрезался бы (канон долга №16)")


if __name__ == "__main__":
    unittest.main()
