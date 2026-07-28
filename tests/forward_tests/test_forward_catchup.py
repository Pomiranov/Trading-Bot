"""Догон пропущенных баров форвард-контура D1 (техдолг №14).

Что здесь проверяется и почему именно так:

  - Тесты цикла подменяют ПРАВИЛА (StubRules), но оставляют настоящие
    IndicatorEngine и RiskManager. Предмет этих тестов — воротА (какой бар
    судится, что на нём разрешено, куда двигается состояние), а не
    численная правильность индикаторов.
  - Паритет-тест T8, наоборот, берёт настоящие правила и настоящий движок:
    его предмет — что нарезка окон по уже посчитанному df_ind даёт то же,
    что пересчёт на префиксе, то есть что заглядывания в будущее нет.
  - StubRules опознаёт бар по iv.close, а не по порядку вызова: тест не
    должен зависеть от того, сколько раз движок спросит правила.
  - Прогоны идут через настоящий ForwardRunner.run() с отрезанным внешним
    миром. Фазы, guard'ы на снятые тикеры и порядок шагов — часть предмета
    проверки, дублировать их в хелпере значило бы не проверять их вовсе.
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_BOT = Path(__file__).resolve().parents[2] / "bot"
sys.path.insert(0, str(_BOT))

import pandas as pd

import run_forward_d1 as fwd
from learning.memory_writer import ExitReasonType
from signals.indicators import IndicatorEngine, signal_window
from signals.rules_engine import Action, RulesEngine

UTC = timezone.utc


# ─────────────────────────────────────────────────────────────────────────────
# Стенд
# ─────────────────────────────────────────────────────────────────────────────

class _FakeTx:
    """asyncpg-подобная транзакция. Rollback НЕ моделируется — см. FakeDB."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


class FakeDB:
    """Подмена asyncpg.Connection: диспетчер по подстроке SQL.

    state и trades мутабельны, поэтому ОДИН экземпляр обслуживает два
    последовательных прогона. Только так тест падения посреди догона (T5)
    проверяет настоящее возобновление, а не его имитацию.

    Оговорка: rollback не моделируется, поэтому сбой инжектируется в запись
    состояния — последний оператор транзакции, где rollback наблюдаемо no-op.
    Инжектировать раньше значило бы утверждать поведение, которое фейк
    воспроизвести не может.
    """

    def __init__(self, candles, trades=None, state=None):
        self.candles = candles
        self.trades = {} if trades is None else trades
        self.state = {} if state is None else state
        self.catchup: list = []
        self.calls: list = []
        self.fail_on = None          # (подстрока SQL, номер попадания)
        self._hits: dict = {}

    # ── служебное ──
    def _maybe_fail(self, sql: str) -> None:
        if not self.fail_on:
            return
        needle, nth = self.fail_on
        if needle in sql:
            self._hits[needle] = self._hits.get(needle, 0) + 1
            if self._hits[needle] == nth:
                raise RuntimeError(f"инъекция сбоя: {needle} #{nth}")

    def open_rows(self) -> list:
        cols = ("trade_id", "ticker", "entry_price", "stop_loss",
                "position_size", "risk_amount", "opened_at")
        return [{k: t[k] for k in cols}
                for t in self.trades.values() if t.get("closed_at") is None]

    def realized_rows(self) -> list:
        """Реализованный PnL по тикерам — ответ на группирующий запрос
        _paper_capital. Базовый стенд pnl не хранит (закрытие пишет только
        closed_at), поэтому здесь ноли; многодневный паритет проверяет
        FakeDBWithPnl в test_forward_per_ticker_capital.py."""
        out: dict = {}
        for t in self.trades.values():
            if t.get("closed_at") is not None:
                out[t["ticker"]] = out.get(t["ticker"], 0.0) + float(t.get("pnl") or 0.0)
        return [{"ticker": k, "realized": v} for k, v in out.items()]

    # ── интерфейс asyncpg ──
    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        if "FROM candles" in sql:
            return self.candles
        # Порядок ветвей значим: группирующий запрос по pnl тоже содержит
        # "FROM trades", и без этой проверки он получил бы ОТКРЫТЫЕ позиции.
        if "SUM(pnl)" in sql:
            return self.realized_rows()
        if "FROM trades" in sql:
            return self.open_rows()
        return []

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        if "FROM forward_state" in sql:
            return self.state.get(args[1])
        if "belief_system" in sql:
            return 1
        if "SUM(pnl)" in sql:
            return Decimal("0")
        return None

    async def execute(self, sql, *args):
        # Сначала сбой, потом запись: провалившийся оператор не должен
        # выглядеть как состоявшийся ни в state, ни в calls.
        self._maybe_fail(sql)
        self.calls.append(("execute", sql, args))
        if "INSERT INTO forward_state" in sql:
            self.state[args[1]] = args[2]
        elif "UPDATE trades SET stop_loss" in sql:
            self.trades[args[0]]["stop_loss"] = args[1]
        elif "INSERT INTO forward_catchup_log" in sql:
            self.catchup.append(args)

    def transaction(self):
        return _FakeTx()

    async def close(self):
        pass

    # ── утверждения ──
    def state_writes(self, ticker=None) -> list:
        return [a[2] for kind, sql, a in self.calls
                if kind == "execute" and "INSERT INTO forward_state" in sql
                and (ticker is None or a[1] == ticker)]

    def stop_updates(self) -> list:
        return [float(a[1]) for kind, sql, a in self.calls
                if kind == "execute" and "UPDATE trades SET stop_loss" in sql]

    def reset_calls(self) -> None:
        self.calls.clear()


