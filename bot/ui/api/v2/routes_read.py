"""Read routes. Every one is genuinely read-only.

The old ``/paper/account``, ``/portfolio``, ``/overview`` and ``/signals``
inserted an ``equity_snapshots`` row and updated ``paper_accounts`` /
``paper_positions`` as a side effect of being read; ``/signals`` inserted into
``trading_signals`` when its query came back empty. Nothing below writes, and the
read-only launch mode installs a connection-level guard that proves it.
"""

from __future__ import annotations

import logging

from flask import request

from qf_platform.contracts import (
    EmptyReason,
    Freshness,
    Meta,
    Units,
    envelope,
)
from qf_platform.environment import Environment
from qf_platform.repositories.events_repository import EventsRepository
from qf_platform.repositories.market_repository import MarketRepository
from qf_platform.services.environment_service import EnvironmentService
from qf_platform.services.equity_service import EquityService
from qf_platform.services.faults_service import FaultsService
from qf_platform.services.gate_service import GateService
from qf_platform.services.health_service import health_service
from qf_platform.services.metrics_service import MetricsService
from qf_platform.services.positions_service import PositionsService
from qf_platform.services.risk_service import RiskService
from qf_platform.services.strategy_service import StrategyService
from qf_platform.services.trades_service import TradesService
from security.guards import require_auth, require_permission
from security.permissions import Permission
from security.session_auth import current_principal

from . import (
    arg_direction,
    arg_environment,
    arg_limit,
    arg_offset,
    arg_period,
    arg_result,
    arg_sort,
    arg_strategy,
    arg_ticker,
    arg_window,
    engine_or_fail,
    engine_unchecked,
    remember_environment,
    schema_is_current,
    v2,
)

logger = logging.getLogger(__name__)


# ── Environment band ──────────────────────────────────────────────────────────

@v2.get("/environment")
@require_auth
def get_environment():
    """Tier 1 of the Overview. Must answer even when the schema is stale.

    The whole point of this endpoint is to tell the operator what they are
    looking at, so it is the last thing that should refuse to respond.
    """
    engine = engine_unchecked()
    if engine is None:
        # No database: the environment is genuinely undetermined. Reporting
        # UNKNOWN is correct; reporting SANDBOX would be a guess.
        return envelope(
            {
                "environment": Environment.UNKNOWN.value,
                "environment_label": "СРЕДА НЕ ОПРЕДЕЛЕНА",
                "is_environment_fault": True,
                "conflicts": ["База данных недоступна."],
            },
            Meta(environment=Environment.UNKNOWN, units=Units.ENUM),
        )

    snapshot = EnvironmentService(engine).snapshot()
    remember_environment(snapshot.environment)

    payload = snapshot.to_dict()
    payload["schema_current"] = schema_is_current()
    principal = current_principal()
    payload["session"] = principal.to_public_dict() if principal else None

    return envelope(
        payload,
        Meta(
            environment=snapshot.environment,
            units=Units.ENUM,
            freshness=snapshot.freshness(),
        ),
    )


@v2.get("/faults")
@require_auth
def get_faults():
    engine = engine_unchecked()
    env_snapshot = None
    risk_status = None
    report = None

    if engine is not None:
        try:
            env_snapshot = EnvironmentService(engine).snapshot()
        except Exception:  # noqa: BLE001 — a fault list that 500s is useless
            logger.warning("Fault region: environment snapshot failed", exc_info=True)
        if schema_is_current():
            try:
                risk_status = RiskService(engine).status(
                    environment=env_snapshot.environment if env_snapshot else Environment.SANDBOX
                )
            except Exception:  # noqa: BLE001
                logger.warning("Fault region: risk status failed", exc_info=True)
        from qf_platform.bootstrap import schema_report

        report = schema_report(engine)

    payload = FaultsService(engine).faults(
        environment_snapshot=env_snapshot,
        risk_status=risk_status,
        schema_report=report,
    )
    return envelope(
        payload,
        Meta(
            environment=env_snapshot.environment if env_snapshot else Environment.UNKNOWN,
            n=payload["total"],
            units=Units.COUNT,
        ),
    )


