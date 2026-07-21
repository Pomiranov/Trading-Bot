"""
SandboxLearningLoop — async bridge between sync PaperEngine and async TradingOrchestrator.

Architecture:
    PaperEngine runs in sync background threads.
    TradingOrchestrator is fully async (asyncpg pools).
    This module provides a thread-safe sync interface to the orchestrator
    by running it in a dedicated asyncio event loop thread.

Usage:
    loop = SandboxLearningLoop(dsn=config.db.dsn)
    loop.start()

    # From any sync thread:
    decision = loop.check_signal(signal_dict, timeout=3.0)   # blocking, returns dict
    trade_id = loop.on_trade_opened(trade_obj, timeout=3.0)  # blocking, returns str
    loop.on_trade_closed(trade_obj)                          # fire-and-forget
    loop.run_full_cycle()                                    # fire-and-forget

    loop.stop()
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from concurrent.futures import Future
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("quantflow.sandbox_loop")

# Default timeout for blocking calls (seconds)
_DEFAULT_TIMEOUT = 5.0


class SandboxLearningLoop:
    """
    Thread-safe synchronous interface to the async TradingOrchestrator.

    Runs a dedicated asyncio event loop in a background daemon thread.
    Callers submit work via concurrent.futures.Future objects placed
    into an asyncio queue — the event loop drains the queue and resolves
    the futures.
    """

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._task_queue: Optional[asyncio.Queue] = None
        self._orchestrator = None
        self._started = threading.Event()
        self._stopping = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stopping = False
            self._thread = threading.Thread(
                target=self._run_loop,
                name="sandbox-learning-loop",
                daemon=True,
            )
            self._thread.start()

        # Block until the event loop is ready
        if not self._started.wait(timeout=15):
            logger.error("SandboxLearningLoop: failed to start within 15s")

    def stop(self) -> None:
        with self._lock:
            self._stopping = True
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=10)

    def is_running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._started.is_set()
        )

    # ------------------------------------------------------------------
    # Internal: event loop thread
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as exc:
            logger.error("SandboxLearningLoop crashed: %s", exc, exc_info=True)
        finally:
            self._loop.close()
            self._started.clear()
            logger.info("SandboxLearningLoop: event loop thread exited")

    async def _async_main(self) -> None:
        from learning.trading_orchestrator import TradingOrchestrator

        self._task_queue = asyncio.Queue()
        self._orchestrator = TradingOrchestrator(dsn=self._dsn)

        try:
            await self._orchestrator.connect()
            logger.info("SandboxLearningLoop: orchestrator connected")
        except Exception as exc:
            logger.error("SandboxLearningLoop: DB connection failed: %s", exc)
            self._started.set()  # unblock callers even on failure
            return

        self._started.set()

        while not self._stopping:
            try:
                item = await asyncio.wait_for(
                    self._task_queue.get(), timeout=1.0
                )
                fut, coro_fn, args, kwargs = item
                try:
                    result = await coro_fn(*args, **kwargs)
                    if fut is not None and not fut.done():
                        # concurrent.futures.Future.set_result is thread-safe
                        fut.set_result(result)
                except Exception as exc:
                    logger.warning("SandboxLearningLoop task error: %s", exc)
                    if fut is not None and not fut.done():
                        try:
                            fut.set_exception(exc)
                        except Exception:
                            pass
                finally:
                    self._task_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

        try:
            await self._orchestrator.disconnect()
        except Exception:
            pass
        logger.info("SandboxLearningLoop: async main exited")

    # ------------------------------------------------------------------
    # Internal: submit work to the event loop
    # ------------------------------------------------------------------

    def _submit(
        self,
        coro_fn,
        *args,
        fire_and_forget: bool = False,
        timeout: float = _DEFAULT_TIMEOUT,
        **kwargs,
    ):
        """
        Submit a coroutine to the learning loop.

        fire_and_forget=True: returns immediately, result is discarded.
        fire_and_forget=False: blocks until result (or timeout), returns result.
        """
        if not self.is_running() or self._task_queue is None:
            logger.debug("SandboxLearningLoop: not running, skipping %s", coro_fn.__name__)
            return None

        if fire_and_forget:
            self._loop.call_soon_threadsafe(
                self._task_queue.put_nowait,
                (None, coro_fn, args, kwargs),
            )
            return None

        # Blocking call: use concurrent.futures.Future
        fut = concurrent_future()
        self._loop.call_soon_threadsafe(
            self._task_queue.put_nowait,
            (fut, coro_fn, args, kwargs),
        )
        try:
            return fut.result(timeout=timeout)
        except Exception as exc:
            logger.warning("SandboxLearningLoop._submit(%s) error: %s", coro_fn.__name__, exc)
            return None

    # ------------------------------------------------------------------
    # Public sync API
    # ------------------------------------------------------------------

    def check_signal(self, signal: dict, timeout: float = _DEFAULT_TIMEOUT) -> dict:
        """
        Gate a signal through the learning system.

        Returns the orchestrator decision dict:
            {"approved": bool, "confidence": Decimal, "reason": str, ...}
        Returns a permissive default if learning loop is unavailable.
        """
        result = self._submit(
            self._orchestrator.check_signal,
            signal,
            timeout=timeout,
        )
        if result is None:
            return {
                "approved": True,
                "confidence": Decimal("0.5"),
                "position_size_multiplier": Decimal("1.0"),
                "reason": "learning loop unavailable — permissive default",
                "matched_hypotheses": [],
            }
        return result

    def on_trade_opened(self, trade, timeout: float = _DEFAULT_TIMEOUT) -> Optional[str]:
        """
        Record trade open in the learning system.
        Returns trade_id from the trades table.
        """
        result = self._submit(
            self._orchestrator.on_trade_opened,
            trade,
            timeout=timeout,
        )
        return result

    def on_trade_closed(self, trade) -> None:
        """Trigger learning cycle after trade close (fire-and-forget)."""
        self._submit(
            self._orchestrator.on_trade_closed,
            trade,
            fire_and_forget=True,
        )

    def run_full_cycle(self) -> None:
        """Run full learning cycle on all historical trades (fire-and-forget)."""
        self._submit(
            self._orchestrator.run_full_learning_cycle,
            fire_and_forget=True,
        )

    def get_strategy_stats(self, strategy_id: str, timeout: float = _DEFAULT_TIMEOUT) -> Optional[dict]:
        """Return belief_system row for strategy_id, or None."""
        result = self._submit(
            self._orchestrator._get_strategy_stats,
            strategy_id,
            timeout=timeout,
        )
        return result

    def notify_learning_event(self, result: dict) -> None:
        """Push learning cycle result to Telegram (fire-and-forget, runs in own thread)."""
        import threading
        threading.Thread(
            target=_send_learning_tg,
            args=(result,),
            daemon=True,
        ).start()


# ------------------------------------------------------------------
# Helper: concurrent.futures.Future
# ------------------------------------------------------------------

def concurrent_future():
    """Return a concurrent.futures.Future bound to the *calling* thread loop."""
    import concurrent.futures
    return concurrent.futures.Future()


# ------------------------------------------------------------------
# Telegram notification (sync, non-blocking)
# ------------------------------------------------------------------

def _send_learning_tg(result: dict) -> None:
    try:
        from tg.notifications.dispatcher import notify_learning_cycle_sync
        notify_learning_cycle_sync(result)
    except Exception as exc:
        logger.debug("Learning TG notify error: %s", exc)


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

sandbox_learning_loop = SandboxLearningLoop()
