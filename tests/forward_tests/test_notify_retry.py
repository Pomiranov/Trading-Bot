"""Доставка уведомлений: бюджет повторов (П1) и след о недоставке (П2).

Предмет куплен замером 02.08, а не выведен из чтения кода.

02.08 в 16:24:24 сторож отработал ПРАВИЛЬНО: прочитал БД, собрал вердикт,
записал его в лог. В 16:24:31 — ровно через 15 с, то есть один `TIMEOUT_SEC`, —
`notify.send` вернул False по `ConnectTimeout` к api.telegram.org, и задача
завершилась кодом 1. Машина в тот момент работала 6 мин 29 с после ХОЛОДНОЙ
загрузки (16:17:55, BootType 0x0), потому что ночью упала в bugcheck 0x9F.

Два дефекта, каждый со своим тестом:

  П1  У отправки НЕТ бюджета повторов — одна попытка. В ТОМ ЖЕ файле у
      подключения к БД бюджет 3 x 10 с, и комментарий forward_healthcheck.py:96
      объясняет зачем: «Docker Desktop может дотягиваться после логона». Сеть
      после холодной загрузки — тот же класс отказа, и он остался без бюджета.

  П2  Провал доставки не оставляет следа, который кто-нибудь читает. Их ровно
      два: строка [ERROR] в логе и LastTaskResult задачи. Лог без повода никто
      не открывает, LastTaskResult затирается следующим прогоном. Отказ
      самоуничтожается за сутки — что 02.08 и произошло бы, не начнись разбор
      в тот же вечер.

🚩 ПОЧЕМУ КЛАСС ОТКАЗА — МАШИННО-РАЗЛИЧИМЫЙ, А НЕ СТРОКА. От класса зависит,
лечится ли отказ повторами ВООБЩЕ. В одном и том же logs/forward_healthcheck.log
лежат оба вида: 02.08 — `ConnectTimeout` (повторы уместны), 26.07 — `401` и
`404` (повторы бесполезны, нужен человек с правильным токеном). Строка их
различает только на глаз, а решение о повторе принимает код.

🚩 ГРАНИЦА ЛЕКАРСТВА, записанная в тесте намеренно: П2 молчит ровно столько,
сколько машина выключена. Неделя простоя — неделя тишины. Это ПРИНЯТЫЙ ПРЕДЕЛ,
равный границе долга №46, а не дефект; кодом на этой машине не лечится.
"""

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

import requests

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import notify  # noqa: E402

HEALTHCHECK_XML = _ROOT / "infra" / "scheduled_tasks" / "QuantFlow_Forward_Healthcheck.xml"


def _fake_ok():
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    return resp


def _http_error(status: int) -> requests.exceptions.HTTPError:
    """HTTPError с настоящим кодом ответа — его читает решение о повторе."""
    resp = requests.Response()
    resp.status_code = status
    return requests.exceptions.HTTPError(f"{status} Client Error", response=resp)


class _SpoolCase(unittest.TestCase):
    """Общий каркас: накопитель уводится во временный каталог.

    Боевой logs/undelivered/ тесты не трогают по той же причине, по которой
    журнал прогонов уводится через FWD_RUN_JOURNAL: 01.08 replay-тесты налили
    97 строк в БОЕВОЙ журнал (§2з), и урок был записан как правило.
    """

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(
            "os.environ", {notify.UNDELIVERED_ENV: self._tmp.name})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(self._tmp.cleanup)
        self._tg = mock.patch.multiple(notify.config.telegram,
                                       token="TESTTOKEN", chat_id="42")
        self._tg.start()
        self.addCleanup(self._tg.stop)
        # Ожидания между попытками не выстаиваем: тест проверяет ПОРЯДОК и
        # ЧИСЛО попыток, а не способность интерпретатора спать.
        self._sleep = mock.patch.object(notify.time, "sleep")
        self.sleep = self._sleep.start()
        self.addCleanup(self._sleep.stop)


