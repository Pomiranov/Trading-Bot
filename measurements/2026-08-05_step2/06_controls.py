import asyncio, sys
from datetime import date, datetime
from pathlib import Path
import pandas as pd
sys.path.insert(0, ".")
sys.path.insert(0, str(Path("../measurements/2026-08-05_step2").resolve()))
from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07
from backtest.candles import load_candles_db
import importlib.util
spec = importlib.util.spec_from_file_location("h", "../measurements/2026-08-05_step2/05_stub_harness.py")
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)

RULES = Path("../knowledge/rules/rules_osc_range.yaml").resolve()
data = asyncio.run(load_candles_db("1d", list(MEASUREMENT_UNIVERSE_2026_07),
                                   SAMPLE_START_2026_07, date(2026, 7, 29)))
TARGETS = [("LKOH", "2025-10-15 21:00:00+00", 29822.40, "выход по СИГНАЛУ"),
           ("ROSN", "2025-10-15 21:00:00+00", -52010.55, "выход СТОПОМ")]
print("=== 1.2 ДВА ПОЛОЖИТЕЛЬНЫХ КОНТРОЛЯ, капитал 1 000 000 ===")
ok_all = True
for t, ts, want, what in TARGETS:
    res = h.run_forced(RULES, t, data[t], pd.Timestamp(ts))
    tr = res.trades
    got = tr[0].pnl if tr else None
    st  = tr[0].status if tr else "—"
    ok = tr and abs(round(got, 2) - want) < 0.005
    ok_all &= bool(ok)
    print(f"  {t:5} {what:18} сделок={len(tr)} status={st:8} "
          f"pnl={got if got is None else round(got,2):>12} ожидалось={want:>12} "
          f"-> {'СОВПАЛО' if ok else 'РАСХОЖДЕНИЕ — СТОП'}")
    if tr:
        print(f"        вход {tr[0].entry_date} по {tr[0].entry_price} x {tr[0].shares} шт., "
              f"выход {tr[0].exit_date} по {tr[0].exit_price}")
print(f"  ИТОГ 1.2: {'ОБА ПРОЙДЕНЫ' if ok_all else 'ПРОВАЛ'}")
print()
print("=== 1.3 ОТРИЦАТЕЛЬНЫЙ КОНТРОЛЬ ===")
res = h.run_forced(RULES, "PLZL", data["PLZL"], data["PLZL"].index[400])
print(f"  бар без сигнала (PLZL, {data['PLZL'].index[400]}): сделок={len(res.trades)+len(res.open_trades_at_end)}"
      f" -> {'подала, как и должна' if (res.trades or res.open_trades_at_end) else 'НЕ ПОДАЛА — дефект'}")
real = h.RulesEngine(rules_file=RULES)
stub = h.ForcedEntryRules(real, set())
eng  = h.BacktestEngine(rules_engine=stub, timeframe="D1")
r2 = eng.run("PLZL", data["PLZL"])
print(f"  пустой список дат: сделок={len(r2.trades)}, заглушка срабатывала {len(stub.fired)} раз")
print(f"  -> форма {'обязана дать rc!=0: run_forced бросает SystemExit при нулевом срабатывании' if not stub.fired else '??'}")
try:
    h.run_forced(RULES, "PLZL", data["PLZL"], pd.Timestamp(data["PLZL"].index[5]))
    print("  rc-контроль: НЕ бросила — дефект")
except SystemExit as e:
    print(f"  rc-контроль (бар в разогреве): SystemExit -> «{str(e)[:70]}»")
