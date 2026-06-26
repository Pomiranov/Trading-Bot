"""Flask dashboard server for QuantFlow trading bot."""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

app = Flask(__name__)
logger = logging.getLogger(__name__)

# ── Database connection ───────────────────────────────────────────────────────

try:
    from sqlalchemy import create_engine, text
    _engine = create_engine(config.db.dsn, pool_pre_ping=True, pool_size=2, max_overflow=3)
    with _engine.connect() as _c:
        _c.execute(text("SELECT 1"))
    DB_AVAILABLE = True
    logger.info("Connected to PostgreSQL at %s", config.db.host)
except Exception as exc:
    logger.warning("DB unavailable, demo mode active: %s", exc)
    DB_AVAILABLE = False
    _engine = None


def _query(sql: str, params: dict | None = None) -> list[dict]:
    with _engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


# ── Math helpers ──────────────────────────────────────────────────────────────

def _sharpe(equities: list[float]) -> float:
    """Annualised Sharpe ratio from an equity series (daily step assumed)."""
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
    """Maximum drawdown as a negative percentage."""
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


# ── Demo data (fallback when tables are empty or DB is down) ──────────────────

def _demo_metrics() -> dict:
    return {
        "portfolio_value": 1_432_850.00,
        "pnl_today":       12_340.50,
        "pnl_today_pct":   0.87,
        "drawdown_pct":    -3.24,
        "sharpe_ratio":    1.84,
        "total_trades":    247,
        "win_rate":        62.3,
        "bot_status":      "live",
    }


def _demo_equity() -> list[dict]:
    import random
    random.seed(42)
    base = 1_000_000.0
    now  = datetime.utcnow()
    pts  = []
    for i in range(90):
        ts   = now - timedelta(days=89 - i)
        base *= 1 + random.gauss(0.002, 0.012)
        pts.append({"ts": ts.strftime("%Y-%m-%d"), "equity": round(base, 2)})
    return pts


def _demo_signals() -> list[dict]:
    import random
    random.seed(7)
    tickers = ["SBER", "GAZP", "LKOH", "YNDX", "NVTK", "GMKN", "ROSN"]
    now = datetime.utcnow()
    return [
        {
            "ts":     (now - timedelta(minutes=i * 7 + random.randint(0, 5))).strftime("%Y-%m-%d %H:%M"),
            "ticker": random.choice(tickers),
            "action": random.choice(["BUY", "SELL", "HOLD"]),
            "score":  round(random.uniform(1.5, 4.5), 2),
            "price":  round(random.uniform(100, 5000), 2),
            "rules":  random.randint(2, 5),
        }
        for i in range(15)
    ]


def _demo_positions() -> list[dict]:
    import random
    random.seed(13)
    rows = []
    for t in ["SBER", "LKOH", "YNDX"]:
        entry   = round(random.uniform(200, 3000), 2)
        current = round(entry * random.uniform(0.95, 1.08), 2)
        shares  = random.randint(10, 100)
        pnl     = round((current - entry) * shares, 2)
        rows.append({
            "ticker":        t,
            "entry_price":   entry,
            "current_price": current,
            "shares":        shares,
            "pnl":           pnl,
            "pnl_pct":       round((current / entry - 1) * 100, 2),
            "stop_price":    round(entry * 0.97, 2),
        })
    return rows


def _demo_log() -> list[dict]:
    import random
    random.seed(99)
    msgs = [
        ("INFO",  "Signal evaluated: SBER → BUY (score 3.20)"),
        ("INFO",  "Position opened: LKOH 30 лотов @ 6 412.00"),
        ("INFO",  "Trailing stop updated: YNDX 3 180.00 → 3 201.40"),
        ("WARN",  "Daily loss limit checked: -0.8% / -2.0%"),
        ("ERROR", "MOEX ISS request timeout, retrying…"),
        ("INFO",  "Position closed: SBER 50 лотов @ 287.20  PnL +1 240 ₽"),
        ("INFO",  "Rules reloaded: 12 rules active"),
        ("WARN",  "Risk check: GAZP position size at 4.8% (limit 5%)"),
    ]
    now = datetime.utcnow()
    return [
        {
            "ts":      (now - timedelta(minutes=i * 3)).strftime("%H:%M:%S"),
            "level":   random.choice(msgs)[0],
            "message": random.choice(msgs)[1],
        }
        for i in range(20)
    ]


