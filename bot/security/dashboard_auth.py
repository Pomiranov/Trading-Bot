"""Dashboard HTTP API access control (Phase 0 emergency hardening)."""
from __future__ import annotations

import hmac
import logging

from flask import Flask, jsonify, request

from config import config
from security.audit import audit_record

logger = logging.getLogger(__name__)

_API_KEY_HEADER = "X-Dashboard-Api-Key"
_LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _client_host() -> str:
    """Real TCP peer only — X-Forwarded-For is client-supplied and must
    never be trusted for the local/trusted-request decision below, or any
    attacker can spoof "X-Forwarded-For: 127.0.0.1" to bypass the API-key
    check on every mutating endpoint. If this app is ever put behind a
    reverse proxy, use werkzeug's ProxyFix (with an explicit trusted-hop
    count) so it rewrites remote_addr correctly instead of trusting a raw
    header here."""
    return request.remote_addr or ""


def _is_local_request() -> bool:
    host = _client_host()
    return host in _LOCAL_HOSTS


def _api_key_valid() -> bool:
    expected = config.dashboard.api_key
    if not expected:
        return False
    provided = request.headers.get(_API_KEY_HEADER, "")
    return bool(provided) and hmac.compare_digest(provided, expected)


def _write_allowed() -> bool:
    """Mutating API calls: local loopback OR valid dashboard API key."""
    if _api_key_valid():
        return True
    if _is_local_request():
        return True
    host = _client_host()
    logger.warning(
        "Denied dashboard write from host=%s path=%s",
        host,
        request.path,
    )
    audit_record(
        event_type="api.auth.denied",
        actor_type="client",
        actor_id=host,
        resource_type="endpoint",
        resource_id=request.path,
        outcome="denied",
        client_ip=host,
    )
    return False


def _read_allowed() -> bool:
    """Read API: open on loopback; require key when dashboard is exposed."""
    if config.dashboard.require_api_key_for_reads:
        return _api_key_valid()
    return True


def register_dashboard_security(app: Flask) -> None:
    """Register before_request hook for /api/* routes."""

    @app.before_request
    def _enforce_dashboard_security():
        path = request.path or ""

        if path == "/health":
            return None

        if not path.startswith("/api/"):
            return None

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not _write_allowed():
                return jsonify({
                    "error": "Требуется авторизация API",
                    "error_code": "UNAUTHORIZED",
                }), 401
            return None

        if not _read_allowed():
            return jsonify({
                "error": "Требуется ключ API дашборда",
                "error_code": "UNAUTHORIZED",
            }), 401

        return None