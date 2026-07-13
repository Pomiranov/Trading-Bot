"""
Reliability primitives: retry with exponential backoff, circuit breaker, timeout.
Drop-in decorators and context managers — no external dependencies.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Retry
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.1
    retriable: Tuple[Type[BaseException], ...] = (Exception,)
    non_retriable: Tuple[Type[BaseException], ...] = ()

    def delay_for(self, attempt: int) -> float:
        delay = min(self.base_delay * (self.backoff_factor ** (attempt - 1)), self.max_delay)
        import random
        return delay + random.uniform(0, self.jitter * delay)

    def is_retriable(self, exc: BaseException) -> bool:
        if self.non_retriable and isinstance(exc, self.non_retriable):
            return False
        return isinstance(exc, self.retriable)


BROKER_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    backoff_factor=2.0,
    non_retriable=(ValueError, TypeError, NotImplementedError),
)

DB_RETRY = RetryPolicy(
    max_attempts=5,
    base_delay=0.5,
    max_delay=8.0,
    backoff_factor=2.0,
)


def retry_sync(policy: RetryPolicy = BROKER_RETRY):
    """Decorator for synchronous functions."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Optional[BaseException] = None
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except BaseException as exc:
                    last_exc = exc
                    if attempt == policy.max_attempts or not policy.is_retriable(exc):
                        raise
                    delay = policy.delay_for(attempt)
                    logger.warning(
                        "%s attempt %d/%d failed (%s: %s) — retrying in %.1fs",
                        fn.__qualname__, attempt, policy.max_attempts,
                        type(exc).__name__, exc, delay,
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def retry_async(policy: RetryPolicy = BROKER_RETRY):
    """Decorator for async functions."""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc: Optional[BaseException] = None
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except BaseException as exc:
                    last_exc = exc
                    if attempt == policy.max_attempts or not policy.is_retriable(exc):
                        raise
                    delay = policy.delay_for(attempt)
                    logger.warning(
                        "%s attempt %d/%d failed (%s: %s) — retrying in %.1fs",
                        fn.__qualname__, attempt, policy.max_attempts,
                        type(exc).__name__, exc, delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# Circuit Breaker
# ──────────────────────────────────────────────────────────────────────────────

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(RuntimeError):
    """Raised when a call is rejected because the circuit is open."""


@dataclass
class CircuitBreaker:
    """
    Thread-safe circuit breaker (suitable for asyncio single-thread use).
    Transitions: CLOSED → OPEN (on failure_threshold failures in window)
                 OPEN → HALF_OPEN (after recovery_timeout seconds)
                 HALF_OPEN → CLOSED (on success) | OPEN (on failure)
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2
    half_open_max_calls: int = 1

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _success_count: int = field(default=0, init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)
    _half_open_calls: int = field(default=0, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
                logger.info("Circuit '%s' → HALF_OPEN (attempting recovery)", self.name)
        return self._state

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit '%s' → CLOSED (recovered)", self.name)
        else:
            self._failure_count = max(0, self._failure_count - 1)

    def _on_failure(self, exc: BaseException) -> None:
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.error(
                "Circuit '%s' → OPEN after %d failures (last: %s: %s)",
                self.name, self._failure_count, type(exc).__name__, exc,
            )

    def call_sync(self, fn: Callable, *args, **kwargs):
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitBreakerOpen(f"Circuit '{self.name}' is OPEN")
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen(f"Circuit '{self.name}' HALF_OPEN — probe in progress")
            self._half_open_calls += 1
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise

    async def call_async(self, fn: Callable, *args, **kwargs):
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitBreakerOpen(f"Circuit '{self.name}' is OPEN")
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen(f"Circuit '{self.name}' HALF_OPEN — probe in progress")
            self._half_open_calls += 1
        try:
            result = await fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def status_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Timeout
# ──────────────────────────────────────────────────────────────────────────────

async def with_timeout(coro, seconds: float, name: str = "operation"):
    """Wrap a coroutine with asyncio timeout, logging on expiry."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        logger.warning("%s timed out after %.1fs", name, seconds)
        raise


# ──────────────────────────────────────────────────────────────────────────────
# Registry of named breakers (one per broker / external service)
# ──────────────────────────────────────────────────────────────────────────────

_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _breakers[name]


def all_breaker_statuses() -> list[dict]:
    return [b.status_dict() for b in _breakers.values()]
