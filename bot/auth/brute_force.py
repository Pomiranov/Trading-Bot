"""Login brute-force protection via Redis."""
from __future__ import annotations

from auth.redis_client import require_redis
from config import config


def _fail_key(username: str) -> str:
    return f"auth:brute:{username.lower()}"


def _lock_key(username: str) -> str:
    return f"auth:lock:{username.lower()}"


def is_locked(username: str) -> bool:
    redis = require_redis()
    return redis.exists(_lock_key(username)) == 1


def record_failure(username: str) -> int:
    redis = require_redis()
    lock_seconds = config.auth.lockout_minutes * 60
    fails = redis.incr(_fail_key(username))
    if fails == 1:
        redis.expire(_fail_key(username), lock_seconds)
    if fails >= config.auth.max_login_attempts:
        redis.setex(_lock_key(username), lock_seconds, "1")
        redis.delete(_fail_key(username))
    return int(fails)


def clear_failures(username: str) -> None:
    redis = require_redis()
    redis.delete(_fail_key(username))
    redis.delete(_lock_key(username))