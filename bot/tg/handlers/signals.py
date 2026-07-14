"""Signals handler — live and historical trading signals via SignalsService."""
from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)

from tg.menus.keyboards import CANCEL_KB
from tg.fsm.states import SignalStates
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)

_SEP = "─" * 28
_TYPE_ICON = {"LONG": "🟢", "BUY": "🟢", "SHORT": "🔴", "SELL": "🔴", "HOLD": "⚪"}
_STATUS_ICON = {"new": "🔵", "executing": "🟡", "filled": "✅", "cancelled": "⛔", "expired": "⏰"}


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def _signals_list_kb(active_filter: str = "all") -> InlineKeyboardMarkup:
    def _lbl(key: str) -> str:
        labels = {"all": "Все", "new": "Новые", "long": "LONG", "short": "SHORT"}
        l = labels.get(key, key)
        return f"✅ {l}" if active_filter == key else l

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(_lbl("all"),   callback_data="sig_filter_all"),
            InlineKeyboardButton(_lbl("new"),   callback_data="sig_filter_new"),
        ],
        [
            InlineKeyboardButton(_lbl("long"),  callback_data="sig_filter_long"),
            InlineKeyboardButton(_lbl("short"), callback_data="sig_filter_short"),
        ],
        [
            InlineKeyboardButton("🔎 По тикеру",   callback_data="sig_query"),
            InlineKeyboardButton("🔄 Обновить",    callback_data="sig_refresh"),
        ],
        [
            InlineKeyboardButton("⚡ Генерировать", callback_data="sig_generate"),
            InlineKeyboardButton("🏠 Главная",     callback_data="m_main"),
        ],
    ])


def _signal_detail_kb(signal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Исполнить в Paper", callback_data=f"sig_exec_{signal_id}")],
        [
            InlineKeyboardButton("◀ Список", callback_data="m_signals"),
            InlineKeyboardButton("🏠 Главная", callback_data="m_main"),
        ],
    ])


# ── Форматирование ────────────────────────────────────────────────────────────

def _confidence_bar(confidence: float) -> str:
    filled = max(0, min(10, round(confidence * 10)))
    return "█" * filled + "░" * (10 - filled)


def _format_signal_card(sig) -> str:
    meta = sig.metadata or {}
    type_icon = _TYPE_ICON.get(sig.signal_type, "⚪")
    status_icon = _STATUS_ICON.get(sig.status, "🔵")

    confidence = meta.get("confidence", sig.probability_pct / 100)
    strategy = meta.get("strategy", sig.source or "—")
    entry_reason = meta.get("entry_reason", "—")
    triggered = meta.get("triggered", [])
    regime = meta.get("regime", "—")

    rsi = meta.get("rsi")
    adx = meta.get("adx")
    macd = meta.get("macd_hist")

    sl_str = f"{sig.stop_loss:.4f}" if sig.stop_loss else "—"
    tp_str = f"{sig.take_profit_1:.4f}" if sig.take_profit_1 else "—"
    tp2_str = f" / {sig.take_profit_2:.4f}" if sig.take_profit_2 else ""
    rr_str = f"{sig.risk_reward:.2f}" if sig.risk_reward else "—"

    risk_pct = reward_pct = None
    if sig.stop_loss and sig.entry_price:
        risk_pct = abs(sig.entry_price - sig.stop_loss) / sig.entry_price * 100
    if sig.take_profit_1 and sig.entry_price:
        reward_pct = abs(sig.take_profit_1 - sig.entry_price) / sig.entry_price * 100

    risk_str = f"{risk_pct:.2f}%" if risk_pct is not None else "—"
    reward_str = f"{reward_pct:.2f}%" if reward_pct is not None else "—"

    lines = [
        f"{type_icon} <b>Сигнал #{sig.id}: {sig.asset}</b> {status_icon}",
        _SEP,
        f"📌 <b>Тип:</b> {sig.signal_type}  •  <b>Стратегия:</b> {strategy}",
        f"🏦 <b>Биржа:</b> {sig.exchange}  •  <b>Класс:</b> {sig.asset_class}",
        f"⏱ <b>Таймфрейм:</b> {sig.timeframe}  •  <b>Режим:</b> {regime}",
        _SEP,
        f"💰 <b>Цена входа:</b>  <code>{sig.entry_price:.4f}</code>",
        f"🛑 <b>Stop Loss:</b>   <code>{sl_str}</code>  (риск {risk_str})",
        f"🎯 <b>Take Profit:</b> <code>{tp_str}{tp2_str}</code>  (доход {reward_str})",
        f"⚖ <b>R:R Ratio:</b>   <code>{rr_str}</code>",
        _SEP,
        f"🎯 <b>Confidence Score:</b>",
        f"   {_confidence_bar(confidence)} <code>{sig.probability_pct:.1f}%</code>",
        _SEP,
        "<b>📊 Индикаторы:</b>",
    ]

    if rsi is not None:
        zone = "перепродан" if rsi < 30 else ("перекуплен" if rsi > 70 else "нейтральный")
        lines.append(f"  RSI:  <code>{rsi:.1f}</code> ({zone})")
    if adx is not None:
        regime_label = "тренд" if adx >= 25 else ("флет" if adx < 20 else "переход")
        lines.append(f"  ADX:  <code>{adx:.1f}</code> ({regime_label})")
    if macd is not None:
        direction = "бычий" if macd > 0 else "медвежий"
        lines.append(f"  MACD: <code>{macd:.4f}</code> ({direction})")

    if triggered:
        lines.append(_SEP)
        lines.append("<b>✅ Сработавшие правила:</b>")
        for rule in triggered[:5]:
            lines.append(f"  • {rule}")

    lines += [
        _SEP,
        "<b>💡 Причина формирования:</b>",
        f"  <i>{entry_reason}</i>",
        _SEP,
        f"🕐 <i>Сгенерирован: {str(sig.generated_at)[:16]} UTC</i>",
    ]
    return "\n".join(lines)


