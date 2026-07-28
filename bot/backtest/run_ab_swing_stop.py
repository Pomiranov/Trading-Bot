"""A/B трейлинг-выхода по свинг-минимумам для trend_moex (Швагер, гл. 9, метод 5).

Запуск:
    python backtest/run_ab_swing_stop.py

Варианты × 12 тикеров × D1 (полный период из таблицы candles):
    baseline — текущий rules.yaml без изменений
    swing5 / swing10 / swing15 — + секция swing_stop {window: N}
        + exit-правило swing_low_break (закрытие ниже последнего
        подтверждённого свинг-минимума); N из книжного диапазона 5..15
        (сноска стр. 168) — три значения, чтобы увидеть чувствительность
        (гл. 17, проблема 9), а не оптимизировать.

Сделки делятся по дате входа: IS до 2025-01-01, OOS после — критерий
принятия: улучшение OOS (trend_moex заморожена, правка только через ворота).
Источник: knowledge/processed/technical/stops_schwager.md.
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

IS_END = pd.Timestamp("2025-01-01")   # граница in-sample / out-of-sample

SWING_LOW_BREAK = {
    "name": "swing_low_break",
    "action": "EXIT",
    "weight": 1.0,
    "description": "Выход: закрытие ниже последнего относительного минимума (Швагер гл.9)",
    "conditions": [{"indicator": "close", "operator": "<", "value": "swing_low"}],
}

VARIANTS = [
    # (id, подпись, window или None=baseline)
    ("baseline", "текущий rules.yaml",            None),
    ("swing5",   "трейлинг по свинг-min, N=5",    5),
    ("swing10",  "трейлинг по свинг-min, N=10",   10),
    ("swing15",  "трейлинг по свинг-min, N=15",   15),
]


def build_variant_files(tmp_dir: Path) -> dict[str, Path]:
    """Сгенерировать yaml каждого варианта из production rules.yaml."""
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f)

    paths = {}
    for vid, _label, window in VARIANTS:
        data = copy.deepcopy(base)
        if window is not None:
            data["swing_stop"] = {"window": window}
            data.setdefault("exit_rules", []).append(copy.deepcopy(SWING_LOW_BREAK))
        path = tmp_dir / f"rules_swing_{vid}.yaml"
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
    """Свечи всех тикеров одного таймфрейма из таблицы candles (как в run_ab_trend_fix)."""
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

    with tempfile.TemporaryDirectory(prefix="ab_swing_stop_") as tmp:
        variant_files = build_variant_files(Path(tmp))

        all_trades: dict[str, list[BacktestTrade]] = {}
        for vid, label, _window in VARIANTS:
            rules  = RulesEngine(rules_file=variant_files[vid])
            engine = BacktestEngine(rules_engine=rules, strategy_id=f"swing_ab_{vid}",
                                    timeframe="D1")
            t0 = time.time()
            trades: list[BacktestTrade] = []
            for ticker, df in data.items():
                trades.extend(engine.run(ticker, df).trades)
            all_trades[vid] = trades
            print(f"  {vid:<10} ({label}): сделок={len(trades)}, {time.time() - t0:.0f} с")

    # ── Сводка: полный период / IS / OOS ─────────────────────────────
    for title, pred in [
        ("ПОЛНЫЙ ПЕРИОД", lambda t: True),
        ("IS (до 2025-01-01)", lambda t: t.entry_date < IS_END),
        ("OOS (с 2025-01-01)", lambda t: t.entry_date >= IS_END),
    ]:
        print(f"\n{'═' * 70}\n  {title}\n{'═' * 70}\n{HEADER}")
        for vid, _l, _w in VARIANTS:
            print(fmt(vid, metrics([t for t in all_trades[vid] if pred(t)])))

    # ── Статусы выходов (виден эффект нового правила) ─────────────────
    print(f"\n{'─' * 70}\n  Статусы закрытия (n)\n{'─' * 70}")
    for vid, _l, _w in VARIANTS:
        by = {}
        for t in all_trades[vid]:
            by[t.status] = by.get(t.status, 0) + 1
        print(f"  {vid:<10} " + "  ".join(f"{k}={v}" for k, v in sorted(by.items())))


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
