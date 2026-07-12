"""Chat ID whitelist authentication middleware."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, BaseHandler, ContextTypes

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


def resolve_chat_id(update: Update) -> int | None:
    if update.effective_chat:
        return update.effective_chat.id
    if update.effective_user:
        return update.effective_user.id
    return None


def is_authorized(update: Update) -> bool:
    """
    Fail-closed: deny when whitelist is empty or chat_id is not listed.
    """
    chat_id = resolve_chat_id(update)
    if chat_id is None:
        return False

    allowed = _allowed_ids()
    if not allowed:
        logger.error(
            "Telegram auth misconfigured: TELEGRAM_CHAT_ID / TELEGRAM_ALLOWED_IDS not set"
        )
        return False

    return chat_id in allowed


async def reject_unauthorized(update: Update) -> None:
    chat_id = resolve_chat_id(update)
    logger.warning("Unauthorized access attempt from chat_id=%s", chat_id)
    if update.effective_message:
        await update.effective_message.reply_text(
            "⛔ Доступ запрещён. Этот бот работает в приватном режиме."
        )
    elif update.callback_query:
        await update.callback_query.answer("⛔ Доступ запрещён", show_alert=True)


async def require_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Call at the top of protected handlers.
    Returns True if authorized, False after sending a rejection message.
    """
    if not isinstance(update, Update):
        return False

    if is_authorized(update):
        return True

    await reject_unauthorized(update)
    return False


async def auth_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global gate (group -1): stop propagation for unauthorized updates."""
    if not is_authorized(update):
        await reject_unauthorized(update)
        raise ApplicationHandlerStop


class AuthMiddleware(BaseHandler):
    """Handler wrapper used as a global auth gate."""

    def __init__(self) -> None:
        super().__init__(callback=auth_gate)

    def check_update(self, update: object) -> bool:
        return isinstance(update, Update)