def _format_signals_list(signals: list, active_filter: str = "all") -> str:
    filter_label = {"all": "Все", "new": "Новые", "long": "LONG", "short": "SHORT"}.get(active_filter, "Все")
    if not signals:
        return (
            f"📡 <b>Сигналы</b> — {filter_label}\n"
            + _SEP + "\n"
            "<i>Сигналов не найдено.\n"
            "Нажмите ⚡ Генерировать для запуска анализа рынка.</i>"
        )

    lines = [f"📡 <b>Сигналы</b> — {filter_label} ({len(signals)})", _SEP]

    for sig in signals[:10]:
        meta = sig.metadata or {}
        type_icon = _TYPE_ICON.get(sig.signal_type, "⚪")
        status_icon = _STATUS_ICON.get(sig.status, "🔵")
        strategy = meta.get("strategy", "—")
        rr_str = f"R:R {sig.risk_reward:.1f}" if sig.risk_reward else ""
        sl_str = f"SL {sig.stop_loss:.2f}" if sig.stop_loss else ""
        tp_str = f"TP {sig.take_profit_1:.2f}" if sig.take_profit_1 else ""
        lines.append(
            f"\n{type_icon} <b>#{sig.id} {sig.asset}</b> {status_icon}\n"
            f"  {sig.signal_type} | {strategy} | <code>{sig.entry_price:.4f}</code>\n"
            f"  {sl_str}  {tp_str}  {rr_str}\n"
            f"  Confidence: <code>{sig.probability_pct:.1f}%</code> | {str(sig.generated_at)[:10]}"
        )

    if len(signals) > 10:
        lines.append(f"\n<i>… и ещё {len(signals) - 10} сигналов</i>")
    return "\n".join(lines)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db_engine(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("db_engine")


def _load_signals(db_engine, signal_filter: str = "all") -> list:
    if db_engine is None:
        return []
    try:
        from qf_platform.services.signals_service import SignalsService
        svc = SignalsService(db_engine)
        status = "new" if signal_filter == "new" else None
        signals = svc.list_signals(limit=50, status=status)
        if signal_filter == "long":
            signals = [s for s in signals if s.signal_type.upper() in ("LONG", "BUY")]
        elif signal_filter == "short":
            signals = [s for s in signals if s.signal_type.upper() in ("SHORT", "SELL")]
        return signals
    except Exception as exc:
        logger.error("Signal load error: %s", exc)
        return []


# ── Render ────────────────────────────────────────────────────────────────────

async def _render_list(update: Update, context: ContextTypes.DEFAULT_TYPE, signal_filter: str = "all") -> None:
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

    db_engine = _get_db_engine(context)
    signals = _load_signals(db_engine, signal_filter)
    text = _format_signals_list(signals, signal_filter)
    kb = _signals_list_kb(signal_filter)

    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cb_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["sig_filter"] = "all"
    await _render_list(update, context, "all")


async def cb_signals_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_list(update, context, context.user_data.get("sig_filter", "all"))


async def cb_signals_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    signal_filter = query.data.replace("sig_filter_", "")
    context.user_data["sig_filter"] = signal_filter
    await _render_list(update, context, signal_filter)


async def cb_signals_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer("⚡ Генерирую сигналы…")

    db_engine = _get_db_engine(context)
    signals = []
    error_text = ""
    if db_engine:
        try:
            from qf_platform.services.signals_service import SignalsService
            signals = SignalsService(db_engine).generate_live_signals(persist=True)
        except Exception as exc:
            logger.error("Generation error: %s", exc)
            error_text = f"\n⚠️ Ошибка: <i>{exc}</i>"

    prefix = f"✅ <b>Сгенерировано: {len(signals)}</b>\n\n" if signals else "⚪ <b>Новых сигналов нет (рынок в HOLD)</b>\n\n"
    text = prefix + _format_signals_list(signals, "all") + error_text
    kb = _signals_list_kb("all")
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_signal_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer("📋 Исполняю в Paper Trading…")

    try:
        signal_id = int(query.data.replace("sig_exec_", ""))
    except ValueError:
        await query.answer("Некорректный ID сигнала", show_alert=True)
        return

    db_engine = _get_db_engine(context)
    if not db_engine:
        await query.answer("DB недоступна", show_alert=True)
        return

    try:
        from qf_platform.services.signals_service import SignalsService
        result = SignalsService(db_engine).execute_signal(signal_id)
        text = (
            f"✅ <b>Сигнал #{signal_id} исполнен</b>\n\n"
            f"Тикер: <b>{result.get('ticker', '—')}</b>\n"
            f"Направление: <b>{result.get('direction', '—')}</b>\n"
            f"Цена входа: <code>{result.get('entry_price', '—')}</code>\n"
            f"Количество: <code>{result.get('quantity', '—')}</code>"
        )
    except Exception as exc:
        logger.error("Signal execute error: %s", exc)
        text = f"❌ <b>Ошибка исполнения #{signal_id}</b>\n<i>{exc}</i>"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀ Сигналы",       callback_data="m_signals"),
            InlineKeyboardButton("📊 Paper Trading", callback_data="m_paper"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


# ── FSM: query by ticker ──────────────────────────────────────────────────────

async def cb_signal_query_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text(
        "📡 <b>Поиск по тикеру</b>\n\nВведите тикер инструмента:\n<i>Например: SBER, GAZP, LKOH</i>",
        reply_markup=CANCEL_KB,
        parse_mode="HTML",
    )
    return SignalStates.ENTER_TICKER


async def signal_enter_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_auth(update, context):
        return ConversationHandler.END

    ticker = update.message.text.strip().upper()
    db_engine = _get_db_engine(context)
    text = f"📡 <b>Сигналы по {ticker}</b>\n" + _SEP + "\n"

    if db_engine:
        try:
            from qf_platform.services.signals_service import SignalsService
            from sqlalchemy import text as sql_text
            svc = SignalsService(db_engine)
            with db_engine.connect() as conn:
                result = conn.execute(
                    sql_text(
                        "SELECT * FROM trading_signals WHERE asset = :t "
                        "ORDER BY generated_at DESC LIMIT 1"
                    ),
                    {"t": ticker},
                )
                cols = list(result.keys())
                rows = result.fetchall()

            if rows:
                d = dict(zip(cols, rows[0]))
                sig = svc._row_to_dto(d)
                text += _format_signal_card(sig)
            else:
                signals = svc.generate_live_signals(persist=True)
                ticker_sigs = [s for s in signals if s.asset == ticker]
                if ticker_sigs:
                    text += _format_signal_card(ticker_sigs[0])
                else:
                    text += f"<i>Нет сигнала для {ticker}. Рынок в состоянии HOLD или нет данных.</i>"
        except Exception as exc:
            logger.error("Ticker signal error for %s: %s", ticker, exc)
            text += f"<i>Ошибка: {exc}</i>"
    else:
        text += "<i>База данных недоступна</i>"

    kb = _signals_list_kb("all")
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
    db_engine = _get_db_engine(context)
    if not context.args:
        await _render_list(update, context, "all")
        return
    ticker = context.args[0].upper()
    if not db_engine:
        await update.message.reply_html("⚠️ База данных недоступна")
        return
    try:
        from qf_platform.services.signals_service import SignalsService
        from sqlalchemy import text as sql_text
        svc = SignalsService(db_engine)
        with db_engine.connect() as conn:
            result = conn.execute(
                sql_text("SELECT * FROM trading_signals WHERE asset = :t ORDER BY generated_at DESC LIMIT 1"),
                {"t": ticker},
            )
            cols = list(result.keys())
            rows = result.fetchall()
        if rows:
            sig = svc._row_to_dto(dict(zip(cols, rows[0])))
            text = _format_signal_card(sig)
        else:
            signals = svc.generate_live_signals(persist=True)
            ticker_sigs = [s for s in signals if s.asset == ticker]
            text = _format_signal_card(ticker_sigs[0]) if ticker_sigs else f"<i>Нет сигнала для {ticker}</i>"
    except Exception as exc:
        text = f"❌ Ошибка: {exc}"
    await update.message.reply_html(text)
