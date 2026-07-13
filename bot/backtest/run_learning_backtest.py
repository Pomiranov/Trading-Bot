"""Бэктест с циклом обучения (sandbox).

Запуск:
    python backtest/run_learning_backtest.py

Шаги:
    1. Загрузить часовые свечи с MOEX ISS (последние 1334 на тикер).
    2. Прогнать BacktestEngine с подключённым TradingOrchestrator:
       каждая сделка зеркалируется в learning/ (on_trade_opened /
       on_trade_closed), все сделки is_sandbox=True.
    3. После бэктеста — orchestrator.run_full_learning_cycle().
    4. Показать итоговую статистику: сделки, confidence стратегий,
       найденные гипотезы.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
import os
from datetime import date, timedelta

from data.loader import loader
from backtest.engine import BacktestEngine
from learning.trading_orchestrator import TradingOrchestrator

TICKERS      = ["SBER", "GAZP", "LKOH", "NVTK"]
INTERVAL     = "1h"
CANDLES_MAX  = 1334          # столько свечей на тикер идёт в бэктест
HISTORY_DAYS = 200           # запас по календарю чтобы набрать CANDLES_MAX


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Свечи и сигналы логируют много — оставляем только предупреждения
    for noisy in ("quantflow.memory", "quantflow.evaluator", "quantflow.orchestrator"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    orchestrator = TradingOrchestrator()
    engine = BacktestEngine(orchestrator=orchestrator)

    end   = date.today()
    start = end - timedelta(days=HISTORY_DAYS)

    print(f"\n{'═' * 62}")
    print(f"  Бэктест с обучением (sandbox) — {', '.join(TICKERS)}")
    print(f"  Интервал {INTERVAL}, до {CANDLES_MAX} свечей на тикер")
    print(f"{'═' * 62}\n")

    results = []
    for ticker in TICKERS:
        df = loader.get_candles(ticker, interval=INTERVAL, start=start, end=end)
        if df.empty:
            print(f"[{ticker}] Нет данных — пропуск")
            continue
        df = df.tail(CANDLES_MAX)
        print(f"[{ticker}] {len(df)} свечей ({df.index.min()} → {df.index.max()})")

        result = engine.run(ticker, df)
        results.append(result)
        print(f"[{ticker}] {result.summary()}\n")

    # Полный цикл обучения по всем накопленным сделкам
    print("Запуск полного цикла обучения...")
    summary = engine.run_full_learning_cycle()
    engine.shutdown_learning()

    # ── Итоговый отчёт ────────────────────────────────────────────────
    print(f"\n{'═' * 62}")
    print("  ИТОГИ")
    print(f"{'═' * 62}")

    total_trades = sum(r.total_trades for r in results)
    total_pnl    = sum(r.total_pnl for r in results)
    print(f"\nСделок в бэктесте: {total_trades} | Суммарный PnL: {total_pnl:+,.0f} руб.")
    for r in results:
        print(f"  {r.summary()}")

    print("\nЦикл обучения:")
    for key, val in summary.items():
        print(f"  {key}: {val}")

    asyncio.run(report_db_state())


async def report_db_state() -> None:
    """Показать состояние belief_system и hypotheses после обучения."""
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv()

    dsn = "postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"),
        os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"),
        os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot"),
    )
    conn = await asyncpg.connect(dsn)
    try:
        n_trades = await conn.fetchval(
            "SELECT COUNT(*) FROM trades WHERE is_sandbox AND closed_at IS NOT NULL"
        )
        print(f"\nЗакрытых sandbox-сделок в БД: {n_trades}")

        print("\nConfidence стратегий (belief_system):")
        rows = await conn.fetch("""
            SELECT strategy_id, confidence, total_trades, win_rate,
                   profit_factor, expectancy, best_regime
            FROM belief_system ORDER BY confidence DESC, strategy_id
        """)
        for r in rows:
            wr = f"{float(r['win_rate']):.1%}" if r["win_rate"] is not None else "—"
            pf = f"{float(r['profit_factor']):.2f}" if r["profit_factor"] is not None else "—"
            ex = f"{float(r['expectancy']):+.3f}R" if r["expectancy"] is not None else "—"
            print(
                f"  {r['strategy_id']:<16} conf={float(r['confidence']):.3f} | "
                f"сделок={r['total_trades'] or 0:<4} | WR={wr:<6} | "
                f"PF={pf:<6} | E={ex:<8} | режим={r['best_regime'] or '—'}"
            )

        print("\nГипотезы (hypotheses):")
        rows = await conn.fetch("""
            SELECT description, stage, total_trades, win_rate, expectancy
            FROM hypotheses ORDER BY stage, created_at
        """)
        if not rows:
            print("  — пока не найдено")
        for r in rows:
            wr = f"{float(r['win_rate']):.1%}" if r["win_rate"] is not None else "—"
            ex = f"{float(r['expectancy']):+.3f}R" if r["expectancy"] is not None else "—"
            print(
                f"  [{r['stage']:<12}] {r['description']} "
                f"(сделок={r['total_trades'] or 0}, WR={wr}, E={ex})"
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
