"""QuantFlow — отправка уведомлений в Telegram для служебных скриптов.

Используется сторожем форвард-контура (bot/forward_healthcheck.py) и
батч-раннером разбора глав (tools/read_chapters.py).

Отправка своя, а не через ui.telegram_bot._send: тот модуль на импорте тянет
legacy feedback_store, risk, signals и ходит в БД (см. run_forward_d1.py:59).
Служебный скрипт не должен зависеть от торгового стека — сторож тем более не
должен зависеть от того, что он охраняет.

Импорт-бюджет модуля намеренно узкий: stdlib + requests + config. Ничего из
learning/, backtest/, ui/ здесь появляться не должно.

Токен и chat_id — из config.telegram (env TELEGRAM_TOKEN / TELEGRAM_CHAT_ID),
тот же секрет, что у ui/telegram_bot.py.
"""

import html as _html
import logging
import sys
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


def send(text: str, *, parse_mode: str = "HTML") -> bool:
    """Отправить сообщение в Telegram. True — доставлено."""
    token = config.telegram.token
    chat_id = config.telegram.chat_id
    if not token or not chat_id:
        logger.error("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID не заданы — сообщение не отправлено")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": truncate(text), "parse_mode": parse_mode},
            timeout=TIMEOUT_SEC,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        # Текст ошибки requests содержит полный URL, то есть и токен —
        # в лог он попасть не должен.
        logger.error("Telegram: %s", first_line(exc).replace(token, "<token>"))
        return False
