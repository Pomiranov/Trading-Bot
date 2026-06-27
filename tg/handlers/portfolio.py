"""Portfolio handler — full portfolio view with asset breakdown."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import broker_service
from tg.formatters.messages import build_portfolio
from tg.menus.keyboards import portfolio_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"


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
        portfolio = await broker_service.get_broker_portfolio(_BROKER_ID)
        text = build_portfolio(portfolio)
        kb = portfolio_keyboard(has_positions=bool(portfolio.positions))
    except Exception as exc:
        logger.error("Portfolio render error: %s", exc)
        text = f"⚠️ Ошибка загрузки портфеля:\n{exc}"
        kb = portfolio_keyboard(has_positions=False)

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_portfolio_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)
