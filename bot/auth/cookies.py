"""Secure cookie helpers for auth tokens."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Response

from config import config


def _cookie_kwargs(max_age: int | None = None) -> dict:
    kwargs = {
        "httponly": True,
        "secure": config.auth.cookie_secure,
        "samesite": "Strict",
        "path": "/",
    }
    if max_age is not None:
        kwargs["max_age"] = max_age
    return kwargs


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    access_expires: datetime,
    csrf_token: str,
) -> Response:
    access_ttl = max(
        int((access_expires - datetime.now(timezone.utc)).total_seconds()),
        60,
    )
    refresh_ttl = config.auth.refresh_token_ttl_days * 86400

    response.set_cookie(
        config.auth.access_cookie_name,
        access_token,
        **_cookie_kwargs(access_ttl),
    )
    response.set_cookie(
        config.auth.refresh_cookie_name,
        refresh_token,
        **_cookie_kwargs(refresh_ttl),
    )
    response.set_cookie(
        config.auth.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=config.auth.cookie_secure,
        samesite="Strict",
        path="/",
        max_age=refresh_ttl,
    )
    return response


def clear_auth_cookies(response: Response) -> Response:
    for name in (
        config.auth.access_cookie_name,
        config.auth.refresh_cookie_name,
        config.auth.csrf_cookie_name,
    ):
        response.set_cookie(name, "", expires=0, path="/")
    return response