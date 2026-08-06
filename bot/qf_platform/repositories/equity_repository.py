"""Equity snapshot access — the real capital series.

The old ``/api/equity`` fell through to a candle-derived path that normalised
SBER's share price to a starting balance and served it as portfolio equity. This
repository is the only source the new contract reads, and it has no fallback: an
account with no snapshots reports "no history", which is true, rather than a
plausible curve, which is not.

Two further problems the read path has to survive:

* **16 123 rows holding 44 distinct values.** Snapshots were written by GET
  handlers on a 12-second poll, so the series records how long a tab was open.
  Resampling happens on the time axis, in SQL, not by taking ``LIMIT 200``.
* **No retention.** ``prune_older_than`` exists so a scheduled job can bound the
  table; it is never called from a read path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from qf_platform.environment import Environment
from qf_platform.repositories.base import BaseRepository

#: Bucket width per window. Chosen so a window yields 60–200 points: enough to
#: show shape, few enough that the payload stays small and the line stays honest.
WINDOW_BUCKETS: dict[str, tuple[Optional[timedelta], str]] = {
    "1d":  (timedelta(days=1),   "15 minutes"),
    "7d":  (timedelta(days=7),   "1 hour"),
    "30d": (timedelta(days=30),  "6 hours"),
    "90d": (timedelta(days=90),  "1 day"),
    "1y":  (timedelta(days=365), "1 week"),
    "all": (None,                "1 day"),
}


class EquityRepository(BaseRepository):
    def series(
        self,
        account_id: int,
        *,
        window: str = "90d",
        environment: Environment = Environment.SANDBOX,
    ) -> list[dict]:
        """Time-bucketed equity for one account and one environment.

        Buckets use ``date_trunc``-equivalent arithmetic via ``to_timestamp(floor(...))``
        so the x-axis is wall-clock time. Each bucket reports the *last* value in
        it — an equity curve is a level, not an average, and averaging inside a
        bucket invents values the account never had.
        """
        span, bucket = WINDOW_BUCKETS.get(window, WINDOW_BUCKETS["90d"])
        params: dict = {
            "aid": account_id,
            "bucket": bucket,
            "env": Environment.coerce(environment).value,
        }
        since_clause = ""
        if span is not None:
            params["since"] = datetime.now(timezone.utc) - span
            since_clause = "AND snapshot_at >= :since"

        return self._query(
            f"""
            WITH bucketed AS (
                SELECT
                    to_timestamp(
                        floor(extract(epoch FROM snapshot_at)
                              / extract(epoch FROM CAST(:bucket AS interval)))
                        * extract(epoch FROM CAST(:bucket AS interval))
                    ) AS bucket_at,
                    snapshot_at,
                    equity
                FROM equity_snapshots
                WHERE account_id = :aid
                  AND COALESCE(environment, 'sandbox') = :env
                  {since_clause}
            )
            SELECT DISTINCT ON (bucket_at)
                   bucket_at AS ts,
                   equity,
                   snapshot_at AS source_at
            FROM bucketed
            ORDER BY bucket_at, snapshot_at DESC
            """,
            params,
        )

    def stats(
        self,
        account_id: int,
        *,
        window: str = "90d",
        environment: Environment = Environment.SANDBOX,
    ) -> dict:
        """Coverage of the raw series: count, first/last observation and value."""
        span, _ = WINDOW_BUCKETS.get(window, WINDOW_BUCKETS["90d"])
        params: dict = {"aid": account_id, "env": Environment.coerce(environment).value}
        since_clause = ""
        if span is not None:
            params["since"] = datetime.now(timezone.utc) - span
            since_clause = "AND snapshot_at >= :since"

        rows = self._query(
            f"""
            SELECT COUNT(*)                    AS observations,
                   COUNT(DISTINCT equity)      AS distinct_values,
                   MIN(snapshot_at)            AS first_at,
                   MAX(snapshot_at)            AS last_at
            FROM equity_snapshots
            WHERE account_id = :aid
              AND COALESCE(environment, 'sandbox') = :env
              {since_clause}
            """,
            params,
        )
        base = rows[0] if rows else {}

        endpoints = self._query(
            f"""
            (SELECT equity, snapshot_at, 'first' AS edge FROM equity_snapshots
              WHERE account_id = :aid AND COALESCE(environment,'sandbox') = :env {since_clause}
              ORDER BY snapshot_at ASC LIMIT 1)
            UNION ALL
            (SELECT equity, snapshot_at, 'last' AS edge FROM equity_snapshots
              WHERE account_id = :aid AND COALESCE(environment,'sandbox') = :env {since_clause}
              ORDER BY snapshot_at DESC LIMIT 1)
            """,
            params,
        )
        edges = {row["edge"]: row for row in endpoints}
        return {
            "observations": int(base.get("observations") or 0),
            "distinct_values": int(base.get("distinct_values") or 0),
            "first_at": base.get("first_at"),
            "last_at": base.get("last_at"),
            "first_equity": float(edges["first"]["equity"]) if "first" in edges else None,
            "last_equity": float(edges["last"]["equity"]) if "last" in edges else None,
        }

    def raw_values(
        self,
        account_id: int,
        *,
        environment: Environment = Environment.SANDBOX,
        since: Optional[datetime] = None,
    ) -> list[float]:
        """Full-resolution equity for drawdown.

        Drawdown must be computed on the raw series: a bucketed series can hide
        the trough between two bucket boundaries and under-report the worst
        drawdown, which is the one number an operator cannot afford to have
        flattered.
        """
        params: dict = {"aid": account_id, "env": Environment.coerce(environment).value}
        clause = ""
        if since is not None:
            params["since"] = since
            clause = "AND snapshot_at >= :since"
        rows = self._query(
            f"""
            SELECT equity FROM equity_snapshots
            WHERE account_id = :aid
              AND COALESCE(environment, 'sandbox') = :env
              {clause}
            ORDER BY snapshot_at ASC
            """,
            params,
        )
        return [float(r["equity"]) for r in rows]

    def daily_closes(
        self,
        account_id: int,
        *,
        environment: Environment = Environment.SANDBOX,
        limit_days: int = 400,
    ) -> list[dict]:
        """One value per calendar day — the last one, not the average.

        The previous implementation used ``AVG(equity) GROUP BY DATE(snapshot_at)``,
        which both invented intraday values and defeated the index (a Seq Scan +
        Sort over 16 000 rows on every analytics call). Ordering by day and
        keeping ``DISTINCT ON`` uses ``idx_equity_snapshots_account``.
        """
        rows = self._query(
            """
            SELECT DISTINCT ON (day)
                   CAST(snapshot_at AS date) AS day,
                   equity,
                   snapshot_at
            FROM equity_snapshots
            WHERE account_id = :aid
              AND COALESCE(environment, 'sandbox') = :env
            ORDER BY day DESC, snapshot_at DESC
            LIMIT :lim
            """,
            {
                "aid": account_id,
                "env": Environment.coerce(environment).value,
                "lim": limit_days,
            },
        )
        return list(reversed(rows))

    def daily_returns(
        self,
        account_id: int,
        *,
        environment: Environment = Environment.SANDBOX,
    ) -> list[float]:
        closes = [float(r["equity"]) for r in self.daily_closes(
            account_id, environment=environment
        )]
        return [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1]
        ]

    # ── Writes. Called by the engine, never by a GET handler. ────────────────

    def record_snapshot(
        self,
        account_id: int,
        source: str,
        equity: float,
        *,
        environment: Environment = Environment.SANDBOX,
    ) -> None:
        self._execute(
            """
            INSERT INTO equity_snapshots (account_id, source, equity, environment)
            VALUES (:aid, :src, :eq, :env)
            """,
            {
                "aid": account_id,
                "src": source,
                "eq": equity,
                "env": Environment.coerce(environment).value,
            },
        )

    def last_snapshot(
        self,
        account_id: int,
        *,
        environment: Environment = Environment.SANDBOX,
    ) -> Optional[dict]:
        rows = self._query(
            """
            SELECT equity, snapshot_at FROM equity_snapshots
            WHERE account_id = :aid AND COALESCE(environment, 'sandbox') = :env
            ORDER BY snapshot_at DESC LIMIT 1
            """,
            {"aid": account_id, "env": Environment.coerce(environment).value},
        )
        return rows[0] if rows else None

    def prune_older_than(self, days: int, *, keep_daily_after_days: int = 7) -> int:
        """Retention: full resolution for `keep_daily_after_days`, one point per
        day beyond that, nothing past `days`. Returns rows removed.

        Deliberately not wired to any request path — a retention policy that runs
        on page view is how the table reached 16 000 rows in the first place.
        """
        result = self._execute(
            """
            WITH cutoff AS (
                SELECT NOW() - CAST(:days || ' days' AS interval)  AS hard,
                       NOW() - CAST(:keep || ' days' AS interval)  AS soft
            ),
            doomed AS (
                SELECT s.id
                FROM equity_snapshots s, cutoff c
                WHERE s.snapshot_at < c.hard
                UNION
                SELECT s.id
                FROM equity_snapshots s, cutoff c
                WHERE s.snapshot_at < c.soft
                  AND s.id NOT IN (
                      SELECT DISTINCT ON (account_id, CAST(snapshot_at AS date)) id
                      FROM equity_snapshots
                      ORDER BY account_id, CAST(snapshot_at AS date), snapshot_at DESC
                  )
            )
            DELETE FROM equity_snapshots WHERE id IN (SELECT id FROM doomed)
            """,
            {"days": int(days), "keep": int(keep_daily_after_days)},
        )
        return int(getattr(result, "rowcount", 0) or 0)
