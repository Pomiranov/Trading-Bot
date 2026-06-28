"""Trading bot management handler — start/pause/stop/status/logs."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.bot_engine import BotStatus, trading_engine
from tg.formatters.messages import build_trading_bot_status
from tg.menus.keyboards import trading_bot_keyboard
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

    summary = trading_engine.summary()
    logs = trading_engine.state.recent_logs(10)
    text = build_trading_bot_status(summary, logs)
    kb = trading_bot_keyboard(summary["status"])

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_trading_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    if trading_engine.is_running():
        await query.answer("Бот уже запущен", show_alert=True)
        return

    trading_engine.start()
    logger.info("Trading bot started via Telegram")
    await _render(update, context)


async def cb_bot_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    if not trading_engine.is_running():
        await query.answer("Бот не запущен", show_alert=True)
        return

    trading_engine.pause()
    logger.info("Trading bot paused via Telegram")
    await _render(update, context)


async def cb_bot_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()
    trading_engine.resume()
    logger.info("Trading bot resumed via Telegram")
    await _render(update, context)


async def cb_bot_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer("⏹ Остановка бота…")
    trading_engine.stop()
    logger.info("Trading bot stopped via Telegram")
    await _render(update, context)


async def cb_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)


async def cb_bot_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    from tg.menus.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    logs = trading_engine.state.recent_logs(20)
    if not logs:
        text = "📜 <b>Логи бота</b>\n\n<i>Нет записей</i>"
    else:
        entries = "\n".join(f"<code>{log}</code>" for log in logs)
        text = f"📜 <b>Логи бота (последние 20)</b>\n\n{entries}"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="bot_logs"),
            InlineKeyboardButton("◀ Назад",    callback_data="m_trading_bot"),
        ],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)
