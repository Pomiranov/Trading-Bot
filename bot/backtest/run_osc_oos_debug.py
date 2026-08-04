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
    counters: dict = {}
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
            # Счётчики копятся ПО ТАЙМФРЕЙМУ как СПИСКИ МЕТОК БАРОВ: разрез
            # назначает этот файл ниже, тем же IS_END, что и сделки на :124/:135.
            c = counters.setdefault(TF_LABEL[tf], dict(
                born_at=[], passed_at=[], known_at=[], downtrend_at=[],
                position_open_at=[], sizing_at=[], capital_at=[], gate_active=False))
            c["born_at"] += res.born_at
            c["downtrend_at"] += res.skipped_downtrend_at
            c["position_open_at"] += res.skipped_position_open_at
            c["sizing_at"] += res.skipped_sizing_at
            c["capital_at"] += res.skipped_capital_at
            # «прошло» = состоявшиеся входы (факт записи, долг №25);
            # «с известным исходом» = только ЗАКРЫТЫЕ. Разница — открытые на краю.
            # Читать С3 как «примеров с известным исходом» нельзя: ровно этот класс
            # отозвал тройку 30 / 60.0% / 1.20 (дрейфующая открытая SBER).
            c["known_at"] += [t.entry_date for t in res.trades]
            c["passed_at"] += [t.entry_date for t in res.trades] +                               [t.entry_date for t in res.open_trades_at_end]
            c["gate_active"] |= res.gate_active
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
    return pd.DataFrame(rows), skipped, open_at_edge, counters


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



# ── Счётчики путей отказа сигнала: разбиение по разрезу IS/OOS ────────────────
#
# РАЗРЕЗ НАЗНАЧАЕТСЯ ЗДЕСЬ, тем же IS_END, которым размечаются сделки на :124/:135.
# Движок отдаёт МЕТКИ БАРОВ и про разрезы не знает: четвёртый литерал границы в
# движке разошёлся бы с колонкой `sample` в CSV молча (класс долга №24). Литералов
# границы от разбиения не прибавилось — по-прежнему один на этот файл.
#
# ТРИ ВИДА НУЛЯ, и число дошедших печатается ПО РАЗРЕЗУ, а не общее: иначе метка
# соврёт в ту же сторону, в которую соврала первая редакция zero_kind.
#   «не достигнут»             — все сигналы разреза оборваны Б1/Б2;
#   «недостижим по построению» — режим исключает путь (фильтр выключен ⇒ Б1);
#   «ноль наблюдений»          — путь достигнут в этом разрезе, событий не было.
#
# ДВА МЕСТА, и одно не считается выполнением: сводка И машиночитаемый TSV,
# сверяются между собой.
PATHS = [("downtrend", "Б1 фильтр даунтренда"),
         ("position_open", "Б2 позиция уже открыта"),
         ("sizing", "Б3 сайзинг не дал позиции"),
         ("capital", "Б4 не хватает капитала")]
SAMPLES = ["IS", "OOS"]


def _split(stamps: list) -> dict:
    """Разложить метки баров по разрезам ТЕМ ЖЕ сравнением, что и сделки."""
    out = {s: 0 for s in SAMPLES}
    for t in stamps:
        out["IS" if pd.Timestamp(t).tz_localize(None) < IS_END else "OOS"] += 1
    return out


def zero_kind(key: str, c: dict, smp: str) -> str:
    if key == "downtrend" and not c["gate_active"]:
        return "недостижим по построению (фильтр выключен)"
    if key in ("sizing", "capital"):
        reached = c["passed"][smp] + c["sizing"][smp] + c["capital"][smp]
        if reached == 0:
            return "не достигнут (все сигналы разреза оборваны Б1/Б2)"
        return f"ноль наблюдений (путь достигнут {reached} раз в этом разрезе)"
    return "ноль наблюдений"


