"""Settings handler — broker tokens, risk limits, polling interval via FSM."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from config import config
from security.credential_store import persist_credential
from services.tinkoff.portfolio import invalidate_portfolio_cache
from services.tinkoff.statistics import invalidate as invalidate_stats_cache
from services.statistics_service import invalidate as invalidate_full_stats
from broker.registry import broker_registry
from tg.fsm.states import SettingsStates
from tg.menus.keyboards import (
    settings_keyboard,
    broker_settings_keyboard,
    tinkoff_settings_keyboard,
    CANCEL_KB,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from tg.middlewares.auth import require_auth

logger = logging.getLogger(__name__)

def _save_env(key: str, value: str, *, actor_id: str | None = None) -> None:
    persist_credential(
        key,
        value,
        config,
        actor_type="telegram",
        actor_id=actor_id,
    )


async def cb_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()
    await query.edit_message_text(
        "⚙ <b>Настройки</b>",
        reply_markup=settings_keyboard(),
        parse_mode="HTML",
    )


async def cb_settings_brokers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    infos = [await a.get_info() for a in broker_registry.all()]
    await query.edit_message_text(
        "🔗 <b>Брокеры</b>\n\nВыберите брокера для настройки:",
        reply_markup=broker_settings_keyboard(infos),
        parse_mode="HTML",
    )


async def cb_settings_broker_tinkoff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()
    has_token = bool(config.tinkoff.token)
    has_account = bool(config.tinkoff.account_id)
    mode = "SANDBOX" if config.tinkoff.sandbox else "LIVE"
    await query.edit_message_text(
        f"🏦 <b>Т-Банк (Tinkoff Invest)</b>\n\n"
        f"Режим: <b>{mode}</b>\n"
        f"Токен: {'✅ настроен' if has_token else '❌ не настроен'}\n"
        f"ID счёта: {'✅ настроен' if has_account else '❌ не настроен'}\n\n"
        f"<i>Токен получите в приложении Т-Инвестиции\n"
        f"Настройки → Безопасность → API-токен</i>",
        reply_markup=tinkoff_settings_keyboard(has_token, has_account),
        parse_mode="HTML",
    )


async def cb_settings_broker_finam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀ Брокеры", callback_data="set_brokers"),
    ]])
    await query.edit_message_text(
        "🏦 <b>Finam</b>\n\n"
        "Интеграция с Finam будет доступна в следующем обновлении.\n\n"
        "API: Finam Trade API v1\n"
        "Документация: finamweb.github.io/trade-api-docs",
        reply_markup=kb,
        parse_mode="HTML",
    )


async def cb_enter_tinkoff_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return ConversationHandler.END
    await query.answer()
    context.user_data["settings_field"] = "TINKOFF_TOKEN"
    await query.edit_message_text(
        "🔑 <b>Введите API токен Tinkoff Invest</b>\n\n"
        "Токен начинается с <code>t.</code>\n"
        "<i>Сообщение будет удалено после сохранения.</i>",
        reply_markup=CANCEL_KB,
        parse_mode="HTML",
    )
    return SettingsStates.ENTER_TINKOFF_TOKEN


async def cb_enter_tinkoff_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return ConversationHandler.END
    await query.answer()
    context.user_data["settings_field"] = "TINKOFF_ACCOUNT_ID"
    await query.edit_message_text(
        "🏦 <b>Введите ID счёта Tinkoff Invest</b>\n\n"
        "Найдите его в приложении: Профиль → Счета\n"
        "<i>Сообщение будет удалено после сохранения.</i>",
        reply_markup=CANCEL_KB,
        parse_mode="HTML",
    )
    return SettingsStates.ENTER_TINKOFF_ACCOUNT


async def _save_credential(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_auth(update, context):
        return ConversationHandler.END

    field = context.user_data.get("settings_field", "")
    value = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    if field not in ("TINKOFF_TOKEN", "TINKOFF_ACCOUNT_ID"):
        return ConversationHandler.END

    if not value:
        await update.effective_chat.send_message(
            "⚠️ Значение не может быть пустым.",
            reply_markup=CANCEL_KB,
        )
        return ConversationHandler.END

    actor = str(update.effective_user.id) if update.effective_user else None
    _save_env(field, value, actor_id=actor)

    invalidate_portfolio_cache()
    invalidate_stats_cache()
    invalidate_full_stats()

    logger.info("Credential saved: key=%s", field)
    await update.effective_chat.send_message(
        f"✅ <b>{field}</b> сохранён.",
        parse_mode="HTML",
        reply_markup=tinkoff_settings_keyboard(
            has_token=bool(config.tinkoff.token),
            has_account=bool(config.tinkoff.account_id),
        ),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def settings_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    return ConversationHandler.END


def build_settings_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_enter_tinkoff_token, pattern=r"^set_tinkoff_token$"),
            CallbackQueryHandler(cb_enter_tinkoff_account, pattern=r"^set_tinkoff_account$"),
        ],
        states={
            SettingsStates.ENTER_TINKOFF_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _save_credential),
            ],
            SettingsStates.ENTER_TINKOFF_ACCOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _save_credential),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(settings_cancel, pattern=r"^m_main$"),
            CommandHandler("cancel", settings_cancel),
        ],
        allow_reentry=True,
        name="settings_flow",
    )
