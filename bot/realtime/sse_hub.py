"""Server-Sent Events hub for live dashboard updates."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class SSEHub:
    """Thread-safe pub/sub for SSE clients."""

    def __init__(self) -> None:
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._last_broadcast = time.time()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event_type: str, data: Any) -> None:
        payload = {"type": event_type, "data": data, "ts": time.time()}
        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)
        self._last_broadcast = time.time()

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def format_sse(self, payload: dict) -> str:
        return f"event: {payload['type']}\ndata: {json.dumps(payload, default=str)}\n\n"


sse_hub = SSEHub()