def _bars(closes, ticker_start=None) -> list:
    """Свечи как строки БД: tz-aware время, OHLCV вокруг закрытия.

    Метки строго раньше сегодняшней МОСКОВСКОЙ даты — иначе
    _last_closed_index срежет последний бар и все позиционные утверждения
    сдвинутся на один. Проверяется здесь же, а не в каждом тесте.
    """
    n = len(closes)
    start = ticker_start or (datetime.now(fwd.MSK).date() - timedelta(days=n))
    rows, prev = [], closes[0]
    for k, c in enumerate(closes):
        t = datetime(start.year, start.month, start.day, tzinfo=UTC) + timedelta(days=k)
        rows.append({
            "time": t,
            "open": prev,
            "high": max(prev, c) * 1.004,
            "low": min(prev, c) * 0.996,
            "close": c,
            "volume": 1_000_000 + k,
        })
        prev = c
    today = datetime.now(fwd.MSK).date()
    assert rows[-1]["time"].astimezone(fwd.MSK).date() < today, \
        "последний синтетический бар обязан быть закрытым"
    return rows


def _smooth(n=260, start=100.0, drift=0.05, wobble=0.3) -> list:
    """Гладкая восходящая пила: индикаторы считаются, настоящие правила молчат."""
    return [round(start + drift * k + wobble * ((-1) ** k), 4) for k in range(n)]


def _walk(n=300, seed=42, start=100.0) -> list:
    """Сеющееся блуждание: даёт пивоты и расхождения — для паритет-теста.

    Свой LCG вместо random: Math.random-подобная глобальная зависимость сделала
    бы тест невоспроизводимым при смене порядка тестов.
    """
    closes, x, v = [], seed, start
    for _ in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        v *= 1.0 + ((x / 2 ** 31) - 0.5) * 0.05
        closes.append(round(v, 4))
    return closes


class StubRules:
    """evaluate/evaluate_exit по конкретной цене закрытия."""

    def __init__(self, buy_at=(), sell_at=(), exit_at=(), rules_version=None):
        self.buy_at = {round(float(c), 6) for c in buy_at}
        self.sell_at = {round(float(c), 6) for c in sell_at}
        self.exit_at = {round(float(c), 6) for c in exit_at}
        # Отпечаток набора правил (долг №30). У стаба он свой, но ОБЯЗАН быть:
        # _try_open читает его безусловно, и подставлять getattr-заглушку в
        # продакшен-коде значило бы вернуть молчаливый пропуск атрибуции.
        # Разные стабы могут задать разные значения — этим проверяется, что
        # отпечаток доезжает до строки trades, а не берётся из воздуха.
        self.rules_version = rules_version or "stub000000000000"
        self.divergence_params: dict = {}

    @staticmethod
    def _res(action, reason):
        r = MagicMock()
        r.action = action
        r.reason = reason
        r.confidence = 0.7
        r.triggered_rules = []
        return r

    def evaluate(self, iv, ticker=""):
        c = round(float(iv.close), 6)
        if c in self.buy_at:
            return self._res(Action.BUY, "стаб BUY")
        if c in self.sell_at:
            return self._res(Action.SELL, "стаб SELL")
        return self._res(Action.HOLD, "стаб HOLD")

    def evaluate_exit(self, iv, ticker=""):
        c = round(float(iv.close), 6)
        if c in self.exit_at:
            return self._res(Action.EXIT, "стаб EXIT")
        return self._res(Action.HOLD, "стаб HOLD")


