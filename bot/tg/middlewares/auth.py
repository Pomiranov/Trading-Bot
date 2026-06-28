"""Chat ID whitelist authentication middleware."""
from __future__ import annotations

import logging
from typing import Any, Callable

from telegram import Update
from telegram.ext import BaseHandler, ContextTypes

from config import config

logger = logging.getLogger(__name__)


def _allowed_ids() -> set[int]:
    ids: set[int] = set()
    if config.telegram.chat_id:
        try:
            ids.add(int(config.telegram.chat_id))
        except ValueError:
            pass
    for raw in getattr(config.telegram, "allowed_chat_ids", []):
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            pass
    return ids


class AuthMiddleware(BaseHandler):
    """Drops updates from unauthorized chat IDs before they reach any handler."""

    def __init__(self) -> None:
        super().__init__(callback=self._noop)

    @staticmethod
    async def _noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        pass

    def check_update(self, update: object) -> bool:
        return False


async def require_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Call this at the top of every handler that needs to be protected.
    Returns True if the user is authorized, False if the update was rejected.
    """
    if not isinstance(update, Update):
        return False

    chat_id: int | None = None
    if update.effective_chat:
        chat_id = update.effective_chat.id
    elif update.effective_user:
        chat_id = update.effective_user.id

    if chat_id is None:
        return False

    allowed = _allowed_ids()
    if not allowed or chat_id in allowed:
        return True

    logger.warning("Unauthorized access attempt from chat_id=%s", chat_id)
    if update.effective_message:
        await update.effective_message.reply_text(
            "⛔ Доступ запрещён. Этот бот работает в приватном режиме."
        )
    elif update.callback_query:
        await update.callback_query.answer("⛔ Доступ запрещён", show_alert=True)
    return False
