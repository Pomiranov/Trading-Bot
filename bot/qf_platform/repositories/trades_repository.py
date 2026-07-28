"""Trade and position access, with the environment attached to every row.

Two physical tables hold trades and they are not interchangeable:

* ``paper_trades`` — 35 rows, the simulated account's closed trades. This is
  what the account's realised PnL and win rate are actually made of.
* ``trades`` — 2 rows, the learning system's richer record (46 columns:
  ``strategy_id``, ``decision_quality``, ``pnl_r``, ``market_regime``).

The old UI computed win rate and profit factor from ``trades`` (n=2) and the
balance from ``paper_trades`` (n=35), under one source badge. Here each query
names its table, returns its own ``n``, and carries an ``environment`` on every
row so a sandbox result can never be read as a live one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from qf_platform.environment import Environment
from qf_platform.repositories.base import BaseRepository

#: Named periods → lower bound. `None` means "everything".
PERIODS: dict[str, Optional[timedelta]] = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
    "all": None,
}

SORTABLE_TRADE_COLUMNS = {
    "closed_at", "opened_at", "ticker", "pnl", "pnl_pct", "quantity",
    "entry_price", "exit_price", "commission", "direction",
}


def period_since(period: str) -> Optional[datetime]:
    span = PERIODS.get(period, PERIODS["30d"])
    return None if span is None else datetime.now(timezone.utc) - span


class TradesRepository(BaseRepository):
    # ── Paper trades — the simulated account's own history ───────────────────

    def paper_trades(
        self,
        account_id: int,
        *,
        period: str = "30d",
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        result: Optional[str] = None,
        environment: Optional[Environment] = None,
        sort: str = "closed_at",
        descending: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        clauses = ["account_id = :aid"]
        params: dict = {"aid": account_id, "lim": limit, "off": offset}

        since = period_since(period)
        if since is not None:
            clauses.append("closed_at >= :since")
            params["since"] = since
        if ticker:
            clauses.append("ticker = :ticker")
            params["ticker"] = ticker.upper()
        if direction:
            clauses.append("LOWER(direction) = :dir")
            params["dir"] = direction.lower()
        if result == "win":
            clauses.append("pnl > 0")
        elif result == "loss":
            clauses.append("pnl < 0")
        elif result == "flat":
            clauses.append("pnl = 0")
        if environment is not None:
            clauses.append("COALESCE(environment, 'sandbox') = :env")
            params["env"] = Environment.coerce(environment).value

        order_column = sort if sort in SORTABLE_TRADE_COLUMNS else "closed_at"
        direction_sql = "DESC" if descending else "ASC"

        return self._query(
            f"""
            SELECT id, ticker, exchange, direction, entry_price, exit_price,
                   quantity, pnl, pnl_pct, commission, slippage, close_reason,
                   entry_reason, opened_at, closed_at,
                   COALESCE(environment, 'sandbox') AS environment,
                   EXTRACT(EPOCH FROM (closed_at - opened_at)) AS duration_seconds
            FROM paper_trades
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_column} {direction_sql} NULLS LAST, id DESC
            LIMIT :lim OFFSET :off
            """,
            params,
        )

    def paper_trades_count(
        self,
        account_id: int,
        *,
        period: str = "30d",
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        result: Optional[str] = None,
        environment: Optional[Environment] = None,
    ) -> int:
        """Total matching the same filters — so the client can show «N из M»
        rather than silently truncating at the page size."""
        clauses = ["account_id = :aid"]
        params: dict = {"aid": account_id}
        since = period_since(period)
        if since is not None:
            clauses.append("closed_at >= :since")
            params["since"] = since
        if ticker:
            clauses.append("ticker = :ticker")
            params["ticker"] = ticker.upper()
        if direction:
            clauses.append("LOWER(direction) = :dir")
            params["dir"] = direction.lower()
        if result == "win":
            clauses.append("pnl > 0")
        elif result == "loss":
            clauses.append("pnl < 0")
        elif result == "flat":
            clauses.append("pnl = 0")
        if environment is not None:
            clauses.append("COALESCE(environment, 'sandbox') = :env")
            params["env"] = Environment.coerce(environment).value

        rows = self._query(
            f"SELECT COUNT(*) AS n FROM paper_trades WHERE {' AND '.join(clauses)}",
            params,
        )
        return int(rows[0]["n"]) if rows else 0

    def paper_pnl_values(
        self,
        account_id: int,
        *,
        period: str = "all",
        environment: Optional[Environment] = None,
    ) -> list[dict]:
        """`pnl` and `pnl_pct` for every matching trade.

        Aggregates are computed in Python from this list rather than in SQL, so
        one place decides what "average profit" means. The old code shipped
        ``AVG(ABS(pnl_pct))`` and reported +16,07 % on an account that had lost
        ₽2 373 454 across 35 trades with zero wins.
        """
        clauses = ["account_id = :aid"]
        params: dict = {"aid": account_id}
        since = period_since(period)
        if since is not None:
            clauses.append("closed_at >= :since")
            params["since"] = since
        if environment is not None:
            clauses.append("COALESCE(environment, 'sandbox') = :env")
            params["env"] = Environment.coerce(environment).value

        return self._query(
            f"""
            SELECT pnl, pnl_pct, commission, closed_at, opened_at, ticker
            FROM paper_trades
            WHERE {' AND '.join(clauses)}
            ORDER BY closed_at ASC
            """,
            params,
        )

    def paper_pnl_periods(self, account_id: int) -> dict:
        """Day / week / month / total realised PnL plus the closed count.

        ``closed_at >= CURRENT_DATE`` is intentional and matches the account's
        own session boundary; the timezone policy is declared once in
        ``contracts.DISPLAY_TZ`` and the database runs in UTC, so this is a UTC
        day. The window is reported in `meta.window` rather than left implicit.
        """
        rows = self._query(
            """
            SELECT
                COALESCE(SUM(pnl) FILTER (WHERE closed_at >= CURRENT_DATE), 0) AS pnl_day,
                COUNT(*)          FILTER (WHERE closed_at >= CURRENT_DATE)     AS n_day,
                COALESCE(SUM(pnl) FILTER (WHERE closed_at >= CURRENT_DATE - INTERVAL '7 days'), 0)  AS pnl_week,
                COUNT(*)          FILTER (WHERE closed_at >= CURRENT_DATE - INTERVAL '7 days')      AS n_week,
                COALESCE(SUM(pnl) FILTER (WHERE closed_at >= CURRENT_DATE - INTERVAL '30 days'), 0) AS pnl_month,
                COUNT(*)          FILTER (WHERE closed_at >= CURRENT_DATE - INTERVAL '30 days')     AS n_month,
                COALESCE(SUM(pnl), 0)        AS realized_pnl,
                COALESCE(SUM(commission), 0) AS commission_total,
                COUNT(*)                     AS closed_count
            FROM paper_trades WHERE account_id = :aid
            """,
            {"aid": account_id},
        )
        return rows[0] if rows else {}

    def paper_trade_tickers(self, account_id: int) -> list[str]:
        return [r["ticker"] for r in self._query(
            "SELECT DISTINCT ticker FROM paper_trades WHERE account_id = :aid ORDER BY ticker",
            {"aid": account_id},
        )]

    # ── Learning trades — richer schema, tiny population ─────────────────────

    def learning_trades(
        self,
        *,
        limit: int = 100,
        environment: Optional[Environment] = None,
        strategy_id: Optional[str] = None,
        closed_only: bool = True,
    ) -> list[dict]:
        clauses = ["1=1"]
        params: dict = {"lim": limit}
        if closed_only:
            clauses.append("closed_at IS NOT NULL")
        if strategy_id:
            clauses.append("strategy_id = :sid")
            params["sid"] = strategy_id
        if environment is not None:
            env = Environment.coerce(environment)
            clauses.append(
                "COALESCE(environment, CASE WHEN is_sandbox IS TRUE THEN 'sandbox'"
                " WHEN is_sandbox IS FALSE THEN 'live' END) = :env"
            )
            params["env"] = env.value

        return self._query(
            f"""
            SELECT trade_id, id, ticker, strategy_id, direction, timeframe,
                   market_regime, entry_price, exit_price, stop_loss, take_profit,
                   quantity, position_size, pnl, pnl_pct, pnl_r, commission,
                   confidence, decision_quality, randomness_factor,
                   strategy_followed, exit_reason_type, exit_reason, entry_reason,
                   opened_at, closed_at, is_sandbox,
                   COALESCE(environment,
                            CASE WHEN is_sandbox IS TRUE  THEN 'sandbox'
                                 WHEN is_sandbox IS FALSE THEN 'live' END) AS environment
            FROM trades
            WHERE {' AND '.join(clauses)}
            ORDER BY closed_at DESC NULLS LAST, opened_at DESC
            LIMIT :lim
            """,
            params,
        )

    def learning_trades_count(self, *, environment: Optional[Environment] = None) -> int:
        clauses = ["closed_at IS NOT NULL"]
        params: dict = {}
        if environment is not None:
            clauses.append(
                "COALESCE(environment, CASE WHEN is_sandbox IS TRUE THEN 'sandbox'"
                " WHEN is_sandbox IS FALSE THEN 'live' END) = :env"
            )
            params["env"] = Environment.coerce(environment).value
        rows = self._query(
            f"SELECT COUNT(*) AS n FROM trades WHERE {' AND '.join(clauses)}", params
        )
        return int(rows[0]["n"]) if rows else 0

    def environment_census(self) -> list[dict]:
        """How many trades sit in each environment, including unlabelled ones.

        Surfacing UNKNOWN is the point: a row whose provenance cannot be
        established is a configuration fault and must be visible as one.
        """
        return self._query(
            """
            SELECT COALESCE(environment,
                            CASE WHEN is_sandbox IS TRUE  THEN 'sandbox'
                                 WHEN is_sandbox IS FALSE THEN 'live'
                                 ELSE 'unknown' END) AS environment,
                   COUNT(*) AS n
            FROM trades
            GROUP BY 1
            ORDER BY n DESC
            """
        )

    # ── Open positions ───────────────────────────────────────────────────────

    def open_paper_positions(
        self,
        account_id: int,
        *,
        environment: Optional[Environment] = None,
    ) -> list[dict]:
        clauses = ["p.account_id = :aid"]
        params: dict = {"aid": account_id}
        if environment is not None:
            clauses.append("COALESCE(p.environment, 'sandbox') = :env")
            params["env"] = Environment.coerce(environment).value

        return self._query(
            f"""
            SELECT p.id, p.ticker, p.exchange, p.direction, p.quantity,
                   p.entry_price, p.stop_loss, p.take_profit, p.unrealized_pnl,
                   p.trailing_stop_pct, p.signal_id, p.entry_reason, p.opened_at,
                   COALESCE(p.environment, 'sandbox') AS environment,
                   t.strategy_id
            FROM paper_positions p
            LEFT JOIN LATERAL (
                SELECT strategy_id FROM trading_signals
                WHERE id = p.signal_id LIMIT 1
            ) t ON true
            WHERE {' AND '.join(clauses)}
            ORDER BY p.opened_at DESC
            """,
            params,
        )

    def account(self, account_id: int) -> Optional[dict]:
        rows = self._query(
            """
            SELECT id, user_id, mode, initial_balance, balance, available_balance,
                   margin_used, currency, created_at, updated_at,
                   COALESCE(environment, 'sandbox') AS environment
            FROM paper_accounts WHERE id = :id
            """,
            {"id": account_id},
        )
        return rows[0] if rows else None

    def accounts(self) -> list[dict]:
        return self._query(
            """
            SELECT id, user_id, mode, initial_balance, balance, available_balance,
                   margin_used, currency, updated_at,
                   COALESCE(environment, 'sandbox') AS environment
            FROM paper_accounts ORDER BY id
            """
        )

    def default_account_id(self, mode: str = "rub", user_id: str = "default") -> Optional[int]:
        """Existing account only — never creates one.

        ``get_or_create_account`` on a read path is a GET that writes. The
        create path lives in ``PaperRepository`` and is reached from the engine
        and from explicit operator actions.
        """
        rows = self._query(
            "SELECT id FROM paper_accounts WHERE user_id = :uid AND mode = :mode",
            {"uid": user_id, "mode": mode},
        )
        return int(rows[0]["id"]) if rows else None