def _seed_position(db, ticker, entry, stop, opened_at, shares=100, trade_id="t-1"):
    db.trades[trade_id] = {
        "trade_id": trade_id, "ticker": ticker,
        "entry_price": Decimal(str(entry)), "stop_loss": Decimal(str(stop)),
        "position_size": Decimal(shares), "risk_amount": Decimal("1000"),
        "opened_at": opened_at, "closed_at": None,
    }
    return trade_id


def _make_runner(db, rules=None):
    """ForwardRunner с подменённым оркестратором. Правила — по желанию теста."""
    opened, closed = [], []
    orch = MagicMock()
    orch.connect = AsyncMock()
    orch.disconnect = AsyncMock()
    orch.check_signal = AsyncMock(return_value={
        "approved": True, "position_size_multiplier": Decimal("1"), "reason": "ok"})

    async def _on_open(trade):
        opened.append(trade)
        db.trades[trade.trade_id] = {
            "trade_id": trade.trade_id, "ticker": trade.ticker,
            "entry_price": trade.entry_price, "stop_loss": trade.stop_loss,
            "position_size": trade.position_size, "risk_amount": trade.risk_amount,
            "opened_at": trade.opened_at, "closed_at": None,
        }

    async def _on_close(trade):
        closed.append(trade)
        rec = db.trades.get(trade.trade_id)
        if rec is not None:
            rec["closed_at"] = trade.closed_at

    orch.on_trade_opened = AsyncMock(side_effect=_on_open)
    orch.on_trade_closed = AsyncMock(side_effect=_on_close)

    with patch.object(fwd, "TradingOrchestrator", return_value=orch):
        runner = fwd.ForwardRunner()
    runner.orch = orch
    if rules is not None:
        runner.rules = rules
    return runner, opened, closed


async def _run(runner, db, tickers=("SBER",)):
    """Настоящий run() с отрезанным внешним миром (ISS, БД, Telegram)."""
    tg = MagicMock()
    tg.send_notification = AsyncMock()
    with patch.object(fwd, "save_candles_to_db", return_value=0), \
         patch.object(fwd, "TICKERS", list(tickers)), \
         patch.object(fwd.asyncpg, "connect", AsyncMock(return_value=db)), \
         patch.dict(sys.modules, {"ui": MagicMock(), "ui.telegram_bot": tg}):
        await runner.run()


def _run_sync(runner, db, tickers=("SBER",)):
    import asyncio
    asyncio.run(_run(runner, db, tickers))


# ─────────────────────────────────────────────────────────────────────────────
# T1 — обязательный кейс: стоп внутри ВТОРОГО из трёх пропущенных баров
# ─────────────────────────────────────────────────────────────────────────────

class TestStopInsideSkippedBar(unittest.TestCase):
    """Открытая позиция + 3 пропущенных бара, стоп пробит на втором.

    Форма кейса различает три разные реализации:
      - текущий (сломанный) код не закрывает НИЧЕГО: close свежего бара выше стопа;
      - «просканировать назад до пробития» выбирает ТРЕТИЙ бар (последний из
        пробитых);
      - только хронологически-первое пробитие даёт ВТОРОЙ бар.

    Пробитие задаётся через close, а не low: и backtest/engine.py:198, и форвард
    сравнивают со стопом price = close. Сохранение этого — часть паритета.
    """

    def setUp(self):
        closes = _smooth(260)
        closes[256] = 115.0    # выше стопа
        closes[257] = 105.0    # ← ПРОБИТИЕ, здесь должен быть выход
        closes[258] = 100.0    # тоже ниже стопа, но уже поздно
        closes[259] = 130.0    # свежий бар — сильно выше стопа
        self.closes = closes
        self.rows = _bars(closes)
        self.times = [r["time"] for r in self.rows]

        self.db = FakeDB(self.rows, state={"SBER": self.times[255]})
        _seed_position(self.db, "SBER", entry=120.0, stop=110.0,
                       opened_at=self.times[252])
        self.runner, self.opened, self.closed = _make_runner(
            self.db, StubRules())          # ни BUY, ни SELL, ни EXIT — только стоп
        _run_sync(self.runner, self.db)

    def test_closed_exactly_once(self):
        self.assertEqual(len(self.closed), 1)

    def test_closed_at_second_skipped_bar(self):
        self.assertEqual(self.closed[0].closed_at, self.times[257])

    def test_exit_price_is_second_bar_close(self):
        self.assertEqual(self.closed[0].exit_price, fwd._dec(self.closes[257]))

    def test_exit_reason_type_is_plain_stop(self):
        # Разрыв 3 бара <= предела 7, значит ничего не выброшено и стоп честный.
        self.assertEqual(self.closed[0].exit_reason_type, ExitReasonType.STOP_LOSS)

    def test_exit_reason_marks_catchup(self):
        self.assertIn("догон", self.closed[0].exit_reason)

    def test_state_advances_bar_by_bar(self):
        self.assertEqual(
            self.db.state_writes("SBER"),
            [self.times[256], self.times[257], self.times[258], self.times[259]],
        )

    def test_no_entry_happened(self):
        self.assertEqual(self.opened, [])

    def test_journal_row_written(self):
        self.assertEqual(len(self.db.catchup), 1)
        args = self.db.catchup[0]
        self.assertEqual(args[3], 3)      # gap_bars
        self.assertEqual(args[4], 3)      # bars_processed
        self.assertEqual(args[5], 0)      # bars_discarded