@v2.get("/health")
@require_auth
def get_health():
    """Cached snapshot. No probe runs on this request path."""
    svc = health_service()
    if svc is None:
        return envelope(
            {"services": [], "collector_age_seconds": None},
            Meta(environment=Environment.UNKNOWN, empty_reason=EmptyReason.NOT_CONFIGURED),
        )
    services = svc.snapshot()
    return envelope(
        {
            "services": services,
            "worst_severity": svc.worst_severity(),
            # Health that has itself gone stale must be visible as such.
            "collector_age_seconds": svc.collector_age_seconds(),
            "latency": svc.latency.percentiles(),
        },
        Meta(environment=arg_environment(), n=len(services), units=Units.ENUM),
    )


# ── Capital ───────────────────────────────────────────────────────────────────

@v2.get("/equity")
@require_auth
def get_equity():
    engine = engine_or_fail()
    environment = arg_environment()
    window = arg_window()
    series = EquityService(engine).series(window=window, environment=environment)
    return envelope(
        series.to_dict(),
        Meta(
            environment=series.environment,
            units=Units.MONEY,
            currency=series.currency,
            n=series.observations,
            window=series.window_label,
            freshness=series.freshness(),
            empty_reason=series.empty_reason,
        ),
    )


@v2.get("/equity/underwater")
@require_auth
def get_underwater():
    engine = engine_or_fail()
    environment = arg_environment()
    window = arg_window()
    svc = EquityService(engine)
    points = svc.underwater(window=window, environment=environment)
    return envelope(
        {"points": points, "window": window},
        Meta(environment=environment, units=Units.PERCENT, n=len(points)),
    )


@v2.get("/drawdown")
@require_auth
def get_drawdown():
    engine = engine_or_fail()
    environment = arg_environment()
    payload = EquityService(engine).drawdown(window=arg_window(), environment=environment)
    return envelope(
        payload,
        Meta(
            environment=environment,
            currency=payload["currency"],
            n=payload["n"],
            window=payload["window_label"],
            # Units are per-field here — pct and abs live side by side, which is
            # the entire point of splitting the old `max_drawdown`.
            extra={"units_by_field": payload["units"]},
        ),
    )


@v2.get("/accounts")
@require_auth
def get_accounts():
    engine = engine_or_fail()
    payload = TradesService(engine).accounts_summary()
    return envelope(
        payload,
        Meta(environment=arg_environment(), n=payload["count"], units=Units.MONEY),
    )


@v2.get("/portfolio")
@require_auth
def get_portfolio():
    """Account state, exposure, allocation and attribution.

    Composed from named slices rather than one merged blob, and each slice
    reports its own failure. ``Promise.allSettled`` on the client used to drop a
    failed slice and still stamp the screen "live"; here a missing slice is named
    in ``meta.missing`` and the response is marked partial.
    """
    engine = engine_or_fail()
    environment = arg_environment()
    period = arg_period("30d")

    positions_svc = PositionsService(engine)
    metrics_svc = MetricsService(engine)
    equity_svc = EquityService(engine)
    trades_svc = TradesService(engine)

    missing: dict[str, str] = {}

    def attempt(name: str, fn, fallback):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("portfolio slice %s failed: %s", name, exc)
            missing[name] = "Не удалось загрузить."
            return fallback

    accounts = attempt("accounts", trades_svc.accounts_summary, {"accounts": [], "count": 0})
    positions = attempt(
        "positions",
        lambda: positions_svc.open_positions(environment=environment),
        {"positions": [], "count": 0, "totals": {}},
    )
    stats = attempt(
        "statistics",
        lambda: metrics_svc.trade_statistics(period=period, environment=environment),
        {},
    )
    pnl = attempt("pnl_windows", metrics_svc.pnl_windows, {"windows": {}})
    drawdown = attempt(
        "drawdown",
        lambda: equity_svc.drawdown(window=arg_window(), environment=environment),
        {},
    )
    risk_adjusted = attempt(
        "risk_adjusted",
        lambda: equity_svc.risk_adjusted(environment=environment),
        {},
    )
    attribution = attempt(
        "attribution",
        lambda: metrics_svc.ticker_breakdown(period=period, environment=environment),
        [],
    )

    allocation = []
    total_value = sum(p.get("position_value") or 0 for p in positions.get("positions", []))
    for item in positions.get("positions", []):
        value = item.get("position_value") or 0
        allocation.append({
            "label": item["ticker"],
            "value": round(value, 2),
            "pct": round(value / total_value * 100.0, 2) if total_value else None,
        })
    allocation.sort(key=lambda a: -(a["value"] or 0))

    currency = (
        accounts["accounts"][0]["currency"] if accounts.get("accounts") else "RUB"
    )

    return envelope(
        {
            "accounts": accounts["accounts"],
            "positions": positions,
            "statistics": stats,
            "pnl_windows": pnl,
            "drawdown": drawdown,
            "risk_adjusted": risk_adjusted,
            "allocation": allocation,
            "attribution": attribution,
            "period": period,
        },
        Meta(
            environment=environment,
            currency=currency,
            n=stats.get("n"),
            window=stats.get("period_label"),
            partial=bool(missing),
            missing=missing,
        ),
    )


