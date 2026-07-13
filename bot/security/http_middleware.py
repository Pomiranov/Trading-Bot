"""Flask HTTP middleware — security headers + request/correlation IDs."""
from __future__ import annotations

import os

from flask import Flask, g, request

from security.request_context import bind_ids, get_correlation_id, get_request_id

_CSP_MAIN = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)
_CSP_MINIAPP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors https://web.telegram.org;"
)

_HTTPS = os.getenv("QF_HTTPS", "0") == "1"


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
    def _apply_security_headers(response):
        response.headers["X-Request-ID"] = get_request_id()
        response.headers["X-Correlation-ID"] = get_correlation_id()

        is_miniapp = request.path.startswith("/static/miniapp/")

        # Prevent MIME-type sniffing
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Prevent clickjacking
        if is_miniapp:
            response.headers.pop("X-Frame-Options", None)
        else:
            response.headers.setdefault("X-Frame-Options", "DENY")
        # No referrer leakage
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # Content Security Policy
        response.headers.setdefault(
            "Content-Security-Policy",
            _CSP_MINIAPP if is_miniapp else _CSP_MAIN,
        )
        # Disable browser features we don't use
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        # HSTS — only when HTTPS is confirmed (opt-in via env)
        if _HTTPS:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response