# ─────────────────────────────────────────────────────────────────────────────
# T2, T3, T7 — входы: только свежий бар, никогда задним числом
# ─────────────────────────────────────────────────────────────────────────────

class TestEntriesOnlyOnFreshBar(unittest.TestCase):

    def test_no_entry_on_historical_bar(self):
        """BUY на КАЖДОМ баре → вход ровно один, и он на свежем баре."""
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={"SBER": times[255]})
        runner, opened, _ = _make_runner(db, StubRules(buy_at=closes))
        _run_sync(runner, db)

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].opened_at, times[259])

    def test_entry_allowed_on_fresh_bar(self):
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={"SBER": times[255]})
        runner, opened, _ = _make_runner(db, StubRules(buy_at=(closes[259],)))
        _run_sync(runner, db)

        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].opened_at, times[259])
        # Проба переехала с runner.available на бюджет тикера: смысл тот же —
        # вход списывает капитал (см. CapitalBook, решение 28.07).
        self.assertLess(runner.book.available("SBER"), 1_000_000.0)

    def test_bootstrap_processes_only_fresh_bar(self):
        """forward_state пуст → только свежий бар, три года истории не переигрываем."""
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows)                          # state пуст
        runner, opened, _ = _make_runner(db, StubRules(buy_at=(closes[259],)))
        _run_sync(runner, db)

        self.assertEqual(db.state_writes("SBER"), [times[259]])
        self.assertEqual(len(opened), 1)           # входы на bootstrap разрешены
        self.assertTrue(any("forward_state пуст" in e for e in runner.events))
        self.assertEqual(db.catchup, [])           # разрыва не было — журнал молчит


# ─────────────────────────────────────────────────────────────────────────────
# T4 — повторный прогон в тот же день
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotentRerun(unittest.TestCase):

    def test_rerun_is_noop(self):
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={"SBER": times[259]})
        runner, opened, closed = _make_runner(db, StubRules(buy_at=closes))
        _run_sync(runner, db)

        self.assertEqual(db.state_writes(), [])
        self.assertEqual(opened, [])
        self.assertEqual(closed, [])
        self.assertEqual(db.catchup, [])


# ─────────────────────────────────────────────────────────────────────────────
# T5 — падение посреди догона не теряет прогресс
# ─────────────────────────────────────────────────────────────────────────────

class TestCrashMidCatchup(unittest.TestCase):

    def test_progress_survives_and_resumes(self):
        closes = _smooth(260)
        closes[256] = 105.0        # пробитие на ПЕРВОМ догоняемом баре
        closes[257] = 120.0
        closes[258] = 121.0
        closes[259] = 122.0
        rows = _bars(closes)
        times = [r["time"] for r in rows]

        db = FakeDB(rows, state={"SBER": times[255]})
        tid = _seed_position(db, "SBER", entry=120.0, stop=110.0,
                             opened_at=times[252])

        # Прогон 1: бар 256 закрывается и фиксируется, на записи состояния
        # бара 257 — сбой. run() ловит исключение по тикеру, поэтому наружу
        # оно не летит; предмет проверки — что состояние осталось на 256.
        db.fail_on = ("INSERT INTO forward_state", 2)
        runner1, _, closed1 = _make_runner(db, StubRules())
        _run_sync(runner1, db)

        self.assertEqual(len(closed1), 1)
        self.assertEqual(closed1[0].closed_at, times[256])
        self.assertEqual(db.state_writes("SBER"), [times[256]])
        self.assertEqual(db.state["SBER"], times[256])
        self.assertIsNotNone(db.trades[tid]["closed_at"])

        # Прогон 2 на ТОМ ЖЕ FakeDB: догон продолжается с 257, повторного
        # закрытия нет — позиция уже закрыта, а входы на исторических барах
        # запрещены, поэтому переигровка бара безопасна.
        db.fail_on = None
        db.reset_calls()
        runner2, opened2, closed2 = _make_runner(db, StubRules())
        _run_sync(runner2, db)

        self.assertEqual(closed2, [])
        self.assertEqual(opened2, [])
        self.assertEqual(db.state_writes("SBER"),
                         [times[257], times[258], times[259]])


