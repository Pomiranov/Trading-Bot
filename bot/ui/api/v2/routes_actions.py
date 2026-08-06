"""Mutating routes: authentication and the operator action set.

Every route here goes through ``@mutating``, which makes all of the following
structural rather than remembered per handler: read-only mode blocks it, CSRF is
validated, a reason is captured where required, an idempotency key is honoured
where the action moves money, and exactly one audit row is written per attempt —
success or failure.

Trading-tier actions additionally require ``trading_authorized`` *and* the
``QF_DASHBOARD_ALLOW_TRADING_ACTIONS`` switch, which is off by default. A control
that can close a position but has no audit trail and no idempotency is worse than
no control, so the safe default is the shipped one.
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from qf_platform.contracts import ApiError, ErrorCode, Meta, Units, envelope
from qf_platform.environment import Environment
from qf_platform.repositories.events_repository import EventCategory, EventsRepository
from qf_platform.services.positions_service import PositionsService
from security.guards import (
    ActionContext,
    mutating,
    require_auth,
    require_permission,
    require_typed_confirmation,
)
from security.permissions import Permission
from security.session_auth import (
    clear_session_cookies,
    client_ip,
    current_principal,
    session_service,
    set_session_cookies,
)

from . import arg_environment, engine_or_fail, engine_unchecked, v2

logger = logging.getLogger(__name__)


def _events() -> EventsRepository | None:
    engine = engine_unchecked()
    return EventsRepository(engine) if engine is not None else None


def _log(level: str, message: str, *, category: str, **metadata) -> None:
    repo = _events()
    if repo is None:
        return
    from security.request_context import get_correlation_id

    repo.log_event(
        level, "dashboard", message, metadata,
        category=category, correlation_id=get_correlation_id(),
    )


# ── Authentication ────────────────────────────────────────────────────────────

@v2.get("/auth/session")
def get_session():
    """Who am I? Public by design — the login screen needs to ask.

    Returns 200 with ``authenticated: false`` rather than 401, so the client can
    distinguish "not logged in" (show the sign-in surface) from "something broke"
    (show an error) without treating every cold load as a failure.
    """
    principal = current_principal()
    svc = session_service()
    from security.csrf import token_for_client
    from security.readonly import describe as readonly_describe

    payload = {
        "authenticated": principal is not None,
        "user": principal.to_public_dict() if principal else None,
        "csrf_token": token_for_client(),
        "read_only": readonly_describe()["read_only"],
        # A fresh deployment with no operator must say so, not fail silently on
        # a login form that can never succeed.
        "has_users": svc.has_any_user() if svc else False,
    }
    return envelope(payload, Meta(environment=Environment.UNKNOWN, units=Units.ENUM))


@v2.post("/auth/login")
def post_login():
    """Password login. Deliberately not wrapped in ``@mutating``.

    There is no session yet, so there is no session-bound CSRF token to check;
    ``security.csrf`` exempts this path and relies on the origin check plus the
    rate limiter instead. The audit row is written here by hand for the same
    reason — ``@mutating`` requires an authenticated principal.
    """
    from security.audit import audit_record
    from security.csrf import validate_csrf
    from security.readonly import read_only_enabled

    validate_csrf(request)

    svc = session_service()
    if svc is None:
        raise ApiError(ErrorCode.DB_UNAVAILABLE)

    body = request.get_json(silent=True) or {}
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        raise ApiError(ErrorCode.VALIDATION_FAILED, detail="Введите логин и пароль.")

    result = svc.authenticate(
        username, password,
        client_ip=client_ip(),
        user_agent=request.headers.get("User-Agent", "")[:256],
    )

    if not result.ok:
        # One generic message for every failure kind. The specific kind goes to
        # the audit log, never to the client — distinguishing "no such user" from
        # "wrong password" is an account-enumeration oracle.
        audit_record(
            event_type="auth.login",
            actor_type="client",
            actor_id=username[:128],
            outcome="denied",
            client_ip=client_ip(),
            metadata={"kind": result.failure_kind},
        )
        _log(
            "WARN", f"Неудачный вход: {username}",
            category=EventCategory.AUTH, kind=result.failure_kind,
        )
        if result.failure_kind == "rate_limited":
            raise ApiError(ErrorCode.RATE_LIMITED)
        raise ApiError(
            ErrorCode.UNAUTHENTICATED,
            detail="Неверный логин или пароль.",
        )

    principal = result.principal
    audit_record(
        event_type="auth.login",
        actor_type="dashboard_user",
        actor_id=principal.username,
        actor_role=principal.role.value,
        outcome="success",
        client_ip=client_ip(),
    )
    _log("INFO", f"Вход: {principal.username}", category=EventCategory.AUTH)

    payload = envelope(
        {
            "authenticated": True,
            "user": principal.to_public_dict(),
            "csrf_token": result.csrf_token,
            "read_only": read_only_enabled(),
        },
        Meta(environment=Environment.UNKNOWN, units=Units.ENUM),
    )
    response = jsonify(payload)
    return set_session_cookies(
        response, session_id=result.session_id, csrf_token=result.csrf_token
    )


@v2.post("/auth/logout")
@require_auth
@mutating(action="auth.logout", target_type="session")
def post_logout(action: ActionContext):
    svc = session_service()
    principal = current_principal()
    action.record(target=principal.username, target_type="session")
    if svc is not None and principal is not None:
        svc.logout(principal.session_id)
    _log("INFO", f"Выход: {principal.username}", category=EventCategory.AUTH)
    response = jsonify(envelope({"authenticated": False}, Meta()))
    return clear_session_cookies(response)


@v2.post("/auth/logout-all")
@require_auth
@mutating(action="auth.logout_all", target_type="session")
def post_logout_all(action: ActionContext):
    svc = session_service()
    principal = current_principal()
    action.record(target=principal.username, target_type="session")
    if svc is not None:
        svc.logout_everywhere(principal.user_id)
    response = jsonify(envelope({"authenticated": False}, Meta()))
    return clear_session_cookies(response)


@v2.post("/auth/password")
@require_auth
@mutating(action="auth.password_change", target_type="user", require_reason=False)
def post_change_password(action: ActionContext):
    from qf_platform.repositories.auth_repository import AuthRepository
    from security import passwords

    engine = engine_or_fail()
    principal = current_principal()
    body = request.get_json(silent=True) or {}
    current = str(body.get("current_password") or "")
    new = str(body.get("new_password") or "")

    repo = AuthRepository(engine)
    user = repo.get_user(principal.user_id)
    if user is None or not passwords.verify_password(user["password_hash"], current):
        # Same generic wording as login, for the same reason.
        raise ApiError(ErrorCode.UNAUTHENTICATED, detail="Неверный текущий пароль.")

    problem = passwords.password_strength_error(new)
    if problem:
        raise ApiError(ErrorCode.VALIDATION_FAILED, detail=problem, field_name="new_password")

    repo.update_password(principal.user_id, passwords.hash_password(new))
    # Changing a password invalidates every other session — that is the point of
    # changing it.
    repo.revoke_user_sessions(principal.user_id)
    action.record(target=principal.username, after={"password_changed": True})
    _log("WARN", f"Пароль изменён: {principal.username}", category=EventCategory.AUTH)

    response = jsonify(envelope({"password_changed": True}, Meta()))
    return clear_session_cookies(response)


# ── Engine control (operator tier) ────────────────────────────────────────────

@v2.post("/engine/start")
@require_permission(Permission.ENGINE_CONTROL)
@mutating(action="engine.start", target_type="engine", require_reason=False)
def post_engine_start(action: ActionContext):
    engine = engine_or_fail()
    from qf_platform.services.environment_service import EnvironmentService

    svc = EnvironmentService(engine)
    before_state, _, _ = svc.engine_status()

    try:
        from engine.paper_engine import paper_engine

        paper_engine.start(db_engine=engine)
        running = paper_engine.is_running()
    except Exception as exc:  # noqa: BLE001
        logger.error("Engine start failed: %s", exc, exc_info=True)
        action.record(target="paper_engine", before={"state": before_state})
        raise ApiError(ErrorCode.INTERNAL, detail="Не удалось запустить движок.")

    after_state, detail, _ = svc.engine_status()
    action.record(
        target="paper_engine",
        before={"state": before_state},
        after={"state": after_state, "running": running},
    )
    _log(
        "WARN", f"Движок запущен оператором {current_principal().username}",
        category=EventCategory.ENGINE,
    )
    return envelope(
        {"state": after_state, "running": running, "detail": detail},
        Meta(environment=arg_environment(), units=Units.ENUM),
    )


@v2.post("/engine/stop")
@require_permission(Permission.ENGINE_CONTROL)
@mutating(action="engine.stop", target_type="engine", require_reason=True)
def post_engine_stop(action: ActionContext):
    """Stop requires a reason; start does not.

    Asymmetric on purpose: an engine that is off needs an explanation the next
    operator can read, and «почему бот не торговал вчера» is otherwise
    unanswerable.
    """
    engine = engine_or_fail()
    from qf_platform.services.environment_service import EnvironmentService

    svc = EnvironmentService(engine)
    before_state, _, _ = svc.engine_status()

    try:
        from engine.paper_engine import paper_engine

        paper_engine.stop()
        running = paper_engine.is_running()
    except Exception as exc:  # noqa: BLE001
        logger.error("Engine stop failed: %s", exc, exc_info=True)
        action.record(target="paper_engine", before={"state": before_state})
        raise ApiError(ErrorCode.INTERNAL, detail="Не удалось остановить движок.")

    after_state, detail, _ = svc.engine_status()
    action.record(
        target="paper_engine",
        before={"state": before_state},
        after={"state": after_state, "running": running},
    )
    _log(
        "WARN",
        f"Движок остановлен оператором {current_principal().username}: {action.reason}",
        category=EventCategory.ENGINE,
    )
    return envelope(
        {"state": after_state, "running": running, "detail": detail},
        Meta(environment=arg_environment(), units=Units.ENUM),
    )


@v2.post("/faults/<code>/acknowledge")
@require_permission(Permission.ACKNOWLEDGE_FAULT)
@mutating(action="fault.acknowledge", target_type="fault", require_reason=False)
def post_acknowledge_fault(code: str, action: ActionContext):
    """Acknowledgement is recorded, not persisted as suppression.

    A fault that can be dismissed is a fault that gets dismissed. The row lands
    in the event log so the next operator can see it was seen; the fault itself
    stays visible until its cause is gone.
    """
    if len(code) > 64:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="code")
    action.record(target=code, after={"acknowledged_by": current_principal().username})
    _log(
        "INFO",
        f"Инцидент {code} подтверждён оператором {current_principal().username}",
        category=EventCategory.OPERATOR,
    )
    return envelope({"acknowledged": code}, Meta(environment=arg_environment()))


# ── Learning cycle (operator tier) ────────────────────────────────────────────

@v2.post("/learning/run-cycle")
@require_permission(Permission.RUN_LEARNING_CYCLE)
@mutating(action="learning.run_cycle", target_type="learning", require_reason=False)
def post_run_learning_cycle(action: ActionContext):
    engine_or_fail()
    try:
        from engine.paper_engine import paper_engine

        loop = getattr(paper_engine, "_learning_loop", None)
        if loop is None or not loop.is_running():
            raise ApiError(
                ErrorCode.CONFLICT,
                detail="Цикл обучения не запущен.",
            )
        loop.run_full_cycle()
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Learning cycle failed: %s", exc, exc_info=True)
        raise ApiError(ErrorCode.INTERNAL, detail="Не удалось запустить цикл обучения.")

    action.record(target="learning_loop", after={"queued": True})
    return envelope({"queued": True}, Meta(environment=arg_environment()))


# ── Backtest (operator tier, compute action) ──────────────────────────────────

@v2.post("/backtest/run")
@require_permission(Permission.RUN_BACKTEST)
@mutating(action="backtest.run", target_type="backtest", require_reason=False)
def post_run_backtest(action: ActionContext):
    from qf_platform.dto import BacktestRequestDTO, to_dict
    from qf_platform.services.backtest_service import BacktestService

    engine = engine_or_fail()
    body = request.get_json(silent=True) or {}

    def number(key: str, default: float, low: float, high: float) -> float:
        try:
            value = float(body.get(key, default))
        except (TypeError, ValueError):
            raise ApiError(ErrorCode.VALIDATION_FAILED, field_name=key)
        if not (low <= value <= high):
            raise ApiError(ErrorCode.VALIDATION_FAILED, field_name=key)
        return value

    ticker = str(body.get("ticker") or "SBER").strip().upper()
    if not ticker or len(ticker) > 24 or not ticker.replace(".", "").replace("-", "").isalnum():
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="ticker")

    dto = BacktestRequestDTO(
        strategy=str(body.get("strategy") or "rules_engine")[:64],
        exchange=str(body.get("exchange") or "moex")[:32],
        ticker=ticker,
        period_start=(body.get("period_start") or None),
        period_end=(body.get("period_end") or None),
        initial_capital=number("initial_capital", 1_000_000, 1_000, 1e12),
        risk_pct=number("risk_pct", 0.05, 0.0001, 1.0),
        commission_pct=number("commission_pct", 0.0003, 0.0, 0.1),
        slippage_pct=number("slippage_pct", 0.0001, 0.0, 0.1),
        leverage=number("leverage", 1.0, 1.0, 20.0),
    )

    try:
        result = BacktestService(engine).run(dto)
    except ValueError as exc:
        # Insufficient data is the operator's problem to fix, so the message is
        # theirs to see — it names the instrument, nothing internal.
        raise ApiError(ErrorCode.VALIDATION_FAILED, detail=str(exc)[:200])
    except Exception as exc:  # noqa: BLE001
        logger.error("Backtest failed: %s", exc, exc_info=True)
        raise ApiError(ErrorCode.INTERNAL, detail="Бэктест завершился ошибкой.")

    action.record(
        target=str(result.run_id),
        target_type="backtest_run",
        after={"ticker": result.ticker, "trades": result.total_trades},
    )
    _log(
        "INFO",
        f"Бэктест {result.ticker}: {result.total_trades} сделок",
        category=EventCategory.OPERATOR,
        run_id=result.run_id,
    )
    return envelope(
        to_dict(result),
        Meta(
            environment=Environment.BACKTEST,
            n=result.total_trades,
            currency="RUB",
            units=Units.MONEY,
        ),
    )


# ── Position close (trading tier) ─────────────────────────────────────────────

def _ticker_for_position(pos_id: int, **_: object) -> str:
    """Expected typed confirmation for a close: the position's own ticker."""
    engine = engine_or_fail()
    position = PositionsService(engine).position(int(pos_id))
    if position is None:
        raise ApiError(ErrorCode.NOT_FOUND)
    return position["ticker"]


