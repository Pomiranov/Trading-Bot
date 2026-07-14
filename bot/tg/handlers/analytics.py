"""Analytics handler — paper trading performance + broker portfolio breakdown."""
from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from services import broker_service
from tg.formatters.numbers import fmt_money, fmt_pct, fmt_pnl, fmt_ratio
from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)
_BROKER_ID = "tinkoff"
_SEP = "─" * 28


def _analytics_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Paper Trading", callback_data="analytics_paper"),
            InlineKeyboardButton("💼 Брокер",        callback_data="analytics_broker"),
        ],
        [
            InlineKeyboardButton("📈 Стратегии",     callback_data="analytics_strategy"),
            InlineKeyboardButton("📉 Просадка",      callback_data="analytics_drawdown"),
        ],
        [
            InlineKeyboardButton("🔄 Обновить",      callback_data="m_analytics"),
            InlineKeyboardButton("🏠 Главная",       callback_data="m_main"),
        ],
    ])


def _paper_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить",  callback_data="analytics_paper"),
            InlineKeyboardButton("◀ Аналитика", callback_data="m_analytics"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


def _broker_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить",  callback_data="analytics_broker"),
            InlineKeyboardButton("◀ Аналитика", callback_data="m_analytics"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


def _strategy_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить",  callback_data="analytics_strategy"),
            InlineKeyboardButton("◀ Аналитика", callback_data="m_analytics"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


def _drawdown_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить",  callback_data="analytics_drawdown"),
            InlineKeyboardButton("◀ Аналитика", callback_data="m_analytics"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])


# ── Main analytics menu ────────────────────────────────────────────────────────

async def _render_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    db_engine = context.bot_data.get("db_engine")
    lines = ["📊 <b>Аналитика</b>", _SEP]

    if db_engine:
        try:
            from qf_platform.services.analytics_service import AnalyticsService
            stats = AnalyticsService(db_engine).trade_stats()
            win_rate = stats.get("win_rate", 0)
            total = stats.get("total_trades", 0)
            total_pnl = stats.get("total_pnl", 0)
            roi = stats.get("roi_pct", 0)
            sharpe = stats.get("sharpe_ratio", 0)
            max_dd = stats.get("max_drawdown", 0)
            pf = stats.get("profit_factor")

            pnl_icon = "📈" if total_pnl >= 0 else "📉"
            lines += [
                "📋 <b>Paper Trading — Сводка</b>",
                f"  Сделок:        {total}",
                f"  Win Rate:      {win_rate:.1f}%",
                f"  {pnl_icon} P&L:  {total_pnl:+.2f} ₽  (ROI {roi:+.2f}%)",
                f"  Sharpe:        {sharpe:.2f}",
                f"  Max Drawdown:  {max_dd * 100:.2f}%",
                f"  Profit Factor: {f'{pf:.2f}' if pf else '—'}",
                _SEP,
                "<i>Выберите раздел для детального анализа:</i>",
            ]
        except Exception as exc:
            lines.append(f"<i>Paper аналитика недоступна: {exc}</i>")
    else:
        lines.append("<i>База данных недоступна</i>")

    text = "\n".join(lines)
    kb = _analytics_main_kb()
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=kb)


# ── Paper analytics ────────────────────────────────────────────────────────────

async def _render_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        text = "📊 <b>Paper Trading Analytics</b>\n\n<i>База данных недоступна</i>"
    else:
        try:
            from qf_platform.services.analytics_service import AnalyticsService
            svc = AnalyticsService(db_engine)
            stats = svc.trade_stats()
            monthly = svc.monthly_pnl()
            bw = svc.best_worst_trades(3)

            total = stats.get("total_trades", 0)
            wins = stats.get("winning_trades", 0)
            losses = stats.get("losing_trades", 0)
            win_rate = stats.get("win_rate", 0)
            total_pnl = stats.get("total_pnl", 0)
            roi = stats.get("roi_pct", 0)
            avg_win = stats.get("avg_win", 0)
            avg_loss = stats.get("avg_loss", 0)
            sharpe = stats.get("sharpe_ratio", 0)
            sortino = stats.get("sortino_ratio", 0)
            max_dd = stats.get("max_drawdown", 0)
            pf = stats.get("profit_factor")
            hold_h = stats.get("avg_hold_time_hours", 0)

            pnl_icon = "📈" if total_pnl >= 0 else "📉"

            lines = [
                "📊 <b>Paper Trading — Полная аналитика</b>",
                _SEP,
                "<b>📋 Сделки:</b>",
                f"  Всего:         {total}",
                f"  Прибыльных:    {wins}  |  Убыточных: {losses}",
                f"  Win Rate:      {win_rate:.1f}%",
                _SEP,
                "<b>💰 Доходность:</b>",
                f"  {pnl_icon} Общий P&L: {total_pnl:+.2f} ₽",
                f"  ROI:           {roi:+.2f}%",
                f"  Ср. прибыль:   {avg_win:+.2f} ₽",
                f"  Ср. убыток:    {avg_loss:+.2f} ₽",
                f"  Profit Factor: {f'{pf:.2f}' if pf else '—'}",
                _SEP,
                "<b>📉 Риск:</b>",
                f"  Max Drawdown:  {max_dd * 100:.2f}%",
                f"  Sharpe Ratio:  {sharpe:.3f}",
                f"  Sortino Ratio: {sortino:.3f}",
                f"  Ср. держание:  {hold_h:.1f} ч",
            ]

            if monthly:
                lines.append(_SEP)
                lines.append("<b>📆 По месяцам:</b>")
                for m in monthly[:3]:
                    p = m.get("pnl", 0)
                    icon = "🟢" if p >= 0 else "🔴"
                    lines.append(
                        f"  {icon} {m.get('month', '—')}: {p:+.2f} ₽  "
                        f"({m.get('trades', 0)} сделок, WR {m.get('win_rate', 0):.0f}%)"
                    )

            best = bw.get("best", [])
            worst = bw.get("worst", [])
            if best or worst:
                lines.append(_SEP)
                if best:
                    lines.append("<b>🏆 Лучшие сделки:</b>")
                    for t in best:
                        lines.append(f"  🟢 {t['ticker']} {t['direction']}: {t['pnl']:+.2f} ₽")
                if worst:
                    lines.append("<b>💔 Худшие сделки:</b>")
                    for t in worst:
                        lines.append(f"  🔴 {t['ticker']} {t['direction']}: {t['pnl']:+.2f} ₽")

            text = "\n".join(lines)
        except Exception as exc:
            logger.error("Paper analytics error: %s", exc)
            text = f"📊 <b>Paper Trading Analytics</b>\n\n<i>Ошибка: {exc}</i>"

    if query:
        await query.edit_message_text(text, reply_markup=_paper_kb(), parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=_paper_kb())


# ── Broker analytics ───────────────────────────────────────────────────────────

async def _render_broker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    try:
        portfolio = await broker_service.get_broker_portfolio(_BROKER_ID)
    except Exception as exc:
        logger.error("Analytics broker portfolio error: %s", exc)
        text = f"⚠️ <b>Брокер недоступен</b>\n<i>{exc}</i>"
        if query:
            await query.edit_message_text(text, reply_markup=_broker_kb(), parse_mode="HTML")
        else:
            await update.effective_message.reply_html(text, reply_markup=_broker_kb())
        return

    positions = portfolio.positions
    if not positions:
        text = "💼 <b>Брокер — Аналитика</b>\n" + _SEP + "\n🗂 <i>Портфель пуст</i>"
    else:
        type_groups: dict[str, list] = {}
        for pos in positions:
            type_groups.setdefault(pos.instrument_type, []).append(pos)

        type_icons = {"stock": "📈", "share": "📈", "etf": "🧺", "bond": "📊",
                      "currency": "💱", "crypto": "₿"}

        lines = [
            "💼 <b>Брокер — Аналитика портфеля</b>",
            _SEP,
            f"💰 Стоимость: {fmt_money(portfolio.total_value, '₽')}",
            f"📈 Доходность: {fmt_pnl(portfolio.total_yield)} ({fmt_pct(portfolio.total_yield_pct)})",
            _SEP,
            "<b>Структура по типам:</b>",
        ]
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
        lines.append("<b>Топ позиций:</b>")
        top = sorted(positions, key=lambda p: p.current_value, reverse=True)[:5]
        for pos in top:
            share = pos.current_value / portfolio.total_value * 100 if portfolio.total_value > 0 else 0
            lines.append(
                f"  <b>{pos.ticker}</b>: {fmt_money(pos.current_value, '₽')} "
                f"({fmt_pct(share)}) | {fmt_pct(pos.unrealized_pnl_pct)}"
            )
        text = "\n".join(lines)

    if query:
        await query.edit_message_text(text, reply_markup=_broker_kb(), parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=_broker_kb())


# ── Strategy breakdown ─────────────────────────────────────────────────────────

async def _render_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        text = "📈 <b>Стратегии</b>\n\n<i>База данных недоступна</i>"
    else:
        try:
            from qf_platform.services.analytics_service import AnalyticsService
            breakdown = AnalyticsService(db_engine).strategy_breakdown()
            if not breakdown:
                text = "📈 <b>Разбивка по стратегиям</b>\n\n<i>Недостаточно данных</i>"
            else:
                lines = ["📈 <b>Разбивка по стратегиям</b>", _SEP]
                for item in breakdown:
                    icon = "🟢" if item.get("total_pnl", 0) >= 0 else "🔴"
                    t = item.get("trades", 0)
                    w = item.get("wins", 0)
                    wr = w / t * 100 if t else 0
                    lines.append(
                        f"{icon} <b>{item.get('source', '—')}</b>\n"
                        f"  Сделок: {t}  |  Win Rate: {wr:.1f}%\n"
                        f"  P&L: {item.get('total_pnl', 0):+.2f} ₽"
                    )
                text = "\n".join(lines)
        except Exception as exc:
            text = f"📈 <b>Стратегии</b>\n\n<i>Ошибка: {exc}</i>"

    if query:
        await query.edit_message_text(text, reply_markup=_strategy_kb(), parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=_strategy_kb())


# ── Drawdown analysis ──────────────────────────────────────────────────────────

async def _render_drawdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    db_engine = context.bot_data.get("db_engine")
    if not db_engine:
        text = "📉 <b>Просадка</b>\n\n<i>База данных недоступна</i>"
    else:
        try:
            from qf_platform.services.analytics_service import AnalyticsService
            svc = AnalyticsService(db_engine)
            stats = svc.trade_stats()
            daily_pnl = svc.daily_pnl(30)

            max_dd = stats.get("max_drawdown", 0)
            sharpe = stats.get("sharpe_ratio", 0)
            sortino = stats.get("sortino_ratio", 0)

            from config import config
            max_allowed_dd = config.risk.max_daily_loss_pct * 100

            dd_icon = "🟢" if max_dd * 100 < max_allowed_dd else "🔴"

            lines = [
                "📉 <b>Анализ просадки и риска</b>",
                _SEP,
                f"{dd_icon} <b>Max Drawdown:</b>  {max_dd * 100:.2f}%  (лимит {max_allowed_dd:.1f}%)",
                f"  Sharpe Ratio:  {sharpe:.3f}",
                f"  Sortino Ratio: {sortino:.3f}",
                _SEP,
                "<b>📅 P&L за 30 дней:</b>",
            ]
            if not daily_pnl:
                lines.append("  <i>Нет данных</i>")
            else:
                for day in daily_pnl[:10]:
                    icon = "🟢" if day.get("pnl", 0) >= 0 else "🔴"
                    lines.append(
                        f"  {icon} {day.get('day', '—')}: "
                        f"{day.get('pnl', 0):+.2f} ₽  ({day.get('trades', 0)} сд.)"
                    )
            text = "\n".join(lines)
        except Exception as exc:
            text = f"📉 <b>Просадка</b>\n\n<i>Ошибка: {exc}</i>"

    if query:
        await query.edit_message_text(text, reply_markup=_drawdown_kb(), parse_mode="HTML")
    else:
        await update.effective_message.reply_html(text, reply_markup=_drawdown_kb())


# ── Public handlers ────────────────────────────────────────────────────────────

async def cb_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_main(update, context)


async def cb_analytics_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_paper(update, context)


async def cb_analytics_broker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_broker(update, context)


async def cb_analytics_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_strategy(update, context)


async def cb_analytics_drawdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_drawdown(update, context)
