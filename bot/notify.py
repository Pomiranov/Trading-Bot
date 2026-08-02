"""QuantFlow — отправка уведомлений в Telegram для служебных скриптов.

Используется сторожем форвард-контура (bot/forward_healthcheck.py) и
батч-раннером разбора глав (tools/read_chapters.py).

Отправка своя, а не через ui.telegram_bot._send: тот модуль на импорте тянет
legacy feedback_store, risk, signals и ходит в БД (см. run_forward_d1.py:102).
Служебный скрипт не должен зависеть от торгового стека — сторож тем более не
должен зависеть от того, что он охраняет.

Импорт-бюджет модуля намеренно узкий: stdlib + requests + config. Ничего из
learning/, backtest/, ui/ здесь появляться не должно.

Токен и chat_id — из config.telegram (env TELEGRAM_TOKEN / TELEGRAM_CHAT_ID),
тот же секрет, что у ui/telegram_bot.py.
"""

import html as _html
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Модуль импортируется и из bot/ (сторож), и из tools/ (раннер), где sys.path
# и cwd другие. Bootstrap идемпотентный: если config уже импортирован —
# ничего не делает. Путь и .env берутся от расположения файла, а не от cwd:
# под Task Scheduler cwd легко оказывается не тем, и тогда .env не
# подхватится, TELEGRAM_TOKEN будет пустым, а причина сбоя — ложной.
ROOT = Path(__file__).resolve().parent.parent

if "config" not in sys.modules:
    from dotenv import load_dotenv

    _bot_dir = str(ROOT / "bot")
    if _bot_dir not in sys.path:
        sys.path.insert(0, _bot_dir)
    load_dotenv(ROOT / ".env")

from config import config  # noqa: E402  — только после sys.path/.env

logger = logging.getLogger("quantflow.notify")

TIMEOUT_SEC = 15

# Лимит sendMessage — 4096 символов. Сообщение длиннее API отклоняет целиком
# (HTTP 400), то есть сводка по двадцати главам пропала бы молча.
MAX_LEN = 4096
_TRUNCATED = "\n…(обрезано)"

# ── Классы отказа доставки ───────────────────────────────────────────────────
#
# КЛАСС, а не строка. От класса зависит, лечится ли отказ повторами вообще, и
# решение об этом принимает код, а не человек, читающий текст. В одном боевом
# логе лежат оба вида: 02.08 — ConnectTimeout (повтор уместен), 26.07 — 401 и
# 404 с токеном-заглушкой (повтор бесполезен, нужен человек). Строка различает
# их только на глаз.
FAIL_DNS = "dns"          # имя не разрешилось
FAIL_CONNECT = "connect"  # соединение не установилось
FAIL_HTTP = "http"        # ответ с ошибкой
FAIL_OTHER = "other"      # всё прочее: повторять НЕ пытаемся

FAIL_RU = {
    FAIL_DNS: "имя не разрешилось",
    FAIL_CONNECT: "соединение не установилось",
    FAIL_HTTP: "ответ с ошибкой",
    FAIL_OTHER: "неопознанный отказ",
}

# ── Бюджет повторов (П1) ─────────────────────────────────────────────────────
#
# 🚩 ВЫБРАН, НЕ ИЗМЕРЕН. Обосновать его «сеть поднимется за минуту-другую»
# НЕЛЬЗЯ: 02.08 успешная проба TCP 443 в 19:04 совместима и с «сеть встала
# через минуту после 16:24», и с волновым пропаданием доступа к api.telegram.org
# по причинам ВНЕ машины. Причина отказа не установлена, и бюджет её не знает.
#
# Порядок величины взят от соседа по тому же процессу: подключение к БД
# (forward_healthcheck.py: DB_ATTEMPTS x DB_RETRY_SEC) стоит 50 с худшего случая
# и куплено доводом «Docker Desktop дотягивается после логона». Внешняя сеть
# восстанавливается не быстрее локального демона, поэтому здесь бюджет ВТРОЕ
# больше. Верхняя граница задана не вкусом, а ExecutionTimeLimit задачи —
# сверяется тестом test_whole_watchdog_budget_fits_ExecutionTimeLimit_of_the_task.
#
# Чего бюджет НЕ даёт, сказано заранее: если сеть не поднимется за него,
# сообщение снова пропадёт. Окно сужается, дыра не закрывается — ради дыры
# существует накопитель ниже.
SEND_ATTEMPTS = 4
SEND_BACKOFF_SEC = (15, 30, 60)
SEND_BUDGET_SEC = SEND_ATTEMPTS * TIMEOUT_SEC + sum(SEND_BACKOFF_SEC)