# ─────────────────────────────────────────────────────────────────────────────
# T6, T6b, T12 — предел догона и порог флага
# ─────────────────────────────────────────────────────────────────────────────

class TestGapCapAndFlag(unittest.TestCase):

    def _setup_gap(self, gap, closes=None, position=None):
        closes = closes or _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        last = len(rows) - 1
        db = FakeDB(rows, state={"SBER": times[last - gap]})
        if position:
            _seed_position(db, "SBER", opened_at=times[last - gap - 8], **position)
        runner, opened, closed = _make_runner(db, StubRules())
        _run_sync(runner, db)
        return db, runner, opened, closed, times, last

    def test_gap_over_cap_discards_oldest_and_still_walks_the_rest(self):
        db, runner, _, _, times, last = self._setup_gap(15)
        # 14 исторических баров (15-й — свежий), предел 7 → 7 выброшено.
        args = db.catchup[0]
        self.assertEqual(args[3], 14)                 # gap_bars
        self.assertEqual(args[4], 7)                  # bars_processed
        self.assertEqual(args[5], 7)                  # bars_discarded
        self.assertTrue(args[8])                      # flagged

        writes = db.state_writes("SBER")
        # Первая запись — прыжок через выброшенные бары, дальше побарно.
        self.assertEqual(writes[0], times[last - 8])
        self.assertEqual(writes[1:], [times[i] for i in range(last - 7, last + 1)])
        # Свежий бар обработан ВСЕГДА, независимо от размера разрыва.
        self.assertEqual(db.state["SBER"], times[last])

    def test_gap_over_cap_is_flagged_loudly(self):
        db, runner, _, _, times, last = self._setup_gap(15)
        flags = [e for e in runner.events if e.startswith("🚨")]
        self.assertEqual(len(flags), 1)
        self.assertIn("14 баров", flags[0])
        self.assertIn("выброшено 7", flags[0])
        self.assertIn(str(times[last - 14].date()), flags[0])
        self.assertIn(str(times[last - 1].date()), flags[0])

    def test_forced_exit_after_gap_gets_its_own_reason_type(self):
        """Выброшены бары + стоп пробит → не чистый стоп, а вынужденный выход.

        Настоящее пробитие могло случиться на выброшенном баре по цене, которой
        мы не видели. STOP_LOSS соврал бы статистике, MANUAL занят paper-движком.
        """
        closes = _smooth(260)
        closes[259] = 50.0            # свежий бар обваливается ниже стопа
        db, runner, _, closed, times, last = self._setup_gap(
            15, closes=closes,
            position={"entry": 95.0, "stop": 90.0})

        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].closed_at, times[last])
        self.assertEqual(closed[0].exit_reason_type, ExitReasonType.GAP_FORCED)
        self.assertIn("Вынужденный выход после разрыва", closed[0].exit_reason)
        self.assertIn("выброшено 7", closed[0].exit_reason)

    def test_small_gap_is_caught_up_without_a_flag(self):
        db, runner, _, _, times, last = self._setup_gap(2)
        self.assertEqual([e for e in runner.events if e.startswith("🚨")], [])
        self.assertEqual(db.catchup[0][3], 1)         # gap_bars
        self.assertFalse(db.catchup[0][8])            # flagged

    def test_gap_at_flag_threshold_is_caught_up_and_flagged(self):
        """Разрыв 4 бара: выходы догоняем И флагаем. Порог флага != предел догона."""
        db, runner, _, _, times, last = self._setup_gap(4)
        self.assertEqual(db.catchup[0][3], 3)         # gap_bars >= CATCHUP_FLAG_BARS
        self.assertEqual(db.catchup[0][5], 0)         # ничего не выброшено
        self.assertTrue(db.catchup[0][8])
        self.assertEqual(len(db.state_writes("SBER")), 4)


