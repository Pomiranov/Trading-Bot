"""Positions handler — paginated list and per-position detail."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import broker_service
from tg.formatters.messages import build_positions_page, build_position_detail
from tg.menus.keyboards import positions_keyboard, position_detail_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"
_PER_PAGE = 5


async def _render_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
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
        positions = await broker_service.get_all_positions()
    except Exception as exc:
        logger.error("Positions fetch error: %s", exc)
        positions = []

    total_pages = max(1, (len(positions) + _PER_PAGE - 1) // _PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    text = build_positions_page(positions, page=page, per_page=_PER_PAGE)
    kb = positions_keyboard(page=page, total_pages=total_pages)

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_page(update, context, page=0)


async def cb_positions_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        page = int(query.data.split("_")[-1])
    except (IndexError, ValueError):
        page = 0
    await _render_page(update, context, page=page)


async def cb_positions_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    page = context.user_data.get("positions_page", 0)
    await _render_page(update, context, page=page)


async def cb_position_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    parts = query.data.split("_")
    ticker = parts[-1] if parts else ""

    try:
        positions = await broker_service.get_all_positions()
        pos = next((p for p in positions if p.ticker == ticker), None)
    except Exception as exc:
        logger.error("Position detail error: %s", exc)
        pos = None

    if pos is None:
        await query.edit_message_text(
            f"⚠️ Позиция {ticker} не найдена",
            reply_markup=positions_keyboard(),
            parse_mode="HTML",
        )
        return

    text = build_position_detail(pos)
    kb = position_detail_keyboard(pos.ticker, pos.broker_id)
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_page(update, context, page=0)
