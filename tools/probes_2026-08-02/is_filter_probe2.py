"""Сверка с записанным «19 сессий из 892, 2.1%» + список сессий «закрыт у всех»."""
import inspect
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

ROOT = Path(r"D:\worktrees\qf-notify-p2p1")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "bot"))
load_dotenv(Path(r"D:\Trading-Bot-Nik") / ".env")

from config import config                                    # noqa: E402
from signals.indicators import structural_downtrend_series    # noqa: E402
from signals.rules_engine import RulesEngine                  # noqa: E402
from universe import MEASUREMENT_UNIVERSE_2026_07 as T12      # noqa: E402

eng = RulesEngine(rules_file=config.rules_dir / "rules_osc_range.yaml")
cfg = dict(eng.structural_downtrend_filter or {})
allowed = set(inspect.signature(structural_downtrend_series).parameters) - {"df", "df_d1"}
cfg = {k: v for k, v in cfg.items() if k in allowed}

conn = psycopg2.connect(config.db.dsn); conn.set_session(readonly=True, autocommit=True)
gates = {}
for t in T12:
    q = ("SELECT (time AT TIME ZONE 'Europe/Moscow')::date AS d, open, high, low, close, volume "
         "FROM candles WHERE ticker=%s AND timeframe='1d' ORDER BY time")
    df = pd.read_sql(q, conn, params=(t,)); df["d"] = pd.to_datetime(df["d"])
    gates[t] = structural_downtrend_series(df.set_index("d"), **cfg)
conn.close()

G = pd.DataFrame(gates)
known = G.notna().sum(axis=1); closed = (G == True).sum(axis=1)   # noqa: E712
allc = (known == len(T12)) & (closed == len(T12))

print(f"ВСЯ ГЛУБИНА ДАННЫХ: сессий {len(G)}, окно {G.index[0].date()} .. {G.index[-1].date()}")
print(f"  сессий «фильтр закрыт у ВСЕХ 12»: {int(allc.sum())} "
      f"({100*int(allc.sum())/len(G):.1f}%)")
print(f"  записано 01.08: 19 из 892, то есть 2.1%")
print("\nВСЕ такие сессии:")
for d in G.index[allc]:
    print("   ", d.date())
print("\nВ границах опорного окна 2023-07-12 .. 2026-07-29:")
w = G.loc[(G.index >= "2023-07-12") & (G.index <= "2026-07-29")]
kw = w.notna().sum(axis=1); cw = (w == True).sum(axis=1)          # noqa: E712
aw = (kw == len(T12)) & (cw == len(T12))
print(f"    сессий {len(w)}, закрыт у всех {int(aw.sum())}")