@v2.post("/positions/<int:pos_id>/close")
@require_permission(Permission.CLOSE_POSITION)
@require_typed_confirmation(_ticker_for_position)
@mutating(
    action="position.close",
    target_type="paper_position",
    idempotent=True,
    require_reason=True,
)
def post_close_position(pos_id: int, action: ActionContext):
    """Close one position.

    The API existed (``QFApi.closePosition``) and was wired to no control at all.
    It now exists behind the full trading-tier gate: typed ticker confirmation, a
    stored reason, an idempotency key so a double click cannot double-fire, an
    explicit permission, and an audit row carrying before/after state.
    """
    engine = engine_or_fail()
    before = PositionsService(engine).position(pos_id)
    if before is None:
        raise ApiError(ErrorCode.NOT_FOUND)

    try:
        from engine.paper_engine import paper_engine

        paper_engine.set_db_engine(engine)
        result = paper_engine.close_trade(pos_id, reason=action.reason or "manual")
    except ValueError as exc:
        raise ApiError(ErrorCode.VALIDATION_FAILED, detail=str(exc)[:200])
    except Exception as exc:  # noqa: BLE001
        logger.error("Position close failed: %s", exc, exc_info=True)
        # State the outcome precisely: the operator needs to know whether the
        # position is closed, not just that something went wrong.
        raise ApiError(
            ErrorCode.INTERNAL,
            detail="Закрытие не подтверждено — проверьте позицию перед повтором.",
        )

    action.record(
        target=str(pos_id),
        before={
            "ticker": before["ticker"],
            "quantity": before["quantity"],
            "entry_price": before["entry_price"],
            "mark_price": before["mark_price"],
            "unrealized_pnl": before["unrealized_pnl"],
        },
        after={"pnl": result.get("pnl"), "exit_price": result.get("exit_price")},
    )
    _log(
        "WARN",
        f"Позиция {before['ticker']} закрыта оператором "
        f"{current_principal().username}: {action.reason}",
        category=EventCategory.TRADE,
        position_id=pos_id,
        pnl=result.get("pnl"),
    )
    return envelope(
        {
            "position_id": pos_id,
            "ticker": before["ticker"],
            "pnl": result.get("pnl"),
            "exit_price": result.get("exit_price"),
        },
        Meta(environment=arg_environment(), currency="RUB", units=Units.MONEY),
    )


