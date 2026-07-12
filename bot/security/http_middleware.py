"""Flask HTTP middleware — request/correlation IDs."""
from __future__ import annotations

from flask import Flask, g, request

from security.request_context import bind_ids, get_correlation_id, get_request_id


def register_request_middleware(app: Flask) -> None:
    @app.before_request
    def _assign_request_ids() -> None:
        incoming_rid = (request.headers.get("X-Request-ID") or "").strip()
        incoming_cid = (request.headers.get("X-Correlation-ID") or "").strip()
        rid, cid = bind_ids(
            request_id=incoming_rid or None,
            correlation_id=incoming_cid or None,
        )
        g.request_id = rid
        g.correlation_id = cid

    @app.after_request
    def _echo_request_ids(response):
        response.headers["X-Request-ID"] = get_request_id()
        response.headers["X-Correlation-ID"] = get_correlation_id()
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response