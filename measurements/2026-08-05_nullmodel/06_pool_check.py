import asyncio, sys
from datetime import date
from pathlib import Path
import pandas as pd
sys.path.insert(0, ".")
from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07
from backtest.candles import load_candles_db
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine
IS_END = pd.Timestamp("2025-01-01")
RULES = Path("../knowledge/rules/rules_osc_range.yaml").resolve()
data = asyncio.run(load_candles_db("1d", list(MEASUREMENT_UNIVERSE_2026_07),
                                   SAMPLE_START_2026_07, date(2026, 7, 29)))
real = RulesEngine(rules_file=RULES)
print(f"  {'тикер':6} {'баров':>6} {'разр.IS':>8} {'разр.OOS':>9} {'сумма':>6} {'мин.OOS-дата':>13} {'макс.OOS-дата':>14}")
tot_is = tot_oos = 0
for t in sorted(data):
    e = BacktestEngine(rules_engine=real, timeframe="D1")
    d = e._drop_forming_bar(t, data[t]); di = e._indicators.compute(d)
    gate = e._downtrend_gate(d, di.index); idx = list(di.index)
    ok = [idx[i] for i in range(e._warmup_bars, len(idx)) if gate is None or not bool(gate.iloc[i])]
    a_is  = [x for x in ok if pd.Timestamp(x).tz_localize(None) <  IS_END]
    a_oos = [x for x in ok if pd.Timestamp(x).tz_localize(None) >= IS_END]
    tot_is += len(a_is); tot_oos += len(a_oos)
    print(f"  {t:6} {len(idx):>6} {len(a_is):>8} {len(a_oos):>9} {len(ok):>6} "
          f"{str(pd.Timestamp(a_oos[0]).date()) if a_oos else '—':>13} "
          f"{str(pd.Timestamp(a_oos[-1]).date()) if a_oos else '—':>14}")
print(f"  {'ИТОГО':6} {'':>6} {tot_is:>8} {tot_oos:>9} {tot_is+tot_oos:>6}")
print()
print(f"  пул СЕРИИ = только OOS = {tot_oos} баров; пул ТАЙМИНГОВОГО скрипта = {tot_is+tot_oos}")
print(f"  минимальная дата в пуле серии по всем бумагам: не ранее 2025-01-01 ПО ПОСТРОЕНИЮ")
