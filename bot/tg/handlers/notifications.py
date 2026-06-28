"""Notification settings handler — per-user toggle for each notification type."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.user_store import user_store
from tg.menus.keyboards import notifications_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return

    if query:
        await query.answer()

    chat_id = update.effective_chat.id
    prefs = user_store.get(chat_id)

    on_count = sum(
        1 for key in vars(prefs.notifications)
        if getattr(prefs.notifications, key, False)
    )

    text = (
        f"🔔 <b>Уведомления</b>\n"
        f"─────────────────────────\n"
        f"Активно: {on_count} из {len(vars(prefs.notifications))}\n\n"
        "Нажмите на уведомление чтобы включить/выключить:"
    )
    kb = notifications_keyboard(prefs.notifications)

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_notification_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return

    notif_key = query.data.replace("notif_toggle_", "")
    chat_id = update.effective_chat.id

    try:
        new_state = user_store.toggle_notification(chat_id, notif_key)
        state_label = "включено 🔔" if new_state else "выключено 🔕"
        await query.answer(f"{notif_key}: {state_label}")
    except ValueError as exc:
        logger.error("Toggle notification error: %s", exc)
        await query.answer("⚠️ Ошибка", show_alert=True)
        return

    await _render(update, context)