# ─────────────────────────────────────────────────────────────────────────────
# T9 — рэтчет трейлинга через бары (регрессия на asyncpg.Record)
# ─────────────────────────────────────────────────────────────────────────────

class TestTrailingRatchet(unittest.TestCase):

    def test_ratchet_reads_the_tightened_stop_not_the_original(self):
        """Стоп в памяти обязан двигаться вместе с UPDATE.

        asyncpg.Record не поддерживает __setitem__. Если open_trades хранит
        Record (или dict не мутируется), то на каждом баре рэтчет сравнивает
        новый уровень с ИСХОДНЫМ стопом, а не с текущим. Тогда бар с откатом
        цены запишет стоп НИЖЕ уже установленного — стоп ослабнет, и пробитие
        на следующем баре не сработает. Это дефект №14 на уровень ниже.

        Дискриминатор: бар 257 идёт ниже 256, поэтому его уровень трейлинга
        меньше уже достигнутого. При корректной мутации на нём UPDATE НЕ
        происходит и последовательность строго возрастает; без мутации UPDATE
        происходит и монотонность ломается.
        """
        closes = _smooth(260)
        closes[255] = 113.5
        closes[256] = 114.5
        closes[257] = 114.0        # ← откат: уровень трейлинга ниже достигнутого
        closes[258] = 115.5
        closes[259] = 116.0
        rows = _bars(closes)
        times = [r["time"] for r in rows]

        db = FakeDB(rows, state={"SBER": times[254]})
        _seed_position(db, "SBER", entry=105.0, stop=100.0, opened_at=times[240])
        runner, _, closed = _make_runner(db, StubRules())
        _run_sync(runner, db)

        updates = db.stop_updates()
        self.assertEqual(closed, [], "позиция не должна закрываться в этом кейсе")
        self.assertEqual(len(db.state_writes("SBER")), 5, "обработано 5 баров")
        self.assertEqual(len(updates), 4, "на баре с откатом UPDATE не нужен")
        self.assertEqual(updates, sorted(updates))
        self.assertTrue(all(b > a for a, b in zip(updates, updates[1:])),
                        f"стоп обязан строго возрастать, получено {updates}")


# ─────────────────────────────────────────────────────────────────────────────
# T10 — бар, предшествующий входу, не судится
# ─────────────────────────────────────────────────────────────────────────────

class TestBarBeforeEntryIsNotJudged(unittest.TestCase):

    def test_pre_entry_bars_do_not_close_the_position(self):
        """Позиция открыта на баре 258, стоп «пробит» на 256 и 257 — выхода нет.

        Достижимо: _try_open пишет сделку через оркестратор (своё соединение), а
        состояние — отдельно, поэтому падение между ними оставляет состояние на
        баре N−3 при позиции с opened_at = бар N. Без guard'а догон закрыл бы
        позицию по цене, которой она ещё не существовала.
        """
        closes = _smooth(260)
        closes[256] = 50.0
        closes[257] = 50.0
        closes[258] = 100.0
        closes[259] = 200.0
        rows = _bars(closes)
        times = [r["time"] for r in rows]

        db = FakeDB(rows, state={"SBER": times[255]})
        _seed_position(db, "SBER", entry=95.0, stop=90.0, opened_at=times[258])
        runner, _, closed = _make_runner(db, StubRules())
        _run_sync(runner, db)

        self.assertEqual(closed, [])
        self.assertEqual(len(db.state_writes("SBER")), 4)


