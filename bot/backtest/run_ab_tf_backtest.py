"""A/B по таймфреймам: trend vs osc на 3 годах истории из таблицы candles.

Запуск:
    python backtest/run_ab_tf_backtest.py

Три прогона (H1, H4, D1) × 12 тикеров × 2 стратегии. Свечи читаются из БД
(таблица candles), MOEX ISS не используется. Сделки пишутся в learning
под strategy_id вида trend_moex_h1 / osc_range_moex_h1 и т.д. (sandbox).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import logging
import os
import time

import pandas as pd

from config import config
from universe import (
    MEASUREMENT_UNIVERSE_2026_07, MEASUREMENT_UNIVERSE_2026_07_VERSION,
)
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine
from learning.trading_orchestrator import TradingOrchestrator

# Набор ПРИКОЛОЧЕН: на нём посчитаны все опорные числа проекта. Не менять —
# набор есть часть определения измерения (bot/universe.py). Новые валидации
# делаются на MEASUREMENT_UNIVERSE_2026_07_EXT.
TICKERS = list(MEASUREMENT_UNIVERSE_2026_07)
TIMEFRAMES = ["1h", "4h", "1d"]     # значения в таблице candles
TF_LABEL   = {"1h": "H1", "4h": "H4", "1d": "D1"}

OSC_RULES_FILE = config.rules_dir / "rules_osc_range.yaml"


def dsn() -> str:
    from dotenv import load_dotenv
    load_dotenv()
    return "postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot"))


async def load_candles_db(timeframe: str) -> dict[str, pd.DataFrame]:
    """Прочитать свечи всех тикеров одного таймфрейма из таблицы candles."""
    import asyncpg
    conn = await asyncpg.connect(dsn())
    data = {}
    try:
        for ticker in TICKERS:
            rows = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM candles
                WHERE ticker = $1 AND timeframe = $2
                ORDER BY time
            """, ticker, timeframe)
            if not rows:
                continue
            df = pd.DataFrame(
                {
                    "open":   [float(r["open"]) for r in rows],
                    "high":   [float(r["high"]) for r in rows],
                    "low":    [float(r["low"]) for r in rows],
                    "close":  [float(r["close"]) for r in rows],
                    "volume": [int(r["volume"]) for r in rows],
                },
                index=pd.DatetimeIndex(
                    [r["time"].replace(tzinfo=None) for r in rows], name="datetime"
                ),
            )
            data[ticker] = df
    finally:
        await conn.close()
    return data


def main() -> None:
    logging.basicConfig(level=logging.ERROR)

    # Долг №28: без --learn прогон НИЧЕГО не пишет в trades. Раньше оркестратор
    # создавался безусловно, и один штатный запуск этих двух скриптов давал
    # 10 179 строк при 7 532 существующих — контаминация в 10-20 раз больше
    # гейта этапа 2 ML (500-1000 закрытых форвардных сделок). Конвенция взята у
    # run_wrd_backtest.py: безопасный дефолт, запись только по явному флагу.
    ap = argparse.ArgumentParser()
    ap.add_argument("--learn", action="store_true",
                    help="писать сделки в trades и запускать цикл обучения. БЕЗ флага прогон только считает (долг №28)")
    args = ap.parse_args()

    orchestrator = TradingOrchestrator() if args.learn else None
    if not args.learn:
        print("Прогон БЕЗ записи в trades (--learn не указан)")
    all_results = {}    # (tf, strategy_id) -> {ticker: BacktestResult}

    last_engine = None
    for tf in TIMEFRAMES:
        data = asyncio.run(load_candles_db(tf))
        n_bars = sum(len(d) for d in data.values())
        print(f"\n{'═' * 60}\n  ТАЙМФРЕЙМ {TF_LABEL[tf]}: {len(data)} тикеров, {n_bars} свечей\n{'═' * 60}")

        for base, rules_file in [("trend_moex", None), ("osc_range_moex", OSC_RULES_FILE)]:
            strategy_id = f"{base}_{TF_LABEL[tf].lower()}"
            rules = RulesEngine(rules_file=rules_file) if rules_file else RulesEngine()
            engine = BacktestEngine(
                universe_version=MEASUREMENT_UNIVERSE_2026_07_VERSION,
                rules_engine=rules,
                orchestrator=orchestrator,
                strategy_id=strategy_id,
                timeframe=TF_LABEL[tf],
            )
            last_engine = engine

            t0 = time.time()
            per_ticker = {}
            for ticker, df in data.items():
                per_ticker[ticker] = engine.run(ticker, df)
            all_results[(tf, strategy_id)] = per_ticker

            total = sum(r.total_trades for r in per_ticker.values())
            pnl   = sum(r.total_pnl for r in per_ticker.values())
            print(f"  {strategy_id:<20} сделок={total:<5} PnL={pnl:+,.0f} руб. "
                  f"({time.time() - t0:.0f} с)")

    # Полный цикл обучения на всей накопленной статистике
    print("\nЗапуск полного цикла обучения...")
    summary = last_engine.run_full_learning_cycle()
    print(f"  {summary}")
    last_engine.shutdown_learning()

    asyncio.run(report(all_results))


