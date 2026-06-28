"""Statistics handler — full trading analytics."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.statistics_service import compute as compute_stats, invalidate
from tg.formatters.messages import build_statistics
from tg.menus.keyboards import statistics_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)


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

    db_engine = context.bot_data.get("db_engine")
    stats = compute_stats(db_engine)
    text = build_statistics(stats)
    kb = statistics_keyboard()

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_statistics_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    invalidate()
    await _render(update, context)


async def cmd_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)
