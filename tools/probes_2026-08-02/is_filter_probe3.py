"""Разогрев SMA200: с какой сессии фильтр вообще МОЖЕТ сработать, и что в IS после."""
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
need = max(cfg["sma_long"], cfg["lower_low_lookback"] + 1)
print(f"Параметры: {cfg}")
print(f"Баров, нужных чтобы ВСЕ три условия могли стать True: {need} "
      f"(sma_long={cfg['sma_long']}, lower_low_lookback+1={cfg['lower_low_lookback']+1})")

conn = psycopg2.connect(config.db.dsn); conn.set_session(readonly=True, autocommit=True)
gates, warm = {}, {}
for t in T12:
    q = ("SELECT (time AT TIME ZONE 'Europe/Moscow')::date AS d, open, high, low, close, volume "
         "FROM candles WHERE ticker=%s AND timeframe='1d' ORDER BY time")
    df = pd.read_sql(q, conn, params=(t,)); df["d"] = pd.to_datetime(df["d"])
    df = df.set_index("d")
    warm[t] = df.index[need - 1] if len(df) >= need else None
    gates[t] = structural_downtrend_series(df, **cfg)
conn.close()

print("\nПервая сессия, на которой фильтр МОЖЕТ быть True (бар №{}):".format(need))
for t in T12:
    print(f"   {t:<5} {warm[t].date() if warm[t] is not None else 'нет'}")

latest = max(w for w in warm.values() if w is not None)
print(f"\nПОЗЖЕ ВСЕХ разогревается: {latest.date()}")

G = pd.DataFrame(gates)
IS = G.loc[(G.index >= "2023-07-12") & (G.index <= "2024-12-31")]
n_is = len(IS)
before = IS.loc[IS.index < latest]
after = IS.loc[IS.index >= latest]
print(f"\nIS: сессий {n_is}")
print(f"   до разогрева всех 12  : {len(before)} сессий ({100*len(before)/n_is:.0f}% IS) — "
      f"фильтр НЕ МОЖЕТ сработать у части бумаг по построению (fillna(False))")
print(f"   после разогрева всех  : {len(after)} сессий")
for nm, W in (("IS до разогрева", before), ("IS после разогрева", after)):
    if not len(W):
        continue
    c = (W == True).sum(axis=1)   # noqa: E712
    print(f"   [{nm}] закрытых бумаг: медиана {c.median():.0f}/12, среднее {c.mean():.1f}, "
          f"максимум {c.max()}, сессий с закрытыми у всех {(c == 12).sum()}")
OOS = G.loc[(G.index >= "2025-01-01") & (G.index <= "2026-07-29")]
c = (OOS == True).sum(axis=1)     # noqa: E712
print(f"   [OOS целиком]      закрытых бумаг: медиана {c.median():.0f}/12, среднее {c.mean():.1f}, "
      f"максимум {c.max()}, сессий с закрытыми у всех {(c == 12).sum()}")