# ── Positions ─────────────────────────────────────────────────────────────────

@v2.get("/positions")
@require_auth
def get_positions():
    engine = engine_or_fail()
    environment = arg_environment()
    payload = PositionsService(engine).open_positions(environment=environment)
    freshness = Freshness(
        source_as_of=None,
        source="candles",
        stale_after_seconds=(payload.get("quote_freshness") or {}).get("stale_after_seconds"),
    )
    return envelope(
        payload,
        Meta(
            environment=environment,
            currency=payload["currency"],
            n=payload["count"],
            units=Units.MONEY,
            freshness=freshness,
            empty_reason=payload.get("empty_reason"),
        ),
    )


# ── Trades ────────────────────────────────────────────────────────────────────

_TRADE_SORTS = {
    "closed_at", "opened_at", "ticker", "pnl", "pnl_pct", "quantity",
    "entry_price", "exit_price", "commission", "direction",
}


@v2.get("/trades")
@require_auth
def get_trades():
    engine = engine_or_fail()
    environment = arg_environment()
    sort, descending = arg_sort(_TRADE_SORTS, "closed_at")
    svc = TradesService(engine)
    payload = svc.closed_trades(
        period=arg_period("30d"),
        ticker=arg_ticker(),
        direction=arg_direction(),
        result=arg_result(),
        environment=environment,
        sort=sort,
        descending=descending,
        limit=arg_limit(200, 500),
        offset=arg_offset(),
    )
    freshness = svc.freshness(payload)
    payload.pop("_source_as_of", None)
    return envelope(
        payload,
        Meta(
            environment=environment,
            currency=payload["currency"],
            n=payload["total"],
            window=payload["period_label"],
            freshness=freshness,
            empty_reason=payload.get("empty_reason"),
        ),
    )


@v2.get("/trades/learning")
@require_auth
def get_learning_trades():
    engine = engine_or_fail()
    payload = TradesService(engine).learning_trades(
        limit=arg_limit(100, 500),
        environment=arg_environment(Environment.SANDBOX),
        strategy_id=arg_strategy(),
    )
    return envelope(
        payload,
        Meta(environment=arg_environment(), n=payload["total"]),
    )


@v2.get("/statistics")
@require_auth
def get_statistics():
    engine = engine_or_fail()
    environment = arg_environment()
    period = arg_period("all")
    payload = MetricsService(engine).trade_statistics(period=period, environment=environment)
    return envelope(
        payload,
        Meta(
            environment=environment,
            currency=payload.get("currency"),
            n=payload.get("n"),
            window=payload.get("period_label"),
            empty_reason=payload.get("empty_reason"),
            extra={"units_by_field": payload.get("units", {})},
        ),
    )


@v2.get("/statistics/distribution")
@require_auth
def get_distribution():
    engine = engine_or_fail()
    environment = arg_environment()
    payload = MetricsService(engine).distribution(
        period=arg_period("all"), environment=environment
    )
    return envelope(
        payload,
        Meta(environment=environment, n=payload["n"], units=Units.MONEY),
    )


