"""Balance handler — multi-currency balance overview."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import broker_service
from tg.formatters.messages import build_balance
from tg.menus.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"

_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔄 Обновить", callback_data="bal_refresh"),
        InlineKeyboardButton("🏠 Главная",  callback_data="m_main"),
    ],
])


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return

    if not rate_limiter.is_allowed(update.effective_user.id):
        if query:
            await query.answer("⏳ Подождите", show_alert=True)
        return

    if query:
        await query.answer()

    try:
        balances = await broker_service.get_broker_balance(_BROKER_ID)
    except Exception as exc:
        logger.error("Balance fetch error: %s", exc)
        balances = []

    text = build_balance(balances)

    if query:
        await query.edit_message_text(text, reply_markup=_KB, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=_KB)


async def cb_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_balance_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)
