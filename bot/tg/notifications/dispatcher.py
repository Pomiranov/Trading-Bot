"""Push notification dispatcher — sends alerts to subscribed users."""
from __future__ import annotations

import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from config import config
from services.user_store import user_store

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def set_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


async def _send(chat_id: int, text: str) -> None:
    if _bot is None:
        return
    try:
        await _bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except TelegramError as exc:
        logger.error("Notification failed to %s: %s", chat_id, exc)


async def notify(notif_type: str, text: str) -> None:
    """Send a notification to all users subscribed to notif_type."""
    recipients = user_store.get_users_with_notification(notif_type)
    if not recipients and config.telegram.chat_id:
        try:
            recipients = [int(config.telegram.chat_id)]
        except (ValueError, TypeError):
            pass
    for chat_id in recipients:
        await _send(chat_id, text)


async def notify_order_fill(ticker: str, direction: str, quantity: int, price: float) -> None:
    dir_icon = "🟢" if direction.upper() == "BUY" else "🔴"
    text = (
        f"{dir_icon} <b>Заявка исполнена</b>\n"
        f"{ticker} {direction} {quantity} лотов @ {price:.2f}"
    )
    await notify("order_fill", text)


async def notify_new_signal(ticker: str, action: str, score: float) -> None:
    action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(action, "⚪")
    text = (
        f"📡 <b>Новый сигнал</b>\n"
        f"{action_emoji} {ticker}: <b>{action}</b> (score: {score:.2f})"
    )
    await notify("new_signal", text)


async def notify_trade_open(ticker: str, price: float, lots: int, stop: float) -> None:
    text = (
        f"🟢 <b>Покупка {ticker}</b>\n"
        f"Цена: {price:.2f} ₽ | Лотов: {lots}\n"
        f"Стоп: {stop:.2f} ₽"
    )
    await notify("order_fill", text)


async def notify_trade_close(ticker: str, price: float, pnl: float) -> None:
    pnl_icon = "🟢" if pnl >= 0 else "🔴"
    text = (
        f"{pnl_icon} <b>Продажа {ticker}</b>\n"
        f"Цена: {price:.2f} ₽ | PnL: {pnl:+.2f} ₽"
    )
    await notify("order_fill", text)


async def notify_api_error(broker: str, error: str) -> None:
    text = f"🔴 <b>Ошибка API {broker}</b>\n{error}"
    await notify("api_error", text)


async def notify_risk_limit(reason: str) -> None:
    text = f"⚠️ <b>Лимит риска</b>\n{reason}"
    await notify("risk_limit", text)


async def notify_bot_started() -> None:
    await notify("bot_started", "▶ <b>Торговый бот запущен</b>")


async def notify_bot_stopped() -> None:
    await notify("bot_stopped", "⏹ <b>Торговый бот остановлен</b>")