@v2.get("/analytics/daily")
@require_auth
def get_daily_pnl():
    engine = engine_or_fail()
    environment = arg_environment()
    points = EquityService(engine).daily_pnl(days=30, environment=environment)
    return envelope(
        {"points": points},
        Meta(environment=environment, n=len(points), units=Units.MONEY, window="30 дней"),
    )


# ── Signals and the gate ──────────────────────────────────────────────────────

@v2.get("/signals")
@require_auth
def get_signals():
    engine = engine_or_fail()
    environment = arg_environment()
    svc = GateService(engine)
    payload = svc.timeline(
        limit=arg_limit(100, 500),
        environment=environment,
        decision=(request.args.get("decision") or "").strip().lower() or None,
        ticker=arg_ticker(),
        strategy_id=arg_strategy(),
    )
    payload.update(svc.gate_summary(environment=environment))
    freshness = svc.freshness(payload)
    payload.pop("_source_as_of", None)
    return envelope(
        payload,
        Meta(
            environment=environment,
            n=payload["count"],
            freshness=freshness,
            empty_reason=payload.get("empty_reason"),
        ),
    )


# ── Strategies ────────────────────────────────────────────────────────────────

@v2.get("/strategies")
@require_auth
def get_strategies():
    engine = engine_or_fail()
    environment = arg_environment()
    svc = StrategyService(engine)
    payload = svc.board(environment=environment)
    freshness = svc.freshness(payload)
    payload.pop("_source_as_of", None)
    return envelope(
        payload,
        Meta(
            environment=environment,
            n=payload["count"],
            freshness=freshness,
            empty_reason=payload.get("empty_reason"),
            extra={"units_by_field": payload.get("units", {})},
        ),
    )


@v2.get("/strategies/<strategy_id>")
@require_auth
def get_strategy_detail(strategy_id: str):
    from qf_platform.contracts import ApiError, ErrorCode

    engine = engine_or_fail()
    payload = StrategyService(engine).detail(strategy_id)
    if payload is None:
        raise ApiError(ErrorCode.NOT_FOUND)
    return envelope(
        payload,
        Meta(environment=arg_environment(), n=payload.get("sample_size")),
    )


@v2.get("/strategies/decisions")
@require_auth
def get_decision_quality():
    engine = engine_or_fail()
    payload = StrategyService(engine).decision_quality(limit=arg_limit(100, 300))
    return envelope(
        payload,
        Meta(
            environment=arg_environment(),
            n=payload["n"],
            units=Units.RATIO,
            empty_reason=payload.get("empty_reason"),
        ),
    )


@v2.get("/hypotheses")
@require_auth
def get_hypotheses():
    engine = engine_or_fail()
    payload = StrategyService(engine).hypotheses(
        stage=(request.args.get("stage") or "").strip().lower() or None
    )
    return envelope(
        payload,
        Meta(
            environment=arg_environment(),
            n=payload["total"],
            empty_reason=payload.get("empty_reason"),
        ),
    )


# ── Risk ──────────────────────────────────────────────────────────────────────

@v2.get("/risk")
@require_auth
def get_risk():
    engine = engine_or_fail()
    environment = arg_environment()
    payload = RiskService(engine).status(environment=environment, window=arg_window())
    return envelope(
        payload,
        Meta(
            environment=environment,
            currency=payload["currency"],
            n=payload["drawdown"]["n"],
            extra={"units_by_field": payload.get("units", {})},
        ),
    )


@v2.get("/risk/events")
@require_auth
def get_risk_events():
    from qf_platform.contracts import to_display

    engine = engine_or_fail()
    rows = RiskService(engine).risk_events(limit=arg_limit(50, 200))
    for row in rows:
        row["occurred_at"] = to_display(row["occurred_at"])
    return envelope(
        {"events": rows, "count": len(rows)},
        Meta(
            environment=arg_environment(),
            n=len(rows),
            empty_reason=None if rows else EmptyReason.NO_EVENTS,
        ),
    )


# ── Event log ─────────────────────────────────────────────────────────────────

@v2.get("/events")
@require_auth
def get_events():
    from qf_platform.contracts import to_display

    engine = engine_or_fail()
    repo = EventsRepository(engine)
    levels = [
        lvl.strip().upper()
        for lvl in (request.args.get("level") or "").split(",")
        if lvl.strip()
    ]
    since = None
    if request.args.get("hours"):
        try:
            since = repo.window_since(max(1, min(720, int(request.args["hours"]))))
        except (TypeError, ValueError):
            from qf_platform.contracts import ApiError, ErrorCode

            raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="hours")

    rows = repo.list_events(
        limit=arg_limit(150, 500),
        levels=levels or None,
        source=(request.args.get("source") or "").strip() or None,
        category=(request.args.get("category") or "").strip() or None,
        correlation_id=(request.args.get("correlation_id") or "").strip() or None,
        since=since,
        search=(request.args.get("q") or "").strip()[:120] or None,
    )
    events = [
        {
            "id": int(row["id"]),
            "created_at": to_display(row["created_at"]),
            "level": row["level"],
            "source": row["source"],
            "category": row["category"],
            "message": row["message"],
            "metadata": row.get("metadata"),
            "correlation_id": row.get("correlation_id"),
            "environment": row.get("environment"),
        }
        for row in rows
    ]
    return envelope(
        {
            "events": events,
            "count": len(events),
            "sources": repo.distinct_sources(),
            "level_census": {r["level"]: int(r["n"]) for r in repo.level_census(hours=24)},
            "empty_reason": None if events else EmptyReason.NO_EVENTS,
        },
        Meta(environment=arg_environment(), n=len(events)),
    )


@v2.get("/audit")
@require_permission(Permission.VIEW_AUDIT)
def get_audit():
    from qf_platform.contracts import to_display

    engine = engine_or_fail()
    repo = EventsRepository(engine)
    rows = repo.list_audit(
        limit=arg_limit(150, 500),
        event_type=(request.args.get("event_type") or "").strip() or None,
        actor_id=(request.args.get("actor") or "").strip() or None,
        outcome=(request.args.get("outcome") or "").strip() or None,
    )
    for row in rows:
        row["event_time"] = to_display(row["event_time"])
        row["id"] = int(row["id"])
    return envelope(
        {
            "events": rows,
            "count": len(rows),
            "census": [
                {"event_type": r["event_type"], "outcome": r["outcome"], "n": int(r["n"])}
                for r in repo.audit_type_census()
            ],
            "empty_reason": None if rows else EmptyReason.NO_EVENTS,
        },
        Meta(environment=arg_environment(), n=len(rows)),
    )


# ── Market data ───────────────────────────────────────────────────────────────

@v2.get("/market/coverage")
@require_auth
def get_market_coverage():
    from qf_platform.contracts import age_seconds, to_display
    from qf_platform.services.environment_service import stale_threshold

    engine = engine_or_fail()
    rows = MarketRepository(engine).candle_coverage()
    instruments = []
    for row in rows:
        newest = row.get("newest")
        age = age_seconds(newest) if newest else None
        threshold = stale_threshold(row.get("timeframe"))
        instruments.append({
            "ticker": row["ticker"],
            "timeframe": row["timeframe"],
            "bars": int(row["bars"]),
            "newest": to_display(newest),
            "oldest": to_display(row.get("oldest")),
            "age_seconds": age,
            "stale_after_seconds": threshold,
            "is_stale": None if age is None else age > threshold,
        })
    instruments.sort(key=lambda i: -(i["age_seconds"] or 0))
    return envelope(
        {"instruments": instruments, "count": len(instruments)},
        Meta(environment=arg_environment(), n=len(instruments), units=Units.COUNT),
    )


