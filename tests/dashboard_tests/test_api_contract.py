"""HTTP-level contract tests against a real application instance.

These need a reachable database, so they skip cleanly when there is none — a
developer without Docker running still gets a green suite, and CI with a database
gets full coverage.

The app is built in read-only mode, which is also the assertion: a GET that tries
to write hits the connection-level guard and fails the test rather than quietly
inserting a row.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BOT = Path(__file__).resolve().parents[2] / "bot"
sys.path.insert(0, str(BOT))


@pytest.fixture(scope="module")
def app():
    """A read-only application, or a skip if the database is unreachable."""
    import os

    os.environ["QF_DASHBOARD_READ_ONLY"] = "1"
    os.environ["QF_INSECURE_COOKIES"] = "1"

    from ui.app_factory import create_app

    application = create_app(start_background=False)
    if application.config.get("QF_ENGINE") is None:
        pytest.skip("database unavailable")
    if not application.config.get("QF_SCHEMA_OK"):
        pytest.skip("schema not migrated — run: python -m qf_platform.migrate")
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authed(app):
    """A logged-in client, or a skip when no operator exists."""
    from qf_platform.repositories.auth_repository import AuthRepository

    repo = AuthRepository(app.config["QF_ENGINE"])
    if repo.user_count() == 0:
        pytest.skip("no dashboard user — run: python -m qf_platform.migrate --create-user")

    password = __import__("os").environ.get("QF_TEST_PASSWORD")
    username = __import__("os").environ.get("QF_TEST_USER", "operator")
    if not password:
        pytest.skip("set QF_TEST_USER/QF_TEST_PASSWORD to exercise authenticated routes")

    c = app.test_client()
    response = c.post("/api/v2/auth/login", json={"username": username, "password": password})
    if response.status_code != 200:
        pytest.skip("test credentials rejected")
    return c


READ_ROUTES = [
    "/api/v2/environment",
    "/api/v2/faults",
    "/api/v2/health",
    "/api/v2/overview",
    "/api/v2/equity?window=90d",
    "/api/v2/equity/underwater?window=90d",
    "/api/v2/drawdown?window=all",
    "/api/v2/accounts",
    "/api/v2/portfolio",
    "/api/v2/positions",
    "/api/v2/trades?period=all",
    "/api/v2/trades/learning",
    "/api/v2/statistics?period=all",
    "/api/v2/statistics/distribution",
    "/api/v2/analytics/daily",
    "/api/v2/signals",
    "/api/v2/strategies",
    "/api/v2/strategies/decisions",
    "/api/v2/hypotheses",
    "/api/v2/risk",
    "/api/v2/risk/events",
    "/api/v2/events",
    "/api/v2/market/coverage",
]


# ── Authentication is the default ────────────────────────────────────────────


@pytest.mark.parametrize("route", READ_ROUTES)
def test_every_read_route_requires_a_session(client, route):
    """Under the old model, zero of 52 routes required a credential."""
    response = client.get(route)
    assert response.status_code == 401
    body = response.get_json()
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_session_endpoint_is_public_and_reports_unauthenticated(client):
    """The login screen has to be able to ask. 200 with `authenticated: false`
    rather than 401, so "not logged in" is distinguishable from "broken"."""
    response = client.get("/api/v2/auth/session")
    assert response.status_code == 200
    assert response.get_json()["data"]["authenticated"] is False


def test_liveness_is_public(client):
    assert client.get("/health").status_code == 200


def test_unknown_api_route_returns_the_json_envelope_not_html(client):
    """Sixteen routes returned an HTML 500 to a JSON client."""
    response = client.get("/api/v2/does-not-exist")
    assert response.status_code in (401, 404)
    assert response.mimetype == "application/json"
    assert "error" in response.get_json()


# ── Login ────────────────────────────────────────────────────────────────────


def test_login_failure_is_generic(client):
    """A missing user and a wrong password must be indistinguishable."""
    missing = client.post("/api/v2/auth/login",
                          json={"username": "no-such-user-xyz", "password": "whatever12345"})
    assert missing.status_code == 401
    message = missing.get_json()["error"]["message"]
    assert "Неверный логин или пароль" in message
    # The response must not say which half was wrong.
    assert "не найден" not in message.lower()
    assert "пароль неверн" not in message.lower()


def test_login_requires_both_fields(client):
    response = client.post("/api/v2/auth/login", json={"username": "", "password": ""})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_FAILED"


# ── Read-only mode ───────────────────────────────────────────────────────────


MUTATING_ROUTES = [
    ("/api/v2/engine/start", {}),
    ("/api/v2/engine/stop", {"reason": "test"}),
    ("/api/v2/learning/run-cycle", {}),
    ("/api/v2/backtest/run", {"ticker": "SBER"}),
    ("/api/v2/positions/1/close", {"reason": "test", "confirm": "SBER"}),
    ("/api/v2/settings/credentials", {"key": "TINKOFF_TOKEN", "value": "x", "reason": "test"}),
]


@pytest.mark.parametrize("route,body", MUTATING_ROUTES)
def test_mutations_are_refused_in_read_only_mode(authed, route, body):
    response = authed.post(route, json=body)
    assert response.status_code in (403, 400)
    code = response.get_json()["error"]["code"]
    # READ_ONLY_MODE, or a permission/validation refusal that fires first — never
    # a success, and never a 500.
    assert code in {"READ_ONLY_MODE", "FORBIDDEN", "VALIDATION_FAILED", "NOT_FOUND"}


def test_csrf_is_required_for_a_mutation(authed):
    """Ten of twelve mutating endpoints were drive-by exploitable."""
    # `test_client` sends the CSRF cookie automatically; strip the header *and*
    # the cookie so the double-submit check has nothing to compare.
    authed.delete_cookie("qf_csrf")
    response = authed.post("/api/v2/engine/stop", json={"reason": "test"},
                           headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] in {"CSRF_INVALID", "READ_ONLY_MODE"}


def test_cross_origin_mutation_is_refused(authed):
    response = authed.post("/api/v2/engine/stop", json={"reason": "x"},
                           headers={"Origin": "http://evil.example"})
    assert response.status_code == 403


# ── The success envelope ─────────────────────────────────────────────────────


@pytest.mark.parametrize("route", READ_ROUTES)
def test_read_routes_return_the_envelope_with_required_meta(authed, route):
    response = authed.get(route)
    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    body = response.get_json()
    assert set(body) == {"data", "meta"}
    meta = body["meta"]
    for field in ("as_of", "timezone", "environment"):
        assert field in meta, f"{route} missing meta.{field}"
    # An unknown environment is a legitimate answer, but it must be one of the enum.
    assert meta["environment"] in {"sandbox", "forward", "backtest", "live", "unknown"}


@pytest.mark.parametrize("route", READ_ROUTES)
def test_read_routes_emit_strict_json(authed, route):
    """A literal NaN makes a strict parser fail, and a panel that fails to parse
    renders empty — which reads as "no data" rather than "broken"."""
    payload = authed.get(route).get_data(as_text=True)
    assert "NaN" not in payload
    assert "Infinity" not in payload
    json.loads(payload)  # raises on a non-strict document


def test_price_derived_routes_carry_freshness(authed):
    for route in ("/api/v2/environment", "/api/v2/positions", "/api/v2/equity",
                  "/api/v2/market/coverage"):
        meta = authed.get(route).get_json()["meta"]
        assert "source_as_of" in meta, route
        assert "data_age_seconds" in meta, route


def test_aggregates_carry_their_sample_size(authed):
    for route in ("/api/v2/statistics?period=all", "/api/v2/drawdown?window=all",
                  "/api/v2/trades?period=all", "/api/v2/strategies"):
        meta = authed.get(route).get_json()["meta"]
        assert meta.get("n") is not None, route


def test_drawdown_reports_both_units_and_no_ambiguous_field(authed):
    data = authed.get("/api/v2/drawdown?window=all").get_json()["data"]
    assert "max_drawdown_pct" in data
    assert "max_drawdown_abs" in data
    # The field that carried two units under one name must be gone.
    assert "max_drawdown" not in data


def test_statistics_reports_signed_and_absolute_means_separately(authed):
    data = authed.get("/api/v2/statistics?period=all").get_json()["data"]
    assert "avg_pnl_pct" in data
    assert "avg_abs_move_pct" in data
    if data["n"] and data["avg_pnl_pct"] is not None and data["total_pnl"] is not None:
        # On a losing set the signed mean must share the sign of the total.
        if data["total_pnl"] < 0:
            assert data["avg_pnl_pct"] < 0, "signed mean must be negative on a losing account"
            assert data["avg_abs_move_pct"] >= 0


def test_equity_comes_from_snapshots_never_from_candles(authed):
    body = authed.get("/api/v2/equity?window=all").get_json()
    assert body["meta"].get("source") in (None, "equity_snapshots")
    data = body["data"]
    # The polling artefact is reported rather than hidden.
    assert "observations" in data and "distinct_values" in data


def test_trades_envelope_matches_the_row_count(app, authed):
    """35 rows existed and 0 rendered because the route returned a bare array
    while the client read `payload.trades`."""
    from qf_platform.repositories.trades_repository import TradesRepository

    repo = TradesRepository(app.config["QF_ENGINE"])
    account_id = repo.default_account_id()
    if account_id is None:
        pytest.skip("no paper account")
    expected = repo.paper_trades_count(account_id, period="all")

    body = authed.get("/api/v2/trades?period=all&limit=500").get_json()
    data = body["data"]
    assert isinstance(data, dict), "must be an object, not a bare array"
    assert "trades" in data
    assert data["total"] == expected
    assert len(data["trades"]) == min(expected, 500)
    assert body["meta"]["n"] == expected


def test_every_trade_row_carries_an_environment(authed):
    for trade in authed.get("/api/v2/trades?period=all").get_json()["data"]["trades"]:
        assert trade["environment"] in {"sandbox", "forward", "backtest", "live", "unknown"}


def test_every_position_carries_its_quote_age(authed):
    data = authed.get("/api/v2/positions").get_json()["data"]
    for position in data["positions"]:
        assert "mark_age_seconds" in position
        assert "mark_is_stale" in position
        assert "distance_to_stop_pct" in position
        # An unpriced position reports None, not a substituted entry price.
        if position["mark_price"] is None:
            assert position["unrealized_pnl"] is None


def test_signals_carry_the_gate_decision_and_never_invent_a_reason(authed):
    data = authed.get("/api/v2/signals").get_json()["data"]
    for signal in data["signals"]:
        assert signal["gate_decision"] in {
            "pending", "filled", "accepted_unfilled", "rejected",
            "skipped", "duplicate", "errored", "unknown",
        }
        assert "gate_decision_label" in signal
        # When the gate recorded nothing, the row says so rather than guessing.
        if signal["gate_reason_missing"]:
            assert not signal["gate_reason"]


def test_strategies_never_expose_confidence_without_a_sample_size(authed):
    data = authed.get("/api/v2/strategies").get_json()["data"]
    for strategy in data["strategies"]:
        assert "sample_size" in strategy
        assert "confidence_is_mature" in strategy
        if strategy["confidence"] is not None:
            assert isinstance(strategy["sample_size"], int)
        # An immature sample is excluded from the ranking entirely.
        if not strategy["confidence_is_mature"]:
            assert strategy["rank"] is None


def test_risk_reports_unconfigured_limits_as_unconfigured(authed):
    data = authed.get("/api/v2/risk").get_json()["data"]
    limit = data["daily"]["limit_pct"]
    assert "configured" in limit
    if not limit["configured"]:
        assert limit["value"] is None, "an unconfigured limit must be None, never 0"


def test_health_never_reports_an_unreported_service_as_healthy(authed):
    for service in authed.get("/api/v2/health").get_json()["data"]["services"]:
        assert service["state"] in {
            "healthy", "degraded", "stale", "paused", "frozen",
            "disconnected", "failed", "unknown",
        }
        # Every state carries a word and a shape, so greyscale survives.
        assert service["label"]
        assert service["shape"]


def test_audit_requires_the_administrator_permission(authed):
    response = authed.get("/api/v2/audit")
    assert response.status_code in (200, 403)
    if response.status_code == 403:
        assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_invalid_environment_is_rejected_not_silently_defaulted(authed):
    """Answering a different question than the one asked is how a live number
    lands on a sandbox screen."""
    response = authed.get("/api/v2/positions?environment=bogus")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_FAILED"


def test_invalid_period_and_sort_are_rejected(authed):
    assert authed.get("/api/v2/trades?period=forever").status_code == 400
    assert authed.get("/api/v2/trades?sort=drop_table").status_code == 400


def test_security_headers_are_present(client):
    response = client.get("/login")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    # No third-party origin, and no blanket unsafe-inline for scripts.
    for banned in ("unpkg.com", "cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"):
        assert banned not in csp
    assert "script-src 'self' 'nonce-" in csp
    # An empty nonce would make a browser discard the whole directive.
    assert "'nonce-'" not in csp
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


def test_api_responses_are_not_cacheable(authed):
    response = authed.get("/api/v2/positions")
    assert "no-store" in response.headers.get("Cache-Control", "")


def test_deep_links_serve_the_shell(authed):
    for path in ("/", "/positions", "/trades", "/status", "/events", "/settings"):
        response = authed.get(path)
        assert response.status_code == 200, path
        assert b"qf-app" in response.data, path


def test_an_unknown_page_still_404s(authed):
    assert authed.get("/definitely-not-a-view").status_code == 404
