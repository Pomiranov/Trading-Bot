"""Platform API routes — portfolio, signals, backtest, overview."""

from __future__ import annotations

import json
import logging
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from qf_platform.dto import BacktestRequestDTO, to_dict
from qf_platform.services.backtest_service import BacktestService
from qf_platform.services.dashboard_service import DashboardService
from qf_platform.services.paper_trading_service import PaperTradingService
from qf_platform.services.portfolio_service import PortfolioService
from qf_platform.services.signals_service import SignalsService
from realtime.sse_hub import sse_hub

logger = logging.getLogger(__name__)

platform_bp = Blueprint("platform", __name__, url_prefix="/api/platform")

_engine = None


def init_platform_routes(engine) -> Blueprint:
    global _engine
    _engine = engine
    return platform_bp


def _require_engine():
    if _engine is None:
        return jsonify({"error": "DB not available"}), 503
    return None


@platform_bp.route("/overview")
def api_overview():
    err = _require_engine()
    if err:
        return err
    svc = DashboardService(_engine)
    return jsonify(to_dict(svc.get_overview()))


@platform_bp.route("/portfolio")
def api_portfolio_summary():
    err = _require_engine()
    if err:
        return err
    mode = request.args.get("mode", "rub")
    svc = PortfolioService(_engine)
    return jsonify(to_dict(svc.get_summary(mode=mode)))


@platform_bp.route("/portfolio/positions")
def api_portfolio_positions():
    err = _require_engine()
    if err:
        return err
    svc = PortfolioService(_engine)
    summary = svc.get_summary()
    positions = summary.best_positions + [
        p for p in summary.worst_positions
        if p not in summary.best_positions
    ]
    seen = set()
    unique = []
    for p in positions:
        key = p.get("ticker")
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return jsonify({
        "positions": unique,
        "source": summary.source,
        "count": summary.open_positions_count,
    })


@platform_bp.route("/signals")
def api_signals_list():
    err = _require_engine()
    if err:
        return err
    svc = SignalsService(_engine)
    signals = svc.list_signals(
        exchange=request.args.get("exchange"),
        asset_class=request.args.get("asset_class"),
        status=request.args.get("status"),
        limit=int(request.args.get("limit", 100)),
    )
    return jsonify([to_dict(s) for s in signals])


@platform_bp.route("/signals/generate", methods=["POST"])
def api_signals_generate():
    err = _require_engine()
    if err:
        return err
    svc = SignalsService(_engine)
    signals = svc.generate_live_signals(persist=True)
    sse_hub.publish("signals_updated", {"count": len(signals)})
    return jsonify([to_dict(s) for s in signals])


@platform_bp.route("/signals/<int:signal_id>/execute", methods=["POST"])
def api_signal_execute(signal_id: int):
    err = _require_engine()
    if err:
        return err
    try:
        svc = SignalsService(_engine)
        result = svc.execute_signal(signal_id)
        sse_hub.publish("trade_executed", {"signal_id": signal_id, **result})
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.warning("Signal execute error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@platform_bp.route("/paper/account")
def api_paper_account():
    err = _require_engine()
    if err:
        return err
    mode = request.args.get("mode", "rub")
    svc = PaperTradingService(_engine)
    account = svc.get_account(mode=mode)
    positions = svc.refresh_positions(int(account["id"]))
    return jsonify({
        "account": {k: (float(v) if k in ("balance", "available_balance", "margin_used", "initial_balance") else v)
                    for k, v in account.items() if k != "updated_at"},
        "positions": positions,
    })


@platform_bp.route("/paper/trade", methods=["POST"])
def api_paper_trade():
    err = _require_engine()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    svc = PaperTradingService(_engine)
    account = svc.get_account(mode=body.get("mode", "rub"))
    try:
        if body.get("action") == "close":
            result = svc.close_position(int(body["position_id"]))
        else:
            result = svc.open_position(
                account_id=int(account["id"]),
                ticker=body.get("ticker", "SBER"),
                direction=body.get("direction", "long"),
                quantity=body.get("quantity"),
                stop_loss=body.get("stop_loss"),
                take_profit=body.get("take_profit"),
            )
        sse_hub.publish("portfolio_updated", result)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@platform_bp.route("/backtest/run", methods=["POST"])
def api_backtest_run():
    err = _require_engine()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    req = BacktestRequestDTO(
        strategy=body.get("strategy", "rules_engine"),
        exchange=body.get("exchange", "moex"),
        ticker=body.get("ticker", "SBER"),
        period_start=body.get("period_start"),
        period_end=body.get("period_end"),
        initial_capital=float(body.get("initial_capital", 1_000_000)),
        risk_pct=float(body.get("risk_pct", 0.05)),
        commission_pct=float(body.get("commission_pct", 0.0003)),
        slippage_pct=float(body.get("slippage_pct", 0.0001)),
        leverage=float(body.get("leverage", 1)),
    )
    try:
        svc = BacktestService(_engine)
        result = svc.run(req)
        sse_hub.publish("backtest_complete", {"run_id": result.run_id, "ticker": result.ticker})
        return jsonify(to_dict(result))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.warning("Backtest error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/backtest/runs")
def api_backtest_runs():
    err = _require_engine()
    if err:
        return err
    svc = BacktestService(_engine)
    return jsonify(svc.list_runs())


@platform_bp.route("/backtest/runs/<int:run_id>/export")
def api_backtest_export(run_id: int):
    err = _require_engine()
    if err:
        return err
    svc = BacktestService(_engine)
    data = svc.export_run(run_id)
    if not data:
        return jsonify({"error": "Run not found"}), 404
    return Response(
        json.dumps(data, default=str, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=backtest_{run_id}.json"},
    )


@platform_bp.route("/health")
def api_system_health():
    from qf_platform.services.system_health_service import SystemHealthService
    svc = SystemHealthService(_engine)
    return jsonify(svc.get_health())


@platform_bp.route("/brokers")
def api_brokers():
    err = _require_engine()
    if err:
        return err
    svc = DashboardService(_engine)
    overview = svc.get_overview()
    return jsonify([to_dict(b) for b in overview.brokers])


@platform_bp.route("/stream")
def api_sse_stream():
    """SSE endpoint for real-time updates."""

    def generate():
        q = sse_hub.subscribe()
        try:
            yield sse_hub.format_sse({
                "type": "connected",
                "data": {"clients": sse_hub.client_count},
                "ts": time.time(),
            })
            while True:
                try:
                    payload = q.get(timeout=25)
                    yield sse_hub.format_sse(payload)
                except Exception:
                    yield ": keepalive\n\n"
        finally:
            sse_hub.unsubscribe(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )