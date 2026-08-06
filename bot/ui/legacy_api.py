"""Legacy ``/api/*`` routes, retained for the Telegram Mini App and the bot.

These are v1. The operational dashboard no longer uses them — it talks to
``/api/v2`` — but the Mini App polls ``/api/platform/analytics/summary`` and the
bot process pushes to ``/api/internal/push``, so removing them would break
shipped consumers.

What changed while keeping the surface:

* **``/api/equity`` no longer fabricates a curve.** It read ``equity_snapshots``,
  and on failure fell through to ``_candle_equity()`` — SBER's daily closes
  normalised to ₽1 000 000 and served as portfolio equity. That fallback is
  deleted, not repaired.
* **No SQL in a handler.** Everything goes through a repository.
* **No writes.** Every route here is a genuine GET.
* **No `200 []` on failure.** Seven routes swallowed every exception and returned
  an empty array, so an outage was indistinguishable from "no data". Failures now
  raise into the one error handler.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from typing import Optional

from flask import Blueprint, Flask, jsonify, request

from qf_platform.contracts import ApiError, ErrorCode, safe_float, to_display

logger = logging.getLogger(__name__)

legacy_bp = Blueprint("legacy", __name__)

_engine = None


def register_legacy_api(app: Flask, *, engine) -> None:
    global _engine
    _engine = engine
    app.register_blueprint(legacy_bp)


def _require_engine():
    if _engine is None:
        raise ApiError(ErrorCode.DB_UNAVAILABLE)
    return _engine


# ── Health ────────────────────────────────────────────────────────────────────

@legacy_bp.get("/health")
def health():
    """Liveness only — public, cheap, and it must never depend on the schema."""
    return jsonify({"status": "ok", "db": _engine is not None})


# ── Broker passthrough ────────────────────────────────────────────────────────

def _tinkoff_error(exc: Exception):
    from services.tinkoff import TinkoffAPIError, TinkoffNotConfigured, TinkoffSDKError

    if isinstance(exc, TinkoffNotConfigured):
        raise ApiError(ErrorCode.BROKER_UNAVAILABLE, detail="Брокер не настроен.")
    if isinstance(exc, (TinkoffSDKError, TinkoffAPIError)):
        raise ApiError(ErrorCode.BROKER_UNAVAILABLE)
    raise ApiError(ErrorCode.BROKER_UNAVAILABLE)


@legacy_bp.get("/api/tinkoff/portfolio")
def api_tinkoff_portfolio():
    from services.tinkoff import get_portfolio_summary

    try:
        summary = get_portfolio_summary()
    except Exception as exc:  # noqa: BLE001
        return _tinkoff_error(exc)
    return jsonify({
        "total_value": summary.total_value,
        "total_yield": summary.total_yield,
        "total_yield_pct": summary.total_yield_pct,
        "positions_count": summary.positions_count,
        "currency": summary.currency,
        "source": "tinkoff",
    })


@legacy_bp.get("/api/tinkoff/positions")
def api_tinkoff_positions():
    from services.tinkoff import get_portfolio_summary

    try:
        summary = get_portfolio_summary()
    except Exception as exc:  # noqa: BLE001
        return _tinkoff_error(exc)
    return jsonify([dataclasses.asdict(p) for p in summary.positions])


@legacy_bp.get("/api/tinkoff/pnl")
def api_tinkoff_pnl():
    from services.tinkoff import get_portfolio_summary

    try:
        summary = get_portfolio_summary()
    except Exception as exc:  # noqa: BLE001
        return _tinkoff_error(exc)
    return jsonify({
        "unrealized": summary.total_yield,
        "unrealized_pct": summary.total_yield_pct,
        "currency": summary.currency,
    })


# ── Statistics ────────────────────────────────────────────────────────────────

@legacy_bp.get("/api/stats")
def api_stats():
    from services.tinkoff import compute_bot_stats

    engine = _require_engine()
    return jsonify(dataclasses.asdict(compute_bot_stats(engine)))


@legacy_bp.get("/api/settings")
def api_settings():
    from config import config

    return jsonify({
        "db": {
            "host": config.db.host,
            "port": config.db.port,
            "name": config.db.name,
            "connected": _engine is not None,
        },
        "risk": {
            "max_position_pct": config.risk.max_position_pct,
            "atr_stop_multiplier": config.risk.atr_stop_multiplier,
            "max_daily_loss_pct": config.risk.max_daily_loss_pct,
            "max_open_positions": config.risk.max_open_positions,
        },
        "app": {
            "tickers": config.tickers,
            "poll_interval": config.poll_interval,
            "log_level": config.log_level,
        },
        "tinkoff": {
            "sandbox": config.tinkoff.sandbox,
            "has_token": bool(config.tinkoff.token),
            "has_account_id": bool(config.tinkoff.account_id),
        },
    })


@legacy_bp.get("/api/settings/tokens")
def api_settings_tokens_get():
    """Configured / not configured only. The value never crosses this boundary."""
    from config import config

    return jsonify({
        "has_tinkoff_token": bool(config.tinkoff.token),
        "has_tinkoff_account_id": bool(config.tinkoff.account_id),
    })


# NOTE: the POST half of /api/settings/tokens is deliberately absent.
# It wrote broker credentials — and its four «Clear» buttons wrote an empty value
# straight to .env — with no confirmation, no CSRF, no permission check and no
# audit row. Credential writes now live at /api/v2/settings/credentials behind the
# administrator role, a typed confirmation and an audit trail.


# ── Market data ───────────────────────────────────────────────────────────────

@legacy_bp.get("/api/candles")
def api_candles():
    from qf_platform.repositories.market_repository import MarketRepository

    engine = _require_engine()
    ticker = (request.args.get("ticker") or "SBER").strip().upper()
    if not ticker.replace(".", "").replace("-", "").isalnum() or len(ticker) > 24:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="ticker")
    try:
        limit = min(max(int(request.args.get("limit", 120)), 1), 365)
    except (TypeError, ValueError):
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="limit")

    rows = MarketRepository(engine).candles(ticker, limit=limit)
    return jsonify([
        {
            "ts": to_display(r["time"]),
            "open": safe_float(r["open"]),
            "high": safe_float(r["high"]),
            "low": safe_float(r["low"]),
            "close": safe_float(r["close"]),
            "volume": int(r["volume"] or 0),
        }
        for r in rows
    ])


@legacy_bp.get("/api/portfolio")
def api_portfolio():
    """Instrument-level market overview, with each quote's own age.

    Renamed in meaning only: it never returned a portfolio, it returned a
    watchlist. The per-ticker `as_of` is new — the previous version dated the row
    with the candle's date but rendered it as a live quote.
    """
    from qf_platform.contracts import age_seconds
    from qf_platform.repositories.market_repository import MarketRepository

    engine = _require_engine()
    repo = MarketRepository(engine)
    result = []
    for row in repo.candle_coverage():
        if row["timeframe"] != "1d":
            continue
        candles = repo.candles(row["ticker"], limit=31)
        if len(candles) < 2:
            continue
        latest = safe_float(candles[-1]["close"])
        previous = safe_float(candles[-2]["close"])
        oldest = safe_float(candles[0]["close"])
        result.append({
            "ticker": row["ticker"],
            "price": latest,
            "change_1d": round((latest - previous) / previous * 100, 2) if previous else None,
            "change_30d": round((latest - oldest) / oldest * 100, 2) if oldest else None,
            "volume": int(candles[-1]["volume"] or 0),
            "as_of": to_display(candles[-1]["time"]),
            "data_age_seconds": age_seconds(candles[-1]["time"]),
        })
    return jsonify(result)


# ── Equity ────────────────────────────────────────────────────────────────────

@legacy_bp.get("/api/equity")
def api_equity():
    """Real equity, or an explicit empty result. Never a candle-derived curve.

    The deleted fallback produced a series running 2025-06-26 → 2025-09-29 ending
    at ₽919 224, while the paper account went ₽10 000 000 → ₽7 626 546. It was the
    largest element on the landing screen and it was SBER's share price.
    """
    from qf_platform.environment import Environment
    from qf_platform.services.equity_service import EquityService

    engine = _require_engine()
    window = (request.args.get("window") or "90d").strip().lower()
    series = EquityService(engine).series(window=window, environment=Environment.SANDBOX)
    return jsonify([
        {"ts": point["ts"], "equity": point["equity"]}
        for point in series.points
    ])


@legacy_bp.get("/api/positions")
def api_positions():
    from qf_platform.environment import Environment
    from qf_platform.services.positions_service import PositionsService

    engine = _require_engine()
    payload = PositionsService(engine).open_positions(environment=Environment.SANDBOX)
    return jsonify([
        {
            "ticker": p["ticker"],
            "entry_price": p["entry_price"],
            # `None` rather than the entry price when there is no quote.
            "current_price": p["mark_price"],
            "current_price_as_of": p["mark_as_of"],
            "current_price_is_stale": p["mark_is_stale"],
            "shares": p["quantity"],
            "pnl": p["unrealized_pnl"],
            "pnl_pct": p["unrealized_pnl_pct"],
            "stop_price": p["stop_loss"],
            "distance_to_stop_pct": p["distance_to_stop_pct"],
            "environment": p["environment"],
        }
        for p in payload["positions"]
    ])


@legacy_bp.get("/api/metrics")
def api_metrics():
    """Account metrics. Every figure carries its sample size."""
    from qf_platform.environment import Environment
    from qf_platform.services.equity_service import EquityService
    from qf_platform.services.metrics_service import MetricsService

    engine = _require_engine()
    metrics = MetricsService(engine)
    equity_svc = EquityService(engine)

    stats = metrics.trade_statistics(period="all", environment=Environment.SANDBOX)
    pnl = metrics.pnl_windows()
    drawdown = equity_svc.drawdown(window="all", environment=Environment.SANDBOX)
    risk_adjusted = equity_svc.risk_adjusted(environment=Environment.SANDBOX)
    series = equity_svc.series(window="all", environment=Environment.SANDBOX)

    day = (pnl.get("windows") or {}).get("day") or {}
    return jsonify({
        "portfolio_value": series.last_equity,
        "pnl_today": day.get("pnl"),
        "pnl_today_n": day.get("n", 0),
        "drawdown_pct": drawdown["max_drawdown_pct"],
        "drawdown_abs": drawdown["max_drawdown_abs"],
        "drawdown_n": drawdown["n"],
        "sharpe_ratio": risk_adjusted["sharpe_ratio"],
        "sharpe_n": risk_adjusted["n"],
        "total_trades": stats.get("n", 0),
        "win_rate": stats.get("win_rate_pct"),
        "win_rate_n": stats.get("win_rate_n", 0),
        "environment": Environment.SANDBOX.value,
        "currency": series.currency,
    })


@legacy_bp.get("/api/log")
def api_log():
    """Real system events. Was reading the `news` table and inferring a log level
    from article sentiment, which is not a system log by any definition."""
    from qf_platform.repositories.events_repository import EventsRepository

    engine = _require_engine()
    rows = EventsRepository(engine).list_events(limit=50)
    return jsonify([
        {
            "ts": to_display(r["created_at"]),
            "level": r["level"],
            "source": r["source"],
            "message": r["message"],
        }
        for r in rows
    ])


# ── Internal push (bot → dashboard SSE) ───────────────────────────────────────

_INTERNAL_TOKEN = os.getenv("QF_INTERNAL_TOKEN", "")


@legacy_bp.post("/api/internal/push")
def api_internal_push():
    """Trade events from the bot process, rebroadcast over SSE.

    Shared-token authenticated, falling back to loopback-only. Uses the real TCP
    peer: ``X-Forwarded-For`` is client-supplied and a remote caller could set it
    to ``127.0.0.1`` to pass the loopback check.
    """
    import hmac

    from realtime.sse_hub import sse_hub

    if _INTERNAL_TOKEN:
        provided = request.headers.get("X-Internal-Token", "")
        if not hmac.compare_digest(provided, _INTERNAL_TOKEN):
            raise ApiError(ErrorCode.UNAUTHENTICATED)
    else:
        host = request.remote_addr or ""
        if host not in {"127.0.0.1", "::1", "localhost", ""}:
            raise ApiError(ErrorCode.UNAUTHENTICATED)

    data = request.get_json(silent=True) or {}
    event_type = data.pop("event_type", "trade_executed")
    sse_hub.publish(event_type, data)
    return jsonify({"ok": True})
