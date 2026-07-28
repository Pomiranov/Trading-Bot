"""A/B-бэктест: trend_moex vs osc_range_moex на одних и тех же свечах.

Запуск:
    python backtest/run_ab_backtest.py

Данные грузятся с MOEX ISS ОДИН раз (последние 1334 свечи 1h на тикер)
и оба прогона идут по одним и тем же DataFrame. Обе стратегии пишут
сделки в learning/ (sandbox), после чего сравнение строится по БД:
общие метрики + разбивка по рыночным режимам (trending/ranging/volatile).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import logging
import os
from datetime import date, timedelta

from config import config
from data.loader import loader
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine
from learning.trading_orchestrator import TradingOrchestrator

TICKERS      = ["SBER", "GAZP", "LKOH", "NVTK"]
INTERVAL     = "1h"
CANDLES_MAX  = 1334
HISTORY_DAYS = 200

OSC_RULES_FILE = config.rules_dir / "rules_osc_range.yaml"

STRATEGIES = [
    # (strategy_id, подпись, rules_file или None=основной rules.yaml)
    ("trend_moex",     "A: трендовая (rules.yaml)",          None),
    ("osc_range_moex", "B: осцилляторы (rules_osc_range.yaml)", OSC_RULES_FILE),
]


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,   # тихий прогон: детали не нужны, важна сводка
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    end   = date.today()
    start = end - timedelta(days=HISTORY_DAYS)

    # ── Данные: один раз для обеих стратегий ─────────────────────────
    data = {}
    for ticker in TICKERS:
        df = loader.get_candles(ticker, interval=INTERVAL, start=start, end=end)
        if df.empty:
            print(f"[{ticker}] Нет данных — пропуск")
            continue
        data[ticker] = df.tail(CANDLES_MAX)
        d = data[ticker]
        print(f"[{ticker}] {len(d)} свечей ({d.index.min()} → {d.index.max()})")

    # Долг №28: см. пояснение в run_ab_tf_backtest.py — запись только по флагу.
    ap = argparse.ArgumentParser()
    ap.add_argument("--learn", action="store_true",
                    help="писать сделки в trades и запускать цикл обучения. БЕЗ флага прогон только считает (долг №28)")
    args = ap.parse_args()

    orchestrator = TradingOrchestrator() if args.learn else None
    if not args.learn:
        print("Прогон БЕЗ записи в trades (--learn не указан)")
    results = {}   # strategy_id -> {ticker: BacktestResult}

    for strategy_id, label, rules_file in STRATEGIES:
        print(f"\n─── Прогон {label} ───")
        rules = RulesEngine(rules_file=rules_file) if rules_file else RulesEngine()
        engine = BacktestEngine(
            rules_engine=rules,
            orchestrator=orchestrator,
            strategy_id=strategy_id,
        )
        per_ticker = {}
        for ticker, df in data.items():
            result = engine.run(ticker, df)
            per_ticker[ticker] = result
            print(f"  {result.summary()}")
        results[strategy_id] = per_ticker
        if orchestrator is not None:
            engine.run_full_learning_cycle()
            engine.shutdown_learning()

    asyncio.run(report(results))


async def report(results: dict) -> None:
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv()

    conn = await asyncpg.connect("postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot")))
    try:
        print(f"\n{'═' * 66}")
        print("  A/B-СРАВНЕНИЕ (одни и те же свечи)")
        print(f"{'═' * 66}")

        # Общая таблица по стратегиям (из БД — единый источник)
        rows = await conn.fetch("""
            SELECT strategy_id,
                   COUNT(*)                                          AS n,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)          AS wins,
                   SUM(pnl)                                          AS pnl,
                   SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END)        AS gross_win,
                   ABS(SUM(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END))  AS gross_loss,
                   AVG(pnl_r)                                        AS avg_r
            FROM trades
            WHERE is_sandbox AND closed_at IS NOT NULL
            GROUP BY strategy_id ORDER BY strategy_id
        """)
        print(f"\n{'Стратегия':<16} {'Сделок':>7} {'WinRate':>8} {'PnL, руб.':>12} {'PF':>6} {'avg R':>7}")
        for r in rows:
            wr = r["wins"] / r["n"] * 100 if r["n"] else 0
            pf = float(r["gross_win"] / r["gross_loss"]) if r["gross_loss"] else float("inf")
            print(f"{r['strategy_id']:<16} {r['n']:>7} {wr:>7.1f}% {float(r['pnl']):>12,.0f} "
                  f"{pf:>6.2f} {float(r['avg_r'] or 0):>+7.3f}")

        # Разбивка по режимам
        rows = await conn.fetch("""
            SELECT strategy_id, market_regime,
                   COUNT(*)                                          AS n,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)          AS wins,
                   SUM(pnl)                                          AS pnl,
                   SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END)        AS gross_win,
                   ABS(SUM(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END))  AS gross_loss,
                   AVG(pnl_r)                                        AS avg_r
            FROM trades
            WHERE is_sandbox AND closed_at IS NOT NULL AND market_regime IS NOT NULL
            GROUP BY strategy_id, market_regime
            ORDER BY strategy_id, market_regime
        """)
        print(f"\n{'Стратегия':<16} {'Режим':<10} {'Сделок':>7} {'WinRate':>8} {'PnL, руб.':>12} {'PF':>6} {'avg R':>7}")
        for r in rows:
            wr = r["wins"] / r["n"] * 100 if r["n"] else 0
            pf = float(r["gross_win"] / r["gross_loss"]) if r["gross_loss"] else float("inf")
            print(f"{r['strategy_id']:<16} {r['market_regime']:<10} {r['n']:>7} {wr:>7.1f}% "
                  f"{float(r['pnl']):>12,.0f} {pf:>6.2f} {float(r['avg_r'] or 0):>+7.3f}")

        # Confidence после обучения
        print("\nBelief system после обучения:")
        for r in await conn.fetch("""
            SELECT strategy_id, confidence, total_trades, best_regime
            FROM belief_system
            WHERE strategy_id IN ('trend_moex', 'osc_range_moex')
            ORDER BY strategy_id
        """):
            print(f"  {r['strategy_id']:<16} conf={float(r['confidence']):.3f} | "
                  f"сделок={r['total_trades']} | best_regime={r['best_regime'] or '—'}")
    finally:
        await conn.close()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
