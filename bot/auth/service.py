"""Authentication service — login, refresh, logout, setup."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from auth.brute_force import clear_failures, is_locked, record_failure
from auth.csrf import generate_csrf_token
from auth.jwt_service import JWTError, create_access_token, decode_access_token
from auth.passwords import hash_password, password_needs_rehash, verify_password
from auth.session_manager import get_session_manager
from auth.user_repository import User, get_user_repository
from config import config

logger = logging.getLogger(__name__)


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    access_expires: datetime
    csrf_token: str
    user: User


@dataclass
class AuthIdentity:
    user_id: int
    username: str
    role: str
    session_id: str
    jti: str


class AuthService:
    def setup_required(self) -> bool:
        repo = get_user_repository()
        return repo.ready and repo.count_users() == 0

    def create_admin(
        self,
        username: str,
        password: str,
        *,
        email: str | None = None,
    ) -> User:
        repo = get_user_repository()
        if not repo.ready:
            raise RuntimeError("Database unavailable")
        if repo.count_users() > 0:
            raise ValueError("Setup already completed")
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        return repo.create_user(
            username=username.strip(),
            password_hash=hash_password(password),
            role="admin",
            email=email,
        )

    def login(
        self,
        username: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens:
        username = username.strip()
        if is_locked(username):
            raise PermissionError("Account temporarily locked. Try again later.")

        repo = get_user_repository()
        user = repo.get_by_username(username)
        if user is None or not user.is_active:
            record_failure(username)
            raise PermissionError("Invalid username or password")

        if not verify_password(user.password_hash, password):
            record_failure(username)
            raise PermissionError("Invalid username or password")

        clear_failures(username)

        if password_needs_rehash(user.password_hash):
            repo.update_password_hash(user.id, hash_password(password))

        return self._issue_tokens(
            user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _issue_tokens(
        self,
        user: User,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens:
        sessions = get_session_manager()
        session = sessions.create_session(
            user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        access, jti, expires = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            session_id=session.session_id,
        )
        csrf = generate_csrf_token(session.session_id)
        return AuthTokens(
            access_token=access,
            refresh_token=session.refresh_token,
            access_expires=expires,
            csrf_token=csrf,
            user=user,
        )

    def refresh(
        self,
        refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens:
        sessions = get_session_manager()
        rotated = sessions.rotate_refresh(
            refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if rotated is None:
            raise PermissionError("Invalid or expired refresh token")

        repo = get_user_repository()
        user = repo.get_by_id(rotated.user_id)
        if user is None or not user.is_active:
            raise PermissionError("User inactive")

        access, jti, expires = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            session_id=rotated.session_id,
        )
        csrf = generate_csrf_token(rotated.session_id)
        return AuthTokens(
            access_token=access,
            refresh_token=rotated.refresh_token,
            access_expires=expires,
            csrf_token=csrf,
            user=user,
        )

    def logout(self, refresh_token: str | None, access_jti: str | None = None) -> None:
        sessions = get_session_manager()
        if refresh_token:
            sessions.revoke_refresh(refresh_token)
        if access_jti:
            ttl = config.auth.access_token_ttl_minutes * 60
            sessions.blacklist_jti(access_jti, ttl)

    def logout_all(self, user_id: int, access_jti: str | None = None) -> int:
        count = get_session_manager().revoke_all_for_user(user_id)
        if access_jti:
            ttl = config.auth.access_token_ttl_minutes * 60
            get_session_manager().blacklist_jti(access_jti, ttl)
        return count

    def resolve_identity(self, access_token: str) -> Optional[AuthIdentity]:
        try:
            payload = decode_access_token(access_token)
        except JWTError:
            return None

        jti = payload.get("jti", "")
        if get_session_manager().is_jti_revoked(jti):
            return None

        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return None

        repo = get_user_repository()
        user = repo.get_by_id(user_id)
        if user is None or not user.is_active:
            return None

        return AuthIdentity(
            user_id=user.id,
            username=user.username,
            role=user.role,
            session_id=payload.get("sid", ""),
            jti=jti,
        )


_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service