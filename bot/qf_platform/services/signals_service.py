"""Trading signals center — generation, storage, filtering."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import Engine

from config import config
from qf_platform.dto import SignalDTO
from qf_platform.repositories.signals_repository import SignalsRepository
from signals.indicators import IndicatorEngine
from signals.rules_engine import Action, RulesEngine

logger = logging.getLogger(__name__)

EXCHANGE_MAP = {
    "SBER": ("moex", "stocks"),
    "GAZP": ("moex", "stocks"),
    "LKOH": ("moex", "stocks"),
    "NVTK": ("moex", "stocks"),
    "YNDX": ("moex", "stocks"),
    "BTCUSDT": ("bybit", "crypto"),
    "ETHUSDT": ("bybit", "crypto"),
}

EXCHANGE_ALIASES = {
    "bybit": "bybit",
    "finam": "finam",
    "tinkoff": "tinkoff",
    "tbank": "tinkoff",
    "т-банк": "tinkoff",
    "moex": "moex",
}


class SignalsService:
    def __init__(self, engine: Engine):
        self._engine = engine
        self._repo = SignalsRepository(engine)
        self._indicators = IndicatorEngine()
        self._rules = RulesEngine()

    def _parse_metadata(self, raw) -> dict:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw:
            import json
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        return {}

    def _row_to_dto(self, row: dict) -> SignalDTO:
        return SignalDTO(
            id=int(row["id"]),
            asset=row["asset"],
            exchange=row["exchange"],
            timeframe=row["timeframe"],
            signal_type=row["signal_type"],
            entry_price=float(row["entry_price"] or 0),
            stop_loss=float(row["stop_loss"]) if row.get("stop_loss") else None,
            take_profit_1=float(row["take_profit_1"]) if row.get("take_profit_1") else None,
            take_profit_2=float(row["take_profit_2"]) if row.get("take_profit_2") else None,
            take_profit_3=float(row["take_profit_3"]) if row.get("take_profit_3") else None,
            risk_reward=float(row["risk_reward"]) if row.get("risk_reward") else None,
            probability_pct=float(row["probability_pct"] or 50),
            generated_at=str(row["generated_at"])[:19],
            status=row["status"],
            source=row["source"],
            asset_class=row["asset_class"],
            metadata=self._parse_metadata(row.get("metadata")),
        )

    def _classify_regime(self, adx) -> str:
        if adx is None or math.isnan(adx):
            return "unknown"
        if adx >= 25:
            return "trending"
        if adx < 20:
            return "ranging"
        return "volatile"

    def _detect_strategy(self, signal) -> str:
        names = {r.name for r in signal.triggered_rules}
        if any("macd" in n.lower() for n in names) and any("rsi" in n.lower() for n in names):
            return "MACD+RSI Momentum"
        if any("ema" in n.lower() or "trend" in n.lower() for n in names):
            return "EMA Trend Follow"
        if any("bb" in n.lower() or "bollinger" in n.lower() for n in names):
            return "Bollinger Reversal"
        if any("adx" in n.lower() for n in names):
            return "ADX Breakout"
        if any("macd" in n.lower() for n in names):
            return "MACD Signal"
        if any("rsi" in n.lower() for n in names):
            return "RSI Oscillator"
        return "Multi-Factor Rules"

    def _build_entry_reason(self, signal, iv) -> str:
        parts = []
        triggered_names = [r.name for r in signal.triggered_rules]
        if triggered_names:
            parts.append(f"Сработали правила: {', '.join(triggered_names[:3])}")
        if iv.rsi and not math.isnan(iv.rsi):
            if iv.rsi < 30:
                parts.append(f"RSI перепродан ({iv.rsi:.1f})")
            elif iv.rsi > 70:
                parts.append(f"RSI перекуплен ({iv.rsi:.1f})")
            else:
                parts.append(f"RSI нейтральный ({iv.rsi:.1f})")
        if iv.adx and not math.isnan(iv.adx):
            if iv.adx >= 25:
                parts.append(f"Сильный тренд (ADX {iv.adx:.1f})")
            else:
                parts.append(f"Флет (ADX {iv.adx:.1f})")
        if iv.macd_hist and not math.isnan(iv.macd_hist):
            direction = "бычий" if iv.macd_hist > 0 else "медвежий"
            parts.append(f"MACD гистограмма {direction}")
        return "; ".join(parts) if parts else "Технические индикаторы"

    def _compute_levels(self, price: float, atr: float, action: str) -> dict:
        sl_dist = atr * config.risk.atr_stop_multiplier
        if action in ("BUY", "LONG"):
            sl = round(price - sl_dist, 4)
            tp1 = round(price + sl_dist, 4)
            tp2 = round(price + sl_dist * 2, 4)
            tp3 = round(price + sl_dist * 3, 4)
        else:
            sl = round(price + sl_dist, 4)
            tp1 = round(price - sl_dist, 4)
            tp2 = round(price - sl_dist * 2, 4)
            tp3 = round(price - sl_dist * 3, 4)
        rr = round(abs(tp1 - price) / abs(price - sl), 2) if sl != price else 0
        return {"stop_loss": sl, "take_profit_1": tp1, "take_profit_2": tp2, "take_profit_3": tp3, "risk_reward": rr}

    def generate_live_signals(self, persist: bool = True) -> list[SignalDTO]:
        tickers = [r["ticker"] for r in self._repo._query(
            "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
        )]
        results: list[SignalDTO] = []

        for ticker in tickers:
            rows = self._repo._query(
                """
                SELECT time, open, high, low, close, volume FROM candles
                WHERE ticker = :ticker AND timeframe = '1d'
                ORDER BY time ASC LIMIT 120
                """,
                {"ticker": ticker},
            )
            if len(rows) < 35:
                continue

            df = pd.DataFrame(rows)
            df.set_index("time", inplace=True)
            for col in ("open", "high", "low", "close", "volume"):
                df[col] = df[col].astype(float)

            iv = self._indicators.latest(df)
            signal = self._rules.evaluate(iv)
            if signal.action == Action.HOLD:
                continue

            price = float(rows[-1]["close"])
            atr = float(iv.atr) if iv.atr and not math.isnan(iv.atr) else price * 0.02
            action = signal.action.value
            if action == "BUY":
                signal_type = "LONG"
            elif action == "SELL":
                signal_type = "SHORT"
            else:
                signal_type = action

            exchange, asset_class = EXCHANGE_MAP.get(ticker, ("moex", "stocks"))
            levels = self._compute_levels(price, atr, action)
            confidence = round(min(0.95, max(0.30, signal.confidence if signal.confidence > 0 else 0.5 + signal.score * 0.05)), 3)
            prob = round(confidence * 100, 1)

            entry_reason = signal.reason or self._build_entry_reason(signal, iv)
            strategy = self._detect_strategy(signal)

            data = {
                "asset": ticker,
                "exchange": exchange,
                "timeframe": "1d",
                "signal_type": signal_type,
                "entry_price": price,
                "probability_pct": prob,
                "status": "new",
                "source": "indicators",
                "asset_class": asset_class,
                "metadata": {
                    "buy_score": signal.buy_score,
                    "sell_score": signal.sell_score,
                    "confidence": confidence,
                    "strategy": strategy,
                    "entry_reason": entry_reason,
                    "triggered": [r.name for r in signal.triggered_rules],
                    "rsi": float(iv.rsi) if iv.rsi and not math.isnan(iv.rsi) else None,
                    "adx": float(iv.adx) if iv.adx and not math.isnan(iv.adx) else None,
                    "macd_hist": float(iv.macd_hist) if iv.macd_hist and not math.isnan(iv.macd_hist) else None,
                    "atr": float(atr),
                    "close": float(price),
                    "regime": self._classify_regime(iv.adx),
                },
                **levels,
            }

            if persist:
                sig_id = self._repo.insert(data)
                data["id"] = sig_id
                data["generated_at"] = datetime.utcnow()
            else:
                data["id"] = 0
                data["generated_at"] = datetime.utcnow()

            results.append(self._row_to_dto(data))

        return results

    def list_signals(
        self,
        exchange: Optional[str] = None,
        asset_class: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[SignalDTO]:
        if exchange:
            exchange = EXCHANGE_ALIASES.get(exchange.lower(), exchange)
        rows = self._repo.list_signals(exchange=exchange, asset_class=asset_class, status=status, limit=limit)
        if not rows:
            return self.generate_live_signals(persist=True)
        return [self._row_to_dto(r) for r in rows]

    def get_signal(self, signal_id: int) -> Optional[SignalDTO]:
        rows = self._repo._query("SELECT * FROM trading_signals WHERE id = :id", {"id": signal_id})
        return self._row_to_dto(rows[0]) if rows else None

    def execute_signal(self, signal_id: int) -> dict:
        signal = self.get_signal(signal_id)
        if not signal:
            raise ValueError("Сигнал не найден")
        self._repo.update_status(signal_id, "executing")
        from qf_platform.services.paper_trading_service import PaperTradingService
        paper = PaperTradingService(self._engine)
        result = paper.execute_from_signal({
            "asset": signal.asset,
            "signal_type": signal.signal_type,
            "stop_loss": signal.stop_loss,
            "take_profit_1": signal.take_profit_1,
            "exchange": signal.exchange,
        })
        self._repo.update_status(signal_id, "executing")
        return result