class TestRetryBudgetExists(_SpoolCase):
    """П1: бюджет повторов объявлен и применяется."""

    def test_module_declares_more_than_one_attempt(self):
        self.assertGreater(
            notify.SEND_ATTEMPTS, 1,
            "у отправки одна попытка: ровно этим 02.08 сторож и промолчал")

    def test_transient_failure_is_retried_and_then_delivers(self):
        """Сценарий 02.08 дословно: сеть недоступна, потом появляется."""
        calls = []

        def post(*a, **kw):
            calls.append(1)
            if len(calls) < 3:
                raise requests.exceptions.ConnectTimeout("timed out")
            return _fake_ok()

        with mock.patch.object(notify.requests, "post", side_effect=post):
            self.assertTrue(notify.send("текст"))
        self.assertEqual(len(calls), 3, "повторов не было — доставка потеряна")

    def test_client_error_is_not_retried(self):
        """401/404 повторами не лечится: нужен человек, а не ожидание.

        26.07 в боевом логе лежат оба: 404 с токеном-заглушкой из .env.example и
        401 с настоящим по форме, но недействительным. Повторять их — тратить
        бюджет задачи впустую и прятать причину за ожиданием.
        """
        with mock.patch.object(notify.requests, "post") as post:
            post.return_value.raise_for_status.side_effect = _http_error(401)
            self.assertFalse(notify.send("текст"))
        self.assertEqual(post.call_count, 1,
                         "ответ с ошибкой клиента повторять нельзя")

    def test_server_error_is_retried(self):
        """5xx и 429 — сторона Telegram, повтор уместен."""
        with mock.patch.object(notify.requests, "post") as post:
            post.return_value.raise_for_status.side_effect = _http_error(503)
            self.assertFalse(notify.send("текст"))
        self.assertEqual(post.call_count, notify.SEND_ATTEMPTS)


class TestFailureClassIsMachineReadable(unittest.TestCase):
    """П2, условие 3: класс, а не строка."""

    def test_three_named_classes_are_distinct(self):
        self.assertEqual(
            len({notify.FAIL_DNS, notify.FAIL_CONNECT, notify.FAIL_HTTP}), 3)

    def test_connect_timeout_is_connect_class(self):
        self.assertEqual(
            notify.classify(requests.exceptions.ConnectTimeout("timed out")),
            notify.FAIL_CONNECT)

    def test_name_resolution_is_dns_class(self):
        exc = requests.exceptions.ConnectionError(
            "Failed to resolve 'api.telegram.org' "
            "([Errno 11001] getaddrinfo failed)")
        self.assertEqual(notify.classify(exc), notify.FAIL_DNS)

    def test_http_error_is_http_class(self):
        self.assertEqual(notify.classify(_http_error(404)), notify.FAIL_HTTP)

    def test_retry_decision_follows_the_class(self):
        self.assertTrue(notify.is_retryable(
            requests.exceptions.ConnectTimeout("timed out")))
        self.assertFalse(notify.is_retryable(_http_error(401)))
        self.assertTrue(notify.is_retryable(_http_error(503)))


class TestUndeliveredLeavesATrace(_SpoolCase):
    """П2: недоставленное переживает процесс."""

    def _fail_all(self, exc=None):
        exc = exc or requests.exceptions.ConnectTimeout("timed out")
        with mock.patch.object(notify.requests, "post", side_effect=exc):
            return notify.send("вердикт сторожа")

    def test_failure_is_spooled_with_time_and_class(self):
        self.assertFalse(self._fail_all())
        rows = notify.pending()
        self.assertEqual(len(rows), 1, "провал доставки не оставил следа")
        self.assertEqual(rows[0]["class"], notify.FAIL_CONNECT)
        self.assertIn("at", rows[0])
        self.assertIn("reason", rows[0])

    def test_token_never_reaches_the_spool(self):
        """Текст ошибки requests содержит URL целиком, то есть и токен."""
        exc = requests.exceptions.ConnectTimeout(
            "HTTPSConnectionPool: /botTESTTOKEN/sendMessage timed out")
        self._fail_all(exc)
        blob = "\n".join(str(r) for r in notify.pending())
        self.assertNotIn("TESTTOKEN", blob)

    def test_notice_lists_EVERY_missed_send_not_only_the_last(self):
        """Условие Ника: перечислять ВСЕ пропущенные, а не последнюю.

        Машина, простоявшая три дня, копит три провала. Сообщение о последнем
        сказало бы «один раз не дошло» — то есть соврало бы в меньшую сторону
        ровно там, где важен масштаб.
        """
        for _ in range(3):
            self._fail_all()
        notice = notify.pending_notice()
        self.assertIsNotNone(notice)
        self.assertIn("3", notice, "в приписке нет числа пропущенных отправок")

    def test_notice_is_none_when_nothing_was_missed(self):
        self.assertIsNone(notify.pending_notice())

    def test_spool_clears_only_after_a_successful_delivery(self):
        self._fail_all()
        self.assertEqual(len(notify.pending()), 1)
        with mock.patch.object(notify.requests, "post", return_value=_fake_ok()):
            self.assertTrue(notify.send("следующее сообщение"))
        self.assertEqual(
            len(notify.pending()), 1,
            "send() не вправе чистить накопитель сам: приписку ещё не показали "
            "человеку. Чистит только тот, кто её отправил")
        notify.clear_pending()
        self.assertEqual(len(notify.pending()), 0)


