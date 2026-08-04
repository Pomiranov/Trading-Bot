import asyncio, sys
from datetime import date
from pathlib import Path
import pandas as pd
sys.path.insert(0, ".")
from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07, MEASUREMENT_UNIVERSE_2026_07_VERSION
from backtest.candles import load_candles_db
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine

IS_END = pd.Timestamp("2025-01-01")     # ЧИТАЕТСЯ, не переобъявляется: то же значение,
                                        # что run_osc_oos_debug.py:47. Скрипт замерочный.
rules = RulesEngine(rules_file=Path("../knowledge/rules/rules_osc_range.yaml"))
data = asyncio.run(load_candles_db("1d", list(MEASUREMENT_UNIVERSE_2026_07),
                                   SAMPLE_START_2026_07, date(2026, 7, 29)))
print(f"  {'тикер':7} {'баров':>6} {'разогрев':>9} {'IS род.':>8} {'OOS род.':>9} {'OOS/IS':>7} {'IS сделок':>10} {'OOS сделок':>11}")
tot = {"is": 0, "oos": 0, "warm": 0}
for t in sorted(data):
    eng = BacktestEngine(universe_version=MEASUREMENT_UNIVERSE_2026_07_VERSION,
                         rules_engine=rules, timeframe="D1")
    res = eng.run(t, data[t])
    b_is = sum(1 for x in res.born_at if pd.Timestamp(x).tz_localize(None) < IS_END)
    b_oos = len(res.born_at) - b_is
    tr_is = sum(1 for x in res.trades if pd.Timestamp(x.entry_date).tz_localize(None) < IS_END)
    tr_oos = len(res.trades) - tr_is
    ratio = f"{b_oos/b_is:.2f}" if b_is else "—"
    print(f"  {t:7} {len(data[t]):>6} {eng._warmup_bars:>9} {b_is:>8} {b_oos:>9} {ratio:>7} {tr_is:>10} {tr_oos:>11}")
    tot["is"] += b_is; tot["oos"] += b_oos; tot["warm"] += eng._warmup_bars
print(f"  {'ИТОГО':7} {'':>6} {tot['warm']:>9} {tot['is']:>8} {tot['oos']:>9} {tot['oos']/tot['is']:>7.2f}")
gr = sum(1 for t in sorted(data) if True)
