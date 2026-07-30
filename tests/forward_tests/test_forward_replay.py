"""Режим реплея форварда (шов контроля пути сигналов, 2026-07-30).

Зачем шов. За 27–30.07 форвард сделал ноль сделок — статистически ожидаемо, но
путь «правила → индикаторы → кворум дивергенций → фильтр даунтренда → решение»
подтверждён только отсутствием падений, то есть не подтверждён. Реплей позволяет
прогнать боевой код на баре, где бэктест давал BUY (положительный контроль), и на
баре, который фильтр обязан отклонить (отрицательный).

Почему в шве НЕТ даты. Момент задаётся СОСТАВОМ ДАННЫХ клона, а не фильтром в
путях чтения: фильтр в `_prepare_ticker` не накрыл бы
`TradingOrchestrator._check_structural_downtrend`, который читает свечи своим
запросом и берёт `.iloc[-1]` полной серии. Фильтр считался бы по сегодняшнему
бару, а не по целевому.

Проверяется то, что молча ломается:
  - реплей в БОЕВУЮ БД роняет прогон ДО любого действия. Это единственная
    защита от переменной окружения, пережившей сессию: иначе контрольная
    сделка однажды уедет в боевые trades;
  - в реплее свечи с ISS НЕ тянутся (иначе догрузка вернёт обрезанные бары и
    отменит момент);
  - в реплее проверка протухания не применяется (иначе ВСЕ цели контроля
    недоступны: ближайшая старше порога);
  - вне реплея поведение прежнее — и догрузка, и порог протухания на месте.
"""

import os
import sys
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import run_forward_d1 as fwd  # noqa: E402
# Стенд переиспользуется, а не дублируется: FakeDB/_bars/_make_runner уже
# отрезают ISS, БД и Telegram, и второй экземпляр однажды отстал бы от первого.
from tests.forward_tests.test_forward_catchup import (  # noqa: E402
    FakeDB, _bars, _make_runner, _smooth,
)

UTC = timezone.utc


@contextmanager
def env(**kwargs):
    """Переменные окружения на время блока, с честным восстановлением."""
    saved = {k: os.environ.get(k) for k in kwargs}
    try:
        for k, v in kwargs.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextmanager
def db_name(name: str):
    """Подменить имя БД, которое видит шов.

    Патчится `config.db.name`, а не переменная окружения: `config` — датакласс,
    читающий env в момент СОЗДАНИЯ объекта, то есть на импорте модуля
    (`bot/config.py:12-18`). Правка `os.environ` после импорта на него не
    действует — ровно та ловушка, из-за которой DB_NAME обязан стоять в
    окружении процесса на запуске.
    """
    with patch.object(fwd.config.db, "name", name):
        yield


class TestReplayGuard(unittest.TestCase):
    """Инвариант: реплей не может тронуть боевую БД."""

    def test_replay_against_production_db_raises(self):
        with env(FWD_REPLAY="1"), db_name(fwd.PRODUCTION_DB):
            with self.assertRaises(fwd.ReplayMisconfigured) as ctx:
                fwd._replay_mode()
        # В тексте обязаны быть оба факта: что просили и куда это указывало.
        self.assertIn("FWD_REPLAY", str(ctx.exception))
        self.assertIn(fwd.PRODUCTION_DB, str(ctx.exception))

    def test_replay_against_clone_is_allowed_and_loud(self):
        with env(FWD_REPLAY="1"), db_name("forward_control"):
            replay, note = fwd._replay_mode()
        self.assertTrue(replay)
        self.assertIsNotNone(note, "режим реплея обязан быть виден в сводке и Telegram")
        # Не «строка непустая», а именно тревожная пометка: ⚠ — конвенция проекта
        # для флага, который обязан быть замечен (ср. catchup_note,
        # per_ticker_note). Проверено внесением дефекта: без этой строки тест
        # проходил и при переписанной на тихую формулировку пометке.
        self.assertIn("⚠", note)
        self.assertIn("РЕПЛЕ", note.upper())
        self.assertIn("forward_control", note,
                      "пометка обязана называть БД: иначе не видно, куда ушёл прогон")

    def test_production_db_without_flag_is_untouched(self):
        with env(FWD_REPLAY=None), db_name(fwd.PRODUCTION_DB):
            replay, note = fwd._replay_mode()
        self.assertFalse(replay)
        self.assertIsNone(note)

    def test_explicit_off_values_do_not_enable_replay(self):
        """Опечатка не должна МОЛЧА включать реплей и не должна его выключать.

        Явные false/0/no/off — выключено. Всё остальное — включено, потому что
        непонятое значение здесь безопаснее трактовать как «человек чего-то
        хотел»: при боевой БД оно упадёт, а не ослабит проверки.
        """
        for value in ("0", "false", "no", "off", "FALSE", " off "):
            with env(FWD_REPLAY=value), db_name(fwd.PRODUCTION_DB):
                replay, _ = fwd._replay_mode()
            self.assertFalse(replay, f"{value!r} обязано выключать реплей")


