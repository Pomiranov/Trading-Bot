"""Schema bootstrap — kept for compatibility, but no longer able to surprise you.

Previously ``ensure_platform_schema(engine)`` ran the whole DDL script in one
transaction and was called at *import time* by ``bot/ui/dashboard.py``. Starting
the web server was therefore a migration; one bad statement rolled back the
other forty; and the failure surfaced as four endpoints returning HTTP 500 with
a clean browser console.

The function now refuses to execute DDL unless the caller passes
``allow_ddl=True`` — which only ``qf_platform.migrate`` and the tests do.
Ordinary callers get a read-only verification instead. Statement splitting,
per-statement transactions and the version ledger live in ``qf_platform.migrate``
so there is exactly one implementation.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_verified: bool = False

#: Escape hatch for a deployment that genuinely wants boot-time migration.
#: Off by default, and the log line says loudly what it did.
_ENV_ALLOW = "QF_ALLOW_STARTUP_DDL"


def startup_ddl_allowed() -> bool:
    return os.getenv(_ENV_ALLOW, "0") == "1"


def ensure_platform_schema(engine, *, allow_ddl: bool = False) -> bool:
    """Verify the schema; migrate only when explicitly permitted.

    Returns ``True`` when the schema satisfies everything the dashboard reads.
    Never raises — a stale schema must produce a structured
    ``SCHEMA_OUT_OF_DATE`` response, not a traceback at import.
    """
    global _verified

    if engine is None:
        return False

    from qf_platform.migrate import apply_schema, verify_schema

    report = verify_schema(engine)
    if report.current:
        _verified = True
        return True

    if not (allow_ddl or startup_ddl_allowed()):
        logger.error(
            "Схема БД устарела и НЕ будет миграцирована автоматически: %s. "
            "Выполните: python -m qf_platform.migrate",
            report.describe(),
        )
        _verified = False
        return False

    logger.warning(
        "Выполняется миграция схемы при старте (%s=1): %s",
        _ENV_ALLOW, report.describe(),
    )
    result = apply_schema(engine, applied_by="startup")
    for index, summary, message in result.failures:
        logger.error("DDL #%d не выполнен: %s → %s", index, summary, message)

    _verified = verify_schema(engine).current
    if _verified:
        logger.info("Platform schema initialized (%d statements)", result.applied)
    return _verified


def schema_verified() -> bool:
    """Whether the last verification succeeded. Read by the API layer so a stale
    schema is reported once, consistently, instead of as N random 500s."""
    return _verified


def schema_report(engine) -> Optional[object]:
    from qf_platform.migrate import verify_schema

    return verify_schema(engine) if engine is not None else None
