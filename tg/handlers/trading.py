"""Trading handler — FSM-based buy/sell flow with two-step confirmation."""
from __future__ import annotations

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from broker.base import OrderDirection, OrderType
from services.trading_service import TradeRequest, execute_trade, resolve_instrument
from tg.fsm.states import TradeStates
from tg.menus.keyboards import (
    confirm_trade_keyboard,
    trading_menu_keyboard,
    CANCEL_KB,
)
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"


async def cb_trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()
    await query.edit_message_text(
        "🔄 <b>Торговля</b>\n\nВыберите операцию:",
        reply_markup=trading_menu_keyboard(_BROKER_ID),
        parse_mode="HTML",
    )


async def cb_trade_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for buy/sell flow."""
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return ConversationHandler.END

    if not rate_limiter.is_allowed(query.from_user.id):
        await query.answer("⏳ Подождите", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    parts = query.data.split("_")
    direction = parts[1].upper()
    context.user_data["trade_direction"] = direction
    context.user_data["trade_broker"] = _BROKER_ID

    dir_label = "покупки" if direction == "BUY" else "продажи"
    await query.edit_message_text(
        f"🔄 <b>{direction}</b>\n\n"
        f"Введите тикер инструмента для {dir_label}:\n"
        f"<i>Например: SBER, GAZP, LKOH</i>",
        reply_markup=CANCEL_KB,
        parse_mode="HTML",
    )
    return TradeStates.ENTER_TICKER


async def trade_enter_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticker = update.message.text.strip().upper()
    if not ticker.isalpha() or len(ticker) > 12:
        await update.message.reply_html(
            "⚠️ Некорректный тикер. Введите тикер латинскими буквами (например: SBER):",
            reply_markup=CANCEL_KB,
        )
        return TradeStates.ENTER_TICKER

    broker_id = context.user_data.get("trade_broker", _BROKER_ID)
    instrument = await resolve_instrument(broker_id, ticker)
    if instrument is None:
        await update.message.reply_html(
            f"⚠️ Инструмент <b>{ticker}</b> не найден.\n\nПроверьте тикер и попробуйте ещё раз:",
            reply_markup=CANCEL_KB,
        )
        return TradeStates.ENTER_TICKER

    context.user_data["trade_ticker"] = ticker
    context.user_data["trade_figi"] = instrument["figi"]
    context.user_data["trade_lot"] = instrument.get("lot", 1)
    context.user_data["trade_instrument_name"] = instrument.get("name", ticker)

    direction = context.user_data.get("trade_direction", "BUY")
    dir_label = "покупки" if direction == "BUY" else "продажи"

    await update.message.reply_html(
        f"📌 <b>{ticker}</b> — {instrument.get('name', '')}\n"
        f"Лот: {instrument.get('lot', 1)} шт.\n\n"
        f"Введите количество <b>лотов</b> для {dir_label}:",
        reply_markup=CANCEL_KB,
    )
    return TradeStates.ENTER_QUANTITY


async def trade_enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        quantity = int(text)
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_html(
            "⚠️ Введите целое положительное число лотов:",
            reply_markup=CANCEL_KB,
        )
        return TradeStates.ENTER_QUANTITY

    context.user_data["trade_quantity"] = quantity
    direction = context.user_data.get("trade_direction", "BUY")
    ticker = context.user_data.get("trade_ticker", "")
    lot = context.user_data.get("trade_lot", 1)
    instrument_name = context.user_data.get("trade_instrument_name", ticker)
    figi = context.user_data.get("trade_figi", "")
    broker_id = context.user_data.get("trade_broker", _BROKER_ID)

    dir_icon = "🟢" if direction == "BUY" else "🔴"
    total_shares = quantity * lot

    await update.message.reply_html(
        f"{dir_icon} <b>Подтверждение заявки</b>\n\n"
        f"Инструмент: <b>{ticker}</b> — {instrument_name}\n"
        f"Операция: <b>{direction}</b>\n"
        f"Лотов: <b>{quantity}</b> ({total_shares} шт.)\n"
        f"Тип: <b>Рыночная заявка</b>\n\n"
        f"⚠️ <i>Заявка будет исполнена по рыночной цене.</i>",
        reply_markup=confirm_trade_keyboard(
            direction.lower(), broker_id, figi, quantity
        ),
    )
    return TradeStates.CONFIRM_ORDER


async def trade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    if len(parts) < 6:
        await query.edit_message_text("⚠️ Некорректный запрос.", reply_markup=None)
        return ConversationHandler.END

    direction_str = parts[2].upper()
    broker_id = parts[3]
    figi = parts[4]
    quantity = int(parts[5])

    direction = OrderDirection.BUY if direction_str == "BUY" else OrderDirection.SELL
    ticker = context.user_data.get("trade_ticker", figi)

    await query.edit_message_text(
        f"⏳ Отправляю рыночную заявку {direction_str} {ticker}…"
    )

    req = TradeRequest(
        broker_id=broker_id,
        ticker=ticker,
        figi=figi,
        direction=direction,
        quantity=quantity,
        order_type=OrderType.MARKET,
    )
    result = await execute_trade(req)

    if result.success:
        text = (
            f"✅ <b>Заявка размещена!</b>\n\n"
            f"Тикер: <b>{ticker}</b>\n"
            f"Операция: <b>{direction.value}</b>\n"
            f"Лотов: <b>{quantity}</b>\n"
            f"ID заявки: <code>{result.order_id}</code>"
        )
    else:
        text = f"❌ <b>Ошибка размещения заявки:</b>\n{result.error}"

    from tg.menus.keyboards import main_menu
    await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="HTML")
    context.user_data.clear()
    return ConversationHandler.END


async def trade_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    return ConversationHandler.END


def build_trade_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_trade_start, pattern=r"^trade_(buy|sell)_[a-z]+$"),
        ],
        states={
            TradeStates.ENTER_TICKER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trade_enter_ticker),
            ],
            TradeStates.ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, trade_enter_quantity),
            ],
            TradeStates.CONFIRM_ORDER: [
                CallbackQueryHandler(trade_confirm, pattern=r"^trade_confirm_"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(trade_cancel, pattern=r"^m_main$"),
            CommandHandler("cancel", trade_cancel),
        ],
        allow_reentry=True,
        name="trade_flow",
    )
