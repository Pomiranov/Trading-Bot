"""Initialize platform database schema."""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from qf_platform.schema import PLATFORM_SCHEMA_SQL

logger = logging.getLogger(__name__)

_initialized = False


def ensure_platform_schema(engine: Engine | None) -> bool:
    global _initialized
    if engine is None or _initialized:
        return _initialized
    try:
        with engine.begin() as conn:
            for stmt in PLATFORM_SCHEMA_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
        _initialized = True
        logger.info("Platform schema initialized")
    except Exception as exc:
        logger.error("Platform schema init failed: %s", exc)
    return _initialized