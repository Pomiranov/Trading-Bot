"""Persistence for dashboard authentication: users, sessions, attempts, idempotency.

Sessions are server-side rows, not signed cookies carrying claims. The cookie
holds an opaque id and nothing else, so revoking a session is a single UPDATE and
a stolen cookie stops working the moment it is revoked — neither of which is true
of a self-contained token.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from qf_platform.repositories.base import BaseRepository

ROLES = ("observer", "operator", "administrator")


class AuthRepository(BaseRepository):
    # ── Users ────────────────────────────────────────────────────────────────

    def find_user(self, username: str) -> Optional[dict]:
        rows = self._query(
            """
            SELECT id, username, password_hash, role, trading_authorized,
                   display_name, is_active, failed_attempts, locked_until,
                   last_login_at, password_changed_at
            FROM dashboard_users WHERE LOWER(username) = LOWER(:u)
            """,
            {"u": username},
        )
        return rows[0] if rows else None

    def get_user(self, user_id: int) -> Optional[dict]:
        rows = self._query(
            """
            SELECT id, username, password_hash, role, trading_authorized,
                   display_name, is_active, last_login_at
            FROM dashboard_users WHERE id = :id
            """,
            {"id": user_id},
        )
        return rows[0] if rows else None

    def user_count(self) -> int:
        rows = self._query("SELECT COUNT(*) AS n FROM dashboard_users WHERE is_active")
        return int(rows[0]["n"]) if rows else 0

    def register_login_outcome(
        self, user_id: int, *, success: bool, lock_after: int = 10, lock_minutes: int = 15
    ) -> None:
        """Advance or reset the per-user lockout counter.

        Distinct from the (username, ip) rate limiter: this one survives a
        restart and protects a single account from a slow distributed guess.
        """
        if success:
            self._execute(
                """
                UPDATE dashboard_users
                   SET failed_attempts = 0, locked_until = NULL,
                       last_login_at = NOW(), updated_at = NOW()
                 WHERE id = :id
                """,
                {"id": user_id},
            )
            return
        self._execute(
            """
            UPDATE dashboard_users
               SET failed_attempts = failed_attempts + 1,
                   locked_until = CASE
                       WHEN failed_attempts + 1 >= :lock_after
                       THEN NOW() + CAST(:lock_minutes || ' minutes' AS interval)
                       ELSE locked_until END,
                   updated_at = NOW()
             WHERE id = :id
            """,
            {"id": user_id, "lock_after": lock_after, "lock_minutes": lock_minutes},
        )

    def update_password(self, user_id: int, password_hash: str) -> None:
        self._execute(
            """
            UPDATE dashboard_users
               SET password_hash = :h, password_changed_at = NOW(), updated_at = NOW(),
                   failed_attempts = 0, locked_until = NULL
             WHERE id = :id
            """,
            {"id": user_id, "h": password_hash},
        )

    # ── Sessions ─────────────────────────────────────────────────────────────

    def create_session(
        self,
        *,
        sid: str,
        user_id: int,
        csrf_token: str,
        ttl_seconds: int,
        client_ip: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        self._execute(
            """
            INSERT INTO dashboard_sessions
                (sid, user_id, csrf_token, expires_at, client_ip, user_agent)
            VALUES (:sid, :uid, :csrf, :expires, :ip, :ua)
            """,
            {
                "sid": sid,
                "uid": user_id,
                "csrf": csrf_token,
                "expires": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
                "ip": (client_ip or "")[:64] or None,
                "ua": (user_agent or "")[:256] or None,
            },
        )

    def load_session(self, sid: str) -> Optional[dict]:
        """Join the session to its user in one query.

        Expiry and revocation are filtered in SQL so an expired row can never be
        returned and then forgotten about by a caller.
        """
        rows = self._query(
            """
            SELECT s.sid, s.user_id, s.csrf_token, s.created_at, s.last_seen_at,
                   s.expires_at, s.client_ip,
                   u.username, u.role, u.trading_authorized, u.display_name, u.is_active
            FROM dashboard_sessions s
            JOIN dashboard_users u ON u.id = s.user_id
            WHERE s.sid = :sid
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
              AND u.is_active
            """,
            {"sid": sid},
        )
        return rows[0] if rows else None

    def touch_session(self, sid: str, *, ttl_seconds: int) -> None:
        """Sliding expiry. Called at most once per session per minute by the
        caller — a write on every request would put the session table on the
        poll path, which is the mistake `equity_snapshots` already made."""
        self._execute(
            """
            UPDATE dashboard_sessions
               SET last_seen_at = NOW(),
                   expires_at = NOW() + CAST(:ttl || ' seconds' AS interval)
             WHERE sid = :sid AND revoked_at IS NULL
            """,
            {"sid": sid, "ttl": int(ttl_seconds)},
        )

    def revoke_session(self, sid: str) -> None:
        self._execute(
            "UPDATE dashboard_sessions SET revoked_at = NOW() WHERE sid = :sid AND revoked_at IS NULL",
            {"sid": sid},
        )

    def revoke_user_sessions(self, user_id: int) -> None:
        self._execute(
            "UPDATE dashboard_sessions SET revoked_at = NOW()"
            " WHERE user_id = :uid AND revoked_at IS NULL",
            {"uid": user_id},
        )

    def purge_expired_sessions(self) -> int:
        result = self._execute(
            "DELETE FROM dashboard_sessions"
            " WHERE expires_at < NOW() - INTERVAL '7 days'"
            "    OR (revoked_at IS NOT NULL AND revoked_at < NOW() - INTERVAL '7 days')"
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def active_sessions(self, user_id: int) -> list[dict]:
        return self._query(
            """
            SELECT sid, created_at, last_seen_at, expires_at, client_ip, user_agent
            FROM dashboard_sessions
            WHERE user_id = :uid AND revoked_at IS NULL AND expires_at > NOW()
            ORDER BY last_seen_at DESC
            """,
            {"uid": user_id},
        )

    # ── Login rate limiting ──────────────────────────────────────────────────

    def record_attempt(self, *, username: Optional[str], client_ip: Optional[str], success: bool) -> None:
        self._execute(
            """
            INSERT INTO dashboard_login_attempts (username, client_ip, success)
            VALUES (:u, :ip, :ok)
            """,
            {
                "u": (username or "")[:64] or None,
                "ip": (client_ip or "")[:64] or None,
                "ok": success,
            },
        )

    def recent_failures(
        self, *, username: Optional[str], client_ip: Optional[str], window_seconds: int
    ) -> int:
        """Failures in the window for this username OR this IP.

        `OR` rather than `AND`: a spray across many usernames from one host and a
        slow guess against one username from many hosts are both attacks, and
        requiring both to match would catch neither.
        """
        rows = self._query(
            """
            SELECT COUNT(*) AS n FROM dashboard_login_attempts
            WHERE success = false
              AND attempted_at >= NOW() - CAST(:window || ' seconds' AS interval)
              AND (
                    (:u  IS NOT NULL AND LOWER(username) = LOWER(:u))
                 OR (:ip IS NOT NULL AND client_ip = :ip)
              )
            """,
            {"u": username, "ip": client_ip, "window": int(window_seconds)},
        )
        return int(rows[0]["n"]) if rows else 0

    def prune_attempts(self, *, older_than_hours: int = 24) -> int:
        result = self._execute(
            "DELETE FROM dashboard_login_attempts"
            " WHERE attempted_at < NOW() - CAST(:h || ' hours' AS interval)",
            {"h": int(older_than_hours)},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    # ── Idempotency ──────────────────────────────────────────────────────────

    def find_idempotent(self, key: str) -> Optional[dict]:
        rows = self._query(
            """
            SELECT idempotency_key, action, actor_id, request_digest,
                   response_json, status_code, created_at
            FROM action_idempotency WHERE idempotency_key = :k
            """,
            {"k": key},
        )
        return rows[0] if rows else None

    def store_idempotent(
        self,
        *,
        key: str,
        action: str,
        actor_id: Optional[str],
        request_digest: str,
        response: dict,
        status_code: int,
    ) -> None:
        self._execute(
            """
            INSERT INTO action_idempotency
                (idempotency_key, action, actor_id, request_digest, response_json, status_code)
            VALUES (:k, :a, :actor, :digest, CAST(:resp AS JSONB), :code)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            {
                "k": key[:80],
                "a": action[:64],
                "actor": (actor_id or "")[:64] or None,
                "digest": request_digest[:64],
                "resp": json.dumps(response, ensure_ascii=False, default=str),
                "code": int(status_code),
            },
        )

    def claim_idempotency_key(
        self, *, key: str, action: str, actor_id: Optional[str], request_digest: str
    ) -> bool:
        """Reserve a key before doing the work. `True` means we won the race.

        Two clicks land as two requests; the loser sees the reservation and must
        not repeat the side effect. `ON CONFLICT DO NOTHING` plus a rowcount check
        makes that a single atomic statement rather than a read-then-write with a
        window in the middle.
        """
        result = self._execute(
            """
            INSERT INTO action_idempotency
                (idempotency_key, action, actor_id, request_digest, status_code)
            VALUES (:k, :a, :actor, :digest, NULL)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            {
                "k": key[:80],
                "a": action[:64],
                "actor": (actor_id or "")[:64] or None,
                "digest": request_digest[:64],
            },
        )
        return int(getattr(result, "rowcount", 0) or 0) == 1

    def complete_idempotency_key(self, *, key: str, response: dict, status_code: int) -> None:
        self._execute(
            """
            UPDATE action_idempotency
               SET response_json = CAST(:resp AS JSONB), status_code = :code
             WHERE idempotency_key = :k
            """,
            {
                "k": key[:80],
                "resp": json.dumps(response, ensure_ascii=False, default=str),
                "code": int(status_code),
            },
        )

    def release_idempotency_key(self, key: str) -> None:
        """Drop an unfinished reservation so a genuine retry can proceed.

        Without this, a request that crashed before completing would leave the
        key claimed and the operator unable to retry the action at all.
        """
        self._execute(
            "DELETE FROM action_idempotency WHERE idempotency_key = :k AND status_code IS NULL",
            {"k": key[:80]},
        )

    def prune_idempotency(self, *, older_than_hours: int = 48) -> int:
        result = self._execute(
            "DELETE FROM action_idempotency"
            " WHERE created_at < NOW() - CAST(:h || ' hours' AS interval)",
            {"h": int(older_than_hours)},
        )
        return int(getattr(result, "rowcount", 0) or 0)
