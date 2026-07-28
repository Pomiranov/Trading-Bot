"""Market data access — quotes and, crucially, how old they are.

Every mark price, unrealized PnL, paper fill and "live" signal in this product
derives from ``candles``. The newest candle in the live database is 32 days old
and nothing in the old UI said so. A quote without its age is not a quote, so
every method here returns the timestamp alongside the price and the caller has
no way to obtain one without the other.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from qf_platform.repositories.base import BaseRepository


class MarketRepository(BaseRepository):
    def latest_quote(self, ticker: str, timeframe: str = "1d") -> Optional[dict]:
        """`{price, as_of, timeframe}` for one instrument, or None."""
        rows = self._query(
            """
            SELECT close AS price, time AS as_of, timeframe
            FROM candles
            WHERE ticker = :ticker AND timeframe = :tf
            ORDER BY time DESC
            LIMIT 1
            """,
            {"ticker": ticker.upper(), "tf": timeframe},
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "price": float(row["price"]),
            "as_of": row["as_of"],
            "timeframe": row["timeframe"],
        }

    def latest_quotes(self, tickers: list[str], timeframe: str = "1d") -> dict[str, dict]:
        """One query for many instruments.

        The old code opened a fresh connection per position inside a loop over a
        five-connection pool. `DISTINCT ON` gets the same answer in one round
        trip and keeps the per-quote timestamp attached.
        """
        if not tickers:
            return {}
        rows = self._query(
            """
            SELECT DISTINCT ON (ticker) ticker, close AS price, time AS as_of, timeframe
            FROM candles
            WHERE ticker = ANY(:tickers) AND timeframe = :tf
            ORDER BY ticker, time DESC
            """,
            {"tickers": [t.upper() for t in tickers], "tf": timeframe},
        )
        return {
            row["ticker"]: {
                "price": float(row["price"]),
                "as_of": row["as_of"],
                "timeframe": row["timeframe"],
            }
            for row in rows
        }

    def newest_candle_at(self, timeframe: Optional[str] = None) -> Optional[datetime]:
        """Freshness of the market-data feed as a whole."""
        clause = "WHERE timeframe = :tf" if timeframe else ""
        rows = self._query(
            f"SELECT MAX(time) AS newest FROM candles {clause}",
            {"tf": timeframe} if timeframe else {},
        )
        return rows[0]["newest"] if rows else None

    def candle_coverage(self) -> list[dict]:
        """Per-instrument feed health: rows, newest bar, oldest bar."""
        return self._query(
            """
            SELECT ticker, timeframe,
                   COUNT(*)   AS bars,
                   MAX(time)  AS newest,
                   MIN(time)  AS oldest
            FROM candles
            GROUP BY ticker, timeframe
            ORDER BY ticker, timeframe
            """
        )

    def candles(self, ticker: str, timeframe: str = "1d", limit: int = 180) -> list[dict]:
        """Newest-first in SQL (so LIMIT takes the recent end), oldest-first out."""
        rows = self._query(
            """
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE ticker = :ticker AND timeframe = :tf
            ORDER BY time DESC
            LIMIT :lim
            """,
            {"ticker": ticker.upper(), "tf": timeframe, "lim": limit},
        )
        return list(reversed(rows))

    def known_tickers(self) -> list[str]:
        return [r["ticker"] for r in self._query(
            "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
        )]