class TestReplayDisablesCandleRefresh(unittest.TestCase):
    """В реплее догрузка с ISS не вызывается.

    Прогоняется НАСТОЯЩИЙ `run()` с отрезанным внешним миром. Первая версия
    этого теста воспроизводила ветку шага 1 у себя — и потому проходила при
    полностью снятом шве: утверждала о копии логики, а не о коде. Проверено
    внесением дефекта.
    """

    def _run_capturing(self, replay: bool, note="⚠ РЕЖИМ РЕПЛЕЯ (тест)"):
        """(mock загрузчика, runner) после настоящего run()."""
        import asyncio
        db = FakeDB(_bars(_smooth(fwd.MIN_HISTORY_BARS + 20)))
        runner, _, _ = _make_runner(db)
        runner.replay = replay
        runner.replay_note = note
        tg = MagicMock()
        tg.send_notification = AsyncMock()
        with patch.object(fwd, "save_candles_to_db", return_value=0) as loader, \
             patch.object(fwd, "TICKERS", ["SBER"]), \
             patch.object(fwd.asyncpg, "connect", AsyncMock(return_value=db)), \
             patch.dict(sys.modules, {"ui": MagicMock(), "ui.telegram_bot": tg}):
            asyncio.run(runner.run())
        return loader, runner, tg

    def test_refresh_skipped_in_replay(self):
        loader, runner, tg = self._run_capturing(replay=True)
        loader.assert_not_called()
        self.assertTrue(any("РЕПЛЕЯ" in e for e in runner.events),
                        "факт реплея обязан попасть в сводку")
        # Громкость = дошло до человека, а не просто «строка не пустая».
        tg.send_notification.assert_awaited()
        self.assertIn("РЕПЛЕЯ", tg.send_notification.await_args.args[0])

    def test_refresh_called_outside_replay(self):
        loader, _, _ = self._run_capturing(replay=False)
        loader.assert_called_once()


class TestStaleGuardScope(unittest.TestCase):
    """Порог протухания: снят в реплее, на месте вне его.

    Проверяется НАСТОЯЩИМ вызовом `_prepare_ticker` на стенде из
    test_forward_catchup, а не арифметикой над константами: сравнение
    `age > STALE_DAYS and not replay` в тесте — тавтология, которая прошла бы и
    при полностью снятом шве.

    Возраст задаётся ОТ КОНСТАНТЫ STALE_DAYS, а не конкретной датой: иначе тест
    сломался бы от смены целей контроля — хрупкость, помеченная правилом 2 §8
    PROJECT_STATE.
    """

    def _stale_db(self):
        """Клон с историей, кончающейся заведомо позже порога протухания."""
        closes = _smooth(fwd.MIN_HISTORY_BARS + 20)
        start = (datetime.now(fwd.MSK).date()
                 - timedelta(days=len(closes) + fwd.STALE_DAYS + 1))
        # FakeDB принимает СПИСОК строк-свечей, а не словарь по тикеру:
        # его fetch отдаёт self.candles на любой запрос "FROM candles".
        return FakeDB(_bars(closes, ticker_start=start))

    def _prepare(self, replay: bool):
        import asyncio
        db = self._stale_db()
        runner, _, _ = _make_runner(db)
        runner._db = db
        runner.replay = replay
        return asyncio.run(runner._prepare_ticker("SBER")), runner

    def test_stale_ticker_is_dropped_outside_replay(self):
        plan, runner = self._prepare(replay=False)
        self.assertIsNone(plan, "вне реплея протухшая свеча обязана снимать тикер")
        self.assertTrue(any("протух" in e or "дн. назад" in e for e in runner.events),
                        "снятие тикера обязано быть объяснено в сводке, а не молчать")

    def test_same_ticker_is_processed_in_replay(self):
        plan, _ = self._prepare(replay=True)
        self.assertIsNotNone(
            plan, "в реплее протухание неприменимо — иначе цели контроля "
                  "недоступны все до одной (ближайшая старше порога на день)")
        self.assertEqual(plan.ticker, "SBER")

    def test_replay_does_not_lift_the_history_minimum(self):
        """Реплей снимает ТОЛЬКО протухание.

        MIN_HISTORY_BARS остаётся: короткая история делает SMA200 и индикаторы
        невычислимыми, и это не вопрос свежести данных. Проверяется вызовом:
        короткая история обязана снимать тикер и В реплее тоже.
        """
        import asyncio
        db = FakeDB(_bars(_smooth(fwd.MIN_HISTORY_BARS - 1)))
        runner, _, _ = _make_runner(db)
        runner._db = db
        runner.replay = True
        plan = asyncio.run(runner._prepare_ticker("SBER"))
        self.assertIsNone(plan, "короткой истории реплей оправданием не является")


if __name__ == "__main__":
    unittest.main()
