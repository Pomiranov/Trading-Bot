"""Flask application factory for the operational dashboard.

The previous entry point did all of this at *module import* time: connect to
PostgreSQL, execute ~40 ``ALTER TABLE`` statements, seed hypotheses, instantiate
an ``IndicatorEngine`` and a ``RulesEngine``, and call ``paper_engine.start()``.
Importing the module therefore migrated the database and began placing simulated
trades — which is also why the dashboard could not be launched during the audit.

Everything is now explicit and ordered:

1. build the app,
2. connect (read-only verification of the schema — never DDL),
3. register security, then routes,
4. optionally start background collectors,
5. and only on an explicit opt-in, start the trading engine.

``create_app()`` is safe to call from a test. It touches no broker and starts no
thread unless asked.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

from flask import Flask, g, request

_BOT_DIR = Path(__file__).resolve().parent.parent
if str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

logger = logging.getLogger(__name__)

_UI_DIR = Path(__file__).resolve().parent

#: Bumped together with any change to the static bundle. Referenced once, in the
#: template context, rather than hardcoded 18 times as `?v=16` was.
ASSET_VERSION = "20260729"


def _build_engine(dsn: str):
    from sqlalchemy import create_engine, text

    # pool_size was 2 with max_overflow 3 — five connections for everything,
    # against a nine-request poll batch. The new client makes one composed
    # request per cycle, but the pool still needs headroom for the engine
    # threads that share this process.
    engine = create_engine(
        dsn,
        pool_pre_ping=True,
        pool_size=int(os.getenv("QF_DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("QF_DB_MAX_OVERFLOW", "10")),
        pool_recycle=1800,
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


def create_app(*, start_background: Optional[bool] = None) -> Flask:
    from config import config
    from security.bootstrap import bootstrap_security

    bootstrap_security(config, service_name="dashboard")

    app = Flask(
        __name__,
        template_folder=str(_UI_DIR / "templates"),
        static_folder=str(_UI_DIR / "static"),
        static_url_path="/static",
    )

    # Static assets are content-addressed by ASSET_VERSION, so they may be cached
    # hard. `SEND_FILE_MAX_AGE_DEFAULT = 0` forced 19 conditional round-trips on
    # every cold load — 418 of 418 responses were 304s.
    app.config.update(
        TEMPLATES_AUTO_RELOAD=os.getenv("QF_DASHBOARD_DEBUG", "0") == "1",
        SEND_FILE_MAX_AGE_DEFAULT=int(os.getenv("QF_STATIC_MAX_AGE", str(60 * 60 * 24 * 30))),
        MAX_CONTENT_LENGTH=1024 * 1024,
        JSON_SORT_KEYS=False,
    )

    from security.errors import register_error_handlers
    from security.http_middleware import register_request_middleware
    from security.readonly import (
        engine_threads_allowed,
        install_engine_guard,
        read_only_enabled,
    )

    register_request_middleware(app)
    register_error_handlers(app)

    # ── Database ─────────────────────────────────────────────────────────────
    engine = None
    schema_ok = False
    try:
        engine = _build_engine(config.db.dsn)
        logger.info("Connected to PostgreSQL at %s", config.db.host)
    except Exception as exc:  # noqa: BLE001
        logger.error("DB unavailable: %s", exc)

    if engine is not None:
        install_engine_guard(engine)
        from qf_platform.bootstrap import ensure_platform_schema

        # Verification only. Migration is `python -m qf_platform.migrate`.
        schema_ok = ensure_platform_schema(engine)
        if not schema_ok:
            logger.error(
                "Схема БД не соответствует ожиданиям приложения. "
                "Дашборд поднимется, но API вернёт SCHEMA_OUT_OF_DATE."
            )

    app.config["QF_ENGINE"] = engine
    app.config["QF_SCHEMA_OK"] = schema_ok

    # ── Security wiring ──────────────────────────────────────────────────────
    from qf_platform.repositories.auth_repository import AuthRepository
    from qf_platform.repositories.events_repository import EventsRepository
    from security import audit as audit_module
    from security.errors import set_events_sink
    from security.guards import set_auth_repository
    from security.session_auth import init_session_auth, register_session_hooks

    if engine is not None:
        audit_module.use_engine(engine)
        set_auth_repository(AuthRepository(engine))
        if schema_ok:
            set_events_sink(EventsRepository(engine))
        init_session_auth(engine)
        session_svc = None
        try:
            from security.session_auth import session_service

            session_svc = session_service()
            if session_svc is not None and schema_ok:
                session_svc.ensure_bootstrap_user()
        except Exception:  # noqa: BLE001
            logger.warning("Bootstrap user check failed", exc_info=True)

    register_session_hooks(app)
    _register_access_control(app)
    _register_latency_probe(app)

    # ── Routes ───────────────────────────────────────────────────────────────
    from ui.api.v2 import init_v2

    app.register_blueprint(init_v2(engine, schema_ok=schema_ok))

    if engine is not None:
        from ui.api.platform_routes import init_platform_routes, platform_bp

        init_platform_routes(engine)
        app.register_blueprint(platform_bp)

    from ui.views import register_views

    register_views(app, engine=engine, asset_version=ASSET_VERSION)

    from ui.legacy_api import register_legacy_api

    register_legacy_api(app, engine=engine)

    # ── Background work ──────────────────────────────────────────────────────
    should_start = (
        start_background
        if start_background is not None
        else not read_only_enabled()
    )

    if engine is not None and should_start:
        from qf_platform.services.health_service import init_health_service

        init_health_service(engine, start=True)
    elif engine is not None:
        # Read-only mode still needs health data; collect once, synchronously,
        # without starting a thread.
        from qf_platform.services.health_service import init_health_service

        svc = init_health_service(engine, start=False)
        try:
            svc.collect_once()
        except Exception:  # noqa: BLE001
            logger.warning("Health collection failed", exc_info=True)

    if engine is not None and should_start and engine_threads_allowed():
        _start_engine(engine)
    elif engine is not None:
        logger.info(
            "Торговый движок не запущен автоматически "
            "(QF_DASHBOARD_AUTOSTART_ENGINE=1 для автостарта, либо кнопка оператора)."
        )

    logger.info(
        "Dashboard ready · read_only=%s · schema_ok=%s · engine_autostart=%s",
        read_only_enabled(), schema_ok, engine_threads_allowed(),
    )
    return app


def _start_engine(engine) -> None:
    """Start the paper engine and its learning loop, explicitly.

    Retained as an opt-in because the sandbox is genuinely meant to run
    continuously in this deployment. What changed is that it is no longer a side
    effect of an import, so a test, a migration or a read-only QA pass cannot
    accidentally begin trading.
    """
    from config import config

    try:
        from engine.paper_engine import paper_engine
        from learning.sandbox_learning_loop import SandboxLearningLoop

        loop = SandboxLearningLoop(dsn=config.db.dsn)
        paper_engine.set_db_engine(engine)
        paper_engine.set_learning_loop(loop)
        paper_engine.start()
        logger.info("PaperEngine + SandboxLearningLoop started (explicit opt-in)")
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось запустить движок: %s", exc, exc_info=True)

    try:
        from learning.knowledge_seeder import seed_knowledge_hypotheses

        seed_knowledge_hypotheses(engine)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Knowledge seeding failed: %s", exc)


def _register_access_control(app: Flask) -> None:
    """Authentication is the default; a route must opt out to be public.

    The old model was the inverse — a single ``before_request`` allow-listed by IP,
    and any route nobody remembered to think about was open. Here the allow-list is
    of *paths that may be anonymous*, and it is short enough to audit by eye.
    """
    from qf_platform.contracts import ApiError, ErrorCode
    from security.csrf import validate_csrf
    from security.session_auth import current_principal

    public_exact = {
        "/health",
        "/login",
        "/api/v2/auth/session",
        "/api/v2/auth/login",
        "/api/internal/push",
    }
    public_prefixes = ("/static/", "/miniapp")

    @app.before_request
    def _enforce_access():  # noqa: ANN202
        path = request.path or ""
        if request.method == "OPTIONS":
            return None
        if path in public_exact or path.startswith(public_prefixes):
            return None

        if current_principal() is None:
            if path.startswith("/api/"):
                raise ApiError(ErrorCode.UNAUTHENTICATED)
            # A browser navigating to a protected page gets the sign-in surface.
            from flask import redirect, url_for

            return redirect(url_for("views.login", next=path))

        # Belt-and-braces: `@mutating` validates CSRF per route, and this catches
        # any mutating route that forgets the decorator.
        validate_csrf(request)
        return None


def _register_latency_probe(app: Flask) -> None:
    """Measure our own request latency so the health strip can report it."""

    @app.before_request
    def _mark_start():  # noqa: ANN202
        g.qf_started_at = time.monotonic()

    @app.after_request
    def _record_latency(response):  # noqa: ANN202
        started = getattr(g, "qf_started_at", None)
        if started is not None and (request.path or "").startswith("/api/"):
            from qf_platform.services.health_service import health_service

            svc = health_service()
            if svc is not None:
                svc.latency.observe((time.monotonic() - started) * 1000.0)
        return response
