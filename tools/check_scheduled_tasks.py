"""Ручной прогон сверки расписания. Логика — в bot/schedule_check.py, одной копией.

    python tools/check_scheduled_tasks.py

Код возврата: 0 — всё совпало, 1 — расхождение или проверить не удалось.

Кто ЗОВЁТ эту проверку, названо явно, иначе она станет списком, который никто не
читает (класс правила 8 §8):

  - СТОРОЖ, каждым своим запуском, то есть раз в сутки в 09:00 — результат
    уходит строкой в сообщение Telegram (forward_healthcheck.build_message
    через schedule_check.describe_tasks);
  - ЧЕЛОВЕК вручную — этим файлом, когда правил задачи или расписание.

Сверяется второе звено: закоммиченный экспорт XML ↔ живая задача Windows.
Первое звено (константа в bot/run_schedule.py ↔ закоммиченный XML) проверяется
тестом, потому что оно портируемо и должно идти и на Mac.

СТРОГО READ-ONLY: единственная внешняя команда — Export-ScheduledTask.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "bot"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from schedule_check import EXPORT_HINT, ROOT, SLOTS, TASK_XML, check  # noqa: E402
from run_schedule import TASK_XML_DIR  # noqa: E402

if __name__ == "__main__":
    ok, report = check()
    for line in report:
        print(line)

    # Готовые команды печатаются ЗДЕСЬ, а не в сообщении сторожа: человек
    # выполняет их из терминала, а Telegram от двух команд PowerShell целиком
    # становится нечитаемым.
    missing = [t for t in SLOTS if not (ROOT / TASK_XML_DIR / TASK_XML[t]).exists()]
    if missing:
        print("\nСнять экспорт задач (только чтение, ничего не меняет):")
        for task in missing:
            print("  " + EXPORT_HINT.format(
                task=task, path=ROOT / TASK_XML_DIR / TASK_XML[task]))

    print("\nИТОГ: совпадает" if ok else "\nИТОГ: РАСХОЖДЕНИЕ")
    sys.exit(0 if ok else 1)
