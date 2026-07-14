"""Trading engine state manager — bridges main trading loop with Telegram bot."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class BotStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


@dataclass
class EngineState:
    status: BotStatus = BotStatus.STOPPED
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    cycles_completed: int = 0
    last_cycle_at: Optional[datetime] = None
    errors_today: int = 0
    trades_today: int = 0
    log_buffer: list[str] = field(default_factory=list)

    def add_log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.log_buffer.append(entry)
        if len(self.log_buffer) > 200:
            self.log_buffer = self.log_buffer[-200:]

    def recent_logs(self, n: int = 20) -> list[str]:
        return self.log_buffer[-n:]


class TradingEngine:
    """
    Singleton that tracks the state of the algorithmic trading loop and
    provides async control methods callable from Telegram handlers.
    """

    def __init__(self) -> None:
        self._state = EngineState()
        self._pause_event = threading.Event()
        self._pause_event.set()   # set = not paused (engine can run)
        self._stop_event = threading.Event()

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def status(self) -> BotStatus:
        return self._state.status

    def set_status(self, status: BotStatus) -> None:
        prev = self._state.status
        self._state.status = status
        now = datetime.now(timezone.utc)
        if status == BotStatus.RUNNING and prev != BotStatus.RUNNING:
            self._state.started_at = now
        elif status == BotStatus.STOPPED:
            self._state.stopped_at = now
        self._state.add_log(f"Статус изменён: {prev.value} → {status.value}")
        logger.info("TradingEngine status: %s → %s", prev.value, status.value)

    def is_running(self) -> bool:
        return self._state.status == BotStatus.RUNNING

    def record_cycle(self) -> None:
        self._state.cycles_completed += 1
        self._state.last_cycle_at = datetime.now(timezone.utc)

    def record_trade(self) -> None:
        self._state.trades_today += 1

    def record_error(self, msg: str) -> None:
        self._state.errors_today += 1
        self._state.add_log(f"ОШИБКА: {msg}")

    def reset_daily(self) -> None:
        self._state.errors_today = 0
        self._state.trades_today = 0

    def pause(self) -> None:
        self._pause_event.clear()
        self.set_status(BotStatus.PAUSED)

    def resume(self) -> None:
        self._pause_event.set()
        self.set_status(BotStatus.RUNNING)

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        self.set_status(BotStatus.STOPPED)

    def start(self) -> None:
        self._stop_event.clear()
        self._pause_event.set()
        self.set_status(BotStatus.RUNNING)

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    @property
    def pause_event(self) -> threading.Event:
        return self._pause_event

    def summary(self) -> dict:
        s = self._state
        return {
            "status": s.status.value,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "last_cycle_at": s.last_cycle_at.isoformat() if s.last_cycle_at else None,
            "cycles_completed": s.cycles_completed,
            "trades_today": s.trades_today,
            "errors_today": s.errors_today,
        }


trading_engine = TradingEngine()
