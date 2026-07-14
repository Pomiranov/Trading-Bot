"""Trading bot management handler — start/pause/stop/status/logs."""
from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from services.bot_engine import BotStatus, trading_engine
from services.paper_auto_engine import paper_auto_engine
from tg.formatters.messages import build_trading_bot_status
from tg.menus.keyboards import trading_bot_keyboard
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)


def _build_auto_trading_status_text() -> str:
    """Build a comprehensive auto trading status message."""
    from services.bot_engine import trading_engine
    from engine.paper_engine import paper_engine
    from risk.risk_manager import risk_manager

    te_summary = trading_engine.summary()
    pe_status = paper_engine.status()
    te_status = te_summary.get("status", "STOPPED")
    pe_running = pe_status.get("running", False)

    te_icon = "🟢" if te_status == "RUNNING" else ("⏸" if te_status == "PAUSED" else "⏹")
    pe_icon = "🟢" if pe_running else "⏹"

    open_pos = len(risk_manager.open_positions)
    daily_pnl = risk_manager.daily_pnl

    from config import config
    max_pos = config.risk.max_open_positions
    max_loss_pct = config.risk.max_daily_loss_pct * 100

    _SEP = "─" * 28
    lines = [
        "🤖 <b>Auto Trading — Статус системы</b>",
        _SEP,
        f"<b>Trading Engine:</b>    {te_icon} {te_status}",
        f"<b>Paper Engine:</b>      {pe_icon} {'Работает' if pe_running else 'Остановлен'}",
        _SEP,
        "<b>📊 Сессия:</b>",
        f"  Циклов:    {te_summary.get('cycles_completed', 0)}",
        f"  Сделок:    {te_summary.get('trades_today', 0)}",
        f"  Ошибок:    {te_summary.get('errors_today', 0)}",
        _SEP,
        "<b>⚠ Лимиты риска:</b>",
        f"  Открытых позиций: {open_pos} / {max_pos}",
        f"  P&L сессии:       {daily_pnl:+.2f} ₽",
        f"  Макс. просадка:   -{max_loss_pct:.1f}%",
        f"  Интервал сигналов: {pe_status.get('signal_interval', 90)}с",
        f"  Мониторинг SL/TP: {pe_status.get('monitor_interval', 30)}с",
    ]

    if te_summary.get("last_cycle_at"):
        lines.append(f"  Последний цикл: {te_summary['last_cycle_at'][:16]}")
    if te_summary.get("started_at"):
        lines.append(f"  Запущен: {te_summary['started_at'][:16]}")

    return "\n".join(lines)


def _auto_trading_keyboard(te_status: str, pe_running: bool) -> InlineKeyboardMarkup:
    rows = []
    if te_status == "RUNNING":
        rows.append([
            InlineKeyboardButton("⏸ Пауза",      callback_data="bot_pause"),
            InlineKeyboardButton("⏹ Остановить", callback_data="bot_stop"),
        ])
    elif te_status == "PAUSED":
        rows.append([
            InlineKeyboardButton("▶ Продолжить", callback_data="bot_resume"),
            InlineKeyboardButton("⏹ Остановить", callback_data="bot_stop"),
        ])
    else:
        rows.append([InlineKeyboardButton("▶ Запустить Auto Trading", callback_data="bot_start")])

    rows.append([
        InlineKeyboardButton("📊 Статус",  callback_data="bot_status"),
        InlineKeyboardButton("📜 Логи",    callback_data="bot_logs"),
    ])
    rows.append([
        InlineKeyboardButton("📡 Сигналы",      callback_data="m_signals"),
        InlineKeyboardButton("📊 Paper Trading", callback_data="m_paper"),
    ])
    rows.append([InlineKeyboardButton("🏠 Главная", callback_data="m_main")])
    return InlineKeyboardMarkup(rows)


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return

    if query:
        await query.answer()

    try:
        from engine.paper_engine import paper_engine
        text = _build_auto_trading_status_text()
        te_status = trading_engine.summary()["status"]
        pe_running = paper_engine.is_running()
        kb = _auto_trading_keyboard(te_status, pe_running)

        # Append recent logs
        logs = trading_engine.state.recent_logs(8)
        if logs:
            _SEP = "─" * 28
            text += f"\n{_SEP}\n<b>📜 Последние события:</b>\n"
            text += "\n".join(f"  <code>{log}</code>" for log in logs)
    except Exception:
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
    paper_auto_engine.start()
    logger.info("Trading bot started via Telegram")
    try:
        from tg.notifications.dispatcher import notify_bot_started
        import asyncio
        asyncio.create_task(notify_bot_started())
    except Exception:
        pass
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
    paper_auto_engine.stop()
    logger.info("Trading bot paused via Telegram")
    await _render(update, context)


async def cb_bot_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()
    trading_engine.resume()
    paper_auto_engine.start()
    logger.info("Trading bot resumed via Telegram")
    await _render(update, context)


async def cb_bot_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer("⏹ Остановка бота…")
    trading_engine.stop()
    paper_auto_engine.stop()
    logger.info("Trading bot stopped via Telegram")
    try:
        from tg.notifications.dispatcher import notify_bot_stopped
        import asyncio
        asyncio.create_task(notify_bot_stopped())
    except Exception:
        pass
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
