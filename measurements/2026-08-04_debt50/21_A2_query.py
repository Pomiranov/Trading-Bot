import sys
sys.path.insert(0, "D:/Trading-Bot-Nik/bot")
from pathlib import Path
from signals.rules_engine import RulesEngine
from backtest.engine import BacktestEngine
from universe import MEASUREMENT_UNIVERSE_2026_07_VERSION as UV

PRE = [("rsi_period",14,60),("atr_period",14,60),("adx_period",14,60),("bb_period",20,86),
       ("macd_fast",12,52),("macd_slow",26,112),("macd_signal_period",9,39),("ema_fast",9,39),
       ("ema_slow",21,90),("pivot_strength",3,13),("pivot_max_age",25,108),
       ("rsi9_period",9,39),("stoch_window",14,60),("stoch_smooth",3,13),
       ("mac_ema_period",28,120)]
CASES = [("D1", "knowledge/rules/rules_osc_range.yaml", 61, 50, 1),
         ("H4", sys.argv[1],                            262, 215, 2)]
print("А2: ФАКТИЧЕСКИЕ поля собранного движка. Не пересчёт, а чтение.")
total_bad = 0
for tf, rf, w_exp, warm_exp, col in CASES:
    e = BacktestEngine(universe_version=UV, rules_engine=RulesEngine(rules_file=Path(rf)),
                       timeframe=tf)
    ind = e._indicators
    ok_w = e._window_bars == w_exp
    ok_h = e._warmup_bars == warm_exp
    print(f"\n--- {tf}, правила {Path(rf).name} ---")
    print(f"  _window_bars = {e._window_bars} (ждём {w_exp}) {'OK' if ok_w else 'РАСХОЖДЕНИЕ'}")
    print(f"  _warmup_bars = {e._warmup_bars} (ждём {warm_exp}) {'OK' if ok_h else 'РАСХОЖДЕНИЕ'}")
    total_bad += (not ok_w) + (not ok_h)
    bad = []
    for name, d1, h4 in PRE:
        got = getattr(ind, name); exp = d1 if col == 1 else h4
        if got != exp:
            bad.append((name, got, exp))
    total_bad += len(bad)
    print(f"  15 параметров индикаторов: расхождений {len(bad)} {bad}")
    print(f"  ИТОГО 17 значений: {'ВСЕ СОШЛИСЬ' if not bad and ok_w and ok_h else 'ЕСТЬ РАСХОЖДЕНИЕ'}")
print(f"\nРАСХОЖДЕНИЙ ВСЕГО (оба ТФ, 34 значения): {total_bad}")
