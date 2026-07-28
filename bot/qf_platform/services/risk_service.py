"""Risk and exposure — with limits that are either configured or absent.

The rule this service exists to enforce: **an unconfigured limit renders as
«не настроено», never as 0**. A daily loss limit of zero reads as "you may not
lose anything", which is both wrong and the opposite of the truth.

Only two limits genuinely exist in configuration (``max_open_positions`` and
``max_daily_loss_pct``, plus position sizing). Everything else the audit's
wireframe asks for is reported as unconfigured rather than invented.
"""

from __future__ import annotations

import logging
from typing import Optional

from config import config
from qf_platform.contracts import Units, safe_float
from qf_platform.environment import Environment
from qf_platform.repositories.trades_repository import TradesRepository
from qf_platform.services.equity_service import EquityService
from qf_platform.services.positions_service import PositionsService

logger = logging.getLogger(__name__)


def _limit(value: Optional[float], *, units: str, source: str) -> dict:
    """A limit is a value plus whether it was actually configured."""
    configured = value is not None and value > 0
    return {
        "value": value if configured else None,
        "configured": configured,
        "units": units,
        "source": source,
    }


class RiskService:
    def __init__(self, engine):
        self._trades = TradesRepository(engine)
        self._positions = PositionsService(engine)
        self._equity = EquityService(engine)

    def status(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        environment: Environment = Environment.SANDBOX,
        window: str = "90d",
    ) -> dict:
        env = Environment.coerce(environment)
        aid = account_id or self._trades.default_account_id(mode=mode)
        account = self._trades.account(aid) if aid else None
        currency = (account or {}).get("currency") or "RUB"
        equity = safe_float((account or {}).get("balance"))

        positions = self._positions.open_positions(
            account_id=aid, mode=mode, environment=env
        )
        drawdown = self._equity.drawdown(
            account_id=aid, mode=mode, window=window, environment=env
        )
        pnl_row = self._trades.paper_pnl_periods(aid) if aid else {}
        daily_pnl = safe_float(pnl_row.get("pnl_day"))
        daily_n = int(pnl_row.get("n_day") or 0)

        max_positions = config.risk.max_open_positions
        max_daily_loss_pct = config.risk.max_daily_loss_pct

        # The configured limit is a percentage; the money figure derived from it is
        # marked as derived so nobody reads it as an independently configured value.
        daily_loss_limit_abs = None
        if equity and max_daily_loss_pct:
            daily_loss_limit_abs = -abs(equity * max_daily_loss_pct)

        totals = positions["totals"]
        breaches: list[dict] = []

        if max_positions and positions["count"] >= max_positions:
            breaches.append({
                "code": "MAX_OPEN_POSITIONS",
                "label": "Достигнут лимит открытых позиций",
                "detail": f"{positions['count']} из {max_positions}",
                "severity": "warning" if positions["count"] == max_positions else "critical",
            })
        if daily_loss_limit_abs is not None and daily_pnl is not None and daily_pnl <= daily_loss_limit_abs:
            breaches.append({
                "code": "DAILY_LOSS_LIMIT",
                "label": "Превышен дневной лимит убытка",
                "detail": f"{daily_pnl:.2f} при лимите {daily_loss_limit_abs:.2f}",
                "severity": "critical",
            })
        if positions.get("stale_quote_count"):
            breaches.append({
                "code": "STALE_MARKS",
                "label": "Устаревшие котировки в открытых позициях",
                "detail": f"{positions['stale_quote_count']} из {positions['count']}",
                "severity": "critical",
            })
        concentration = totals.get("largest_position_pct")
        if concentration is not None and concentration > 50:
            breaches.append({
                "code": "CONCENTRATION",
                "label": "Высокая концентрация",
                "detail": f"крупнейшая позиция — {concentration:.1f} % экспозиции",
                "severity": "warning",
            })

        return {
            "environment": env.value,
            "currency": currency,
            "equity": equity,
            "exposure": {
                "abs": totals.get("exposure_abs"),
                "pct": totals.get("exposure_pct"),
            },
            "capital_at_risk": {
                "abs": totals.get("capital_at_risk_abs"),
                "pct": totals.get("capital_at_risk_pct"),
                # Positions with no stop contribute nothing to capital-at-risk, so
                # the figure would silently understate risk without this count.
                "positions_without_stop": sum(
                    1 for p in positions["positions"] if not p.get("stop_loss")
                ),
            },
            "positions": {
                "open": positions["count"],
                "limit": max_positions or None,
                "limit_configured": bool(max_positions),
                "stale_marks": positions.get("stale_quote_count", 0),
            },
            "drawdown": {
                "max_pct": drawdown["max_drawdown_pct"],
                "max_abs": drawdown["max_drawdown_abs"],
                "current_pct": drawdown["current_drawdown_pct"],
                "current_abs": drawdown["current_drawdown_abs"],
                "n": drawdown["n"],
                "window": drawdown["window"],
                "window_label": drawdown["window_label"],
            },
            "daily": {
                "pnl": None if daily_n == 0 else daily_pnl,
                "n": daily_n,
                "limit_pct": _limit(
                    max_daily_loss_pct * 100 if max_daily_loss_pct else None,
                    units=Units.PERCENT, source="config.risk.max_daily_loss_pct",
                ),
                "limit_abs_derived": daily_loss_limit_abs,
                "limit_abs_is_derived": True,
            },
            "concentration_pct": concentration,
            "sizing": {
                "max_position_pct": _limit(
                    config.risk.max_position_pct * 100 if config.risk.max_position_pct else None,
                    units=Units.PERCENT, source="config.risk.max_position_pct",
                ),
                "atr_stop_multiplier": _limit(
                    config.risk.atr_stop_multiplier,
                    units=Units.RATIO, source="config.risk.atr_stop_multiplier",
                ),
            },
            "breaches": breaches,
            "units": {
                "equity": Units.MONEY,
                "exposure.abs": Units.MONEY,
                "exposure.pct": Units.PERCENT,
                "drawdown.max_pct": Units.PERCENT,
                "drawdown.max_abs": Units.MONEY,
                "daily.pnl": Units.MONEY,
            },
        }

    def risk_events(self, *, limit: int = 50) -> list[dict]:
        """Historical risk events, from the gate's own record.

        Sourced from ``skipped_signals`` where the risk stage rejected a trade —
        that is what a "risk event" actually is in this system. Nothing is
        synthesised.
        """
        from qf_platform.repositories.signals_gate_repository import (
            GateStage,
            SignalsGateRepository,
        )

        rows = SignalsGateRepository(self._trades._engine).skipped(limit=limit)
        return [
            {
                "occurred_at": row["skipped_at"],
                "ticker": row.get("ticker"),
                "strategy_id": row.get("strategy_id"),
                "code": row.get("skip_reason"),
                "stage": row.get("gate_stage"),
                "reason": row.get("reason_text") or row.get("skip_reason"),
                "environment": row.get("environment"),
            }
            for row in rows
            if row.get("gate_stage") in (GateStage.RISK, GateStage.DUPLICATE)
        ]
