"""Route guards: authentication, permission, CSRF, read-only, idempotency, audit.

One decorator per concern, composed on the route. Making each concern a decorator
rather than a convention inside the handler is what stops the old pattern where a
mutating endpoint simply forgot to check anything — ten of twelve did.

Usage::

    @bp.post("/positions/<int:pos_id>/close")
    @require_permission(Permission.CLOSE_POSITION)
    @mutating(action="position.close", idempotent=True, require_reason=True)
    def close_position(pos_id: int, action: ActionContext):
        ...
        action.record(target=str(pos_id), before={...}, after={...})
        return envelope(...)

``@mutating`` blocks in read-only mode, validates CSRF, resolves the idempotency
key, and writes exactly one audit row per attempt — success or failure.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from flask import g, jsonify, request

from qf_platform.contracts import ApiError, ErrorCode
from qf_platform.environment import Environment
from security.audit import audit_record
from security.csrf import validate_csrf
from security.permissions import Permission, Principal
from security.readonly import read_only_enabled
from security.session_auth import client_ip, current_principal

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "X-Idempotency-Key"
MAX_REASON_LENGTH = 500

#: Set by the app factory. Idempotency needs storage; without it, idempotent
#: actions are refused rather than silently executed twice.
_auth_repo = None


def set_auth_repository(repo) -> None:
    global _auth_repo
    _auth_repo = repo


def require_auth(view: Callable) -> Callable:
    """Authenticated routes are the default; a public route must opt out."""

    @functools.wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        if current_principal() is None:
            raise ApiError(ErrorCode.UNAUTHENTICATED)
        return view(*args, **kwargs)

    wrapper.__qf_requires_auth__ = True  # type: ignore[attr-defined]
    return wrapper


def require_permission(permission: Permission) -> Callable:
    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            principal = current_principal()
            if principal is None:
                raise ApiError(ErrorCode.UNAUTHENTICATED)
            if not principal.can(permission):
                # The reason travels to the client: a disabled control that
                # cannot say why is unactionable.
                raise ApiError(
                    ErrorCode.FORBIDDEN,
                    detail=principal.denial_reason(permission),
                )
            return view(*args, **kwargs)

        wrapper.__qf_permission__ = permission  # type: ignore[attr-defined]
        return wrapper

    return decorator


@dataclass
class ActionContext:
    """Everything an audited mutation needs, and the audit row it will write."""

    action: str
    principal: Optional[Principal]
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    environment: Environment = Environment.SANDBOX
    target: Optional[str] = None
    target_type: Optional[str] = None
    before: Optional[dict] = None
    after: Optional[dict] = None
    extra: dict = field(default_factory=dict)
    _recorded: bool = False

    def record(
        self,
        *,
        target: Optional[str] = None,
        target_type: Optional[str] = None,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        **extra: Any,
    ) -> None:
        """Attach the before/after state. The row is written by the decorator on
        the way out, so an exception still produces an audit entry."""
        if target is not None:
            self.target = target
        if target_type is not None:
            self.target_type = target_type
        if before is not None:
            self.before = before
        if after is not None:
            self.after = after
        self.extra.update(extra)
        self._recorded = True

    def replayed(self, response: dict) -> None:
        self.extra["idempotent_replay"] = True
        self.after = {"replayed": True}


def _redact(payload: Optional[dict]) -> Optional[dict]:
    """Never let a secret into the audit log.

    Keys are matched by substring, so ``TINKOFF_TOKEN``, ``api_key`` and
    ``password_hash`` are all caught without an exhaustive list.
    """
    if not payload:
        return payload
    sensitive = ("token", "secret", "password", "api_key", "apikey", "credential", "hash")
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in sensitive):
            out[key] = "«скрыто»"
        elif isinstance(value, dict):
            out[key] = _redact(value)
        else:
            out[key] = value
    return out


def _request_digest() -> str:
    """Fingerprint of the request body, so a replayed idempotency key with a
    *different* payload is a conflict rather than a silent no-op."""
    try:
        body = request.get_data(cache=True) or b""
    except Exception:  # noqa: BLE001
        body = b""
    return hashlib.sha256(request.path.encode() + b"|" + body).hexdigest()


def _extract_reason(required: bool) -> Optional[str]:
    body = request.get_json(silent=True) or {}
    reason = body.get("reason") if isinstance(body, dict) else None
    if reason is not None:
        reason = str(reason).strip()[:MAX_REASON_LENGTH]
    if required and not reason:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            detail="Укажите причину действия.",
            field_name="reason",
        )
    return reason or None


def _extract_typed_confirmation(expected: str) -> None:
    """Typed confirmation for a trading action.

    The operator types the ticker (or the word ``LIVE``). A checkbox or a second
    click is not enough for something that moves money, and a mistyped value must
    fail loudly rather than proceed.
    """
    body = request.get_json(silent=True) or {}
    provided = str((body or {}).get("confirm") or "").strip()
    if provided.upper() != expected.upper():
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            detail=f"Для подтверждения введите «{expected}».",
            field_name="confirm",
        )


def mutating(
    *,
    action: str,
    target_type: str = "endpoint",
    idempotent: bool = False,
    require_reason: bool = False,
    audit: bool = True,
) -> Callable:
    """Wrap a state-changing endpoint.

    Order of checks is deliberate: read-only first (cheapest, and the most
    absolute), then CSRF, then reason, then idempotency. An action refused by the
    read-only guard must not consume an idempotency key.
    """

    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            if read_only_enabled():
                raise ApiError(ErrorCode.READ_ONLY_MODE)

            validate_csrf(request)

            principal = current_principal()
            if principal is None:
                raise ApiError(ErrorCode.UNAUTHENTICATED)

            reason = _extract_reason(require_reason)
            key = (request.headers.get(IDEMPOTENCY_HEADER) or "").strip() or None

            ctx = ActionContext(
                action=action,
                principal=principal,
                reason=reason,
                idempotency_key=key,
                target_type=target_type,
                environment=getattr(g, "qf_environment", Environment.SANDBOX),
            )

            claimed = False
            if idempotent:
                if not key:
                    raise ApiError(
                        ErrorCode.VALIDATION_FAILED,
                        detail="Требуется заголовок X-Idempotency-Key.",
                        field_name=IDEMPOTENCY_HEADER,
                    )
                if _auth_repo is None:
                    raise ApiError(ErrorCode.DB_UNAVAILABLE)

                digest = _request_digest()
                existing = _auth_repo.find_idempotent(key)
                if existing is not None:
                    if existing.get("request_digest") != digest:
                        raise ApiError(
                            ErrorCode.CONFLICT,
                            detail="Этот ключ идемпотентности уже использован с другими параметрами.",
                        )
                    if existing.get("status_code") is None:
                        # Reservation exists but no result yet: a concurrent
                        # request is mid-flight. Refusing is correct — replaying
                        # nothing is safer than executing twice.
                        raise ApiError(
                            ErrorCode.CONFLICT,
                            detail="Действие уже выполняется. Дождитесь результата.",
                        )
                    ctx.replayed(existing.get("response_json") or {})
                    _write_audit(ctx, outcome="replayed")
                    response = jsonify(existing.get("response_json") or {})
                    response.status_code = int(existing.get("status_code") or 200)
                    response.headers["X-Idempotent-Replay"] = "1"
                    return response

                claimed = _auth_repo.claim_idempotency_key(
                    key=key,
                    action=action,
                    actor_id=principal.username,
                    request_digest=digest,
                )
                if not claimed:
                    raise ApiError(
                        ErrorCode.CONFLICT,
                        detail="Действие уже выполняется. Дождитесь результата.",
                    )

            g.qf_action = ctx
            try:
                result = view(*args, action=ctx, **kwargs)
            except ApiError as exc:
                if claimed and key:
                    _auth_repo.release_idempotency_key(key)
                if audit:
                    _write_audit(ctx, outcome="failure", error_code=exc.code)
                raise
            except Exception:
                if claimed and key:
                    _auth_repo.release_idempotency_key(key)
                if audit:
                    _write_audit(ctx, outcome="failure", error_code=ErrorCode.INTERNAL)
                raise

            status = 200
            payload: Any = result
            if isinstance(result, tuple):
                payload, status = result[0], result[1]

            if claimed and key and _auth_repo is not None:
                try:
                    stored = payload if isinstance(payload, dict) else {}
                    _auth_repo.complete_idempotency_key(
                        key=key, response=stored, status_code=int(status)
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("Не удалось сохранить результат идемпотентности", exc_info=True)

            if audit:
                _write_audit(ctx, outcome="success")
            return result

        wrapper.__qf_mutating__ = action  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _write_audit(ctx: ActionContext, *, outcome: str, error_code: Optional[str] = None) -> None:
    principal = ctx.principal
    metadata = dict(ctx.extra)
    if error_code:
        metadata["error_code"] = error_code
    metadata.setdefault("method", request.method)
    metadata.setdefault("path", request.path)

    try:
        audit_record(
            event_type=ctx.action,
            actor_type="dashboard_user",
            actor_id=principal.username if principal else None,
            actor_role=principal.role.value if principal else None,
            resource_type=ctx.target_type,
            resource_id=ctx.target,
            outcome=outcome,
            client_ip=client_ip(),
            environment=ctx.environment.value if ctx.environment else None,
            reason=ctx.reason,
            state_before=_redact(ctx.before),
            state_after=_redact(ctx.after),
            idempotency_key=ctx.idempotency_key,
            metadata=_redact(metadata),
        )
    except Exception:  # noqa: BLE001 — the action already happened; do not undo it
        logger.error("Не удалось записать audit-событие %s", ctx.action, exc_info=True)


def require_typed_confirmation(expected_from: Callable[..., str]) -> Callable:
    """Typed confirmation whose expected value depends on the route arguments.

    ``expected_from`` receives the view's kwargs and returns what the operator
    must type — usually the ticker of the position being closed.
    """

    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            expected = expected_from(**{k: v for k, v in kwargs.items() if k != "action"})
            _extract_typed_confirmation(expected)
            return view(*args, **kwargs)

        return wrapper

    return decorator
