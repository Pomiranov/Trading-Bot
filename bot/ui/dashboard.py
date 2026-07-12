"""Flask dashboard server for QuantFlow trading bot."""

import dataclasses
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from config import config
from security.bootstrap import bootstrap_security
from security.credential_store import persist_credential
from security.dashboard_auth import register_dashboard_security
from security.http_middleware import register_request_middleware
from services.tinkoff import (
    TinkoffAPIError,
    TinkoffNotConfigured,
    TinkoffSDKError,
    compute_bot_stats,
    get_portfolio_summary,
    invalidate_portfolio_cache,
)
from services.tinkoff.statistics import invalidate as invalidate_stats_cache

bootstrap_security(config, service_name="dashboard")

app = Flask(__name__)
logger = logging.getLogger(__name__)

register_request_middleware(app)
register_dashboard_security(app)

# ── Database connection ───────────────────────────────────────────────────────

try:
    from sqlalchemy import create_engine, text

    _engine = create_engine(config.db.dsn, pool_pre_ping=True, pool_size=2, max_overflow=3)
    with _engine.connect() as _c:
        _c.execute(text("SELECT 1"))
    DB_AVAILABLE = True
    logger.info("Connected to PostgreSQL at %s", config.db.host)
except Exception as exc:
    logger.warning("DB unavailable: %s", exc)
    DB_AVAILABLE = False
    _engine = None


def _query(sql: str, params: dict | None = None) -> list[dict]:
    with _engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


# ── Math helpers ──────────────────────────────────────────────────────────────

def _sharpe(equities: list[float]) -> float:
    if len(equities) < 3:
        return 0.0
    returns = [(equities[i] - equities[i - 1]) / equities[i - 1]
               for i in range(1, len(equities))]
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / max(n - 1, 1)
    std = variance ** 0.5
    return round(mean / std * (252 ** 0.5), 2) if std else 0.0


def _max_drawdown(equities: list[float]) -> float:
    if len(equities) < 2:
        return 0.0
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        peak = max(peak, e)
        dd = (e - peak) / peak * 100
        max_dd = min(max_dd, dd)
    return round(max_dd, 2)


def _fmt_ts(v) -> str:
    return v.strftime("%Y-%m-%d %H:%M") if hasattr(v, "strftime") else str(v)[:16]


def _fmt_hms(v) -> str:
    return v.strftime("%H:%M:%S") if hasattr(v, "strftime") else str(v)[11:19]


# ── Real DB queries ───────────────────────────────────────────────────────────

BASE_CAPITAL = 1_000_000.0


def _db_metrics() -> dict:
    rows = _query("""
        SELECT
            COUNT(*)                                                    AS total_trades,
            COUNT(*) FILTER (WHERE pnl > 0)                            AS winning_trades,
            COALESCE(SUM(pnl) FILTER (WHERE DATE(closed_at) = CURRENT_DATE), 0) AS pnl_today,
            COALESCE(SUM(pnl), 0)                                      AS total_pnl
        FROM trades
        WHERE closed_at IS NOT NULL
    """)
    r = rows[0] if rows else {}
    total = int(r.get("total_trades") or 0)
    if total == 0:
        raise ValueError("trades table is empty")

    wins = int(r.get("winning_trades") or 0)
    pnl_today = float(r.get("pnl_today") or 0)
    total_pnl = float(r.get("total_pnl") or 0)
    portfolio = BASE_CAPITAL + total_pnl

    eq_rows = _query("""
        SELECT :base + SUM(pnl) OVER (ORDER BY closed_at) AS equity
        FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at
    """, {"base": BASE_CAPITAL})
    equities = [float(row["equity"]) for row in eq_rows]

    return {
        "portfolio_value": round(portfolio, 2),
        "pnl_today":       round(pnl_today, 2),
        "pnl_today_pct":   round(pnl_today / BASE_CAPITAL * 100, 4),
        "drawdown_pct":    _max_drawdown(equities),
        "sharpe_ratio":    _sharpe(equities),
        "total_trades":    total,
        "win_rate":        round(wins / total * 100, 1),
        "bot_status":      "live",
    }


