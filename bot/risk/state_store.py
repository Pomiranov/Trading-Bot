"""Cross-process shared state for RiskManager.

The dashboard (bot/ui/dashboard.py) and the bot (bot/main.py) run as two
separate OS processes (on macOS via start.sh, on Windows via start.ps1 /
Task Scheduler). A plain in-process singleton for open positions / daily
PnL means each process enforces max_open_positions / max_daily_loss_pct
against its own, incomplete view — a position opened from the dashboard is
invisible to the bot process's risk checks and vice versa. This module gives
both processes one shared, lock-guarded source of truth on disk instead.

Not a general-purpose KV store: single JSON file + an OS lock on a separate
lock file, scoped to exactly the two counters RiskManager needs. Good enough
for two local processes on one host; if this ever needs to work across hosts,
move it to the database instead.

Locking goes through portalocker rather than fcntl.flock directly: fcntl is
POSIX-only and the bot also runs on Windows. portalocker maps to flock on
POSIX and to msvcrt byte-range locks on Windows, keeping one code path with
the same semantics on both.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import portalocker

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
    # "a+", not "w": "w" truncates on every acquisition. Harmless under flock,
    # but Windows byte-range locks are mandatory — truncating a file another
    # process holds locked can raise PermissionError.
    with open(LOCK_PATH, "a+") as lock_file:
        portalocker.lock(lock_file, portalocker.LOCK_EX)   # blocking, no LOCK_NB
        try:
            state = _read_state_unlocked()
            yield state
            _write_state_unlocked(state)
        finally:
            portalocker.unlock(lock_file)
