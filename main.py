"""Главный файл запуска торгового бота."""

import asyncio
import logging
import signal
import sys
from datetime import datetime

# Windows-консоль по умолчанию использует cp1251 — переключаем на utf-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config import config
from data.loader import loader
from signals.indicators import IndicatorEngine
from signals.rules_engine import rules_engine, Action

# Индикаторы живого контура строятся с периодами из rules.yaml (секции
# indicators/divergence) — тем же способом, что в BacktestEngine. Иначе
# ema_slow=50 из конфига (фикс A3) не действовал бы в live.
indicator_engine = IndicatorEngine(**{
    **rules_engine.indicator_params,
    **rules_engine.divergence_params,
})
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
    """Сравнительный бэктест: базовые правила (ДО) vs все правила (ПОСЛЕ)."""
    from backtest.engine import BacktestEngine, BacktestResult
    from signals.rules_engine import RulesEngine
    from datetime import date, timedelta
    import pandas as pd
    import numpy as np

    # ── Синтетические данные (фоллбэк при недоступности MOEX ISS) ────
    def _synthetic(ticker: str, n_hours: int = 2200) -> pd.DataFrame:
        start_prices = {
            "SBER": 280.0, "GAZP": 165.0,
            "LKOH": 7200.0, "NVTK": 1100.0, "YNDX": 3800.0,
        }
        seed = sum(ord(c) for c in ticker)
        rng  = np.random.default_rng(seed)
        p0   = start_prices.get(ticker, 1000.0)

        # Случайное блуждание с несколькими трендовыми периодами
        rets = rng.normal(0.00006, 0.006, n_hours)
        for _ in range(7):
            s = rng.integers(0, n_hours - 300)
            l = rng.integers(80, 300)
            d = rng.choice([-1, 1]) * rng.uniform(0.001, 0.004)
            rets[s: s + l] += d
        prices = p0 * np.exp(np.cumsum(rets))

        idx = pd.date_range("2024-01-02 10:00", periods=n_hours, freq="1h")
        trading = [t for t in idx if t.weekday() < 5 and 10 <= t.hour < 18]
        n = len(trading)
        p = prices[:n]

        spread = np.abs(rng.normal(0, 0.003, n))
        df = pd.DataFrame({
            "open":   p * (1 + rng.normal(0, 0.001, n)),
            "high":   p * (1 + spread),
            "low":    p * (1 - spread),
            "close":  p,
            "volume": rng.integers(500_000, 10_000_000, n).astype(float),
        }, index=trading)
        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"]  = df[["low",  "open", "close"]].min(axis=1)
        return df

    # ── Загрузка данных ───────────────────────────────────────────────
    end   = date.today()
    start = end - timedelta(days=365)
    data: dict[str, pd.DataFrame] = {}
    synthetic_used = False

    for ticker in config.tickers:
        try:
            df = loader.get_candles(ticker, interval="1d", start=start, end=end)
            if df.empty:
                raise ValueError("Пустой ответ MOEX ISS")
            data[ticker] = df
            logger.info("[%s] Загружено %d свечей с MOEX", ticker, len(df))
        except Exception as exc:
            logger.warning("[%s] MOEX недоступен (%s) — синтетические данные", ticker, exc)
            data[ticker] = _synthetic(ticker)
            synthetic_used = True

    if synthetic_used:
        print("\n[!] MOEX ISS недоступен — используются синтетические данные\n")

    # ── Два движка: legacy (ДО) и расширенный (ПОСЛЕ) ─────────────────
    engine_before = BacktestEngine(rules_engine=RulesEngine(extended=False))
    engine_after  = BacktestEngine(rules_engine=RulesEngine(extended=True))

    before: dict[str, BacktestResult] = {}
    after:  dict[str, BacktestResult] = {}

    W = 70
    print("\n" + "=" * W)
    print("  ДО  --  только секция rules (базовые BUY/SELL правила)")
    print("=" * W)
    for ticker, df in data.items():
        r = engine_before.run(ticker, df)
        before[ticker] = r
        print(" ", r.summary())

    print("\n" + "=" * W)
    print("  ПОСЛЕ  --  все секции: rules + filters + exit_rules + ticker_specific + macro")
    print("=" * W)
    for ticker, df in data.items():
        r = engine_after.run(ticker, df)
        after[ticker] = r
        print(" ", r.summary())

    # ── Агрегация по всем тикерам ─────────────────────────────────────
    def _agg(res: dict) -> dict:
        n      = max(len(res), 1)
        trades = sum(r.total_trades   for r in res.values())
        wins   = sum(r.winning_trades for r in res.values())
        pf_vals = [r.profit_factor for r in res.values()
                   if r.profit_factor not in (0.0, float("inf"))]
        return {
            "sharpe":        sum(r.sharpe        for r in res.values()) / n,
            "win_rate":      wins / trades * 100 if trades else 0.0,
            "max_drawdown":  sum(r.max_drawdown  for r in res.values()) / n,
            "profit_factor": sum(pf_vals) / max(len(pf_vals), 1),
            "total_trades":  trades,
            "cagr":          sum(r.cagr          for r in res.values()) / n,
        }

    bef = _agg(before)
    aft = _agg(after)

    # ── Сравнительная таблица ─────────────────────────────────────────
    def _delta(b, a, fmt, higher_is_good=True) -> str:
        d     = a - b
        arrow = ("▲" if d > 0 else "▼" if d < 0 else "─")
        if not higher_is_good:
            arrow = ("▼" if d > 0 else "▲" if d < 0 else "─")
        return f"{arrow} {d:{fmt}}"

    rows = [
        ("Sharpe Ratio",
         f"{bef['sharpe']:.3f}", f"{aft['sharpe']:.3f}",
         _delta(bef["sharpe"],        aft["sharpe"],        "+.3f")),
        ("Win Rate",
         f"{bef['win_rate']:.1f}%",   f"{aft['win_rate']:.1f}%",
         _delta(bef["win_rate"],      aft["win_rate"],      "+.1f") + "%"),
        ("Max Drawdown",
         f"{bef['max_drawdown']:.1f}%", f"{aft['max_drawdown']:.1f}%",
         _delta(bef["max_drawdown"],  aft["max_drawdown"],  "+.1f", higher_is_good=False) + "%"),
        ("Profit Factor",
         f"{bef['profit_factor']:.2f}", f"{aft['profit_factor']:.2f}",
         _delta(bef["profit_factor"], aft["profit_factor"], "+.2f")),
        ("Всего сделок",
         str(bef["total_trades"]),    str(aft["total_trades"]),
         _delta(bef["total_trades"],  aft["total_trades"],  "+.0f")),
        ("CAGR",
         f"{bef['cagr']:.2f}%",      f"{aft['cagr']:.2f}%",
         _delta(bef["cagr"],         aft["cagr"],          "+.2f") + "%"),
    ]

    print("\n" + "=" * W)
    print("  СРАВНИТЕЛЬНАЯ ТАБЛИЦА (средние по всем тикерам)")
    print("=" * W)
    hdr = f"{'Метрика':<20} {'ДО':>12} {'ПОСЛЕ':>12} {'Изменение':>18}"
    print(hdr)
    print("-" * W)
    for name, bv, av, dv in rows:
        print(f"{name:<20} {bv:>12} {av:>12} {dv:>18}")
    print("=" * W + "\n")


if __name__ == "__main__":
    main()
