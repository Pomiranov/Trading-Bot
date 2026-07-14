"""Main entry point — trading loop + Telegram bot."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Ensure bot/ directory is on sys.path so all internal imports resolve
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine as _create_engine

from config import config
from security.bootstrap import bootstrap_security
from data.loader import loader
from signals.indicators import IndicatorEngine
from signals.rules_engine import rules_engine, Action
from risk.risk_manager import risk_manager
from broker.tinkoff_client import tinkoff_client
from learning.feedback import feedback_store, TradeRecord
from learning.trading_orchestrator import TradingOrchestrator
from learning.memory_writer import Trade, Market, Direction, ExitReasonType
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

bootstrap_security(config, service_name="trading-bot")
logger = logging.getLogger(__name__)

_paper_sqlalchemy_engine = None


def _get_paper_engine():
    global _paper_sqlalchemy_engine
    if _paper_sqlalchemy_engine is None:
        _paper_sqlalchemy_engine = _create_engine(
            config.db.dsn, pool_size=2, max_overflow=2, pool_pre_ping=True
        )
    return _paper_sqlalchemy_engine


# Строим IndicatorEngine с параметрами из rules.yaml (periods, divergence params)
indicator_engine = IndicatorEngine(**{
    **rules_engine.indicator_params,
    **rules_engine.divergence_params,
})


def _handle_signal(sig, frame):
    logger.info("Signal %s received — shutting down", sig)
    trading_engine.stop()


async def trading_loop():
    logger.info("Trading loop started. Tickers: %s", config.tickers)
    trading_engine.start()
    risk_manager.reset_daily()
    trading_engine.reset_daily()

    orchestrator = TradingOrchestrator(dsn=config.db.dsn)
    await orchestrator.connect()

    await notify_bot_started()

    while not trading_engine.stop_event.is_set():
        # threading.Event.wait() is blocking — poll asynchronously instead
        if not trading_engine.pause_event.is_set():
            await asyncio.sleep(1)
            continue

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
            await _process_ticker(ticker, orchestrator)

        trading_engine.record_cycle()
        await asyncio.sleep(config.poll_interval)

    await orchestrator.disconnect()
    await notify_bot_stopped()
    logger.info("Trading loop stopped")


async def _process_ticker(ticker: str, orchestrator: TradingOrchestrator):
    try:
        df = loader.get_candles(ticker, interval="1h")
        if df.empty:
            return

        indicators = indicator_engine.latest(df)
        sig = rules_engine.evaluate(indicators)
        open_positions = risk_manager.open_positions

        if sig.action == Action.BUY and ticker not in open_positions:
            # Проверяем confidence через orchestrator (learning system)
            orch_decision = await orchestrator.check_signal({
                "strategy_id": getattr(sig, "strategy_id", "default_moex"),
                "market_regime": getattr(indicators, "market_regime", None),
                "market_features": {
                    "rsi": indicators.rsi,
                    "atr": indicators.atr,
                    "adx": indicators.adx,
                    "macd_hist": indicators.macd_hist,
                },
            })
            if not orch_decision["approved"]:
                logger.info("[%s] Orchestrator blocked: %s", ticker, orch_decision["reason"])
                return

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

                # Legacy feedback (для dashboard и qf_platform)
                db_id = feedback_store.record_open(TradeRecord(
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
                if hasattr(pos, "db_id"):
                    pos.db_id = db_id

                # Learning system (orchestrator + memory_writer + belief)
                trade_obj = Trade(
                    market=Market.STOCKS,
                    ticker=ticker,
                    direction=Direction.BUY,
                    strategy_id=getattr(sig, "strategy_id", "default_moex"),
                    entry_price=Decimal(str(indicators.close)),
                    stop_loss=Decimal(str(pos.stop_price)),
                    position_size=Decimal(str(pos.shares)),
                    risk_amount=Decimal(str(pos.risk_amount)),
                    risk_percent=Decimal(str(round(pos.risk_amount / balance, 4))) if balance else Decimal("0"),
                    opened_at=datetime.now(timezone.utc),
                    is_sandbox=config.tinkoff.sandbox,
                    confidence=Decimal(str(round(orch_decision["confidence"], 4))),
                    entry_reason=", ".join(r.name for r in sig.triggered_rules),
                    market_features={
                        "rsi": indicators.rsi,
                        "atr": indicators.atr,
                        "adx": indicators.adx,
                        "macd_hist": indicators.macd_hist,
                    },
                )
                trade_obj.trade_id = await orchestrator.on_trade_opened(trade_obj)

                trading_engine.state.add_log(f"BUY {ticker} @ {indicators.close:.2f}")
                await notify_trade_open(ticker, indicators.close, pos.lot_size, pos.stop_price)

                # Paper trade mirror — always record in paper account for dashboard
                try:
                    from qf_platform.services.paper_trading_service import PaperTradingService
                    from qf_platform.repositories.signals_repository import SignalsRepository
                    _pe = _get_paper_engine()
                    _pts = PaperTradingService(_pe)
                    _acc = _pts.get_account()
                    _pts.open_position(
                        account_id=int(_acc["id"]),
                        ticker=ticker,
                        direction="long",
                        stop_loss=pos.stop_price,
                    )
                    SignalsRepository(_pe).insert({
                        "asset": ticker, "exchange": "moex", "timeframe": "1h",
                        "signal_type": "LONG", "entry_price": indicators.close,
                        "stop_loss": pos.stop_price,
                        "take_profit_1": round(indicators.close + 2 * (indicators.close - pos.stop_price), 4),
                        "probability_pct": round(min(95, 50 + sig.buy_score * 5), 1),
                        "status": "executing", "source": "trading_loop", "asset_class": "stocks",
                        "metadata": {"rules": [r.name for r in sig.triggered_rules], "buy_score": sig.buy_score},
                    })
                except Exception as _pe_exc:
                    logger.warning("Paper trade mirror (BUY) error: %s", _pe_exc)

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

                # Legacy feedback
                if hasattr(pos, "db_id") and pos.db_id:
                    feedback_store.record_close(pos.db_id, indicators.close)

                # Learning system — закрытие сделки запускает цикл обучения
                if hasattr(pos, "trade_id") and pos.trade_id:
                    close_trade = Trade(
                        trade_id=pos.trade_id,
                        market=Market.STOCKS,
                        ticker=ticker,
                        direction=Direction.BUY,
                        strategy_id=getattr(pos, "strategy_id", "default_moex"),
                        entry_price=Decimal(str(pos.entry_price)),
                        stop_loss=Decimal(str(pos.stop_price)),
                        position_size=Decimal(str(pos.shares)),
                        risk_amount=Decimal(str(pos.risk_amount)),
                        opened_at=getattr(pos, "opened_at", datetime.now(timezone.utc)),
                        exit_price=Decimal(str(indicators.close)),
                        closed_at=datetime.now(timezone.utc),
                        pnl=Decimal(str(round(pnl, 4))),
                        exit_reason_type=ExitReasonType.SIGNAL,
                        is_sandbox=config.tinkoff.sandbox,
                    )
                    await orchestrator.on_trade_closed(close_trade)

                trading_engine.state.add_log(f"SELL {ticker} @ {indicators.close:.2f} PnL={pnl:+.2f}")
                await notify_trade_close(ticker, indicators.close, pnl)

                # Paper position close mirror
                try:
                    from qf_platform.services.paper_trading_service import PaperTradingService
                    _pe = _get_paper_engine()
                    _pts = PaperTradingService(_pe)
                    _acc = _pts.get_account()
                    for _ppos in _pts._repo.list_positions(int(_acc["id"])):
                        if _ppos["ticker"].upper() == ticker.upper():
                            _pts.close_position(int(_ppos["id"]))
                            break
                except Exception as _pe_exc:
                    logger.warning("Paper trade mirror (SELL) error: %s", _pe_exc)

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
        except PermissionError:
            # Windows: PermissionError means the process EXISTS but we lack permission to signal it
            logger.error(
                "Бот уже запущен (PID %d). Остановите предыдущий процесс.",
                int(_PID_FILE.read_text().strip()),
            )
            return False
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
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
    except (OSError, AttributeError):
        pass  # SIGTERM unavailable on Windows

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
