"""Immutable security audit log — PostgreSQL-backed with graceful degradation."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from config import config
from security.request_context import get_correlation_id, get_request_id

logger = logging.getLogger(__name__)

CREATE_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_events (
    id              BIGSERIAL PRIMARY KEY,
    event_time      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type      VARCHAR(64)  NOT NULL,
    actor_type      VARCHAR(32)  NOT NULL,
    actor_id        VARCHAR(128),
    resource_type   VARCHAR(64),
    resource_id     VARCHAR(128),
    outcome         VARCHAR(16)  NOT NULL,
    client_ip       VARCHAR(64),
    correlation_id  VARCHAR(64),
    request_id      VARCHAR(64),
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_events_time ON audit_events (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_correlation ON audit_events (correlation_id);
"""


@dataclass
class AuditEvent:
    event_type: str
    actor_type: str
    outcome: str
    actor_id: str | None = None
    actor_role: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    client_ip: str | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    environment: str | None = None
    reason: str | None = None
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] | None = None


class AuditLogger:
    """Append-only trail. Never raises into the caller.

    Two changes from the original: it can be handed the application's existing
    engine instead of opening a second pool of its own (the dashboard's pool is
    five connections in total, so a private one is a real cost), and it no longer
    executes DDL. `audit_events` is declared in `qf_platform/schema.py` and
    created by `python -m qf_platform.migrate`; a logger that migrates on first
    write is a third DDL authority, which is the problem this refactor removes.
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine
        self._available = engine is not None
        self._owns_engine = False
        if engine is None:
            self._init_db()

    def attach_engine(self, engine) -> None:
        """Adopt the application's engine. Called by the app factory."""
        if engine is None:
            return
        self._engine = engine
        self._owns_engine = False
        self._available = True

    def _init_db(self) -> None:
        """Fallback for processes with no shared engine (the Telegram bot, CLI).

        Verifies reachability with a SELECT. It does not create the table: a
        missing `audit_events` is a migration problem and is reported as one.
        """
        if not config.db.password and not config.db.host:
            return
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(
                config.db.dsn,
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=1,
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM audit_events LIMIT 1"))
            self._engine = engine
            self._owns_engine = True
            self._available = True
            logger.info("Audit log storage available")
        except Exception as exc:
            logger.warning(
                "Audit log unavailable (%s). Run: python -m qf_platform.migrate",
                str(exc).splitlines()[0][:200],
            )
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def record(self, event: AuditEvent) -> None:
        event.correlation_id = event.correlation_id or get_correlation_id()
        event.request_id = event.request_id or get_request_id()

        safe_meta = event.metadata or {}
        log_line = (
            f"audit event_type={event.event_type} actor={event.actor_type}:"
            f"{event.actor_id or '-'} outcome={event.outcome} "
            f"resource={event.resource_type or '-'}:{event.resource_id or '-'}"
        )
        logger.info(log_line)

        if not self._available or self._engine is None:
            return

        try:
            from sqlalchemy import text

            with self._engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO audit_events (
                            event_time, event_type, actor_type, actor_id, actor_role,
                            resource_type, resource_id, outcome, client_ip,
                            correlation_id, request_id, environment, reason,
                            state_before, state_after, idempotency_key, metadata
                        ) VALUES (
                            :event_time, :event_type, :actor_type, :actor_id, :actor_role,
                            :resource_type, :resource_id, :outcome, :client_ip,
                            :correlation_id, :request_id, :environment, :reason,
                            CAST(:state_before AS JSONB), CAST(:state_after AS JSONB),
                            :idempotency_key, CAST(:metadata AS JSONB)
                        )
                    """),
                    {
                        "event_time": datetime.now(timezone.utc),
                        "event_type": event.event_type,
                        "actor_type": event.actor_type,
                        "actor_id": event.actor_id,
                        "actor_role": event.actor_role,
                        "resource_type": event.resource_type,
                        "resource_id": event.resource_id,
                        "outcome": event.outcome,
                        "client_ip": event.client_ip,
                        "correlation_id": event.correlation_id,
                        "request_id": event.request_id,
                        "environment": event.environment,
                        "reason": event.reason,
                        "state_before": _dump(event.state_before),
                        "state_after": _dump(event.state_after),
                        "idempotency_key": event.idempotency_key,
                        "metadata": json.dumps(safe_meta, ensure_ascii=False, default=str),
                    },
                )
        except Exception as exc:
            logger.error("Audit log write failed: %s", exc)


def _dump(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def use_engine(engine) -> None:
    """Point the audit logger at an already-open engine.

    Called by the dashboard app factory so the trail shares the application's
    connection pool instead of opening a second one against a five-connection
    budget.
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(engine=engine)
    else:
        _audit_logger.attach_engine(engine)


def audit_record(
    event_type: str,
    actor_type: str,
    outcome: str,
    *,
    actor_id: str | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    client_ip: str | None = None,
    environment: str | None = None,
    reason: str | None = None,
    state_before: dict[str, Any] | None = None,
    state_after: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    get_audit_logger().record(
        AuditEvent(
            event_type=event_type,
            actor_type=actor_type,
            outcome=outcome,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            client_ip=client_ip,
            environment=environment,
            reason=reason,
            state_before=state_before,
            state_after=state_after,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )
    )