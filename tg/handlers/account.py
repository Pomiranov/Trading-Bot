"""Account handler — user profile, connected accounts, activity."""
from __future__ import annotations

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from broker.registry import broker_registry
from services.user_store import user_store
from tg.menus.keyboards import account_keyboard, InlineKeyboardMarkup, InlineKeyboardButton
from tg.middlewares.auth import require_auth


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return

    if query:
        await query.answer()

    user = update.effective_user
    chat_id = update.effective_chat.id
    prefs = user_store.get(chat_id)

    username_line = f"@{user.username}" if user and user.username else "—"
    registered = prefs.registered_at[:10] if prefs.registered_at else "—"
    last_seen = prefs.last_seen[:16].replace("T", " ") if prefs.last_seen else "—"

    broker_lines = []
    for adapter in broker_registry.all():
        info = await adapter.get_info()
        icon = "🟢" if info.is_connected else ("🟡" if info.is_configured else "⚪")
        broker_lines.append(f"  {icon} {info.name}")

    text = (
        f"👤 <b>Аккаунт</b>\n"
        f"─────────────────────────\n"
        f"Имя:         {user.full_name if user else '—'}\n"
        f"Username:    {username_line}\n"
        f"Chat ID:     <code>{chat_id}</code>\n"
        f"Язык:        {prefs.language.upper()}\n"
        f"Часовой пояс: {prefs.timezone}\n"
        f"Брокер по умолчанию: {prefs.default_broker}\n"
        f"─────────────────────────\n"
        f"📅 Зарегистрирован: {registered}\n"
        f"🕐 Последняя активность: {last_seen}\n"
        f"─────────────────────────\n"
        f"🔗 <b>Подключённые брокеры:</b>\n"
        + "\n".join(broker_lines)
    )

    if query:
        await query.edit_message_text(text, reply_markup=account_keyboard(), parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=account_keyboard())


async def cb_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_account_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    lines = ["🔗 <b>Подключённые счета</b>\n─────────────────────────"]
    for adapter in broker_registry.all():
        info = await adapter.get_info()
        icon = "🟢" if info.is_connected else ("🟡" if info.is_configured else "⚪")
        lines.append(f"\n{icon} <b>{info.name}</b>")
        lines.append(f"  {info.description}")
        if info.error:
            lines.append(f"  ⚠ {info.error}")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀ Аккаунт", callback_data="m_account"),
        InlineKeyboardButton("🏠 Главная", callback_data="m_main"),
    ]])
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=kb,
        parse_mode="HTML",
    )
