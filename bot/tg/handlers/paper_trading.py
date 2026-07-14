"""Paper trading Telegram handlers — portfolio, stats, positions, trades."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from tg.middlewares.auth import require_auth
from tg.middlewares.rate_limit import rate_limiter

logger = logging.getLogger(__name__)


def _fmt(value: float) -> str:
    """Format number with Russian thousands separator."""
    return f"{value:,.2f}".replace(",", " ")


def _paper_menu_keyboard(is_running: bool) -> InlineKeyboardMarkup:
    toggle_label = "⏹ Остановить движок" if is_running else "▶ Запустить движок"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="paper_toggle")],
        [
            InlineKeyboardButton("📈 Позиции",   callback_data="paper_positions"),
            InlineKeyboardButton("📋 Сделки",    callback_data="paper_trades"),
        ],
        [
            InlineKeyboardButton("📊 Аналитика", callback_data="paper_stats"),
            InlineKeyboardButton("⚠ Риск",      callback_data="paper_risk"),
        ],
        [
            InlineKeyboardButton("📡 Сигналы",   callback_data="m_signals"),
            InlineKeyboardButton("🤖 Auto Bot",  callback_data="m_trading_bot"),
        ],
        [
            InlineKeyboardButton("🔄 Обновить",  callback_data="m_paper"),
            InlineKeyboardButton("🏠 Главная",   callback_data="m_main"),
        ],
    ])


async def _render_paper_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_auth(update, context):
        if query:
            await query.answer()
        return
    if query:
        await query.answer()

    from engine.paper_engine import paper_engine
    is_running = paper_engine.is_running()

    db_engine = context.bot_data.get("db_engine")
    portfolio_text = "<i>DB недоступна</i>"
    if db_engine:
        try:
            paper_engine.set_db_engine(db_engine)
            portfolio = paper_engine.get_portfolio()
            account = portfolio["account"]
            pnl = portfolio["pnl"]
            positions = portfolio["positions"]
            balance = float(account.get("balance", 0))
            available = float(account.get("available_balance", 0))
            margin = float(account.get("margin_used", 0))
            currency = account.get("currency", "RUB")
            pnl_day = float(pnl.get("pnl_day", 0))
            realized = float(pnl.get("realized_pnl", 0))

            engine_status = "🟢 Работает" if is_running else "🔴 Остановлен"
            pnl_day_icon = "📈" if pnl_day >= 0 else "📉"
            realized_icon = "✅" if realized >= 0 else "❌"

            # Risk manager status
            try:
                from risk.risk_manager import risk_manager
                from config import config
                open_pos_count = len(risk_manager.open_positions)
                daily_pnl_rm = risk_manager.daily_pnl
                max_pos = config.risk.max_open_positions
                max_loss = config.risk.max_daily_loss_pct * 100
                risk_str = (
                    f"\n⚠ <b>Риск-менеджмент</b>\n"
                    f"Открытых позиций: <code>{open_pos_count}/{max_pos}</code>\n"
                    f"P&L сессии: <code>{daily_pnl_rm:+.2f} ₽</code>  (лимит -{max_loss:.1f}%)"
                )
            except Exception:
                risk_str = ""

            portfolio_text = (
                f"<b>📊 Paper Trading</b>\n"
                f"─────────────────────────\n"
                f"Движок: {engine_status}\n\n"
                f"💼 <b>Счёт</b>\n"
                f"Баланс: <code>{_fmt(balance)} {currency}</code>\n"
                f"Доступно: <code>{_fmt(available)} {currency}</code>\n"
                f"В позициях: <code>{_fmt(margin)} {currency}</code>\n\n"
                f"📈 <b>P&L</b>\n"
                f"{pnl_day_icon} За день: <code>{_fmt(pnl_day)} {currency}</code>\n"
                f"{realized_icon} Реализовано: <code>{_fmt(realized)} {currency}</code>\n\n"
                f"Открытых позиций: <b>{len(positions)}</b>"
                f"{risk_str}"
            )
        except Exception as exc:
            logger.warning("paper main render error: %s", exc)
            portfolio_text = f"<i>Ошибка загрузки данных: {exc}</i>"

    kb = _paper_menu_keyboard(is_running)
    if query:
        await query.edit_message_text(portfolio_text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.effective_message.reply_html(portfolio_text, reply_markup=kb)


async def cmd_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command /paper — shows paper trading portfolio."""
    await _render_paper_main(update, context)


