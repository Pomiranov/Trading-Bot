"""Main entry point — trading loop + Telegram bot."""
from __future__ import annotations

import asyncio
import logging
import math
import os
import signal
import sys
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Консоль Windows по умолчанию в cp1251 — символы ↑ → ═ из логов learning-слоя
# роняют logging в UnicodeEncodeError. Делается до bootstrap_security(), пока
# обработчики логирования ещё не созданы (как в run_forward_d1.py).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure bot/ directory is on sys.path so all internal imports resolve
sys.path.insert(0, str(Path(__file__).parent))

import asyncpg
from sqlalchemy import create_engine as _create_engine

from config import config
from security.bootstrap import bootstrap_security
from data.loader import loader
from signals.indicators import IndicatorEngine
from signals.rules_engine import rules_engine, Action, classify_regime
from universe import universe_version
from risk.risk_manager import risk_manager
from broker.tinkoff_client import tinkoff_client
from learning.belief_seed import seed_belief
from learning.trading_orchestrator import TradingOrchestrator
from learning.memory_writer import (
    Trade,
    Market,
    Direction,
    MarketRegime,
    ExitReasonType,
)
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

# Живая торговля пишется в отдельную belief-строку, засеянную из бэктестной —
# тот же приём, что у форварда osc_range (run_forward_d1.py). Статистика живого
# контура не смешивается с бэктестной, откат безболезненный.
STRATEGY_ID        = "trend_moex_live"
SEED_FROM_STRATEGY = "trend_moex"

# ticker → Trade, отданный в on_trade_opened. Нужен чтобы донести trade_id и
# контекст входа (market_features, confidence, entry_reason) до закрытия:
# PositionSizing риск-менеджера этих полей не несёт и не должен.
_open_trades: dict[str, Trade] = {}

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


async def _seed_belief() -> None:
    """Создать belief-строку живой стратегии (однократно, идемпотентно).

    Без неё check_signal отклоняет все сигналы: стратегии нет в belief_system.
    Пул оркестратора приватный — берём отдельное короткоживущее соединение.

    Логика — в learning/belief_seed.py, одна с форвардом. confidence НЕ
    наследуется: раньше здесь копировалось 0.2887 от trend_moex, что не описывает
    ни EMA50, ни то, что исполнится, а порог 0.20 это значение проходит (долг №30,
    §5а PROJECT_STATE).
    """
    conn = await asyncpg.connect(config.db.dsn)
    try:
        await seed_belief(
            conn,
            strategy_id=STRATEGY_ID,
            seed_from=SEED_FROM_STRATEGY,
            name_suffix=" (живая)",
            fallback_name="Следование тренду (живая)",
            fallback_description="Живой контур trend_moex, H1, исполнение через Tinkoff",
        )
    finally:
        await conn.close()


async def _reconcile_positions_with_broker() -> None:
    """
    Align risk_manager's tracked positions with what the broker actually
    holds before each scan cycle.

    Why this exists: tinkoff_client.place_market_order() swallows all
    exceptions and returns None on failure — including a network timeout
    that happens *after* the broker already filled the order. When that
    happens, risk_manager never learns the position exists, so the next
    cycle's signal for the same ticker looks like a fresh entry and can
    open a second real position. There is no other place in the codebase
    that reconciles internal state against the broker, so this runs once
    per scan cycle rather than only on the failure path, to also catch
    positions closed externally (e.g. a stop-loss order at the broker)
    that register_close() was never called for.
    """
    try:
        from services.tinkoff.portfolio import get_portfolio_summary
        summary = get_portfolio_summary()
    except Exception as exc:
        logger.debug("Position reconciliation skipped (portfolio unavailable): %s", exc)
        return

    broker_positions = {
        p.ticker: {"avg_price": p.average_price, "lots": p.quantity_lots}
        for p in summary.positions
    }
    discrepancies = risk_manager.reconcile_with_broker(broker_positions)
    for msg in discrepancies:
        await notify_risk_limit(f"Реконсиляция позиций: {msg}")


