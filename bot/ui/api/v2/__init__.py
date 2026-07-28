"""``/api/v2`` — the contract layer.

Routes here are thin by rule: they parse and validate query parameters, call one
service, and wrap the result in the envelope. There is no SQL, no financial
arithmetic and no branching on data shape in this package. That is what makes
"one metric, one authoritative calculation" enforceable rather than aspirational.

``/api/v1`` (the legacy ``/api/*`` and ``/api/platform/*`` routes) stays in place
for the Telegram Mini App and the bot process, with its GETs made read-only. The
operational dashboard talks only to v2.
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, g, request

from qf_platform.contracts import ApiError, ErrorCode, Meta, clamp_limit, envelope
from qf_platform.environment import Environment
from security.guards import require_auth
from security.permissions import Permission

logger = logging.getLogger(__name__)

v2 = Blueprint("v2", __name__, url_prefix="/api/v2")

#: Injected once by the app factory. Routes never construct an engine.
_engine = None
_schema_ok = True


def init_v2(engine, *, schema_ok: bool = True) -> Blueprint:
    global _engine, _schema_ok
    _engine = engine
    _schema_ok = schema_ok

    # Import for side effects: each module registers its routes on `v2`.
    from . import routes_actions, routes_read  # noqa: F401

    return v2


def engine_or_fail():
    """Every data route calls this first.

    Two distinct failures, two distinct codes: no database at all, versus a
    database whose schema predates what the dashboard reads. Collapsing them into
    a generic 500 is how «четыре панели вечно грузятся» happened.
    """
    if _engine is None:
        raise ApiError(ErrorCode.DB_UNAVAILABLE)
    if not _schema_ok:
        raise ApiError(
            ErrorCode.SCHEMA_OUT_OF_DATE,
            detail="Выполните: python -m qf_platform.migrate",
        )
    return _engine


def engine_unchecked():
    """For routes that must answer even under schema drift (health, environment)."""
    return _engine


def schema_is_current() -> bool:
    return _schema_ok


# ── Query-parameter parsing ───────────────────────────────────────────────────

_ENVIRONMENTS = {e.value for e in Environment}
_PERIODS = {"1d", "7d", "30d", "90d", "1y", "all"}
_WINDOWS = {"1d", "7d", "30d", "90d", "1y", "all"}
_RESULTS = {"win", "loss", "flat"}
_DIRECTIONS = {"long", "short", "buy", "sell"}


def arg_environment(default: Environment = Environment.SANDBOX) -> Environment:
    """Environment from the query string.

    An unrecognised value is a validation error, not a silent fallback to
    sandbox: quietly answering a different question than the one asked is exactly
    how a live number lands on a sandbox screen.
    """
    raw = (request.args.get("environment") or "").strip().lower()
    if not raw:
        return default
    if raw not in _ENVIRONMENTS:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="environment")
    resolved = Environment.coerce(raw)
    if resolved is Environment.UNKNOWN and raw != Environment.UNKNOWN.value:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="environment")
    return resolved


def arg_choice(name: str, allowed: set[str], default: Optional[str]) -> Optional[str]:
    raw = (request.args.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw not in allowed:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name=name)
    return raw


def arg_period(default: str = "30d") -> str:
    return arg_choice("period", _PERIODS, default)


def arg_window(default: str = "90d") -> str:
    return arg_choice("window", _WINDOWS, default)


def arg_result() -> Optional[str]:
    return arg_choice("result", _RESULTS, None)


def arg_direction() -> Optional[str]:
    return arg_choice("direction", _DIRECTIONS, None)


def arg_limit(default: int = 100, maximum: int = 1000) -> int:
    return clamp_limit(request.args.get("limit"), default, maximum)


def arg_offset() -> int:
    try:
        return max(0, int(request.args.get("offset") or 0))
    except (TypeError, ValueError):
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="offset")


def arg_ticker() -> Optional[str]:
    raw = (request.args.get("ticker") or "").strip().upper()
    if not raw:
        return None
    # Tickers are identifiers, not free text: constrain the shape rather than
    # trusting a LIKE pattern built from user input.
    if len(raw) > 24 or not raw.replace(".", "").replace("-", "").isalnum():
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="ticker")
    return raw


def arg_strategy() -> Optional[str]:
    raw = (request.args.get("strategy_id") or "").strip()
    if not raw:
        return None
    if len(raw) > 50:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="strategy_id")
    return raw


def arg_flag(name: str, default: bool = False) -> bool:
    raw = (request.args.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def arg_sort(allowed: set[str], default: str) -> tuple[str, bool]:
    """`(column, descending)` from ``sort=-closed_at`` style input."""
    raw = (request.args.get("sort") or "").strip()
    if not raw:
        return default, True
    descending = raw.startswith("-")
    column = raw.lstrip("-+")
    if column not in allowed:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="sort")
    return column, descending


def remember_environment(environment: Environment) -> None:
    """Stash the resolved environment so the audit row records which environment
    an action ran against."""
    g.qf_environment = environment


__all__ = [
    "v2", "init_v2", "engine_or_fail", "engine_unchecked", "schema_is_current",
    "envelope", "Meta", "require_auth", "Permission",
    "arg_environment", "arg_period", "arg_window", "arg_limit", "arg_offset",
    "arg_ticker", "arg_strategy", "arg_result", "arg_direction", "arg_choice",
    "arg_flag", "arg_sort", "remember_environment",
]
