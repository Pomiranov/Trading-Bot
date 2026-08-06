"""The one authoritative migration path for the QuantFlow platform schema.

Why this exists
---------------
``bot/ui/dashboard.py`` used to call ``ensure_platform_schema()`` at *module
import time*, which executed ~40 ``ALTER TABLE`` statements against the live
database. Starting the web server was therefore a migration. Worse, every
statement ran inside a single ``engine.begin()``, so one failure rolled back all
of them — and the failure was silent: four endpoints returned HTTP 500 forever
while the browser console stayed clean.

Two changes fix that class of bug for good:

1. **Per-statement transactions.** A statement that fails no longer takes its
   predecessors with it, and the failing statement is reported by index and by
   its first line, so the operator knows exactly what to fix.
2. **Explicit invocation.** Nothing here runs on import. The dashboard calls
   ``verify_schema()`` (read-only) at boot and refuses to serve stale data with
   a ``SCHEMA_OUT_OF_DATE`` envelope instead of migrating behind the operator's back.

Usage
-----
::

    python -m qf_platform.migrate --check            # report drift, write nothing
    python -m qf_platform.migrate                    # apply (asks for confirmation)
    python -m qf_platform.migrate --yes              # apply unattended (CI/deploy)
    python -m qf_platform.migrate --create-user NAME --role administrator

``--check`` is safe against production. ``--yes`` is not, and says so.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Allow `python -m qf_platform.migrate` from the repo root as well as from bot/.
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from qf_platform.schema import (  # noqa: E402
    PLATFORM_SCHEMA_SQL,
    REQUIRED_COLUMNS,
    SCHEMA_VERSION,
)


def split_statements(script: str) -> list[str]:
    """Split a DDL script into statements, honouring dollar-quoted bodies.

    ``PLATFORM_SCHEMA_SQL.split(";")`` is what the old bootstrap did. It is
    correct only as long as nobody ever adds a ``DO $$ … $$`` block or a
    semicolon inside a string literal — at which point it silently produces
    fragments that fail with a syntax error pointing at the wrong line.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(script)
    dollar_tag: Optional[str] = None
    in_single = False
    in_line_comment = False

    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if dollar_tag:
            if script.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":          # escaped quote
                    buf.append(nxt)
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            in_line_comment = True
            buf.append(ch)
            i += 1
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == "$":
            close = script.find("$", i + 1)
            tag_body = script[i + 1:close] if close != -1 else None
            if close != -1 and (tag_body == "" or tag_body.isidentifier()):
                dollar_tag = script[i:close + 1]
                buf.append(dollar_tag)
                i = close + 1
                continue

        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if not _is_comment_only(s)]


def _is_comment_only(stmt: str) -> bool:
    for line in stmt.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return False
    return True


def _summary(stmt: str, width: int = 110) -> str:
    """First non-comment line, for a log message that identifies the statement."""
    for line in stmt.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return stripped[:width]
    return stmt[:width]


@dataclass
class MigrationResult:
    applied: int = 0
    skipped: int = 0
    failures: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def apply_schema(engine, *, applied_by: str = "cli") -> MigrationResult:
    """Execute the schema, one statement per transaction.

    Never raises for a single bad statement: it records the failure and keeps
    going, because a legacy database usually needs *most* of the script and a
    stop-on-first-error run leaves the schema half-built with no report.
    """
    from sqlalchemy import text

    statements = split_statements(PLATFORM_SCHEMA_SQL)
    result = MigrationResult()

    for index, stmt in enumerate(statements, start=1):
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
            result.applied += 1
        except Exception as exc:  # noqa: BLE001 — every statement is reported
            message = str(exc).splitlines()[0][:300]
            result.failures.append((index, _summary(stmt), message))
            logger.error(
                "Migration statement %d/%d failed: %s\n  → %s",
                index, len(statements), _summary(stmt), message,
            )

    if result.ok:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO schema_migrations (version, applied_by, statements, notes)"
                        " VALUES (:v, :by, :n, :notes)"
                        " ON CONFLICT (version) DO UPDATE"
                        " SET applied_at = NOW(), applied_by = :by, statements = :n"
                    ),
                    {
                        "v": SCHEMA_VERSION,
                        "by": applied_by[:64],
                        "n": result.applied,
                        "notes": "qf_platform.migrate",
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not record schema version: %s", exc)

    return result


@dataclass
class SchemaReport:
    reachable: bool = False
    version: Optional[int] = None
    expected_version: int = SCHEMA_VERSION
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def current(self) -> bool:
        return self.reachable and not self.missing_tables and not self.missing_columns

    def describe(self) -> str:
        if not self.reachable:
            return f"схема недоступна: {self.error or 'нет соединения'}"
        if self.current:
            return f"схема актуальна (версия в БД: {self.version}, ожидается {self.expected_version})"
        parts = []
        if self.missing_tables:
            parts.append("нет таблиц: " + ", ".join(sorted(self.missing_tables)))
        if self.missing_columns:
            parts.append(
                "нет колонок: "
                + "; ".join(f"{t}({', '.join(cols)})" for t, cols in sorted(self.missing_columns.items()))
            )
        return " · ".join(parts)


def verify_schema(engine) -> SchemaReport:
    """Read-only drift check. Issues SELECTs against the catalog only.

    This is what the web process calls at boot. It never writes, so importing
    or starting the dashboard cannot migrate anything.
    """
    from sqlalchemy import text

    report = SchemaReport()
    if engine is None:
        report.error = "engine is None"
        return report

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns"
                    " WHERE table_schema = current_schema()"
                )
            ).fetchall()
            present: dict[str, set[str]] = {}
            for table, column in rows:
                present.setdefault(table, set()).add(column)

            for table, columns in REQUIRED_COLUMNS.items():
                if table not in present:
                    report.missing_tables.append(table)
                    continue
                missing = [c for c in columns if c not in present[table]]
                if missing:
                    report.missing_columns[table] = missing

            if "schema_migrations" in present:
                row = conn.execute(
                    text("SELECT MAX(version) FROM schema_migrations")
                ).fetchone()
                report.version = int(row[0]) if row and row[0] is not None else None

        report.reachable = True
    except Exception as exc:  # noqa: BLE001
        report.error = str(exc).splitlines()[0][:300]

    return report