@v2.get("/market/candles")
@require_auth
def get_candles():
    from qf_platform.contracts import ApiError, ErrorCode, age_seconds, safe_float, to_display

    engine = engine_or_fail()
    ticker = arg_ticker()
    if not ticker:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="ticker")
    rows = MarketRepository(engine).candles(ticker, limit=arg_limit(180, 400))
    newest = rows[-1]["time"] if rows else None
    return envelope(
        {
            "ticker": ticker,
            "candles": [
                {
                    "ts": to_display(row["time"]),
                    "open": safe_float(row["open"]),
                    "high": safe_float(row["high"]),
                    "low": safe_float(row["low"]),
                    "close": safe_float(row["close"]),
                    "volume": int(row["volume"] or 0),
                }
                for row in rows
            ],
        },
        Meta(
            environment=arg_environment(),
            units=Units.PRICE,
            n=len(rows),
            freshness=Freshness(source_as_of=newest, source="candles", stale_after_seconds=129600),
            empty_reason=None if rows else EmptyReason.NOT_CONFIGURED,
        ),
    )


# ── Overview: one request, named slices ───────────────────────────────────────

@v2.get("/overview")
@require_auth
def get_overview():
    """Everything the Overview needs, in one request.

    Nine separate calls every twelve seconds was the old client's batch, four of
    which independently recomputed the whole paper portfolio. One composed
    response cuts the idle request rate by roughly an order of magnitude, and —
    more importantly — makes partial failure explicit: each slice either arrives
    or is named in ``meta.missing``, so the screen can never be stamped "live"
    while part of it is stale.
    """
    engine = engine_unchecked()
    missing: dict[str, str] = {}

    env_snapshot = None
    if engine is not None:
        try:
            env_snapshot = EnvironmentService(engine).snapshot()
        except Exception as exc:  # noqa: BLE001
            logger.warning("overview: environment failed: %s", exc)
            missing["environment"] = "Не удалось определить среду."

    environment = env_snapshot.environment if env_snapshot else Environment.UNKNOWN
    remember_environment(environment)
    # A screen whose environment is unknown must not silently query as sandbox.
    query_env = environment if environment is not Environment.UNKNOWN else Environment.SANDBOX

    def attempt(name: str, fn, fallback):
        if engine is None or not schema_is_current():
            missing[name] = (
                "База данных недоступна." if engine is None
                else "Схема БД устарела."
            )
            return fallback
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("overview slice %s failed: %s", name, exc)
            missing[name] = "Не удалось загрузить."
            return fallback

    positions = attempt(
        "positions",
        lambda: PositionsService(engine).open_positions(environment=query_env),
        {"positions": [], "count": 0, "totals": {}, "empty_reason": EmptyReason.NO_POSITIONS},
    )
    risk = attempt("risk", lambda: RiskService(engine).status(environment=query_env), {})
    equity = attempt(
        "equity",
        lambda: EquityService(engine).series(window="90d", environment=query_env).to_dict(),
        {"points": [], "observations": 0},
    )
    pnl = attempt("pnl", lambda: MetricsService(engine).pnl_windows(), {"windows": {}})
    latest_signal = attempt(
        "latest_signal", lambda: GateService(engine).latest(environment=query_env), None
    )
    gate = attempt(
        "gate", lambda: GateService(engine).gate_summary(environment=query_env), {}
    )

    svc = health_service()
    health = svc.snapshot() if svc else []
    if svc is None:
        missing["health"] = "Сбор метрик не запущен."

    from qf_platform.bootstrap import schema_report

    faults = FaultsService(engine).faults(
        environment_snapshot=env_snapshot,
        risk_status=risk,
        schema_report=schema_report(engine) if engine is not None else None,
    )

    return envelope(
        {
            "environment": env_snapshot.to_dict() if env_snapshot else None,
            "faults": faults,
            "risk": risk,
            "positions": positions,
            "equity": equity,
            "pnl": pnl,
            "latest_signal": latest_signal,
            "gate": gate,
            "health": {
                "services": health,
                "collector_age_seconds": svc.collector_age_seconds() if svc else None,
                "latency": svc.latency.percentiles() if svc else None,
            },
            "schema_current": schema_is_current(),
        },
        Meta(
            environment=environment,
            currency=(positions.get("currency") or "RUB"),
            freshness=env_snapshot.freshness() if env_snapshot else Freshness(),
            partial=bool(missing),
            missing=missing,
        ),
    )
