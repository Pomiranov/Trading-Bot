"""Telegram-бот управления торговым ботом. Команды: /status /signal /stop."""

import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import config
from data.loader import loader
from learning.feedback import feedback_store
from risk.risk_manager import risk_manager
from signals.indicators import indicator_engine
from signals.rules_engine import rules_engine, Action

logger = logging.getLogger(__name__)

# Флаг работы торгового цикла
_bot_running = False


def _fmt_float(val) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.2f}"
    except (TypeError, ValueError):
        return str(val)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение."""
    await update.message.reply_text(
        "Торговый бот MOEX запущен.\n\n"
        "Команды:\n"
        "/status — состояние бота и портфеля\n"
        "/signal <TICKER> — получить торговый сигнал\n"
        "/stop — остановить торговый цикл\n"
        "/trades — последние сделки\n"
        "/stats — статистика торговли\n"
        "/rules — список торговых правил"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — текущее состояние бота."""
    positions = risk_manager.open_positions
    daily_pnl = risk_manager.daily_pnl
    status_emoji = "🟢" if _bot_running else "🔴"

    lines = [
        f"{status_emoji} Торговый цикл: {'активен' if _bot_running else 'остановлен'}",
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        f"💰 Дневной PnL: {_fmt_float(daily_pnl)} руб.",
        f"📊 Открытых позиций: {len(positions)} / {config.risk.max_open_positions}",
    ]

    if positions:
        lines.append("\n— Позиции —")
        for ticker, pos in positions.items():
            lines.append(
                f"  {ticker}: вход {_fmt_float(pos.entry_price)}, "
                f"стоп {_fmt_float(pos.stop_price)}, "
                f"лотов {pos.lot_size}"
            )

    await update.message.reply_text("\n".join(lines))


async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/signal <TICKER> — запросить торговый сигнал для тикера."""
    if not ctx.args:
        await update.message.reply_text("Укажите тикер: /signal SBER")
        return

    ticker = ctx.args[0].upper()
    await update.message.reply_text(f"Загружаю данные для {ticker}...")

    try:
        df = loader.get_candles(ticker, interval="1h")
        if df.empty:
            await update.message.reply_text(f"Нет данных для {ticker}")
            return

        indicators = indicator_engine.latest(df)
        signal = rules_engine.evaluate(indicators)

        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(signal.action.value, "⚪")

        triggered_names = "\n".join(
            f"  • {r.name} (+{r.weight})" for r in signal.triggered_rules
        )

        text = (
            f"{action_emoji} Сигнал для {ticker}: *{signal.action.value}*\n\n"
            f"📈 Покупка: {signal.buy_score:.2f} | 📉 Продажа: {signal.sell_score:.2f}\n\n"
            f"📊 Индикаторы:\n"
            f"  RSI: {_fmt_float(indicators.rsi)}\n"
            f"  MACD гистограмма: {_fmt_float(indicators.macd_hist)}\n"
            f"  ADX: {_fmt_float(indicators.adx)}\n"
            f"  ATR: {_fmt_float(indicators.atr)}\n"
            f"  EMA быстрая/медленная: {_fmt_float(indicators.ema_fast)} / {_fmt_float(indicators.ema_slow)}\n"
        )

        if triggered_names:
            text += f"\n✅ Сработали правила:\n{triggered_names}"

        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as exc:
        logger.error("Ошибка команды /signal %s: %s", ticker, exc)
        await update.message.reply_text(f"Ошибка: {exc}")


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/stop — остановить торговый цикл."""
    global _bot_running
    _bot_running = False
    await update.message.reply_text("⏹ Торговый цикл остановлен.")
    logger.info("Торговый цикл остановлен командой /stop")


async def cmd_trades(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/trades — последние 10 сделок."""
    trades = feedback_store.get_recent_trades(limit=10)
    if not trades:
        await update.message.reply_text("Нет записей о сделках.")
        return

    lines = ["📋 Последние сделки:\n"]
    for t in trades:
        pnl_str = f"{_fmt_float(t.get('pnl'))} руб." if t.get("pnl") is not None else "открыта"
        lines.append(
            f"  {t['ticker']} {t['direction']} "
            f"{_fmt_float(t['entry_price'])} → {_fmt_float(t.get('exit_price'))} "
            f"| {pnl_str} | {t['status']}"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — общая статистика торговли."""
    stats = feedback_store.get_stats()
    if not stats or not stats.get("total_trades"):
        await update.message.reply_text("Нет закрытых сделок для анализа.")
        return

    total = stats["total_trades"] or 0
    wins = stats["winning_trades"] or 0
    winrate = (wins / total * 100) if total else 0

    text = (
        f"📊 Статистика торговли\n\n"
        f"Всего сделок: {total}\n"
        f"Прибыльных: {wins} ({winrate:.1f}%)\n"
        f"Убыточных: {stats.get('losing_trades', 0)}\n"
        f"Общий PnL: {_fmt_float(stats.get('total_pnl'))} руб.\n"
        f"Средний PnL: {_fmt_float(stats.get('avg_pnl'))} руб.\n"
        f"Лучшая: +{_fmt_float(stats.get('max_win'))} руб.\n"
        f"Худшая: {_fmt_float(stats.get('max_loss'))} руб.\n"
        f"Средний % PnL: {_fmt_float(stats.get('avg_pnl_pct'))}%"
    )
    await update.message.reply_text(text)


async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/rules — список загруженных торговых правил."""
    lines = ["📜 Торговые правила:\n"]
    for rule in rules_engine._rules:
        emoji = "🟢" if rule.get("action") == "BUY" else "🔴"
        lines.append(
            f"{emoji} [{rule.get('weight', 1.0)}] {rule['name']}\n"
            f"    {rule.get('description', '')}"
        )
    await update.message.reply_text("\n".join(lines))


def set_bot_running(state: bool) -> None:
    global _bot_running
    _bot_running = state


def build_app() -> Application:
    """Создать и настроить приложение Telegram-бота."""
    app = Application.builder().token(config.telegram.token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("trades", cmd_trades))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("rules", cmd_rules))
    return app


async def send_notification(text: str) -> None:
    """Отправить уведомление в чат (вызывается из торгового цикла)."""
    if not config.telegram.token or not config.telegram.chat_id:
        return
    try:
        from telegram import Bot
        bot = Bot(token=config.telegram.token)
        await bot.send_message(chat_id=config.telegram.chat_id, text=text)
    except Exception as exc:
        logger.error("Ошибка отправки уведомления Telegram: %s", exc)


def run_bot() -> None:
    """Запустить Telegram-бот в блокирующем режиме."""
    app = build_app()
    logger.info("Telegram-бот запущен")
    app.run_polling(drop_pending_updates=True)
