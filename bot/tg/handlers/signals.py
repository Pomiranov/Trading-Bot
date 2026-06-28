"""Signals handler — live and historical trading signals."""
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
from data.loader import loader
from signals.indicators import indicator_engine
from signals.rules_engine import rules_engine, Action
from tg.formatters.numbers import fmt_float, fmt_pct
from tg.menus.keyboards import signals_keyboard, CANCEL_KB
from tg.fsm.states import SignalStates
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)

_ACTION_EMOJI = {
    "BUY": "🟢",
    "SELL": "🔴",
    "HOLD": "⚪",
}


def _build_signal_text(ticker: str) -> str:
    try:
        df = loader.get_candles(ticker, interval="1h")
        if df.empty:
            return f"⚠️ Нет данных для <b>{ticker}</b>"

        ind = indicator_engine.latest(df)
        sig = rules_engine.evaluate(ind)

        action_emoji = _ACTION_EMOJI.get(sig.action.value, "⚪")
        triggered = "\n".join(
            f"  • {r.name} (+{r.weight})"
            for r in sig.triggered_rules
        ) or "  — нет"

        return (
            f"📡 <b>Сигнал: {ticker}</b>\n"
            f"─────────────────────────\n"
            f"{action_emoji} <b>Рекомендация: {sig.action.value}</b>\n\n"
            f"📊 Score покупки:  {fmt_float(sig.buy_score)}\n"
            f"📉 Score продажи: {fmt_float(sig.sell_score)}\n\n"
            f"📈 Индикаторы:\n"
            f"  RSI:        {fmt_float(ind.rsi)}\n"
            f"  MACD hist:  {fmt_float(ind.macd_hist)}\n"
            f"  ADX:        {fmt_float(ind.adx)}\n"
            f"  ATR:        {fmt_float(ind.atr)}\n"
            f"  EMA fast:   {fmt_float(ind.ema_fast)}\n"
            f"  EMA slow:   {fmt_float(ind.ema_slow)}\n"
            f"  BB%:        {fmt_pct(ind.bb_pct * 100 if ind.bb_pct else None)}\n"
            f"  Close:      {fmt_float(ind.close)}\n\n"
            f"✅ Сработавшие правила:\n{triggered}"
        )
    except Exception as exc:
        logger.error("Signal error for %s: %s", ticker, exc)
        return f"❌ Ошибка расчёта сигнала для <b>{ticker}</b>:\n{exc}"


def _build_all_signals_text() -> str:
    lines = ["📡 <b>Актуальные сигналы</b>\n─────────────────────────"]
    for ticker in config.tickers:
        try:
            df = loader.get_candles(ticker, interval="1h")
            if df.empty:
                lines.append(f"⚪ <b>{ticker}</b>: нет данных")
                continue
            ind = indicator_engine.latest(df)
            sig = rules_engine.evaluate(ind)
            emoji = _ACTION_EMOJI.get(sig.action.value, "⚪")
            lines.append(
                f"{emoji} <b>{ticker}</b>: {sig.action.value} "
                f"(B:{fmt_float(sig.buy_score)} S:{fmt_float(sig.sell_score)})"
            )
        except Exception as exc:
            lines.append(f"⚠️ <b>{ticker}</b>: ошибка")
    return "\n".join(lines)


async def _render_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    text = _build_all_signals_text()
    kb = signals_keyboard("all")

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


async def cb_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_all(update, context)


async def cb_signals_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_all(update, context)


async def cb_signals_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _render_all(update, context)


async def cb_signal_query_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text(
        "📡 <b>Запрос сигнала</b>\n\nВведите тикер инструмента:\n<i>Например: SBER</i>",
        reply_markup=CANCEL_KB,
        parse_mode="HTML",
    )
    return SignalStates.ENTER_TICKER


async def signal_enter_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticker = update.message.text.strip().upper()
    text = _build_signal_text(ticker)
    kb = signals_keyboard()
    await update.message.reply_html(text, reply_markup=kb)
    return ConversationHandler.END


async def signal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END


def build_signal_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_signal_query_start, pattern=r"^sig_query$"),
        ],
        states={
            SignalStates.ENTER_TICKER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, signal_enter_ticker),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(signal_cancel, pattern=r"^m_main$"),
            CommandHandler("cancel", signal_cancel),
        ],
        allow_reentry=True,
        name="signal_flow",
    )


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_auth(update, context):
        return
    if not context.args:
        await update.message.reply_html(
            "📡 Укажите тикер: <code>/signal SBER</code>",
        )
        return
    ticker = context.args[0].upper()
    text = _build_signal_text(ticker)
    await update.message.reply_html(text)
