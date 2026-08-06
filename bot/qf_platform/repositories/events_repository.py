"""News, system events and the audit trail.

``system_events`` had a schema and zero rows: nothing wrote to it, so "what went
wrong?" had no data behind it and four endpoints could return HTTP 500 with a
clean browser console. ``log_event`` is now called from the error handler, the
signal gate, the engine lifecycle and every operator action, so the Event Log
screen reads real rows.

``log_event`` keeps its original positional signature so existing callers keep
working; the new arguments are keyword-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from qf_platform.environment import Environment
from qf_platform.repositories.base import BaseRepository

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL")


class EventCategory:
    """Coarse grouping, so the log can be filtered by *what happened* rather
    than by which module happened to log it."""

    ENGINE = "engine"
    GATE = "gate"
    TRADE = "trade"
    BROKER = "broker"
    DATA = "data"
    AUTH = "auth"
    API = "api"
    SCHEMA = "schema"
    OPERATOR = "operator"
    SYSTEM = "system"


class EventsRepository(BaseRepository):
    # ── system_events ────────────────────────────────────────────────────────

    def log_event(
        self,
        level: str,
        source: str,
        message: str,
        metadata: dict | None = None,
        *,
        category: str = EventCategory.SYSTEM,
        correlation_id: Optional[str] = None,
        environment: Optional[Environment] = None,
    ) -> None:
        """Write one event. Never raises.

        An event-log write that could fail a request would turn observability
        into an outage. Failures fall back to the application logger.
        """
        try:
            self._execute(
                """
                INSERT INTO system_events
                    (level, source, message, category, metadata, correlation_id, environment)
                VALUES (:level, :source, :message, :category,
                        CAST(:meta AS JSONB), :cid, :env)
                """,
                {
                    "level": (level or "INFO").upper()[:16],
                    "source": (source or "unknown")[:64],
                    "message": message,
                    "category": (category or EventCategory.SYSTEM)[:32],
                    "meta": json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    "cid": correlation_id[:64] if correlation_id else None,
                    "env": Environment.coerce(environment).value if environment else None,
                },
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "system_events write failed: [%s] %s: %s", level, source, message
            )

    def list_events(
        self,
        *,
        limit: int = 100,
        levels: Optional[list[str]] = None,
        source: Optional[str] = None,
        category: Optional[str] = None,
        correlation_id: Optional[str] = None,
        environment: Optional[Environment] = None,
        since: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        clauses = ["1=1"]
        params: dict = {"lim": limit}
        if levels:
            clauses.append("level = ANY(:levels)")
            params["levels"] = [lvl.upper() for lvl in levels]
        if source:
            clauses.append("source = :source")
            params["source"] = source
        if category:
            clauses.append("category = :category")
            params["category"] = category
        if correlation_id:
            clauses.append("correlation_id = :cid")
            params["cid"] = correlation_id
        if environment is not None:
            clauses.append("COALESCE(environment, 'sandbox') = :env")
            params["env"] = Environment.coerce(environment).value
        if since is not None:
            clauses.append("created_at >= :since")
            params["since"] = since
        if search:
            # Parameterised LIKE — the pattern is a bound value, never concatenated.
            clauses.append("message ILIKE :search")
            params["search"] = f"%{search}%"

        return self._query(
            f"""
            SELECT id, created_at, level, source, COALESCE(category, 'system') AS category,
                   message, metadata, correlation_id, environment
            FROM system_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT :lim
            """,
            params,
        )

    def count_events(
        self,
        *,
        levels: Optional[list[str]] = None,
        since: Optional[datetime] = None,
    ) -> int:
        clauses = ["1=1"]
        params: dict = {}
        if levels:
            clauses.append("level = ANY(:levels)")
            params["levels"] = [lvl.upper() for lvl in levels]
        if since is not None:
            clauses.append("created_at >= :since")
            params["since"] = since
        rows = self._query(
            f"SELECT COUNT(*) AS n FROM system_events WHERE {' AND '.join(clauses)}", params
        )
        return int(rows[0]["n"]) if rows else 0

    def level_census(self, *, hours: int = 24) -> list[dict]:
        return self._query(
            """
            SELECT level, COUNT(*) AS n
            FROM system_events
            WHERE created_at >= NOW() - CAST(:hours || ' hours' AS interval)
            GROUP BY level
            """,
            {"hours": int(hours)},
        )

    def distinct_sources(self, *, limit: int = 40) -> list[str]:
        return [r["source"] for r in self._query(
            "SELECT DISTINCT source FROM system_events ORDER BY source LIMIT :lim",
            {"lim": limit},
        )]

    def recent_errors(self, limit: int = 10) -> list[dict]:
        return self._query(
            """
            SELECT created_at, level, source, message, correlation_id
            FROM system_events
            WHERE level IN ('ERROR', 'WARN', 'CRITICAL')
            ORDER BY created_at DESC LIMIT :limit
            """,
            {"limit": limit},
        )

    def recent_events(self, limit: int = 30) -> list[dict]:
        return self._query(
            """
            SELECT created_at, level, source, message
            FROM system_events ORDER BY created_at DESC LIMIT :limit
            """,
            {"limit": limit},
        )

    # ── audit_events ─────────────────────────────────────────────────────────

    def list_audit(
        self,
        *,
        limit: int = 100,
        event_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        outcome: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        clauses = ["1=1"]
        params: dict = {"lim": limit}
        if event_type:
            clauses.append("event_type = :etype")
            params["etype"] = event_type
        if actor_id:
            clauses.append("actor_id = :actor")
            params["actor"] = actor_id
        if outcome:
            clauses.append("outcome = :outcome")
            params["outcome"] = outcome
        if since is not None:
            clauses.append("event_time >= :since")
            params["since"] = since

        return self._query(
            f"""
            SELECT id, event_time, event_type, actor_type, actor_id, actor_role,
                   resource_type, resource_id, outcome, environment, reason,
                   state_before, state_after, idempotency_key,
                   client_ip, correlation_id, request_id, metadata
            FROM audit_events
            WHERE {' AND '.join(clauses)}
            ORDER BY event_time DESC, id DESC
            LIMIT :lim
            """,
            params,
        )

    def audit_type_census(self, *, days: int = 30) -> list[dict]:
        return self._query(
            """
            SELECT event_type, outcome, COUNT(*) AS n
            FROM audit_events
            WHERE event_time >= NOW() - CAST(:days || ' days' AS interval)
            GROUP BY event_type, outcome
            ORDER BY n DESC
            """,
            {"days": int(days)},
        )

    # ── news ─────────────────────────────────────────────────────────────────

    def list_news(self, limit: int = 20) -> list[dict]:
        return self._query(
            """
            SELECT published_at, source, title, sentiment, importance, url
            FROM news ORDER BY published_at DESC LIMIT :limit
            """,
            {"limit": limit},
        )

    def news_count(self) -> int:
        rows = self._query("SELECT COUNT(*) AS cnt FROM news")
        return int(rows[0]["cnt"]) if rows else 0

    # ── forward / live runner heartbeat ──────────────────────────────────────

    def runner_states(self) -> list[dict]:
        return self._query(
            """
            SELECT strategy_id, ticker, last_candle_time, heartbeat_at, updated_at,
                   COALESCE(status, 'unknown') AS status, detail,
                   COALESCE(environment, 'forward') AS environment
            FROM forward_state
            ORDER BY COALESCE(heartbeat_at, updated_at) DESC NULLS LAST
            """
        )

    def record_runner_heartbeat(
        self,
        *,
        strategy_id: str,
        ticker: str,
        last_candle_time: datetime,
        status: str = "healthy",
        detail: Optional[str] = None,
        environment: Environment = Environment.FORWARD,
    ) -> None:
        try:
            self._execute(
                """
                INSERT INTO forward_state
                    (strategy_id, ticker, last_candle_time, status, detail,
                     environment, heartbeat_at, updated_at)
                VALUES (:sid, :ticker, :candle, :status, :detail, :env, NOW(), NOW())
                ON CONFLICT (strategy_id, ticker) DO UPDATE
                   SET last_candle_time = :candle, status = :status, detail = :detail,
                       environment = :env, heartbeat_at = NOW(), updated_at = NOW()
                """,
                {
                    "sid": strategy_id[:50],
                    "ticker": ticker.upper()[:20],
                    "candle": last_candle_time,
                    "status": status[:24],
                    "detail": detail,
                    "env": Environment.coerce(environment).value,
                },
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "forward_state heartbeat failed for %s/%s", strategy_id, ticker
            )

    @staticmethod
    def window_since(hours: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(hours=hours)