@v2.post("/signals/<int:signal_id>/execute")
@require_permission(Permission.EXECUTE_SIGNAL)
@mutating(
    action="signal.execute",
    target_type="trading_signal",
    idempotent=True,
    require_reason=True,
)
def post_execute_signal(signal_id: int, action: ActionContext):
    from qf_platform.repositories.signals_gate_repository import (
        GateDecision,
        GateStage,
        SignalsGateRepository,
    )
    from qf_platform.services.signals_service import SignalsService

    engine = engine_or_fail()
    gate = SignalsGateRepository(engine)
    try:
        result = SignalsService(engine).execute_signal(signal_id)
    except ValueError as exc:
        gate.record_decision(
            signal_id, decision=GateDecision.ERRORED,
            stage=GateStage.BROKER, reason=str(exc)[:300],
        )
        raise ApiError(ErrorCode.VALIDATION_FAILED, detail=str(exc)[:200])
    except Exception as exc:  # noqa: BLE001
        logger.error("Signal execute failed: %s", exc, exc_info=True)
        # Record the refusal so «accepted but not filled» is a visible outcome
        # rather than a silent gap in the signal timeline.
        gate.record_decision(
            signal_id, decision=GateDecision.ACCEPTED_UNFILLED,
            stage=GateStage.BROKER, reason="Брокер не подтвердил исполнение.",
        )
        raise ApiError(ErrorCode.BROKER_UNAVAILABLE, detail="Исполнение не подтверждено.")

    gate.record_decision(
        signal_id, decision=GateDecision.FILLED, stage=GateStage.BROKER,
        reason=f"Исполнено оператором: {action.reason}",
    )
    action.record(target=str(signal_id), after=dict(result))
    return envelope(result, Meta(environment=arg_environment(), units=Units.MONEY))


