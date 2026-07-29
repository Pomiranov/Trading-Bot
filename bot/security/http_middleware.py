"""Flask HTTP middleware — security headers, correlation IDs, compression.

Three fixes to what this module used to do:

1. **The CSP scoping bug.** It tested ``request.path.startswith("/static/miniapp/")``
   while the Mini App is served from ``/miniapp``, so the Mini App received
   ``frame-ancestors 'none'`` and could not be framed by Telegram Web at all — a
   correctness bug hiding inside a security control.
2. **``'unsafe-inline'`` for scripts is gone.** The operational shell has one
   inline bootstrap and it carries a per-response nonce. Granting
   ``'unsafe-inline'`` to every script materially weakened the policy against the
   31 unescaped ``innerHTML`` sinks that existed alongside it.
3. **No third-party origins.** ``unpkg.com``, ``cdn.jsdelivr.net``,
   ``fonts.googleapis.com`` and ``fonts.gstatic.com`` were all permitted because
   the page loaded two chart libraries and three font stylesheets from them. All
   four are removed: fonts are self-hosted and the charts are local.

Compression is added here because it was absent entirely — 326 KB of local assets
served uncompressed, of which measurement showed 77.6 % was avoidable.
"""
from __future__ import annotations

import gzip
import io
import os

from flask import Flask, g, request

from security.request_context import bind_ids, get_correlation_id, get_request_id


def _csp(*, nonce: str, frame_ancestors: str) -> str:
    """One policy builder, two call sites, no duplicated string literals.

    ``style-src`` keeps ``'unsafe-inline'``: the shell sets a handful of layout
    custom properties inline (panel heights, chart geometry) and a nonce cannot be
    attached to a style attribute. Scripts, which are what an XSS needs, do not
    get that latitude.

    An *empty* nonce is omitted rather than emitted. ``'nonce-'`` is an invalid
    source expression, and a browser that rejects it discards the whole
    ``script-src`` directive — which is the opposite of what this header is for.
    Responses with no inline script (API JSON, error pages) legitimately have no
    nonce.
    """
    script_src = f"script-src 'self' 'nonce-{nonce}'" if nonce else "script-src 'self'"
    return "; ".join([
        "default-src 'self'",
        script_src,
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        f"frame-ancestors {frame_ancestors}",
    ]) + ";"


_HTTPS = os.getenv("QF_HTTPS", "0") == "1"

#: Compress only text-ish payloads above this size. Below it, framing overhead
#: outweighs the saving.
_MIN_COMPRESS_BYTES = 1024
_COMPRESSIBLE = (
    "application/json",
    "text/html",
    "text/css",
    "text/plain",
    "application/javascript",
    "text/javascript",
    "image/svg+xml",
)


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

        path = request.path or ""
        # Correct prefix. The Mini App is mounted at /miniapp (see ui/views.py),
        # not /static/miniapp/.
        is_miniapp = path.startswith("/miniapp")

        nonce = getattr(g, "qf_csp_nonce", "") or ""

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if is_miniapp:
            response.headers.pop("X-Frame-Options", None)
        else:
            response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            _csp(
                nonce=nonce,
                frame_ancestors="https://web.telegram.org" if is_miniapp else "'none'",
            ),
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        # An authenticated operational surface must never be cached by a shared
        # proxy, and an API response must never be reused across sessions.
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if _HTTPS:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    @app.after_request
    def _compress(response):
        """gzip for text payloads. There was no compression of any kind.

        Skipped for streamed responses (the SSE endpoint) and for anything already
        encoded. ``Vary: Accept-Encoding`` is set so a cache cannot serve a gzipped
        body to a client that did not ask for one.
        """
        if response.direct_passthrough or response.is_streamed:
            return response
        if response.headers.get("Content-Encoding"):
            return response
        if "gzip" not in (request.headers.get("Accept-Encoding") or "").lower():
            return response

        mimetype = (response.mimetype or "").lower()
        if not any(mimetype.startswith(kind) for kind in _COMPRESSIBLE):
            return response

        data = response.get_data()
        if len(data) < _MIN_COMPRESS_BYTES:
            return response

        buffer = io.BytesIO()
        # mtime=0 keeps the output byte-stable for identical input, so an ETag
        # derived from it does not churn.
        with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=6, mtime=0) as handle:
            handle.write(data)
        compressed = buffer.getvalue()
        if len(compressed) >= len(data):
            return response

        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"
        return response
