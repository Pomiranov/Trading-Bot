"""Разовый read-only замер: состояние фильтра даунтренда по сессиям IS.

Ничего не пишет. Переиспользует предикат проекта (structural_downtrend_series),
а не воспроизводит его: вторая копия мерила бы себя.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

ROOT = Path(r"D:\worktrees\qf-notify-p2p1")
LIVE = Path(r"D:\Trading-Bot-Nik")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bot"))
load_dotenv(LIVE / ".env")          # секреты берём из боевого .env, ничего не меняя

from config import config                                    # noqa: E402
from signals.indicators import structural_downtrend_series    # noqa: E402
from signals.rules_engine import RulesEngine                  # noqa: E402
from universe import MEASUREMENT_UNIVERSE_2026_07, MEASUREMENT_UNIVERSE_2026_07_EXT  # noqa: E402

eng = RulesEngine(rules_file=config.rules_dir / "rules_osc_range.yaml")
cfg = dict(eng.structural_downtrend_filter or {})
print("Параметры фильтра из rules_osc_range.yaml:", cfg)
# Отбрасываем ровно то, что отбрасывает бэктест: enabled и apply_to — не
# параметры серии, а управление применением. Список берём из сигнатуры самой
# функции, чтобы не угадывать.
import inspect  # noqa: E402
_allowed = set(inspect.signature(structural_downtrend_series).parameters) - {"df", "df_d1"}
cfg = {k: v for k, v in cfg.items() if k in _allowed}
print("Передаём в серию:", cfg)

IS_A, IS_B = pd.Timestamp("2023-07-12"), pd.Timestamp("2024-12-31")
OOS_A, OOS_B = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-07-29")

conn = psycopg2.connect(config.db.dsn)
conn.set_session(readonly=True, autocommit=True)

def load(ticker):
    q = ("SELECT (time AT TIME ZONE 'Europe/Moscow')::date AS d, open, high, low, close, volume "
         "FROM candles WHERE ticker=%s AND timeframe='1d' ORDER BY time")
    df = pd.read_sql(q, conn, params=(ticker,))
    df["d"] = pd.to_datetime(df["d"])
    return df.set_index("d")

for label, tickers in (("НАБОР 12 (на нём считались разрезы)", MEASUREMENT_UNIVERSE_2026_07),
                       ("НАБОР 20 (_EXT)", MEASUREMENT_UNIVERSE_2026_07_EXT)):
    gates = {}
    for t in tickers:
        df = load(t)
        s = structural_downtrend_series(df, **cfg)      # причинная серия, как dt_gate бэктеста
        gates[t] = s
    G = pd.DataFrame(gates)
    print(f"\n================ {label}: {len(tickers)} бумаг ================")
    for wname, a, b in (("IS ", IS_A, IS_B), ("OOS", OOS_A, OOS_B)):
        W = G.loc[(G.index >= a) & (G.index <= b)]
        n_sess = len(W)
        known = W.notna().sum(axis=1)              # у скольких бумаг фильтр ВООБЩЕ посчитан
        closed = (W == True).sum(axis=1)           # noqa: E712  — у скольких закрыт
        full_known = (known == len(tickers))
        all_closed = full_known & (closed == len(tickers))
        undefined_all = (known == 0)
        print(f"  {wname}: сессий {n_sess}")
        print(f"      сессий, где фильтр посчитан у ВСЕХ бумаг : {int(full_known.sum())}")
        print(f"      сессий, где фильтр НЕ посчитан НИ У КОГО : {int(undefined_all.sum())}")
        print(f"      сессий, где фильтр ЗАКРЫТ у ВСЕХ         : {int(all_closed.sum())}"
              f"  ({100*int(all_closed.sum())/n_sess:.1f}% окна)")
        if int(full_known.sum()):
            sub = closed[full_known]
            print(f"      среди сессий с полным расчётом: медиана закрытых бумаг "
                  f"{sub.median():.0f} из {len(tickers)}, среднее {sub.mean():.1f}")
        first_known = W.index[full_known][0].date() if int(full_known.sum()) else None
        print(f"      первая сессия окна с полным расчётом     : {first_known}")

conn.close()