def _db_equity() -> list[dict]:
    rows = _query("""
        SELECT ts, :base + SUM(daily_pnl) OVER (ORDER BY ts) AS equity
        FROM (
            SELECT DATE(closed_at) AS ts, SUM(pnl) AS daily_pnl
            FROM trades WHERE closed_at IS NOT NULL GROUP BY DATE(closed_at)
        ) daily ORDER BY ts
    """, {"base": BASE_CAPITAL})
    if not rows:
        raise ValueError("no closed trades for equity curve")
    return [{"ts": str(r["ts"]), "equity": round(float(r["equity"]), 2)} for r in rows]


def _candle_equity() -> list[dict]:
    rows = _query("""
        SELECT time, close FROM candles
        WHERE ticker = 'SBER' AND timeframe = '1d'
        ORDER BY time ASC LIMIT 90
    """)
    if not rows:
        raise ValueError("no candle data")
    first = float(rows[0]["close"])
    if first == 0:
        raise ValueError("zero first price")
    return [
        {"ts": str(r["time"])[:10], "equity": round(BASE_CAPITAL * float(r["close"]) / first, 2)}
        for r in rows
    ]


def _db_signals() -> list[dict]:
    rows = _query("""
        SELECT t.opened_at AS ts, t.ticker, t.direction, t.entry_price AS price,
               t.quantity, tf.outcome, tf.signals
        FROM trades t
        LEFT JOIN trade_feedback tf ON tf.trade_id = t.id
        ORDER BY t.opened_at DESC LIMIT 50
    """)
    if not rows:
        raise ValueError("trades table is empty")
    result = []
    for r in rows:
        direction = (r.get("direction") or "").lower()
        action = "BUY" if direction == "long" else "SELL" if direction == "short" else "HOLD"
        signals_json = r.get("signals")
        score = float(signals_json.get("score", 0) or 0) if isinstance(signals_json, dict) else 0.0
        result.append({
            "ts": _fmt_ts(r["ts"]),
            "ticker": r["ticker"],
            "action": action,
            "score": score,
            "price": float(r.get("price") or 0),
            "rules": int(r.get("quantity") or 1),
        })
    return result


def _db_positions() -> list[dict]:
    rows = _query("""
        SELECT t.ticker, t.direction, t.entry_price, t.quantity AS shares,
               t.stop_loss AS stop_price, t.take_profit, t.opened_at,
               COALESCE(c.close, t.entry_price) AS current_price
        FROM trades t
        LEFT JOIN LATERAL (
            SELECT close FROM candles WHERE ticker = t.ticker ORDER BY time DESC LIMIT 1
        ) c ON true
        WHERE t.closed_at IS NULL ORDER BY t.opened_at DESC
    """)
    if not rows:
        raise ValueError("no open positions")
    result = []
    for r in rows:
        entry = float(r["entry_price"] or 0)
        current = float(r["current_price"] or entry)
        shares = int(r.get("shares") or 0)
        direction = (r.get("direction") or "long").lower()
        if direction == "long":
            pnl = (current - entry) * shares
            pnl_pct = round((current / entry - 1) * 100, 2) if entry else 0
        else:
            pnl = (entry - current) * shares
            pnl_pct = round((entry / current - 1) * 100, 2) if current else 0
        result.append({
            "ticker": r["ticker"],
            "entry_price": entry,
            "current_price": current,
            "shares": shares,
            "pnl": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "stop_price": float(r.get("stop_price") or 0),
        })
    return result


