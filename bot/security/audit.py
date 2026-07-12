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
    resource_type: str | None = None
    resource_id: str | None = None
    client_ip: str | None = None
    correlation_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] | None = None


class AuditLogger:
    def __init__(self) -> None:
        self._engine = None
        self._available = False
        self._init_db()

    def _init_db(self) -> None:
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
            with engine.begin() as conn:
                for stmt in CREATE_AUDIT_TABLE_SQL.split(";"):
                    stripped = stmt.strip()
                    if stripped:
                        conn.execute(text(stripped))
            self._engine = engine
            self._available = True
            logger.info("Audit log storage initialized")
        except Exception as exc:
            logger.warning("Audit log DB unavailable: %s", exc)
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
                            event_time, event_type, actor_type, actor_id,
                            resource_type, resource_id, outcome, client_ip,
                            correlation_id, request_id, metadata
                        ) VALUES (
                            :event_time, :event_type, :actor_type, :actor_id,
                            :resource_type, :resource_id, :outcome, :client_ip,
                            :correlation_id, :request_id, CAST(:metadata AS JSONB)
                        )
                    """),
                    {
                        "event_time": datetime.now(timezone.utc),
                        "event_type": event.event_type,
                        "actor_type": event.actor_type,
                        "actor_id": event.actor_id,
                        "resource_type": event.resource_type,
                        "resource_id": event.resource_id,
                        "outcome": event.outcome,
                        "client_ip": event.client_ip,
                        "correlation_id": event.correlation_id,
                        "request_id": event.request_id,
                        "metadata": json.dumps(safe_meta, ensure_ascii=False),
                    },
                )
        except Exception as exc:
            logger.error("Audit log write failed: %s", exc)


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_record(
    event_type: str,
    actor_type: str,
    outcome: str,
    *,
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    client_ip: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    get_audit_logger().record(
        AuditEvent(
            event_type=event_type,
            actor_type=actor_type,
            outcome=outcome,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            client_ip=client_ip,
            metadata=metadata,
        )
    )