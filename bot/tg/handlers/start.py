"""Entry point handler — /start command and main menu navigation."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from services.user_store import user_store
from tg.menus.keyboards import main_menu
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

_WELCOME = (
    "👋 <b>Добро пожаловать в торговый терминал!</b>\n\n"
    "Управляйте инвестициями, отслеживайте портфель и\n"
    "получайте аналитику прямо в Telegram.\n\n"
    "Выберите раздел:"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return

    user = update.effective_user
    chat_id = update.effective_chat.id

    if not rate_limiter.is_allowed(chat_id):
        await update.message.reply_text("⏳ Слишком много запросов. Подождите немного.")
        return

    user_store.touch(chat_id, username=user.username if user else None)

    await update.message.reply_html(_WELCOME, reply_markup=main_menu())


async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return

    if not rate_limiter.is_allowed(query.from_user.id):
        await query.answer("⏳ Слишком много запросов", show_alert=True)
        return

    await query.answer()
    await query.edit_message_text(
        _WELCOME,
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
