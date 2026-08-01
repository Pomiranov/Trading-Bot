"""Сторож обязан кричать, когда прогон НЕ СОСТОЯЛСЯ. И не кричать, когда он идёт.

Предмет. 01.08 прогон уехал с слота 00:15 на 11:38 — машину выключили
(«Завершение работы» при включённом Быстром запуске; долг №45), и
сторож сказал `✅ Форвард жив`. Факт пропуска он при этом ЗНАЛ и напечатал —
строкой `Ночной прогон: последняя запись 31.07 00:15 (mtime … — расходится)`,
которая приходит из `_forward_log_line()` и попадает в `tail`, то есть на уровень
тревоги не влияет. Проверок A1–A4 на «запуск не случился» у сторожа нет вовсе, а
единственный косвенный канал — возраст бара — промолчал, потому что порог
проглочен (`2 > 2` = False при пороге 2). Долг №46.

Что здесь проверяется — предикатом, а не перечислением файлов:

    любое состояние, при котором форвардный прогон не дал ПАРНОЙ записи
    (старт + финиш) за ожидаемый слот, обязано приводить к 🚨 в Telegram.

Почему запись парная, а не одна. Три состояния различимы только парой:
нет старта → не запускался; старт без финиша → запустился и умер; старт и
финиш → норма. Одиночная запись «прогон был» их склеивает.

Почему нужен льготный интервал. Замерено 01.08: при догоне после включения
планировщик
стартует форвард и сторожа ОДНОЙ секундой — форвард 11:38:44, сторож 11:38:45,
финиш прогона 11:38:56. Без льготы сторож увидел бы собственный живой прогон
мёртвым, и не разово, а на КАЖДОЙ догнанной ночи.

Почему торгового календаря здесь нет. A5 не спрашивает «была ли сессия»: задача
стоит на каждый день, значит запись обязана быть и в биржевой праздник. Календарь
нужен другой проверке — «прогон был, но сессию не обработал», — и она вынесена из
этого блока, потому что календаря в проекте нет.

Боевой журнал НЕ ТРОГАЕТСЯ: путь берётся из FWD_RUN_JOURNAL, каждый случай
работает на своём временном файле. Append-only журнал, отредактированный руками,
перестаёт быть свидетельством.
"""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import forward_healthcheck as hc  # noqa: E402
import run_schedule as sched  # noqa: E402
from market_time import MSK  # noqa: E402

BAT = _ROOT / "run_forward_d1.bat"

# ── Договор о текстах вердикта ───────────────────────────────────────────────
#
# Фразы объявлены здесь, а не подглядываются в реализации: тест задаёт контракт,
# а не описывает то, что получилось. Требование поправки 2 — «слот пропущен» и
# «прогона нет» должны различаться В САМОМ СООБЩЕНИИ, иначе человек каждый раз
# полезет в логи, чтобы понять, какое из двух действий нужно.
V_NO_START = "прогона до сих пор нет"        # старта нет вовсе
V_CAUGHT_UP = "ДОГОН СОСТОЯЛСЯ"              # слот пуст, прогон догнан и завершён
V_CATCHUP_RUNNING = "ДОГОН ИДЁТ"             # слот пуст, догон в полёте
V_DEAD = "прогон умер"                       # старт есть, финиша нет, льгота вышла
V_BAD_RC = "завершился с ошибкой"            # пара полная, rc != 0
V_JOURNAL_LOST = "журнал прогонов потерян"   # файла нет
V_EVIDENCE_LOST = "свидетельство утрачено"   # journal_created новее слота

# Все фразы A5 вместе — для случаев, где проверяется ОТСУТСТВИЕ тревоги A5.
# Проверять «нет 🚨 вообще» нельзя: A2 «свечи не поступают» в биржевой праздник
# срабатывает законно и к A5 отношения не имеет.
V_ALL = (V_NO_START, V_CAUGHT_UP, V_CATCHUP_RUNNING, V_DEAD, V_BAD_RC,
         V_JOURNAL_LOST, V_EVIDENCE_LOST)

_AGE_NEAR_THRESHOLD = re.compile(r"\((\d+)\s*дн\. назад,\s*порог\s*(\d+)\)")


