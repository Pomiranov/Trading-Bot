"""
Telegram-бот управления торговым ботом — полный rewrite.

Команды  : /start /status /signal /signals /stop /start_trading
           /portfolio /backtest /help
Кнопки   : [✅ Подтвердить сделку] [❌ Отклонить] после каждого BUY/SELL
Алерты   : новые сигналы, исполнение сделок, стоп-лосс, просадка > 5%,
           ежедневный отчёт в 19:00 МСК
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import config
from data.loader import loader
from learning.feedback import feedback_store
from notify import truncate
from risk.risk_manager import risk_manager
from signals.indicators import indicator_engine
from signals.rules_engine import rules_engine, Action
from tg.middlewares.auth import require_auth

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────

_bot_running: bool = False
_state_lock = threading.Lock()

# trade_id → {ticker, figi, lot, action, price, stop, ind, signal, instrument}
_pending_trades: dict[str, dict] = {}

# Prevents duplicate signal alerts within the same hour
# Format: "TICKER:BUY:2026062714"
_sent_signal_keys: set[str] = set()

# Drawdown guard — tracks portfolio value peak for the session
_portfolio_peak: float = 0.0
_drawdown_alerted: bool = False

# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt(val, dec: int = 2) -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.{dec}f}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_money(val) -> str:
    if val is None:
        return "—"
    try:
        v = float(val)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:,.2f} ₽".replace(",", " ")
    except (TypeError, ValueError):
        return str(val)


def _confidence(score: float, max_score: float = 5.0) -> int:
    if max_score <= 0:
        return 0
    return min(int(score / max_score * 100), 99)


def _take_profit(entry: float, stop: float, rr: float = 2.0) -> float:
    return entry + abs(entry - stop) * rr


def _pnl_emoji(pnl: float) -> str:
    return "🟢" if pnl >= 0 else "🔴"


def _status_line() -> str:
    with _state_lock:
        running = _bot_running
    return "✅ Работает" if running else "⏸ Остановлен"


# ── Signal message builder ────────────────────────────────────────────────────

def _build_signal_text(ticker: str, signal, ind) -> str:
    action = signal.action
    dir_emoji = "🟢" if action == Action.BUY else "🔴"
    action_str = action.value

    price = ind.close
    atr = ind.atr or 0.0
    mult = config.risk.atr_stop_multiplier

    if action == Action.BUY:
        stop = price - atr * mult
        tp = _take_profit(price, stop)
    else:
        stop = price + atr * mult
        tp = price - abs(price - stop) * 2.0

    stop_pct = (stop - price) / price * 100 if price else 0.0
    tp_pct = (tp - price) / price * 100 if price else 0.0
    conf = _confidence(
        signal.buy_score if action == Action.BUY else signal.sell_score
    )

    rules_str = " + ".join(r.name for r in signal.triggered_rules[:3]) or "—"

    lines = [
        f"{dir_emoji} <b>{action_str} {ticker}</b>",
        f"Цена: <b>{_fmt(price)} ₽</b>",
        f"Уверенность: <b>{conf}%</b>",
        f"Причина: {rules_str}",
        f"Стоп-лосс: {_fmt(stop)} ₽ ({stop_pct:+.1f}%)",
        f"Тейк-профит: {_fmt(tp)} ₽ ({tp_pct:+.1f}%)",
        "",
        f"RSI: <code>{_fmt(ind.rsi)}</code>  "
        f"MACD hist: <code>{_fmt(ind.macd_hist)}</code>  "
        f"ADX: <code>{_fmt(ind.adx)}</code>",
    ]
    return "\n".join(lines)


# ── Cross-event-loop notification (PTB v20+ safe) ────────────────────────────

async def _send(text: str, reply_markup=None, parse_mode: str = "HTML") -> None:
    """
    Send a message from ANY async context.

    Creates a new Bot instance with its own httpx session per call.
    This is the only safe pattern when calling from an event loop that is
    different from the one running Application (trading loop vs bot thread).

    Два режима отказа Telegram роняли ВСЁ сообщение в HTTP 400, оставляя одну
    строку в логе: длина больше 4096 и битый HTML. Второе случалось само —
    любой текст исключения с «<» попадал в сводку через _event(). Поэтому
    длина срезается заранее, а на ошибке разметки идёт повтор ПЛАИН-ТЕКСТОМ:
    экранировать здесь нельзя, часть вызывающих (send_signal_alert, дашборд)
    ставит HTML намеренно, и escape сломал бы их вывод. Лучше сообщение без
    форматирования, чем отсутствие сообщения.
    """
    if not config.telegram.token or not config.telegram.chat_id:
        return
    text = truncate(text)
    try:
        async with Bot(token=config.telegram.token) as bot:
            await bot.send_message(
                chat_id=config.telegram.chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
    except Exception as exc:
        if parse_mode is None:
            logger.error("Telegram send error: %s", exc)
            return
        logger.warning("Telegram отклонил сообщение (%s) — повтор без разметки", exc)
        await _send(text, reply_markup=reply_markup, parse_mode=None)


async def send_notification(text: str) -> None:
    """Public API — called from trading loop for trade notifications."""
    await _send(text)


# ── Signal alert with inline confirm / reject buttons ────────────────────────

async def send_signal_alert(ticker: str, signal, ind) -> None:
    """
    Send a BUY/SELL signal alert.

    If auto-trading is OFF  → include [Confirm] [Reject] buttons.
    If auto-trading is ON   → informational only (trade already executing).
    """
    if signal.action not in (Action.BUY, Action.SELL):
        return

    # Deduplicate: one alert per ticker+action per hour
    now_key = datetime.now().strftime("%Y%m%d%H")
    sig_key = f"{ticker}:{signal.action.value}:{now_key}"
    if sig_key in _sent_signal_keys:
        return
    _sent_signal_keys.add(sig_key)

    text = _build_signal_text(ticker, signal, ind)
    with _state_lock:
        auto = _bot_running

    if auto:
        await _send(
            f"📡 <b>Сигнал</b> (авторежим — исполняется автоматически)\n\n{text}"
        )
        return

    # Manual confirmation mode
    try:
        from broker.tinkoff_client import tinkoff_client
        instrument = await asyncio.to_thread(tinkoff_client.find_instrument, ticker)
    except Exception:
        instrument = None

    trade_id = str(uuid.uuid4())[:8]
    _pending_trades[trade_id] = {
        "ticker": ticker,
        "figi": instrument["figi"] if instrument else None,
        "lot": instrument.get("lot", 1) if instrument else 1,
        "action": signal.action.value,
        "price": ind.close,
        "ind": ind,
        "signal": signal,
        "instrument": instrument,
        "created_at": datetime.now(timezone.utc),
    }

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Подтвердить сделку",
            callback_data=f"confirm_trade:{trade_id}",
        ),
        InlineKeyboardButton(
            "❌ Отклонить",
            callback_data=f"reject_trade:{trade_id}",
        ),
    ]])
    await _send(text, reply_markup=kb)


async def send_stop_loss_alert(ticker: str, price: float, pnl: float) -> None:
    text = (
        f"🚨 <b>Стоп-лосс сработал: {ticker}</b>\n\n"
        f"Цена закрытия: <b>{_fmt(price)} ₽</b>\n"
        f"PnL: {_fmt_money(pnl)}\n\n"
        f"<i>Позиция закрыта по стоп-лоссу</i>"
    )
    await _send(text)


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — приветствие."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /start", update.effective_user.id)
    text = (
        "🤖 <b>QuantFlow Trading Bot</b>\n"
        "─────────────────────────\n\n"
        "<b>Торговля:</b>\n"
        "/start_trading — запустить авторежим\n"
        "/stop — остановить авторежим\n"
        "/status — статус бота и позиции\n\n"
        "<b>Анализ:</b>\n"
        "/signal SBER — сигнал по тикеру\n"
        "/signals — все актуальные сигналы\n"
        "/portfolio — портфель Tinkoff\n"
        "/backtest — бэктест за 30 дней\n\n"
        "<b>Прочее:</b>\n"
        "/help — подробная справка\n\n"
        "📡 Алерты приходят автоматически при:\n"
        "• новом сигнале BUY/SELL\n"
        "• исполнении сделки\n"
        "• просадке портфеля > 5%\n"
        "• ежедневный отчёт в 19:00 МСК"
    )
    await update.message.reply_html(text)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — полная справка."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /help", update.effective_user.id)
    text = (
        "❓ <b>Справка QuantFlow Bot</b>\n"
        "─────────────────────────\n\n"
        "<b>Команды управления:</b>\n"
        "/start_trading — включить автоторговлю\n"
        "/stop — выключить автоторговлю\n\n"
        "<b>Информация:</b>\n"
        "/status — статус, позиции, P&L сегодня\n"
        "/portfolio — полный портфель из Tinkoff API\n"
        "/signals — сигналы по всем тикерам\n"
        "/signal &lt;TICKER&gt; — сигнал по конкретному тикеру\n"
        "/backtest — бэктест за последние 30 дней\n\n"
        "<b>Режимы работы:</b>\n"
        "• <b>Авторежим</b> (start_trading) — бот исполняет сделки автоматически\n"
        "• <b>Ручной режим</b> (stop) — каждый сигнал требует подтверждения\n\n"
        "<b>Кнопки подтверждения:</b>\n"
        "В ручном режиме к каждому сигналу BUY/SELL прилагаются кнопки:\n"
        "  [✅ Подтвердить сделку] [❌ Отклонить]\n\n"
        "<b>Автоматические алерты:</b>\n"
        "🔔 Новый BUY/SELL сигнал\n"
        "✅ Исполнение сделки\n"
        "🚨 Срабатывание стоп-лосса\n"
        "⚠️ Просадка портфеля > 5%\n"
        "📊 Ежедневный отчёт в 19:00 МСК"
    )
    await update.message.reply_html(text)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — текущий статус бота."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /status", update.effective_user.id)
    positions = risk_manager.open_positions
    daily_pnl = risk_manager.daily_pnl
    mode = "SANDBOX" if config.tinkoff.sandbox else "LIVE"

    drawdown_pct = 0.0
    if _portfolio_peak > 0:
        try:
            from services.tinkoff.portfolio import get_portfolio_summary
            summary = await asyncio.to_thread(get_portfolio_summary)
            drawdown_pct = (summary.total_value - _portfolio_peak) / _portfolio_peak * 100
        except Exception:
            pass

    pnl_emoji = _pnl_emoji(daily_pnl)
    dd_emoji = "⚠️" if drawdown_pct < -5.0 else ("🟢" if drawdown_pct >= 0 else "🟡")

    lines = [
        "📊 <b>QuantFlow Bot</b>",
        "─────────────────────────",
        f"Статус: {_status_line()}",
        f"Режим: {mode}",
        f"Тикеры: {', '.join(config.tickers)}",
        f"Позиций открыто: {len(positions)}/{config.risk.max_open_positions}",
        f"{pnl_emoji} P&L сегодня: <b>{_fmt_money(daily_pnl)}</b>",
        f"{dd_emoji} Просадка: {drawdown_pct:+.1f}%",
        "",
    ]

    if positions:
        lines.append("─── Открытые позиции ───")
        for ticker, pos in positions.items():
            lines.append(
                f"  📌 <b>{ticker}</b>  вход {_fmt(pos.entry_price)} ₽  "
                f"стоп {_fmt(pos.stop_price)} ₽  лотов {pos.lot_size}"
            )
    else:
        lines.append("Открытых позиций нет")

    await update.message.reply_html("\n".join(lines))


async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/signal TICKER — сигнал по конкретному тикеру."""
    if not await require_auth(update, ctx):
        return
    if not ctx.args:
        await update.message.reply_html(
            "⚠️ Укажите тикер: <code>/signal SBER</code>"
        )
        return

    ticker = ctx.args[0].upper()
    logger.info("User %s: /signal %s", update.effective_user.id, ticker)
    await update.message.reply_html(f"⏳ Загружаю данные для <b>{ticker}</b>…")

    try:
        df = await asyncio.to_thread(loader.get_candles, ticker, interval="1h")
        if df.empty:
            await update.message.reply_html(f"❌ Нет данных для <b>{ticker}</b>")
            return

        ind = indicator_engine.latest(df)
        signal = rules_engine.evaluate(ind)

        text = _build_signal_text(ticker, signal, ind)

        if signal.action in (Action.BUY, Action.SELL):
            trade_id = str(uuid.uuid4())[:8]
            try:
                from broker.tinkoff_client import tinkoff_client
                instrument = tinkoff_client.find_instrument(ticker)
            except Exception:
                instrument = None

            _pending_trades[trade_id] = {
                "ticker": ticker,
                "figi": instrument["figi"] if instrument else None,
                "lot": instrument.get("lot", 1) if instrument else 1,
                "action": signal.action.value,
                "price": ind.close,
                "ind": ind,
                "signal": signal,
                "instrument": instrument,
                "created_at": datetime.now(timezone.utc),
            }
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "✅ Подтвердить сделку",
                    callback_data=f"confirm_trade:{trade_id}",
                ),
                InlineKeyboardButton(
                    "❌ Отклонить",
                    callback_data=f"reject_trade:{trade_id}",
                ),
            ]])
            await update.message.reply_html(text, reply_markup=kb)
        else:
            await update.message.reply_html(f"⚪ <b>HOLD {ticker}</b>\n\n{text}")

    except Exception as exc:
        logger.error("/signal %s error: %s", ticker, exc)
        await update.message.reply_html(f"❌ Ошибка: {exc}")


