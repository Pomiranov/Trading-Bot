"""One error envelope for the whole API.

Before: five conventions in one codebase. Sixteen blueprint routes had no
``try/except`` and returned an HTML 500 — Werkzeug traceback included, if debug
was ever on — to a JSON client. Seven routes swallowed every exception and
returned ``200 []``, which is worse: the client cannot tell "no trades" from
"the database is down", so an outage renders as an empty panel and the operator
reads it as "nothing happened today".

After: every failure is

    {"error": {"code": "...", "message": "...", "id": "<correlation-id>"}}

with an HTTP status from the code. The message is picked from a fixed table of
safe Russian strings; SQL, stack traces, credentials and filesystem paths never
reach the client. The correlation id does reach the client, so an operator can
quote it and the matching row can be found in ``system_events``.
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Flask, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from qf_platform.contracts import ApiError, ErrorCode, error_envelope
from security.readonly import ReadOnlyViolation
from security.request_context import get_correlation_id

logger = logging.getLogger(__name__)

#: HTTP status → contract code, for errors Werkzeug raises before we see them.
_HTTP_TO_CODE = {
    400: ErrorCode.VALIDATION_FAILED,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.VALIDATION_FAILED,
    408: ErrorCode.UPSTREAM_TIMEOUT,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.VALIDATION_FAILED,
    415: ErrorCode.VALIDATION_FAILED,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.INTERNAL,
    501: ErrorCode.NOT_IMPLEMENTED,
    502: ErrorCode.BROKER_UNAVAILABLE,
    503: ErrorCode.DB_UNAVAILABLE,
    504: ErrorCode.UPSTREAM_TIMEOUT,
}

#: Set by the app factory so failures can be written to the event log.
_events_sink = None


def set_events_sink(repository) -> None:
    """Give the handler somewhere to record failures.

    ``system_events`` had zero rows, so "find a system error" was unanswerable
    from the UI. Every 5xx now leaves a row with the same correlation id the
    client was shown.
    """
    global _events_sink
    _events_sink = repository


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def _record(code: str, status: int, correlation_id: str, internal: Optional[str]) -> None:
    if status < 500 and code not in {ErrorCode.DB_UNAVAILABLE, ErrorCode.SCHEMA_OUT_OF_DATE}:
        return
    if _events_sink is None:
        return
    try:
        from qf_platform.repositories.events_repository import EventCategory

        _events_sink.log_event(
            "ERROR",
            "api",
            f"{code} {request.method} {request.path}",
            {"status": status, "detail": (internal or "")[:1000]},
            category=EventCategory.API,
            correlation_id=correlation_id,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Не удалось записать ошибку в system_events", exc_info=True)


def _respond(code: str, message: str, status: int, internal: Optional[str] = None):
    correlation_id = get_correlation_id()
    if status >= 500:
        logger.error(
            "%s %s → %s %s | cid=%s | %s",
            request.method, request.path, status, code, correlation_id, internal or "",
        )
    else:
        logger.info(
            "%s %s → %s %s | cid=%s", request.method, request.path, status, code, correlation_id
        )
    _record(code, status, correlation_id, internal)

    if not _wants_json():
        # An HTML consumer gets a plain page, not a JSON blob it cannot render.
        from flask import Response

        return Response(
            f"<!doctype html><meta charset=utf-8><title>{status}</title>"
            f"<body style='font:14px system-ui;background:#030303;color:#fff;padding:40px'>"
            f"<h1 style='font-size:20px'>{status}</h1><p>{message}</p>"
            f"<p style='opacity:.56;font-size:12px'>ID: {correlation_id}</p>",
            status=status,
            mimetype="text/html",
        )

    response = jsonify(error_envelope(code, message, correlation_id))
    response.status_code = status
    return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):  # noqa: ANN202
        return _respond(exc.code, exc.message(), exc.status, internal=exc.field_name)

    @app.errorhandler(ReadOnlyViolation)
    def _read_only(exc: ReadOnlyViolation):  # noqa: ANN202
        return _respond(
            ErrorCode.READ_ONLY_MODE,
            "Дашборд запущен в режиме только для чтения — изменение данных заблокировано.",
            403,
            internal=str(exc),
        )

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):  # noqa: ANN202
        status = exc.code or 500
        code = _HTTP_TO_CODE.get(status, ErrorCode.INTERNAL)
        from qf_platform.contracts import ERROR_MESSAGES

        return _respond(code, ERROR_MESSAGES.get(code, exc.name), status, internal=exc.description)

    @app.errorhandler(Exception)
    def _unhandled(exc: Exception):  # noqa: ANN202
        # The exception text is logged and stored, never returned: SQLAlchemy
        # puts the full statement and parameter list into its message.
        from qf_platform.contracts import ERROR_MESSAGES

        logger.exception("Unhandled exception on %s %s", request.method, request.path)
        code = _classify(exc)
        return _respond(
            code,
            ERROR_MESSAGES[code],
            500 if code == ErrorCode.INTERNAL else 503,
            internal=f"{type(exc).__name__}: {exc}",
        )

    # Werkzeug's 404/405 for unknown /api paths reach `_http_error` above, so a
    # JSON client never receives an HTML error page.
    app.config.setdefault("TRAP_HTTP_EXCEPTIONS", False)


def _classify(exc: Exception) -> str:
    """Map an infrastructure exception onto a contract code.

    String matching on the class name rather than importing every driver: the
    error handler must work whether or not psycopg2/SQLAlchemy are importable in
    the current process.
    """
    name = type(exc).__name__
    text = f"{name}: {exc}".lower()
    if name in {"OperationalError", "InterfaceError", "DBAPIError"} or "could not connect" in text:
        return ErrorCode.DB_UNAVAILABLE
    if name in {"UndefinedColumn", "UndefinedTable", "ProgrammingError"} and "does not exist" in text:
        return ErrorCode.SCHEMA_OUT_OF_DATE
    if "timeout" in text or name in {"TimeoutError", "ReadTimeout"}:
        return ErrorCode.UPSTREAM_TIMEOUT
    return ErrorCode.INTERNAL
