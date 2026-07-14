"""Unified market data hub — DB + API providers with graceful fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MarketQuote:
    ticker: str
    last: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    exchange: str = "db"

    @property
    def mid(self) -> float:
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return self.last


class MarketDataHub:
    def __init__(self, db_engine):
        self._engine = db_engine

    def get_quote(self, ticker: str) -> Optional[MarketQuote]:
        # 1. Try DB (fastest, most reliable)
        price = self._from_db(ticker)
        if price:
            return MarketQuote(ticker=ticker.upper(), last=price, exchange="db")

        # 2. Try Tinkoff live (optional, graceful fail)
        try:
            from broker.tinkoff_client import tinkoff_client
            instr = tinkoff_client.find_instrument(ticker)
            if instr:
                ob = tinkoff_client.get_orderbook(instr["figi"])
                if ob and ob.get("last_price"):
                    p = float(ob["last_price"])
                    return MarketQuote(
                        ticker=ticker.upper(),
                        last=p,
                        bid=ob.get("bids", [{}])[0].get("price"),
                        ask=ob.get("asks", [{}])[0].get("price"),
                        exchange="tinkoff",
                    )
        except Exception:
            pass

        return None

    def _from_db(self, ticker: str) -> Optional[float]:
        from sqlalchemy import text
        try:
            with self._engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT close FROM candles WHERE ticker = :t"
                        " AND timeframe = '1d' ORDER BY time DESC LIMIT 1"
                    ),
                    {"t": ticker.upper()},
                ).fetchone()
                return float(row[0]) if row else None
        except Exception as exc:
            logger.debug("MarketDataHub._from_db error for %s: %s", ticker, exc)
            return None

    def get_ohlc(
        self,
        ticker: str,
        interval: str = "1d",
        limit: int = 120,
    ) -> pd.DataFrame:
        from sqlalchemy import text
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT time, open, high, low, close, volume FROM candles
                        WHERE ticker = :t AND timeframe = :tf
                        ORDER BY time DESC LIMIT :lim
                        """
                    ),
                    {"t": ticker.upper(), "tf": interval, "lim": limit},
                ).fetchall()
        except Exception as exc:
            logger.warning("MarketDataHub.get_ohlc error: %s", exc)
            return pd.DataFrame()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df.sort_values("time").reset_index(drop=True)

    def available_tickers(self) -> list[str]:
        from sqlalchemy import text
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT DISTINCT ticker FROM candles ORDER BY ticker")
                ).fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            logger.warning("MarketDataHub.available_tickers error: %s", exc)
            return []
