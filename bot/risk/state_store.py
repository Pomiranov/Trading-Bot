"""Cross-process shared state for RiskManager.

The dashboard (bot/ui/dashboard.py) and the bot (bot/main.py) run as two
separate OS processes (see start.sh — one via `nohup ... &`, the other via
`exec`). A plain in-process singleton for open positions / daily PnL means
each process enforces max_open_positions / max_daily_loss_pct against its
own, incomplete view — a position opened from the dashboard is invisible to
the bot process's risk checks and vice versa. This module gives both
processes one shared, lock-guarded source of truth on disk instead.

Not a general-purpose KV store: single JSON file + advisory OS lock
(fcntl.flock), scoped to exactly the two counters RiskManager needs. Good
enough for two local processes on one host; if this ever needs to work
across hosts, move it to the database instead.
"""
from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

STATE_PATH = Path(__file__).parent.parent / "data" / "risk_state.json"
LOCK_PATH = Path(__file__).parent.parent / "data" / "risk_state.lock"

_EMPTY_STATE = {"daily_pnl": 0.0, "open_positions": {}}


def _read_state_unlocked() -> dict:
    if not STATE_PATH.exists():
        return {"daily_pnl": 0.0, "open_positions": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"daily_pnl": 0.0, "open_positions": {}}
    data.setdefault("daily_pnl", 0.0)
    data.setdefault("open_positions", {})
    return data


def _write_state_unlocked(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_PATH)


@contextmanager
def transaction() -> Iterator[dict]:
    """Read-modify-write the shared risk state under a lock held across
    both processes for the whole critical section (read → caller mutates
    the yielded dict in place → write) — this is what makes check-then-act
    sequences (e.g. "is there room for one more position?" then "add one")
    atomic with respect to the *other* process, not just other threads in
    this one."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            state = _read_state_unlocked()
            yield state
            _write_state_unlocked(state)
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
