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
from qf_platform.services.analytics_service import AnalyticsService
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
    try:
        limit = min(max(int(request.args.get("limit", 100) or 100), 1), 1000)
    except (ValueError, TypeError):
        limit = 100
    svc = SignalsService(_engine)
    # persist_on_empty=False: this GET used to fall through to
    # `generate_live_signals(persist=True)` when the query came back empty, so
    # eight of the rows in `trading_signals` are artefacts of dashboard polling
    # rather than of market events. A signal table that a viewer can write to
    # cannot be presented as a decision record.
    signals = svc.list_signals(
        exchange=request.args.get("exchange"),
        asset_class=request.args.get("asset_class"),
        status=request.args.get("status"),
        limit=limit,
        persist_on_empty=False,
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
    """Read-only. Was `refresh_positions`, which INSERTed an equity_snapshots row
    and UPDATEd paper_accounts/paper_positions on every GET."""
    err = _require_engine()
    if err:
        return err
    mode = request.args.get("mode", "rub")
    svc = PaperTradingService(_engine)
    account = svc.get_account(mode=mode)
    positions, totals = svc.compute_positions(int(account["id"]))
    return jsonify({
        "account": {k: (float(v) if k in ("balance", "available_balance", "margin_used", "initial_balance") else v)
                    for k, v in account.items() if k != "updated_at"},
        "positions": positions,
        "computed": {k: round(v, 2) if isinstance(v, float) else v for k, v in totals.items()},
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


@platform_bp.route("/engine/status")
def api_engine_status():
    from engine.paper_engine import paper_engine
    return jsonify(paper_engine.status())


@platform_bp.route("/engine/start", methods=["POST"])
def api_engine_start():
    err = _require_engine()
    if err:
        return err
    from engine.paper_engine import paper_engine
    paper_engine.start(db_engine=_engine)
    return jsonify({"ok": True, "running": paper_engine.is_running()})


@platform_bp.route("/engine/stop", methods=["POST"])
def api_engine_stop():
    from engine.paper_engine import paper_engine
    paper_engine.stop()
    return jsonify({"ok": True, "running": paper_engine.is_running()})


@platform_bp.route("/analytics")
def api_analytics():
    err = _require_engine()
    if err:
        return err
    svc = AnalyticsService(_engine)
    return jsonify(svc.full_report())


@platform_bp.route("/paper/trades")
def api_paper_trades():
    err = _require_engine()
    if err:
        return err
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 500)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid limit or offset"}), 400
    # The envelope mismatch that made «История Paper Trades» permanently empty:
    # this route returned a bare array while the client read `payload.trades`, so
    # 35 existing rows rendered as zero. It now returns the object the client
    # expects, with the total so «N из M» is possible instead of silent truncation.
    from qf_platform.repositories.trades_repository import TradesRepository

    repo = TradesRepository(_engine)
    aid = repo.default_account_id()
    if aid is None:
        return jsonify({"trades": [], "total": 0, "returned": 0, "offset": offset})

    rows = repo.paper_trades(aid, period="all", limit=limit, offset=offset)
    total = repo.paper_trades_count(aid, period="all")
    return jsonify({
        "trades": [
            {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}
            for row in rows
        ],
        "total": total,
        "returned": len(rows),
        "offset": offset,
    })


@platform_bp.route("/paper/position/<int:pos_id>/close", methods=["POST"])
def api_paper_position_close(pos_id: int):
    err = _require_engine()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "manual")
    from engine.paper_engine import paper_engine
    paper_engine.set_db_engine(_engine)
    try:
        result = paper_engine.close_trade(pos_id, reason=reason)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.warning("position close error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@platform_bp.route("/paper/position/<int:pos_id>/partial", methods=["POST"])
def api_paper_position_partial(pos_id: int):
    err = _require_engine()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    qty_pct = float(body.get("qty_pct", 0.5))
    from engine.paper_engine import paper_engine
    paper_engine.set_db_engine(_engine)
    try:
        result = paper_engine.close_trade_partial(pos_id, qty_pct=qty_pct)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.warning("partial close error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@platform_bp.route("/risk/status")
def api_risk_status():
    """Current risk manager state — positions, daily PnL, limits."""
    try:
        from risk.risk_manager import risk_manager
        from config import config
        open_pos = risk_manager.open_positions
        return jsonify({
            "open_positions": [
                {
                    "ticker": ticker,
                    "entry_price": ps.entry_price,
                    "stop_price": ps.stop_price,
                    "shares": ps.shares,
                    "risk_amount": ps.risk_amount,
                    "position_value": ps.position_value,
                }
                for ticker, ps in open_pos.items()
            ],
            "daily_pnl": risk_manager.daily_pnl,
            "limits": {
                "max_open_positions": config.risk.max_open_positions,
                "max_daily_loss_pct": config.risk.max_daily_loss_pct,
                "max_position_pct": config.risk.max_position_pct,
                "atr_stop_multiplier": config.risk.atr_stop_multiplier,
            },
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/signals/<int:signal_id>")
def api_signal_detail(signal_id: int):
    """Full signal detail with metadata."""
    err = _require_engine()
    if err:
        return err
    svc = SignalsService(_engine)
    sig = svc.get_signal(signal_id)
    if sig is None:
        return jsonify({"error": "Signal not found"}), 404
    return jsonify(to_dict(sig))


@platform_bp.route("/analytics/summary")
def api_analytics_summary():
    """Quick analytics summary for dashboard header."""
    err = _require_engine()
    if err:
        return err
    try:
        svc = AnalyticsService(_engine)
        stats = svc.trade_stats()
        return jsonify({
            "total_trades": stats.get("total_trades", 0),
            "win_rate": stats.get("win_rate", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "roi_pct": stats.get("roi_pct", 0),
            "sharpe_ratio": stats.get("sharpe_ratio", 0),
            # `max_drawdown` is gone: it carried a fraction under a name every
            # renderer printed as a percentage. Both units, both named.
            "max_drawdown_pct": stats.get("max_drawdown_pct", 0),
            "max_drawdown_abs": stats.get("max_drawdown_abs", 0),
            "profit_factor": stats.get("profit_factor"),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/stream")
def api_sse_stream():
    """SSE endpoint for real-time updates."""

    def generate():
        import queue as _queue
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
                except _queue.Empty:
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


# ─── Learning API ─────────────────────────────────────────────────────────────

def _db_rows(sql: str, params: dict | None = None) -> list[dict]:
    """Execute raw SQL and return list of dicts."""
    from sqlalchemy import text
    with _engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [
            {
                k: (str(v) if hasattr(v, "isoformat") or hasattr(v, "hex") else v)
                for k, v in zip(cols, row)
            }
            for row in result.fetchall()
        ]


@platform_bp.route("/learning/overview")
def api_learning_overview():
    """High-level learning system state for the dashboard header."""
    err = _require_engine()
    if err:
        return err
    try:
        # Strategy confidence summary
        strategies = _db_rows("""
            SELECT strategy_id, confidence, win_rate, total_trades,
                   profit_factor, expectancy, best_regime, updated_at AS last_updated
            FROM belief_system
            ORDER BY confidence DESC
        """)

        # Active hypotheses count
        hyp_counts = _db_rows("""
            SELECT stage, COUNT(*) AS cnt
            FROM hypotheses
            GROUP BY stage
        """)
        hyp_by_stage = {r["stage"]: int(r["cnt"]) for r in hyp_counts}

        # Recent decision quality
        quality_rows = _db_rows("""
            SELECT AVG(decision_quality) AS avg_quality,
                   COUNT(*) AS evaluated,
                   MAX(closed_at) AS last_trade
            FROM trades
            WHERE decision_quality IS NOT NULL
              AND closed_at IS NOT NULL
        """)
        quality = quality_rows[0] if quality_rows else {}

        # Learning loop status
        learning_active = False
        try:
            from engine.paper_engine import paper_engine
            status = paper_engine.status()
            learning_active = status.get("learning_active", False)
        except Exception:
            pass

        return jsonify({
            "learning_active": learning_active,
            "strategies": strategies,
            "hypotheses": hyp_by_stage,
            "decision_quality": {
                "avg": round(float(quality.get("avg_quality") or 0), 3),
                "evaluated": int(quality.get("evaluated") or 0),
                "last_trade": quality.get("last_trade"),
            },
            "trades_total": sum(
                int(s.get("total_trades") or 0) for s in strategies
            ),
        })
    except Exception as exc:
        logger.warning("learning overview error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/learning/strategies")
def api_learning_strategies():
    """All strategies from belief_system with full stats."""
    err = _require_engine()
    if err:
        return err
    try:
        rows = _db_rows("""
            SELECT strategy_id, confidence, win_rate, total_trades,
                   profit_factor, expectancy, sharpe_ratio,
                   best_regime, updated_at AS last_updated
            FROM belief_system
            ORDER BY confidence DESC, total_trades DESC
        """)
        if rows:
            sids = [r["strategy_id"] for r in rows]
            history_rows = _db_rows("""
                SELECT strategy_id, closed_at, confidence
                FROM (
                    SELECT strategy_id, closed_at, confidence,
                           ROW_NUMBER() OVER (PARTITION BY strategy_id ORDER BY closed_at DESC) AS rn
                    FROM trades
                    WHERE strategy_id = ANY(:sids)
                      AND closed_at IS NOT NULL
                      AND confidence IS NOT NULL
                ) t
                WHERE rn <= 20
                ORDER BY strategy_id, closed_at
            """, {"sids": sids})
            history_by_sid: dict = {}
            for h in history_rows:
                history_by_sid.setdefault(h["strategy_id"], []).append(
                    {"ts": h["closed_at"], "value": float(h["confidence"] or 0)}
                )
            for row in rows:
                row["confidence_history"] = history_by_sid.get(row["strategy_id"], [])
        return jsonify(rows)
    except Exception as exc:
        logger.warning("learning strategies error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/learning/hypotheses")
def api_learning_hypotheses():
    """Hypothesis lifecycle — all stages with stats."""
    err = _require_engine()
    if err:
        return err
    try:
        stage_filter = request.args.get("stage") or None

        rows = _db_rows("""
            SELECT hypothesis_id, description,
                   conditions->>'strategy_id' AS strategy_id,
                   conditions,
                   stage, win_rate, profit_factor,
                   total_trades AS sample_size,
                   created_at, promoted_at, rejected_at,
                   stat_test_result->>'rejection_reason' AS rejection_reason
            FROM hypotheses
            WHERE (:stage IS NULL OR stage = :stage)
            ORDER BY
                CASE stage
                    WHEN 'active' THEN 0
                    WHEN 'candidate' THEN 1
                    WHEN 'observation' THEN 2
                    WHEN 'rejected' THEN 3
                END,
                total_trades DESC
        """, {"stage": stage_filter})
        return jsonify(rows)
    except Exception as exc:
        logger.warning("learning hypotheses error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/learning/decisions")
def api_learning_decisions():
    """Recent trade decisions with quality scores."""
    err = _require_engine()
    if err:
        return err
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = _db_rows("""
            SELECT trade_id, opened_at, closed_at, ticker, strategy_id,
                   direction, entry_price, exit_price, pnl, pnl_r,
                   confidence, decision_quality, randomness_factor,
                   strategy_followed, exit_reason_type, entry_reason,
                   market_regime
            FROM trades
            WHERE closed_at IS NOT NULL
            ORDER BY closed_at DESC
            LIMIT :limit
        """, {"limit": limit})
        return jsonify(rows)
    except Exception as exc:
        logger.warning("learning decisions error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/learning/activity")
def api_learning_activity():
    """Recent learning events — skipped signals + trade quality evolution."""
    err = _require_engine()
    if err:
        return err
    try:
        limit = min(int(request.args.get("limit", 30)), 100)

        # Skipped signals (rejected by orchestrator)
        skipped = _db_rows("""
            SELECT skip_id AS id, skipped_at AS created_at, strategy_id,
                   skip_reason, ticker, direction, details
            FROM skipped_signals
            ORDER BY skipped_at DESC
            LIMIT :limit
        """, {"limit": limit})

        # Recent quality trend (rolling 5-trade avg)
        quality_trend = _db_rows("""
            SELECT closed_at,
                   decision_quality,
                   AVG(decision_quality) OVER (
                       ORDER BY closed_at
                       ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                   ) AS rolling_avg
            FROM trades
            WHERE decision_quality IS NOT NULL AND closed_at IS NOT NULL
            ORDER BY closed_at DESC
            LIMIT 50
        """)

        return jsonify({
            "skipped_signals": skipped,
            "quality_trend": list(reversed(quality_trend)),
        })
    except Exception as exc:
        logger.warning("learning activity error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@platform_bp.route("/learning/run_cycle", methods=["POST"])
def api_learning_run_cycle():
    """Manually trigger a full learning cycle (for admin use)."""
    err = _require_engine()
    if err:
        return err
    try:
        from engine.paper_engine import paper_engine
        ll = getattr(paper_engine, "_learning_loop", None)
        if ll and ll.is_running():
            ll.run_full_cycle()
            return jsonify({"ok": True, "message": "Full learning cycle queued"})
        return jsonify({"ok": False, "message": "Learning loop not running"}), 503
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


