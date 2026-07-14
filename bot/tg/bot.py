"""
Telegram Application factory.

Wires all handlers, middlewares, conversations, and background jobs.
Entry point: run_bot() — blocking, runs its own event loop.
send_notification() — safe async helper callable from the trading loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram import Bot, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import config
from security.bootstrap import bootstrap_security
from tg.middlewares.auth import AuthMiddleware
from tg.middlewares.error_handler import handle_error
from tg.notifications.dispatcher import set_bot

# Handlers
from tg.handlers.start import cmd_start, cb_main_menu
from tg.handlers.dashboard import cb_dashboard, cmd_dashboard, cb_dashboard_refresh
from tg.handlers.portfolio import cb_portfolio, cb_portfolio_refresh, cmd_portfolio
from tg.handlers.positions import (
    cb_positions, cb_positions_page, cb_positions_refresh, cmd_positions,
    cb_position_detail,
)
from tg.handlers.orders import (
    cb_orders, cb_orders_filter, cb_orders_refresh, cb_order_cancel, cmd_orders,
)
from tg.handlers.operations import (
    cb_operations, cb_operations_page, cb_operations_refresh, cmd_operations,
)
from tg.handlers.balance import cb_balance, cb_balance_refresh, cmd_balance
from tg.handlers.statistics import cb_statistics, cb_statistics_refresh, cmd_statistics
from tg.handlers.analytics import (
    cb_analytics,
    cb_analytics_paper, cb_analytics_broker,
    cb_analytics_strategy, cb_analytics_drawdown,
)
from tg.handlers.trading import cb_trading_menu, build_trade_conversation
from tg.handlers.trading_bot import (
    cb_trading_bot, cb_bot_start, cb_bot_pause, cb_bot_resume,
    cb_bot_stop, cb_bot_status, cb_bot_logs, cmd_bot_status,
)
from tg.handlers.signals import (
    cb_signals, cb_signals_refresh, cb_signals_filter,
    cb_signals_generate, cb_signal_execute,
    cmd_signal, build_signal_conversation,
)
from tg.handlers.notifications import cb_notifications, cb_notification_toggle
from tg.handlers.settings import (
    cb_settings, cb_settings_brokers, cb_settings_broker_tinkoff,
    cb_settings_broker_finam, build_settings_conversation,
)
from tg.handlers.account import cb_account, cb_account_accounts
from tg.handlers.help import cb_help, cmd_help
from tg.handlers.miniapp import cmd_game, cb_game, setup_menu_button
from tg.handlers.paper_trading import (
    cmd_paper, cb_paper_menu, cb_paper_toggle,
    cb_paper_stats, cb_paper_positions, cb_paper_trades,
    cb_paper_risk,
)

logger = logging.getLogger(__name__)


def _build_application() -> Application:
    bootstrap_security(config, service_name="telegram-bot")

    if not config.telegram.token:
        raise RuntimeError(
            "TELEGRAM_TOKEN не настроен. Укажите его в .env файле."
        )

    app = (
        ApplicationBuilder()
        .token(config.telegram.token)
        .build()
    )

    # ── Inject DB engine into bot_data for handlers that need statistics ──
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(
            config.db.dsn,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
        )
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        app.bot_data["db_engine"] = engine
        logger.info("DB connected for Telegram bot statistics")
    except Exception as exc:
        logger.warning("DB unavailable for bot: %s — statistics disabled", exc)
        app.bot_data["db_engine"] = None

    # ── Global error handler ─────────────────────────────────────────────
    app.add_error_handler(handle_error)

    # ── Auth gate (group -1): fail-closed before any handler ─────────────
    app.add_handler(AuthMiddleware(), group=-1)

    # ── FSM Conversations (must be added before catch-all handlers) ──────
    app.add_handler(build_trade_conversation())
    app.add_handler(build_signal_conversation())
    app.add_handler(build_settings_conversation())

    # ── Command handlers ─────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("dashboard",  cmd_dashboard))
    app.add_handler(CommandHandler("portfolio",  cmd_portfolio))
    app.add_handler(CommandHandler("positions",  cmd_positions))
    app.add_handler(CommandHandler("orders",     cmd_orders))
    app.add_handler(CommandHandler("operations", cmd_operations))
    app.add_handler(CommandHandler("balance",    cmd_balance))
    app.add_handler(CommandHandler("stats",      cmd_statistics))
    app.add_handler(CommandHandler("signal",     cmd_signal))
    app.add_handler(CommandHandler("status",     cmd_bot_status))
    app.add_handler(CommandHandler("help",       cmd_help))

    # ── Menu navigation ───────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(cb_main_menu,           pattern=r"^m_main$"))
    app.add_handler(CallbackQueryHandler(cb_dashboard,           pattern=r"^m_dashboard$"))
    app.add_handler(CallbackQueryHandler(cb_dashboard_refresh,   pattern=r"^dash_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_portfolio,           pattern=r"^m_portfolio$"))
    app.add_handler(CallbackQueryHandler(cb_portfolio_refresh,   pattern=r"^port_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_positions,           pattern=r"^m_positions$"))
    app.add_handler(CallbackQueryHandler(cb_positions_page,      pattern=r"^pos_pg_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_positions_refresh,   pattern=r"^pos_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_orders,              pattern=r"^m_orders$"))
    app.add_handler(CallbackQueryHandler(cb_orders_filter,       pattern=r"^ord_filter_"))
    app.add_handler(CallbackQueryHandler(cb_orders_refresh,      pattern=r"^ord_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_order_cancel,        pattern=r"^ord_cancel_"))
    app.add_handler(CallbackQueryHandler(cb_operations,          pattern=r"^m_operations$"))
    app.add_handler(CallbackQueryHandler(cb_operations_page,     pattern=r"^ops_pg_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_operations_refresh,  pattern=r"^ops_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_balance,             pattern=r"^m_balance$"))
    app.add_handler(CallbackQueryHandler(cb_balance_refresh,     pattern=r"^bal_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_statistics,          pattern=r"^m_statistics$"))
    app.add_handler(CallbackQueryHandler(cb_statistics_refresh,  pattern=r"^stat_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_analytics,           pattern=r"^m_analytics$"))
    app.add_handler(CallbackQueryHandler(cb_analytics_paper,     pattern=r"^analytics_paper$"))
    app.add_handler(CallbackQueryHandler(cb_analytics_broker,    pattern=r"^analytics_broker$"))
    app.add_handler(CallbackQueryHandler(cb_analytics_strategy,  pattern=r"^analytics_strategy$"))
    app.add_handler(CallbackQueryHandler(cb_analytics_drawdown,  pattern=r"^analytics_drawdown$"))
    app.add_handler(CallbackQueryHandler(cb_trading_menu,        pattern=r"^m_trading$"))
    app.add_handler(CallbackQueryHandler(cb_trading_bot,         pattern=r"^m_trading_bot$"))
    app.add_handler(CallbackQueryHandler(cb_bot_start,           pattern=r"^bot_start$"))
    app.add_handler(CallbackQueryHandler(cb_bot_pause,           pattern=r"^bot_pause$"))
    app.add_handler(CallbackQueryHandler(cb_bot_resume,          pattern=r"^bot_resume$"))
    app.add_handler(CallbackQueryHandler(cb_bot_stop,            pattern=r"^bot_stop$"))
    app.add_handler(CallbackQueryHandler(cb_bot_status,          pattern=r"^bot_status$"))
    app.add_handler(CallbackQueryHandler(cb_bot_logs,            pattern=r"^bot_logs$"))
    app.add_handler(CallbackQueryHandler(cb_signals,             pattern=r"^m_signals$"))
    app.add_handler(CallbackQueryHandler(cb_signals_refresh,     pattern=r"^sig_refresh$"))
    app.add_handler(CallbackQueryHandler(cb_signals_filter,      pattern=r"^sig_filter_"))
    app.add_handler(CallbackQueryHandler(cb_signals_generate,    pattern=r"^sig_generate$"))
    app.add_handler(CallbackQueryHandler(cb_signal_execute,      pattern=r"^sig_exec_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_notifications,       pattern=r"^m_notifications$"))
    app.add_handler(CallbackQueryHandler(cb_notification_toggle, pattern=r"^notif_toggle_"))
    app.add_handler(CallbackQueryHandler(cb_settings,            pattern=r"^m_settings$"))
    app.add_handler(CallbackQueryHandler(cb_settings_brokers,    pattern=r"^set_brokers$"))
    app.add_handler(CallbackQueryHandler(cb_settings_broker_tinkoff, pattern=r"^set_broker_tinkoff$"))
    app.add_handler(CallbackQueryHandler(cb_settings_broker_finam,   pattern=r"^set_broker_finam$"))
    app.add_handler(CallbackQueryHandler(cb_account,             pattern=r"^m_account$"))
    app.add_handler(CallbackQueryHandler(cb_account_accounts,    pattern=r"^acc_accounts$"))
    app.add_handler(CallbackQueryHandler(cb_help,                pattern=r"^m_help$"))
    app.add_handler(CallbackQueryHandler(cb_game,                pattern=r"^m_game$"))

    # ── Positions detail ──────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(cb_position_detail, pattern=r"^pos_detail_"))

    # No-op callbacks (pagination labels, unimplemented history)
    app.add_handler(CallbackQueryHandler(
        lambda u, c: u.callback_query.answer(),
        pattern=r"^(pos_noop|ops_noop|pos_hist_.+)$",
    ))

    # ── Stub handlers for settings sections not yet implemented ───────────────
    async def _cb_coming_soon(update, context):
        await update.callback_query.answer("Раздел в разработке", show_alert=True)

    app.add_handler(CallbackQueryHandler(
        _cb_coming_soon,
        pattern=r"^(set_tokens|set_timezone|set_currency|set_risk|set_interval|set_security|sig_filter_active)$",
    ))

    # ── Command: /game ────────────────────────────────────────────────────
    app.add_handler(CommandHandler("game", cmd_game))

    # ── Paper Trading ─────────────────────────────────────────────────────
    app.add_handler(CommandHandler("paper", cmd_paper))
    app.add_handler(CallbackQueryHandler(cb_paper_menu,      pattern=r"^m_paper$"))
    app.add_handler(CallbackQueryHandler(cb_paper_toggle,    pattern=r"^paper_toggle$"))
    app.add_handler(CallbackQueryHandler(cb_paper_stats,     pattern=r"^paper_stats$"))
    app.add_handler(CallbackQueryHandler(cb_paper_positions, pattern=r"^paper_positions$"))
    app.add_handler(CallbackQueryHandler(cb_paper_trades,    pattern=r"^paper_trades$"))
    app.add_handler(CallbackQueryHandler(cb_paper_risk,      pattern=r"^paper_risk$"))

    return app


_application: Optional[Application] = None


def run_bot() -> None:
    """Start the Telegram bot (blocking). Call from a dedicated thread."""
    global _application
    _application = _build_application()
    set_bot(_application.bot)
    logger.info("Telegram bot starting (polling)…")

    async def _post_init(app) -> None:
        await setup_menu_button(app.bot)

    _application.post_init = _post_init
    _application.run_polling(drop_pending_updates=True, stop_signals=[])
    logger.info("Telegram bot stopped")


async def send_notification(text: str) -> None:
    """
    Fire-and-forget notification from the trading loop.
    Safe to call from any async context.
    """
    if not config.telegram.token or not config.telegram.chat_id:
        return
    try:
        from tg.notifications.dispatcher import notify
        await notify("order_fill", text)
    except Exception as exc:
        logger.error("Notification error: %s", exc)
