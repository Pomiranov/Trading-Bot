"""Проверка НЕ-ДЕГЕНЕРАТИВНОСТИ выхода З4. Не пятый замер, а контроль того,
что 20/20 есть свойство рынка, а не всегда-True серия.

Та же проектная функция, та же причинная семантика. Печатается:
  - доля True по ВСЕЙ истории каждой бумаги (если 100% — серия вырождена);
  - число бумаг под фильтром на КАЖДОЙ из последних 15 московских сессий
    (по .iloc[i] своего бара — не .iloc[-1]).
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

import asyncpg
import pandas as pd

sys.path.insert(0, "D:/Trading-Bot-Nik/bot")
from config import config                                   # noqa: E402
from market_time import session_date                        # noqa: E402
from universe import FORWARD_TICKERS                        # noqa: E402
from signals.indicators import structural_downtrend_series  # noqa: E402
from signals.rules_engine import RulesEngine                # noqa: E402

GATE_KEYS = ("sma_short", "sma_long", "lower_low_lookback", "lower_low_window")
RULES_FILE = config.rules_dir / "rules_osc_range.yaml"


async def main() -> None:
    rules = RulesEngine(rules_file=RULES_FILE)
    full_cfg = rules.structural_downtrend_filter
    params = {k: full_cfg[k] for k in GATE_KEYS if k in full_cfg}

    conn = await asyncpg.connect(config.db.dsn)
    per_session = {}   # msk_session -> число бумаг под фильтром
    try:
        print("Доля True по всей истории (100% = серия вырождена, значит замер "
              "измерил бы дефект):")
        print(f"{'ticker':7} {'bars':>5} {'true':>6} {'share':>7}")
        for ticker in FORWARD_TICKERS:
            rows = await conn.fetch(
                "SELECT time, open, high, low, close, volume FROM candles "
                "WHERE ticker = $1 AND timeframe = '1d' ORDER BY time", ticker)
            raw_times = [r["time"] for r in rows]
            df = pd.DataFrame(
                {
                    "open":   [float(r["open"]) for r in rows],
                    "high":   [float(r["high"]) for r in rows],
                    "low":    [float(r["low"]) for r in rows],
                    "close":  [float(r["close"]) for r in rows],
                    "volume": [int(r["volume"]) for r in rows],
                },
                index=pd.DatetimeIndex([t.replace(tzinfo=None) for t in raw_times],
                                       name="datetime"),
            )
            s = structural_downtrend_series(df, **params)
            n_true = int(s.sum())
            print(f"{ticker:7} {len(s):5} {n_true:6} {n_true / len(s) * 100:6.1f}%")

            for i in range(max(0, len(s) - 15), len(s)):
                key = session_date(raw_times[i])
                per_session.setdefault(key, [0, 0])
                per_session[key][0] += int(bool(s.iloc[i]))
                per_session[key][1] += 1

        print()
        print("Число бумаг под фильтром по московским сессиям "
              "(.iloc[i] своего бара):")
        print(f"{'msk_session':12} {'under':>6} {'of':>4}")
        for key in sorted(per_session):
            under, total = per_session[key]
            print(f"{key.isoformat():12} {under:6} {total:4}")
    finally:
        await conn.close()


asyncio.run(main())
