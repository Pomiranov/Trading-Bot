"""User persistence layer."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from auth.models import ALL_DDL
from config import config

logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
    email: str | None = None
    created_at: datetime | None = None


class UserRepository:
    def __init__(self) -> None:
        self._engine = None
        self._ready = False
        self._init()

    def _init(self) -> None:
        try:
            from sqlalchemy import create_engine, text

            self._engine = create_engine(
                config.db.dsn,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=2,
            )
            with self._engine.begin() as conn:
                for stmt in ALL_DDL.split(";"):
                    s = stmt.strip()
                    if s:
                        conn.execute(text(s))
            self._ready = True
            logger.info("Auth user tables ready")
        except Exception as exc:
            logger.warning("Auth user DB unavailable: %s", exc)

    @property
    def ready(self) -> bool:
        return self._ready

    def count_users(self) -> int:
        if not self._ready:
            return 0
        from sqlalchemy import text

        with self._engine.connect() as conn:
            row = conn.execute(text("SELECT COUNT(*) AS c FROM users")).mappings().one()
            return int(row["c"])

    def get_by_username(self, username: str) -> Optional[User]:
        if not self._ready:
            return None
        from sqlalchemy import text

        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, username, email, password_hash, role, is_active, created_at
                    FROM users WHERE username = :username LIMIT 1
                """),
                {"username": username},
            ).mappings().first()
            if not row:
                return None
            return User(
                id=row["id"],
                username=row["username"],
                email=row.get("email"),
                password_hash=row["password_hash"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row.get("created_at"),
            )

    def get_by_id(self, user_id: int) -> Optional[User]:
        if not self._ready:
            return None
        from sqlalchemy import text

        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, username, email, password_hash, role, is_active, created_at
                    FROM users WHERE id = :id LIMIT 1
                """),
                {"id": user_id},
            ).mappings().first()
            if not row:
                return None
            return User(
                id=row["id"],
                username=row["username"],
                email=row.get("email"),
                password_hash=row["password_hash"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row.get("created_at"),
            )

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "admin",
        email: str | None = None,
    ) -> User:
        if not self._ready:
            raise RuntimeError("User database unavailable")
        from sqlalchemy import text

        with self._engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (:username, :email, :password_hash, :role)
                    RETURNING id, username, email, password_hash, role, is_active, created_at
                """),
                {
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
                },
            ).mappings().one()
        return User(
            id=row["id"],
            username=row["username"],
            email=row.get("email"),
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row.get("created_at"),
        )

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        if not self._ready:
            return
        from sqlalchemy import text

        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE users
                    SET password_hash = :hash, updated_at = :now
                    WHERE id = :id
                """),
                {
                    "hash": password_hash,
                    "now": datetime.now(timezone.utc),
                    "id": user_id,
                },
            )


_repo: UserRepository | None = None


def get_user_repository() -> UserRepository:
    global _repo
    if _repo is None:
        _repo = UserRepository()
    return _repo