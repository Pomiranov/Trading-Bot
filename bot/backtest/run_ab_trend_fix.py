"""A/B фиксов trend_moex (A3: ema_slow 21→50, A4: без exit ADX<20).

Запуск:
    python backtest/run_ab_trend_fix.py

Четыре варианта правил × 12 тикеров × D1 (полный период из таблицы candles):
    baseline  — ema_slow=21, exit trend_regime_lost (как до фиксов)
    a3_ema50  — только A3
    a4_noexit — только A4
    a3a4      — оба фикса (= текущий rules.yaml)

Варианты генерируются из production rules.yaml переключением ровно двух
дельт — прочие правила гарантированно идентичны. Прогон БЕЗ оркестратора:
сделки в learning/ не пишутся, метрики считаются из BacktestResult.
Диагноз: knowledge/processed/strategies/trend_following_problems_schwager.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import copy
import os
import tempfile
import time

import pandas as pd
import yaml

from config import config
from universe import (
    MEASUREMENT_UNIVERSE_2026_07, MEASUREMENT_UNIVERSE_2026_07_VERSION,
)
from backtest.engine import BacktestEngine, BacktestTrade
from signals.rules_engine import RulesEngine

# Набор ПРИКОЛОЧЕН: на нём посчитаны все опорные числа проекта. Не менять —
# набор есть часть определения измерения (bot/universe.py). Новые валидации
# делаются на MEASUREMENT_UNIVERSE_2026_07_EXT.
TICKERS = list(MEASUREMENT_UNIVERSE_2026_07)
RULES_FILE = config.rules_dir / "rules.yaml"

# Удалённое фиксом A4 правило выхода — дословно, для baseline/a3-вариантов
TREND_REGIME_LOST = {
    "name": "trend_regime_lost",
    "action": "EXIT",
    "weight": 1.0,
    "description": "Тренд ослаб (ADX < 20) - рынок вышел из режима trending",
    "conditions": [{"indicator": "adx", "operator": "<", "value": 20}],
}

VARIANTS = [
    # (id, подпись, ema50 (A3), без exit-правила (A4))
    ("baseline",  "до фиксов: EMA21 + exit ADX<20", False, False),
    ("a3_ema50",  "только A3: EMA50",               True,  False),
    ("a4_noexit", "только A4: без exit ADX<20",     False, True),
    ("a3a4",      "A3+A4 (текущий rules.yaml)",     True,  True),
]


def build_variant_files(tmp_dir: Path) -> dict[str, Path]:
    """Сгенерировать yaml каждого варианта из production rules.yaml.

    Обе дельты выставляются явно, поэтому текущее состояние rules.yaml
    (какие из фиксов A3/A4 сейчас применены) значения не имеет."""
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f)

    paths = {}
    for vid, _label, ema50, no_exit in VARIANTS:
        data = copy.deepcopy(base)
        if ema50:
            data.setdefault("indicators", {})["ema_slow"] = 50   # A3
        else:
            data.pop("indicators", None)          # без A3 → дефолт ema_slow=21
        data["exit_rules"] = [] if no_exit else [copy.deepcopy(TREND_REGIME_LOST)]
        path = tmp_dir / f"rules_trend_{vid}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        paths[vid] = path
    return paths


def dsn() -> str:
    from dotenv import load_dotenv
    load_dotenv()
    return "postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot"))


async def load_candles_db(timeframe: str = "1d") -> dict[str, pd.DataFrame]:
    """Свечи всех тикеров одного таймфрейма из таблицы candles (как в run_ab_tf)."""
    import asyncpg
    conn = await asyncpg.connect(dsn())
    data = {}
    try:
        for ticker in TICKERS:
            rows = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM candles
                WHERE ticker = $1 AND timeframe = $2
                ORDER BY time
            """, ticker, timeframe)
            if not rows:
                continue
            data[ticker] = pd.DataFrame(
                {
                    "open":   [float(r["open"]) for r in rows],
                    "high":   [float(r["high"]) for r in rows],
                    "low":    [float(r["low"]) for r in rows],
                    "close":  [float(r["close"]) for r in rows],
                    "volume": [int(r["volume"]) for r in rows],
                },
                index=pd.DatetimeIndex(
                    [r["time"].replace(tzinfo=None) for r in rows], name="datetime"
                ),
            )
    finally:
        await conn.close()
    return data


