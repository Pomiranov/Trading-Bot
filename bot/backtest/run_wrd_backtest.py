"""Бэктест wrd_moex — система ШД-дня (Швагер, гл. 18) на D1, IS/OOS.

Запуск:
    python backtest/run_wrd_backtest.py [--learn]

Параметры стратегии — из knowledge/rules/rules_wrd_moex.yaml (книжные,
без подбора под результат). Первая строка отчёта — счётчики ШД-событий
и сделок раздельно по IS/OOS: событийная система на 3 годах D1 даёт
мало сделок (у автора ~5-7 за 3.5 года на рынок), статистика хрупкая —
отчёт обязан показывать n до любых метрик.

--learn: зеркалировать сделки в learning/ через TradingOrchestrator
(quantflow-схема: trades c trade_id/strategy_id/market_features,
sandbox). По умолчанию — чисто аналитический прогон без записи.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import logging
import os

import pandas as pd

from config import config
from universe import (
    SAMPLE_START_2026_07,
    MEASUREMENT_UNIVERSE_2026_07, MEASUREMENT_UNIVERSE_2026_07_VERSION,
)
from backtest.candles import dsn, load_candles_db, window_note
from backtest.engine import BacktestEngine, BacktestTrade
from signals.indicators import IndicatorEngine
from signals.rules_engine import RulesEngine

# Набор ПРИКОЛОЧЕН: на нём посчитаны все опорные числа проекта. Не менять —
# набор есть часть определения измерения (bot/universe.py). Новые валидации
# делаются на MEASUREMENT_UNIVERSE_2026_07_EXT.
TICKERS = list(MEASUREMENT_UNIVERSE_2026_07)
RULES_FILE = config.rules_dir / "rules_wrd_moex.yaml"

IS_END = pd.Timestamp("2025-01-01")   # граница in-sample / out-of-sample


# dsn() и load_candles_db() вынесены в backtest/candles.py (долг №37):
# окно выборки стало ОБЯЗАТЕЛЬНЫМ аргументом, а пять копий одного запроса
# были той же болезнью, что девять копий списка тикеров.

def metrics(trades: list[BacktestTrade]) -> dict:
    n      = len(trades)
    wins   = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gw     = sum(t.pnl for t in wins)
    gl     = abs(sum(t.pnl for t in losses))
    avg_w  = gw / len(wins) if wins else 0.0
    avg_l  = gl / len(losses) if losses else 0.0
    days   = [
        (t.exit_date - t.entry_date).days
        for t in trades if t.exit_date is not None
    ]
    return {
        "n": n,
        "wr": len(wins) / n * 100 if n else 0.0,
        "pnl": sum(t.pnl for t in trades),
        "pf": (gw / gl) if gl else (float("inf") if gw else 0.0),
        "payoff": (avg_w / avg_l) if avg_l else 0.0,
        "days": sum(days) / len(days) if days else 0.0,
    }


def fmt(label: str, m: dict) -> str:
    pf = f"{m['pf']:6.2f}" if m["pf"] != float("inf") else "   inf"
    return (f"{label:<22} {m['n']:>5} {m['wr']:>6.1f}% {m['pnl']:>13,.0f} "
            f"{pf} {m['payoff']:>6.2f} {m['days']:>6.1f}")


HEADER = f"{'':<22} {'n':>5} {'WR':>7} {'PnL, руб.':>13} {'PF':>6} {'payoff':>6} {'дней':>6}"


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    ap = argparse.ArgumentParser()
    ap.add_argument("--learn", action="store_true",
                    help="зеркалировать сделки в learning/ через оркестратор (sandbox)")
    args = ap.parse_args()

    rules = RulesEngine(rules_file=RULES_FILE)
    print(f"Правила: {RULES_FILE.name}, wrd_params={rules.wrd_params}, learn={args.learn}")

    orchestrator = None
    if args.learn:
        from learning.trading_orchestrator import TradingOrchestrator
        orchestrator = TradingOrchestrator()

    data = asyncio.run(load_candles_db("1d", TICKERS, SAMPLE_START_2026_07))
    n_bars = sum(len(d) for d in data.values())
    print(f"D1: {len(data)} тикеров, {n_bars} свечей")
    # Окно печатает window_note (одна копия расчёта). Было `lo.date() → hi.date()`,
    # то есть НАИВНАЯ UTC-дата — третья из трёх дат бара и самая обманчивая: у D1 она
    # равна «сессия − 1 день» у ВСЕХ строк (долг №26).
    for line in window_note(data, SAMPLE_START_2026_07).splitlines():
        print(f"  {line}")

    # ── Счётчик ШД-событий (по индикаторному слою, вся история) ──────
    ind = IndicatorEngine(**rules.wrd_params)
    events = {"IS": 0, "OOS": 0}
    events_by_ticker: dict[str, tuple[int, int]] = {}
    for ticker, df in data.items():
        computed = ind.compute(df)
        flags = computed["wrd_day"].fillna(False)
        ev_is  = int(flags[flags.index <  IS_END].sum())
        ev_oos = int(flags[flags.index >= IS_END].sum())
        events["IS"]  += ev_is
        events["OOS"] += ev_oos
        events_by_ticker[ticker] = (ev_is, ev_oos)

    # ── Бэктест ───────────────────────────────────────────────────────
    engine = BacktestEngine(
        universe_version=MEASUREMENT_UNIVERSE_2026_07_VERSION,
        rules_engine=rules,
        orchestrator=orchestrator,
        strategy_id="wrd_moex",
        timeframe="D1",
    )
    trades: list[BacktestTrade] = []
    trades_by_ticker: dict[str, list[BacktestTrade]] = {}
    for ticker, df in data.items():
        res = engine.run(ticker, df)
        trades_by_ticker[ticker] = res.trades
        trades.extend(res.trades)
    if orchestrator is not None:
        engine.run_full_learning_cycle()
        engine.shutdown_learning()

    t_is  = [t for t in trades if t.entry_date <  IS_END]
    t_oos = [t for t in trades if t.entry_date >= IS_END]

    # ── Отчёт: счётчики ПЕРВОЙ строкой ────────────────────────────────
    print(f"\nШД-события: IS={events['IS']}, OOS={events['OOS']} | "
          f"сделки: IS={len(t_is)}, OOS={len(t_oos)}")
    if len(t_is) < 30 or len(t_oos) < 30:
        print("⚠️  Сделок МАЛО (порог хрупкости n<30 на период): статистика "
              "ориентировочная, выводы о PF/WR неустойчивы.")

    print(f"\n{'═' * 72}\n  wrd_moex, D1 (книжные параметры, без оптимизации)\n{'═' * 72}")
    print(HEADER)
    print(fmt("ПОЛНЫЙ ПЕРИОД", metrics(trades)))
    print(fmt("IS (до 2025-01-01)", metrics(t_is)))
    print(fmt("OOS (с 2025-01-01)", metrics(t_oos)))

    # ── По тикерам: события и сделки ──────────────────────────────────
    print(f"\n  По тикерам (события IS/OOS | сделки IS/OOS | PnL):")
    for ticker in data:
        ev_is, ev_oos = events_by_ticker[ticker]
        tt = trades_by_ticker[ticker]
        n_is  = sum(1 for t in tt if t.entry_date < IS_END)
        n_oos = len(tt) - n_is
        pnl = sum(t.pnl for t in tt)
        print(f"    {ticker:<6} события {ev_is:>3}/{ev_oos:<3} | "
              f"сделки {n_is:>2}/{n_oos:<2} | {pnl:>+12,.0f}")

    # ── Статусы закрытия ──────────────────────────────────────────────
    by: dict[str, int] = {}
    for t in trades:
        by[t.status] = by.get(t.status, 0) + 1
    print(f"\n  Статусы закрытия: " + "  ".join(f"{k}={v}" for k, v in sorted(by.items())))


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
