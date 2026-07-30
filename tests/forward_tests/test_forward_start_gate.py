"""Гейт старта форварда: ожидание БД и ГРОМКИЙ отказ (правка 30.07).

Предмет. До 30.07 отказ старта был тихим — строка в logs\\forward_d1.log и
`exit /b 1`, — а гейт проверял БД `docker exec trading_db pg_isready`, то есть
ВНУТРИ контейнера, минуя хостовый порт-прокси Docker Desktop. Прогон подключается
с хоста, поэтому гейт мог сказать «готово», после чего Python падал на том же
порту. Замер 30.07 11:04: `Permission denied (0x0000271D/10013)` на
`localhost (::1), port 5432`.

Проверяется то, что молча ломается и не видно чтением кода:

  - ключ причины, переданный из .bat, СУЩЕСТВУЕТ в REASONS. Опечатка в ключе
    превращает конкретную причину в невнятный текст ровно в тот момент, когда
    человека зовут впервые;
  - предел ожидания в .bat — ОДНО число на гейт и на текст уведомления. Два
    литерала разъехались бы при первой же правке (класс «ставка комиссии в восьми
    местах», PROJECT_STATE раздел 2а);
  - .bat остаётся ASCII: cmd читает его в OEM-кодировке, и кириллица приехала бы
    в Telegram мусором — то есть уведомление сломалось бы в том единственном
    сценарии, для которого написано;
  - диагностика адресов печатает ТЕКСТ ошибки. Без него «::1 не ответил»
    неотличимо от «на ::1 слушает кто-то другой»: замерено 30.07, что на этой
    машине отсутствующий слушатель даёт `Connection refused` на 127.0.0.1 и
    `Permission denied` на ::1 — то есть одна и та же причина выглядит
    по-разному, а разные причины могут выглядеть одинаково.
"""

import re
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

import db_wait  # noqa: E402
import forward_start_alert as alert  # noqa: E402

BAT = _ROOT / "run_forward_d1.bat"


class TestReasonText(unittest.TestCase):
    """Текст причины, уходящий человеку в Telegram."""

    def test_known_key_with_parameter(self):
        text = alert._text(["db-timeout", "450"])
        self.assertIn("450", text)
        self.assertNotIn("{}", text)

    def test_known_key_without_parameter_says_question_mark(self):
        """«за ? с» честнее, чем «за {} с» или молчаливый дефолт.

        Видно, что число потерялось по дороге, а не что предела не было.
        """
        text = alert._text(["db-timeout"])
        self.assertIn("?", text)
        self.assertNotIn("{}", text)

    def test_key_without_placeholder_ignores_extra_args(self):
        self.assertEqual(alert._text(["docker-compose"]),
                         alert.REASONS["docker-compose"])

    def test_unknown_key_passes_through_verbatim(self):
        """Неизвестный ключ НЕ подменяется дефолтом молча.

        Иначе опечатка в .bat превратила бы причину в «что-то случилось» — тот же
        тихий отказ, ради которого весь этот гейт и переписан.
        """
        self.assertEqual(alert._text(["ручная", "проверка"]), "ручная проверка")

    def test_no_args_says_so(self):
        text = alert._text([])
        self.assertIn("не передана", text)


class TestBatContract(unittest.TestCase):
    """Договор между .bat и Python-скриптами. Ломается молча, поэтому тест."""

    @classmethod
    def setUpClass(cls):
        cls.raw = BAT.read_bytes()
        cls.text = cls.raw.decode("ascii", errors="replace")
        # Только ИСПОЛНЯЕМЫЕ строки. Комментарии разбирать нельзя: в них
        # намеренно упомянут и прежний `pg_isready`, и имя скрипта уведомлений —
        # это объяснение правки, и терять его, чтобы упростить тест, значило бы
        # обменять причину на удобство проверки.
        cls.code = "\n".join(
            line for line in cls.text.splitlines()
            if not line.strip().lower().startswith("rem")
        )

    def test_every_reason_key_in_bat_is_known(self):
        keys = re.findall(r"forward_start_alert\.py\s+([a-z][a-z0-9-]*)", self.code)
        self.assertTrue(keys, "в .bat не найдено ни одного вызова уведомления — "
                              "громкий отказ потерян")
        for key in keys:
            self.assertIn(key, alert.REASONS,
                          f"ключ причины {key!r} из .bat отсутствует в REASONS")

    def test_wait_budget_is_one_number(self):
        """Предел ожидания БД — одна переменная, а не два литерала."""
        gate = re.search(r"db_wait\.py\s+--timeout\s+(\S+)", self.code)
        told = re.search(r"forward_start_alert\.py\s+db-timeout\s+(\S+)", self.code)
        self.assertIsNotNone(gate, "вызов db_wait.py не найден")
        self.assertIsNotNone(told, "уведомление о таймауте БД не найдено")
        self.assertEqual(gate.group(1), told.group(1),
                         "гейт и уведомление называют РАЗНЫЙ предел ожидания")
        self.assertTrue(gate.group(1).startswith("%"),
                        "предел задан литералом — при правке разъедется")

    def test_numeric_argument_is_separated_from_redirect(self):
        """Цифра, склеенная с >>, может быть съедена как файловый handle.

        Замерено 30.07: `x 450>>` передаёт 450, `x 1>>` ТЕРЯЕТ аргумент (одиночная
        цифра — это handle), `x 1 >>` передаёт. Сегодняшние 180 и 450 безопасны, но
        привычка к пробелу — то, что не даст будущему однозначному пределу
        приехать как «аргумент не передан».
        """
        self.assertIsNone(
            re.search(r"forward_start_alert\.py[^\n]*[0-9]>>", self.code),
            "числовой аргумент склеен с >> — при однозначном значении потеряется")

    def test_bat_is_ascii_only(self):
        try:
            self.raw.decode("ascii")
        except UnicodeDecodeError as exc:
            self.fail(f".bat содержит не-ASCII (байт {exc.start}): cmd читает файл "
                      f"в OEM-кодировке, и такой текст приедет в лог и Telegram "
                      f"мусором. Русские формулировки — в Python-скриптах.")

    def test_in_container_pg_isready_gate_is_gone(self):
        """Прежний гейт обязан отсутствовать, а не просто дополняться.

        `docker exec … pg_isready` проверяет БД внутри контейнера и потому может
        подтвердить готовность, которой с хоста нет. Оставленный рядом с новым, он
        снова стал бы источником ложного «готово».
        """
        self.assertNotIn("pg_isready", self.code)


class TestAddressDiagnostics(unittest.TestCase):
    """Строка диагностики адресов — единственный источник причины отказа."""

    def test_marks_the_address_the_run_uses(self):
        line = db_wait._describe({"localhost": None}, "localhost")
        self.assertIn("адрес прогона", line)

    def test_keeps_error_text_of_each_failing_address(self):
        line = db_wait._describe(
            {"localhost": "Permission denied (0x0000271D/10013)",
             "127.0.0.1": "Connection refused (0x0000274D/10061)"},
            "localhost",
        )
        self.assertIn("Permission denied", line)
        self.assertIn("Connection refused", line)

    def test_success_is_visible_next_to_failure(self):
        line = db_wait._describe(
            {"localhost": "нет ответа", "127.0.0.1": None}, "localhost")
        self.assertIn("ОК", line)
        self.assertIn("нет ответа", line)

    def test_first_line_drops_traceback(self):
        exc = RuntimeError("первая строка\nвторая строка\nтретья")
        self.assertEqual(db_wait._first_line(exc), "первая строка")


if __name__ == "__main__":
    unittest.main()