def metrics(trades: list[BacktestTrade]) -> dict:
    n      = len(trades)
    wins   = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gw     = sum(t.pnl for t in wins)
    gl     = abs(sum(t.pnl for t in losses))
    avg_w  = gw / len(wins) if wins else 0.0
    avg_l  = gl / len(losses) if losses else 0.0
    days   = [
        (t.exit_date - t.entry_date).days
        for t in trades if t.exit_date is not None
    ]
    return {
        "n": n,
        "wr": len(wins) / n * 100 if n else 0.0,
        "pnl": sum(t.pnl for t in trades),
        "pf": (gw / gl) if gl else (float("inf") if gw else 0.0),
        "payoff": (avg_w / avg_l) if avg_l else 0.0,
        "days": sum(days) / len(days) if days else 0.0,
    }


def fmt(label: str, m: dict) -> str:
    pf = f"{m['pf']:6.2f}" if m["pf"] != float("inf") else "   inf"
    return (f"{label:<10} {m['n']:>5} {m['wr']:>6.1f}% {m['pnl']:>13,.0f} "
            f"{pf} {m['payoff']:>6.2f} {m['days']:>6.1f}")


HEADER = f"{'':<10} {'n':>5} {'WR':>7} {'PnL, руб.':>13} {'PF':>6} {'payoff':>6} {'дней':>6}"


def main() -> None:
    import logging
    logging.basicConfig(level=logging.ERROR)

    data = asyncio.run(load_candles_db("1d"))
    n_bars = sum(len(d) for d in data.values())
    lo = min(d.index.min() for d in data.values())
    hi = max(d.index.max() for d in data.values())
    print(f"D1: {len(data)} тикеров, {n_bars} свечей, {lo.date()} → {hi.date()}")

    with tempfile.TemporaryDirectory(prefix="ab_trend_fix_") as tmp:
        variant_files = build_variant_files(Path(tmp))

        all_trades: dict[str, list[BacktestTrade]] = {}
        for vid, label, _ema50, _no_exit in VARIANTS:
            rules  = RulesEngine(rules_file=variant_files[vid])
            engine = BacktestEngine(rules_engine=rules, strategy_id=f"trend_fix_{vid}",
                                    timeframe="D1")
            ema = engine._indicators.ema_slow
            t0 = time.time()
            trades: list[BacktestTrade] = []
            for ticker, df in data.items():
                trades.extend(engine.run(ticker, df).trades)
            all_trades[vid] = trades
            print(f"  {vid:<10} ({label}): ema_slow={ema}, "
                  f"сделок={len(trades)}, {time.time() - t0:.0f} с")

    # ── Сводка: полный период ─────────────────────────────────────────
    print(f"\n{'═' * 70}\n  ПОЛНЫЙ ПЕРИОД\n{'═' * 70}\n{HEADER}")
    for vid, _l, _a, _b in VARIANTS:
        print(fmt(vid, metrics(all_trades[vid])))

    # ── По годам (по дате входа) ──────────────────────────────────────
    years = sorted({t.entry_date.year for tr in all_trades.values() for t in tr})
    for year in years:
        print(f"\n{'─' * 70}\n  {year}\n{'─' * 70}\n{HEADER}")
        for vid, _l, _a, _b in VARIANTS:
            sub = [t for t in all_trades[vid] if t.entry_date.year == year]
            print(fmt(vid, metrics(sub)))

    # ── Статусы выходов (видно эффект A4) ─────────────────────────────
    print(f"\n{'─' * 70}\n  Статусы закрытия (n): STOPPED/TARGET/WIN/LOSS\n{'─' * 70}")
    for vid, _l, _a, _b in VARIANTS:
        by = {}
        for t in all_trades[vid]:
            by[t.status] = by.get(t.status, 0) + 1
        print(f"  {vid:<10} " + "  ".join(f"{k}={v}" for k, v in sorted(by.items())))


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
