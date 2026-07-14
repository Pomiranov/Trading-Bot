"""Quant Hunt Mini App handler — opens the game as Telegram Web App."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from config import config
from tg.middlewares.auth import require_auth

logger = logging.getLogger(__name__)


def _miniapp_url() -> str:
    return config.dashboard.miniapp_url


async def cmd_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send Quant Hunt mini app button as inline keyboard."""
    if not await require_auth(update, context):
        return

    url = _miniapp_url()
    text = (
        "🎮 <b>QUANT HUNT</b>\n\n"
        "Охотся за квантовыми токенами, собирай очки и покоряй рейтинг!\n\n"
        "• Common / Rare / Epic / Legendary квантумы\n"
        "• Рыночные события: Bull Run, Bear Market, Crash\n"
        "• Power-ups: Freeze, Magnet, Multiplier, Bomb\n"
        "• Прогнозирование Chart Direction\n"
        "• Ежедневные миссии и ачивки\n\n"
        f"<i>URL: {url}</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Открыть Quant Hunt", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])
    await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    url = _miniapp_url()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Открыть Quant Hunt", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("◀ Назад", callback_data="m_main")],
    ])
    await query.edit_message_text(
        "🎮 <b>QUANT HUNT</b> — торговая мини-игра\n\n"
        "Нажми кнопку чтобы открыть игру внутри Telegram:",
        reply_markup=kb,
        parse_mode="HTML",
    )


async def setup_menu_button(bot) -> None:
    """Set the persistent menu button to open Quant Hunt Mini App."""
    from telegram import MenuButtonWebApp, WebAppInfo
    url = _miniapp_url()
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🎮 Quant Hunt", web_app=WebAppInfo(url=url))
        )
        logger.info("Mini App menu button set: %s", url)
    except Exception as exc:
        logger.warning("Could not set menu button (needs HTTPS for real Telegram): %s", exc)
