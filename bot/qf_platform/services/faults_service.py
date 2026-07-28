"""The fault region — "do I need to act right now?"

Zero rows when healthy, and the region collapses to zero height. There is
deliberately no green "all clear" band: a permanent reassurance becomes invisible
within a day and takes the operator's attention budget with it.

Each fault carries the five things that make it actionable: state, subject,
human reason, age, and one recommended action with a link. Faults are ordered by
severity, and never more than five are returned — the sixth becomes «+N ещё».
"""

from __future__ import annotations

import logging
from typing import Optional

from qf_platform.contracts import age_seconds, to_display
from qf_platform.environment import Environment
from qf_platform.services.health_service import (
    STATE_PRESENTATION,
    HealthState,
    health_service,
)

logger = logging.getLogger(__name__)

MAX_VISIBLE_FAULTS = 5


class FaultsService:
    def __init__(self, engine):
        self._engine = engine

    def faults(
        self,
        *,
        environment_snapshot=None,
        risk_status: Optional[dict] = None,
        schema_report=None,
    ) -> dict:
        items: list[dict] = []

        # ── Schema drift. First, because everything else is unreliable under it.
        if schema_report is not None and not getattr(schema_report, "current", True):
            items.append({
                "code": "SCHEMA_OUT_OF_DATE",
                "state": HealthState.FAILED,
                "subject": "Схема базы данных",
                "reason": getattr(schema_report, "describe", lambda: "устарела")(),
                "action": {"label": "Как исправить", "route": "/health", "hint": "python -m qf_platform.migrate"},
                "occurred_at": None,
                "severity": 3,
            })

        # ── Environment. An undetermined environment is a fault in its own right.
        env = environment_snapshot
        if env is not None:
            if env.environment is Environment.UNKNOWN:
                items.append({
                    "code": "ENVIRONMENT_UNKNOWN",
                    "state": HealthState.FAILED,
                    "subject": "Среда исполнения",
                    "reason": "; ".join(env.conflicts) if env.conflicts
                              else "Не удалось определить, песочница это или live.",
                    "action": {"label": "Открыть настройки", "route": "/settings"},
                    "occurred_at": None,
                    "severity": 3,
                })
            if env.unknown_environment_rows:
                items.append({
                    "code": "UNLABELLED_ROWS",
                    "state": HealthState.DEGRADED,
                    "subject": "Сделки без среды",
                    "reason": f"{env.unknown_environment_rows} строк в trades без метки среды.",
                    "action": {"label": "Открыть сделки", "route": "/trades"},
                    "occurred_at": None,
                    "severity": 2,
                })
            if env.market_is_stale:
                age = env.market_age_seconds or 0
                items.append({
                    "code": "MARKET_DATA_STALE",
                    "state": HealthState.STALE,
                    "subject": "Рыночные данные",
                    "reason": _humanise_age(age) + " — все цены и PnL производные от этих свечей.",
                    "action": {"label": "Проверить загрузчик", "route": "/health"},
                    "occurred_at": to_display(env.market_as_of),
                    "severity": 3,
                })
            elif env.market_is_stale is None:
                items.append({
                    "code": "MARKET_DATA_UNKNOWN",
                    "state": HealthState.UNKNOWN,
                    "subject": "Рыночные данные",
                    "reason": "Возраст последней свечи не определён.",
                    "action": {"label": "Проверить загрузчик", "route": "/health"},
                    "occurred_at": None,
                    "severity": 2,
                })

        # ── Service health. Anything not healthy and not merely paused.
        svc = health_service()
        if svc is not None:
            for service in svc.snapshot():
                state = service["state"]
                if state in (HealthState.HEALTHY,):
                    continue
                # A paused engine is an operator decision, not a fault — unless
                # nobody knows why it is paused.
                if state == HealthState.PAUSED and service["key"] == "engine":
                    continue
                if service["severity"] < 2:
                    continue
                items.append({
                    "code": f"SERVICE_{service['key'].upper()}",
                    "state": state,
                    "subject": service["name"],
                    "reason": service.get("reason") or STATE_PRESENTATION[state]["label"],
                    "action": {
                        "label": service.get("action") or "Открыть здоровье системы",
                        "route": "/health",
                    },
                    "occurred_at": service.get("checked_at"),
                    "severity": service["severity"],
                })

            collector_age = svc.collector_age_seconds()
            if collector_age is None or collector_age > 300:
                items.append({
                    "code": "HEALTH_COLLECTOR_STALE",
                    "state": HealthState.UNKNOWN,
                    "subject": "Сбор метрик здоровья",
                    "reason": "Проверки не выполнялись" + (
                        "" if collector_age is None else f" {_humanise_age(collector_age)}"
                    ),
                    "action": {"label": "Открыть здоровье системы", "route": "/health"},
                    "occurred_at": None,
                    "severity": 2,
                })

        # ── Risk breaches.
        for breach in (risk_status or {}).get("breaches", []):
            items.append({
                "code": breach["code"],
                "state": HealthState.FAILED if breach.get("severity") == "critical"
                         else HealthState.DEGRADED,
                "subject": breach["label"],
                "reason": breach.get("detail") or "",
                "action": {"label": "Открыть риск", "route": "/risk"},
                "occurred_at": None,
                "severity": 3 if breach.get("severity") == "critical" else 2,
            })

        items.sort(key=lambda item: (-item["severity"], item["subject"]))
        for item in items:
            presentation = STATE_PRESENTATION.get(
                item["state"], STATE_PRESENTATION[HealthState.UNKNOWN]
            )
            item["label"] = presentation["label"]
            item["shape"] = presentation["shape"]
            if item.get("occurred_at") is None:
                item["age_seconds"] = None

        visible = items[:MAX_VISIBLE_FAULTS]
        return {
            "faults": visible,
            "total": len(items),
            "hidden": max(0, len(items) - len(visible)),
            "worst_severity": items[0]["severity"] if items else 0,
        }


def _humanise_age(seconds: int) -> str:
    """Server-side age text for a fault reason.

    The client owns formatting in general; a fault's reason is a sentence, and
    assembling half a sentence on each side is how «Устарело · 14» happens.
    """
    if seconds < 60:
        return f"{seconds} с назад"
    if seconds < 3600:
        return f"{seconds // 60} мин назад"
    if seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} ч {minutes} мин назад" if minutes else f"{hours} ч назад"
    return f"{seconds // 86400} дн назад"
