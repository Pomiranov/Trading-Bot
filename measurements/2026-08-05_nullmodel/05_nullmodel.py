"""Часть D попытки №4: нуль-модель. РЕШЕНИЯ ОБЪЯВЛЕНЫ ДО ПЕРВОГО ПРОГОНА.

1.1 ПРИКОЛОЧЕНО: набор 12 (MEASUREMENT_UNIVERSE_2026_07), окно 2023-07-12 …
    --as-of 2026-07-29, механика выхода делегируется боевому движку (2xATR с
    трейлингом), издержки боевые (costs.COMMISSION_PCT), капитал 1 000 000 на
    бумагу, плечо С ФИЛЬТРОМ.
1.2 Рандомизируется ТОЛЬКО дата входа, и только среди баров, где фильтр РАЗРЕШАЛ
    вход (gate False). Иначе замер проверял бы фильтр, а не правила.
1.3 РАСПРЕДЕЛЕНИЕ ПО БУМАГАМ — вариант (I): сохраняется НАБЛЮДЁННОЕ число входов
    на каждую бумагу. Обоснование: предмет части D — «умеют ли правила выбирать
    МОМЕНТ», и вариант (I) оставляет случайным ровно момент. Вариант (II) (тянуть
    свободно по 12) проверял бы ещё и выбор бумаги — другой вопрос, новая запись.
    ⚠ Разрез: сравнение идёт с PF 1.638 разреза D1/OOS, поэтому и тянутся ТОЛЬКО
    OOS-бары, и наблюдённое число берётся по OOS. n каждого прогона = 18 ровно.
1.4 СТОЛКНОВЕНИЯ — вариант (а): тянуть даты, пока не наберётся ровно наблюдённое
    число СДЕЛОК по бумаге. Обоснование: объявленные статистики (PF и доля top-2)
    зависят от n, и фиксация n = 18 убирает n из сравнения. Предел попыток на
    бумагу — 300, при недоборе прогон помечается и в статистику НЕ идёт.
    Смещение названо: отбор «до успеха» предпочитает бары, где столкновения нет;
    это и есть «годная выборка из 18 сделок», то есть цель сравнения.
1.5 ГПСЧ: random.Random из stdlib — в проекте ГПСЧ не было вовсе (замерено).
    СИД ПЕЧАТАЕТСЯ в шапке. Серия воспроизводима одной командой.
1.6 N объявлен ЧИСЛОМ ДО серии из замера: один прогон 20.30 с ⇒ N = 200 (~68 мин).
    N=1000 потребовал бы 5.6 часа и в сессию не влезает — уменьшение объявлено
    ЗАРАНЕЕ, а не после взгляда на числа.

СТАТИСТИК ДВЕ, больше ни одной:
  3.1 процентиль наблюдённого PF 1.638 в распределении нуля;
  3.2 медиана доли top-2 сделок в PnL прогона (наблюдённое 103.2 %).
"""
import asyncio, importlib.util, json, random, sys, time
from datetime import date
from pathlib import Path
import pandas as pd
sys.path.insert(0, ".")
from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07
from backtest.candles import load_candles_db
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine

SEED, N, TRIES = 20260805, 200, 300
IS_END = pd.Timestamp("2025-01-01")      # ЧИТАЕТСЯ (run_osc_oos_debug.py:47)
RULES = Path("../knowledge/rules/rules_osc_range.yaml").resolve()
OUT = Path("../measurements/2026-08-05_nullmodel")
spec = importlib.util.spec_from_file_location("h", "../measurements/2026-08-05_step2/05_stub_harness.py")
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)

def pf(p):
    gp = sum(x for x in p if x > 0); gl = -sum(x for x in p if x <= 0)
    return gp / gl if gl else float("inf")

def drift_control(tag):
    """Контроль дрейфа: боевая тройка D1/OOS с фильтром. Долг №41."""
    real = RulesEngine(rules_file=RULES)
    out = []
    for t in sorted(data):
        r = BacktestEngine(rules_engine=real, timeframe="D1").run(t, data[t])
        out += [x.pnl for x in r.trades
                if pd.Timestamp(x.entry_date).tz_localize(None) >= IS_END] \
               if data[t] is not None else []
    n = len(out); s = sum(out); w = sum(1 for x in out if x > 0)
    line = (f"[{tag}] n={n} WR={100*w/n:.1f}% PF={pf(out):.3f} PnL={s:.2f}")
    ok = (n == 18 and round(100*w/n,1) == 72.2 and round(pf(out),3) == 1.638
          and round(s,2) == 127747.97)
    print(f"  {line}  -> {'СОШЛОСЬ' if ok else 'РАСХОЖДЕНИЕ — СЕРИЯ НЕДЕЙСТВИТЕЛЬНА'}")
    return ok, line

