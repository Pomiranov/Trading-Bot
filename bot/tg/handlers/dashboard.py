"""Dashboard handler — real-time portfolio overview."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from broker.base import BrokerInfo
from broker.registry import broker_registry
from services import broker_service
from services.bot_engine import trading_engine
from services.statistics_service import compute as compute_stats
from tg.formatters.messages import build_dashboard
from tg.menus.keyboards import dashboard_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)

_BROKER_ID = "tinkoff"


async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return

    user_id = update.effective_user.id
    if not rate_limiter.is_allowed(user_id):
        if query:
            await query.answer("⏳ Подождите", show_alert=True)
        return

    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    stats = compute_stats(db_engine) if db_engine else None

    portfolio = None
    broker_info: BrokerInfo = await broker_registry.get(_BROKER_ID).get_info()
    if broker_info.is_connected:
        try:
            portfolio = await broker_service.get_broker_portfolio(_BROKER_ID)
        except Exception as exc:
            logger.warning("Dashboard portfolio error: %s", exc)

    text = build_dashboard(
        portfolio=portfolio,
        stats=stats,
        broker_info=broker_info,
        bot_status=trading_engine.status,
    )

    kb = dashboard_keyboard(_BROKER_ID)
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_dashboard(update, context)


async def cb_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_dashboard(update, context)


async def cb_dashboard_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_dashboard(update, context)
