"""Main entry point — trading loop + Telegram bot."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path

from config import config
from data.loader import loader
from signals.indicators import indicator_engine
from signals.rules_engine import rules_engine, Action
from risk.risk_manager import risk_manager
from broker.tinkoff_client import tinkoff_client
from learning.feedback import feedback_store, TradeRecord
from services.bot_engine import trading_engine, BotStatus
from tg.bot import run_bot, send_notification
from tg.notifications.dispatcher import (
    notify_trade_open,
    notify_trade_close,
    notify_api_error,
    notify_risk_limit,
    notify_bot_started,
    notify_bot_stopped,
)

logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _handle_signal(sig, frame):
    logger.info("Signal %s received — shutting down", sig)
    trading_engine.stop()


async def trading_loop():
    logger.info("Trading loop started. Tickers: %s", config.tickers)
    trading_engine.start()
    risk_manager.reset_daily()
    trading_engine.reset_daily()

    await notify_bot_started()

    while not trading_engine.stop_event.is_set():
        await trading_engine.pause_event.wait()

        if trading_engine.stop_event.is_set():
            break

        now = datetime.now()
        if not (7 <= now.hour < 16):
            logger.debug("Exchange closed (%s UTC), waiting…", now.strftime("%H:%M"))
            await asyncio.sleep(300)
            continue

        for ticker in config.tickers:
            if trading_engine.stop_event.is_set():
                break
            await _process_ticker(ticker)

        trading_engine.record_cycle()
        await asyncio.sleep(config.poll_interval)

    await notify_bot_stopped()
    logger.info("Trading loop stopped")


async def _process_ticker(ticker: str):
    try:
        df = loader.get_candles(ticker, interval="1h")
        if df.empty:
            return

        indicators = indicator_engine.latest(df)
        sig = rules_engine.evaluate(indicators)
        open_positions = risk_manager.open_positions

        if sig.action == Action.BUY and ticker not in open_positions:
            balance = tinkoff_client.get_balance()
            pos = risk_manager.calculate_position(
                ticker=ticker,
                entry_price=indicators.close,
                atr=indicators.atr,
                portfolio_value=balance,
                lot_size=1,
            )
            if pos is None:
                return

            check = risk_manager.check_trade_allowed(ticker, balance, pos)
            if not check.allowed:
                logger.info("[%s] Trade blocked: %s", ticker, check.reason)
                await notify_risk_limit(f"[{ticker}] {check.reason}")
                return

            instrument = tinkoff_client.find_instrument(ticker)
            if instrument is None:
                logger.error("[%s] Instrument not found in Tinkoff", ticker)
                return

            order_id = tinkoff_client.place_market_order(
                figi=instrument["figi"],
                quantity=pos.lot_size,
                direction="buy",
            )
            if order_id:
                risk_manager.register_open(pos)
                trading_engine.record_trade()
                feedback_store.record_open(TradeRecord(
                    ticker=ticker,
                    direction="BUY",
                    entry_price=indicators.close,
                    shares=pos.shares,
                    stop_price=pos.stop_price,
                    signal_rules=[r.name for r in sig.triggered_rules],
                    buy_score=sig.buy_score,
                    sell_score=sig.sell_score,
                    rsi=indicators.rsi,
                    macd_hist=indicators.macd_hist,
                    adx=indicators.adx,
                    atr=indicators.atr,
                ))
                trading_engine.state.add_log(f"BUY {ticker} @ {indicators.close:.2f}")
                await notify_trade_open(ticker, indicators.close, pos.lot_size, pos.stop_price)

        elif sig.action == Action.SELL and ticker in open_positions:
            pos = open_positions[ticker]
            instrument = tinkoff_client.find_instrument(ticker)
            if instrument is None:
                return

            order_id = tinkoff_client.place_market_order(
                figi=instrument["figi"],
                quantity=pos.lot_size,
                direction="sell",
            )
            if order_id:
                pnl = risk_manager.register_close(ticker, indicators.close)
                trading_engine.record_trade()
                if hasattr(pos, "db_id") and pos.db_id:
                    feedback_store.record_close(pos.db_id, indicators.close)
                trading_engine.state.add_log(f"SELL {ticker} @ {indicators.close:.2f} PnL={pnl:+.2f}")
                await notify_trade_close(ticker, indicators.close, pnl)

        elif ticker in open_positions:
            risk_manager.trailing_stop(ticker, indicators.close, indicators.atr)

    except Exception as exc:
        logger.error("Error processing %s: %s", ticker, exc, exc_info=True)
        trading_engine.record_error(f"{ticker}: {exc}")


_PID_FILE = Path(__file__).parent / ".bot.pid"


def _acquire_pid_lock() -> bool:
    """Return False if another instance is already running."""
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, 0)  # signal 0 = проверка существования процесса
            logger.error(
                "Бот уже запущен (PID %d). Остановите предыдущий процесс: kill %d",
                pid, pid,
            )
            return False
        except (ProcessLookupError, ValueError):
            pass  # старый PID-файл от упавшего процесса
    _PID_FILE.write_text(str(os.getpid()))
    return True


def _release_pid_lock() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def main():
    logger.info("=== Trading Bot starting ===")
    logger.info("Tinkoff mode: %s", "SANDBOX" if config.tinkoff.sandbox else "LIVE")
    logger.info("Tickers: %s", ", ".join(config.tickers))

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if "--backtest" in sys.argv:
        _run_backtest()
        return

    if "--bot-only" in sys.argv:
        run_bot()
        return

    if not _acquire_pid_lock():
        sys.exit(1)

    try:
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

        asyncio.run(trading_loop())
    finally:
        _release_pid_lock()

    logger.info("=== Trading Bot stopped ===")


def _run_backtest():
    from backtest.engine import BacktestEngine
    from datetime import date, timedelta

    engine = BacktestEngine()
    end = date.today()
    start = end - timedelta(days=365)

    for ticker in config.tickers:
        logger.info("Backtest: %s (%s — %s)", ticker, start, end)
        df = loader.get_candles(ticker, interval="1h", start=start, end=end)
        if df.empty:
            logger.warning("No data for %s", ticker)
            continue
        result = engine.run(ticker, df)
        print(result.summary())


if __name__ == "__main__":
    main()
