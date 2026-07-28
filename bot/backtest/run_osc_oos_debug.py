"""Отладка osc_range: разбивка in-sample / out-of-sample + статистика по правилам входа.

Запуск:
    python backtest/run_osc_oos_debug.py [--rules путь/к/rules.yaml] [--label метка]

Гоняет бэктест по D1 и H4 на всей истории из таблицы candles БЕЗ записи
в learning (orchestrator=None) — чисто аналитический прогон. Сделки
делятся по дате входа:
    in-sample  : до 2025-01-01 (настройка)
    out-sample : с 2025-01-01  (проверка)
Печатает WR/PF/n по периодам, по правилам входа и по режимам рынка.
Полный список сделок сохраняется в CSV рядом со скриптом (--label в имени).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import logging
import os

import pandas as pd

from config import config
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine, classify_regime
from signals.indicators import IndicatorEngine

TICKERS = ["SBER", "GAZP", "LKOH", "NVTK", "ROSN", "TATN",
           "MGNT", "MOEX", "PLZL", "CHMF", "ALRS", "SNGS"]

# Тикеры в многолетнем даунтренде — для раздельной оценки фильтра
DOWNTREND_TICKERS = {"GAZP", "ROSN", "SNGS"}
TIMEFRAMES = ["4h", "1d"]
TF_LABEL = {"4h": "H4", "1d": "D1"}

IS_END = pd.Timestamp("2025-01-01")   # граница in-sample / out-of-sample

DEFAULT_RULES = config.rules_dir / "rules_osc_range.yaml"


def dsn() -> str:
    from dotenv import load_dotenv
    load_dotenv()
    return "postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot"))


async def load_candles_db(timeframe: str) -> dict[str, pd.DataFrame]:
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
            df = pd.DataFrame(
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
            data[ticker] = df
    finally:
        await conn.close()
    return data


def collect_trades(rules_file: Path, pm: bool = False) -> tuple[pd.DataFrame, dict]:
    """Прогнать бэктест по всем ТФ/тикерам.

    Возвращает (DataFrame сделок, {(tf, ticker): пропущено фильтром даунтренда}).
    """
    ind_engine = IndicatorEngine()
    rows = []
    skipped: dict = {}
    for tf in TIMEFRAMES:
        data = asyncio.run(load_candles_db(tf))
        rules = RulesEngine(rules_file=rules_file)
        engine = BacktestEngine(
            rules_engine=rules, timeframe=TF_LABEL[tf],
            breakeven_r=1.0 if pm else None,
            target_r=2.0 if pm else None,
        )
        for ticker, df in data.items():
            res = engine.run(ticker, df)
            if res.skipped_downtrend:
                skipped[(TF_LABEL[tf], ticker)] = res.skipped_downtrend
            df_ind = ind_engine.compute(df)
            for t in res.trades:
                adx = None
                if t.entry_date in df_ind.index:
                    v = df_ind.loc[t.entry_date, "adx"]
                    adx = float(v) if pd.notna(v) else None
                rows.append({
                    "tf":      TF_LABEL[tf],
                    "ticker":  ticker,
                    "entry":   t.entry_date,
                    "exit":    t.exit_date,
                    "pnl":     round(t.pnl, 2),
                    "status":  t.status,
                    "rules":   t.entry_rules,
                    "regime":  classify_regime(adx) or "unknown",
                    "sample":  "IS" if t.entry_date < IS_END else "OOS",
                })
        print(f"  {TF_LABEL[tf]}: прогнано {len(data)} тикеров")
    return pd.DataFrame(rows), skipped


def stats(df: pd.DataFrame) -> str:
    n = len(df)
    if n == 0:
        return f"{'—':>4} {'—':>7} {'—':>6} {'—':>12}"
    wins = (df["pnl"] > 0).sum()
    wr = wins / n * 100
    gw = df.loc[df["pnl"] > 0, "pnl"].sum()
    gl = abs(df.loc[df["pnl"] <= 0, "pnl"].sum())
    pf = gw / gl if gl else float("inf")
    return f"{n:>4} {wr:>6.1f}% {pf:>6.2f} {df['pnl'].sum():>+12,.0f}"


HEADER = f"{'':<30} {'n':>4} {'WR':>7} {'PF':>6} {'PnL, руб.':>12}"


def report(trades: pd.DataFrame, show_oos: bool = False) -> None:
    for tf in ["D1", "H4"]:
        sub = trades[trades["tf"] == tf]
        print(f"\n{'═' * 64}\n  {tf}\n{'═' * 64}")
        print(HEADER)
        samples = ["IS", "OOS"] if show_oos else ["IS"]
        for sample in samples:
            print(f"{sample:<30} {stats(sub[sub['sample'] == sample])}")
        if not show_oos:
            print(f"{'OOS (скрыто до финала)':<30}")

        # Раздельно: тикеры-даунтренды vs остальные
        print(f"\n  По группам тикеров:\n{HEADER}")
        dt_mask = sub["ticker"].isin(DOWNTREND_TICKERS)
        for sample in samples:
            s_mask = sub["sample"] == sample
            print(f"{sample + ' GAZP/ROSN/SNGS':<30} {stats(sub[s_mask & dt_mask])}")
            print(f"{sample + ' остальные 9':<30} {stats(sub[s_mask & ~dt_mask])}")

        # По правилам входа (сделка учитывается в каждом правиле её комбо) — IS only
        print(f"\n  По правилам входа (in-sample):\n{HEADER}")
        is_sub = sub[sub["sample"] == "IS"]
        rule_names = sorted({r for combo in is_sub["rules"] for r in combo.split("+") if r})
        for rn in rule_names:
            mask = is_sub["rules"].str.split("+").apply(lambda rs: rn in rs)
            print(f"{rn:<30} {stats(is_sub[mask])}")

        print(f"\n  По комбинациям правил (in-sample):\n{HEADER}")
        for combo, grp in is_sub.groupby("rules"):
            print(f"{combo[:30]:<30} {stats(grp)}")

        print(f"\n  По режимам (in-sample):\n{HEADER}")
        for regime, grp in is_sub.groupby("regime"):
            print(f"{regime:<30} {stats(grp)}")


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--pm", action="store_true", help="ведение позиции: безубыток +1R, цель 2R")
    ap.add_argument("--show-oos", action="store_true", help="показать out-of-sample (только финал)")
    args = ap.parse_args()

    print(f"Правила: {args.rules}\nМетка: {args.label}  pm={args.pm}")
    trades, skipped = collect_trades(args.rules, pm=args.pm)
    out_csv = Path(__file__).resolve().parent / f"osc_debug_{args.label}.csv"
    trades.to_csv(out_csv, index=False)
    print(f"\nСделки сохранены: {out_csv} ({len(trades)} шт.)")
    if skipped:
        total = sum(skipped.values())
        print(f"Отклонено фильтром структурного даунтренда: {total} BUY-баров")
        for (tf, ticker), n in sorted(skipped.items()):
            print(f"  {tf} {ticker}: {n}")
    report(trades, show_oos=args.show_oos)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
