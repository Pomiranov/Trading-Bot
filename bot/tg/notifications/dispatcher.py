"""Push notification dispatcher — sends alerts to subscribed users."""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from telegram import Bot
from telegram.error import TelegramError

from config import config
from services.user_store import user_store

logger = logging.getLogger(__name__)


def _send_telegram_sync(chat_id: int, text: str) -> None:
    """Thread-safe synchronous Telegram message via Bot API (no asyncio required)."""
    token = config.telegram.token
    if not token or not chat_id:
        return
    try:
        import requests as req
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=3,
        )
    except Exception as exc:
        logger.debug("sync telegram notify failed: %s", exc)


def _get_sync_recipients() -> list[int]:
    """Return list of chat IDs for synchronous (thread) notifications."""
    recipients = user_store.get_users_with_notification("order_fill")
    if not recipients and config.telegram.chat_id:
        try:
            recipients = [int(config.telegram.chat_id)]
        except (ValueError, TypeError):
            pass
    return recipients


def notify_paper_trade_open_sync(
    ticker: str,
    direction: str,
    price: float,
    quantity,
    probability: Optional[float] = None,
    entry_reason: str = "",
) -> None:
    """Send paper trade open notification from any thread (no asyncio)."""
    dir_icon = "🟢" if direction.lower() == "long" else "🔴"
    dir_label = "LONG" if direction.lower() == "long" else "SHORT"
    prob_str = f"  Уверенность: <b>{probability:.0f}%</b>\n" if probability is not None else ""
    reason_str = f"  Причина: <i>{entry_reason}</i>\n" if entry_reason else ""
    text = (
        f"{dir_icon} <b>Paper Trade открыт</b>\n"
        f"<b>{ticker}</b> {dir_label}\n"
        f"  Цена входа: <code>{price:.4f}</code>\n"
        f"  Количество: <code>{quantity}</code>\n"
        f"{prob_str}{reason_str}"
        f"<i>Paper Trading · Виртуальный счёт</i>"
    )
    for chat_id in _get_sync_recipients():
        _send_telegram_sync(chat_id, text)


def notify_paper_trade_close_sync(
    ticker: str,
    pnl: float,
    pnl_pct: float = 0.0,
    reason: str = "manual",
    exit_price: Optional[float] = None,
) -> None:
    """Send paper trade close notification from any thread (no asyncio)."""
    icon = "✅" if pnl >= 0 else "❌"
    pnl_sign = "+" if pnl >= 0 else ""
    reason_labels = {
        "SL_HIT": "Стоп-лосс",
        "TP_HIT": "Тейк-профит",
        "manual": "Ручное закрытие",
        "partial_full": "Полное закрытие",
    }
    reason_label = reason_labels.get(reason, reason)
    price_str = f"  Цена выхода: <code>{exit_price:.4f}</code>\n" if exit_price else ""
    text = (
        f"{icon} <b>Paper Trade закрыт</b>\n"
        f"<b>{ticker}</b>\n"
        f"{price_str}"
        f"  P&amp;L: <code>{pnl_sign}{pnl:.2f} ₽</code> ({pnl_sign}{pnl_pct:.2f}%)\n"
        f"  Причина: <i>{reason_label}</i>\n"
        f"<i>Paper Trading · Виртуальный счёт</i>"
    )
    for chat_id in _get_sync_recipients():
        _send_telegram_sync(chat_id, text)


def _internal_headers() -> dict:
    import os
    token = os.getenv("QF_INTERNAL_TOKEN", "")
    return {"X-Internal-Token": token} if token else {}


async def _push_sse(event_type: str, data: dict) -> None:
    """Push event to dashboard SSE hub via HTTP (fire-and-forget)."""
    try:
        url = f"http://127.0.0.1:{config.dashboard.port}/api/internal/push"
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.post(url, json={"event_type": event_type, **data}, headers=_internal_headers())
    except Exception:
        pass  # dashboard may not be running

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
    await _push_sse("trade_executed", {
        "action": "BUY", "ticker": ticker, "price": price, "lots": lots, "stop": stop,
    })


