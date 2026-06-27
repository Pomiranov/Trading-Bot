"""Orders handler — active/filled/cancelled orders with cancel action."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from broker.base import OrderStatus
from services import broker_service
from services.trading_service import cancel_order
from tg.formatters.messages import build_orders
from tg.menus.keyboards import orders_filter_keyboard, order_action_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"

_FILTER_MAP = {
    "active": ([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED], "Активные"),
    "filled": ([OrderStatus.FILLED], "Исполненные"),
    "cancelled": ([OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED], "Отменённые"),
}


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_key: str = "active") -> None:
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

    status_filter, label = _FILTER_MAP.get(filter_key, _FILTER_MAP["active"])

    try:
        orders = await broker_service.get_broker_orders(_BROKER_ID, status_filter=status_filter)
    except Exception as exc:
        logger.error("Orders fetch error: %s", exc)
        orders = []

    text = build_orders(orders, label)
    kb = orders_filter_keyboard(active_filter=filter_key)

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context, "active")


async def cb_orders_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    filter_key = query.data.replace("ord_filter_", "")
    context.user_data["orders_filter"] = filter_key
    await _render(update, context, filter_key)


async def cb_orders_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    filter_key = context.user_data.get("orders_filter", "active")
    await _render(update, context, filter_key)


async def cb_order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 4:
        await query.answer("⚠️ Некорректный запрос", show_alert=True)
        return

    broker_id = parts[2]
    order_id = "_".join(parts[3:])

    result = await cancel_order(broker_id, order_id)
    if result.success:
        await query.edit_message_text(
            "✅ Заявка успешно отменена.",
            reply_markup=orders_filter_keyboard(),
            parse_mode="HTML",
        )
    else:
        await query.answer(f"⚠️ {result.error}", show_alert=True)


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context, "active")