# ── Credentials (administrator tier) ─────────────────────────────────────────

#: Only these may be written from the web dashboard. The set is explicit so a new
#: environment variable does not become remotely writable by accident.
_WRITABLE_CREDENTIALS = {
    "TINKOFF_TOKEN": "Токен Т-Инвестиции",
    "TINKOFF_ACCOUNT_ID": "Идентификатор счёта Т-Инвестиции",
    "BYBIT_API_KEY": "Ключ Bybit",
    "BYBIT_API_SECRET": "Секрет Bybit",
}


@v2.get("/settings/credentials")
@require_permission(Permission.MANAGE_CREDENTIALS)
def get_credentials():
    """Configured / not configured, and a length. Never the value.

    No masked prefix either: even four leading characters of a broker token is a
    material disclosure on a screen that may be shared or screenshotted.
    """
    from config import config

    values = {
        "TINKOFF_TOKEN": config.tinkoff.token,
        "TINKOFF_ACCOUNT_ID": config.tinkoff.account_id,
        "BYBIT_API_KEY": config.bybit.api_key,
        "BYBIT_API_SECRET": config.bybit.api_secret,
    }
    return envelope(
        {
            "credentials": [
                {
                    "key": key,
                    "label": label,
                    "configured": bool(values.get(key)),
                    "length": len(values.get(key) or ""),
                }
                for key, label in _WRITABLE_CREDENTIALS.items()
            ],
            "storage": "environment / encrypted vault",
        },
        Meta(environment=arg_environment(), units=Units.ENUM),
    )


