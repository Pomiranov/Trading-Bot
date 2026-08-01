"""Сверка расписания: константа ↔ закоммиченный XML ↔ живая задача Windows.

Зачем модуль, а не строчка в тесте. Проверка, которую никто не зовёт, — это
список, который никто не читает: тот же класс, что правило 8 §8. Поэтому логика
лежит здесь ОДНОЙ копией, и её зовут двое:

  - сторож, каждым своим запуском (то есть раз в сутки) — результат уходит
    строкой в сообщение Telegram;
  - человек вручную — `python tools/check_scheduled_tasks.py`.

Второе звено (XML ↔ живая задача) проверяется только на Windows. На Mac
напарника проверка не молчит, а honestly говорит «не проверено»: молчание
прочиталось бы как «проверено и совпало».

Первое звено (константа ↔ XML) здесь не проверяется — оно портируемо и потому
живёт в тестах, где идёт и на Mac.

Импорт-бюджет: только stdlib + run_schedule. Ничего от БД и learning: модуль
зовёт сторож, у которого бюджет узкий по построению.

СТРОГО READ-ONLY: единственная внешняя команда — Export-ScheduledTask. Никаких
Set-*: сторож ничего не лечит (см. докстринг forward_healthcheck), а правки
задач у агента режет классификатор и делает их человек.
"""

import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_schedule import (SLOT_FORWARD, SLOT_HEALTHCHECK, TASK_FORWARD,  # noqa: E402
                         TASK_HEALTHCHECK, TASK_XML, TASK_XML_DIR)

ROOT = Path(__file__).resolve().parent.parent

SLOTS = {TASK_FORWARD: SLOT_FORWARD, TASK_HEALTHCHECK: SLOT_HEALTHCHECK}

_NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}

# Windows пишет XML задач в UTF-16 с BOM; Export-ScheduledTask через Out-File
# -Encoding utf8 даёт UTF-8, возможно с BOM. Читаем терпимо к обоим, потому что
# файл снимает человек командой, а не код — и требовать от него точной кодировки
# значило бы поставить проверку в зависимость от того, как её вход набрали.
_ENCODINGS = ("utf-8-sig", "utf-16", "utf-8")

EXPORT_HINT = ('Export-ScheduledTask -TaskName "{task}" | '
               'Out-File -Encoding utf8 {path}')


def _read_xml(path: Path) -> str:
    last: Exception | None = None
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as exc:
            last = exc
    raise ValueError(f"кодировка не распознана ({last})")


def slot_from_xml(xml_text: str) -> str:
    """Время суток триггера из XML задачи, как 'HH:MM'.

    Берётся StartBoundary календарного триггера. Дата в нём — когда задачу
    завели, и к слоту отношения не имеет; значимо только время суток.

    Смещение зоны СОЗНАТЕЛЬНО игнорируется, и это не небрежность. Замерено
    01.08 на живом экспорте: у `QuantFlow Forward D1` стоит
    `2026-07-12T00:15:00` — БЕЗ смещения, а у `QuantFlow Forward Healthcheck`
    `2026-07-26T09:00:00+03:00` — СО смещением. То есть два триггера одного
    проекта записаны по-разному. Ежедневный триггер планировщика срабатывает по
    МЕСТНЫМ настенным часам, поэтому сверять надо именно настенное время суток;
    разбор смещения здесь дал бы расхождение там, где его нет.
    Оговорка, которую надо помнить: при смене часового пояса машины эти две
    записи разъедутся по фактическому моменту запуска, и данная проверка этого
    НЕ поймает — она про «слот в коде равен слоту в задаче», а не про зоны.
    """
    root = ElementTree.fromstring(xml_text.lstrip("﻿"))
    starts = [el.text for el in root.iterfind(".//t:StartBoundary", _NS) if el.text]
    if not starts:
        # fail-loud: пустой результат означал бы «слоты совпали», когда
        # сверять было нечего.
        raise ValueError("в XML нет ни одного StartBoundary")
    stamp = starts[0]
    m = re.match(r"\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})", stamp)
    if not m:
        raise ValueError(f"StartBoundary {stamp!r} не разобран")
    return f"{m.group(1)}:{m.group(2)}"


def live_task_xml(task: str) -> str:
    """XML живой задачи. Только чтение; пусто/ошибка — наружу исключением."""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f'Export-ScheduledTask -TaskName "{task}"'],
        capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ValueError((proc.stderr or "пустой вывод").strip().splitlines()[0])
    return proc.stdout


def check() -> tuple[bool, list[str]]:
    """(всё совпало, строки отчёта). Каждая задача — своя строка."""
    ok = True
    lines: list[str] = []
    for task, slot in SLOTS.items():
        want = f"{slot:%H:%M}"
        path = ROOT / TASK_XML_DIR / TASK_XML[task]
        if not path.exists():
            ok = False
            # Сама команда экспорта здесь НЕ печатается: строка уходит в
            # Telegram, а две команды PowerShell целиком делают сообщение
            # нечитаемым. Команда — в выводе tools/check_scheduled_tasks.py,
            # то есть там, где её собираются выполнять.
            lines.append(f"{task}: экспорта XML нет "
                         f"({TASK_XML_DIR}/{TASK_XML[task]})")
            continue
        try:
            in_file = slot_from_xml(_read_xml(path))
        except (ValueError, ElementTree.ParseError) as exc:
            ok = False
            lines.append(f"{task}: XML не разобран — {exc}")
            continue
        if in_file != want:
            ok = False
            lines.append(f"{task}: слот в коде {want}, в XML {in_file} — "
                         "расписание уехало")
            continue
        if sys.platform != "win32":
            lines.append(f"{task}: слот {want} совпадает с XML; живая задача "
                         "не проверена (не Windows)")
            continue
        try:
            in_live = slot_from_xml(live_task_xml(task))
        except Exception as exc:      # noqa: BLE001 — текст уходит человеку
            ok = False
            lines.append(f"{task}: живую задачу прочитать не удалось — "
                         f"{str(exc).splitlines()[0]}")
            continue
        if in_live != want:
            ok = False
            lines.append(f"{task}: слот в коде {want}, в живой задаче {in_live} — "
                         "расписание уехало")
        else:
            lines.append(f"{task}: слот {want} совпадает с XML и живой задачей")
    return ok, lines


def describe_tasks() -> tuple[bool, str]:
    """(тревога?, одна строка для сообщения сторожа).

    Сбой самой проверки НЕ валит сторожа: сторож не должен умирать от
    диагностики того, что он охраняет. Но и не молчит — говорит, что не смог.
    """
    try:
        ok, lines = check()
    except Exception as exc:      # noqa: BLE001 — последний барьер
        return False, ("⚠ Задачи планировщика: проверить не удалось — "
                       f"{str(exc).splitlines()[0]}")
    if ok:
        return False, "Задачи планировщика: слоты совпадают с XML"
    return True, "🚨 Задачи планировщика: " + "; ".join(lines)


if __name__ == "__main__":
    all_ok, report = check()
    for line in report:
        print(line)
    sys.exit(0 if all_ok else 1)