async def notify_trade_close(ticker: str, price: float, pnl: float) -> None:
    pnl_icon = "🟢" if pnl >= 0 else "🔴"
    text = (
        f"{pnl_icon} <b>Продажа {ticker}</b>\n"
        f"Цена: {price:.2f} ₽ | PnL: {pnl:+.2f} ₽"
    )
    await notify("order_fill", text)
    await _push_sse("trade_executed", {
        "action": "SELL", "ticker": ticker, "price": price, "pnl": pnl,
    })
    await _push_sse("portfolio_updated", {})


async def notify_api_error(broker: str, error: str) -> None:
    text = f"🔴 <b>Ошибка API {broker}</b>\n{error}"
    await notify("api_error", text)


async def notify_risk_limit(reason: str) -> None:
    text = f"⚠️ <b>Лимит риска</b>\n{reason}"
    await notify("risk_limit", text)


async def notify_bot_started() -> None:
    await notify("bot_started", "▶ <b>Торговый бот запущен</b>\n<i>Paper Trading Engine активирован</i>")


async def notify_bot_stopped() -> None:
    await notify("bot_stopped", "⏹ <b>Торговый бот остановлен</b>\n<i>Все движки выключены</i>")


async def notify_paper_engine_started() -> None:
    await notify("bot_started", "▶ <b>Paper Engine запущен</b>\n<i>Автоматическая генерация сигналов активна</i>")


async def notify_paper_engine_stopped() -> None:
    await notify("bot_stopped", "⏹ <b>Paper Engine остановлен</b>")


async def notify_signals_new(signals: list) -> None:
    if not signals:
        return
    lines = [f"📡 <b>Новые сигналы ({len(signals)})</b>"]
    for sig in signals[:5]:
        icon = "🟢" if sig.signal_type.upper() in ("LONG", "BUY") else "🔴"
        meta = sig.metadata or {}
        strategy = meta.get("strategy", "—")
        lines.append(
            f"{icon} <b>{sig.asset}</b> {sig.signal_type} "
            f"| {strategy} "
            f"| Confidence: {sig.probability_pct:.1f}%"
        )
    if len(signals) > 5:
        lines.append(f"<i>… и ещё {len(signals) - 5}</i>")
    await notify("new_signal", "\n".join(lines))


def notify_signals_generated_sync(signals: list) -> None:
    """Send signals notification from any thread (no asyncio)."""
    if not signals:
        return
    lines = [f"📡 <b>Сигналы сгенерированы: {len(signals)}</b>"]
    for sig in signals[:3]:
        icon = "🟢" if sig.signal_type.upper() in ("LONG", "BUY") else "🔴"
        meta = sig.metadata or {} if hasattr(sig, "metadata") else {}
        strategy = meta.get("strategy", "—") if isinstance(meta, dict) else "—"
        lines.append(
            f"{icon} <b>{sig.asset}</b> {sig.signal_type} "
            f"| {strategy} | {sig.probability_pct:.1f}%"
        )
    if len(signals) > 3:
        lines.append(f"<i>… и ещё {len(signals) - 3}</i>")
    text = "\n".join(lines)
    for chat_id in _get_sync_recipients():
        _send_telegram_sync(chat_id, text)


def notify_risk_limit_sync(reason: str) -> None:
    """Send risk limit notification from any thread."""
    text = f"⚠️ <b>Лимит риска — сигнал отклонён</b>\n<i>{reason}</i>"
    for chat_id in _get_sync_recipients():
        _send_telegram_sync(chat_id, text)


def notify_daily_loss_limit_sync(daily_pnl: float, limit: float) -> None:
    """Send daily loss limit notification from any thread."""
    text = (
        f"🔴 <b>Дневной лимит убытков достигнут</b>\n"
        f"P&L за день: <code>{daily_pnl:+.2f} ₽</code>\n"
        f"Лимит: <code>-{limit:.2f} ₽</code>\n"
        f"<i>Автоматическая торговля приостановлена</i>"
    )
    for chat_id in _get_sync_recipients():
        _send_telegram_sync(chat_id, text)


async def notify_system_error(component: str, error: str) -> None:
    text = (
        f"🔴 <b>Ошибка системы: {component}</b>\n"
        f"<code>{error[:200]}</code>"
    )
    await notify("api_error", text)
