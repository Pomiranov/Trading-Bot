"""Request / correlation ID propagation via contextvars."""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def _new_id() -> str:
    return uuid.uuid4().hex


def set_correlation_id(value: str) -> str:
    _correlation_id.set(value)
    return value


def get_correlation_id() -> str:
    value = _correlation_id.get()
    if value is None:
        value = _new_id()
        _correlation_id.set(value)
    return value


def set_request_id(value: str) -> str:
    _request_id.set(value)
    return value


def get_request_id() -> str:
    value = _request_id.get()
    if value is None:
        value = _new_id()
        _request_id.set(value)
    return value


def bind_ids(
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> tuple[str, str]:
    rid = set_request_id(request_id or _new_id())
    cid = set_correlation_id(correlation_id or rid)
    return rid, cid


class RequestContextFilter(logging.Filter):
    """Inject correlation_id and request_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        record.request_id = get_request_id()
        return True