@v2.post("/settings/credentials")
@require_permission(Permission.MANAGE_CREDENTIALS)
@mutating(action="credential.write", target_type="credential", require_reason=True)
def post_credentials(action: ActionContext):
    from security.credential_store import persist_credential

    body = request.get_json(silent=True) or {}
    key = str(body.get("key") or "").strip()
    value = body.get("value")

    if key not in _WRITABLE_CREDENTIALS:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="key")
    if not isinstance(value, str) or not value.strip():
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            detail="Пустое значение — используйте отдельное действие очистки.",
            field_name="value",
        )

    from config import config

    persist_credential(
        key, value.strip(), config,
        actor_type="dashboard_user",
        actor_id=current_principal().username,
        client_ip=client_ip(),
    )
    # The value never enters the audit row; `_redact` in guards.py would catch it
    # anyway, but not passing it is the stronger guarantee.
    action.record(target=key, before={"configured": True}, after={"configured": True})
    _log(
        "WARN",
        f"Учётные данные {key} обновлены администратором {current_principal().username}",
        category=EventCategory.AUTH,
    )
    return envelope({"key": key, "configured": True}, Meta(environment=arg_environment()))


@v2.post("/settings/credentials/<key>/clear")
@require_permission(Permission.MANAGE_CREDENTIALS)
@require_typed_confirmation(lambda key, **_: str(key))
@mutating(action="credential.clear", target_type="credential", require_reason=True)
def post_clear_credential(key: str, action: ActionContext):
    """Clearing a credential requires typing its name.

    The old UI had four «Clear» buttons that wrote an empty value straight to
    ``.env`` on a single click, with no confirmation and no audit row.
    """
    from config import config
    from security.credential_store import persist_credential

    if key not in _WRITABLE_CREDENTIALS:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="key")

    persist_credential(
        key, "", config,
        actor_type="dashboard_user",
        actor_id=current_principal().username,
        client_ip=client_ip(),
    )
    action.record(target=key, before={"configured": True}, after={"configured": False})
    _log(
        "WARN",
        f"Учётные данные {key} очищены администратором {current_principal().username}: "
        f"{action.reason}",
        category=EventCategory.AUTH,
    )
    return envelope({"key": key, "configured": False}, Meta(environment=arg_environment()))


