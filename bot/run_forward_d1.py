"""QuantFlow — форвард-контур osc_range_moex на D1 (бумажная торговля + обучение).

Запуск:
    python run_forward_d1.py        # ежедневно после закрытия MOEX (пн-пт ~19:15 МСК)

Один прогон: догрузить D1-свечи → для каждого тикера обработать последнюю
свечу зеркально бэктесту (backtest/engine.py): стоп-лосс → exit_rules →
SELL-сигнал → трейлинг; вход — через orchestrator.check_signal() (внутри
фильтр структурного даунтренда, отказ пишется в skipped_signals), закрытие —
через on_trade_closed() (запускает цикл обучения).

Паритет с бэктестом: окно индикаторов 61 бар, сделки по ценам закрытия,
комиссия 0.03% за сторону, ATR-трейлинг (config.risk.atr_stop_multiplier).

Сознательные отличия от бэктеста:
  - портфельный режим: общий бумажный капитал FORWARD_CAPITAL (по умолчанию
    1 000 000 руб.) на все тикеры и лимит config.risk.max_open_positions —
    в бэктесте у каждого тикера был независимый капитал 1 млн;
  - position_size_multiplier из check_signal логируется, но НЕ применяется
    (сначала валидируем бэктест-конфигурацию как есть).

Состояние — только в БД: открытые позиции в trades (closed_at IS NULL,
strategy_id = osc_range_moex_d1_fwd), идемпотентность через forward_state.
Повторный запуск в тот же день — no-op.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
import logging
import math
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import asyncpg
import pandas as pd

from config import config
from data.loader import save_candles_to_db
from signals.indicators import IndicatorEngine
from signals.rules_engine import RulesEngine, Action, classify_regime
from risk.risk_manager import RiskManager
from learning.trading_orchestrator import TradingOrchestrator
from learning.memory_writer import (
    Trade,
    Market,
    Direction,
    MarketRegime,
    ExitReasonType,
)
# ui.telegram_bot импортируется лениво в run(): его импорт тянет легаси
# feedback_store, который при загрузке модуля ходит в БД со старой схемой.

logger = logging.getLogger("quantflow.forward")

STRATEGY_ID        = "osc_range_moex_d1_fwd"
SEED_FROM_STRATEGY = "osc_range_moex_d1"     # belief-строка-источник (бэктест)

TICKERS = ["SBER", "GAZP", "LKOH", "NVTK", "ROSN", "TATN",
           "MGNT", "MOEX", "PLZL", "CHMF", "ALRS", "SNGS"]

RULES_FILE = Path(__file__).resolve().parent.parent / "knowledge" / "rules" / "rules_osc_range.yaml"

COMMISSION_PCT   = 0.0003    # 0.03% за сторону — как в бэктесте
WINDOW_BARS      = 61        # окно latest_precomputed — как iloc[i-60:i+1] бэктеста
MIN_HISTORY_BARS = 250       # SMA200 фильтра + запас
STALE_DAYS       = 5         # свеча старше — данные протухли, тикер не обрабатываем
REFRESH_DAYS     = 10        # окно перекрытия при догрузке свечей

FORWARD_CAPITAL = float(os.getenv("FORWARD_CAPITAL", "1000000"))


def _dec(value: float) -> Decimal:
    """float → Decimal без артефактов двоичного представления (как в бэктесте)."""
    return Decimal(str(round(float(value), 6)))


def signal_for_last_bar(
    rules: RulesEngine,
    ind_engine: IndicatorEngine,
    df: pd.DataFrame,
    ticker: str = "",
):
    """Индикаторы и сигнал по последней свече — ровно как в бэктесте.

    Возвращает (df_ind, iv, signal). Вынесено в модульную функцию, чтобы
    паритет-тесты могли прогнать ту же логику на обрезанной истории.
    """
    df_ind = ind_engine.compute(df)
    iv = ind_engine.latest_precomputed(df_ind.iloc[-WINDOW_BARS:])
    return df_ind, iv, rules.evaluate(iv, ticker)


class ForwardRunner:
    """Однопроходный дневной прогон форвард-контура."""

    def __init__(self):
        self.rules      = RulesEngine(rules_file=RULES_FILE)
        self.indicators = IndicatorEngine(**getattr(self.rules, "divergence_params", {}))
        self.risk       = RiskManager()
        self.orch       = TradingOrchestrator()
        self._db: Optional[asyncpg.Connection] = None
        self.events: list[str] = []     # сводка дня для консоли и Telegram
        self.available: float = 0.0     # свободный бумажный капитал

    # ── Инфраструктура ────────────────────────────────────────────────

    @staticmethod
    def _dsn() -> str:
        return config.db.dsn

    def _event(self, msg: str) -> None:
        self.events.append(msg)
        logger.info(msg)

    async def _seed_belief(self) -> None:
        """Создать belief-строку форвард-стратегии (однократно, идемпотентно)."""
        exists = await self._db.fetchval(
            "SELECT 1 FROM belief_system WHERE strategy_id = $1", STRATEGY_ID)
        if exists:
            return
        await self._db.execute("""
            INSERT INTO belief_system (strategy_id, strategy_name, market, description,
                                       confidence, best_regime, best_timeframe)
            SELECT $1, strategy_name || ' (форвард)', market, description,
                   confidence, best_regime, best_timeframe
            FROM belief_system WHERE strategy_id = $2
            ON CONFLICT (strategy_id) DO NOTHING
        """, STRATEGY_ID, SEED_FROM_STRATEGY)
        exists = await self._db.fetchval(
            "SELECT 1 FROM belief_system WHERE strategy_id = $1", STRATEGY_ID)
        if not exists:   # источника нет — минимальная строка с дефолтами
            await self._db.execute("""
                INSERT INTO belief_system (strategy_id, strategy_name, market, description)
                VALUES ($1, 'Осцилляторы боковика D1 (форвард)', 'stocks',
                        'Форвард-контур osc_range_moex, D1, бумажное исполнение')
                ON CONFLICT (strategy_id) DO NOTHING
            """, STRATEGY_ID)
        self._event(f"Belief-строка {STRATEGY_ID} создана")

    async def _load_open_trades(self) -> dict:
        """Открытые форвард-позиции из БД: ticker → запись trades."""
        rows = await self._db.fetch("""
            SELECT trade_id, ticker, entry_price, stop_loss, position_size,
                   risk_amount, opened_at
            FROM trades
            WHERE strategy_id = $1 AND closed_at IS NULL AND is_sandbox
            ORDER BY opened_at
        """, STRATEGY_ID)
        open_trades: dict = {}
        for r in rows:
            if r["ticker"] in open_trades:
                logger.warning("Несколько открытых позиций по %s — использую первую", r["ticker"])
                continue
            open_trades[r["ticker"]] = r
        return open_trades

    async def _paper_capital(self, open_trades: dict) -> float:
        """Свободный капитал = базовый + реализованный PnL − стоимость открытых."""
        realized = await self._db.fetchval("""
            SELECT COALESCE(SUM(pnl), 0) FROM trades
            WHERE strategy_id = $1 AND closed_at IS NOT NULL
        """, STRATEGY_ID)
        open_value = sum(
            float(r["entry_price"]) * float(r["position_size"])
            for r in open_trades.values()
        )
        return FORWARD_CAPITAL + float(realized) - open_value

    # ── Обработка тикера ─────────────────────────────────────────────

    async def _process_ticker(self, ticker: str, open_trades: dict) -> None:
        rows = await self._db.fetch("""
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE ticker = $1 AND timeframe = '1d'
            ORDER BY time
        """, ticker)
        if len(rows) < MIN_HISTORY_BARS:
            self._event(f"⚠ {ticker}: мало истории D1 ({len(rows)} баров) — пропуск")
            return

        last_raw = rows[-1]["time"]     # tz-aware, как в БД

        # Идемпотентность: последняя свеча уже обработана?
        state_time = await self._db.fetchval("""
            SELECT last_candle_time FROM forward_state
            WHERE strategy_id = $1 AND ticker = $2
        """, STRATEGY_ID, ticker)
        if state_time is not None and last_raw <= state_time:
            logger.info("[%s] Свежих свечей нет (последняя %s) — пропуск", ticker, last_raw.date())
            return

        # Протухшие данные: решение по старой свече опаснее, чем его отсутствие
        age_days = (datetime.now(timezone.utc) - last_raw).days
        if age_days > STALE_DAYS:
            self._event(f"⚠ {ticker}: последняя свеча {last_raw.date()} ({age_days} дн. назад) — пропуск")
            return

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

        df_ind, iv, signal = signal_for_last_bar(self.rules, self.indicators, df, ticker)
        row   = df_ind.iloc[-1]
        price = float(row["close"])
        _atr  = row.get("atr")
        atr   = float(_atr) if _atr is not None and pd.notna(_atr) else price * 0.01

        pos = open_trades.get(ticker)
        if pos is not None:
            # Порядок как в бэктесте: стоп → exit_rules → SELL → трейлинг
            if price <= float(pos["stop_loss"]):
                await self._close_position(
                    pos, price, last_raw, ExitReasonType.STOP_LOSS,
                    f"Форвард: стоп-лосс {float(pos['stop_loss']):.2f}")
                open_trades.pop(ticker)
            else:
                exit_sig = self.rules.evaluate_exit(iv, ticker)
                if exit_sig.action == Action.EXIT:
                    await self._close_position(
                        pos, price, last_raw, ExitReasonType.SIGNAL, exit_sig.reason)
                    open_trades.pop(ticker)
                elif signal.action == Action.SELL:
                    await self._close_position(
                        pos, price, last_raw, ExitReasonType.SIGNAL, signal.reason)
                    open_trades.pop(ticker)
                elif atr > 0:
                    new_stop = price - atr * self.risk.cfg.atr_stop_multiplier
                    if new_stop > float(pos["stop_loss"]):
                        await self._db.execute(
                            "UPDATE trades SET stop_loss = $2 WHERE trade_id = $1",
                            pos["trade_id"], _dec(new_stop))
                        logger.info("[%s] Трейлинг-стоп: %.2f", ticker, new_stop)

        elif signal.action == Action.BUY:
            await self._try_open(ticker, df_ind, iv, signal, price, atr, last_raw, open_trades)

        # Свеча обработана — зафиксировать для идемпотентности
        await self._db.execute("""
            INSERT INTO forward_state (strategy_id, ticker, last_candle_time, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (strategy_id, ticker)
            DO UPDATE SET last_candle_time = EXCLUDED.last_candle_time, updated_at = NOW()
        """, STRATEGY_ID, ticker, last_raw)

    async def _try_open(self, ticker, df_ind, iv, signal, price, atr, dt, open_trades) -> None:
        """BUY-сигнал: check_signal (фильтры, confidence) → сайзинг → открытие."""

        def _feat(col: str) -> Optional[float]:
            val = df_ind.iloc[-1].get(col)
            if val is None or not pd.notna(val):
                return None
            val = float(val)
            return val if math.isfinite(val) else None

        volume_ratio = None
        vol_ma = df_ind["volume"].rolling(20).mean().iloc[-1]
        vol    = df_ind["volume"].iloc[-1]
        if pd.notna(vol_ma) and vol_ma:
            volume_ratio = round(float(vol) / float(vol_ma), 4)

        features = {
            "rsi": _feat("rsi"), "atr": _feat("atr"), "adx": _feat("adx"),
            "bb_pct": _feat("bb_pct"), "volume_ratio": volume_ratio,
        }
        # Кворум расхождений сигнального окна — как в бэктесте, для learning
        for attr in ("bull_div_count", "bear_div_count"):
            val = getattr(iv, attr, float("nan"))
            if val is not None and math.isfinite(val):
                features[attr] = float(val)
        features = {k: v for k, v in features.items() if v is not None}
        regime = classify_regime(_feat("adx"))

        decision = await self.orch.check_signal({
            "strategy_id":     STRATEGY_ID,
            "ticker":          ticker,
            "direction":       "BUY",
            "timeframe":       "D1",
            "market_regime":   regime,
            "market_features": features,
            "is_sandbox":      True,
        })
        if not decision["approved"]:
            self._event(f"⛔ {ticker}: BUY-сигнал отклонён — {decision['reason']}")
            return

        if len(open_trades) >= config.risk.max_open_positions:
            self._event(f"⛔ {ticker}: BUY-сигнал, но лимит позиций "
                        f"({config.risk.max_open_positions}) исчерпан")
            return

        pos = self.risk.calculate_position(
            ticker=ticker, entry_price=price, atr=atr,
            portfolio_value=self.available, lot_size=1,
        )
        if pos is None or pos.position_value > self.available:
            self._event(f"⛔ {ticker}: BUY-сигнал, но не хватает капитала "
                        f"(свободно {self.available:,.0f})")
            return

        entry = _dec(price)
        stop  = _dec(pos.stop_price)
        n     = Decimal(int(pos.shares))
        risk  = (entry - stop) * n
        if risk <= 0:
            risk = entry * Decimal("0.01") * n

        conf = getattr(signal, "confidence", None)
        trade = Trade(
            market          = Market.STOCKS,
            ticker          = ticker,
            direction       = Direction.BUY,
            strategy_id     = STRATEGY_ID,
            entry_price     = entry,
            stop_loss       = stop,
            position_size   = n,
            risk_amount     = risk,
            risk_percent    = (risk / _dec(self.available)).quantize(Decimal("0.0001"))
                              if self.available > 0 else None,
            opened_at       = dt,
            timeframe       = "D1",
            market_regime   = MarketRegime(regime) if regime else None,
            market_features = features or None,
            confidence      = _dec(min(max(conf, 0.0), 1.0))
                              if conf is not None and math.isfinite(conf) else None,
            entry_reason    = (signal.reason or "Сигнал BUY форварда")
                              + f" | size_mult={float(decision['position_size_multiplier']):.2f} (не применён)",
            is_sandbox      = True,
        )
        await self.orch.on_trade_opened(trade)

        commission = pos.position_value * COMMISSION_PCT
        self.available -= pos.position_value + commission
        open_trades[ticker] = {
            "trade_id": trade.trade_id, "ticker": ticker,
            "entry_price": entry, "stop_loss": stop,
            "position_size": n, "risk_amount": risk, "opened_at": dt,
        }
        self._event(f"🟢 {ticker}: BUY {pos.shares} акц. @ {price:.2f}, "
                    f"стоп {pos.stop_price:.2f} ({signal.reason[:80]})")

    async def _close_position(self, rec, price: float, dt, reason_type, reason_text: str) -> None:
        """Бумажное закрытие по цене закрытия свечи (PnL как в бэктесте)."""
        shares     = float(rec["position_size"])
        entry      = float(rec["entry_price"])
        commission = shares * price * COMMISSION_PCT
        pnl        = (price - entry) * shares - commission

        trade = Trade(
            market           = Market.STOCKS,
            ticker           = rec["ticker"],
            direction        = Direction.BUY,
            strategy_id      = STRATEGY_ID,
            entry_price      = Decimal(str(rec["entry_price"])),
            stop_loss        = Decimal(str(rec["stop_loss"])),
            position_size    = Decimal(str(rec["position_size"])),
            risk_amount      = Decimal(str(rec["risk_amount"])),
            opened_at        = rec["opened_at"],
            timeframe        = "D1",
            exit_price       = _dec(price),
            closed_at        = dt,
            pnl              = _dec(pnl),
            commission       = _dec(commission),
            exit_reason_type = reason_type,
            exit_reason      = reason_text,
            is_sandbox       = True,
            trade_id         = str(rec["trade_id"]),
        )
        await self.orch.on_trade_closed(trade)
        self.available += shares * price - commission
        emoji = "🔴" if pnl <= 0 else "💰"
        self._event(f"{emoji} {rec['ticker']}: EXIT @ {price:.2f}, PnL {pnl:+,.0f} руб. "
                    f"({reason_text[:80]})")

    # ── Главный цикл ─────────────────────────────────────────────────

    async def run(self) -> None:
        started = datetime.now(timezone.utc)

        # 1. Догрузка свечей: сбой не фатален — идемпотентность и проверка
        #    протухания не дадут решать по старым данным.
        try:
            saved = save_candles_to_db(TICKERS, interval="1d", days=REFRESH_DAYS, verbose=False)
            logger.info("Догрузка свечей: %d строк", saved)
        except Exception as exc:
            self._event(f"⚠ Догрузка свечей с MOEX ISS не удалась: {exc}")

        await self.orch.connect()
        self._db = await asyncpg.connect(self._dsn())
        try:
            await self._seed_belief()
            open_trades    = await self._load_open_trades()
            self.available = await self._paper_capital(open_trades)
            logger.info("Открытых позиций: %d | свободный капитал: %s",
                        len(open_trades), f"{self.available:,.0f}")

            for ticker in TICKERS:
                try:
                    await self._process_ticker(ticker, open_trades)
                except Exception as exc:
                    self._event(f"⚠ {ticker}: ошибка обработки — {exc}")
                    logger.exception("[%s] Ошибка обработки", ticker)

            summary = (f"Форвард D1 {started.date()}: позиций {len(open_trades)}, "
                       f"свободно {self.available:,.0f} руб., событий {len(self.events)}")
            print("\n" + "═" * 64)
            print(f"  {summary}")
            for e in self.events:
                print(f"  {e}")
            print("═" * 64)

            if self.events:
                from ui.telegram_bot import send_notification
                await send_notification("📊 " + summary + "\n" + "\n".join(self.events))
        finally:
            await self._db.close()
            await self.orch.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(ForwardRunner().run())


if __name__ == "__main__":
    main()
