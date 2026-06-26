"""Главный файл запуска торгового бота."""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from config import config
from data.loader import loader
from signals.indicators import indicator_engine
from signals.rules_engine import rules_engine, Action
from risk.risk_manager import risk_manager
from broker.tinkoff_client import tinkoff_client
from learning.feedback import feedback_store, TradeRecord
from ui.telegram_bot import send_notification, set_bot_running, run_bot

logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_shutdown = asyncio.Event()


def _handle_signal(sig, frame):
    logger.info("Получен сигнал %s — завершаем работу...", sig)
    _shutdown.set()


async def trading_loop():
    """Основной торговый цикл: опрос сигналов по всем тикерам."""
    logger.info("Торговый цикл запущен. Тикеры: %s", config.tickers)
    set_bot_running(True)

    # Сброс дневного PnL при старте
    risk_manager.reset_daily()

    while not _shutdown.is_set():
        now = datetime.now()
        # MOEX работает с 10:00 до 18:45 МСК (07:00-15:45 UTC)
        if not (7 <= now.hour < 16):
            logger.debug("Биржа закрыта (%s UTC), ожидаем...", now.strftime("%H:%M"))
            await asyncio.sleep(300)
            continue

        for ticker in config.tickers:
            if _shutdown.is_set():
                break
            await _process_ticker(ticker)

        await asyncio.sleep(config.poll_interval)

    set_bot_running(False)
    logger.info("Торговый цикл остановлен")


async def _process_ticker(ticker: str):
    """Обработать один тикер: загрузить данные, оценить сигнал, выполнить сделку."""
    try:
        df = loader.get_candles(ticker, interval="1h")
        if df.empty:
            return

        indicators = indicator_engine.latest(df)
        signal = rules_engine.evaluate(indicators)
        open_positions = risk_manager.open_positions

        logger.debug("[%s] %s", ticker, signal)

        # --- Сигнал на покупку ---
        if signal.action == Action.BUY and ticker not in open_positions:
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
                logger.info("[%s] Сделка запрещена: %s", ticker, check.reason)
                return

            instrument = tinkoff_client.find_instrument(ticker)
            if instrument is None:
                logger.error("[%s] Инструмент не найден в Т-Инвестиции", ticker)
                return

            order_id = tinkoff_client.place_market_order(
                figi=instrument["figi"],
                quantity=pos.lot_size,
                direction="buy",
            )
            if order_id:
                risk_manager.register_open(pos)
                trade_id = feedback_store.record_open(TradeRecord(
                    ticker=ticker,
                    direction="BUY",
                    entry_price=indicators.close,
                    shares=pos.shares,
                    stop_price=pos.stop_price,
                    signal_rules=[r.name for r in signal.triggered_rules],
                    buy_score=signal.buy_score,
                    sell_score=signal.sell_score,
                    rsi=indicators.rsi,
                    macd_hist=indicators.macd_hist,
                    adx=indicators.adx,
                    atr=indicators.atr,
                ))
                msg = (
                    f"🟢 ПОКУПКА {ticker}\n"
                    f"Цена: {indicators.close:.2f} руб.\n"
                    f"Лотов: {pos.lot_size} | Акций: {pos.shares}\n"
                    f"Стоп: {pos.stop_price:.2f} руб.\n"
                    f"Счёт: {signal.buy_score:.2f}"
                )
                await send_notification(msg)
                logger.info("[%s] Куплено %d лотов @ %.2f", ticker, pos.lot_size, indicators.close)

        # --- Сигнал на продажу ---
        elif signal.action == Action.SELL and ticker in open_positions:
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
                if pos.db_id if hasattr(pos, "db_id") else None:
                    feedback_store.record_close(pos.db_id, indicators.close)

                msg = (
                    f"🔴 ПРОДАЖА {ticker}\n"
                    f"Цена: {indicators.close:.2f} руб.\n"
                    f"PnL: {pnl:+.2f} руб.\n"
                    f"Счёт: {signal.sell_score:.2f}"
                )
                await send_notification(msg)
                logger.info("[%s] Продано @ %.2f, PnL=%.2f", ticker, indicators.close, pnl)

        # --- Скользящий стоп ---
        elif ticker in open_positions:
            new_stop = risk_manager.trailing_stop(ticker, indicators.close, indicators.atr)
            if new_stop:
                logger.debug("[%s] Скользящий стоп обновлён: %.2f", ticker, new_stop)

    except Exception as exc:
        logger.error("Ошибка обработки тикера %s: %s", ticker, exc, exc_info=True)


def main():
    logger.info("=== Торговый бот MOEX запускается ===")
    logger.info("Режим Tinkoff: %s", "SANDBOX" if config.tinkoff.sandbox else "PRODUCTION")
    logger.info("Тикеры: %s", ", ".join(config.tickers))

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if "--backtest" in sys.argv:
        _run_backtest()
        return

    if "--bot-only" in sys.argv:
        run_bot()
        return

    # Запускаем торговый цикл и Telegram-бот параллельно
    import threading
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    asyncio.run(trading_loop())
    logger.info("=== Торговый бот остановлен ===")


def _run_backtest():
    """Быстрый бэктест по всем тикерам из конфига."""
    from backtest.engine import BacktestEngine
    from datetime import date, timedelta

    engine = BacktestEngine()
    end = date.today()
    start = end - timedelta(days=365)

    for ticker in config.tickers:
        logger.info("Бэктест: %s (%s — %s)", ticker, start, end)
        df = loader.get_candles(ticker, interval="1h", start=start, end=end)
        if df.empty:
            logger.warning("Нет данных для бэктеста %s", ticker)
            continue
        result = engine.run(ticker, df)
        print(result.summary())


if __name__ == "__main__":
    main()