# ── Maintenance (administrator tier) ─────────────────────────────────────────

@v2.post("/maintenance/prune-equity")
@require_permission(Permission.MANAGE_LIMITS)
@mutating(action="maintenance.prune_equity", target_type="equity_snapshots", require_reason=True)
def post_prune_equity(action: ActionContext):
    """Apply the retention policy to ``equity_snapshots``.

    16 123 rows holding 44 distinct values accumulated because four GET handlers
    inserted one each on a 12-second poll. The writes are gone; this reclaims what
    they left behind, and it is an explicit operator action rather than something
    that fires on page view.
    """
    from qf_platform.repositories.equity_repository import EquityRepository

    engine = engine_or_fail()
    body = request.get_json(silent=True) or {}
    try:
        days = int(body.get("keep_days", 365))
        keep_full = int(body.get("full_resolution_days", 7))
    except (TypeError, ValueError):
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="keep_days")
    if not (7 <= days <= 3650) or not (1 <= keep_full <= days):
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="keep_days")

    removed = EquityRepository(engine).prune_older_than(
        days, keep_daily_after_days=keep_full
    )
    action.record(
        target="equity_snapshots",
        after={"removed": removed, "keep_days": days, "full_resolution_days": keep_full},
    )
    _log(
        "INFO", f"Retention: удалено {removed} снапшотов equity",
        category=EventCategory.OPERATOR,
    )
    return envelope(
        {"removed": removed}, Meta(environment=arg_environment(), units=Units.COUNT)
    )