def _db_log() -> list[dict]:
    rows = _query("""
        SELECT published_at, source, title, sentiment, importance
        FROM news ORDER BY published_at DESC LIMIT 50
    """)
    if not rows:
        raise ValueError("news table is empty")
    result = []
    for r in rows:
        sentiment = float(r.get("sentiment") or 0)
        importance = int(r.get("importance") or 0)
        if importance >= 4 or sentiment <= -0.3:
            level = "ERROR"
        elif sentiment <= -0.1 or importance >= 3:
            level = "WARN"
        else:
            level = "INFO"
        result.append({
            "ts": _fmt_hms(r["published_at"]),
            "level": level,
            "message": f"[{r.get('source') or 'news'}] {r.get('title') or ''}",
        })
    return result


# ── Settings persistence ──────────────────────────────────────────────────────

_ALLOWED_TOKEN_KEYS = {"TINKOFF_TOKEN", "TINKOFF_ACCOUNT_ID"}


def _client_ip() -> str:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "")


def _save_env_key(key: str, value: str) -> None:
    """Persist credential via encrypted vault and/or .env."""
    persist_credential(
        key,
        value.strip(),
        config,
        actor_type="dashboard",
        actor_id="settings_ui",
        client_ip=_client_ip(),
    )
    invalidate_portfolio_cache()
    invalidate_stats_cache()


# ── Tinkoff error helpers ─────────────────────────────────────────────────────

def _tinkoff_error_response(exc: Exception):
    if isinstance(exc, TinkoffSDKError):
        return jsonify({"error": str(exc), "error_code": "SDK_ERROR"}), 503
    if isinstance(exc, TinkoffNotConfigured):
        return jsonify({"error": str(exc), "error_code": "NOT_CONFIGURED"}), 503
    return jsonify({"error": str(exc), "error_code": "API_ERROR"}), 502


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "db": DB_AVAILABLE,
    })


# ── Tinkoff Invest routes ─────────────────────────────────────────────────────

@app.route("/api/tinkoff/portfolio")
def api_tinkoff_portfolio():
    try:
        summary = get_portfolio_summary()
        return jsonify({
            "total_value": summary.total_value,
            "total_yield": summary.total_yield,
            "total_yield_pct": summary.total_yield_pct,
            "positions_count": summary.positions_count,
            "currency": summary.currency,
        })
    except Exception as exc:
        return _tinkoff_error_response(exc)


@app.route("/api/tinkoff/positions")
def api_tinkoff_positions():
    try:
        summary = get_portfolio_summary()
        return jsonify([dataclasses.asdict(p) for p in summary.positions])
    except Exception as exc:
        return _tinkoff_error_response(exc)


@app.route("/api/tinkoff/pnl")
def api_tinkoff_pnl():
    try:
        summary = get_portfolio_summary()
        return jsonify({
            "unrealized": summary.total_yield,
            "unrealized_pct": summary.total_yield_pct,
            "currency": summary.currency,
        })
    except Exception as exc:
        return _tinkoff_error_response(exc)


# ── Bot statistics (from local DB) ────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    if not DB_AVAILABLE or _engine is None:
        return jsonify({
            "total_trades": None,
            "winning_trades": None,
            "losing_trades": None,
            "win_rate": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "avg_trade_pnl": None,
            "total_pnl": None,
            "has_sufficient_data": False,
        })
    stats = compute_bot_stats(_engine)
    return jsonify(dataclasses.asdict(stats))


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/api/settings")
def api_settings():
    return jsonify({
        "db": {
            "host":      config.db.host,
            "port":      config.db.port,
            "name":      config.db.name,
            "connected": DB_AVAILABLE,
        },
        "risk": {
            "max_position_pct":    config.risk.max_position_pct,
            "atr_stop_multiplier": config.risk.atr_stop_multiplier,
            "max_daily_loss_pct":  config.risk.max_daily_loss_pct,
            "max_open_positions":  config.risk.max_open_positions,
        },
        "app": {
            "tickers":       config.tickers,
            "poll_interval": config.poll_interval,
            "log_level":     config.log_level,
        },
        "tinkoff": {
            "sandbox":          config.tinkoff.sandbox,
            "has_token":        bool(config.tinkoff.token),
            "has_account_id":   bool(config.tinkoff.account_id),
        },
    })


