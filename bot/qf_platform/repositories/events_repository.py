"""News and system events persistence."""

from __future__ import annotations

import json

from qf_platform.repositories.base import BaseRepository


class EventsRepository(BaseRepository):
    def log_event(self, level: str, source: str, message: str, metadata: dict | None = None) -> None:
        self._execute(
            """
            INSERT INTO system_events (level, source, message, metadata)
            VALUES (:level, :source, :message, :meta)
            """,
            {"level": level, "source": source, "message": message, "meta": json.dumps(metadata or {})},
        )

    def recent_errors(self, limit: int = 10) -> list[dict]:
        return self._query(
            """
            SELECT created_at, level, source, message
            FROM system_events
            WHERE level IN ('ERROR', 'WARN')
            ORDER BY created_at DESC LIMIT :limit
            """,
            {"limit": limit},
        )

    def recent_events(self, limit: int = 30) -> list[dict]:
        return self._query(
            """
            SELECT created_at, level, source, message
            FROM system_events ORDER BY created_at DESC LIMIT :limit
            """,
            {"limit": limit},
        )

    def list_news(self, limit: int = 20) -> list[dict]:
        return self._query(
            """
            SELECT published_at, source, title, sentiment, importance, url
            FROM news ORDER BY published_at DESC LIMIT :limit
            """,
            {"limit": limit},
        )

    def news_count(self) -> int:
        rows = self._query("SELECT COUNT(*) AS cnt FROM news")
        return int(rows[0]["cnt"]) if rows else 0