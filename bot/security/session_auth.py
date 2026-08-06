"""Server-side session authentication for the operational dashboard.

Replaces the previous access-control surface, which was one ``before_request``
hook comparing the source IP against an allow-list. Under shipped defaults that
meant zero of 52 routes required a credential, and because the check was
IP-based rather than cookie-based, ``SameSite`` gave no CSRF protection either.

Design, and why each part is the way it is:

* **Opaque session id in an ``HttpOnly`` cookie.** No claims client-side, so
  privilege cannot be edited and revocation is immediate. Sessions live in
  ``dashboard_sessions``.
* **Session id rotated on login.** Prevents session fixation: a value the
  attacker planted before authentication is not the value that ends up
  authenticated.
* **Generic authentication errors.** «Неверный логин или пароль» for a missing
  user, a wrong password and a locked account alike; combined with
  ``dummy_verify`` the timing matches too.
* **Two independent rate limits.** A per-(username, IP) sliding window against
  bursts, and a persistent per-user lockout against a slow distributed guess.
* **CSRF token bound to the session**, delivered in a readable cookie and echoed
  in a header — see ``security.csrf``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from flask import Flask, g, request

from qf_platform.repositories.auth_repository import AuthRepository
from security import passwords
from security.permissions import Principal, Role

logger = logging.getLogger(__name__)

SESSION_COOKIE = "qf_session"
CSRF_COOKIE = "qf_csrf"
CSRF_HEADER = "X-CSRF-Token"

#: 8 hours: one trading day. Sliding, refreshed at most once a minute.
SESSION_TTL_SECONDS = int(os.getenv("QF_SESSION_TTL_SECONDS", str(8 * 3600)))
_TOUCH_INTERVAL_SECONDS = 60

#: Burst limiter: N failures from the same username or IP inside the window.
LOGIN_WINDOW_SECONDS = int(os.getenv("QF_LOGIN_WINDOW_SECONDS", "300"))
LOGIN_MAX_FAILURES = int(os.getenv("QF_LOGIN_MAX_FAILURES", "5"))

#: Persistent lockout: consecutive failures on one account.
ACCOUNT_LOCK_AFTER = int(os.getenv("QF_ACCOUNT_LOCK_AFTER", "10"))
ACCOUNT_LOCK_MINUTES = int(os.getenv("QF_ACCOUNT_LOCK_MINUTES", "15"))


def secure_cookies() -> bool:
    """``Secure`` is on unless the deployment says it is serving plain HTTP.

    Defaulting to on means a production deployment that forgets to set anything
    still gets the safe behaviour; localhost development opts out explicitly.
    """
    if os.getenv("QF_HTTPS", "0") == "1":
        return True
    return os.getenv("QF_INSECURE_COOKIES", "0") != "1"


@dataclass
class LoginResult:
    ok: bool
    principal: Optional[Principal] = None
    session_id: Optional[str] = None
    csrf_token: Optional[str] = None
    #: Machine-readable, for the audit trail — never shown to the client.
    failure_kind: Optional[str] = None
    retry_after_seconds: Optional[int] = None


class SessionService:
    def __init__(self, engine):
        self._repo = AuthRepository(engine)

    # ── Login / logout ───────────────────────────────────────────────────────

    def authenticate(
        self,
        username: str,
        password: str,
        *,
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> LoginResult:
        username = (username or "").strip()

        failures = self._repo.recent_failures(
            username=username or None,
            client_ip=client_ip,
            window_seconds=LOGIN_WINDOW_SECONDS,
        )
        if failures >= LOGIN_MAX_FAILURES:
            # Do not touch the password path at all — that is the point of a
            # rate limit — but still record the attempt so the window slides.
            self._repo.record_attempt(username=username or None, client_ip=client_ip, success=False)
            return LoginResult(
                ok=False,
                failure_kind="rate_limited",
                retry_after_seconds=LOGIN_WINDOW_SECONDS,
            )

        user = self._repo.find_user(username) if username else None

        if user is None:
            # Spend comparable time so a missing account is not detectable.
            passwords.dummy_verify(password)
            self._repo.record_attempt(username=username or None, client_ip=client_ip, success=False)
            return LoginResult(ok=False, failure_kind="unknown_user")

        locked_until = user.get("locked_until")
        if locked_until is not None:
            from qf_platform.contracts import age_seconds

            remaining = age_seconds(locked_until)
            if remaining is not None and remaining <= 0:
                passwords.dummy_verify(password)
                self._repo.record_attempt(username=username, client_ip=client_ip, success=False)
                return LoginResult(
                    ok=False, failure_kind="account_locked",
                    retry_after_seconds=ACCOUNT_LOCK_MINUTES * 60,
                )

        if not user.get("is_active"):
            passwords.dummy_verify(password)
            self._repo.record_attempt(username=username, client_ip=client_ip, success=False)
            return LoginResult(ok=False, failure_kind="inactive")

        if not passwords.verify_password(user["password_hash"], password):
            self._repo.record_attempt(username=username, client_ip=client_ip, success=False)
            self._repo.register_login_outcome(
                int(user["id"]), success=False,
                lock_after=ACCOUNT_LOCK_AFTER, lock_minutes=ACCOUNT_LOCK_MINUTES,
            )
            return LoginResult(ok=False, failure_kind="bad_password")

        # Success. Upgrade the digest if the KDF parameters have moved on.
        if passwords.needs_rehash(user["password_hash"]):
            try:
                self._repo.update_password(int(user["id"]), passwords.hash_password(password))
            except Exception:  # noqa: BLE001 — never fail a valid login over this
                logger.warning("Не удалось обновить хеш пароля для %s", username)

        sid = passwords.new_session_id()
        csrf_token = passwords.new_csrf_token()
        self._repo.create_session(
            sid=sid,
            user_id=int(user["id"]),
            csrf_token=csrf_token,
            ttl_seconds=SESSION_TTL_SECONDS,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._repo.record_attempt(username=username, client_ip=client_ip, success=True)
        self._repo.register_login_outcome(int(user["id"]), success=True)

        principal = Principal(
            user_id=int(user["id"]),
            username=user["username"],
            role=Role.coerce(user.get("role")),
            trading_authorized=bool(user.get("trading_authorized")),
            display_name=user.get("display_name"),
            session_id=sid,
        )
        return LoginResult(ok=True, principal=principal, session_id=sid, csrf_token=csrf_token)

    def logout(self, sid: Optional[str]) -> None:
        if sid:
            self._repo.revoke_session(sid)

    def logout_everywhere(self, user_id: int) -> None:
        self._repo.revoke_user_sessions(user_id)

    # ── Per-request resolution ───────────────────────────────────────────────

    def resolve(self, sid: Optional[str]) -> tuple[Optional[Principal], Optional[str]]:
        """`(principal, csrf_token)` for a session id, or `(None, None)`."""
        if not sid:
            return None, None
        row = self._repo.load_session(sid)
        if row is None:
            return None, None

        principal = Principal.from_session_row(row)

        # Sliding expiry, but not on every request: a write per poll would put
        # the session table on the 12-second poll path.
        last_seen = row.get("last_seen_at")
        should_touch = True
        if last_seen is not None:
            from qf_platform.contracts import age_seconds

            age = age_seconds(last_seen)
            should_touch = age is None or age >= _TOUCH_INTERVAL_SECONDS
        if should_touch:
            try:
                self._repo.touch_session(sid, ttl_seconds=SESSION_TTL_SECONDS)
            except Exception:  # noqa: BLE001
                logger.debug("Не удалось обновить срок сессии", exc_info=True)

        return principal, row.get("csrf_token")

    def has_any_user(self) -> bool:
        try:
            return self._repo.user_count() > 0
        except Exception:  # noqa: BLE001
            return False

    def ensure_bootstrap_user(self) -> Optional[str]:
        """Create the first administrator from the environment, if asked.

        Returns the username created, or None. There is no default password: if
        ``QF_DASHBOARD_BOOTSTRAP_PASSWORD`` is unset, nothing happens and the
        login page explains that no operator exists yet.
        """
        if self.has_any_user():
            return None
        password = passwords.bootstrap_password_from_env()
        if not password:
            return None
        username = os.getenv("QF_DASHBOARD_BOOTSTRAP_USER", "operator").strip() or "operator"
        problem = passwords.password_strength_error(password)
        if problem:
            logger.error("QF_DASHBOARD_BOOTSTRAP_PASSWORD отклонён: %s", problem)
            return None
        try:
            from qf_platform.migrate import create_user

            create_user(
                self._repo._engine, username, password,
                role="administrator", trading_authorized=False,
                display_name=os.getenv("QF_DASHBOARD_BOOTSTRAP_NAME") or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Не удалось создать первого пользователя: %s", exc)
            return None
        logger.warning(
            "Создан первый администратор «%s» из QF_DASHBOARD_BOOTSTRAP_PASSWORD. "
            "Удалите эту переменную окружения и смените пароль.", username,
        )
        return username

    def sessions_for(self, user_id: int) -> list[dict]:
        return self._repo.active_sessions(user_id)

    def housekeeping(self) -> None:
        """Bounded cleanup. Called from the engine's schedule, not a request."""
        try:
            self._repo.purge_expired_sessions()
            self._repo.prune_attempts()
            self._repo.prune_idempotency()
        except Exception:  # noqa: BLE001
            logger.debug("Сессионная уборка не выполнена", exc_info=True)


