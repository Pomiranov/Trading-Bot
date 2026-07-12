"""Refresh token sessions — Redis primary, PostgreSQL audit trail."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from auth.redis_client import require_redis
from auth.user_repository import get_user_repository
from config import config

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: str
    user_id: int
    refresh_token: str
    expires_at: datetime


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionManager:
    def create_session(
        self,
        user_id: int,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_id: str | None = None,
    ) -> SessionInfo:
        redis = require_redis()
        session_id = str(uuid.uuid4())
        refresh_token = secrets.token_urlsafe(48)
        token_hash = _hash_token(refresh_token)
        ttl_seconds = config.auth.refresh_token_ttl_days * 86400
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        redis.setex(
            f"auth:refresh:{token_hash}",
            ttl_seconds,
            f"{user_id}:{session_id}",
        )

        repo = get_user_repository()
        if repo.ready:
            from sqlalchemy import text

            with repo._engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO user_sessions (
                            id, user_id, refresh_token_hash, device_id,
                            ip_address, user_agent, expires_at
                        ) VALUES (
                            :id, :user_id, :hash, :device_id,
                            :ip, :ua, :expires
                        )
                    """),
                    {
                        "id": session_id,
                        "user_id": user_id,
                        "hash": token_hash,
                        "device_id": device_id,
                        "ip": ip_address,
                        "ua": (user_agent or "")[:512],
                        "expires": expires,
                    },
                )

        return SessionInfo(
            session_id=session_id,
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=expires,
        )

    def validate_refresh(self, refresh_token: str) -> Optional[SessionInfo]:
        redis = require_redis()
        token_hash = _hash_token(refresh_token)
        raw = redis.get(f"auth:refresh:{token_hash}")
        if not raw:
            return None
        user_id_str, session_id = raw.split(":", 1)
        ttl = redis.ttl(f"auth:refresh:{token_hash}")
        expires = datetime.now(timezone.utc) + timedelta(seconds=max(ttl, 0))
        return SessionInfo(
            session_id=session_id,
            user_id=int(user_id_str),
            refresh_token=refresh_token,
            expires_at=expires,
        )

    def rotate_refresh(self, old_token: str, **kwargs) -> Optional[SessionInfo]:
        info = self.validate_refresh(old_token)
        if info is None:
            return None
        self.revoke_refresh(old_token)
        return self.create_session(info.user_id, **kwargs)

    def revoke_refresh(self, refresh_token: str) -> None:
        redis = require_redis()
        token_hash = _hash_token(refresh_token)
        redis.delete(f"auth:refresh:{token_hash}")

        repo = get_user_repository()
        if repo.ready:
            from sqlalchemy import text

            with repo._engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE user_sessions
                        SET revoked_at = :now
                        WHERE refresh_token_hash = :hash AND revoked_at IS NULL
                    """),
                    {"now": datetime.now(timezone.utc), "hash": token_hash},
                )

    def revoke_all_for_user(self, user_id: int) -> int:
        redis = require_redis()
        repo = get_user_repository()
        count = 0
        if repo.ready:
            from sqlalchemy import text

            with repo._engine.begin() as conn:
                rows = conn.execute(
                    text("""
                        SELECT refresh_token_hash FROM user_sessions
                        WHERE user_id = :uid AND revoked_at IS NULL
                    """),
                    {"uid": user_id},
                ).mappings().all()
                for row in rows:
                    redis.delete(f"auth:refresh:{row['refresh_token_hash']}")
                    count += 1
                conn.execute(
                    text("""
                        UPDATE user_sessions SET revoked_at = :now
                        WHERE user_id = :uid AND revoked_at IS NULL
                    """),
                    {"now": datetime.now(timezone.utc), "uid": user_id},
                )
        return count

    def blacklist_jti(self, jti: str, ttl_seconds: int) -> None:
        redis = require_redis()
        if ttl_seconds > 0:
            redis.setex(f"auth:jti:{jti}", ttl_seconds, "1")

    def is_jti_revoked(self, jti: str) -> bool:
        redis = require_redis()
        return redis.exists(f"auth:jti:{jti}") == 1

    def touch_session(self, session_id: str) -> None:
        repo = get_user_repository()
        if not repo.ready:
            return
        from sqlalchemy import text

        with repo._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE user_sessions SET last_active = :now WHERE id = :id
                """),
                {"now": datetime.now(timezone.utc), "id": session_id},
            )


_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager