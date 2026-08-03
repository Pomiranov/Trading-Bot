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
from datetime import date

import pandas as pd

from config import config
from universe import (
    SAMPLE_START_2026_07, SAMPLE_END_2026_07,
    MEASUREMENT_UNIVERSE_2026_07, MEASUREMENT_UNIVERSE_2026_07_VERSION,
)
from backtest.candles import dsn, load_candles_db, window_note
from backtest.engine import BacktestEngine
from signals.rules_engine import RulesEngine, classify_regime
from signals.indicators import IndicatorEngine

# Набор ПРИКОЛОЧЕН: на нём посчитаны все опорные числа проекта. Не менять —
# набор есть часть определения измерения (bot/universe.py). Новые валидации
# делаются на MEASUREMENT_UNIVERSE_2026_07_EXT.
TICKERS = list(MEASUREMENT_UNIVERSE_2026_07)
# Тикеры в многолетнем даунтренде — для раздельной оценки фильтра
DOWNTREND_TICKERS = {"GAZP", "ROSN", "SNGS"}
TIMEFRAMES = ["4h", "1d"]
TF_LABEL = {"4h": "H4", "1d": "D1"}

IS_END = pd.Timestamp("2025-01-01")   # граница in-sample / out-of-sample

DEFAULT_RULES = config.rules_dir / "rules_osc_range.yaml"


# dsn() и load_candles_db() вынесены в backtest/candles.py (долг №37):
# окно выборки стало ОБЯЗАТЕЛЬНЫМ аргументом, а пять копий одного запроса
# были той же болезнью, что девять копий списка тикеров.

def collect_trades(rules_file: Path, pm: bool = False,
                   as_of: date | None = None, rescale_windows: bool = True) -> tuple[pd.DataFrame, dict, list]:
    """Прогнать бэктест по всем ТФ/тикерам.

    Возвращает (DataFrame ЗАКРЫТЫХ сделок,
                {(tf, ticker): пропущено фильтром даунтренда},
                список позиций, открытых на краю данных).

    Открытые в DataFrame и в CSV НЕ попадают (долг №25): они не сделки, а положение
    дел на конце данных, и их результат ещё не определён. Идут отдельным списком и
    печатаются отдельным блоком — так их нельзя случайно сложить в n/WR/PF/PnL.

    Окно печатается ПО ТАЙМФРЕЙМАМ, а не одной строкой на прогон: на 2026-07-30
    D1 доходит до сессии 30.07, а H4 стоит на 11.07 (свечи H4/H1 не догружались,
    форвард качает только D1). Общая строка это различие скрыла бы, а оно объясняет,
    почему обрезка конца в диапазоне после 11.07 меняет только D1-числа.
    """
    ind_engine = IndicatorEngine()
    rows = []
    open_at_edge: list = []
    skipped: dict = {}
    for tf in TIMEFRAMES:
        data = asyncio.run(load_candles_db(tf, TICKERS, SAMPLE_START_2026_07, as_of))
        print(f"\n── {TF_LABEL[tf]} ──")
        for line in window_note(data, SAMPLE_START_2026_07, as_of).splitlines():
            print(f"  {line}")
        rules = RulesEngine(rules_file=rules_file)
        engine = BacktestEngine(
            universe_version=MEASUREMENT_UNIVERSE_2026_07_VERSION,
            rules_engine=rules, timeframe=TF_LABEL[tf],
            rescale_windows=rescale_windows,
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
            for t in res.open_trades_at_end:
                open_at_edge.append({
                    "tf":          TF_LABEL[tf],
                    "ticker":      ticker,
                    "entry":       t.entry_date,
                    "entry_price": t.entry_price,
                    "shares":      t.shares,
                    "last_bar":    df.index[-1],
                    "unrealized":  round(res.unrealized_pnl, 2),
                    "sample":      "IS" if t.entry_date < IS_END else "OOS",
                })
        print(f"  {TF_LABEL[tf]}: прогнано {len(data)} тикеров")
    return pd.DataFrame(rows), skipped, open_at_edge


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
    ap.add_argument("--no-rescale", action="store_true",
                    help="контрольная строка замера: окна остаются D1-овскими (61/50) "
                         "при любом таймфрейме; множитель не трогается")
    ap.add_argument("--pm", action="store_true", help="ведение позиции: безубыток +1R, цель 2R")
    ap.add_argument("--show-oos", action="store_true", help="показать out-of-sample (только финал)")
    ap.add_argument("--as-of", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                    help="обрезать выборку по эту МОСКОВСКУЮ СЕССИЮ включительно "
                         "(не метку бара). Без флага — по самые свежие данные")
    args = ap.parse_args()

    # Отпечатки НАБОРА и ОКНА печатаются наравне с файлом правил: отчёт без них
    # через полгода нечитаем — по нему нельзя сказать ни на каких бумагах он
    # посчитан, ни с какого момента. Окно добавлено 30.07 (долг №37): до этого
    # конец выборки назывался, а начало — нет.
    print(f"Правила: {args.rules}\nМетка: {args.label}  pm={args.pm}")
    print(f"Набор: MEASUREMENT_UNIVERSE_2026_07, {len(TICKERS)} бумаг, "
          f"отпечаток {MEASUREMENT_UNIVERSE_2026_07_VERSION}")
    if args.as_of is None:
        # Константа названа ЗДЕСЬ, а не только в universe.py, чтобы у неё был живой
        # потребитель: приколоченная дата, которую никто не печатает, гниёт молча.
        print(f"Конец окна НЕ приколочен. Опорные числа эры 2026-07 считаны по "
              f"сессию {SAMPLE_END_2026_07.isoformat()}; воспроизвести: "
              f"--as-of {SAMPLE_END_2026_07.isoformat()}")
    trades, skipped, open_at_edge = collect_trades(args.rules, pm=args.pm,
                                                   as_of=args.as_of,
                                                   rescale_windows=not args.no_rescale)
    out_csv = Path(__file__).resolve().parent / f"osc_debug_{args.label}.csv"
    trades.to_csv(out_csv, index=False)
    print(f"\nЗакрытые сделки сохранены: {out_csv} ({len(trades)} шт.)")

    # Блок открытых печатается ВСЕГДА, даже пустой: «открытых нет» — это тоже
    # результат, и его отсутствие в отчёте неотличимо от «забыли посмотреть».
    # Именно на этом стоял долг №25: тройка с фильтром воспроизводилась ровно
    # потому, что открытых там не было, — а прочитать это было негде.
    print(f"\n{'─' * 64}")
    if not open_at_edge:
        print("  Открытых позиций на краю данных: НЕТ — n/WR/PF/PnL полны")
    else:
        print(f"  ОТКРЫТО НА КРАЮ ДАННЫХ: {len(open_at_edge)} — в n/WR/PF/PnL НЕ входят")
        print("  (долг №25: до 30.07 они закрывались по последнему бару и дрейфовали)")
        for o in open_at_edge:
            print(f"    {o['tf']} {o['ticker']:<6} вход {o['entry']} по {o['entry_price']:.2f} "
                  f"× {o['shares']} шт. [{o['sample']}]")
            print(f"      последний бар {o['last_bar']}, "
                  f"нереализовано {o['unrealized']:+,.2f} руб.")
    print(f"{'─' * 64}")
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
