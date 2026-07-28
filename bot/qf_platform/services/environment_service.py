"""The environment band: what am I looking at, and is it current?

This is the first thing on the Overview and the first thing the audit found
missing: sandbox-vs-live was displayed nowhere, while the marketing site puts
``РЕЖИМ · ПЕСОЧНИЦА`` permanently in its terminal's chrome. Engine state was
reachable at ``/api/platform/engine/status`` but not rendered, and data freshness
was a grey timestamp in the topbar that said "updated now" regardless of whether
anything had actually updated.

Three invariants:

* The environment is resolved from configuration and from the data, and when the
  two disagree the answer is ``UNKNOWN`` — a fault — not a guess.
* Engine state distinguishes *paused by an operator* from *not running* from
  *never reported*. They are three different situations with three different
  actions.
* Freshness is the age of the newest market bar, not the age of the response.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import config
from qf_platform.contracts import Freshness, age_seconds, to_display
from qf_platform.environment import ENVIRONMENT_LABELS, Environment
from qf_platform.repositories.market_repository import MarketRepository
from qf_platform.repositories.trades_repository import TradesRepository

logger = logging.getLogger(__name__)

#: Market data older than this is stale for operational purposes. One minute is
#: the audit's threshold for a live feed; anything beyond it must be visible.
MARKET_STALE_AFTER_SECONDS = 60

#: A daily bar cannot be fresher than a day, so judging a 1d feed against 60s
#: would paint every healthy deployment red. Per-timeframe thresholds keep the
#: marker meaningful: 32 days old is stale on any timeframe, 20 hours is not.
TIMEFRAME_STALE_AFTER = {
    "1m": 120,
    "5m": 600,
    "15m": 1800,
    "1h": 5400,
    "H1": 5400,
    "4h": 18000,
    "1d": 129600,   # 36 hours — a weekend gap is not a fault
    "D1": 129600,
}


def stale_threshold(timeframe: Optional[str]) -> int:
    return TIMEFRAME_STALE_AFTER.get(timeframe or "", MARKET_STALE_AFTER_SECONDS)


class EngineState:
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


ENGINE_LABELS = {
    EngineState.RUNNING: "Работает",
    EngineState.PAUSED: "Пауза",
    EngineState.STOPPED: "Остановлен",
    EngineState.UNKNOWN: "Состояние неизвестно",
}


@dataclass
class EnvironmentSnapshot:
    environment: Environment
    environment_label: str
    broker_label: str
    engine_state: str
    engine_label: str
    engine_detail: Optional[str]
    learning_active: Optional[bool]
    market_as_of: Optional[datetime]
    market_age_seconds: Optional[int]
    market_stale_after_seconds: int
    market_is_stale: Optional[bool]
    read_only: bool
    trading_actions_enabled: bool
    live_allowed: bool
    #: Rows whose provenance could not be established. Non-zero is a fault.
    unknown_environment_rows: int
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "environment": self.environment.value,
            "environment_label": self.environment_label,
            "is_real_money": self.environment.is_real_money,
            "is_environment_fault": self.environment.is_fault or bool(self.conflicts),
            "broker": self.broker_label,
            "engine": {
                "state": self.engine_state,
                "label": self.engine_label,
                "detail": self.engine_detail,
                "learning_active": self.learning_active,
            },
            "market_data": {
                "source_as_of": to_display(self.market_as_of),
                "data_age_seconds": self.market_age_seconds,
                "stale_after_seconds": self.market_stale_after_seconds,
                "is_stale": self.market_is_stale,
            },
            "read_only": self.read_only,
            "trading_actions_enabled": self.trading_actions_enabled,
            "live_allowed": self.live_allowed,
            "unknown_environment_rows": self.unknown_environment_rows,
            "conflicts": list(self.conflicts),
        }

    def freshness(self) -> Freshness:
        return Freshness(
            source_as_of=self.market_as_of,
            source="candles",
            stale_after_seconds=self.market_stale_after_seconds,
        )


class EnvironmentService:
    def __init__(self, engine):
        self._engine = engine
        self._market = MarketRepository(engine)
        self._trades = TradesRepository(engine)

    # ── Environment resolution ───────────────────────────────────────────────

    def resolve_environment(self) -> tuple[Environment, list[str]]:
        """Configured environment plus any contradiction found in the data.

        A conflict is a real condition, not a hypothetical: if the broker is
        configured for sandbox but the trades table contains rows marked live,
        one of the two is wrong and the operator must be told rather than shown
        whichever the code happened to read first.
        """
        conflicts: list[str] = []

        configured: Environment
        if not config.tinkoff.token and not config.bybit.api_key:
            # No broker configured at all — the paper engine is the only source.
            configured = Environment.SANDBOX
        elif config.tinkoff.sandbox:
            configured = Environment.SANDBOX
        else:
            configured = Environment.LIVE

        try:
            census = {row["environment"]: int(row["n"]) for row in self._trades.environment_census()}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Environment census failed: %s", exc)
            return Environment.UNKNOWN, ["Не удалось определить среду по данным сделок."]

        if configured is Environment.SANDBOX and census.get("live"):
            conflicts.append(
                f"Брокер настроен на песочницу, но в trades есть {census['live']} live-строк."
            )
        if configured is Environment.LIVE and census.get("sandbox"):
            conflicts.append(
                f"Брокер настроен на live, но в trades есть {census['sandbox']} sandbox-строк."
            )

        return configured, conflicts

    def unknown_row_count(self) -> int:
        try:
            census = {r["environment"]: int(r["n"]) for r in self._trades.environment_census()}
        except Exception:  # noqa: BLE001
            return 0
        return census.get("unknown", 0)

    # ── Engine state ─────────────────────────────────────────────────────────

    def engine_status(self) -> tuple[str, Optional[str], Optional[bool]]:
        """`(state, detail, learning_active)`.

        Distinguishes "not running" from "never reported". Importing the engine
        module can fail (it pulls in the broker stack), and a failed import is
        UNKNOWN, not STOPPED — telling an operator the engine is stopped when the
        truth is that we cannot see it is the kind of false certainty §20 warns
        about.
        """
        from security.readonly import read_only_enabled

        if read_only_enabled():
            return (
                EngineState.STOPPED,
                "Режим только для чтения — движок не запускается.",
                False,
            )
        try:
            from engine.paper_engine import paper_engine

            status = paper_engine.status()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Engine status unavailable: %s", exc)
            return EngineState.UNKNOWN, "Движок не отчитывался.", None

        running = bool(status.get("running"))
        learning = status.get("learning_active")
        if running:
            return EngineState.RUNNING, None, bool(learning) if learning is not None else None
        # `stop()` was called (as opposed to never started) — the engine keeps a
        # flag for it; absent that we can only say "stopped".
        detail = status.get("stopped_reason") or "Остановлен оператором или не запускался."
        return EngineState.PAUSED if status.get("paused") else EngineState.STOPPED, detail, \
            bool(learning) if learning is not None else None

    # ── Market freshness ─────────────────────────────────────────────────────

    def market_freshness(self, timeframe: str = "1d") -> tuple[Optional[datetime], Optional[int], int]:
        try:
            newest = self._market.newest_candle_at(timeframe)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Market freshness lookup failed: %s", exc)
            return None, None, stale_threshold(timeframe)
        threshold = stale_threshold(timeframe)
        return newest, age_seconds(newest), threshold

    def broker_label(self) -> str:
        if config.tinkoff.token:
            return "Т-Банк"
        if config.bybit.api_key:
            return "Bybit"
        return "Брокер не настроен"

    # ── Composite ────────────────────────────────────────────────────────────

    def snapshot(self, *, timeframe: str = "1d") -> EnvironmentSnapshot:
        from security.permissions import live_mode_enabled, trading_actions_enabled
        from security.readonly import read_only_enabled

        environment, conflicts = self.resolve_environment()
        if conflicts:
            # A contradiction is not resolved by picking a side.
            environment = Environment.UNKNOWN

        engine_state, engine_detail, learning = self.engine_status()
        newest, age, threshold = self.market_freshness(timeframe)

        return EnvironmentSnapshot(
            environment=environment,
            environment_label=ENVIRONMENT_LABELS[environment],
            broker_label=self.broker_label(),
            engine_state=engine_state,
            engine_label=ENGINE_LABELS[engine_state],
            engine_detail=engine_detail,
            learning_active=learning,
            market_as_of=newest,
            market_age_seconds=age,
            market_stale_after_seconds=threshold,
            market_is_stale=None if age is None else age > threshold,
            read_only=read_only_enabled(),
            trading_actions_enabled=trading_actions_enabled(),
            live_allowed=live_mode_enabled(),
            unknown_environment_rows=self.unknown_row_count(),
            conflicts=conflicts,
        )
