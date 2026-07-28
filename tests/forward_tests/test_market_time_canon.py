"""Канон метки бара и починенная запись загрузчика (долг №16).

Предмет. В candles для D1 сосуществовали две конвенции: московская полночь
(канон, 21:00+00 предыдущего дня) и наивная МСК-полночь, записанная как
00:00+00. Вторую давал bot/data/loader.py, отдавая наивный datetime в
TIMESTAMPTZ. На стыке конвенций по каждому тикеру появилась пара строк на одну
сессию 25.06 — фантомный бар, сдвигающий каждое rolling-окно после неё.

Здесь проверяется:
  - session_date() читает МСК-дату верно на ОБЕИХ конвенциях (иначе ремонт
    нельзя было бы готовить до правки данных);
  - d1_bar_time() ставит метку ровно на московскую полночь;
  - загрузчик пишет tz-aware момент, а окно DELETE считается по московским
    полуночам — именно граница окна и создавала дубль.

SQL-сторона канона (уникальный индекс candles_d1_one_per_msk_session
использует то же выражение) проверяется прямым запросом при ремонте: выражение
живёт в БД, а не в Python, и юнит-тест его вычислить не может. Результат сверки
записан в docs/PROJECT_STATE.md.
"""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import pandas as pd

from market_time import MSK, D1_BAR_OPEN_MSK, d1_bar_time, is_canonical_d1, session_date

UTC = timezone.utc

# Реальная пара из БД: обе строки описывают сессию 2026-06-25.
CANON_ROW = datetime(2026, 6, 24, 21, 0, tzinfo=UTC)   # московская полночь
NAIVE_ROW = datetime(2026, 6, 25, 0, 0, tzinfo=UTC)    # МСК-полночь как UTC
SESSION = date(2026, 6, 25)


class TestSessionDate(unittest.TestCase):

    def test_both_conventions_give_the_same_session(self):
        """Ключевое свойство: чтение через МСК верно ДО ремонта данных."""
        self.assertEqual(session_date(CANON_ROW), SESSION)
        self.assertEqual(session_date(NAIVE_ROW), SESSION)

    def test_utc_date_is_the_defect_being_avoided(self):
        """Фиксируем цену наивного `.date()`: у канона он даёт сессию −1 день."""
        self.assertEqual(CANON_ROW.date(), date(2026, 6, 24))
        self.assertNotEqual(CANON_ROW.date(), session_date(CANON_ROW))

    def test_midnight_boundary(self):
        one_sec_before = CANON_ROW - timedelta(seconds=1)
        self.assertEqual(session_date(one_sec_before), date(2026, 6, 24))
        self.assertEqual(session_date(CANON_ROW), date(2026, 6, 25))

    def test_works_on_intraday_marks(self):
        """1h/4h в каноне: 04:00 МСК = 01:00 UTC той же даты."""
        self.assertEqual(session_date(datetime(2026, 6, 25, 1, 0, tzinfo=UTC)),
                         date(2026, 6, 25))
        # Вечерняя сессия: 23:00 МСК = 20:00 UTC, всё ещё та же сессия.
        self.assertEqual(session_date(datetime(2026, 6, 25, 20, 0, tzinfo=UTC)),
                         date(2026, 6, 25))


class TestD1BarTime(unittest.TestCase):

    def test_canonical_mark_is_msk_midnight(self):
        self.assertEqual(d1_bar_time(SESSION), CANON_ROW)

    def test_round_trip(self):
        for d in (date(2023, 7, 3), date(2025, 1, 1), date(2026, 7, 28)):
            self.assertEqual(session_date(d1_bar_time(d)), d)

    def test_is_canonical_discriminates_the_real_pair(self):
        self.assertTrue(is_canonical_d1(CANON_ROW))
        self.assertFalse(is_canonical_d1(NAIVE_ROW))

    def test_canon_constant_is_midnight(self):
        self.assertEqual((D1_BAR_OPEN_MSK.hour, D1_BAR_OPEN_MSK.minute), (0, 0))


class TestLoaderWritesCanon(unittest.TestCase):
    """Загрузчик: tz-aware записи и окно DELETE по московским полуночам.

    БД не поднимается: подменяются ISS-ответ и psycopg2. Предмет — ровно те два
    выражения, которые правились, поэтому мок здесь не обедняет проверку.
    """

    def setUp(self):
        from data import loader as ldr
        self.ldr = ldr

        # ISS отдаёт МОСКОВСКИЕ стенные часы наивным индексом — как в реальности.
        idx = pd.DatetimeIndex([datetime(2026, 6, 25), datetime(2026, 6, 26)],
                               name="datetime")
        self.df = pd.DataFrame(
            {"open": [1.0, 2.0], "high": [1.0, 2.0], "low": [1.0, 2.0],
             "close": [1.0, 2.0], "volume": [10, 20]}, index=idx)

        self.cur = MagicMock()
        self.cur.rowcount = 0
        self.cur.__enter__ = MagicMock(return_value=self.cur)
        self.cur.__exit__ = MagicMock(return_value=False)
        self.conn = MagicMock()
        self.conn.cursor = MagicMock(return_value=self.cur)

        self.captured: dict = {}

        def _fake_execute_values(cur, sql, records, page_size=None):
            self.captured["records"] = records

        with patch.object(ldr.loader, "get_candles", return_value=self.df), \
             patch("psycopg2.connect", return_value=self.conn), \
             patch("psycopg2.extras.execute_values", _fake_execute_values):
            ldr.save_candles_to_db(["SBER"], interval="1d", days=5, verbose=False)

    def test_records_are_tz_aware(self):
        times = [r[0] for r in self.captured["records"]]
        for ts in times:
            self.assertIsNotNone(ts.tzinfo, f"{ts} записывается наивным — вернётся дубль")

    def test_records_land_on_msk_midnight(self):
        """Сессия 25.06 обязана лечь на 24.06 21:00 UTC, а не на 25.06 00:00."""
        times = [r[0].astimezone(UTC) for r in self.captured["records"]]
        self.assertEqual(times[0], datetime(2026, 6, 24, 21, 0, tzinfo=UTC))
        self.assertEqual(times[1], datetime(2026, 6, 25, 21, 0, tzinfo=UTC))
        for ts in times:
            self.assertTrue(is_canonical_d1(ts))

    def test_delete_window_bounds_are_msk_midnights(self):
        """Граница окна — причина дубля: с UTC-полуночью каноничный бар первого
        дня окна оказывался раньше начала и DELETE его не забирал."""
        sql, params = self.cur.execute.call_args[0]
        self.assertIn("time >= %s AND time < %s", sql)
        self.assertNotIn("BETWEEN", sql)
        win_start, win_end = params[2], params[3]
        self.assertIsNotNone(win_start.tzinfo)
        self.assertIsNotNone(win_end.tzinfo)
        self.assertTrue(is_canonical_d1(win_start))
        self.assertTrue(is_canonical_d1(win_end))

    def test_window_covers_the_canonical_bar_of_its_first_day(self):
        """Регрессия на сам дефект: бар первой сессии окна обязан попадать в окно."""
        _, params = self.cur.execute.call_args[0]
        win_start, win_end = params[2], params[3]
        first_session = session_date(win_start)
        canon_bar = d1_bar_time(first_session)
        self.assertGreaterEqual(canon_bar, win_start)
        self.assertLess(canon_bar, win_end)


if __name__ == "__main__":
    unittest.main()
