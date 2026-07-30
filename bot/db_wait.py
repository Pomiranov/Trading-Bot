"""QuantFlow — ожидание готовности БД перед ночным прогоном форварда.

Запуск (из run_forward_d1.bat):
    python bot\\db_wait.py [--timeout 450] [--interval 5]

Код возврата: 0 — БД приняла соединение по адресу, которым пользуется прогон;
1 — не приняла за отведённое время. Больше ничего не делает: docker не
поднимает, задачи не перезапускает, в БД не пишет.

Почему этот скрипт, а не `docker exec trading_db pg_isready`, как было в .bat до
30.07. `pg_isready` внутри контейнера проверяет БД, МИНУЯ хостовый порт-прокси
Docker Desktop, а прогон подключается с хоста. То есть прежний гейт мог сказать
«готово», после чего Python падал на том же самом порту. Замер 30.07 в 11:04:
сторож три раза получил `Permission denied (0x0000271D/10013)` на
`localhost (::1), port 5432`, то есть с хоста порт ещё не был опубликован —
класс отказа, которого прежний гейт не видел по построению.

Почему адресов три, а гейт по одному. Гейт обязан проверять РОВНО тот адрес,
которым пользуется прогон (`config.db.host`, по умолчанию `localhost`) — иначе он
опять проверяет не то. Но `localhost` на этой машине резолвится в IPv6 первым, а
порт-прокси публикует IPv4, поэтому `127.0.0.1` и `::1` пробуются отдельно как
ДИАГНОСТИКА: без неё в логе будет «не ответил» без причины, и «Docker ещё не
поднял прокси» не отличить от «на IPv6 слушает кто-то другой». Решение по
`DB_HOST` принимается через несколько ночей по этому логу, а не аргументом.

Импорт-бюджет узкий намеренно: stdlib + psycopg2 + config. Скрипт обязан
работать именно тогда, когда всё остальное лежит, поэтому ни learning, ни
pandas, ни requests здесь появляться не должны — по той же причине, по которой их
нет в forward_healthcheck.py и notify.py.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import argparse
import time
from datetime import datetime
from pathlib import Path

import psycopg2

# Скрипт живёт в bot/, конфиг тоже. Путь и .env — от расположения файла, а не от
# cwd: под Task Scheduler cwd легко оказывается не тем, и тогда .env не
# подхватится, DB_PASSWORD будет пустым, а причина сбоя — ложной.
# Тот же bootstrap, что в forward_healthcheck.py:45-50.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from config import config  # noqa: E402  — только после sys.path/.env

# Бюджет ожидания. ВЫБРАН, НЕ ИЗМЕРЕН: холодный выход из гибернации ни разу не
# замерялся — все состоявшиеся прогоны 12–30.07 шли на уже поднятой БД, а
# единственный известный отказ (сторож 30.07 11:04) наблюдался только 24 секунды
# и на них не закончился. 450 с = порядок «минуты, не секунды» из наблюдения
# 11:04, с запасом. Каждый прогон печатает ФАКТИЧЕСКОЕ время до успеха, поэтому
# через несколько ночей предел выбирается по данным, как CATCHUP_MAX_BARS
# (run_forward_d1.py:128-141).
TIMEOUT_SEC_DEFAULT = 450
INTERVAL_SEC_DEFAULT = 5

# Короткий таймаут одной попытки: длинный съел бы бюджет ожидания целиком на
# первом же зависшем connect, и «ждём 450 с» превратилось бы в «ждём один connect».
CONNECT_TIMEOUT_SEC = 3

# Адреса для диагностики. Гейт по ним НЕ решает — см. докстринг.
PROBE_ADDRESSES = ("127.0.0.1", "::1")


def _first_line(exc: Exception) -> str:
    """Одна строка из исключения, без трейсбека.

    Дублирует notify.first_line намеренно: импорт notify потянул бы requests, а
    этот скрипт обязан работать в самой поломанной обстановке. Та же причина, по
    которой forward_healthcheck.py дублирует STRATEGY_ID вместо импорта прогона.
    """
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:300]


def _try_connect(host: str) -> str | None:
    """None — соединение принято. Иначе текст ошибки."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=config.db.port,
            user=config.db.user,
            password=config.db.password,
            dbname=config.db.name,
            connect_timeout=CONNECT_TIMEOUT_SEC,
        )
    except Exception as exc:
        return _first_line(exc)
    conn.close()
    return None


def wait(timeout_sec: int, interval_sec: int) -> int:
    """Ждать, пока БД примет соединение по адресу прогона. 0 — приняла."""
    gate_host = config.db.host
    started = time.monotonic()
    attempts = 0
    last: dict[str, str | None] = {}

    while True:
        attempts += 1
        # Порядок важен: сначала адрес прогона. Если он ответил, диагностика уже
        # не нужна — лишние connect'ы в успешном случае только тратят время.
        last[gate_host] = _try_connect(gate_host)
        if last[gate_host] is None:
            elapsed = time.monotonic() - started
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] БД готова: {gate_host}:"
                  f"{config.db.port}/{config.db.name} за {elapsed:.1f} с, "
                  f"попыток: {attempts}")
            return 0

        for addr in PROBE_ADDRESSES:
            if addr != gate_host:
                last[addr] = _try_connect(addr)

        elapsed = time.monotonic() - started
        # Предел проверяется МЕЖДУ попытками, поэтому фактический перебег
        # ограничен длительностью одной попытки: до трёх connect'ов по
        # CONNECT_TIMEOUT_SEC, то есть ~9 с при пределе 450. Ужимать это до
        # секунды значило бы прерывать connect на полуслове и получать в логе
        # ошибку таймаута вместо настоящей причины отказа.
        if elapsed + interval_sec > timeout_sec:
            break
        # Первая попытка печатается всегда: иначе при быстром успехе в логе не
        # останется НИ ОДНОЙ строки, и «БД была не готова 4 секунды» не отличить
        # от «гейт не запускался».
        if attempts == 1:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] БД не готова, ждём "
                  f"(предел {timeout_sec} с): " + _describe(last, gate_host))
        time.sleep(interval_sec)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] БД НЕ ГОТОВА за {elapsed:.1f} с, "
          f"попыток: {attempts} — " + _describe(last, gate_host))
    return 1


def _describe(last: dict[str, str | None], gate_host: str) -> str:
    """Состояние всех адресов одной строкой, с текстом ошибки каждого.

    Текст ошибки обязателен: отказ на уровне сокета выглядит одинаково и при
    «Docker ещё не поднял порт-прокси», и при «на этом адресе слушает кто-то
    другой». Первый случай пройдёт сам, второй — никогда.
    """
    parts = []
    for addr, err in last.items():
        mark = " ← адрес прогона" if addr == gate_host else ""
        parts.append(f"{addr}{mark}: " + ("ОК" if err is None else err))
    return " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ожидание готовности БД")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SEC_DEFAULT,
                        help=f"предел ожидания, с (дефолт {TIMEOUT_SEC_DEFAULT})")
    parser.add_argument("--interval", type=int, default=INTERVAL_SEC_DEFAULT,
                        help=f"пауза между попытками, с (дефолт {INTERVAL_SEC_DEFAULT})")
    args = parser.parse_args()
    return wait(max(1, args.timeout), max(1, args.interval))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:      # последний барьер: без трейсбека наружу
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Гейт БД упал: "
              f"{_first_line(exc)}")
        sys.exit(1)