@app.route("/api/settings/tokens", methods=["GET"])
def api_settings_tokens_get():
    return jsonify({
        "has_tinkoff_token":      bool(config.tinkoff.token),
        "has_tinkoff_account_id": bool(config.tinkoff.account_id),
    })


@app.route("/api/settings/tokens", methods=["POST"])
def api_settings_tokens_post():
    body = request.get_json(silent=True) or {}
    key = body.get("key", "")
    value = body.get("value", "")

    if key not in _ALLOWED_TOKEN_KEYS:
        return jsonify({"ok": False, "error": "Недопустимый ключ"}), 400
    if not isinstance(value, str):
        return jsonify({"ok": False, "error": "Некорректное значение"}), 400

    try:
        _save_env_key(key, value.strip())
        logger.info("Credential updated: key=%s", key)  # value is never logged
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error("Failed to save credential key=%s: %s", key, exc)
        return jsonify({"ok": False, "error": "Ошибка сохранения"}), 500


# ── Legacy DB routes (no demo fallback) ──────────────────────────────────────

@app.route("/api/metrics")
def api_metrics():
    if not DB_AVAILABLE:
        return jsonify({"error": "DB not available"}), 503
    try:
        return jsonify(_db_metrics())
    except ValueError:
        return jsonify({
            "portfolio_value": 0.0, "pnl_today": 0.0, "pnl_today_pct": 0.0,
            "drawdown_pct": 0.0, "sharpe_ratio": 0.0,
            "total_trades": 0, "win_rate": 0.0, "bot_status": "stopped",
        })
    except Exception as exc:
        logger.warning("metrics error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/signals")
def api_signals():
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        return jsonify(_db_signals())
    except (ValueError, Exception) as exc:
        logger.info("signals: %s", exc)
        return jsonify([])


@app.route("/api/positions")
def api_positions():
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        return jsonify(_db_positions())
    except (ValueError, Exception) as exc:
        logger.info("positions: %s", exc)
        return jsonify([])


@app.route("/api/log")
def api_log():
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        return jsonify(_db_log())
    except (ValueError, Exception) as exc:
        logger.info("log: %s", exc)
        return jsonify([])


@app.route("/api/equity")
def api_equity():
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        return jsonify(_db_equity())
    except (ValueError, Exception):
        pass
    try:
        return jsonify(_candle_equity())
    except Exception as exc:
        logger.warning("equity error: %s", exc)
        return jsonify([])


# ── Candles / Portfolio / Live signals / Backtest ─────────────────────────────

@app.route("/api/candles")
def api_candles():
    ticker = request.args.get("ticker", "SBER").upper()
    limit = min(int(request.args.get("limit", 120)), 365)
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        rows = _query("""
            SELECT time, open, high, low, close, volume
            FROM candles WHERE ticker = :ticker AND timeframe = '1d'
            ORDER BY time ASC LIMIT :limit
        """, {"ticker": ticker, "limit": limit})
        return jsonify([{
            "ts":     str(r["time"])[:10],
            "open":   round(float(r["open"]),  2),
            "high":   round(float(r["high"]),  2),
            "low":    round(float(r["low"]),   2),
            "close":  round(float(r["close"]), 2),
            "volume": int(r["volume"]),
        } for r in rows])
    except Exception as exc:
        logger.warning("candles error: %s", exc)
        return jsonify([])


@app.route("/api/portfolio")
def api_portfolio():
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        tickers = [r["ticker"] for r in _query(
            "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
        )]
        result = []
        for ticker in tickers:
            rows = _query("""
                SELECT close, volume, time FROM candles
                WHERE ticker = :ticker AND timeframe = '1d'
                ORDER BY time DESC LIMIT 31
            """, {"ticker": ticker})
            if len(rows) < 2:
                continue
            latest = float(rows[0]["close"])
            prev = float(rows[1]["close"])
            old_30 = float(rows[-1]["close"])
            result.append({
                "ticker":     ticker,
                "price":      round(latest, 2),
                "change_1d":  round((latest - prev)   / prev   * 100, 2) if prev   else 0.0,
                "change_30d": round((latest - old_30) / old_30 * 100, 2) if old_30 else 0.0,
                "volume":     int(rows[0]["volume"]),
                "ts":         str(rows[0]["time"])[:10],
            })
        return jsonify(result)
    except Exception as exc:
        logger.warning("portfolio error: %s", exc)
        return jsonify([])


