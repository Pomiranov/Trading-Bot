"""Read-only guarantees, migration safety, and permission logic.

None of these need a database: the read-only guard is a statement classifier, the
migration runner's splitter is a pure function, and permissions are pure logic.
The one thing they *do* assert about the real world is that importing the
application performs no DDL.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOT = ROOT / "bot"
sys.path.insert(0, str(BOT))

from qf_platform.migrate import split_statements  # noqa: E402
from qf_platform.schema import PLATFORM_SCHEMA_SQL, REQUIRED_COLUMNS  # noqa: E402
from security.permissions import (  # noqa: E402
    Permission,
    Principal,
    Role,
)
from security.readonly import is_write_statement  # noqa: E402


# ── The read-only guard classifies statements, not paths ─────────────────────


@pytest.mark.parametrize("sql", [
    "INSERT INTO equity_snapshots (equity) VALUES (1)",
    "  insert into trades (ticker) values ('SBER')",
    "UPDATE paper_accounts SET balance = 1",
    "DELETE FROM paper_positions WHERE id = 1",
    "ALTER TABLE trades ADD COLUMN x INT",
    "CREATE INDEX idx ON trades (id)",
    "DROP TABLE trades",
    "TRUNCATE trades",
    "-- a leading comment\nUPDATE trades SET pnl = 0",
    "/* block */ DELETE FROM trades",
    "WITH doomed AS (SELECT id FROM trades) DELETE FROM trades WHERE id IN (SELECT id FROM doomed)",
    "SELECT * FROM trades FOR UPDATE",
])
def test_write_statements_are_detected(sql):
    assert is_write_statement(sql)


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "  select equity from equity_snapshots order by snapshot_at desc",
    # The word "update" inside a plain SELECT must not trip the guard.
    "SELECT updated_at FROM belief_system",
    "SELECT * FROM trades WHERE notes LIKE '%insert%'",
    "WITH recent AS (SELECT * FROM trades) SELECT * FROM recent",
    "EXPLAIN SELECT * FROM trades",
])
def test_read_statements_are_not_flagged(sql):
    assert not is_write_statement(sql)


def test_cte_hiding_a_write_is_caught():
    """`WITH x AS (...) DELETE FROM ...` starts with WITH but mutates."""
    assert is_write_statement(
        "WITH cutoff AS (SELECT NOW()) DELETE FROM equity_snapshots WHERE id > 0"
    )


# ── The statement splitter ───────────────────────────────────────────────────


def test_splitter_handles_the_real_schema():
    statements = split_statements(PLATFORM_SCHEMA_SQL)
    assert len(statements) > 100
    # No fragment may be comment-only, and none may be blank.
    for statement in statements:
        assert statement.strip()
        lines = [l.strip() for l in statement.splitlines() if l.strip()]
        assert any(not l.startswith("--") for l in lines)


def test_splitter_respects_dollar_quoting():
    """`PLATFORM_SCHEMA_SQL.split(';')` breaks the moment a DO block appears."""
    script = "CREATE TABLE a (x INT); DO $$ BEGIN PERFORM 1; PERFORM 2; END $$; SELECT 1;"
    statements = split_statements(script)
    assert len(statements) == 3
    assert "PERFORM 1" in statements[1] and "PERFORM 2" in statements[1]


def test_splitter_respects_string_literals():
    script = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
    statements = split_statements(script)
    assert len(statements) == 2
    assert "'a;b'" in statements[0]


def test_splitter_handles_escaped_quotes():
    script = "INSERT INTO t VALUES ('it''s; fine'); SELECT 2;"
    statements = split_statements(script)
    assert len(statements) == 2


def test_splitter_ignores_semicolons_in_line_comments():
    script = "SELECT 1; -- a comment; with a semicolon\nSELECT 2;"
    assert len(split_statements(script)) == 2


# ── The schema declares what the dashboard reads ─────────────────────────────


def test_required_columns_cover_the_environment_split():
    """Every table the dashboard filters by environment must declare the column."""
    for table in ("trades", "paper_trades", "equity_snapshots", "trading_signals",
                  "skipped_signals"):
        assert "environment" in REQUIRED_COLUMNS[table], table


def test_required_columns_cover_the_gate_decision():
    assert "gate_decision" in REQUIRED_COLUMNS["trading_signals"]
    assert "gate_reason" in REQUIRED_COLUMNS["trading_signals"]
    assert "gate_stage" in REQUIRED_COLUMNS["skipped_signals"]
    assert "reason_text" in REQUIRED_COLUMNS["skipped_signals"]


def test_required_columns_cover_auth_and_audit():
    assert "password_hash" in REQUIRED_COLUMNS["dashboard_users"]
    assert "csrf_token" in REQUIRED_COLUMNS["dashboard_sessions"]
    assert "state_before" in REQUIRED_COLUMNS["audit_events"]
    assert "actor_role" in REQUIRED_COLUMNS["audit_events"]


def test_index_on_a_migrated_column_comes_after_its_alter():
    """The shipped ordering defect: `CREATE INDEX … (strategy_id)` ran *before*
    the ALTER that adds `strategy_id`, and because the whole script ran in one
    transaction, the failure rolled back all forty ALTERs — silently, with four
    endpoints then returning 500 forever and a clean browser console."""
    statements = split_statements(PLATFORM_SCHEMA_SQL)
    add_strategy = next(
        i for i, s in enumerate(statements)
        if "ADD COLUMN IF NOT EXISTS strategy_id" in s
    )
    index_strategy = next(
        i for i, s in enumerate(statements)
        if "idx_trades_strategy" in s
    )
    assert index_strategy > add_strategy

    add_sandbox = next(
        i for i, s in enumerate(statements)
        if "ADD COLUMN IF NOT EXISTS is_sandbox" in s
    )
    index_sandbox = next(i for i, s in enumerate(statements) if "idx_trades_sandbox" in s)
    assert index_sandbox > add_sandbox


def test_environment_index_follows_its_column():
    statements = split_statements(PLATFORM_SCHEMA_SQL)
    add = next(i for i, s in enumerate(statements)
               if "ALTER TABLE trades" in s and "environment" in s)
    index = next(i for i, s in enumerate(statements) if "idx_trades_environment" in s)
    assert index > add


# ── Importing the app must not perform DDL ───────────────────────────────────


def test_importing_the_platform_modules_touches_no_database():
    """`bot/ui/dashboard.py` used to connect, migrate, seed hypotheses and start
    the trading engine at *module import*. Importing the schema and bootstrap
    modules must be inert.

    Run in a subprocess with a deliberately unreachable database: if any import
    tries to connect, the process fails.
    """
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import qf_platform.schema, qf_platform.bootstrap, qf_platform.migrate\n"
        "import qf_platform.contracts, qf_platform.environment\n"
        "import security.readonly, security.permissions, security.passwords\n"
        "print('IMPORTS_CLEAN')\n" % str(BOT)
    )
    env = dict(os.environ)
    env.update({
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "1",           # nothing listens here
        "DB_PASSWORD": "x",
        "TELEGRAM_TOKEN": "",
        "TINKOFF_TOKEN": "",
    })
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=60, env=env, cwd=str(BOT),
    )
    assert "IMPORTS_CLEAN" in result.stdout, result.stderr[-2000:]


def test_learning_package_import_does_not_connect():
    """`feedback_store` was a module-level singleton whose __init__ ran DDL, so
    importing the `learning` package migrated `trades`."""
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import learning.feedback as f\n"
        "assert type(f.feedback_store).__name__ == '_LazyFeedbackStore', type(f.feedback_store)\n"
        "print('LAZY_OK')\n" % str(BOT)
    )
    env = dict(os.environ)
    env.update({"DB_HOST": "127.0.0.1", "DB_PORT": "1", "DB_PASSWORD": "x"})
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=60, env=env, cwd=str(BOT),
    )
    assert "LAZY_OK" in result.stdout, result.stderr[-2000:]


def test_ensure_platform_schema_refuses_ddl_by_default(monkeypatch):
    """Verification, not migration, unless explicitly permitted."""
    from qf_platform import bootstrap

    calls = {"apply": 0, "verify": 0}

    class Report:
        current = False

        def describe(self):
            return "нет колонок: trades(environment)"

    monkeypatch.setattr("qf_platform.migrate.verify_schema", lambda engine: Report())
    monkeypatch.setattr(
        "qf_platform.migrate.apply_schema",
        lambda engine, applied_by="": calls.__setitem__("apply", calls["apply"] + 1),
    )
    monkeypatch.delenv("QF_ALLOW_STARTUP_DDL", raising=False)

    assert bootstrap.ensure_platform_schema(object()) is False
    assert calls["apply"] == 0


# ── Permissions ──────────────────────────────────────────────────────────────


def observer():
    return Principal(user_id=1, username="o", role=Role.OBSERVER, trading_authorized=False)


def operator():
    return Principal(user_id=2, username="p", role=Role.OPERATOR, trading_authorized=False)


def administrator(trading=False):
    return Principal(user_id=3, username="a", role=Role.ADMINISTRATOR, trading_authorized=trading)


def test_observer_can_read_and_nothing_else():
    principal = observer()
    assert principal.can(Permission.VIEW)
    assert not principal.can(Permission.ENGINE_CONTROL)
    assert not principal.can(Permission.MANAGE_CREDENTIALS)
    assert not principal.can(Permission.CLOSE_POSITION)
    assert not principal.can(Permission.VIEW_AUDIT)


def test_operator_controls_the_engine_but_not_credentials():
    principal = operator()
    assert principal.can(Permission.ENGINE_CONTROL)
    assert principal.can(Permission.RUN_BACKTEST)
    assert not principal.can(Permission.MANAGE_CREDENTIALS)


def test_administrator_cannot_trade_without_the_separate_capability(monkeypatch):
    """An administrator who manages configuration must not be able to move money
    by virtue of the role alone."""
    monkeypatch.setenv("QF_DASHBOARD_ALLOW_TRADING_ACTIONS", "1")
    assert not administrator(trading=False).can(Permission.CLOSE_POSITION)
    assert administrator(trading=True).can(Permission.CLOSE_POSITION)


def test_trading_is_off_by_default_even_with_the_capability(monkeypatch):
    monkeypatch.delenv("QF_DASHBOARD_ALLOW_TRADING_ACTIONS", raising=False)
    assert not administrator(trading=True).can(Permission.CLOSE_POSITION)


def test_live_switch_needs_its_own_flag(monkeypatch):
    monkeypatch.setenv("QF_DASHBOARD_ALLOW_TRADING_ACTIONS", "1")
    monkeypatch.delenv("QF_DASHBOARD_ALLOW_LIVE", raising=False)
    assert not administrator(trading=True).can(Permission.SWITCH_TO_LIVE)
    monkeypatch.setenv("QF_DASHBOARD_ALLOW_LIVE", "1")
    assert administrator(trading=True).can(Permission.SWITCH_TO_LIVE)


def test_unknown_role_degrades_to_least_privilege():
    assert Role.coerce("superuser") is Role.OBSERVER
    assert Role.coerce(None) is Role.OBSERVER
    assert Role.coerce("") is Role.OBSERVER


def test_denial_reason_names_the_requirement():
    reason = observer().denial_reason(Permission.ENGINE_CONTROL)
    assert "Оператор" in reason
    assert "управление движком" in reason


def test_public_dict_never_exposes_a_secret():
    payload = administrator(trading=True).to_public_dict()
    assert "password" not in str(payload).lower()
    assert "session" not in payload
    assert set(payload) == {
        "username", "display_name", "role", "role_label",
        "trading_authorized", "permissions",
    }
