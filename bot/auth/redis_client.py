"""Redis connection for auth sessions, revocation, and rate limits."""
from __future__ import annotations

import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

_client = None
_available: bool | None = None


def get_redis():
    global _client, _available
    if _client is not None:
        return _client

    try:
        import redis

        url = config.redis.url
        password = config.redis.password or None
        _client = redis.Redis.from_url(
            url,
            password=password,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        _client.ping()
        _available = True
        logger.info("Redis connected for auth")
        return _client
    except Exception as exc:
        _available = False
        logger.warning("Redis unavailable: %s", exc)
        _client = None
        return None


def redis_available() -> bool:
    if _available is None:
        get_redis()
    return bool(_available)


def require_redis():
    client = get_redis()
    if client is None:
        raise RuntimeError(
            "Redis is required for authentication. Start Redis or set AUTH_ENABLED=false"
        )
    return client