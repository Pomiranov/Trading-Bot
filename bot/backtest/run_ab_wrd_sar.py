"""A/B wrd_moex: чистый книжный SAR (гл. 18) vs текущий 2×ATR-контур.

Запуск:
    python backtest/run_ab_wrd_sar.py

Тест книжной гипотезы, НЕ подбор стопа: в стройке wrd_moex 179 из 191
сделок закрыл ATR-стоп/трейлинг, книжный SAR-выход (закрытие за ptr_low)
сработал 12 раз — наложенный контур затеняет stop-and-reverse, сердце
системы гл. 18. Вопрос A/B: жива ли книжная механика без ATR поверх.

Единственная меняемая переменная — use_stops движка (вкл/выкл стопа
и трейлинга). Правила, книжные параметры (k=2.0, ATR(10), N1=4, N2=2),
long-only адаптация и сайзинг по стоп-дистанции идентичны в обоих
вариантах; боевой rules_wrd_moex.yaml не модифицируется.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
import time

import pandas as pd

from config import config
from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07
from backtest.engine import BacktestEngine, BacktestTrade
from backtest.candles import load_candles_db, window_note
from backtest.run_wrd_backtest import metrics, IS_END
from signals.rules_engine import RulesEngine

# ВОСЬМОЙ потребитель общего загрузчика, пропущенный при закрытии долга №37.
# Долг перевёл ПЯТЬ скриптов со своей копией запроса, а этот копии не имел — он
# импортировал загрузчик из run_wrd_backtest по цепочке ре-экспорта, поэтому в
# список пяти не попал и в тест окна (tests/forward_tests/test_universe.py) тоже.
# Результат: с 30.07 он падал `TypeError` на `load_candles_db("1d")` — окна нет,
# набора нет. Fail-loud отработал как задуман (громко, а не молча более широкой
# выборкой), но скрипт всё это время был мёртв, и заметить это было нечем.
# Ре-экспорт заменён прямым импортом: цепочка «скрипт → скрипт → модуль» и была
# тем, что спрятало пропуск.
TICKERS = list(MEASUREMENT_UNIVERSE_2026_07)
RULES_FILE = config.rules_dir / "rules_wrd_moex.yaml"

VARIANTS = [
    # (id, подпись, use_stops)
    ("baseline", "2×ATR-стоп + трейлинг (текущий контур)", True),
    ("pure_sar", "чистый SAR гл.18 (без стопа/трейлинга)",  False),
]


def fmt(label: str, m: dict) -> str:
    pf = f"{m['pf']:6.2f}" if m["pf"] != float("inf") else "   inf"
    return (f"{label:<10} {m['n']:>5} {m['wr']:>6.1f}% {m['pnl']:>13,.0f} "
            f"{pf} {m['payoff']:>6.2f} {m['days']:>6.1f}")


HEADER = f"{'':<10} {'n':>5} {'WR':>7} {'PnL, руб.':>13} {'PF':>6} {'payoff':>6} {'дней':>6}"


def exit_breakdown(trades: list[BacktestTrade],
                   open_at_end: list[BacktestTrade]) -> dict:
    """Типы выхода: стоп / цель / SAR-разворот + сколько позиций ещё ОТКРЫТО.

    Переписано 30.07 вместе с закрытием долга №25. Раньше «принудительный финал
    последней свечи» определялся эвристикой `t.exit_date == last_bar[ticker]`, и она
    была неточна в обе стороны: принудительное закрытие попадало в `trades` наравне
    с настоящими выходами (потому и понадобилась эвристика), а обычный выход ПО
    ПРАВИЛУ, случившийся на последнем баре, ею же зачислялся в «финал». Теперь
    открытые приходят отдельным списком от движка — это факт, а не догадка по дате.
    """
    by = {"stop": 0, "sar": 0, "target": 0, "open": len(open_at_end)}
    for t in trades:
        if t.status == "STOPPED":
            by["stop"] += 1
        elif t.status == "TARGET":
            by["target"] += 1
        else:
            by["sar"] += 1
    return by


def main() -> None:
    logging.basicConfig(level=logging.ERROR)

    data = asyncio.run(load_candles_db("1d", TICKERS, SAMPLE_START_2026_07))
    n_bars = sum(len(d) for d in data.values())
    print(f"D1: {len(data)} тикеров, {n_bars} свечей")
    # Окно печатает window_note (одна копия расчёта). Было `lo.date() → hi.date()`,
    # то есть НАИВНАЯ UTC-дата — третья из трёх дат бара и самая обманчивая: у D1 она
    # равна «сессия − 1 день» у ВСЕХ строк (долг №26).
    for line in window_note(data, SAMPLE_START_2026_07).splitlines():
        print(f"  {line}")
    all_trades: dict[str, list[BacktestTrade]] = {}
    all_open: dict[str, list[BacktestTrade]] = {}
    for vid, label, use_stops in VARIANTS:
        rules  = RulesEngine(rules_file=RULES_FILE)
        engine = BacktestEngine(rules_engine=rules, strategy_id=f"wrd_ab_{vid}",
                                timeframe="D1", use_stops=use_stops)
        t0 = time.time()
        trades: list[BacktestTrade] = []
        opened: list[BacktestTrade] = []
        for ticker, df in data.items():
            res = engine.run(ticker, df)
            trades.extend(res.trades)
            opened.extend(res.open_trades_at_end)
        all_trades[vid] = trades
        all_open[vid] = opened
        print(f"  {vid:<10} ({label}): закрытых сделок={len(trades)}, "
              f"открыто на краю={len(opened)}, {time.time() - t0:.0f} с")

    # ── Счётчики ПЕРВОЙ строкой ───────────────────────────────────────
    counts = {}
    for vid, _l, _s in VARIANTS:
        tr = all_trades[vid]
        counts[vid] = (
            sum(1 for t in tr if t.entry_date < IS_END),
            sum(1 for t in tr if t.entry_date >= IS_END),
        )
    print(f"\nСделки IS/OOS: baseline={counts['baseline'][0]}/{counts['baseline'][1]}, "
          f"pure_sar={counts['pure_sar'][0]}/{counts['pure_sar'][1]}")

    # ── Сводные таблицы ───────────────────────────────────────────────
    for title, pred in [
        ("ПОЛНЫЙ ПЕРИОД", lambda t: True),
        ("IS (до 2025-01-01)", lambda t: t.entry_date < IS_END),
        ("OOS (с 2025-01-01)", lambda t: t.entry_date >= IS_END),
    ]:
        print(f"\n{'═' * 70}\n  {title}\n{'═' * 70}\n{HEADER}")
        for vid, _l, _s in VARIANTS:
            print(fmt(vid, metrics([t for t in all_trades[vid] if pred(t)])))

    # ── Разбивка по типу выхода ───────────────────────────────────────
    print(f"\n{'─' * 70}\n  Типы выхода: стоп / цель / SAR-разворот + открыто на краю\n{'─' * 70}")
    for vid, _l, _s in VARIANTS:
        by = exit_breakdown(all_trades[vid], all_open[vid])
        n = len(all_trades[vid])
        # Исключение «выход на последнем баре» здесь больше не нужно: с долга №25
        # принудительных закрытий в trades нет вовсе, и всякий не-стоп/не-цель —
        # действительно SAR-разворот. Раньше эвристика по дате была обязательна и
        # при этом врала на выходе по правилу, попавшем на последний бар.
        sar_trades = [t for t in all_trades[vid] if t.status not in ("STOPPED", "TARGET")]
        sar_pnl = sum(t.pnl for t in sar_trades)
        print(f"  {vid:<10} стоп={by['stop']:<4} цель={by['target']:<4} "
              f"SAR={by['sar']:<4} открыто={by['open']:<3} | "
              f"PnL SAR-выходов: {sar_pnl:>+12,.0f} ({n} закрытых)")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
