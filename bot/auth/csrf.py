"""CSRF protection — double-submit cookie pattern."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from flask import Request

from config import config


def generate_csrf_token(session_seed: str | None = None) -> str:
    seed = session_seed or secrets.token_hex(16)
    digest = hmac.new(
        config.auth.csrf_secret.encode("utf-8"),
        seed.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{seed}.{digest}"


def validate_csrf(request: Request) -> bool:
    header = (request.headers.get("X-CSRF-Token") or "").strip()
    cookie = (request.cookies.get(config.auth.csrf_cookie_name) or "").strip()
    if not header or not cookie:
        return False
    if not hmac.compare_digest(header, cookie):
        return False
    parts = cookie.split(".", 1)
    if len(parts) != 2:
        return False
    seed, digest = parts
    expected = generate_csrf_token(seed).split(".", 1)[1]
    return hmac.compare_digest(digest, expected)


def uses_cookie_auth(request: Request) -> bool:
    return bool(request.cookies.get(config.auth.access_cookie_name))