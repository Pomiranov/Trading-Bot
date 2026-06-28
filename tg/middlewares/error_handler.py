"""Global error handler for the Telegram application."""
from __future__ import annotations

import logging
import traceback

from telegram import Update
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import ContextTypes

from broker.base import BrokerConnectionError, BrokerNotConfigured

logger = logging.getLogger(__name__)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    exc = context.error
    if exc is None:
        return

    # 409 Conflict — другой экземпляр бота перехватил polling; логируем один раз, не спамим
    if isinstance(exc, Conflict):
        logger.warning("Telegram conflict (409): другой экземпляр бота держит сессию. Ожидание…")
        return

    # Сетевые таймауты — ожидаемо при нестабильном интернете
    if isinstance(exc, (NetworkError, TimedOut)):
        logger.debug("Telegram network error (ignored): %s", exc)
        return

    logger.error("Unhandled exception in update handler", exc_info=exc)

    if not isinstance(update, Update):
        return

    msg = _user_message(exc)
    target = update.effective_message or (
        update.callback_query.message if update.callback_query else None
    )
    if target:
        try:
            await target.reply_text(f"⚠️ {msg}")
        except Exception:
            pass


def _user_message(exc: BaseException) -> str:
    if isinstance(exc, BrokerNotConfigured):
        return f"Брокер не настроен: {exc}\n\nПерейдите в ⚙ Настройки → Брокеры."
    if isinstance(exc, BrokerConnectionError):
        return f"Ошибка подключения к брокеру: {exc}"
    if isinstance(exc, ValueError):
        return f"Некорректные данные: {exc}"
    return "Произошла внутренняя ошибка. Попробуйте позже."
