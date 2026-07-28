"""A/B wrd_moex: чистый книжный SAR (гл. 18) vs текущий 2×ATR-контур.

Запуск:
    python backtest/run_ab_wrd_sar.py

Тест книжной гипотезы, НЕ подбор стопа: в стройке wrd_moex 179 из 191
сделок закрыл ATR-стоп/трейлинг, книжный SAR-выход (закрытие за ptr_low)
сработал 12 раз — наложенный контур затеняет stop-and-reverse, сердце
системы гл. 18. Вопрос A/B: жива ли книжная механика без ATR поверх.

Единственная меняемая переменная — use_stops движка (вкл/выкл стопа
и трейлинга). Правила, книжные параметры (k=2.0, ATR(10), N1=4, N2=2),
long-only адаптация и сайзинг по стоп-дистанции идентичны в обоих
вариантах; боевой rules_wrd_moex.yaml не модифицируется.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
import time

import pandas as pd

from config import config
from backtest.engine import BacktestEngine, BacktestTrade
from backtest.run_wrd_backtest import load_candles_db, metrics, IS_END
from signals.rules_engine import RulesEngine

RULES_FILE = config.rules_dir / "rules_wrd_moex.yaml"

VARIANTS = [
    # (id, подпись, use_stops)
    ("baseline", "2×ATR-стоп + трейлинг (текущий контур)", True),
    ("pure_sar", "чистый SAR гл.18 (без стопа/трейлинга)",  False),
]


def fmt(label: str, m: dict) -> str:
    pf = f"{m['pf']:6.2f}" if m["pf"] != float("inf") else "   inf"
    return (f"{label:<10} {m['n']:>5} {m['wr']:>6.1f}% {m['pnl']:>13,.0f} "
            f"{pf} {m['payoff']:>6.2f} {m['days']:>6.1f}")


HEADER = f"{'':<10} {'n':>5} {'WR':>7} {'PnL, руб.':>13} {'PF':>6} {'payoff':>6} {'дней':>6}"


def exit_breakdown(trades: list[BacktestTrade], last_bar: dict[str, pd.Timestamp]) -> dict:
    """Типы выхода: стоп / SAR-разворот / принудительный финал последней свечи."""
    by = {"stop": 0, "sar": 0, "final": 0, "target": 0}
    for t in trades:
        if t.status == "STOPPED":
            by["stop"] += 1
        elif t.status == "TARGET":
            by["target"] += 1
        elif t.exit_date is not None and t.exit_date == last_bar.get(t.ticker):
            by["final"] += 1
        else:
            by["sar"] += 1
    return by


def main() -> None:
    logging.basicConfig(level=logging.ERROR)

    data = asyncio.run(load_candles_db("1d"))
    n_bars = sum(len(d) for d in data.values())
    lo = min(d.index.min() for d in data.values())
    hi = max(d.index.max() for d in data.values())
    print(f"D1: {len(data)} тикеров, {n_bars} свечей, {lo.date()} → {hi.date()}")
    last_bar = {ticker: df.index[-1] for ticker, df in data.items()}

    all_trades: dict[str, list[BacktestTrade]] = {}
    for vid, label, use_stops in VARIANTS:
        rules  = RulesEngine(rules_file=RULES_FILE)
        engine = BacktestEngine(rules_engine=rules, strategy_id=f"wrd_ab_{vid}",
                                timeframe="D1", use_stops=use_stops)
        t0 = time.time()
        trades: list[BacktestTrade] = []
        for ticker, df in data.items():
            trades.extend(engine.run(ticker, df).trades)
        all_trades[vid] = trades
        print(f"  {vid:<10} ({label}): сделок={len(trades)}, {time.time() - t0:.0f} с")

    # ── Счётчики ПЕРВОЙ строкой ───────────────────────────────────────
    counts = {}
    for vid, _l, _s in VARIANTS:
        tr = all_trades[vid]
        counts[vid] = (
            sum(1 for t in tr if t.entry_date < IS_END),
            sum(1 for t in tr if t.entry_date >= IS_END),
        )
    print(f"\nСделки IS/OOS: baseline={counts['baseline'][0]}/{counts['baseline'][1]}, "
          f"pure_sar={counts['pure_sar'][0]}/{counts['pure_sar'][1]}")

    # ── Сводные таблицы ───────────────────────────────────────────────
    for title, pred in [
        ("ПОЛНЫЙ ПЕРИОД", lambda t: True),
        ("IS (до 2025-01-01)", lambda t: t.entry_date < IS_END),
        ("OOS (с 2025-01-01)", lambda t: t.entry_date >= IS_END),
    ]:
        print(f"\n{'═' * 70}\n  {title}\n{'═' * 70}\n{HEADER}")
        for vid, _l, _s in VARIANTS:
            print(fmt(vid, metrics([t for t in all_trades[vid] if pred(t)])))

    # ── Разбивка по типу выхода ───────────────────────────────────────
    print(f"\n{'─' * 70}\n  Типы выхода: стоп / SAR-разворот / финал последней свечи\n{'─' * 70}")
    for vid, _l, _s in VARIANTS:
        by = exit_breakdown(all_trades[vid], last_bar)
        n = len(all_trades[vid])
        sar_trades = [
            t for t in all_trades[vid]
            if t.status not in ("STOPPED", "TARGET")
            and not (t.exit_date is not None and t.exit_date == last_bar.get(t.ticker))
        ]
        sar_pnl = sum(t.pnl for t in sar_trades)
        print(f"  {vid:<10} стоп={by['stop']:<4} SAR={by['sar']:<4} "
              f"финал={by['final']:<3} | PnL SAR-выходов: {sar_pnl:>+12,.0f} "
              f"({n} сделок всего)")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