async def cmd_signals(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/signals — сигналы по всем тикерам."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /signals", update.effective_user.id)
    await update.message.reply_html("⏳ Анализирую все тикеры…")

    _EMOJI = {Action.BUY: "🟢", Action.SELL: "🔴", Action.HOLD: "⚪"}
    lines = ["📡 <b>Актуальные сигналы</b>", "─────────────────────────"]

    for ticker in config.tickers:
        try:
            df = await asyncio.to_thread(loader.get_candles, ticker, interval="1h")
            if df.empty:
                lines.append(f"⚫ <b>{ticker}</b>: нет данных")
                continue
            ind = indicator_engine.latest(df)
            sig = rules_engine.evaluate(ind)
            emoji = _EMOJI[sig.action]
            conf = _confidence(
                sig.buy_score if sig.action == Action.BUY else sig.sell_score
            )
            lines.append(
                f"{emoji} <b>{ticker}</b>: {sig.action.value}  "
                f"({conf}%)  цена {_fmt(ind.close)} ₽  "
                f"RSI {_fmt(ind.rsi)}"
            )
        except Exception as exc:
            logger.error("/signals ticker %s: %s", ticker, exc)
            lines.append(f"⚠️ <b>{ticker}</b>: ошибка")

    await update.message.reply_html("\n".join(lines))


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/stop — остановить автоторговлю (перейти в ручной режим)."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /stop", update.effective_user.id)
    set_bot_running(False)
    await update.message.reply_html(
        "⏸ <b>Автоторговля остановлена</b>\n\n"
        "Теперь каждый сигнал требует ручного подтверждения.\n"
        "Для возобновления: /start_trading"
    )


