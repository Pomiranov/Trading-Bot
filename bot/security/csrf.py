"""CSRF protection for every mutating request.

There was none. Because the previous auth was IP-based rather than cookie-based,
``SameSite`` provided nothing either, and ten of twelve mutating endpoints —
engine start/stop, signal execution, paper trades, credential writes — were
drive-by exploitable from any page the operator happened to visit.

Two rules, both enforced here:

1. **No mutating GET.** A ``GET`` that changes state can be triggered by an
   ``<img src>``, which no token can protect. Four of them existed
   (``/paper/account``, ``/portfolio``, ``/overview``, ``/signals``); they are
   now read-only, and this module makes the rule structural rather than a
   convention.
2. **Double-submit with a session-bound token.** The token lives in the session
   row, is delivered in a script-readable cookie, and must be echoed in
   ``X-CSRF-Token``. A cross-origin page cannot read the cookie, so it cannot
   produce the header; comparison is against the *session's* token, so a token
   minted for another session does not work either.
"""

from __future__ import annotations

from typing import Optional

from flask import Request

from qf_platform.contracts import ApiError, ErrorCode
from security import passwords
from security.session_auth import CSRF_COOKIE, CSRF_HEADER, current_csrf_token

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Endpoints reachable without a session, and therefore without a session token.
#: Login is protected instead by the rate limiter plus an origin check; there is
#: no session to bind a token to before the user has one.
CSRF_EXEMPT_PATHS = frozenset({
    "/api/v2/auth/login",
    "/api/internal/push",   # protected by a shared internal token / loopback
})


def is_mutating(request: Request) -> bool:
    return request.method.upper() in MUTATING_METHODS


def _same_origin(request: Request) -> bool:
    """Verify ``Origin``/``Referer`` against this host.

    Belt-and-braces alongside the token: a browser always sends ``Origin`` on a
    cross-origin POST, so a mismatch is a positive signal even before the token
    is examined. A *missing* origin is not treated as failure — non-browser
    clients (curl, the Telegram bot) legitimately omit it, and they are already
    covered by the token requirement.
    """
    origin = request.headers.get("Origin")
    if origin:
        return origin.rstrip("/") == request.host_url.rstrip("/")
    referer = request.headers.get("Referer")
    if referer:
        return referer.startswith(request.host_url)
    return True


def validate_csrf(request: Request) -> None:
    """Raise ``ApiError(CSRF_INVALID)`` when the request fails the check."""
    if not is_mutating(request):
        return
    if request.path in CSRF_EXEMPT_PATHS:
        if not _same_origin(request):
            raise ApiError(ErrorCode.CSRF_INVALID)
        return

    if not _same_origin(request):
        raise ApiError(ErrorCode.CSRF_INVALID)

    expected = current_csrf_token()
    if not expected:
        # No session ⇒ nothing to compare against. Report it as an
        # authentication problem, which is what it actually is.
        raise ApiError(ErrorCode.UNAUTHENTICATED)

    provided = request.headers.get(CSRF_HEADER, "") or request.cookies.get(CSRF_COOKIE, "")
    if not provided or not passwords.constant_time_equals(provided, expected):
        raise ApiError(ErrorCode.CSRF_INVALID)


def token_for_client() -> Optional[str]:
    """The value the client should echo. Safe to embed in a page for the same
    session — it is worthless without the ``HttpOnly`` session cookie."""
    return current_csrf_token()
