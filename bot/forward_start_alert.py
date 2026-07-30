"""QuantFlow — громкое уведомление о НЕсостоявшемся старте форвард-прогона.

Запуск (из run_forward_d1.bat, перед exit /b 1):
    python bot\\forward_start_alert.py docker-daemon
    python bot\\forward_start_alert.py db-timeout 450
    python bot\\forward_start_alert.py "свободный текст"      # для ручной проверки

Причины передаются КЛЮЧОМ, а текст живёт здесь. Причина не в красоте: cmd читает
.bat в OEM-кодировке (cp866), и кириллица, переданная аргументом из .bat, приехала
бы в Telegram мусором — то есть уведомление сломалось бы ровно в том сценарии, для
которого написано. Поэтому .bat остаётся чисто латинским, как и был до 30.07.

Код возврата: 0 — доставлено, 1 — нет. Вызывающий .bat всё равно завершается
кодом 1: прогон не состоялся, и LastTaskResult обязан это показывать. Тем
сторож отличается сознательно — у него не состоялась ПРОВЕРКА, и он возвращает 0
после успешной отправки (forward_healthcheck.py:586-599).

Зачем отдельный файл. До 30.07 отказ старта был ТИХИМ: строка в
logs\\forward_d1.log и `exit /b 1`. Про то, что прогона не было, человек узнавал
только из сообщения сторожа в 09:00 — то есть через девять часов, и не про
причину, а про следствие. Принцип §9 PROJECT_STATE: система флагает, человек
решает. Флагать нечем — значит принцип не работает.

Импорт-бюджет: только notify (stdlib + requests + config). Ни БД, ни learning,
ни pandas: скрипт вызывается ровно в тот момент, когда БД недоступна, и любая
зависимость от неё сделала бы уведомление невозможным именно тогда, когда оно
нужно.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

# Тот же bootstrap, что в forward_healthcheck.py:45-50 и db_wait.py: путь и .env
# от расположения файла, а не от cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from notify import credentials_ready, escape, send  # noqa: E402

STRATEGY_ID = "osc_range_moex_d1_fwd"
LOG_HINT = "logs\\forward_d1.log"

# Ключ → текст. `{}` подставляется вторым аргументом, если он есть.
REASONS = {
    "docker-daemon": "Docker daemon не поднялся за {} с — docker info не отвечает. "
                     "Стек не запускался, БД не проверялась.",
    "docker-compose": "docker compose up -d завершился с ошибкой при поднятом "
                      "daemon — смотреть его вывод в логе.",
    "db-timeout":     "БД не приняла соединение за {} с после подъёма стека. "
                      "В логе — какой адрес отвечал, какой нет и с какой ошибкой.",
}


def _text(argv: list[str]) -> str:
    """Текст причины из ключа и необязательного параметра.

    Неизвестный ключ НЕ подменяется дефолтом молча: он уходит в сообщение как есть.
    Иначе опечатка в .bat превратила бы конкретную причину в «что-то случилось» —
    тот же класс, что тихий отказ, ради которого этот скрипт написан.
    """
    if not argv:
        return "причина не передана вызывающим .bat"
    key, rest = argv[0], argv[1:]
    template = REASONS.get(key)
    if template is None:
        return " ".join(argv).strip()
    if "{}" not in template:
        return template
    # Параметр не передан — «за ? с» честнее, чем «за {} с»: видно, что число
    # потерялось по дороге, а не что предела не было.
    return template.format(rest[0] if rest else "?")


def main(argv: list[str]) -> int:
    reason = _text(argv)

    if not credentials_ready():
        # Слать некуда. Печатаем в stdout — .bat перенаправляет его в лог, так
        # что след всё равно останется, пусть и тихий.
        print(f"Старт форварда не состоялся, уведомить некому: {reason}")
        return 1

    text = (
        f"🚨 <b>Форвард НЕ СТАРТОВАЛ</b> — {STRATEGY_ID}\n"
        f"Прогон 00:15 не состоялся, решение за человеком.\n"
        f"Причина: {escape(reason)}\n"
        f"Подробности: {escape(LOG_HINT)}"
    )
    delivered = send(text)
    print(f"Старт форварда не состоялся ({reason}); "
          f"уведомление {'доставлено' if delivered else 'НЕ доставлено'}")
    return 0 if delivered else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:      # последний барьер: без трейсбека наружу
        print(f"Уведомление о несостоявшемся старте не отправлено: {exc}")
        sys.exit(1)
