"""System health, collected off the request path and cached.

The previous implementation ran, on every ``/health``, ``/overview`` and
``/brokers`` request — i.e. six times a minute per open tab:

* ``subprocess.run(["docker", "ps"])``      → 8 640 process spawns per day
* ``psutil.cpu_percent(interval=0.1)``      → a hard 100 ms sleep in the request thread
* a Redis client with a 1 s connect timeout → for a Redis this project does not use
* two separate database connections        → against a five-connection pool

That is ~130 ms of pure blocking before any application data is read. Here the
probes run in a background thread on their own schedule and requests read the
last completed snapshot. A request never blocks on a probe, and a probe that has
never completed reports ``UNKNOWN`` rather than defaulting to healthy.

Eight states, each carrying all seven properties the audit requires: word, shape,
timestamp, reason, action, age and the environment it applies to. ``UNKNOWN``
never collapses into ``HEALTHY``: a service that has never reported is not a
service that is fine.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from config import config
from qf_platform.contracts import age_seconds, to_display

logger = logging.getLogger(__name__)


class HealthState:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    PAUSED = "paused"
    FROZEN = "frozen"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    UNKNOWN = "unknown"


#: Word + shape per state. The shape is what survives greyscale, so it is part of
#: the contract rather than a CSS decision.
STATE_PRESENTATION = {
    HealthState.HEALTHY:      {"label": "Работает",   "shape": "dot-filled",  "severity": 0},
    HealthState.DEGRADED:     {"label": "Деградация", "shape": "dot-half",    "severity": 2},
    HealthState.STALE:        {"label": "Устарело",   "shape": "ring",        "severity": 2},
    HealthState.PAUSED:       {"label": "Пауза",      "shape": "square",      "severity": 1},
    HealthState.FROZEN:       {"label": "Заморожено", "shape": "ring-slash",  "severity": 1},
    HealthState.DISCONNECTED: {"label": "Нет связи",  "shape": "ring",        "severity": 3},
    HealthState.FAILED:       {"label": "Ошибка",     "shape": "dot-filled",  "severity": 3},
    HealthState.UNKNOWN:      {"label": "Неизвестно", "shape": "ring-dashed", "severity": 2},
}


@dataclass
class ServiceHealth:
    key: str
    name: str
    state: str
    reason: Optional[str] = None
    action: Optional[str] = None
    checked_at: Optional[datetime] = None
    source_as_of: Optional[datetime] = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        presentation = STATE_PRESENTATION.get(self.state, STATE_PRESENTATION[HealthState.UNKNOWN])
        return {
            "key": self.key,
            "name": self.name,
            "state": self.state,
            "label": presentation["label"],
            "shape": presentation["shape"],
            "severity": presentation["severity"],
            "reason": self.reason,
            "action": self.action,
            "checked_at": to_display(self.checked_at),
            "source_as_of": to_display(self.source_as_of),
            "data_age_seconds": age_seconds(self.source_as_of) if self.source_as_of else None,
            "detail": self.detail,
        }


@dataclass
class LatencySample:
    """In-process request-latency histogram.

    API latency was listed as unavailable. Measuring it here — p50/p95 over a
    bounded ring buffer — is honest and costs nothing; inventing a number would
    not be.
    """

    capacity: int = 512
    values: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe(self, milliseconds: float) -> None:
        with self._lock:
            self.values.append(milliseconds)
            if len(self.values) > self.capacity:
                del self.values[: len(self.values) - self.capacity]

    def percentiles(self) -> dict:
        with self._lock:
            data = sorted(self.values)
        if not data:
            return {"n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}

        def pct(fraction: float) -> float:
            index = min(len(data) - 1, max(0, int(round(fraction * (len(data) - 1)))))
            return round(data[index], 1)

        return {
            "n": len(data),
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "max_ms": round(data[-1], 1),
        }


class HealthService:
    """Background collector plus a cached read.

    ``start()`` is called once by the app factory. ``snapshot()`` never performs
    I/O: it returns whatever the collector last produced, with a ``checked_at``
    so the client can see that health itself has gone stale.
    """

    #: How often each probe class runs. Chosen so nothing here is on a 12-second
    #: poll: a container list changing every 15 seconds is not information.
    FAST_INTERVAL = 15.0     # db, engine, market data
    SLOW_INTERVAL = 120.0    # docker, disk, host metrics

    def __init__(self, engine=None):
        self._engine = engine
        self._lock = threading.Lock()
        self._services: dict[str, ServiceHealth] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_fast: float = 0.0
        self._last_slow: float = 0.0
        self.latency = LatencySample()
        self._seed_unknown()

    def _seed_unknown(self) -> None:
        """Every service starts UNKNOWN, not HEALTHY.

        The old UI rendered the absence of a signal as nothing at all, which the
        eye reads as "no problem".
        """
        catalogue = [
            ("database", "База данных"),
            ("market_data", "Рыночные данные"),
            ("tinkoff", "Т-Банк"),
            ("bybit", "Bybit"),
            ("forward_runner", "Форвард-раннер"),
            ("engine", "Движок"),
            ("telegram", "Telegram"),
            ("api", "API"),
            ("host", "Хост"),
            ("containers", "Контейнеры"),
        ]
        for key, name in catalogue:
            self._services[key] = ServiceHealth(
                key=key, name=name, state=HealthState.UNKNOWN,
                reason="Ещё не проверялось.", action="Дождитесь первой проверки.",
            )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="qf-health-collector", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # Run the fast probes immediately so the first page load has real data.
        while not self._stop.is_set():
            now = time.monotonic()
            try:
                if now - self._last_fast >= self.FAST_INTERVAL:
                    self._collect_fast()
                    self._last_fast = now
                if now - self._last_slow >= self.SLOW_INTERVAL:
                    self._collect_slow()
                    self._last_slow = now
            except Exception:  # noqa: BLE001 — the collector must never die
                logger.warning("Health collection cycle failed", exc_info=True)
            self._stop.wait(2.0)

    def collect_once(self) -> None:
        """Synchronous collection, for tests and for the read-only QA pass."""
        self._collect_fast()
        self._collect_slow()

    # ── Probes ───────────────────────────────────────────────────────────────

    def _set(self, health: ServiceHealth) -> None:
        health.checked_at = datetime.now(timezone.utc)
        with self._lock:
            self._services[health.key] = health

    def _collect_fast(self) -> None:
        self._probe_database()
        self._probe_market_data()
        self._probe_brokers()
        self._probe_engine()
        self._probe_forward_runner()
        self._probe_telegram()
        self._probe_api()

    def _collect_slow(self) -> None:
        self._probe_host()
        self._probe_containers()

    def _probe_database(self) -> None:
        if self._engine is None:
            self._set(ServiceHealth(
                key="database", name="База данных", state=HealthState.DISCONNECTED,
                reason="Соединение не сконфигурировано.",
                action="Проверьте DB_HOST/DB_PASSWORD.",
            ))
            return
        from sqlalchemy import text

        started = time.monotonic()
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                size = conn.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar()
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            state = HealthState.DEGRADED if elapsed_ms > 500 else HealthState.HEALTHY
            self._set(ServiceHealth(
                key="database", name="База данных", state=state,
                reason=f"Ответ {elapsed_ms:.0f} мс" if state == HealthState.DEGRADED else None,
                action="Проверьте нагрузку на БД." if state == HealthState.DEGRADED else None,
                detail={
                    "host": config.db.host,
                    "latency_ms": elapsed_ms,
                    "size_mb": round(int(size or 0) / 1024 / 1024, 1),
                },
            ))
        except Exception as exc:  # noqa: BLE001
            self._set(ServiceHealth(
                key="database", name="База данных", state=HealthState.FAILED,
                reason=str(exc).splitlines()[0][:160],
                action="Откройте журнал событий.",
            ))

    def _probe_market_data(self) -> None:
        if self._engine is None:
            return
        from qf_platform.repositories.market_repository import MarketRepository
        from qf_platform.services.environment_service import stale_threshold

        try:
            repo = MarketRepository(self._engine)
            newest = repo.newest_candle_at("1d")
        except Exception as exc:  # noqa: BLE001
            self._set(ServiceHealth(
                key="market_data", name="Рыночные данные", state=HealthState.FAILED,
                reason=str(exc).splitlines()[0][:160], action="Откройте журнал событий.",
            ))
            return

        if newest is None:
            self._set(ServiceHealth(
                key="market_data", name="Рыночные данные", state=HealthState.UNKNOWN,
                reason="В таблице candles нет данных.",
                action="Проверьте загрузчик свечей.",
            ))
            return

        age = age_seconds(newest) or 0
        threshold = stale_threshold("1d")
        if age > threshold:
            days = age // 86400
            human = f"{days} дн назад" if days else f"{age // 3600} ч назад"
            self._set(ServiceHealth(
                key="market_data", name="Рыночные данные", state=HealthState.STALE,
                reason=f"Последняя свеча {human}.",
                action="Проверьте загрузчик свечей.",
                source_as_of=newest,
            ))
        else:
            self._set(ServiceHealth(
                key="market_data", name="Рыночные данные", state=HealthState.HEALTHY,
                source_as_of=newest,
            ))

    def _probe_brokers(self) -> None:
        """Configuration state only — no broker call on a health probe.

        Opening a gRPC channel to check liveness is what produced four
        ``GetPortfolio`` calls in the same second. Actual reachability is reported
        by the portfolio path, which needs the connection anyway, and cached.
        """
        tinkoff_configured = bool(config.tinkoff.token and config.tinkoff.account_id)
        self._set(ServiceHealth(
            key="tinkoff", name="Т-Банк",
            state=HealthState.HEALTHY if tinkoff_configured else HealthState.UNKNOWN,
            reason=None if tinkoff_configured else "Токен или account_id не заданы.",
            action=None if tinkoff_configured else "Настройки → Брокеры.",
            detail={
                "configured": tinkoff_configured,
                "sandbox": config.tinkoff.sandbox,
            },
        ))
        bybit_configured = bool(config.bybit.api_key and config.bybit.api_secret)
        self._set(ServiceHealth(
            key="bybit", name="Bybit",
            state=HealthState.HEALTHY if bybit_configured else HealthState.UNKNOWN,
            reason=None if bybit_configured else "Ключи не заданы.",
            action=None if bybit_configured else "Настройки → Брокеры.",
            detail={"configured": bybit_configured, "testnet": config.bybit.testnet},
        ))

    def _probe_engine(self) -> None:
        from qf_platform.services.environment_service import EngineState, EnvironmentService

        if self._engine is None:
            return
        try:
            state, detail, learning = EnvironmentService(self._engine).engine_status()
        except Exception as exc:  # noqa: BLE001
            self._set(ServiceHealth(
                key="engine", name="Движок", state=HealthState.UNKNOWN,
                reason=str(exc).splitlines()[0][:160], action="Проверьте сервис.",
            ))
            return

        mapping = {
            EngineState.RUNNING: HealthState.HEALTHY,
            EngineState.PAUSED: HealthState.PAUSED,
            EngineState.STOPPED: HealthState.PAUSED,
            EngineState.UNKNOWN: HealthState.UNKNOWN,
        }
        self._set(ServiceHealth(
            key="engine", name="Движок", state=mapping.get(state, HealthState.UNKNOWN),
            reason=detail,
            action="Обзор → Возобновить" if state != EngineState.RUNNING else None,
            detail={"learning_active": learning},
        ))

    def _probe_forward_runner(self) -> None:
        if self._engine is None:
            return
        from qf_platform.repositories.events_repository import EventsRepository

        try:
            rows = EventsRepository(self._engine).runner_states()
        except Exception as exc:  # noqa: BLE001
            self._set(ServiceHealth(
                key="forward_runner", name="Форвард-раннер", state=HealthState.UNKNOWN,
                reason=str(exc).splitlines()[0][:160],
            ))
            return

        if not rows:
            self._set(ServiceHealth(
                key="forward_runner", name="Форвард-раннер", state=HealthState.UNKNOWN,
                reason="Раннер ни разу не отчитывался.",
                action="Проверьте, запущен ли форвард-раннер.",
            ))
            return

        newest = max(
            (r.get("heartbeat_at") or r.get("updated_at") for r in rows if r.get("heartbeat_at") or r.get("updated_at")),
            default=None,
        )
        age = age_seconds(newest)
        if age is None:
            state, reason = HealthState.UNKNOWN, "Нет отметки времени."
        elif age > 86400:
            state, reason = HealthState.STALE, f"Не обновлялся {age // 86400} дн."
        elif age > 3600:
            state, reason = HealthState.DEGRADED, f"Не обновлялся {age // 60} мин."
        else:
            state, reason = HealthState.HEALTHY, None
        self._set(ServiceHealth(
            key="forward_runner", name="Форвард-раннер", state=state, reason=reason,
            action="Открыть журнал" if state != HealthState.HEALTHY else None,
            source_as_of=newest,
            detail={"instruments": len(rows)},
        ))

    def _probe_telegram(self) -> None:
        configured = bool(config.telegram.token)
        self._set(ServiceHealth(
            key="telegram", name="Telegram",
            state=HealthState.HEALTHY if configured else HealthState.UNKNOWN,
            reason=None if configured else "Токен не задан.",
            action=None if configured else "Настройки → Уведомления.",
            detail={
                "configured": configured,
                # Delivery status is genuinely not exposed by any endpoint. Saying
                # so is better than showing a green dot that means "configured".
                "delivery_status": "не отслеживается",
            },
        ))

    def _probe_api(self) -> None:
        percentiles = self.latency.percentiles()
        p95 = percentiles.get("p95_ms")
        if percentiles["n"] == 0:
            state, reason = HealthState.UNKNOWN, "Нет измерений."
        elif p95 is not None and p95 > 1500:
            state, reason = HealthState.DEGRADED, f"p95 {p95:.0f} мс"
        else:
            state, reason = HealthState.HEALTHY, None
        self._set(ServiceHealth(
            key="api", name="API", state=state, reason=reason,
            action="Открыть метрики" if state == HealthState.DEGRADED else None,
            detail=percentiles,
        ))

    def _probe_host(self) -> None:
        detail: dict = {}
        state = HealthState.HEALTHY
        reason = None
        try:
            import psutil

            # interval=None returns the value since the previous call — no sleep.
            # interval=0.1 blocked the request thread for 100 ms, six times a minute.
            detail["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
            memory = psutil.virtual_memory()
            detail["ram_percent"] = round(memory.percent, 1)
            detail["ram_used_mb"] = round(memory.used / 1024 / 1024, 1)
            detail["ram_total_mb"] = round(memory.total / 1024 / 1024, 1)
            if memory.percent > 92:
                state, reason = HealthState.DEGRADED, f"RAM {memory.percent:.0f} %"
        except ImportError:
            state, reason = HealthState.UNKNOWN, "psutil не установлен."
        except Exception as exc:  # noqa: BLE001
            state, reason = HealthState.UNKNOWN, str(exc)[:160]

        try:
            usage = shutil.disk_usage("/")
            detail["disk_free_gb"] = round(usage.free / 1024 ** 3, 1)
            if usage.free / usage.total < 0.08:
                state, reason = HealthState.DEGRADED, "Мало места на диске."
        except Exception:  # noqa: BLE001
            pass

        self._set(ServiceHealth(
            key="host", name="Хост", state=state, reason=reason,
            action="Проверьте сервер." if state != HealthState.HEALTHY else None,
            detail=detail,
        ))

    def _probe_containers(self) -> None:
        """Container list, at most every two minutes, in a background thread.

        Retained because knowing the database container is gone is genuinely
        useful; moved off the request path because 8 640 ``docker ps`` spawns a
        day to render a count is not.
        """
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode != 0:
                self._set(ServiceHealth(
                    key="containers", name="Контейнеры", state=HealthState.UNKNOWN,
                    reason="docker недоступен.",
                ))
                return
            names = [c for c in result.stdout.strip().splitlines() if c]
            self._set(ServiceHealth(
                key="containers", name="Контейнеры", state=HealthState.HEALTHY,
                detail={"containers": names, "count": len(names)},
            ))
        except FileNotFoundError:
            self._set(ServiceHealth(
                key="containers", name="Контейнеры", state=HealthState.UNKNOWN,
                reason="docker не установлен.",
            ))
        except Exception as exc:  # noqa: BLE001
            self._set(ServiceHealth(
                key="containers", name="Контейнеры", state=HealthState.UNKNOWN,
                reason=str(exc)[:160],
            ))

    # ── Read ─────────────────────────────────────────────────────────────────

    def snapshot(self) -> list[dict]:
        with self._lock:
            services = list(self._services.values())
        # Worst first: an operator scanning the strip should meet the problem
        # before the six things that are fine.
        services.sort(
            key=lambda s: (
                -STATE_PRESENTATION.get(s.state, STATE_PRESENTATION[HealthState.UNKNOWN])["severity"],
                s.name,
            )
        )
        return [s.to_dict() for s in services]

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            health = self._services.get(key)
        return health.to_dict() if health else None

    def worst_severity(self) -> int:
        with self._lock:
            states = [s.state for s in self._services.values()]
        return max(
            (STATE_PRESENTATION.get(s, STATE_PRESENTATION[HealthState.UNKNOWN])["severity"] for s in states),
            default=0,
        )

    def collector_age_seconds(self) -> Optional[int]:
        """How old the health data itself is. Health that has gone stale must be
        visible as such, or the strip becomes a decoration."""
        with self._lock:
            stamps = [s.checked_at for s in self._services.values() if s.checked_at]
        if not stamps:
            return None
        return age_seconds(max(stamps))


#: Process-wide singleton. Created by the app factory; `None` in a bare import so
#: importing this module starts no threads.
_service: Optional[HealthService] = None


def init_health_service(engine, *, start: bool = True) -> HealthService:
    global _service
    if _service is None:
        _service = HealthService(engine)
    if start:
        _service.start()
    return _service


def health_service() -> Optional[HealthService]:
    return _service