async def trading_loop():
    logger.info("Trading loop started. Tickers: %s", config.tickers)
    trading_engine.start()
    risk_manager.reset_daily()
    trading_engine.reset_daily()

    orchestrator = TradingOrchestrator(dsn=config.db.dsn)
    await orchestrator.connect()
    await _seed_belief()

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

        await _reconcile_positions_with_broker()

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
            regime = classify_regime(indicators.adx)
            # Незаполненные индикаторы приходят как NaN, а json.dumps сериализует
            # их в невалидный для jsonb литерал NaN — отсеиваем, как в форварде.
            features = {
                key: value
                for key, value in (
                    ("rsi",       indicators.rsi),
                    ("atr",       indicators.atr),
                    ("adx",       indicators.adx),
                    ("macd_hist", indicators.macd_hist),
                )
                if value is not None and math.isfinite(value)
            }

            # Проверяем confidence через orchestrator (learning system).
            # ticker/direction обязательны: без них фильтр структурного
            # даунтренда молчит, а отказы не пишутся в skipped_signals.
            orch_decision = await orchestrator.check_signal({
                "strategy_id":     STRATEGY_ID,
                "ticker":          ticker,
                "direction":       "BUY",
                "timeframe":       "1h",
                "market_regime":   regime,
                "market_features": features,
                "is_sandbox":      config.tinkoff.sandbox,
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

                # Learning system (orchestrator + memory_writer + belief)
                trade_obj = Trade(
                    market=Market.STOCKS,
                    ticker=ticker,
                    direction=Direction.BUY,
                    strategy_id=STRATEGY_ID,
                    entry_price=Decimal(str(indicators.close)),
                    stop_loss=Decimal(str(pos.stop_price)),
                    position_size=Decimal(str(pos.shares)),
                    risk_amount=Decimal(str(pos.risk_amount)),
                    risk_percent=Decimal(str(round(pos.risk_amount / balance, 4))) if balance else Decimal("0"),
                    opened_at=datetime.now(timezone.utc),
                    timeframe="1h",
                    market_regime=MarketRegime(regime) if regime else None,
                    is_sandbox=config.tinkoff.sandbox,
                    confidence=Decimal(str(round(orch_decision["confidence"], 4))),
                    entry_reason=", ".join(r.name for r in sig.triggered_rules),
                    market_features=features or None,
                    # Привязка к набору правил (долг №30). origin='live' — живой
                    # контур; is_sandbox здесь означает песочницу БРОКЕРА, а не
                    # происхождение сделки, поэтому различает не он.
                    signal_rules=sorted(r.name for r in sig.triggered_rules
                                        if r.action == Action.BUY),
                    rules_version=rules_engine.rules_version,
                    origin="live",
                    # Живой контур ходит по config.tickers — ЧЕТВЁРТЫЙ набор,
                    # отдельный от измерительных и от форвардного.
                    universe_version=universe_version(tuple(config.tickers)),
                )
                # Сбой learning-слоя не должен ломать торговый цикл: ордер уже стоит.
                try:
                    trade_obj.trade_id = await orchestrator.on_trade_opened(trade_obj)
                    _open_trades[ticker] = trade_obj
                except Exception as exc:
                    logger.error(
                        "[%s] Не записано открытие в learning: %s", ticker, exc, exc_info=True
                    )

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

                # Learning system — закрытие сделки запускает цикл обучения.
                # Дозаполняем ТОТ ЖЕ объект: orchestrator найдёт строку по trade_id
                # и сделает UPDATE. Пересборка Trade потеряла бы market_features,
                # confidence и entry_reason и вставила бы второй ряд.
                close_trade = _open_trades.pop(ticker, None)
                if close_trade is None:
                    logger.warning(
                        "[%s] Нет контекста открытия (позиция от предыдущего запуска) — "
                        "цикл обучения пропущен", ticker,
                    )
                else:
                    close_trade.exit_price       = Decimal(str(indicators.close))
                    close_trade.closed_at        = datetime.now(timezone.utc)
                    close_trade.pnl              = Decimal(str(round(pnl, 4)))
                    close_trade.exit_reason_type = ExitReasonType.SIGNAL
                    close_trade.exit_reason      = sig.reason
                    try:
                        await orchestrator.on_trade_closed(close_trade)
                    except Exception as exc:
                        logger.error(
                            "[%s] Не записано закрытие в learning: %s", ticker, exc, exc_info=True
                        )

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
