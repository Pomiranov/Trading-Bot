"""Roles and permissions for the operational dashboard.

Three roles plus one orthogonal capability:

* ``observer``      — reads everything, changes nothing.
* ``operator``      — pause/resume the engine, reconnect a broker, acknowledge
                      a fault, run a backtest.
* ``administrator`` — everything an operator can do, plus credentials, limits
                      and strategy state.
* ``trading_authorized`` — a separate boolean, not a role. Executing a signal or
  closing a position requires it *in addition to* a sufficient role, so an
  administrator who manages configuration is not automatically able to move money.

Until the operator action set is fully built out, ``TRADING`` permissions are
additionally gated by ``QF_DASHBOARD_ALLOW_TRADING_ACTIONS``, which defaults to
off. A trading control that exists but has no audit trail and no idempotency is
worse than no control at all, so the default is the safe one.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Iterable, Optional


class Role(str, Enum):
    OBSERVER = "observer"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"

    @classmethod
    def coerce(cls, value) -> "Role":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower()
        for member in cls:
            if member.value == text:
                return member
        # An unrecognised role degrades to the least privilege, never the most.
        return cls.OBSERVER

    @property
    def rank(self) -> int:
        return {Role.OBSERVER: 0, Role.OPERATOR: 1, Role.ADMINISTRATOR: 2}[self]


ROLE_LABELS = {
    Role.OBSERVER: "Наблюдатель",
    Role.OPERATOR: "Оператор",
    Role.ADMINISTRATOR: "Администратор",
}


class Permission(str, Enum):
    # Read
    VIEW = "view"
    VIEW_AUDIT = "view_audit"
    # Operator
    ENGINE_CONTROL = "engine_control"
    BROKER_RECONNECT = "broker_reconnect"
    ACKNOWLEDGE_FAULT = "acknowledge_fault"
    RUN_BACKTEST = "run_backtest"
    RUN_LEARNING_CYCLE = "run_learning_cycle"
    # Administrator
    MANAGE_CREDENTIALS = "manage_credentials"
    MANAGE_LIMITS = "manage_limits"
    MANAGE_STRATEGIES = "manage_strategies"
    MANAGE_USERS = "manage_users"
    # Trading — requires `trading_authorized` on top of the role
    EXECUTE_SIGNAL = "execute_signal"
    CLOSE_POSITION = "close_position"
    OPEN_POSITION = "open_position"
    SWITCH_TO_LIVE = "switch_to_live"


#: Minimum role per permission.
_MIN_ROLE: dict[Permission, Role] = {
    Permission.VIEW: Role.OBSERVER,
    Permission.VIEW_AUDIT: Role.ADMINISTRATOR,
    Permission.ENGINE_CONTROL: Role.OPERATOR,
    Permission.BROKER_RECONNECT: Role.OPERATOR,
    Permission.ACKNOWLEDGE_FAULT: Role.OPERATOR,
    Permission.RUN_BACKTEST: Role.OPERATOR,
    Permission.RUN_LEARNING_CYCLE: Role.OPERATOR,
    Permission.MANAGE_CREDENTIALS: Role.ADMINISTRATOR,
    Permission.MANAGE_LIMITS: Role.ADMINISTRATOR,
    Permission.MANAGE_STRATEGIES: Role.ADMINISTRATOR,
    Permission.MANAGE_USERS: Role.ADMINISTRATOR,
    Permission.EXECUTE_SIGNAL: Role.OPERATOR,
    Permission.CLOSE_POSITION: Role.OPERATOR,
    Permission.OPEN_POSITION: Role.OPERATOR,
    Permission.SWITCH_TO_LIVE: Role.ADMINISTRATOR,
}

#: Permissions that additionally require the trading capability.
TRADING_PERMISSIONS = frozenset({
    Permission.EXECUTE_SIGNAL,
    Permission.CLOSE_POSITION,
    Permission.OPEN_POSITION,
    Permission.SWITCH_TO_LIVE,
})

#: Human names, used in the "permission denied" state so the UI can say *which*
#: permission is missing and who grants it, rather than just refusing.
PERMISSION_LABELS = {
    Permission.VIEW: "просмотр",
    Permission.VIEW_AUDIT: "просмотр журнала аудита",
    Permission.ENGINE_CONTROL: "управление движком",
    Permission.BROKER_RECONNECT: "переподключение брокера",
    Permission.ACKNOWLEDGE_FAULT: "подтверждение инцидента",
    Permission.RUN_BACKTEST: "запуск бэктеста",
    Permission.RUN_LEARNING_CYCLE: "запуск цикла обучения",
    Permission.MANAGE_CREDENTIALS: "управление учётными данными",
    Permission.MANAGE_LIMITS: "изменение лимитов",
    Permission.MANAGE_STRATEGIES: "управление стратегиями",
    Permission.MANAGE_USERS: "управление пользователями",
    Permission.EXECUTE_SIGNAL: "исполнение сигнала",
    Permission.CLOSE_POSITION: "закрытие позиции",
    Permission.OPEN_POSITION: "открытие позиции",
    Permission.SWITCH_TO_LIVE: "переключение в live-режим",
}


def trading_actions_enabled() -> bool:
    """Master switch for the trading tier. Off unless explicitly enabled."""
    return os.getenv("QF_DASHBOARD_ALLOW_TRADING_ACTIONS", "0") == "1"


def live_mode_enabled() -> bool:
    """Live trading from the web dashboard. Separately off by default."""
    return os.getenv("QF_DASHBOARD_ALLOW_LIVE", "0") == "1"


class Principal:
    """The authenticated actor. Immutable for the life of a request."""

    __slots__ = ("user_id", "username", "role", "trading_authorized", "display_name", "session_id")

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        role: Role,
        trading_authorized: bool,
        display_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.user_id = user_id
        self.username = username
        self.role = Role.coerce(role)
        self.trading_authorized = bool(trading_authorized)
        self.display_name = display_name or username
        self.session_id = session_id

    def can(self, permission: Permission) -> bool:
        required = _MIN_ROLE.get(permission)
        if required is None:
            return False
        if self.role.rank < required.rank:
            return False
        if permission in TRADING_PERMISSIONS:
            if not trading_actions_enabled():
                return False
            if not self.trading_authorized:
                return False
            if permission is Permission.SWITCH_TO_LIVE and not live_mode_enabled():
                return False
        return True

    def denial_reason(self, permission: Permission) -> str:
        """Why the action is unavailable — shown in the disabled control's
        explanation, because «недоступно» without a reason is unactionable."""
        label = PERMISSION_LABELS.get(permission, permission.value)
        required = _MIN_ROLE.get(permission, Role.ADMINISTRATOR)
        if permission in TRADING_PERMISSIONS and not trading_actions_enabled():
            return (
                f"Торговые действия отключены в этой сборке "
                f"(QF_DASHBOARD_ALLOW_TRADING_ACTIONS=0). Требуется: {label}."
            )
        if permission is Permission.SWITCH_TO_LIVE and not live_mode_enabled():
            return "Переключение в live-режим отключено (QF_DASHBOARD_ALLOW_LIVE=0)."
        if self.role.rank < required.rank:
            return (
                f"Требуется роль «{ROLE_LABELS[required]}» для действия «{label}». "
                f"Ваша роль — «{ROLE_LABELS[self.role]}». Права выдаёт администратор."
            )
        if permission in TRADING_PERMISSIONS and not self.trading_authorized:
            return (
                f"Для действия «{label}» нужно отдельное разрешение trading_authorized. "
                "Его выдаёт администратор."
            )
        return f"Действие «{label}» недоступно."

    def permissions(self) -> list[str]:
        return [p.value for p in Permission if self.can(p)]

    def to_public_dict(self) -> dict:
        """What the client is told about itself. No hash, no session id, no secret."""
        return {
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role.value,
            "role_label": ROLE_LABELS[self.role],
            "trading_authorized": self.trading_authorized,
            "permissions": self.permissions(),
        }

    @classmethod
    def from_session_row(cls, row: dict) -> "Principal":
        return cls(
            user_id=int(row["user_id"]),
            username=row["username"],
            role=Role.coerce(row.get("role")),
            trading_authorized=bool(row.get("trading_authorized")),
            display_name=row.get("display_name"),
            session_id=row.get("sid"),
        )


def any_of(principal: Optional[Principal], permissions: Iterable[Permission]) -> bool:
    return bool(principal) and any(principal.can(p) for p in permissions)