# ── Real DB queries ───────────────────────────────────────────────────────────
# Schema:
#   trades       (id, ticker, direction, opened_at, closed_at,
#                 entry_price, exit_price, quantity, pnl,
#                 stop_loss, take_profit, reason_open, reason_close)
#   candles      (time, ticker, timeframe, open, high, low, close, volume)
#   news         (id, source, published_at, title, body, url,
#                 tickers, sentiment, importance, category)
#   trade_feedback (id, trade_id, signals JSONB, outcome, notes, created_at)

BASE_CAPITAL = 1_000_000.0   # starting portfolio size assumed for PnL calc


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
    r     = rows[0] if rows else {}
    total = int(r.get("total_trades") or 0)

    if total == 0:
        raise ValueError("trades table is empty")

    wins      = int(r.get("winning_trades") or 0)
    pnl_today = float(r.get("pnl_today") or 0)
    total_pnl = float(r.get("total_pnl") or 0)
    portfolio = BASE_CAPITAL + total_pnl

    # Equity series for Sharpe & max drawdown
    eq_rows = _query("""
        SELECT
            :base + SUM(pnl) OVER (ORDER BY closed_at) AS equity
        FROM trades
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at
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
    """Daily cumulative equity from closed trades."""
    rows = _query("""
        SELECT
            ts,
            :base + SUM(daily_pnl) OVER (ORDER BY ts) AS equity
        FROM (
            SELECT DATE(closed_at) AS ts, SUM(pnl) AS daily_pnl
            FROM trades
            WHERE closed_at IS NOT NULL
            GROUP BY DATE(closed_at)
        ) daily
        ORDER BY ts
    """, {"base": BASE_CAPITAL})

    if not rows:
        raise ValueError("no closed trades for equity curve")

    return [{"ts": str(r["ts"]), "equity": round(float(r["equity"]), 2)} for r in rows]


def _candle_equity() -> list[dict]:
    """SBER close prices normalized to BASE_CAPITAL (used when no trades exist)."""
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
    """Recent trades as BUY/SELL signals; HOLD from trade_feedback outcome."""
    rows = _query("""
        SELECT
            t.opened_at                                         AS ts,
            t.ticker,
            t.direction,
            t.entry_price                                       AS price,
            t.quantity,
            tf.outcome,
            tf.signals
        FROM trades t
        LEFT JOIN trade_feedback tf ON tf.trade_id = t.id
        ORDER BY t.opened_at DESC
        LIMIT 50
    """)

    if not rows:
        raise ValueError("trades table is empty")

    result = []
    for r in rows:
        direction = (r.get("direction") or "").lower()
        action    = "BUY" if direction == "long" else "SELL" if direction == "short" else "HOLD"

        # Try to extract score from JSONB signals field
        signals_json = r.get("signals")
        score = 0.0
        if isinstance(signals_json, dict):
            score = float(signals_json.get("score", 0) or 0)

        result.append({
            "ts":     _fmt_ts(r["ts"]),
            "ticker": r["ticker"],
            "action": action,
            "score":  score,
            "price":  float(r.get("price") or 0),
            "rules":  int(r.get("quantity") or 1),
        })
    return result


def _db_positions() -> list[dict]:
    """Open trades (closed_at IS NULL) with current price from latest candle."""
    rows = _query("""
        SELECT
            t.ticker,
            t.direction,
            t.entry_price,
            t.quantity                              AS shares,
            t.stop_loss                             AS stop_price,
            t.take_profit,
            t.opened_at,
            COALESCE(c.close, t.entry_price)        AS current_price
        FROM trades t
        LEFT JOIN LATERAL (
            SELECT close
            FROM candles
            WHERE ticker = t.ticker
            ORDER BY time DESC
            LIMIT 1
        ) c ON true
        WHERE t.closed_at IS NULL
        ORDER BY t.opened_at DESC
    """)

    if not rows:
        raise ValueError("no open positions")

    result = []
    for r in rows:
        entry     = float(r["entry_price"] or 0)
        current   = float(r["current_price"] or entry)
        shares    = int(r.get("shares") or 0)
        direction = (r.get("direction") or "long").lower()

        if direction == "long":
            pnl     = (current - entry) * shares
            pnl_pct = round((current / entry - 1) * 100, 2) if entry else 0
        else:
            pnl     = (entry - current) * shares
            pnl_pct = round((entry / current - 1) * 100, 2) if current else 0

        result.append({
            "ticker":        r["ticker"],
            "entry_price":   entry,
            "current_price": current,
            "shares":        shares,
            "pnl":           round(pnl, 2),
            "pnl_pct":       pnl_pct,
            "stop_price":    float(r.get("stop_price") or 0),
        })
    return result


def _db_log() -> list[dict]:
    """Recent news as event log; importance & sentiment → log level."""
    rows = _query("""
        SELECT
            published_at,
            source,
            title,
            sentiment,
            importance
        FROM news
        ORDER BY published_at DESC
        LIMIT 50
    """)

    if not rows:
        raise ValueError("news table is empty")

    result = []
    for r in rows:
        sentiment  = float(r.get("sentiment") or 0)
        importance = int(r.get("importance") or 0)

        if importance >= 4 or sentiment <= -0.3:
            level = "ERROR"
        elif sentiment <= -0.1 or importance >= 3:
            level = "WARN"
        else:
            level = "INFO"

        source  = r.get("source") or "news"
        title   = r.get("title") or ""
        message = f"[{source}] {title}"

        result.append({
            "ts":      _fmt_hms(r["published_at"]),
            "level":   level,
            "message": message,
        })
    return result


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _safe(fn_db, fn_demo):
    """Try DB query; fall back to demo if DB is down or table is empty."""
    if DB_AVAILABLE:
        try:
            return fn_db()
        except ValueError as exc:
            logger.info("Empty table, using demo: %s", exc)
        except Exception as exc:
            logger.warning("DB query error, using demo: %s", exc)
    return fn_demo()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/metrics")
def api_metrics():
    return jsonify(_safe(_db_metrics, _demo_metrics))


@app.route("/api/signals")
def api_signals():
    return jsonify(_safe(_db_signals, _demo_signals))


@app.route("/api/positions")
def api_positions():
    return jsonify(_safe(_db_positions, _demo_positions))


@app.route("/api/log")
def api_log():
    return jsonify(_safe(_db_log, _demo_log))


@app.route("/api/equity")
def api_equity():
    if DB_AVAILABLE:
        try:
            return jsonify(_db_equity())
        except (ValueError, Exception):
            pass
        try:
            return jsonify(_candle_equity())
        except Exception as exc:
            logger.warning("candle equity fallback failed: %s", exc)
    return jsonify(_demo_equity())


# ── New routes (candles / portfolio / live signals / backtest / settings) ──────

@app.route("/api/candles")
def api_candles():
    ticker = request.args.get("ticker", "SBER").upper()
    limit  = min(int(request.args.get("limit", 120)), 365)
    if not DB_AVAILABLE:
        return jsonify([])
    try:
        rows = _query("""
            SELECT time, open, high, low, close, volume
            FROM candles
            WHERE ticker = :ticker AND timeframe = '1d'
            ORDER BY time ASC
            LIMIT :limit
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
            latest   = float(rows[0]["close"])
            prev     = float(rows[1]["close"])
            old_30   = float(rows[-1]["close"])
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
        return jsonify(_demo_signals())
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from signals.indicators import IndicatorEngine
        from signals.rules_engine import RulesEngine
        engine = IndicatorEngine()
        rules  = RulesEngine()

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

            iv     = engine.latest(df)
            signal = rules.evaluate(iv)
            latest = rows[-1]

            def _safe_f(v):
                import math
                return round(float(v), 4) if v is not None and not (isinstance(v, float) and math.isnan(v)) else 0.0

            result.append({
                "ts":       str(latest["time"])[:16],
                "ticker":   ticker,
                "action":   signal.action.value,
                "score":    round(float(signal.score), 2),
                "price":    round(float(latest["close"]), 2),
                "rsi":      _safe_f(iv.rsi),
                "macd_hist": _safe_f(iv.macd_hist),
                "adx":      _safe_f(iv.adx),
                "bb_pct":   _safe_f(iv.bb_pct),
                "buy_score":  round(float(signal.buy_score), 2),
                "sell_score": round(float(signal.sell_score), 2),
                "rules":    len(signal.triggered_rules),
                "triggered": [r.name for r in signal.triggered_rules],
            })
        return jsonify(result)
    except Exception as exc:
        logger.warning("live signals error: %s", exc)
        return jsonify(_demo_signals())


@app.route("/api/backtest", methods=["GET", "POST"])
def api_backtest():
    if not DB_AVAILABLE:
        return jsonify({"error": "DB not available"})
    try:
        from backtest.engine import BacktestEngine
        tickers = [r["ticker"] for r in _query(
            "SELECT DISTINCT ticker FROM candles ORDER BY ticker"
        )]
        results = []
        for ticker in tickers:
            rows = _query("""
                SELECT time, open, high, low, close, volume FROM candles
                WHERE ticker = :ticker AND timeframe = '1d'
                ORDER BY time ASC
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
        return jsonify({"error": str(exc)})


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
            "sandbox":   config.tinkoff.sandbox,
            "has_token": bool(config.tinkoff.token),
        },
    })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("DASHBOARD_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)