# ── Admin: create the first dashboard user ────────────────────────────────────


def create_user(
    engine,
    username: str,
    password: str,
    *,
    role: str = "observer",
    trading_authorized: bool = False,
    display_name: Optional[str] = None,
) -> None:
    """Create or update a dashboard operator.

    The password never reaches the database, the logs or the repository — only
    a KDF digest does. There is deliberately no default password and no way to
    create a user without supplying one.
    """
    from sqlalchemy import text

    from security.passwords import hash_password  # local import: keeps CLI light

    if not username or not username.strip():
        raise ValueError("username is required")
    if not password or len(password) < 12:
        raise ValueError("password must be at least 12 characters")

    digest = hash_password(password)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO dashboard_users
                    (username, password_hash, role, trading_authorized, display_name)
                VALUES (:u, :h, :r, :t, :d)
                ON CONFLICT (username) DO UPDATE
                   SET password_hash = :h, role = :r, trading_authorized = :t,
                       display_name = COALESCE(:d, dashboard_users.display_name),
                       failed_attempts = 0, locked_until = NULL,
                       password_changed_at = NOW(), updated_at = NOW(),
                       is_active = true
                """
            ),
            {
                "u": username.strip(),
                "h": digest,
                "r": role,
                "t": bool(trading_authorized),
                "d": display_name,
            },
        )


def _build_engine():
    from sqlalchemy import create_engine

    from config import config

    return create_engine(config.db.dsn, pool_pre_ping=True, pool_size=1, max_overflow=1)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m qf_platform.migrate",
        description="Apply or verify the QuantFlow platform schema.",
    )
    parser.add_argument("--check", action="store_true",
                       help="report drift and exit; writes nothing")
    parser.add_argument("--yes", action="store_true",
                       help="apply without the interactive confirmation")
    parser.add_argument("--create-user", metavar="USERNAME",
                       help="create or update a dashboard operator")
    parser.add_argument("--role", default="observer",
                       choices=["observer", "operator", "administrator"])
    parser.add_argument("--trading-authorized", action="store_true",
                       help="grant the separate trading permission")
    parser.add_argument("--display-name", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        engine = _build_engine()
    except Exception as exc:  # noqa: BLE001
        print(f"Не удалось подключиться к базе: {exc}", file=sys.stderr)
        return 2

    if args.create_user:
        password = os.environ.get("QF_NEW_USER_PASSWORD") or getpass.getpass(
            f"Пароль для {args.create_user} (мин. 12 символов): "
        )
        confirm = os.environ.get("QF_NEW_USER_PASSWORD") or getpass.getpass("Повторите: ")
        if password != confirm:
            print("Пароли не совпадают.", file=sys.stderr)
            return 2
        try:
            create_user(
                engine, args.create_user, password,
                role=args.role,
                trading_authorized=args.trading_authorized,
                display_name=args.display_name,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Не удалось создать пользователя: {exc}", file=sys.stderr)
            return 1
        print(f"Пользователь {args.create_user} создан/обновлён, роль {args.role}"
              f"{', торговля разрешена' if args.trading_authorized else ''}.")
        return 0

    report = verify_schema(engine)
    print(report.describe())

    if args.check:
        return 0 if report.current else 1

    if report.current:
        print("Изменений не требуется.")
        return 0

    if not args.yes:
        print("\nБудет выполнен DDL против базы "
              f"{os.environ.get('DB_NAME', 'trading_bot')}. "
              "Сделайте резервную копию перед продолжением.")
        answer = input("Продолжить? введите MIGRATE: ").strip()
        if answer != "MIGRATE":
            print("Отменено.")
            return 1

    result = apply_schema(engine, applied_by=getpass.getuser()[:64])
    print(f"Выполнено выражений: {result.applied}")
    if result.failures:
        print(f"Ошибок: {len(result.failures)}", file=sys.stderr)
        for index, summary, message in result.failures:
            print(f"  #{index}: {summary}\n      → {message}", file=sys.stderr)
        return 1

    after = verify_schema(engine)
    print(after.describe())
    return 0 if after.current else 1


if __name__ == "__main__":
    raise SystemExit(main())