# ─────────────────────────────────────────────────────────────────────────────
# T11 — бары-двойники на одну сессию внутри разрыва
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicateSessionBars(unittest.TestCase):
    """Две строки на одну московскую сессию (реальный дефект: 12 пар на 06-25).

    Старая идемпотентность (last_raw <= state_time) вторую строку молча
    пропускала; эта логика переписана, поэтому устойчивость нужна явно:
    легитимный бар не потерять, один и тот же не обработать дважды.
    """

    def setUp(self):
        closes = _smooth(260)
        closes[257] = 105.0                     # пробитие на дублирующейся сессии
        rows = _bars(closes)
        # Копия сессии бара 257 в старой конвенции времени: предыдущий день
        # 21:00+00 = та же московская дата, но другое мгновение, поэтому
        # UNIQUE (ticker, timeframe, time) её не ловит.
        twin = dict(rows[257])
        twin["time"] = rows[257]["time"] - timedelta(hours=3)
        rows.insert(257, twin)

        self.rows = rows
        self.times = [r["time"] for r in rows]
        self.dup_date = rows[257]["time"].astimezone(fwd.MSK).date()

        self.db = FakeDB(rows, state={"SBER": self.times[255]})
        _seed_position(self.db, "SBER", entry=120.0, stop=110.0,
                       opened_at=self.times[250])
        self.runner, _, self.closed = _make_runner(self.db, StubRules())
        _run_sync(self.runner, self.db)

    def test_duplicate_is_detected_and_reported(self):
        self.assertTrue(any("бары-двойники" in e for e in self.runner.events))
        dups = self.db.catchup[0][10]
        self.assertIsNotNone(dups)
        self.assertIn(str(self.dup_date), dups)

    def test_both_rows_advance_state_no_row_is_skipped(self):
        writes = self.db.state_writes("SBER")
        # 256, двойник, 257, 258, свежий 259 — пять СТРОК, каждая ровно раз.
        self.assertEqual(writes, [self.times[i] for i in range(256, 261)])
        self.assertEqual(len(writes), len(set(writes)))

    def test_session_is_not_closed_twice(self):
        self.assertEqual(len(self.closed), 1)
        self.assertEqual(self.closed[0].closed_at, self.times[257])


# ─────────────────────────────────────────────────────────────────────────────
# T13 — снятый тикер не роняет прогон
# ─────────────────────────────────────────────────────────────────────────────

class TestRemovedTickerDoesNotBreakTheRun(unittest.TestCase):

    def test_ticker_without_fresh_candles_does_not_block_the_other(self):
        """_prepare_ticker возвращает None (это ОБЫЧНЫЙ день) — прогон продолжается.

        Первая редакция кода фаз обращалась к plans[t].historical напрямую и
        падала с AttributeError на первом снятом тикере, лишая обработки тикер
        с открытой позицией. Это хуже исходного дефекта.
        """
        closes = _smooth(260)
        closes[257] = 105.0
        closes[258] = 100.0
        closes[259] = 130.0
        rows = _bars(closes)
        times = [r["time"] for r in rows]

        db = FakeDB(rows, state={
            "AAA": times[259],        # свежих свечей нет → тикер снят
            "BBB": times[255],        # разрыв 3 бара, стоп пробит на втором
        })
        _seed_position(db, "BBB", entry=120.0, stop=110.0, opened_at=times[252])
        runner, _, closed = _make_runner(db, StubRules())
        _run_sync(runner, db, tickers=("AAA", "BBB"))

        self.assertEqual(len(closed), 1, "BBB обязан быть обработан полностью")
        self.assertEqual(closed[0].closed_at, times[257])
        self.assertEqual(db.state_writes("BBB"),
                         [times[256], times[257], times[258], times[259]])
        self.assertEqual(db.state_writes("AAA"), [], "состояние AAA не тронуто")
        self.assertEqual(db.state["AAA"], times[259])


# ─────────────────────────────────────────────────────────────────────────────
# T8 — заглядывания в будущее нет
# ─────────────────────────────────────────────────────────────────────────────

