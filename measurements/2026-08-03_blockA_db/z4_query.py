"""З4: сколько бумаг набора под фильтром структурного даунтренда НА БАРЕ
московской сессии 2026-07-31.

ТОЛЬКО ЧТЕНИЕ: единственный SQL — SELECT из candles, дословно тот же, что в
run_forward_d1.py::_prepare_ticker (строки 526-531).

СЕМАНТИКА — ПРИЧИННАЯ, как dt_gate.iloc[i] в backtest/engine.py::_downtrend_gate:
значение фильтра читается НА БАРЕ СВОЕЙ СЕССИИ, а не .iloc[-1] полной серии.
Ради контраста печатается и .iloc[-1] — это семантика живого контура
(trading_orchestrator -> is_structural_downtrend, долг №48).

Своей реализации трёх условий здесь НЕТ: вызывается проектная
signals.indicators.structural_downtrend_series. Параметры берутся из боевого
rules-файла через RulesEngine.structural_downtrend_filter и фильтруются тем же
набором ключей, что в _downtrend_gate (engine.py:441-445).
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

import asyncpg
import pandas as pd

ROOT = Path(__file__).resolve()
BOT = Path("D:/Trading-Bot-Nik/bot")
sys.path.insert(0, str(BOT))

import config as cfg_mod                                    # noqa: E402
from config import config                                   # noqa: E402
from market_time import session_date                        # noqa: E402
from universe import FORWARD_TICKERS, FORWARD_TICKERS_VERSION  # noqa: E402
from signals.indicators import structural_downtrend_series  # noqa: E402
from signals.rules_engine import RulesEngine                # noqa: E402

TARGET_SESSION = date(2026, 7, 31)   # МОСКОВСКАЯ ТОРГОВАЯ СЕССИЯ
RULES_FILE = config.rules_dir / "rules_osc_range.yaml"

# Ключи — те же, что отбирает engine.py::_downtrend_gate
GATE_KEYS = ("sma_short", "sma_long", "lower_low_lookback", "lower_low_window")

SQL = """
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE ticker = $1 AND timeframe = '1d'
            ORDER BY time
"""


async def main() -> None:
    rules = RulesEngine(rules_file=RULES_FILE)
    full_cfg = rules.structural_downtrend_filter
    params = {k: full_cfg[k] for k in GATE_KEYS if k in full_cfg}

    print("З4. Фильтр структурного даунтренда на баре московской сессии "
          f"{TARGET_SESSION.isoformat()}")
    print("=" * 78)
    print(f"функция:      signals.indicators.structural_downtrend_series "
          f"(bot/signals/indicators.py:93)")
    print(f"семантика:    ПРИЧИННАЯ — series.iloc[i], i = бар своей сессии "
          f"(как dt_gate.iloc[i], bot/backtest/engine.py:446-447)")
    print(f"набор:        universe.FORWARD_TICKERS, {len(FORWARD_TICKERS)} бумаг, "
          f"версия {FORWARD_TICKERS_VERSION}")
    print(f"rules-файл:   {RULES_FILE}")
    print(f"конфиг целиком: {full_cfg}")
    print(f"params -> structural_downtrend_series: {params}")
    print(f"загрузка свечей: дословный SELECT из _prepare_ticker "
          f"(bot/run_forward_d1.py:526-531), индекс tz-naive как там же (599-601)")
    print("=" * 78)
    print()

    conn = await asyncpg.connect(config.db.dsn)
    try:
        hdr = (f"{'ticker':7} {'bars':>5} {'i':>5} {'bar_label_utc':26} "
               f"{'msk_session':11} {'close':>10} {'gate@i':>7} {'gate@-1':>8} {'last==i':>8}")
        print(hdr)
        print("-" * len(hdr))

        n_true = 0
        n_checked = 0
        diverged = []
        missing = []

        for ticker in FORWARD_TICKERS:
            rows = await conn.fetch(SQL, ticker)
            raw_times = [r["time"] for r in rows]

            df = pd.DataFrame(
                {
                    "open":   [float(r["open"]) for r in rows],
                    "high":   [float(r["high"]) for r in rows],
                    "low":    [float(r["low"]) for r in rows],
                    "close":  [float(r["close"]) for r in rows],
                    "volume": [int(r["volume"]) for r in rows],
                },
                index=pd.DatetimeIndex(
                    [t.replace(tzinfo=None) for t in raw_times], name="datetime"
                ),
            )

            series = structural_downtrend_series(df, **params)

            # индекс бара ЦЕЛЕВОЙ сессии — по проектному канону session_date
            idx = [k for k, t in enumerate(raw_times)
                   if session_date(t) == TARGET_SESSION]
            if len(idx) != 1:
                missing.append((ticker, len(idx)))
                print(f"{ticker:7} {len(rows):5} {'--':>5} "
                      f"{'НЕТ БАРА ЭТОЙ СЕССИИ' if not idx else 'ДУБЛИ БАРА':26} "
                      f"{TARGET_SESSION.isoformat():11} {'--':>10} {'--':>7} {'--':>8} {'--':>8}")
                continue

            i = idx[0]
            gate_i = bool(series.iloc[i])
            gate_last = bool(series.iloc[-1])
            n_checked += 1
            n_true += int(gate_i)
            if gate_i != gate_last:
                diverged.append(ticker)

            print(f"{ticker:7} {len(rows):5} {i:5} {str(raw_times[i]):26} "
                  f"{session_date(raw_times[i]).isoformat():11} "
                  f"{float(df['close'].iloc[i]):10.2f} "
                  f"{str(gate_i):>7} {str(gate_last):>8} {str(i == len(raw_times) - 1):>8}")

        print()
        print("=" * 78)
        print(f"ИТОГ (причинная семантика, series.iloc[i]):")
        print(f"  бумаг в наборе:                         {len(FORWARD_TICKERS)}")
        print(f"  бар сессии {TARGET_SESSION.isoformat()} найден у:            {n_checked}")
        print(f"  ПОД ФИЛЬТРОМ (gate@i == True):          {n_true}")
        print(f"  НЕ под фильтром (gate@i == False):      {n_checked - n_true}")
        print(f"  бумаг без единственного бара сессии:    {len(missing)} {missing}")
        print(f"  расхождение .iloc[i] vs .iloc[-1]:      "
              f"{len(diverged)} {diverged if diverged else '(нет)'}")
        print("=" * 78)
    finally:
        await conn.close()


asyncio.run(main())
