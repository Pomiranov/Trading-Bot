"""Read-only launch mode — the safe way to look at real data.

``QF_DASHBOARD_READ_ONLY=1`` gives an operator (or a QA pass, or this
implementation's own verification) a dashboard that reads production data and
cannot change anything:

* every mutating endpoint returns ``READ_ONLY_MODE`` before it reaches a service;
* no engine thread starts;
* no migration runs;
* no broker command is issued;
* the SQLAlchemy engine itself rejects writes, so a mistake in a service cannot
  become a write.

That last point matters. A flag checked in the HTTP layer protects only the paths
someone remembered to check. A guard on the connection protects the ones they
did not — which, given that four GET handlers were inserting rows, is the failure
mode that actually happened here.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

_ENV_FLAG = "QF_DASHBOARD_READ_ONLY"

#: Statement kinds that mutate. Matched on the first keyword of the statement,
#: so a SELECT whose text happens to contain the word "update" is unaffected.
_WRITE_PREFIXES = (
    "insert", "update", "delete", "truncate", "drop", "alter", "create",
    "grant", "revoke", "comment", "reindex", "vacuum", "refresh", "copy",
)

_LEADING_NOISE = re.compile(r"^(?:\s|--[^\n]*\n|/\*.*?\*/)+", re.DOTALL)

#: Tables that read-only mode still permits writing to, and why.
#:
#: "Read-only" is a promise about **domain** data: no trade, position, account,
#: equity snapshot, signal, belief or backtest may change. It is not a promise
#: that the process writes zero bytes — and it must not be, because the mode
#: exists so an operator can *log in and look*, and logging in creates a session.
#:
#: Each entry below is session or observability bookkeeping. Nothing here can
#: alter a number the dashboard displays. The domain tables are absent from this
#: set and therefore hard-blocked, and `@mutating` independently refuses every
#: state-changing endpoint, so this allowlist cannot become a bypass.
_ALLOWED_WRITE_TABLES = frozenset({
    "dashboard_sessions",        # login/logout must work
    "dashboard_login_attempts",  # the rate limiter's storage
    "dashboard_users",           # lockout counters and last_login_at only
    "audit_events",              # an audit trail that stops in QA mode is useless
    "system_events",             # so a read-only pass still records what it saw
    "action_idempotency",        # reservations released on refusal
})

#: Table name in a write statement: INSERT INTO x, UPDATE x, DELETE FROM x.
_TARGET_TABLE = re.compile(
    r"\b(?:insert\s+into|update|delete\s+from)\s+(?:only\s+)?\"?([a-z_][a-z0-9_$]*)\"?",
    re.IGNORECASE,
)


def _targets_only_allowed_tables(sql: str) -> bool:
    """True when every write target in the statement is on the allowlist."""
    targets = {name.lower() for name in _TARGET_TABLE.findall(sql or "")}
    return bool(targets) and targets.issubset(_ALLOWED_WRITE_TABLES)


class ReadOnlyViolation(RuntimeError):
    """A write was attempted while the dashboard is in read-only mode."""


def read_only_enabled() -> bool:
    return os.getenv(_ENV_FLAG, "0") == "1"


def engine_threads_allowed() -> bool:
    """Auto-starting the trading engine inside the web process is opt-in.

    It used to happen at module import: ``paper_engine.start()`` ran as a side
    effect of importing ``bot/ui/dashboard.py``, so merely importing the app for
    a test began placing simulated trades.
    """
    if read_only_enabled():
        return False
    return os.getenv("QF_DASHBOARD_AUTOSTART_ENGINE", "0") == "1"


def is_write_statement(sql: str) -> bool:
    text = _LEADING_NOISE.sub("", sql or "").lstrip("(").lstrip()
    lowered = text[:400].lower()

    # A CTE can hide a write in its tail: WITH x AS (...) DELETE FROM ...
    if lowered.startswith("with"):
        return any(
            re.search(rf"\b{kw}\b", lowered) for kw in ("insert", "update", "delete", "merge")
        )

    first = lowered.split(None, 1)[0] if lowered else ""
    if first in _WRITE_PREFIXES:
        return True
    # SELECT ... FOR UPDATE takes row locks; not a mutation, but not read-only
    # either, and it has no place on a viewing path.
    return "for update" in lowered or "for no key update" in lowered


def install_engine_guard(engine) -> None:
    """Reject write statements at the connection level.

    Uses SQLAlchemy's ``before_cursor_execute`` so the check sits below every
    repository, service and route. Installed only when the flag is on, so normal
    operation pays nothing for it.
    """
    if engine is None or not read_only_enabled():
        return

    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def _block_writes(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if not is_write_statement(statement):
            return
        if _targets_only_allowed_tables(statement):
            return
        first_line = (statement or "").strip().splitlines()[0][:160]
        logger.error("READ-ONLY: заблокирована запись: %s", first_line)
        raise ReadOnlyViolation(
            "Дашборд запущен в режиме только для чтения — запись заблокирована."
        )

    logger.warning(
        "%s=1 — режим только для чтения: доменные данные (сделки, позиции, счёт, "
        "equity, сигналы, стратегии) неизменяемы; движок не запускается; миграции "
        "не выполняются. Разрешены только сессии и журналы: %s.",
        _ENV_FLAG, ", ".join(sorted(_ALLOWED_WRITE_TABLES)),
    )


def describe() -> dict:
    """Surfaced in `/api/v2/environment` so the UI can explain why an action is
    disabled instead of just greying it out."""
    return {
        "read_only": read_only_enabled(),
        "engine_autostart": engine_threads_allowed(),
        "flag": _ENV_FLAG,
        "writable_infrastructure_tables": sorted(_ALLOWED_WRITE_TABLES),
    }
