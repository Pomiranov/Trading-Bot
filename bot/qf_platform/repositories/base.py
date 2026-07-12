"""Base repository with shared query helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text


class BaseRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def _query(self, sql: str, params: dict | None = None) -> list[dict]:
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            cols = list(result.keys())
            return [dict(zip(cols, row)) for row in result.fetchall()]

    def _execute(self, sql: str, params: dict | None = None) -> Any:
        with self._engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return result