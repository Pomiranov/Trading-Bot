"""Operations handler — paginated transaction history."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from services import broker_service
from tg.formatters.messages import build_operations
from tg.menus.keyboards import operations_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"
_PER_PAGE = 10
_DEFAULT_DAYS = 30


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
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

    from_dt = datetime.now(timezone.utc) - timedelta(days=_DEFAULT_DAYS)

    try:
        operations = await broker_service.get_broker_operations(
            _BROKER_ID,
            from_dt=from_dt,
            limit=100,
        )
    except Exception as exc:
        logger.error("Operations fetch error: %s", exc)
        operations = []

    total_pages = max(1, (len(operations) + _PER_PAGE - 1) // _PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    text = build_operations(operations, page=page, per_page=_PER_PAGE)
    kb = operations_keyboard(page=page, total_pages=total_pages)

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_operations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context, page=0)


async def cb_operations_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        page = int(query.data.split("_")[-1])
    except (IndexError, ValueError):
        page = 0
    await _render(update, context, page=page)


async def cb_operations_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    page = context.user_data.get("ops_page", 0)
    await _render(update, context, page=page)


async def cmd_operations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context, page=0)