print(f"НУЛЬ-МОДЕЛЬ. СИД={SEED}  N={N}  предел попыток на бумагу={TRIES}")
data = asyncio.run(load_candles_db("1d", list(MEASUREMENT_UNIVERSE_2026_07),
                                   SAMPLE_START_2026_07, date(2026, 7, 29)))
real = RulesEngine(rules_file=RULES)
allowed, observed = {}, {}
for t in sorted(data):
    e = BacktestEngine(rules_engine=real, timeframe="D1")
    d = e._drop_forming_bar(t, data[t]); di = e._indicators.compute(d)
    gate = e._downtrend_gate(d, di.index); idx = list(di.index)
    allowed[t] = [idx[i] for i in range(e._warmup_bars, len(idx))
                  if (gate is None or not bool(gate.iloc[i]))
                  and pd.Timestamp(idx[i]).tz_localize(None) >= IS_END]
    r = e.run(t, data[t])
    observed[t] = sum(1 for x in r.trades
                      if pd.Timestamp(x.entry_date).tz_localize(None) >= IS_END)
print(f"  наблюдённых входов D1/OOS: {sum(observed.values())} (ожидалось 18)")
print(f"  разрешённых OOS-баров: {sum(len(v) for v in allowed.values())}")
print("КОНТРОЛЬ ДРЕЙФА ДО СЕРИИ:")
ok_before, line_before = drift_control("до")

rng = random.Random(SEED)
runs, t0 = [], time.perf_counter()
for k in range(N):
    pnls, short = [], False
    for t in sorted(data):
        need = observed[t]
        got = 0; tries = 0
        while got < need and tries < TRIES:
            tries += 1
            try:
                res = h.run_forced(RULES, t, data[t], rng.choice(allowed[t]))
            except SystemExit:
                continue
            if res.trades:
                pnls.append(res.trades[0].pnl); got += 1
        if got < need: short = True
    top2 = sorted(pnls, reverse=True)[:2]
    s = sum(pnls)
    runs.append(dict(k=k, n=len(pnls), pf=pf(pnls), pnl=s, short=short,
                     top2_share=(sum(top2)/s*100 if s else None)))
    if (k+1) % 20 == 0:
        print(f"  прогонов {k+1}/{N}, {time.perf_counter()-t0:.0f} с")
print("КОНТРОЛЬ ДРЕЙФА ПОСЛЕ СЕРИИ:")
ok_after, line_after = drift_control("после")

good = [r for r in runs if not r["short"] and r["n"] == 18]
pfs = sorted(r["pf"] for r in good)
shares = sorted(r["top2_share"] for r in good if r["top2_share"] is not None)
import statistics as st
obs_pf = 1.638
below = sum(1 for x in pfs if x < obs_pf)
print()
print(f"ГОДНЫХ ПРОГОНОВ: {len(good)} из {N} (n=18 и без недобора)")
print(f"3.1 ПРОЦЕНТИЛЬ наблюдённого PF {obs_pf}: {100*below/len(pfs):.1f}")
print(f"    распределение нуля: p5={pfs[int(.05*len(pfs))]:.3f} медиана={st.median(pfs):.3f} "
      f"p95={pfs[int(.95*len(pfs))]:.3f} min={pfs[0]:.3f} max={pfs[-1]:.3f}")
print(f"3.2 МЕДИАНА доли top-2: {st.median(shares):.1f}%  (наблюдённое 103.2%)")
lines = ["run	n	pf	pnl	top2_share_pct	short"]
for r in runs:
    sh = "" if r["top2_share"] is None else f"{r['top2_share']:.4f}"
    lines.append(f"{r['k']}	{r['n']}	{r['pf']:.6f}	{r['pnl']:.4f}	{sh}	{int(r['short'])}")
Path(OUT/"20_DISTRIBUTION.tsv").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
Path(OUT/"25_SUMMARY.json").write_text(json.dumps(dict(
    seed=SEED, N=N, tries=TRIES, one_run_sec=20.30, good=len(good),
    percentile_of_1638=100*below/len(pfs), p5=pfs[int(.05*len(pfs))],
    median_pf=st.median(pfs), p95=pfs[int(.95*len(pfs))],
    median_top2_share=st.median(shares), drift_before=line_before,
    drift_after=line_after, drift_ok=bool(ok_before and ok_after)), ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nулики записаны в {OUT}")
