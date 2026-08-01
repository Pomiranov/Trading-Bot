"""Журнал прогонов форварда: положительное свидетельство о самом прогоне.

Зачем. До 01.08 «прогон не состоялся» сторож мог только ВЫВОДИТЬ из пустоты —
из того, что не появилось свежего бара. Вывод по пустоте молчит там, где нужнее
всего: 01.08 прогон уехал с слота 00:15 на 11:38 (машина спала), к моменту
проверки бар был на месте, и сторож сказал «✅ Форвард жив». Долг №46.

Здесь пишется ПОЛОЖИТЕЛЬНОЕ свидетельство: прогон сам говорит, что он был.
Отсутствие записи — факт, а не догадка.

Записи парные, и это принципиально. Одиночная «прогон был» склеивает три
состояния, которые требуют РАЗНЫХ действий:

    нет start           → не запускался (сон, выключение, задача отключена)
    start без finish    → запустился и умер
    start + finish      → норма, смотреть rc

Запуск (из run_forward_d1.bat):
    python bot\\run_journal.py start
    python bot\\run_journal.py finish 0
    python bot\\run_journal.py session 2026-08-01     # из run_forward_d1.py

Почему `session` — отдельная запись, а не поле в `finish`. Финиш пишет .bat, и
он обработанной сессии не знает: конвенция сессии живёт в market_time и доступна
только Python-прогону. Передавать её через .bat значило бы либо завести вторую
копию конвенции, либо парсить лог. Каждый пишет то, что знает.

Импорт-бюджет: ТОЛЬКО stdlib + run_schedule + market_time (оба сами stdlib-only).
Ни config, ни .env, ни БД, ни learning. Причина та же, что у
forward_start_alert.py: `start` пишется РАНЬШЕ подключения к БД и раньше чтения
конфига, то есть раньше всего, что может упасть. Зависимость от них сделала бы
запись невозможной ровно тогда, когда она нужна.

🚫 ЖУРНАЛ НЕ РОТИРОВАТЬ И НЕ УСЕКАТЬ НИКОГДА. Две строки в сутки — около 70 КБ в
год. Ротация вернула бы неразличимость «записи нет» и «свидетельство утрачено»,
против которой введена строка journal_created. Запрет записан также в
infra/logrotate/quantflow.conf и в долге №46.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Тот же bootstrap, что в forward_start_alert.py:39-40: путь от расположения
# файла, а не от cwd — под Task Scheduler cwd легко оказывается не тем.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))

from market_time import MSK  # noqa: E402
from run_schedule import journal_path, last_slot  # noqa: E402

EVENTS = ("start", "finish", "session")


def _append(record: dict) -> Path:
    """Одна строка JSON в журнал. Файл создаётся с записью journal_created.

    journal_created — не украшение. Без неё «нет строки start за слот»
    неотличимо от «файл создан заново уже после слота», то есть потеря
    свидетельства читалась бы как уверенное «прогон не запускался». Долг №46
    пункт 3, класс «молчаливый ноль».

    Открытие в режиме "a" и одна запись за вызов: журнал append-only, и
    перезапись файла целиком здесь невозможна по построению.
    """
    path = Path(journal_path(ROOT))
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8") as fh:
        if fresh:
            fh.write(json.dumps(
                {"event": "journal_created", "at": datetime.now(MSK).isoformat()},
                ensure_ascii=False) + "\n")
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def build(argv: list[str]) -> dict:
    """Запись по аргументам командной строки.

    Неизвестное событие НЕ подменяется дефолтом: молчаливый `start` вместо
    опечатки означал бы, что прогон, которого не было, отмечен состоявшимся —
    то есть журнал начал бы лгать в ту же сторону, против которой написан.
    """
    if not argv:
        raise ValueError("событие не передано: ожидается " + "|".join(EVENTS))
    event, rest = argv[0], argv[1:]
    if event not in EVENTS:
        raise ValueError(f"неизвестное событие {event!r}: ожидается "
                         + "|".join(EVENTS))

    now = datetime.now(MSK)
    record = {"event": event, "at": now.isoformat()}

    if event == "start":
        # Слот пишется В ЗАПИСЬ, а не выводится сторожем из времени старта:
        # догнанный прогон стартует в 11:38 и относится к слоту 00:15, и связь
        # эта известна только тому, кто запускается. Слот — из run_schedule,
        # своей копии «00:15» здесь нет.
        record["slot"] = last_slot(now).isoformat()
        return record

    if event == "finish":
        if not rest:
            raise ValueError("finish без кода завершения: код обязателен, "
                             "иначе «прогон закончился» неотличимо от "
                             "«закончился успешно»")
        record["rc"] = int(rest[0])
        return record

    # session
    if not rest:
        raise ValueError("session без даты московской сессии")
    record["session"] = date.fromisoformat(rest[0]).isoformat()
    return record


def write(*argv) -> Path:
    """Запись из Python-кода, а не из .bat. Исключения — наружу.

    Нужна ровно для события `session`: обработанную московскую сессию знает
    только прогон, потому что конвенция сессии живёт в market_time.
    Проглатывать здесь ошибку нельзя — вызывающий обязан решить сам; и если
    записи не будет, сторож увидит «rc=0 без сессии» и закричит.
    """
    return _append(build([str(a) for a in argv]))


def main(argv: list[str]) -> int:
    try:
        record = build(argv)
    except ValueError as exc:
        # Печатаем в stdout: .bat перенаправляет его в forward_d1.log, так что
        # след останется. Код 1, но вызывающий .bat из-за журнала прогон НЕ
        # отменяет: сорванная запись хуже, чем несделанный прогон, только для
        # диагностики, а не для торговли.
        print(f"Журнал прогонов: запись не сделана — {exc}")
        return 1
    try:
        path = _append(record)
    except OSError as exc:
        print(f"Журнал прогонов: запись не сделана — {exc}")
        return 1
    print(f"Журнал прогонов: {record['event']} → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