async def cmd_start_trading(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/start_trading — включить автоторговлю."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /start_trading", update.effective_user.id)
    set_bot_running(True)
    mode = "SANDBOX" if config.tinkoff.sandbox else "⚠️ LIVE"
    await update.message.reply_html(
        f"▶ <b>Автоторговля запущена</b>\n\n"
        f"Режим: <b>{mode}</b>\n"
        f"Тикеры: {', '.join(config.tickers)}\n"
        f"Интервал: {config.poll_interval} с\n\n"
        f"Сигналы будут исполняться автоматически.\n"
        f"Для остановки: /stop"
    )


async def cmd_portfolio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/portfolio — портфель из Tinkoff API."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /portfolio", update.effective_user.id)
    await update.message.reply_html("⏳ Загружаю портфель из Tinkoff…")

    try:
        from services.tinkoff.portfolio import get_portfolio_summary
        from services.tinkoff.client import TinkoffNotConfigured, TinkoffSDKError

        summary = await asyncio.to_thread(get_portfolio_summary)

        pnl_emoji = _pnl_emoji(summary.total_yield)
        lines = [
            "💼 <b>Портфель Tinkoff</b>",
            "─────────────────────────",
            f"💰 Стоимость: <b>{summary.total_value:,.2f} ₽</b>".replace(",", " "),
            f"{pnl_emoji} Доходность: <b>{_fmt_money(summary.total_yield)}</b> "
            f"({summary.total_yield_pct:+.2f}%)",
            f"📌 Позиций: {summary.positions_count}",
            "",
        ]

        if summary.positions:
            lines.append("─── Позиции ───")
            for pos in sorted(
                summary.positions, key=lambda p: p.current_value, reverse=True
            )[:15]:
                pnl_icon = "🟢" if pos.expected_yield >= 0 else "🔴"
                lines.append(
                    f"{pnl_icon} <b>{pos.ticker}</b>  "
                    f"{pos.quantity:.0f} шт  "
                    f"→ {pos.current_price:.2f} ₽  "
                    f"PnL: {_fmt_money(pos.expected_yield)} "
                    f"({pos.expected_yield_pct:+.2f}%)"
                )
        else:
            lines.append("Портфель пуст")

        lines += [
            "",
            f"<i>Режим: {'SANDBOX' if config.tinkoff.sandbox else 'LIVE'}</i>",
        ]
        await update.message.reply_html("\n".join(lines))

    except Exception as exc:
        logger.error("/portfolio error: %s", exc)
        _hint = ""
        if "не настроен" in str(exc).lower() or "token" in str(exc).lower():
            _hint = "\n\nПроверьте TINKOFF_TOKEN и TINKOFF_ACCOUNT_ID в .env"
        await update.message.reply_html(f"❌ Ошибка загрузки портфеля:\n{exc}{_hint}")