class TestNoLookahead(unittest.TestCase):
    """Нарезка окон по полному df_ind ≡ пересчёт на префиксе.

    Это единственный тест, который поймает будущий рефакторинг
    _oscillator_context, ломающий оконную относительность. Настоящие правила и
    блуждание вместо гладкой пилы — иначе bull_div_count/micro_w_trigger были бы
    NaN и проверка стала бы пустой.
    """

    FLOATS = ("close", "atr", "rsi", "rsi9", "adx", "stoch_k", "stoch_d",
              "mac_high", "mac_low", "bb_pct", "macd", "macd_signal")
    DISCRETE = ("bull_div_count", "bear_div_count", "micro_w_trigger",
                "micro_m_trigger", "div_low", "div_high")

    def setUp(self):
        closes = _walk(300, seed=42)
        rows = _bars(closes)
        self.df = pd.DataFrame(
            {k: [r[k] for r in rows] for k in ("open", "high", "low", "close", "volume")},
            index=pd.DatetimeIndex([r["time"].replace(tzinfo=None) for r in rows],
                                   name="datetime"),
        )
        self.rules = RulesEngine(rules_file=fwd.RULES_FILE)
        self.eng = IndicatorEngine(**getattr(self.rules, "divergence_params", {}))
        self.df_ind = self.eng.compute(self.df)

    def _assert_same(self, a, b, field, i):
        both_nan = (a is None or pd.isna(a)) and (b is None or pd.isna(b))
        if both_nan:
            return
        # places=6, не точное равенство: running-sum в pandas.rolling накапливает
        # разную ошибку на префиксе и на полной серии.
        self.assertAlmostEqual(float(a), float(b), places=6,
                               msg=f"{field} на баре {i}")

    def test_slice_equals_prefix_recompute(self):
        for i in (200, 250, 299):
            iv_slice = self.eng.latest_precomputed(signal_window(self.df_ind, i))
            _, iv_trunc, sig_trunc = fwd.signal_for_last_bar(
                self.rules, self.eng, self.df.iloc[:i + 1], "SBER")

            for field in self.FLOATS:
                self._assert_same(getattr(iv_slice, field),
                                  getattr(iv_trunc, field), field, i)
            # Дискретные выходы обязаны совпадать ТОЧНО: это то, на чём
            # правила принимают решение.
            for field in self.DISCRETE:
                a, b = getattr(iv_slice, field), getattr(iv_trunc, field)
                if pd.isna(a) and pd.isna(b):
                    continue
                self.assertEqual(a, b, f"{field} на баре {i}")

            self.assertEqual(self.rules.evaluate(iv_slice, "SBER").action,
                             sig_trunc.action, f"действие на баре {i}")

    def test_signal_window_ends_exactly_at_the_bar(self):
        for i in (100, 200, 299):
            w = signal_window(self.df_ind, i)
            self.assertEqual(w.index[-1], self.df_ind.index[i])
            self.assertLessEqual(len(w), fwd.WINDOW_BARS)


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers(unittest.TestCase):

    def test_last_closed_index_excludes_todays_forming_bar(self):
        """Бар сегодняшней московской сессии ещё формируется — он не закрыт."""
        today = datetime.now(fwd.MSK).date()
        times = [
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(today.year, today.month, today.day, tzinfo=UTC),
        ]
        self.assertEqual(fwd.last_closed_index(times), 0)

    def test_last_closed_index_all_closed(self):
        times = [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)]
        self.assertEqual(fwd.last_closed_index(times), 1)

    def test_last_closed_index_nothing_closed(self):
        today = datetime.now(fwd.MSK).date()
        times = [datetime(today.year, today.month, today.day, tzinfo=UTC)]
        self.assertEqual(fwd.last_closed_index(times), -1)

    def test_duplicate_sessions_matches_production_shape(self):
        """Ровно форма реального дефекта: 21:00+00 и 00:00+00 одной сессии."""
        times = [
            datetime(2026, 6, 23, tzinfo=UTC),
            datetime(2026, 6, 24, 21, tzinfo=UTC),   # МСК 06-25 00:00
            datetime(2026, 6, 25, tzinfo=UTC),       # МСК 06-25 03:00
            datetime(2026, 6, 26, tzinfo=UTC),
        ]
        dups = fwd._duplicate_sessions(times)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["date"], "2026-06-25")
        self.assertEqual(len(dups[0]["times"]), 2)

    def test_duplicate_sessions_clean_series(self):
        times = [datetime(2026, 6, d, tzinfo=UTC) for d in (23, 24, 25, 26)]
        self.assertEqual(fwd._duplicate_sessions(times), [])

    def test_catchup_cap_env_can_only_tighten(self):
        with patch.dict("os.environ", {"FWD_CATCHUP_MAX_BARS": "30"}):
            value, note = fwd._catchup_max_bars()
        self.assertEqual(value, fwd.CATCHUP_MAX_BARS_CEILING)
        self.assertIsNotNone(note, "попытка ослабить предел обязана быть видна")

    def test_catchup_cap_env_tighter_is_accepted(self):
        with patch.dict("os.environ", {"FWD_CATCHUP_MAX_BARS": "3"}):
            value, note = fwd._catchup_max_bars()
        self.assertEqual(value, 3)
        self.assertIsNone(note)

    def test_catchup_cap_default(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("FWD_CATCHUP_MAX_BARS", None)
            value, note = fwd._catchup_max_bars()
        self.assertEqual(value, fwd.CATCHUP_MAX_BARS_DEFAULT)
        self.assertIsNone(note)


if __name__ == "__main__":
    unittest.main()