class TestBudgetFitsTheTaskLimit(unittest.TestCase):
    """Бюджет ожиданий против предела, который задаёт планировщик.

    Образец — test_wait_budget_is_one_number: число, живущее в двух местах,
    разъезжается молча. Здесь второе место — XML задачи, и он закоммичен.
    """

    def test_send_budget_is_the_sum_of_its_parts(self):
        self.assertEqual(
            notify.SEND_BUDGET_SEC,
            notify.SEND_ATTEMPTS * notify.TIMEOUT_SEC
            + sum(notify.SEND_BACKOFF_SEC),
            "бюджет отправки посчитан не из своих слагаемых")

    def test_backoff_covers_every_gap_between_attempts(self):
        self.assertEqual(len(notify.SEND_BACKOFF_SEC), notify.SEND_ATTEMPTS - 1,
                         "число пауз не совпадает с числом промежутков")

    def test_whole_watchdog_budget_fits_ExecutionTimeLimit_of_the_task(self):
        """Сторож обязан уложиться в предел ЗАДАЧИ, иначе его убьют на полпути.

        Предел берётся из закоммиченного XML, а не из литерала 3600: вторая
        копия числа разъехалась бы при переносе задачи.
        """
        import forward_healthcheck as hc
        import schedule_check

        # Читаем ЕГО читалкой, а не своей: у экспорта Windows объявление
        # говорит UTF-16, а байты приходят UTF-8 с BOM, и schedule_check._read_xml
        # уже терпит оба. Вторая копия этой терпимости разъехалась бы с первой.
        raw = schedule_check._read_xml(HEALTHCHECK_XML)
        m = re.search(r"<ExecutionTimeLimit>PT(\d+)H</ExecutionTimeLimit>", raw)
        self.assertIsNotNone(m, "ExecutionTimeLimit не найден в XML задачи")
        limit = int(m.group(1)) * 3600

        db = (hc.DB_ATTEMPTS * hc.DB_CONNECT_TIMEOUT
              + (hc.DB_ATTEMPTS - 1) * hc.DB_RETRY_SEC)
        total = db + notify.SEND_BUDGET_SEC
        self.assertLess(
            total, limit,
            f"худший случай {total} с не влезает в предел задачи {limit} с: "
            f"планировщик убьёт сторожа раньше, чем он успеет доложить")


class TestWatchdogShowsThePendingNotice(unittest.TestCase):
    """Приписка обязана попасть В СООБЩЕНИЕ, а не остаться в файле."""

    def test_notice_is_prepended_to_the_verdict(self):
        import forward_healthcheck as hc
        with mock.patch.object(notify, "pending_notice",
                               return_value="⚠ Прошлая доставка провалилась"):
            text = hc._with_pending_notice("✅ <b>Форвард жив</b>")
        self.assertTrue(text.startswith("⚠ Прошлая доставка провалилась"),
                        "приписка не в начале — её не увидят")
        self.assertIn("Форвард жив", text)

    def test_verdict_is_untouched_when_nothing_is_pending(self):
        import forward_healthcheck as hc
        with mock.patch.object(notify, "pending_notice", return_value=None):
            self.assertEqual(hc._with_pending_notice("вердикт"), "вердикт")


class TestExitCodesAreDistinguishable(unittest.TestCase):
    """Код 1 сегодня значит и «не доставлено», и «сторож упал»."""

    def test_crash_has_its_own_exit_code(self):
        import forward_healthcheck as hc
        self.assertNotEqual(
            hc.EXIT_NOT_DELIVERED, hc.EXIT_CRASHED,
            "по коду возврата нельзя отличить сорванную доставку от падения")


if __name__ == "__main__":
    unittest.main()