async def cmd_backtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/backtest — быстрый бэктест за последние 30 дней."""
    if not await require_auth(update, ctx):
        return
    logger.info("User %s: /backtest", update.effective_user.id)
    await update.message.reply_html(
        f"⏳ Запускаю бэктест за 30 дней по {len(config.tickers)} тикерам…\n"
        f"<i>Это займёт несколько секунд.</i>"
    )

    def _run():
        from backtest.engine import BacktestEngine
        from datetime import date, timedelta

        engine = BacktestEngine()
        end = date.today()
        start = end - timedelta(days=30)
        results = []

        for ticker in config.tickers:
            try:
                df = loader.get_candles(ticker, interval="1d", start=start, end=end)
                if len(df) < 5:
                    continue
                res = engine.run(ticker, df)
                results.append((ticker, res))
            except Exception as exc:
                logger.warning("Backtest %s: %s", ticker, exc)

        return results

    try:
        results = await asyncio.to_thread(_run)

        if not results:
            await update.message.reply_html("❌ Нет данных для бэктеста.")
            return

        lines = [
            "📊 <b>Бэктест — последние 30 дней</b>",
            "─────────────────────────────────────",
        ]
        total_pnl = 0.0
        for ticker, res in results:
            pnl_icon = _pnl_emoji(res.total_pnl)
            wr = (
                f"{res.win_rate:.0f}%"
                if hasattr(res, "win_rate") and res.win_rate
                else "—"
            )
            dd = (
                f"{res.max_drawdown:.1f}%"
                if hasattr(res, "max_drawdown") and res.max_drawdown
                else "—"
            )
            lines.append(
                f"{pnl_icon} <b>{ticker}</b>  "
                f"PnL: {_fmt_money(res.total_pnl)}  "
                f"Сделок: {res.total_trades}  "
                f"WR: {wr}  "
                f"DD: {dd}"
            )
            total_pnl += res.total_pnl

        lines += [
            "─────────────────────────────────────",
            f"{'🟢' if total_pnl >= 0 else '🔴'} <b>Итого: {_fmt_money(total_pnl)}</b>",
            f"<i>Период: 30 дней  |  Тикеров: {len(results)}</i>",
        ]
        await update.message.reply_html("\n".join(lines))

    except Exception as exc:
        logger.error("/backtest error: %s", exc)
        await update.message.reply_html(f"❌ Ошибка бэктеста: {exc}")


# ── Inline button callbacks ───────────────────────────────────────────────────

async def cb_confirm_trade(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """✅ Подтвердить сделку."""
    if not await require_auth(update, ctx):
        return
    from broker.tinkoff_client import tinkoff_client
    from learning.feedback import feedback_store, TradeRecord

    query = update.callback_query
    await query.answer()

    trade_id = query.data.split(":", 1)[1]
    trade = _pending_trades.pop(trade_id, None)

    if trade is None:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_html("⚠️ Сделка устарела или уже обработана.")
        return

    ticker = trade["ticker"]
    figi = trade.get("figi")
    action = trade["action"]        # "BUY" or "SELL"
    lot = trade.get("lot", 1)
    ind = trade["ind"]
    signal = trade["signal"]

    logger.info("User %s confirmed trade: %s %s", update.effective_user.id, action, ticker)
    await query.edit_message_reply_markup(reply_markup=None)

    if not figi:
        await query.message.reply_html(
            f"❌ Инструмент <b>{ticker}</b> не найден в Tinkoff. Сделка отменена."
        )
        return

    # Risk check — get portfolio value, size position, validate rules
    try:
        balance = await asyncio.to_thread(tinkoff_client.get_balance)
        pos = risk_manager.calculate_position(
            ticker=ticker,
            entry_price=ind.close,
            atr=ind.atr or 1.0,
            portfolio_value=balance,
            lot_size=lot,
            direction="long" if action == "BUY" else "short",
        )
        if pos is None:
            await query.message.reply_html(
                f"⚠️ Не удалось рассчитать размер позиции для <b>{ticker}</b>."
            )
            return

        check = risk_manager.check_trade_allowed(ticker, balance, pos)
        if not check.allowed:
            await query.message.reply_html(
                f"🛡 <b>Сделка заблокирована риск-менеджером</b>\n{check.reason}"
            )
            return
    except Exception as exc:
        logger.error("Risk check error: %s", exc)
        await query.message.reply_html(f"❌ Ошибка проверки риска: {exc}")
        return

    # Execute order via tinkoff_client synchronous SDK (runs in thread)
    try:
        order_id = await asyncio.to_thread(
            tinkoff_client.place_market_order,
            figi,
            pos.lot_size,
            action.lower(),       # "buy" or "sell"
        )
    except Exception as exc:
        logger.error("Order placement error: %s", exc)
        await query.message.reply_html(f"❌ Ошибка выставления заявки: {exc}")
        return

    if order_id:
        risk_manager.register_open(pos)
        feedback_store.record_open(TradeRecord(
            ticker=ticker,
            direction=action,
            entry_price=ind.close,
            shares=pos.shares,
            stop_price=pos.stop_price,
            signal_rules=[r.name for r in signal.triggered_rules],
            buy_score=signal.buy_score,
            sell_score=signal.sell_score,
            rsi=ind.rsi,
            macd_hist=ind.macd_hist,
            adx=ind.adx,
            atr=ind.atr,
        ))
        dir_emoji = "🟢" if action == "BUY" else "🔴"
        await query.message.reply_html(
            f"✅ <b>Заявка исполнена</b>\n\n"
            f"{dir_emoji} {action} <b>{ticker}</b>\n"
            f"Цена: {_fmt(ind.close)} ₽\n"
            f"Лотов: {pos.lot_size}  |  Акций: {pos.shares}\n"
            f"Стоп-лосс: {_fmt(pos.stop_price)} ₽\n"
            f"ID заявки: <code>{order_id}</code>"
        )
    else:
        await query.message.reply_html(
            f"❌ Брокер отклонил заявку {action} {ticker}. Проверьте баланс и лимиты."
        )


async def cb_reject_trade(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """❌ Отклонить сделку."""
    if not await require_auth(update, ctx):
        return
    query = update.callback_query
    await query.answer("Сделка отклонена.")

    trade_id = query.data.split(":", 1)[1]
    trade = _pending_trades.pop(trade_id, None)

    ticker = trade["ticker"] if trade else "?"
    logger.info("User %s rejected trade: %s", update.effective_user.id, ticker)

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_html(
        f"❌ Сделка <b>{ticker}</b> отклонена."
    )


# ── Background monitoring tasks ───────────────────────────────────────────────

async def _signal_monitor_loop(app: Application) -> None:
    """
    Фоновый мониторинг сигналов.

    Проверяет все тикеры каждые 5 минут в рабочие часы.
    Отправляет алерт при новом BUY/SELL, не повторяя его в течение часа.
    """
    global _sent_signal_keys

    while True:
        await asyncio.sleep(300)  # 5 минут

        now = datetime.now(timezone.utc)
        if not (7 <= now.hour < 16):
            continue

        current_hour = now.strftime("%Y%m%d%H")

        # Prune stale pending trades older than 2 hours
        cutoff = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
        stale = [
            tid for tid, t in _pending_trades.items()
            if (cutoff - t["created_at"]).total_seconds() > 7200
        ]
        for tid in stale:
            _pending_trades.pop(tid, None)

        for ticker in config.tickers:
            try:
                df = await asyncio.to_thread(
                    loader.get_candles, ticker, interval="1h"
                )
                if df.empty:
                    continue

                ind = indicator_engine.latest(df)
                sig = rules_engine.evaluate(ind)

                if sig.action not in (Action.BUY, Action.SELL):
                    continue

                # Key includes action: one alert per ticker+action per hour
                sig_key = f"{ticker}:{sig.action.value}:{current_hour}"
                if sig_key in _sent_signal_keys:
                    continue

                _sent_signal_keys.add(sig_key)
                logger.info("Signal monitor: %s %s", sig.action.value, ticker)

                text = _build_signal_text(ticker, sig, ind)
                with _state_lock:
                    auto = _bot_running

                if auto:
                    await app.bot.send_message(
                        chat_id=config.telegram.chat_id,
                        text=f"📡 <b>Сигнал</b> (авторежим)\n\n{text}",
                        parse_mode="HTML",
                    )
                else:
                    trade_id = str(uuid.uuid4())[:8]
                    try:
                        from broker.tinkoff_client import tinkoff_client
                        instrument = await asyncio.to_thread(
                            tinkoff_client.find_instrument, ticker
                        )
                    except Exception:
                        instrument = None

                    _pending_trades[trade_id] = {
                        "ticker": ticker,
                        "figi": instrument["figi"] if instrument else None,
                        "lot": instrument.get("lot", 1) if instrument else 1,
                        "action": sig.action.value,
                        "price": ind.close,
                        "ind": ind,
                        "signal": sig,
                        "instrument": instrument,
                        "created_at": datetime.now(timezone.utc),
                    }
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "✅ Подтвердить сделку",
                            callback_data=f"confirm_trade:{trade_id}",
                        ),
                        InlineKeyboardButton(
                            "❌ Отклонить",
                            callback_data=f"reject_trade:{trade_id}",
                        ),
                    ]])
                    await app.bot.send_message(
                        chat_id=config.telegram.chat_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=kb,
                    )

            except Exception as exc:
                logger.error("Signal monitor %s: %s", ticker, exc)


async def _drawdown_monitor_loop(app: Application) -> None:
    """
    Мониторинг просадки портфеля каждые 10 минут.
    Отправляет ⚠️-алерт при просадке > 5% от пика сессии.
    """
    global _portfolio_peak, _drawdown_alerted

    while True:
        await asyncio.sleep(600)  # 10 минут

        try:
            from services.tinkoff.portfolio import get_portfolio_summary
            from services.tinkoff.client import TinkoffNotConfigured, TinkoffSDKError

            summary = await asyncio.to_thread(get_portfolio_summary)
            value = summary.total_value

            if value > _portfolio_peak:
                _portfolio_peak = value
                _drawdown_alerted = False
                continue

            if _portfolio_peak <= 0:
                continue

            dd_pct = (value - _portfolio_peak) / _portfolio_peak * 100

            if dd_pct < -5.0 and not _drawdown_alerted:
                _drawdown_alerted = True
                await app.bot.send_message(
                    chat_id=config.telegram.chat_id,
                    text=(
                        f"⚠️ <b>Предупреждение: просадка портфеля</b>\n\n"
                        f"Текущая просадка: <b>{dd_pct:.1f}%</b>\n"
                        f"Текущая стоимость: {value:,.0f} ₽\n"
                        f"Пик сессии: {_portfolio_peak:,.0f} ₽\n\n"
                        f"Рекомендуется проверить позиции.\n"
                        f"/portfolio — посмотреть детали"
                    ).replace(",", " "),
                    parse_mode="HTML",
                )

        except Exception as exc:
            if "не настроен" not in str(exc).lower():
                logger.warning("Drawdown monitor error: %s", exc)


async def _daily_report_loop(app: Application) -> None:
    """
    Ежедневный отчёт в 19:00 МСК (16:00 UTC).
    Проверяет время каждую минуту.
    """
    reported_date: Optional[date] = None

    while True:
        await asyncio.sleep(60)

        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()

        if not (now_utc.hour == 16 and now_utc.minute < 5):
            continue
        if reported_date == today:
            continue

        reported_date = today

        try:
            positions = risk_manager.open_positions
            daily_pnl = risk_manager.daily_pnl
            stats = feedback_store.get_stats()

            total = int(stats.get("total_trades") or 0)
            wins = int(stats.get("winning_trades") or 0)
            max_win = float(stats.get("max_win") or 0)
            max_loss = float(stats.get("max_loss") or 0)

            today_str = today.strftime("%d.%m.%Y")
            pnl_icon = _pnl_emoji(daily_pnl)

            report_lines = [
                f"📊 <b>Ежедневный отчёт — {today_str}</b>",
                "─────────────────────────",
                f"{pnl_icon} P&L сегодня: <b>{_fmt_money(daily_pnl)}</b>",
                f"📌 Позиций открыто: {len(positions)}",
                "",
                "─── Статистика (всё время) ───",
                f"Всего сделок: {total}",
            ]

            if total > 0:
                wr = wins / total * 100
                report_lines += [
                    f"Прибыльных: {wins} ({wr:.0f}%)",
                    f"Лучшая: {_fmt_money(max_win)}",
                    f"Худшая: {_fmt_money(max_loss)}",
                ]

            report_lines += [
                "",
                f"Режим: {'SANDBOX' if config.tinkoff.sandbox else 'LIVE'}",
                f"Статус бота: {_status_line()}",
            ]

            await app.bot.send_message(
                chat_id=config.telegram.chat_id,
                text="\n".join(report_lines),
                parse_mode="HTML",
            )
            logger.info("Daily report sent for %s", today)

        except Exception as exc:
            logger.error("Daily report error: %s", exc)


async def _post_init(app: Application) -> None:
    """Запускает фоновые задачи после инициализации Application."""
    if config.telegram.chat_id:
        # asyncio.ensure_future schedules on the running loop without
        # triggering PTB's "not running" warning from app.create_task
        asyncio.ensure_future(_signal_monitor_loop(app))
        asyncio.ensure_future(_drawdown_monitor_loop(app))
        asyncio.ensure_future(_daily_report_loop(app))
        logger.info("Background monitoring tasks started")
    else:
        logger.warning("TELEGRAM_CHAT_ID not set — background tasks disabled")


# ── Application factory ───────────────────────────────────────────────────────

def build_app() -> Application:
    """Собрать и настроить Application со всеми хендлерами."""
    app = (
        Application.builder()
        .token(config.telegram.token)
        .post_init(_post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start",         cmd_start))
    app.add_handler(CommandHandler("help",          cmd_help))
    app.add_handler(CommandHandler("status",        cmd_status))
    app.add_handler(CommandHandler("signal",        cmd_signal))
    app.add_handler(CommandHandler("signals",       cmd_signals))
    app.add_handler(CommandHandler("stop",          cmd_stop))
    app.add_handler(CommandHandler("start_trading", cmd_start_trading))
    app.add_handler(CommandHandler("portfolio",     cmd_portfolio))
    app.add_handler(CommandHandler("backtest",      cmd_backtest))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(cb_confirm_trade, pattern=r"^confirm_trade:"))
    app.add_handler(CallbackQueryHandler(cb_reject_trade,  pattern=r"^reject_trade:"))

    return app


# ── Public API (called from main.py and other modules) ────────────────────────

def set_bot_running(state: bool) -> None:
    global _bot_running
    with _state_lock:
        _bot_running = state
    logger.info("Bot running state → %s", state)


def run_bot() -> None:
    """Запустить бот в блокирующем режиме. Вызывать из отдельного потока."""
    if not config.telegram.token:
        logger.error("TELEGRAM_TOKEN не настроен — бот не запущен")
        return
    app = build_app()
    logger.info("Telegram bot polling started (@%s mode)", "sandbox" if config.tinkoff.sandbox else "live")
    app.run_polling(drop_pending_updates=True, stop_signals=[])
    logger.info("Telegram bot stopped")


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    if not config.telegram.token:
        print("❌ TELEGRAM_TOKEN не настроен в .env")
        sys.exit(1)
    if not config.telegram.chat_id:
        print("❌ TELEGRAM_CHAT_ID не настроен в .env")
        sys.exit(1)

    print(f"🤖 Запуск QuantFlow Telegram Bot")
    print(f"   Token: {config.telegram.token[:10]}…")
    print(f"   Chat:  {config.telegram.chat_id}")
    print(f"   Mode:  {'SANDBOX' if config.tinkoff.sandbox else 'LIVE'}")
    print(f"   Tickers: {', '.join(config.tickers)}")
    print()

    run_bot()