async def cb_paper_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback m_paper."""
    await _render_paper_main(update, context)


async def cb_paper_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback paper_toggle — start/stop the paper engine."""
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return

    from engine.paper_engine import paper_engine
    db_engine = context.bot_data.get("db_engine")
    if db_engine:
        paper_engine.set_db_engine(db_engine)

    if paper_engine.is_running():
        paper_engine.stop()
        await query.answer("⏹ Paper движок остановлен", show_alert=True)
        logger.info("PaperEngine stopped via Telegram")
    else:
        paper_engine.start(db_engine=db_engine)
        await query.answer("▶ Paper движок запущен", show_alert=True)
        logger.info("PaperEngine started via Telegram")

    # Query is already answered above — edit the message directly without re-answering
    is_running = paper_engine.is_running()
    kb = _paper_menu_keyboard(is_running)
    engine_status = "🟢 Работает" if is_running else "🔴 Остановлен"
    try:
        await query.edit_message_text(
            f"<b>📊 Paper Trading</b>\n─────────────────────────\n"
            f"Движок: {engine_status}\n\n"
            f"<i>Нажмите 🔄 Обновить для загрузки данных счёта</i>",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception:
        pass


async def cb_paper_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback paper_stats — full analytics."""
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    if not rate_limiter.is_allowed(update.effective_user.id):
        await query.answer("Подождите", show_alert=True)
        return
    await query.answer()

    db_engine = context.bot_data.get("db_engine")
    text = "<i>DB недоступна</i>"
    if db_engine:
        try:
            from qf_platform.services.analytics_service import AnalyticsService
            svc = AnalyticsService(db_engine)
            stats = svc.trade_stats()
            text = (
                f"<b>📊 Аналитика Paper Trading</b>\n\n"
                f"Всего сделок: <b>{stats['total_trades']}</b>\n"
                f"Винрейт: <b>{_fmt(stats['win_rate'])}%</b>\n"
                f"Профит-фактор: <b>{stats['profit_factor'] or '—'}</b>\n\n"
                f"📈 <b>Доходность</b>\n"
                f"Общий P&L: <code>{_fmt(stats['total_pnl'])}</code>\n"
                f"ROI: <b>{_fmt(stats['roi_pct'])}%</b>\n"
                f"Ср. выигрыш: <code>{_fmt(stats['avg_win'])}</code>\n"
                f"Ср. проигрыш: <code>{_fmt(stats['avg_loss'])}</code>\n\n"
                f"📉 <b>Риск</b>\n"
                f"Макс. просадка: <b>{_fmt(stats['max_drawdown'] * 100)}%</b>\n"
                f"Sharpe: <b>{stats['sharpe_ratio']}</b>\n"
                f"Sortino: <b>{stats['sortino_ratio']}</b>\n\n"
                f"⏱ Ср. время сделки: <b>{_fmt(stats['avg_hold_time_hours'])} ч</b>"
            )
        except Exception as exc:
            logger.warning("paper stats render error: %s", exc)
            text = f"<i>Ошибка: {exc}</i>"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="paper_stats"),
            InlineKeyboardButton("◀ Назад",     callback_data="m_paper"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_paper_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback paper_positions — list open positions."""
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    db_engine = context.bot_data.get("db_engine")
    text = "<i>DB недоступна</i>"
    if db_engine:
        try:
            from engine.paper_engine import paper_engine
            paper_engine.set_db_engine(db_engine)
            portfolio = paper_engine.get_portfolio()
            positions = portfolio["positions"]
            account = portfolio["account"]
            currency = account.get("currency", "RUB")

            if not positions:
                text = "<b>📈 Открытые позиции</b>\n\n<i>Нет открытых позиций</i>"
            else:
                lines = ["<b>📈 Открытые позиции</b>\n"]
                for pos in positions[:10]:
                    direction_icon = "🟢" if pos.get("direction") == "long" else "🔴"
                    pnl_val = float(pos.get("unrealized_pnl", 0))
                    pnl_sign = "+" if pnl_val >= 0 else ""
                    lines.append(
                        f"{direction_icon} <b>{pos['ticker']}</b> ({pos.get('direction', 'long')})\n"
                        f"  Вход: <code>{_fmt(float(pos['entry_price']))}</code>"
                        f"  Текущая: <code>{_fmt(float(pos.get('current_price', pos['entry_price'])))}</code>\n"
                        f"  Кол-во: {pos.get('quantity')}"
                        f"  P&L: <code>{pnl_sign}{_fmt(pnl_val)} {currency}</code>"
                        f" ({pnl_sign}{_fmt(float(pos.get('pnl_pct', 0)))}%)\n"
                    )
                text = "\n".join(lines)
        except Exception as exc:
            logger.warning("paper positions render error: %s", exc)
            text = f"<i>Ошибка: {exc}</i>"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="paper_positions"),
            InlineKeyboardButton("◀ Назад",     callback_data="m_paper"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_paper_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback paper_trades — last 10 closed trades."""
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    db_engine = context.bot_data.get("db_engine")
    text = "<i>DB недоступна</i>"
    if db_engine:
        try:
            from qf_platform.repositories.paper_repository import PaperRepository
            repo = PaperRepository(db_engine)
            account = repo.get_or_create_account()
            trades = repo.list_trades(int(account["id"]), limit=10)
            currency = account.get("currency", "RUB")

            if not trades:
                text = "<b>📋 Закрытые сделки</b>\n\n<i>Сделок пока нет</i>"
            else:
                lines = ["<b>📋 Последние 10 сделок</b>\n"]
                for t in trades:
                    pnl_val = float(t.get("pnl", 0))
                    icon = "✅" if pnl_val >= 0 else "❌"
                    pnl_sign = "+" if pnl_val >= 0 else ""
                    closed_at = str(t.get("closed_at", ""))[:10]
                    close_reason = t.get("close_reason", "manual")
                    entry_reason = t.get("entry_reason") or ""
                    reason_labels = {
                        "SL_HIT": "SL", "TP_HIT": "TP",
                        "manual": "вручную", "partial_full": "полное закрытие"
                    }
                    close_label = reason_labels.get(close_reason, close_reason)
                    entry_str = f"\n  Причина входа: <i>{entry_reason}</i>" if entry_reason else ""
                    lines.append(
                        f"{icon} <b>{t['ticker']}</b> {t.get('direction', 'long')} "
                        f"({closed_at}) — {close_label}\n"
                        f"  Вход: <code>{_fmt(float(t['entry_price']))}</code>  "
                        f"Выход: <code>{_fmt(float(t['exit_price']))}</code>\n"
                        f"  P&amp;L: <code>{pnl_sign}{_fmt(pnl_val)} {currency}</code>"
                        f"{entry_str}\n"
                    )
                text = "\n".join(lines)
        except Exception as exc:
            logger.warning("paper trades render error: %s", exc)
            text = f"<i>Ошибка: {exc}</i>"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="paper_trades"),
            InlineKeyboardButton("◀ Назад",     callback_data="m_paper"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_paper_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback paper_risk — Risk Management status."""
    query = update.callback_query
    if not await require_auth(update, context):
        await query.answer()
        return
    await query.answer()

    _SEP = "─" * 28
    try:
        from risk.risk_manager import risk_manager
        from config import config

        open_pos = risk_manager.open_positions
        daily_pnl = risk_manager.daily_pnl
        max_pos = config.risk.max_open_positions
        max_loss_pct = config.risk.max_daily_loss_pct
        atr_mult = config.risk.atr_stop_multiplier
        pos_pct = config.risk.max_position_pct

        # Get portfolio value for limit calculation
        db_engine = context.bot_data.get("db_engine")
        portfolio_value = 0.0
        if db_engine:
            try:
                from engine.paper_engine import paper_engine
                paper_engine.set_db_engine(db_engine)
                port = paper_engine.get_portfolio()
                portfolio_value = float(port["account"].get("balance", 0))
            except Exception:
                pass

        max_loss_rub = portfolio_value * max_loss_pct if portfolio_value else 0
        daily_icon = "🟢" if daily_pnl >= -max_loss_rub * 0.5 else ("🟡" if daily_pnl >= -max_loss_rub else "🔴")

        lines = [
            "⚠ <b>Risk Management</b>",
            _SEP,
            "<b>📊 Текущее состояние:</b>",
            f"  Открытых позиций: <code>{len(open_pos)} / {max_pos}</code>",
            f"  {daily_icon} P&L сессии: <code>{daily_pnl:+.2f} ₽</code>",
            f"  Дневной лимит: <code>-{max_loss_rub:.2f} ₽</code>  ({max_loss_pct * 100:.1f}%)",
            _SEP,
            "<b>⚙ Параметры риска:</b>",
            f"  ATR-множитель стопа: <code>{atr_mult}x</code>",
            f"  Макс. размер позиции: <code>{pos_pct * 100:.1f}%</code> от депозита",
            f"  Макс. позиций: <code>{max_pos}</code>",
        ]

        if open_pos:
            lines.append(_SEP)
            lines.append("<b>📈 Открытые позиции (RiskMgr):</b>")
            for ticker, ps in list(open_pos.items())[:5]:
                lines.append(
                    f"  <b>{ticker}</b>: вход <code>{ps.entry_price:.4f}</code>  "
                    f"стоп <code>{ps.stop_price:.4f}</code>  "
                    f"риск <code>{ps.risk_amount:.2f} ₽</code>"
                )

        text = "\n".join(lines)
    except Exception as exc:
        logger.warning("paper risk render error: %s", exc)
        text = f"⚠ <b>Risk Management</b>\n\n<i>Ошибка: {exc}</i>"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="paper_risk"),
            InlineKeyboardButton("◀ Назад",     callback_data="m_paper"),
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="m_main")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