# ── Flask integration ─────────────────────────────────────────────────────────

_service: Optional[SessionService] = None


def init_session_auth(engine) -> Optional[SessionService]:
    global _service
    _service = SessionService(engine) if engine is not None else None
    return _service


def session_service() -> Optional[SessionService]:
    return _service


def client_ip() -> str:
    """The real TCP peer only.

    ``X-Forwarded-For`` is client-supplied. Trusting it would let an attacker
    choose the identity written into the audit log and the key the rate limiter
    counts against. Behind a reverse proxy, use Werkzeug's ``ProxyFix`` with an
    explicit trusted-hop count so ``remote_addr`` is rewritten correctly instead.
    """
    return request.remote_addr or ""


def current_principal() -> Optional[Principal]:
    return getattr(g, "qf_principal", None)


def current_csrf_token() -> Optional[str]:
    return getattr(g, "qf_csrf_token", None)


def attach_principal() -> None:
    """Resolve the session once per request and stash it on ``g``."""
    g.qf_principal = None
    g.qf_csrf_token = None
    svc = session_service()
    if svc is None:
        return
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return
    try:
        principal, csrf_token = svc.resolve(sid)
    except Exception:  # noqa: BLE001 — a DB blip must not 500 every route
        logger.warning("Не удалось разрешить сессию", exc_info=True)
        return
    g.qf_principal = principal
    g.qf_csrf_token = csrf_token


def set_session_cookies(response, *, session_id: str, csrf_token: str):
    """Session cookie is ``HttpOnly``; the CSRF cookie deliberately is not.

    Double-submit needs JavaScript to read the token and echo it in a header. The
    token is useless without the session cookie, which script cannot read, so the
    pair is safe while remaining usable from a fetch wrapper.
    """
    secure = secure_cookies()
    response.set_cookie(
        SESSION_COOKIE, session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True, secure=secure, samesite="Strict", path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token,
        max_age=SESSION_TTL_SECONDS,
        httponly=False, secure=secure, samesite="Strict", path="/",
    )
    return response


def clear_session_cookies(response):
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.set_cookie(
            name, "", expires=0, max_age=0,
            httponly=(name == SESSION_COOKIE),
            secure=secure_cookies(), samesite="Strict", path="/",
        )
    return response


def register_session_hooks(app: Flask) -> None:
    @app.before_request
    def _resolve_session():  # noqa: ANN202
        g.qf_request_started = time.monotonic()
        attach_principal()