class JournalCase(unittest.TestCase):
    """Общая обвязка: временный журнал и снимок, в котором ничего не болит."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(prefix="fwd_journal_")
        self.journal = Path(self._dir.name) / "forward_runs.jsonl"
        self._prev_env = os.environ.get(sched.JOURNAL_ENV)
        os.environ[sched.JOURNAL_ENV] = str(self.journal)
        self.now = datetime.now(MSK)
        self.slot = sched.last_slot(self.now)

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop(sched.JOURNAL_ENV, None)
        else:
            os.environ[sched.JOURNAL_ENV] = self._prev_env
        self._dir.cleanup()

    # ── журнал ───────────────────────────────────────────────────────────
    def write_journal(self, *records: dict) -> None:
        with self.journal.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def created(self, at: datetime) -> dict:
        return {"event": "journal_created", "at": at.isoformat()}

    def start(self, at: datetime, slot: datetime | None = None) -> dict:
        return {"event": "start", "at": at.isoformat(),
                "slot": (slot or self.slot).isoformat(), "pid": 4242}

    def finish(self, at: datetime, rc: int, session: date) -> dict:
        return {"event": "finish", "at": at.isoformat(), "rc": rc,
                "session": session.isoformat()}

    # ── снимок ───────────────────────────────────────────────────────────
    def snapshot(self, state_session: date, candles_session: date) -> hc.Snapshot:
        """Снимок, где болит ровно то, что задано датами, и ничего больше.

        Все тикеры набора присутствуют — иначе сработает A4 «форвард потерял
        тикеры», и тест позеленел бы по другой причине, чем проверяет.
        """
        state_bar = datetime.combine(state_session, hc.dtime(0, 0), tzinfo=MSK)
        candles_bar = datetime.combine(candles_session, hc.dtime(0, 0), tzinfo=MSK)
        rows = [(t, state_bar) for t in hc.TICKERS]
        candle_dates = {t: [candles_session] for t in hc.TICKERS}
        return hc.Snapshot(rows=rows, candles_max=candles_bar,
                           candle_dates=candle_dates, catchups={})

    def healthy(self) -> hc.Snapshot:
        """Прогон отработал: обработана сессия слота, свечи до неё же."""
        session = sched.slot_session(self.slot)
        return self.snapshot(session, session)

    def message(self, snap: hc.Snapshot) -> str:
        return hc.build_message(snap, None, None)

    def assertNoA5(self, text: str, why: str) -> None:
        for phrase in V_ALL:
            self.assertNotIn(phrase, text, f"{why}\n--- сообщение ---\n{text}")


class TestRunDidNotHappen(JournalCase):
    """Случаи 1, 2 — обязаны ПАДАТЬ на текущем коде."""

    def test_1_no_start_record_for_the_slot(self):
        """Записи о старте за слот нет — сторож обязан кричать.

        Ровно ночь на 01.08: слот 00:15 прошёл, прогона не было, машина выключена.
        Возраст бара при этом может быть в норме (сторож догнан после того, как
        прогон всё же отработал позже), поэтому косвенный канал «возраст» не
        спасает — нужна запись о самом прогоне.
        """
        self.write_journal(self.created(self.slot - timedelta(days=30)))
        text = self.message(self.healthy())
        self.assertIn("🚨", text,
                      "сторож молчит, хотя записи о старте за слот "
                      f"{self.slot:%d.%m %H:%M} в журнале нет\n"
                      f"--- сообщение ---\n{text}")
        self.assertIn(V_NO_START, text,
                      "тревога есть, но не различает «прогона нет» от «слот "
                      f"пропущен, догон состоялся»\n--- сообщение ---\n{text}")

    def test_2_start_without_finish_past_grace(self):
        """Старт есть, финиша нет, льгота истекла — прогон умер.

        Отличается от случая 4 ровно временем: там прогон ещё в льготе.
        """
        started = self.now - timedelta(seconds=sched.GRACE_SEC + 60)
        self.write_journal(self.created(self.slot - timedelta(days=30)),
                          self.start(started))
        text = self.message(self.healthy())
        self.assertIn("🚨", text,
                      f"старт {started:%d.%m %H:%M:%S} без финиша, прошло "
                      f"{sched.GRACE_SEC + 60} с из {sched.GRACE_SEC} — "
                      f"сторож молчит\n--- сообщение ---\n{text}")


class TestNoFalseAlarm(JournalCase):
    """Случаи 3, 4 — падать НЕ должны ни до правки, ни после."""

    def test_3_complete_pair_on_exchange_holiday_is_silent(self):
        """Пара полная, новой сессии нет (биржевой выходной) — A5 молчит.

        Страж от ложного срабатывания: A5 не смеет опираться на «появился ли
        новый бар». Проверяется отсутствие фраз A5, а НЕ отсутствие 🚨 вообще —
        A2 «свечи не поступают» в праздник срабатывает законно и к A5 отношения
        не имеет.
        """
        session = sched.slot_session(self.slot)
        self.write_journal(
            self.created(self.slot - timedelta(days=30)),
            self.start(self.slot + timedelta(seconds=4)),
            self.finish(self.slot + timedelta(seconds=16), 0, session),
        )
        # Сессия не продвинулась: свечи и состояние на два дня назад.
        stale = hc.datetime.now(MSK).date() - timedelta(days=hc.MAX_AGE_DAYS)
        text = self.message(self.snapshot(stale, stale))
        self.assertNoA5(text, "пара записей полная, rc=0 — A5 не имеет права "
                              "тревожить из-за отсутствия новой сессии")

    def test_4_start_within_grace_is_silent(self):
        """Старт есть, финиша нет, льгота НЕ истекла — прогон идёт, тишина.

        Воспроизводит замеренный случай 01.08: сторож отработал 11:38:45, старт
        прогона был 11:38:44, финиш только 11:38:56. Без этого случая правка
        дала бы ложную тревогу на каждой догнанной ночи.
        """
        self.write_journal(self.created(self.slot - timedelta(days=30)),
                           self.start(self.now - timedelta(seconds=1),
                                      slot=self.slot))
        text = self.message(self.healthy())
        self.assertNotIn(V_DEAD, text,
                         "прогон стартовал секунду назад и объявлен мёртвым — "
                         f"это ложная тревога на каждом догоне\n"
                         f"--- сообщение ---\n{text}")


class TestSwallowedThreshold(unittest.TestCase):
    """Случаи 7, 8 — проглоченный порог. Обязаны ПАДАТЬ на текущем коде.

    Долг №46, пункт 2. Два дефекта в одной строке сообщения.
    """

    def snapshot(self, state_session: date, candles_session: date) -> hc.Snapshot:
        state_bar = datetime.combine(state_session, hc.dtime(0, 0), tzinfo=MSK)
        candles_bar = datetime.combine(candles_session, hc.dtime(0, 0), tzinfo=MSK)
        return hc.Snapshot(rows=[(t, state_bar) for t in hc.TICKERS],
                           candles_max=candles_bar,
                           candle_dates={t: [candles_session] for t in hc.TICKERS},
                           catchups={})

    def test_7_age_equal_to_threshold_must_alarm(self):
        """Возраст РОВНО порог обязан давать тревогу.

        `:457` сравнивает строго: при MAX_AGE_DEFAULT=2 и возрасте 2 выходит
        `2 > 2` = False. Порог, названный «2», стреляет с 3 — класс
        «проглоченный порог» §8. Замерено 01.08: сообщение сказало «✅ Форвард
        жив» при «2 дн. назад, порог 2».
        """
        today = datetime.now(MSK).date()
        at_threshold = today - timedelta(days=hc.MAX_AGE_DAYS)
        text = hc.build_message(self.snapshot(at_threshold, at_threshold), None, None)
        self.assertNotIn("✅", text,
                         f"возраст {hc.MAX_AGE_DAYS} при пороге {hc.MAX_AGE_DAYS} — "
                         f"сторож говорит «жив»\n--- сообщение ---\n{text}")

    def test_8_threshold_is_printed_next_to_the_compared_number(self):
        """Подпись «порог» обязана стоять у ТОГО числа, которое сравнивается.

        `:515` печатает возраст по forward_state, а `:456-457` сравнивает возраст
        по candles. Это разные величины; 01.08 обе равнялись 2, поэтому
        сообщение выглядело связным. Здесь они РАЗНЫЕ — и видно, что подпись
        стоит у посторонней.

        Состояние реалистично, а не выдумано: прогон грузит свечи и не
        обрабатывает тикеры — это режим отказа A1, ради которого A1 и написана.
        """
        today = datetime.now(MSK).date()
        state_session = today - timedelta(days=5)     # обработано давно
        candles_session = today - timedelta(days=1)   # свечи свежие
        text = hc.build_message(
            self.snapshot(state_session, candles_session), None, None)
        compared = (today - candles_session).days
        found = _AGE_NEAR_THRESHOLD.findall(text)
        self.assertTrue(found, "строки «(N дн. назад, порог M)» в сообщении нет "
                               f"вовсе\n--- сообщение ---\n{text}")
        for age_printed, _threshold in found:
            self.assertEqual(
                int(age_printed), compared,
                f"рядом с «порог» напечатано {age_printed}, а сравнивается "
                f"{compared} (возраст свечей). Подпись стоит у другого числа\n"
                f"--- сообщение ---\n{text}")


class TestScheduleIsOneSource(unittest.TestCase):
    """Расписание и льгота — одно место. Проверки 9, 10; XML — 11, отдельно."""

    def test_10_grace_recomputed_from_bat_budgets(self):
        """Бюджеты ожидания живут в .bat и НЕ перепечатаны в run_schedule.

        Иначе при правке .bat льгота разъедется с реальным поведением молча —
        класс «ставка комиссии в восьми местах» (§2а).
        """
        budgets = sched.bat_budgets(BAT.read_text(encoding="ascii", errors="replace"))
        self.assertIn("DAEMON_WAIT_S", budgets,
                      "в .bat не найден set DAEMON_WAIT_S — сверять нечем")
        self.assertIn("DBWAIT_TIMEOUT", budgets,
                      "в .bat не найден set DBWAIT_TIMEOUT — сверять нечем")
        self.assertEqual(sched.DAEMON_WAIT_S, budgets["DAEMON_WAIT_S"])
        self.assertEqual(sched.DBWAIT_TIMEOUT, budgets["DBWAIT_TIMEOUT"])
        self.assertEqual(
            sched.GRACE_SEC,
            budgets["DAEMON_WAIT_S"] + budgets["DBWAIT_TIMEOUT"]
            + sched.RUN_MAX_SEC * sched.RUN_SAFETY,
            "GRACE_SEC не пересчитывается из своих слагаемых")

    def test_slot_of_forward_is_before_midnight_check(self):
        """Слот 00:15 обрабатывает ПРЕДЫДУЩУЮ московскую сессию.

        Три даты раздельно: слот 02.08 00:15 → сессия 2026-08-01. Смешение
        стоило бы того же, что почти стоило сессии 30.07.
        """
        slot = datetime(2026, 8, 2, 0, 15, tzinfo=MSK)
        self.assertEqual(sched.slot_session(slot), date(2026, 8, 1))

    def test_last_slot_before_todays_slot_points_at_yesterday(self):
        """Сторож, запущенный в 00:05, спрашивает про ВЧЕРАШНИЙ слот.

        Иначе он потребует записи о прогоне, который ещё не должен был случиться.
        """
        at = datetime(2026, 8, 2, 0, 5, tzinfo=MSK)
        self.assertEqual(sched.last_slot(at),
                         datetime(2026, 8, 1, 0, 15, tzinfo=MSK))


class TestTestsDoNotWriteProductionJournal(unittest.TestCase):
    """Тесты и бэктесты НЕ ИМЕЮТ ПРАВА писать в журнал прогонов.

    Найдено живой проверкой 01.08, уже после того как правка была написана:
    replay-тесты поднимают ForwardRunner в процессе, дошли до записи `session` и
    налили 97 строк в БОЕВОЙ logs/forward_runs.jsonl — все `session`, ни одного
    `start`. Это не просто мусор: сторож привязывает `session` к последнему
    предшествующему `start`, значит чужая строка могла прицепиться к настоящему
    прогону и объявить обработанной сессию, которой тот не видел.

    Лечится ПРЕДИКАТОМ, а не памятью «выставить переменную в тестах»: писать
    `session` вправе только процесс, о старте которого .bat сделал запись.
    """

    def test_session_is_written_only_by_a_scheduled_run(self):
        prev = os.environ.pop(sched.IN_SLOT_RUN_ENV, None)
        try:
            self.assertFalse(
                sched.in_slot_run(),
                "признак прогона по расписанию выставлен вне .bat — тогда любой "
                "тест сможет писать в журнал прогонов")
        finally:
            if prev is not None:
                os.environ[sched.IN_SLOT_RUN_ENV] = prev

    def test_runner_guards_the_session_write_by_that_predicate(self):
        """Запись `session` в прогоне обязана стоять ПОД условием предиката.

        Проверяется исходником, а не поведением: поднять ForwardRunner в тесте
        значило бы воспроизвести ровно ту контаминацию, от которой защищаемся.
        """
        src = (_ROOT / "bot" / "run_forward_d1.py").read_text(encoding="utf-8")
        call = src.find('run_journal.write("session"')
        guard = src.find("run_schedule.in_slot_run()")
        self.assertGreater(call, -1, "запись сессии в журнал потерялась")
        self.assertGreater(guard, -1,
                           "запись сессии не защищена предикатом — тесты и "
                           "бэктесты будут писать в боевой журнал")
        self.assertLess(guard, call,
                        "предикат стоит ПОСЛЕ записи — защита не работает")

    def test_only_the_bat_sets_the_marker(self):
        """Признак ставит ровно один файл. Две точки установки = нет предиката."""
        setters = []
        for path in sorted((_ROOT / "bot").glob("*.py")) + [BAT]:
            text = path.read_text(encoding="utf-8", errors="replace")
            if f"{sched.IN_SLOT_RUN_ENV}=1" in text.replace(" ", ""):
                setters.append(path.name)
        self.assertEqual(setters, [BAT.name],
                         f"признак прогона по расписанию ставится в {setters}, "
                         f"а должен только в {BAT.name}")


class TestBatJournalContract(unittest.TestCase):
    """Договор .bat ↔ журнал. Ломается молча, поэтому тест.

    Разбираются только ИСПОЛНЯЕМЫЕ строки: в комментариях .bat намеренно
    упомянуты и прежние ошибки, и имена скриптов — это объяснение правки, и
    терять его ради простоты проверки значило бы обменять причину на удобство
    (тот же приём, что в TestBatContract, test_forward_start_gate.py:80-91).
    """

    @classmethod
    def setUpClass(cls):
        cls.raw = BAT.read_bytes()
        cls.code = "\n".join(
            line for line in cls.raw.decode("ascii", errors="replace").splitlines()
            if not line.strip().lower().startswith("rem"))

    def test_start_is_written_before_any_gate(self):
        """`start` — раньше ожидания docker-демона и раньше ожидания БД.

        Иначе запись о прогоне не появится в единственном случае, для которого
        она написана: когда прогон не дошёл до гейтов.
        """
        start = self.code.find("run_journal.py start")
        self.assertGreater(start, -1, "в .bat нет записи start в журнал прогонов")
        for later in ("docker info", "db_wait.py", "run_forward_d1.py"):
            pos = self.code.find(later)
            self.assertGreater(pos, -1, f"в .bat не найден {later}")
            self.assertLess(start, pos,
                            f"start пишется ПОСЛЕ {later} — прогон, упавший "
                            f"раньше, не оставит о себе записи")

    def test_exit_code_is_captured_before_journal_call(self):
        """`set RC=%ERRORLEVEL%` — ДО вызова журнала, иначе код прогона потерян.

        Вызов python перезаписывает %ERRORLEVEL%, и в журнал уехал бы код самой
        бухгалтерии вместо кода прогона.
        """
        run = self.code.find("run_forward_d1.py")
        capture = self.code.find("set RC=%ERRORLEVEL%")
        journal = self.code.find("run_journal.py finish %RC%")
        self.assertGreater(capture, run,
                           "%ERRORLEVEL% не сохраняется после прогона")
        self.assertLess(capture, journal,
                        "код сохраняется ПОСЛЕ вызова журнала — уже поздно")
        self.assertIn("exit /b %RC%", self.code,
                      ".bat возвращает не код прогона, а код журнала — "
                      "LastTaskResult покажет не то")

    def test_numeric_argument_is_separated_from_redirect(self):
        """Одиночная цифра, склеенная с >>, съедается как файловый handle.

        Замерено 30.07: `x 1>>` ТЕРЯЕТ аргумент. Для журнала это значит запись
        finish без кода — то есть «прогон закончился» неотличимо от
        «закончился успешно».
        """
        self.assertIsNone(
            re.search(r"run_journal\.py[^\n]*[0-9]>>", self.code),
            "числовой аргумент журнала склеен с >> — потеряется")

    def test_bat_is_still_ascii_only(self):
        """cmd читает .bat в OEM-кодировке; кириллица приедет мусором."""
        try:
            self.raw.decode("ascii")
        except UnicodeDecodeError as exc:
            self.fail(f".bat содержит не-ASCII (байт {exc.start}). Русские "
                      f"формулировки — в Python-скриптах, как было до правки.")


class TestSlotMatchesCommittedXml(unittest.TestCase):
    """Звено 11: константа слота ↔ закоммиченный экспорт XML задачи.

    Портируемо и потому здесь, а не в tools/: идёт и на Mac напарника. Второе
    звено (XML ↔ живая задача) — Windows-only, в bot/schedule_check.py.
    """

    def test_11_committed_xml_matches_the_constant(self):
        import schedule_check as sc

        missing = []
        for task, slot in sc.SLOTS.items():
            path = _ROOT / sched.TASK_XML_DIR / sched.TASK_XML[task]
            if not path.exists():
                missing.append(sc.EXPORT_HINT.format(task=task, path=path))
                continue
            self.assertEqual(
                sc.slot_from_xml(sc._read_xml(path)), f"{slot:%H:%M}",
                f"{task}: слот в коде и в закоммиченном XML разошлись")
        if missing:
            # Именно fail, а не skip: пропущенная проверка — это список, который
            # никто не читает. Экспорт снимает человек (агенту Set-*/экспорт
            # задач режет классификатор), и до тех пор сверять НЕЧЕМ — молчать
            # об этом нельзя.
            self.fail("экспорта XML задач нет, сверять нечем. Снять командами:\n"
                      + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