@app.route("/api/signals/live")
def api_signals_live():
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        from signals.indicators import IndicatorEngine
        from signals.rules_engine import RulesEngine
        engine = IndicatorEngine()
        rules = RulesEngine()

        tickers = [r["ticker"] for r in _query(
            "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
        )]
        result = []
        for ticker in tickers:
            rows = _query("""
                SELECT time, open, high, low, close, volume FROM candles
                WHERE ticker = :ticker AND timeframe = '1d'
                ORDER BY time ASC LIMIT 120
            """, {"ticker": ticker})
            if len(rows) < 35:
                continue
            df = pd.DataFrame(rows)
            df.set_index("time", inplace=True)
            for col in ("open", "high", "low", "close", "volume"):
                df[col] = df[col].astype(float)
            iv = engine.latest(df)
            signal = rules.evaluate(iv)
            latest = rows[-1]

            import math

            def _safe_f(v):
                return round(float(v), 4) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 0.0

            result.append({
                "ts":         str(latest["time"])[:16],
                "ticker":     ticker,
                "action":     signal.action.value,
                "score":      round(float(signal.score), 2),
                "price":      round(float(latest["close"]), 2),
                "rsi":        _safe_f(iv.rsi),
                "macd_hist":  _safe_f(iv.macd_hist),
                "adx":        _safe_f(iv.adx),
                "bb_pct":     _safe_f(iv.bb_pct),
                "buy_score":  round(float(signal.buy_score), 2),
                "sell_score": round(float(signal.sell_score), 2),
                "rules":      len(signal.triggered_rules),
                "triggered":  [r.name for r in signal.triggered_rules],
            })
        return jsonify(result)
    except Exception as exc:
        logger.warning("live signals error: %s", exc)
        return jsonify([])


@app.route("/api/backtest", methods=["GET", "POST"])
def api_backtest():
    if not DB_AVAILABLE:
        return jsonify({"error": "DB not available"}), 503
    try:
        from backtest.engine import BacktestEngine
        tickers = [r["ticker"] for r in _query(
            "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
        )]
        results = []
        for ticker in tickers:
            rows = _query("""
                SELECT time, open, high, low, close, volume FROM candles
                WHERE ticker = :ticker AND timeframe = '1d' ORDER BY time ASC
            """, {"ticker": ticker})
            if len(rows) < 55:
                continue
            df = pd.DataFrame(rows)
            df.set_index("time", inplace=True)
            for col in ("open", "high", "low", "close", "volume"):
                df[col] = df[col].astype(float)
            eng = BacktestEngine(initial_capital=BASE_CAPITAL)
            res = eng.run(ticker, df)
            step = max(1, len(res.equity_curve) // 60)
            results.append({
                "ticker":         ticker,
                "total_trades":   res.total_trades,
                "winning_trades": res.winning_trades,
                "losing_trades":  res.losing_trades,
                "total_pnl":      round(res.total_pnl, 2),
                "max_drawdown":   round(res.max_drawdown, 2),
                "sharpe":         round(res.sharpe, 2),
                "win_rate":       round(res.win_rate, 1),
                "avg_pnl":        round(res.avg_pnl, 2),
                "equity_curve":   [round(v, 2) for v in res.equity_curve[::step]],
                "candles_count":  len(rows),
            })
        return jsonify(results)
    except Exception as exc:
        logger.warning("backtest error: %s", exc)
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    host = config.dashboard.host
    port = config.dashboard.port
    logger.info("Dashboard listening on %s:%s", host, port)
    app.run(host=host, port=port, debug=False)