# ── Накопитель недоставленного (П2) ──────────────────────────────────────────
#
# Зачем. 02.08 сторож отработал правильно и промолчал: единственными следами
# отказа были строка в логе и LastTaskResult, затираемый следующим прогоном.
# Отказ доставки самоуничтожался за сутки.
#
# 🚩 ГРАНИЦА ЛЕКАРСТВА, записанная здесь, а не только в документе: накопитель
# молчит ровно столько, сколько машина выключена. Неделя простоя — неделя
# тишины. Это ПРИНЯТЫЙ ПРЕДЕЛ, равный границе долга №46, а не дефект: кодом на
# этой машине он не лечится и остаётся доводом за внешний хост.
UNDELIVERED_ENV = "FWD_UNDELIVERED_DIR"     # ради проверки НА КОПИИ, как FWD_RUN_JOURNAL
UNDELIVERED_DEFAULT = "logs/undelivered"


def escape(text: str) -> str:
    """html.escape для вызывающих — чтобы не импортировать html ради одной строки."""
    return _html.escape(text)


def first_line(exc: Exception) -> str:
    """Одна строка из исключения — без трейсбека, чтобы не пугать в Telegram."""
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:300]


def credentials_ready() -> bool:
    """Есть ли куда отправлять. Пишет причину в лог, если нет.

    Заглушки из .env.example (`your_...`) — тот же случай, что «не задано»:
    сообщение уйдёт в никуда, а скрипт отчитается об успехе.
    """
    token = config.telegram.token
    chat_id = config.telegram.chat_id
    if not token or not chat_id:
        logger.error("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID не заданы — некому уведомлять")
        return False
    if token.startswith("your_") or chat_id.startswith("your_"):
        logger.error("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID остались заглушками "
                     "из .env.example — некому уведомлять")
        return False
    return True


def truncate(text: str) -> str:
    """Обрезать до лимита Telegram. Публичная: ловушка 4096 одна на весь проект.

    Второе определение этой константы означало бы, что однажды одно из них
    отстанет, и сообщение начнёт пропадать в той половине кода, где лимит
    забыли.
    """
    if len(text) <= MAX_LEN:
        return text
    logger.warning("Сообщение %d символов — обрезано до лимита Telegram %d",
                   len(text), MAX_LEN)
    return text[: MAX_LEN - len(_TRUNCATED)] + _TRUNCATED


def classify(exc: Exception) -> str:
    """Машинно-различимый класс отказа доставки.

    Порядок веток значим: ConnectTimeout — подкласс ConnectionError, и общая
    ветка съела бы его, потеряв различие «имени нет» и «адрес не отвечает».
    """
    if isinstance(exc, requests.exceptions.HTTPError):
        return FAIL_HTTP
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return FAIL_CONNECT
    if isinstance(exc, requests.exceptions.ConnectionError):
        blob = str(exc).lower()
        # Признаки разрешения имени у трёх стеков сразу: urllib3, POSIX, WinSock.
        if any(mark in blob for mark in (
                "nameresolutionerror", "failed to resolve", "getaddrinfo",
                "name or service not known", "temporary failure in name resolution",
                "11001",   # WSAHOST_NOT_FOUND
        )):
            return FAIL_DNS
        return FAIL_CONNECT
    if isinstance(exc, requests.exceptions.Timeout):
        # Соединение встало, ответа нет. Для решения о повторе это тот же
        # случай, что и «не установилось», и отдельного класса не заводим:
        # различие ничего не меняло бы в действии.
        return FAIL_CONNECT
    return FAIL_OTHER


def is_retryable(exc: Exception) -> bool:
    """Лечится ли этот отказ ожиданием.

    4xx повторять НЕЛЬЗЯ и это не осторожность: 26.07 в боевом логе лежат 404
    (токен-заглушка из .env.example) и 401 (токен недействителен). Повторы
    потратили бы бюджет задачи и спрятали причину за ожиданием — то есть
    сделали бы ровно то, против чего написан весь этот модуль.
    """
    cls = classify(exc)
    if cls in (FAIL_DNS, FAIL_CONNECT):
        return True
    if cls == FAIL_HTTP:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return status is not None and (status == 429 or 500 <= status <= 599)
    return False


# ── Накопитель недоставленного ───────────────────────────────────────────────

def undelivered_dir(root: Path | None = None) -> Path:
    """Каталог накопителя. Читается ПРИ ВЫЗОВЕ, не на импорте.

    Как journal_path в run_schedule: тест меняет переменную окружения между
    случаями, а модуль к тому моменту уже импортирован.
    """
    override = os.getenv(UNDELIVERED_ENV)
    if override:
        return Path(override)
    return (root or ROOT) / UNDELIVERED_DEFAULT


def spool(text: str, failure_class: str, reason: str) -> Path | None:
    """Положить недоставленное на диск. Возвращает путь или None при отказе.

    Отказ записи НЕ поднимается наружу: накопитель — диагностика, и уронить
    из-за него процесс значило бы обменять работу на её протокол.
    """
    try:
        directory = undelivered_dir()
        directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        # Порядковый суффикс: две неудачи в одну микросекунду маловероятны, но
        # молча потерянная запись здесь недопустима по смыслу модуля.
        seq = len(list(directory.glob("*.json")))
        path = directory / f"{now:%Y%m%dT%H%M%S}-{seq:03d}.json"
        path.write_text(json.dumps({
            "at": now.isoformat(timespec="seconds"),
            "class": failure_class,
            "reason": reason,
            "text": text,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except Exception as exc:      # noqa: BLE001 — последний барьер
        logger.error("Накопитель недоставленного: запись не сделана — %s",
                     first_line(exc))
        return None


def pending() -> list[dict]:
    """Записи о недоставленных сообщениях, по возрастанию времени.

    Битый файл НЕ пропускается молча: он попадает в список отдельной записью
    класса FAIL_OTHER. Иначе провал доставки спрятался бы за испорченной
    записью о провале доставки.
    """
    directory = undelivered_dir()
    if not directory.exists():
        return []
    rows: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:      # noqa: BLE001
            rows.append({"at": path.stem, "class": FAIL_OTHER,
                         "reason": f"запись не разобрана: {first_line(exc)}",
                         "text": ""})
    return rows


def pending_notice() -> str | None:
    """Приписка о ВСЕХ пропущенных отправках. None — пропущенных нет.

    Перечисляются все, а не последняя: машина, простоявшая три дня, копит три
    провала, и «один раз не дошло» соврало бы в меньшую сторону ровно там, где
    важен масштаб.
    """
    rows = pending()
    if not rows:
        return None
    lines = [f"⚠ <b>Предыдущие доставки провалились: {len(rows)}</b>"]
    for row in rows:
        at = str(row.get("at", "?"))
        cls = row.get("class", FAIL_OTHER)
        lines.append(f"  {escape(at)} — {FAIL_RU.get(cls, cls)}: "
                     f"{escape(str(row.get('reason', '')))}")
    return "\n".join(lines)


def clear_pending() -> int:
    """Убрать накопленное. Зовёт ТОТ, КТО ПОКАЗАЛ приписку человеку.

    Намеренно НЕ вызывается из send(): успешная отправка какого-то другого
    сообщения не означает, что человек увидел список пропущенных. Чистка на
    успехе доставки была бы тем же «прочитано и забыто», против которого
    сторож не сохраняет состояние до подтверждённой доставки.
    """
    directory = undelivered_dir()
    if not directory.exists():
        return 0
    removed = 0
    for path in sorted(directory.glob("*.json")):
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            logger.error("Накопитель: %s не удалён — %s", path.name, first_line(exc))
    return removed


def send(text: str, *, parse_mode: str = "HTML", spool_on_failure: bool = True) -> bool:
    """Отправить сообщение в Telegram. True — доставлено.

    Повторы — только для отказов, которые ожиданием лечатся (см. is_retryable).
    Окончательный провал оставляет след на диске: код 1 и строка в логе за
    сутки затираются, а накопитель переживает и прогон, и перезагрузку.
    """
    token = config.telegram.token
    chat_id = config.telegram.chat_id
    if not token or not chat_id:
        logger.error("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID не заданы — сообщение не отправлено")
        return False

    payload = {"chat_id": chat_id, "text": truncate(text), "parse_mode": parse_mode}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    last_cls, last_reason = FAIL_OTHER, "попыток не было"

    for attempt in range(1, SEND_ATTEMPTS + 1):
        try:
            resp = requests.post(url, json=payload, timeout=TIMEOUT_SEC)
            resp.raise_for_status()
            return True
        except Exception as exc:      # noqa: BLE001 — класс определяем ниже
            last_cls = classify(exc)
            # Текст ошибки requests содержит полный URL, то есть и токен: он не
            # должен попасть ни в лог, ни в накопитель, ни в Telegram.
            last_reason = first_line(exc).replace(token, "<token>")
            # Три исхода, и в логе они обязаны выглядеть по-разному: «жду и
            # повторю», «повтор не поможет» и «попытки кончились» требуют от
            # человека разных действий, а слитые в одну строку неразличимы.
            worth_retry = is_retryable(exc)
            attempts_left = attempt < SEND_ATTEMPTS
            if not worth_retry:
                tail = " — повтор не поможет, нужен человек"
            elif not attempts_left:
                tail = f" — попытки кончились ({SEND_ATTEMPTS})"
            else:
                tail = f" — повтор через {SEND_BACKOFF_SEC[attempt - 1]} с"
            logger.error("Telegram [%s], попытка %d/%d: %s%s",
                         last_cls, attempt, SEND_ATTEMPTS, last_reason, tail)
            if not (worth_retry and attempts_left):
                break
            time.sleep(SEND_BACKOFF_SEC[attempt - 1])

    if spool_on_failure:
        spool(text, last_cls, last_reason)
    return False