def counters_report(counters: dict, path: Path) -> None:
    lines = ["tf\tsample\tmetric\tvalue\tzero_kind"]
    print("\n" + "=" * 76)
    print("  СЧЁТЧИКИ ПУТЕЙ ОТКАЗА СИГНАЛА — разбиение по разрезу IS/OOS")
    print("=" * 76)
    for tf, raw in sorted(counters.items()):
        c = {k: _split(raw[k + "_at"]) for k in ("born", "passed", "known",
                                                 "downtrend", "position_open",
                                                 "sizing", "capital")}
        c["gate_active"] = raw["gate_active"]
        print(f"\n  -- {tf} --")
        hdr = f"  {'':<34}" + "".join(f"{s:>10}" for s in SAMPLES) + f"{'ЦЕЛОЕ':>10}"
        print(hdr)
        def row(title, key):
            vals = [c[key][s] for s in SAMPLES]
            tot = sum(vals)
            print(f"  {title:<34}" + "".join(f"{v:>10}" for v in vals) + f"{tot:>10}")
            for s in SAMPLES:
                zk = "" if c[key][s] else zero_kind(key, c, s)
                lines.append(f"{tf}\t{s}\t{key}\t{c[key][s]}\t{zk}")
            lines.append(f"{tf}\tALL\t{key}\t{tot}\t")
            return tot
        born = row("Б0 сигнал родился", "born")
        passed = row("прошло (стало сделкой)", "passed")
        known = row("  из них с ИЗВЕСТНЫМ исходом", "known")
        opened = passed - known
        print(f"  {'  разница = открытых на краю':<34}" +
              "".join(f"{c['passed'][s]-c['known'][s]:>10}" for s in SAMPLES) + f"{opened:>10}")
        tots = {}
        for k, title in PATHS:
            tots[k] = row(title, k)
        for k, title in PATHS:
            for s in SAMPLES:
                if not c[k][s]:
                    print(f"    НУЛЬ {title} / {s}: {zero_kind(k, c, s)}")
        print("  " + "-" * 66)
        ok_all = True
        for s in SAMPLES + ["ЦЕЛОЕ"]:
            if s == "ЦЕЛОЕ":
                b, p_, r = born, passed, sum(tots.values())
            else:
                b, p_ = c["born"][s], c["passed"][s]
                r = sum(c[k][s] for k, _ in PATHS)
            ok = (p_ + r == b)
            ok_all &= ok
            print(f"  тождество {s:>6}: прошло {p_} + отказы {r} = {p_+r} против родилось {b}"
                  f"  ->  {'СХОДИТСЯ' if ok else 'НЕ СХОДИТСЯ'}")
            lines.append(f"{tf}\t{s}\tidentity_holds\t{int(ok)}\t")
        lines.append(f"{tf}\tALL\tgate_active\t{int(c['gate_active'])}\t")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  машиночитаемая улика: {path}")
    back: dict = {}
    for ln in path.read_text(encoding="utf-8").splitlines()[1:]:
        q = (ln.split("\t") + ["", "", "", "", ""])[:5]
        back[(q[0], q[1], q[2])] = q[3]
    bad = []
    for tf, raw in counters.items():
        c = {k: _split(raw[k + "_at"]) for k in ("born", "passed", "known",
                                                 "downtrend", "position_open",
                                                 "sizing", "capital")}
        for k in list(c):
            for s in SAMPLES:
                if back.get((tf, s, k)) != str(c[k][s]):
                    bad.append(f"{tf}/{s}/{k}")
            if back.get((tf, "ALL", k)) != str(sum(c[k].values())):
                bad.append(f"{tf}/ALL/{k}")
    print("  сверка сводки с файлом: " + ("СОВПАЛО" if not bad else "РАСХОЖДЕНИЕ: " + ", ".join(bad)))

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
    trades, skipped, open_at_edge, counters = collect_trades(
        args.rules, pm=args.pm, as_of=args.as_of,
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
    counters_report(counters, out_csv.with_name(f"counters_{args.label}.tsv"))
    report(trades, show_oos=args.show_oos)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