async def report(all_results: dict) -> None:
    import asyncpg
    conn = await asyncpg.connect(dsn())
    try:
        for tf in TIMEFRAMES:
            label = TF_LABEL[tf]
            sids = [f"trend_moex_{label.lower()}", f"osc_range_moex_{label.lower()}"]
            print(f"\n{'═' * 66}\n  {label}: СВОДКА\n{'═' * 66}")

            rows = await conn.fetch("""
                SELECT strategy_id, COUNT(*) n,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) wins,
                       SUM(pnl) pnl,
                       SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) gw,
                       ABS(SUM(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END)) gl,
                       AVG(pnl_r) avg_r
                FROM trades
                WHERE is_sandbox AND closed_at IS NOT NULL AND strategy_id = ANY($1)
                GROUP BY strategy_id ORDER BY strategy_id
            """, sids)
            print(f"\n{'Стратегия':<20} {'Сделок':>7} {'WinRate':>8} {'PnL, руб.':>13} {'PF':>6} {'avg R':>8}")
            for r in rows:
                wr = r["wins"] / r["n"] * 100 if r["n"] else 0
                pf = float(r["gw"] / r["gl"]) if r["gl"] else float("inf")
                print(f"{r['strategy_id']:<20} {r['n']:>7} {wr:>7.1f}% {float(r['pnl']):>13,.0f} "
                      f"{pf:>6.2f} {float(r['avg_r'] or 0):>+8.3f}")

            rows = await conn.fetch("""
                SELECT strategy_id, market_regime, COUNT(*) n,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) wins,
                       SUM(pnl) pnl,
                       SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) gw,
                       ABS(SUM(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END)) gl,
                       AVG(pnl_r) avg_r
                FROM trades
                WHERE is_sandbox AND closed_at IS NOT NULL
                  AND strategy_id = ANY($1) AND market_regime IS NOT NULL
                GROUP BY strategy_id, market_regime
                ORDER BY strategy_id, market_regime
            """, sids)
            print(f"\n{'Стратегия':<20} {'Режим':<10} {'Сделок':>7} {'WinRate':>8} {'PnL, руб.':>13} {'PF':>6} {'avg R':>8}")
            for r in rows:
                wr = r["wins"] / r["n"] * 100 if r["n"] else 0
                pf = float(r["gw"] / r["gl"]) if r["gl"] else float("inf")
                print(f"{r['strategy_id']:<20} {r['market_regime']:<10} {r['n']:>7} {wr:>7.1f}% "
                      f"{float(r['pnl']):>13,.0f} {pf:>6.2f} {float(r['avg_r'] or 0):>+8.3f}")

            # Топ-3 / антитоп-3 тикеров по PnL (из результатов бэктеста)
            for (tf_key, sid), per_ticker in all_results.items():
                if tf_key != tf:
                    continue
                ranked = sorted(per_ticker.items(), key=lambda kv: kv[1].total_pnl, reverse=True)
                top = ", ".join(f"{t} {r.total_pnl:+,.0f}" for t, r in ranked[:3])
                bot = ", ".join(f"{t} {r.total_pnl:+,.0f}" for t, r in ranked[-3:])
                print(f"\n{sid}:")
                print(f"  топ-3:     {top}")
                print(f"  антитоп-3: {bot}")

        # ── Belief system и гипотезы ──────────────────────────────────
        print(f"\n{'═' * 66}\n  ОБУЧЕНИЕ: CONFIDENCE И ГИПОТЕЗЫ\n{'═' * 66}\n")
        for r in await conn.fetch("""
            SELECT strategy_id, confidence, total_trades, win_rate, best_regime
            FROM belief_system
            WHERE strategy_id LIKE 'trend_moex_%' OR strategy_id LIKE 'osc_range_moex_%'
            ORDER BY confidence DESC
        """):
            wr = f"{float(r['win_rate']):.1%}" if r["win_rate"] is not None else "—"
            print(f"  {r['strategy_id']:<20} conf={float(r['confidence']):.3f} | "
                  f"сделок={r['total_trades']:<5} | WR={wr:<7} | режим={r['best_regime'] or '—'}")

        print("\nГипотезы:")
        rows = await conn.fetch("""
            SELECT description, stage, total_trades, win_rate, expectancy
            FROM hypotheses ORDER BY stage, total_trades DESC
        """)
        if not rows:
            print("  — нет")
        for r in rows:
            wr = f"{float(r['win_rate']):.1%}" if r["win_rate"] is not None else "—"
            ex = f"{float(r['expectancy']):+.3f}R" if r["expectancy"] is not None else "—"
            print(f"  [{r['stage']:<12}] {r['description']} "
                  f"(n={r['total_trades'] or 0}, WR={wr}, E={ex})")
    finally:
        await conn.close()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
