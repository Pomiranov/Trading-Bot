"""Analytics handler — portfolio breakdown and performance metrics."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import broker_service
from tg.formatters.numbers import fmt_money, fmt_pct, fmt_pnl
from tg.menus.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"
_SEP = "─" * 28

_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔄 Обновить",  callback_data="m_analytics"),
        InlineKeyboardButton("💼 Портфель",  callback_data="m_portfolio"),
    ],
    [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
])


async def _render(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    try:
        portfolio = await broker_service.get_broker_portfolio(_BROKER_ID)
    except Exception as exc:
        logger.error("Analytics portfolio error: %s", exc)
        text = f"⚠️ Ошибка загрузки данных:\n{exc}"
        if query:
            await query.edit_message_text(text, reply_markup=_KB)
        else:
            await update.effective_message.reply_text(text, reply_markup=_KB)
        return

    positions = portfolio.positions
    if not positions:
        text = (
            "📊 <b>Аналитика портфеля</b>\n"
            + _SEP + "\n"
            "🗂 <i>Портфель пуст</i>"
        )
        if query:
            await query.edit_message_text(text, reply_markup=_KB, parse_mode="HTML")
        else:
            await update.effective_message.reply_html(text, reply_markup=_KB)
        return

    type_groups: dict[str, list] = {}
    for pos in positions:
        type_groups.setdefault(pos.instrument_type, []).append(pos)

    lines = [
        "📊 <b>Аналитика портфеля</b>",
        _SEP,
        f"💰 Стоимость: {fmt_money(portfolio.total_value, '₽')}",
        f"📈 Доходность: {fmt_pnl(portfolio.total_yield)} ({fmt_pct(portfolio.total_yield_pct)})",
        _SEP,
        "<b>Структура по типам:</b>",
    ]

    type_icons = {"stock": "📈", "share": "📈", "etf": "🧺", "bond": "📊",
                  "currency": "💱", "crypto": "₿"}

    for itype, grp in sorted(type_groups.items(), key=lambda x: -sum(p.current_value for p in x[1])):
        grp_val = sum(p.current_value for p in grp)
        grp_pnl = sum(p.unrealized_pnl for p in grp)
        pct = grp_val / portfolio.total_value * 100 if portfolio.total_value > 0 else 0
        icon = type_icons.get(itype, "📌")
        lines.append(
            f"  {icon} {itype.capitalize()}: "
            f"{fmt_money(grp_val, '₽')} ({fmt_pct(pct)}) "
            f"| PnL: {fmt_pnl(grp_pnl)}"
        )

    lines.append(_SEP)
    lines.append("<b>Топ позиций по стоимости:</b>")
    top = sorted(positions, key=lambda p: p.current_value, reverse=True)[:5]
    for pos in top:
        share = pos.current_value / portfolio.total_value * 100 if portfolio.total_value > 0 else 0
        lines.append(
            f"  <b>{pos.ticker}</b>: {fmt_money(pos.current_value, '₽')} "
            f"({fmt_pct(share)}) | {fmt_pct(pos.unrealized_pnl_pct)}"
        )

    text = "\n".join(lines)
    if query:
        await query.edit_message_text(text, reply_markup=_KB, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=_KB)


async def cb_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render(update, context)
