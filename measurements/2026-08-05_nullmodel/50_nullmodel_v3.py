"""Chast D, BOLSHAYA SERIYA. Vse resheniya obyavleny DO pervogo progona.

Zapusk:
    cd bot
    python ../measurements/2026-08-05_nullmodel/50_nullmodel_v3.py --mode smoke --procs 1
    python ../measurements/2026-08-05_nullmodel/50_nullmodel_v3.py --mode series --procs auto

CHTO IZMENILOS PROTIV N=200 - rovno dve veshchi, i obe obyavleny:
  N: 200 -> 1000;
  sid: 20260805 -> MASTER_SEED nizhe (prezhniy povtoril by pervye 200 progonov).
Vse ostalnoe BEZ IZMENENIY: razrez tolko OOS, variant (I) po bumagam, pravilo
stolknoveniy (a) s predelom 300, DVE statistiki, polosy razresheniya, porog 30
polozhitelnyh progonov dlya mediany.

POCHEMU STATISTIKA NE MENYAETSYA. Pervaya statistika ne razreshila, i soblazn
zamenit ee "bolee moshchnoy" velik - no vybor statistiki POSLE togo, kak izvestno,
chto ona ne razreshila, est podgonka. Menyaetsya TOLKO N.

KONTROL "POSLE" UDALEN, a ne oslablen. Zamer po kodu: load_candles_db zovetsya ODIN
RAZ, oba prezhnih kontrolya chitali TOT ZHE obyekt pamyati => ih ravenstvo bylo
tozhdestvom, a ne proverkoy. Seriya atomarna po dannym, "dreyf posredi serii"
nevozmozhen. Kontrol "DO" ostavlen: on pereschityvaet troyku iz ZAGRUZHENNYH dannyh
protiv zamorozhennoy tseli - eto ne tozhdestvo.
Vmesto kontrolya "posle" - OTPECHATOK zagruzhennogo massiva (pravilo 25 §8).

KLON NE NUZHEN: bekstest v trades ne pishet po postroeniyu (orchestrator=None),
svechi chitaet odin raz => seriya read-only, vremya sutok bezrazlichno.

PARALLELIZM (punkt 1). Prichina: N=1000 x 20.30 s = 5 ch 38 min v odin potok, a
mashinu VYKLYUCHAYUT (zamereno §10a) => seriya ne dozhivet. N=1000 obyavleno
poslednim i ne menyaetsya, znachit menyaetsya sposob.
  Sid kazhdogo progona: random.Random(f"{MASTER}:{k}"), gde k - nomer progona.
  => rezultat NE ZAVISIT ot chisla rabochih protsessov PO POSTROENIYU.
  Determinizm DOKAZYVAETSYA, a ne zayavlyaetsya: --mode smoke prognan na 1 i na 2
  protsessah daet pobaytovo odinakovyy TSV posle sortirovki po nomeru progona.

KONTROLNYE TOCHKI (punkt 3). Stroka TSV pishetsya SRAZU po zavershenii kazhdogo
progona (flush), a ne v kontse serii: obryv ne stiraet schet. Vozobnovlenie
prodolzhaet s togo zhe nomera i NE menyaet posledovatelnost sidov (sleduet iz 1.2).
ZAPRET: chastichnyy TSV vo vremya serii NE CHITAT - eto podglyadyvanie v
raspredelenie.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import random
import statistics as st
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")

from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07  # noqa: E402
from backtest.candles import load_candles_db                              # noqa: E402
from backtest.engine import BacktestEngine                                # noqa: E402
from signals.rules_engine import RulesEngine                              # noqa: E402

# ── OBYAVLENNYE VELICHINY ─────────────────────────────────────────────────────
MASTER_SEED = 20260806      # punkt 4.1. 20260805 pereispolzovat NELZYA
SMOKE_SEED = 777            # punkt 2.1. Otdelnyy: master na smoke NE ispolzuetsya
N_SERIES = 1000             # punkt 2 promta: POSLEDNYAYA seriya etogo pribora
N_SMOKE = 6
TRIES = 300                 # predel popytok na bumagu, pravilo stolknoveniy (a)
POROG_POS = 30              # menshe - mediana ne snimaetsya
EXPECT_FP = "0216ab485d977d91"
EXPECT_RAW, EXPECT_RND = 127747.96, 127747.97

IS_END = pd.Timestamp("2025-01-01")
HERE = Path(__file__).resolve().parent
RULES = (HERE.parents[1] / "knowledge" / "rules" / "rules_osc_range.yaml").resolve()

_G = {}


def _pf(p):
    gp = sum(x for x in p if x > 0)
    gl = -sum(x for x in p if x <= 0)
    return gp / gl if gl else float("inf")


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "h", str(HERE / ".." / "2026-08-05_step2" / "05_stub_harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _prepare():
    """Zagruzka svechey, otpechatok, pul i nablyudennye chisla. Odin raz na protsess."""
    data = asyncio.run(load_candles_db(
        "1d", list(MEASUREMENT_UNIVERSE_2026_07), SAMPLE_START_2026_07, date(2026, 7, 29)))
    rows = 0
    tmin = tmax = None
    h = hashlib.sha256()
    for t in sorted(data):
        d = data[t]
        rows += len(d)
        a, b = d.index[0], d.index[-1]
        tmin = a if tmin is None or a < tmin else tmin
        tmax = b if tmax is None or b > tmax else tmax
        for c in ("open", "high", "low", "close", "volume"):
            h.update(t.encode())
            h.update(d[c].to_numpy().tobytes())
    fp = h.hexdigest()[:16]
    real = RulesEngine(rules_file=RULES)
    allowed, observed = {}, {}
    for t in sorted(data):
        e = BacktestEngine(rules_engine=real, timeframe="D1")
        dd = e._drop_forming_bar(t, data[t])
        di = e._indicators.compute(dd)
        gate = e._downtrend_gate(dd, di.index)
        idx = list(di.index)
        allowed[t] = [idx[i] for i in range(e._warmup_bars, len(idx))
                      if (gate is None or not bool(gate.iloc[i]))
                      and pd.Timestamp(idx[i]).tz_localize(None) >= IS_END]
        r = e.run(t, data[t])
        observed[t] = sum(1 for x in r.trades
                          if pd.Timestamp(x.entry_date).tz_localize(None) >= IS_END)
    return dict(data=data, allowed=allowed, observed=observed, fp=fp, rows=rows,
                tmin=tmin, tmax=tmax, h=_load_harness())


def _worker_init():
    _G.update(_prepare())


def _one_run(arg):
    """Odin progon nul-modeli. Sid vyvoditsya iz mastera i nomera - punkt 1.2."""
    k, seed_base = arg
    g = _G if _G else None
    if g is None:
        _worker_init()
        g = _G
    seed_str = f"{seed_base}:{k}"
    rng = random.Random(seed_str)
    pnls, dates = [], []
    short = False
    for t in sorted(g["data"]):
        need = g["observed"][t]
        got = tries = 0
        while got < need and tries < TRIES:
            tries += 1
            ts = rng.choice(g["allowed"][t])
            try:
                res = g["h"].run_forced(RULES, t, g["data"][t], ts)
            except SystemExit:
                continue
            if res.trades:
                pnls.append(res.trades[0].pnl)
                dates.append(f"{t}:{pd.Timestamp(ts).date()}")
                got += 1
        if got < need:
            short = True
    s = sum(pnls)
    top2 = sorted(pnls, reverse=True)[:2]
    return dict(k=k, seed=seed_str, n=len(pnls), pf=_pf(pnls), pnl=s,
                short=short, top2=(sum(top2) / s * 100 if s else None),
                dates=";".join(dates))


def _control_before(g):
    """Kontrol DO. Pochinen svedeniem sposoba: DVE summy, kazhdaya so svoey tselyu."""
    real = RulesEngine(rules_file=RULES)
    out = []
    for t in sorted(g["data"]):
        r = BacktestEngine(rules_engine=real, timeframe="D1").run(t, g["data"][t])
        out += [x.pnl for x in r.trades
                if pd.Timestamp(x.entry_date).tz_localize(None) >= IS_END]
    n = len(out)
    w = sum(1 for x in out if x > 0)
    raw = sum(out)
    rnd = sum(round(x, 2) for x in out)
    ok = (n == 18 and round(100 * w / n, 1) == 72.2 and round(_pf(out), 3) == 1.638
          and round(raw, 2) == EXPECT_RAW and round(rnd, 2) == EXPECT_RND)
    print(f"KONTROL DO: n={n} WR={100*w/n:.1f}% PF={_pf(out):.3f} "
          f"PnL_syraya={raw:.2f} (cel {EXPECT_RAW}) PnL_okrugl={rnd:.2f} (cel {EXPECT_RND})"
          f" -> {'SOSHLOS' if ok else 'RASHOZHDENIE'}")
    return ok


HEADER = "run\tseed\tn\tpf\tpnl\ttop2_share_pct\tshort\tentries"


def _fmt(r):
    sh = "" if r["top2"] is None else f"{r['top2']:.4f}"
    return (f"{r['k']}\t{r['seed']}\t{r['n']}\t{r['pf']:.6f}\t{r['pnl']:.4f}\t"
            f"{sh}\t{int(r['short'])}\t{r['dates']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "series"], required=True)
    ap.add_argument("--procs", default="1")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    smoke = a.mode == "smoke"
    seed_base = SMOKE_SEED if smoke else MASTER_SEED
    N = N_SMOKE if smoke else N_SERIES
    procs = (max(1, (os.cpu_count() or 2) - 2) if a.procs == "auto" else int(a.procs))
    out_tsv = Path(a.out) if a.out else HERE / (
        f"70_SMOKE_p{procs}.tsv" if smoke else "60_DISTRIBUTION_N1000.tsv")

    print(f"MODE={a.mode}  seed_base={seed_base}  N={N}  procs={procs}  "
          f"yader v sisteme={os.cpu_count()}")
    if smoke:
        print("SMOKE: sid 777, CHISLA NEDEYSTVITELNY, v reestr ne vnosyatsya")

    _worker_init()
    g = _G
    print(f"OTPECHATOK SVECHEY: strok={g['rows']} tikerov={len(g['data'])} "
          f"min={g['tmin']} max={g['tmax']} sha256[:16]={g['fp']} "
          f"-> {'SOVPAL' if g['fp'] == EXPECT_FP else 'RASHOZHDENIE'}")
    if g["fp"] != EXPECT_FP:
        raise SystemExit(f"OTKAZ: otpechatok {g['fp']} != {EXPECT_FP}")
    if not _control_before(g):
        raise SystemExit("OTKAZ: kontrol DO ne proshel, seriya ne zapuskaetsya")
    nobs = sum(g["observed"].values())
    print(f"nablyudennyh D1/OOS={nobs} razreshennyh OOS-barov={sum(len(v) for v in g['allowed'].values())}")
    if nobs != 18:
        raise SystemExit(f"OTKAZ: nablyudennyh {nobs} != 18")

    # ── vozobnovlenie: chitaem TOLKO nomera progonov, ne znacheniya (punkt 3.2) ──
    done = set()
    if out_tsv.exists():
        for ln in out_tsv.read_text(encoding="utf-8").splitlines()[1:]:
            if ln.strip():
                done.add(int(ln.split("\t")[0]))
        print(f"VOZOBNOVLENIE: uzhe est {len(done)} progonov, posledovatelnost sidov ne menyaetsya")
    else:
        out_tsv.write_text(HEADER + chr(10), encoding="utf-8")
    todo = [(k, seed_base) for k in range(N) if k not in done]
    if not todo:
        print("vse progony uzhe est")
        return

    t0 = time.perf_counter()
    fh = out_tsv.open("a", encoding="utf-8")
    results = []
    if procs == 1:
        for arg in todo:
            r = _one_run(arg)
            results.append(r)
            fh.write(_fmt(r) + chr(10))
            fh.flush()                      # punkt 3.1: srazu, ne v kontse
            print(f"  progon {r['k']} sid={r['seed']} n={r['n']} godnyy={not r['short'] and r['n']==18}")
    else:
        import multiprocessing as mp
        with mp.Pool(procs, initializer=_worker_init) as pool:
            for r in pool.imap_unordered(_one_run, todo, chunksize=1):
                results.append(r)
                fh.write(_fmt(r) + chr(10))
                fh.flush()
                if smoke or (len(results) % 50 == 0):
                    print(f"  progon {r['k']} sid={r['seed']} n={r['n']} "
                          f"godnyy={not r['short'] and r['n']==18} "
                          f"({len(results)}/{len(todo)}, {time.perf_counter()-t0:.0f} s)")
    fh.close()
    dt = time.perf_counter() - t0
    print(f"VREMYA: {dt:.1f} s na {len(todo)} progonov = {dt/len(todo):.2f} s/progon "
          f"pri procs={procs}")

    # ── TSV sortiruetsya po nomeru progona: pobaytovaya sravnimost (punkt 1.3) ──
    body = sorted((ln for ln in out_tsv.read_text(encoding="utf-8").splitlines()[1:] if ln.strip()),
                  key=lambda x: int(x.split("\t")[0]))
    out_tsv.write_text(HEADER + chr(10) + chr(10).join(body) + chr(10), encoding="utf-8")

    if smoke:
        print("SMOKE ZAVERSHEN. Statistiki NE snimayutsya: chisla nedeystvitelny.")
        bad = [r for r in results if r["n"] != 18]
        print(f"  progonov s n!=18: {len(bad)}")
        allmin = min(d.split(":")[1] for r in results for d in r["dates"].split(";"))
        print(f"  minimalnaya vytyanutaya data vhoda: {allmin} "
              f"-> {'VSE >= 2025-01-01' if allmin >= '2025-01-01' else 'ESTIS-DATY - DEFEKT'}")
        return

    good = [r for r in results if not r["short"] and r["n"] == 18]
    pfs = sorted(r["pf"] for r in good)
    pos = [r for r in good if r["pnl"] > 0]
    neg = [r for r in good if r["pnl"] <= 0]
    pct = 100 * sum(1 for x in pfs if x < 1.638) / len(pfs)
    print(f"GODNYH: {len(good)} iz {N}")
    print(f"3.1 PROTSENTIL PF 1.638: {pct:.1f}")
    print(f"    p1={pfs[int(.01*len(pfs))]:.3f} p5={pfs[int(.05*len(pfs))]:.3f} "
          f"mediana={st.median(pfs):.3f} p95={pfs[int(.95*len(pfs))]:.3f} "
          f"p99={pfs[int(.99*len(pfs))]:.3f}")
    print(f"    OTRITSATELNYH: {len(neg)} iz {len(good)} = {100*len(neg)/len(good):.1f}%")
    med = None
    if len(pos) < POROG_POS:
        print(f"3.2 MEDIANA doli top-2: NE RAZRESHIMO (polozhitelnyh {len(pos)} < {POROG_POS})")
    else:
        med = st.median([r["top2"] for r in pos])
        print(f"3.2 MEDIANA doli top-2 (pnl>0, n={len(pos)}): {med:.1f}% (nablyudennoe 103.2%)")
    (HERE / "65_SUMMARY_N1000.json").write_text(json.dumps(dict(
        master_seed=MASTER_SEED, N=N, tries=TRIES, procs=procs,
        candles_fingerprint=g["fp"], candles_rows=g["rows"],
        control_before_ok=True, control_after="UDALEN (tozhdestvo)",
        good=len(good), percentile_of_1638=pct, negative_runs=len(neg),
        positive_runs=len(pos), median_top2_share=med,
        p1=pfs[int(.01*len(pfs))], p5=pfs[int(.05*len(pfs))],
        median_pf=st.median(pfs), p95=pfs[int(.95*len(pfs))],
        p99=pfs[int(.99*len(pfs))], seconds=dt), ensure_ascii=False, indent=2),
        encoding="utf-8")


if __name__ == "__main__":
    main()
