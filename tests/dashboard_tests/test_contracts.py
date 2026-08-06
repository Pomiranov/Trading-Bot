"""Regression tests for the data-correctness defects.

One test per defect, each asserting the *specific* wrong behaviour cannot return.
These are pure-function tests against `qf_platform.contracts` and the environment
enum — no database, so they run anywhere.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bot"))

from qf_platform.contracts import (  # noqa: E402
    ApiError,
    EmptyReason,
    ErrorCode,
    Freshness,
    Meta,
    Units,
    age_seconds,
    clamp_limit,
    drawdown_from_equity,
    envelope,
    error_envelope,
    is_mature_sample,
    mean_abs,
    profit_factor,
    safe_float,
    sharpe_from_returns,
    signed_mean,
    to_display,
    win_rate,
)
from qf_platform.environment import Environment  # noqa: E402


# ── Defect: avg_profit_pct was AVG(ABS(pnl_pct)) ─────────────────────────────


def test_signed_mean_is_negative_for_an_all_losing_account():
    """The exact live case: 35 trades, zero wins, −₽2 373 454.

    `AVG(ABS(pnl_pct))` reported **+16,07 %**. A signed mean must be negative.
    """
    # 35 losses averaging −16,069 %, as measured.
    losses = [-16.069] * 35
    mean, n = signed_mean(losses)
    assert n == 35
    assert mean is not None and mean < 0
    assert mean == pytest.approx(-16.069)


def test_mean_abs_is_reported_separately_and_is_positive():
    """The old value survives — under a name that says what it is."""
    losses = [-16.069] * 35
    signed, _ = signed_mean(losses)
    absolute, n = mean_abs(losses)
    assert n == 35
    assert absolute == pytest.approx(16.069)
    # The two must not be confusable.
    assert signed != absolute
    assert signed == -absolute


def test_signed_mean_of_mixed_signs_can_be_negative_while_abs_is_large():
    """A set of large wins and larger losses: the distinction that matters."""
    values = [10.0, -12.0, 8.0, -20.0]
    signed, _ = signed_mean(values)
    absolute, _ = mean_abs(values)
    assert signed == pytest.approx(-3.5)
    assert absolute == pytest.approx(12.5)


def test_empty_sample_yields_none_not_zero():
    """A measured zero and an absent measurement are different facts."""
    assert signed_mean([]) == (None, 0)
    assert mean_abs([]) == (None, 0)
    assert win_rate([]) == (None, 0, 0)
    assert profit_factor([]) == (None, 0)


# ── Defect: max_drawdown carried two units under one name ────────────────────


def test_drawdown_returns_percent_and_absolute_separately():
    """−23,73 % rendered as «−0,2 %» because a fraction was printed as a percent."""
    equities = [10_000_000.0, 9_000_000.0, 7_626_545.68]
    pct, absolute, peak = drawdown_from_equity(equities)
    assert pct == pytest.approx(-23.7345, abs=1e-3)
    assert absolute == pytest.approx(-2_373_454.32, abs=0.5)
    assert peak == pytest.approx(10_000_000.0)
    # Percent is already ×100 — the whole point of the split.
    assert abs(pct) > 1


def test_drawdown_of_exactly_23_7_percent():
    equities = [1000.0, 763.0]
    pct, absolute, _ = drawdown_from_equity(equities)
    assert pct == pytest.approx(-23.7)
    assert absolute == pytest.approx(-237.0)


def test_drawdown_on_monotonically_rising_equity_is_zero():
    pct, absolute, _ = drawdown_from_equity([100.0, 110.0, 120.0, 130.0])
    assert pct == 0.0
    assert absolute == 0.0


def test_drawdown_on_empty_and_single_point_is_unmeasured_not_zero():
    """One observation is not a zero drawdown — it is no drawdown measurement."""
    assert drawdown_from_equity([]) == (None, None, None)
    assert drawdown_from_equity([100.0]) == (None, None, None)


def test_drawdown_measures_the_trough_not_the_endpoint():
    """Recovery must not erase the worst drawdown that actually happened."""
    equities = [100.0, 50.0, 100.0]
    pct, absolute, _ = drawdown_from_equity(equities)
    assert pct == pytest.approx(-50.0)
    assert absolute == pytest.approx(-50.0)


def test_drawdown_uses_the_running_peak_not_the_first_value():
    equities = [100.0, 200.0, 150.0]
    pct, absolute, peak = drawdown_from_equity(equities)
    assert pct == pytest.approx(-25.0)
    assert absolute == pytest.approx(-50.0)
    assert peak == pytest.approx(200.0)


# ── Defect: statistics without their sample size ─────────────────────────────


def test_win_rate_carries_numerator_and_denominator():
    pct, wins, n = win_rate([1.0, -1.0, 2.0, -2.0, 3.0])
    assert (wins, n) == (3, 5)
    assert pct == pytest.approx(60.0)


def test_win_rate_zero_from_no_trades_differs_from_measured_zero():
    """«н/д (0 сделок)» and «0,0 % (0 из 14)» must not be the same value."""
    absent_pct, absent_wins, absent_n = win_rate([])
    measured_pct, measured_wins, measured_n = win_rate([-1.0] * 14)
    assert absent_pct is None and absent_n == 0
    assert measured_pct == 0.0 and measured_n == 14 and measured_wins == 0


def test_profit_factor_is_none_when_undefined_never_zero():
    """No losses ⇒ unbounded, not 0. Zero profit factor is a real, terrible result."""
    value, n = profit_factor([1.0, 2.0, 3.0])
    assert value is None
    assert n == 3
    # And a genuinely zero-profit set *is* 0.0, distinguishable from the above.
    value2, n2 = profit_factor([-1.0, -2.0])
    assert value2 == 0.0 and n2 == 2


def test_sample_maturity_threshold():
    assert not is_mature_sample(29)
    assert is_mature_sample(30)
    assert not is_mature_sample(0)
    assert not is_mature_sample(None)


def test_sharpe_needs_a_usable_sample():
    """A 252-day annualised Sharpe over two observations is noise."""
    assert sharpe_from_returns([]) is None
    assert sharpe_from_returns([0.01]) is None
    # Zero variance is undefined, not infinite.
    assert sharpe_from_returns([0.01, 0.01, 0.01]) is None
    assert sharpe_from_returns([0.01, -0.005, 0.02, 0.0]) is not None


# ── Defect: NaN reaching JSON ────────────────────────────────────────────────


def test_safe_float_maps_nan_and_inf_to_default():
    """`jsonify` emits a literal NaN, which strict parsers reject — and a panel
    that fails to parse renders empty, which reads as "no data"."""
    assert safe_float(float("nan")) is None
    assert safe_float(float("inf")) is None
    assert safe_float(float("-inf")) is None
    assert safe_float("not a number") is None
    assert safe_float(None) is None
    assert safe_float("1.5") == 1.5
    assert safe_float(2) == 2.0


def test_aggregates_ignore_nan_entries():
    mean, n = signed_mean([1.0, float("nan"), 3.0])
    assert n == 2
    assert mean == pytest.approx(2.0)


# ── Defect: is_sandbox as a boolean, unknown coerced to sandbox ──────────────


def test_unknown_environment_is_never_coerced_to_sandbox():
    assert Environment.from_sandbox_flag(None) is Environment.UNKNOWN
    assert Environment.coerce(None) is Environment.UNKNOWN
    assert Environment.coerce("") is Environment.UNKNOWN
    assert Environment.coerce("something else") is Environment.UNKNOWN


def test_sandbox_flag_maps_both_ways():
    assert Environment.from_sandbox_flag(True) is Environment.SANDBOX
    assert Environment.from_sandbox_flag(False) is Environment.LIVE


def test_explicit_environment_beats_the_boolean():
    """A row labelled live is live even if the legacy boolean disagrees."""
    assert Environment.from_sandbox_flag(True, explicit="live") is Environment.LIVE
    assert Environment.from_sandbox_flag(False, explicit="backtest") is Environment.BACKTEST


def test_exchange_marker_resolves_forward_and_backtest():
    """FORWARD and BACKTEST are inexpressible in a boolean."""
    assert Environment.from_sandbox_flag(None, exchange="backtest") is Environment.BACKTEST
    assert Environment.from_sandbox_flag(None, exchange="forward") is Environment.FORWARD
    assert Environment.from_sandbox_flag(None, exchange="paper") is Environment.SANDBOX


def test_unknown_environment_is_a_fault_and_live_is_real_money():
    assert Environment.UNKNOWN.is_fault
    assert not Environment.SANDBOX.is_fault
    assert Environment.LIVE.is_real_money
    assert not Environment.SANDBOX.is_real_money


# ── Freshness: unknown age must never read as fresh ─────────────────────────


def test_freshness_reports_is_stale_none_when_age_is_unknown():
    """`None` is not `False`. Unknown freshness must not render as fresh."""
    meta = Freshness(source_as_of=None, source="candles", stale_after_seconds=60).as_meta()
    assert meta["data_age_seconds"] is None
    assert meta["is_stale"] is None


def test_freshness_marks_a_32_day_old_candle_as_stale():
    old = datetime.now(timezone.utc) - timedelta(days=32)
    meta = Freshness(source_as_of=old, source="candles", stale_after_seconds=129_600).as_meta()
    assert meta["is_stale"] is True
    assert meta["data_age_seconds"] > 32 * 86_400 - 60


def test_freshness_worst_picks_the_oldest_slice():
    now = datetime.now(timezone.utc)
    fresh = Freshness(source_as_of=now)
    stale = Freshness(source_as_of=now - timedelta(days=32))
    assert Freshness.worst([fresh, stale]).source_as_of == stale.source_as_of
    # An unknown-age slice does not win, but it does not silently become fresh
    # either — the caller sees `None`.
    assert Freshness.worst([Freshness()]).source_as_of is None


def test_naive_datetimes_are_treated_as_utc_and_rendered_with_an_offset():
    """A naive datetime rendered without an offset lets the client guess, and a
    three-hour silent shift on an equity x-axis has no visible error."""
    naive = datetime(2026, 7, 28, 12, 0, 0)
    rendered = to_display(naive)
    assert rendered is not None
    assert rendered.endswith("+03:00")
    assert age_seconds(naive) is not None


# ── The envelope ─────────────────────────────────────────────────────────────


def test_success_envelope_always_carries_as_of_environment_and_timezone():
    payload = envelope({"x": 1}, Meta(environment=Environment.SANDBOX, units=Units.MONEY, n=35))
    assert set(payload) == {"data", "meta"}
    meta = payload["meta"]
    assert meta["environment"] == "sandbox"
    assert meta["units"] == "money"
    assert meta["n"] == 35
    assert "as_of" in meta and meta["as_of"]
    assert meta["timezone"] == "MSK"


def test_meta_omits_absent_optionals_rather_than_emitting_nulls():
    meta = envelope(None, Meta())["meta"]
    assert "units" not in meta
    assert "n" not in meta
    assert "window" not in meta
    assert "empty_reason" not in meta


def test_meta_carries_the_empty_reason_so_eight_messages_stay_distinct():
    meta = envelope([], Meta(empty_reason=EmptyReason.NO_TRADES_IN_PERIOD))["meta"]
    assert meta["empty_reason"] == "NO_TRADES_IN_PERIOD"


def test_partial_response_names_what_is_missing():
    meta = envelope({}, Meta(partial=True, missing={"positions": "Не удалось загрузить."}))["meta"]
    assert meta["partial"] is True
    assert "positions" in meta["missing"]


def test_error_envelope_shape():
    payload = error_envelope(ErrorCode.DB_UNAVAILABLE, "База данных недоступна.", "cid-1")
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "id"}
    assert payload["error"]["id"] == "cid-1"


def test_api_error_messages_never_leak_internals():
    """The safe message comes from a fixed table; exception text never reaches it."""
    error = ApiError(ErrorCode.INTERNAL)
    assert "SELECT" not in error.message()
    assert "Traceback" not in error.message()
    assert error.status == 500
    # A vetted detail may be appended, but only when the caller passes one.
    assert "python -m" in ApiError(
        ErrorCode.SCHEMA_OUT_OF_DATE, detail="Выполните: python -m qf_platform.migrate"
    ).message()


def test_error_codes_map_to_sensible_statuses():
    assert ApiError(ErrorCode.UNAUTHENTICATED).status == 401
    assert ApiError(ErrorCode.FORBIDDEN).status == 403
    assert ApiError(ErrorCode.READ_ONLY_MODE).status == 403
    assert ApiError(ErrorCode.CONFLICT).status == 409
    assert ApiError(ErrorCode.RATE_LIMITED).status == 429
    assert ApiError(ErrorCode.DB_UNAVAILABLE).status == 503


# ── Query validation ─────────────────────────────────────────────────────────


def test_clamp_limit_bounds_and_rejects_garbage():
    assert clamp_limit(None, 100, 500) == 100
    assert clamp_limit(9999, 100, 500) == 500
    assert clamp_limit(0, 100, 500) == 1
    with pytest.raises(ApiError):
        clamp_limit("abc", 100, 500)
