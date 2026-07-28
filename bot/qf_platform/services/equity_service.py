"""Equity curve and drawdown — from real snapshots, on a real time axis.

Replaces two defects at once:

* ``/api/equity`` fell through to a candle-derived path when there were no closed
  ``trades``, normalising SBER's share price to a starting balance and serving it
  as portfolio equity. There is no fallback here: no snapshots means "no history".
* ``max_drawdown`` carried a fraction under a name the UI rendered as a
  percentage, so a −23,73 % drawdown displayed as «−0,2 %». Percent and absolute
  are separate fields with declared units.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from qf_platform.contracts import (
    EmptyReason,
    Freshness,
    Units,
    drawdown_from_equity,
    safe_float,
    sharpe_from_returns,
    sortino_from_returns,
    to_display,
)
from qf_platform.environment import Environment
from qf_platform.repositories.equity_repository import WINDOW_BUCKETS, EquityRepository
from qf_platform.repositories.trades_repository import TradesRepository

logger = logging.getLogger(__name__)

WINDOW_LABELS = {
    "1d": "сутки",
    "7d": "7 дней",
    "30d": "30 дней",
    "90d": "90 дней",
    "1y": "год",
    "all": "вся история",
}

#: Equity older than five minutes is stale for a capital panel: it means the
#: engine stopped writing snapshots, which is itself the signal.
EQUITY_STALE_AFTER_SECONDS = 300


@dataclass
class EquitySeries:
    points: list[dict]
    window: str
    window_label: str
    observations: int
    distinct_values: int
    first_at: Optional[datetime]
    last_at: Optional[datetime]
    first_equity: Optional[float]
    last_equity: Optional[float]
    environment: Environment
    currency: str
    empty_reason: Optional[str] = None

    @property
    def change_abs(self) -> Optional[float]:
        if self.first_equity is None or self.last_equity is None:
            return None
        return self.last_equity - self.first_equity

    @property
    def change_pct(self) -> Optional[float]:
        if not self.first_equity:
            return None
        change = self.change_abs
        return None if change is None else change / self.first_equity * 100.0

    def to_dict(self) -> dict:
        return {
            "points": self.points,
            "window": self.window,
            "window_label": self.window_label,
            "observations": self.observations,
            # A series of 16 000 rows holding 44 distinct values is a polling
            # artefact, not a market. Reporting both lets the UI say so.
            "distinct_values": self.distinct_values,
            "first_at": to_display(self.first_at),
            "last_at": to_display(self.last_at),
            "first_equity": self.first_equity,
            "last_equity": self.last_equity,
            "change_abs": self.change_abs,
            "change_pct": self.change_pct,
            "environment": self.environment.value,
            "currency": self.currency,
        }

    def freshness(self) -> Freshness:
        return Freshness(
            source_as_of=self.last_at,
            source="equity_snapshots",
            stale_after_seconds=EQUITY_STALE_AFTER_SECONDS,
        )


class EquityService:
    def __init__(self, engine):
        self._equity = EquityRepository(engine)
        self._trades = TradesRepository(engine)

    def _account(self, account_id: Optional[int], mode: str) -> Optional[dict]:
        aid = account_id or self._trades.default_account_id(mode=mode)
        return self._trades.account(aid) if aid else None

    def series(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        window: str = "90d",
        environment: Environment = Environment.SANDBOX,
    ) -> EquitySeries:
        window = window if window in WINDOW_BUCKETS else "90d"
        account = self._account(account_id, mode)

        if account is None:
            return EquitySeries(
                points=[], window=window, window_label=WINDOW_LABELS[window],
                observations=0, distinct_values=0,
                first_at=None, last_at=None, first_equity=None, last_equity=None,
                environment=Environment.coerce(environment), currency="RUB",
                empty_reason=EmptyReason.NOT_CONFIGURED,
            )

        aid = int(account["id"])
        env = Environment.coerce(environment)
        stats = self._equity.stats(aid, window=window, environment=env)
        rows = self._equity.series(aid, window=window, environment=env)

        points = [
            {
                "ts": to_display(row["ts"]),
                "equity": safe_float(row["equity"]),
                "source_at": to_display(row.get("source_at")),
            }
            for row in rows
            if safe_float(row["equity"]) is not None
        ]

        return EquitySeries(
            points=points,
            window=window,
            window_label=WINDOW_LABELS[window],
            observations=stats["observations"],
            distinct_values=stats["distinct_values"],
            first_at=stats["first_at"],
            last_at=stats["last_at"],
            first_equity=stats["first_equity"],
            last_equity=stats["last_equity"],
            environment=env,
            currency=account.get("currency") or "RUB",
            empty_reason=None if points else EmptyReason.NO_EQUITY_HISTORY,
        )

    def drawdown(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        window: str = "90d",
        environment: Environment = Environment.SANDBOX,
    ) -> dict:
        """Max drawdown in both units, plus the current drawdown from peak.

        Computed on the full-resolution series: a bucketed series can miss the
        trough between two boundaries and under-report the worst drawdown.
        """
        account = self._account(account_id, mode)
        if account is None:
            return self._empty_drawdown(window, Environment.coerce(environment), "RUB")

        aid = int(account["id"])
        env = Environment.coerce(environment)
        span, _ = WINDOW_BUCKETS.get(window, WINDOW_BUCKETS["90d"])
        since = None if span is None else datetime.now(timezone.utc) - span
        values = self._equity.raw_values(aid, environment=env, since=since)

        max_pct, max_abs, peak = drawdown_from_equity(values)

        current_pct = current_abs = None
        if values:
            running_peak = max(values)
            current_abs = values[-1] - running_peak
            current_pct = (current_abs / running_peak * 100.0) if running_peak else None

        return {
            "max_drawdown_pct": None if max_pct is None else round(max_pct, 2),
            "max_drawdown_abs": None if max_abs is None else round(max_abs, 2),
            "max_drawdown_peak": None if peak is None else round(peak, 2),
            "current_drawdown_pct": None if current_pct is None else round(current_pct, 2),
            "current_drawdown_abs": None if current_abs is None else round(current_abs, 2),
            "n": len(values),
            "window": window,
            "window_label": WINDOW_LABELS.get(window, window),
            "environment": env.value,
            "currency": account.get("currency") or "RUB",
            "units": {
                "max_drawdown_pct": Units.PERCENT,
                "max_drawdown_abs": Units.MONEY,
                "current_drawdown_pct": Units.PERCENT,
                "current_drawdown_abs": Units.MONEY,
            },
        }

    @staticmethod
    def _empty_drawdown(window: str, environment: Environment, currency: str) -> dict:
        return {
            "max_drawdown_pct": None, "max_drawdown_abs": None, "max_drawdown_peak": None,
            "current_drawdown_pct": None, "current_drawdown_abs": None,
            "n": 0, "window": window, "window_label": WINDOW_LABELS.get(window, window),
            "environment": environment.value, "currency": currency,
            "units": {
                "max_drawdown_pct": Units.PERCENT, "max_drawdown_abs": Units.MONEY,
                "current_drawdown_pct": Units.PERCENT, "current_drawdown_abs": Units.MONEY,
            },
        }

    def risk_adjusted(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        environment: Environment = Environment.SANDBOX,
    ) -> dict:
        """Sharpe and Sortino with their sample size.

        Both are `None` below a usable sample. A 252-day annualised Sharpe over
        two observations is noise, and rendering it as a number invites a decision
        it cannot support.
        """
        account = self._account(account_id, mode)
        if account is None:
            return {"sharpe_ratio": None, "sortino_ratio": None, "n": 0, "mature": False}

        env = Environment.coerce(environment)
        returns = self._equity.daily_returns(int(account["id"]), environment=env)
        n = len(returns)
        #: 20 daily observations is the floor for quoting an annualised figure.
        mature = n >= 20
        sharpe = sharpe_from_returns(returns) if mature else None
        sortino = sortino_from_returns(returns) if mature else None
        return {
            "sharpe_ratio": None if sharpe is None else round(sharpe, 2),
            "sortino_ratio": None if sortino is None else round(sortino, 2),
            "n": n,
            "mature": mature,
            "basis": "дневные приращения equity_snapshots",
            "environment": env.value,
        }

    def underwater(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        window: str = "90d",
        environment: Environment = Environment.SANDBOX,
    ) -> list[dict]:
        """Drawdown-from-peak over time, sharing the equity chart's x-axis."""
        series = self.series(
            account_id=account_id, mode=mode, window=window, environment=environment
        )
        peak = None
        out: list[dict] = []
        for point in series.points:
            value = point.get("equity")
            if value is None:
                continue
            peak = value if peak is None or value > peak else peak
            out.append({
                "ts": point["ts"],
                "drawdown_pct": round((value - peak) / peak * 100.0, 3) if peak else 0.0,
            })
        return out

    def daily_pnl(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        days: int = 30,
        environment: Environment = Environment.SANDBOX,
    ) -> list[dict]:
        """Signed daily change in equity — the input for the PnL bar chart."""
        account = self._account(account_id, mode)
        if account is None:
            return []
        closes = self._equity.daily_closes(
            int(account["id"]), environment=Environment.coerce(environment)
        )
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        out: list[dict] = []
        for index in range(1, len(closes)):
            day = closes[index]["day"]
            if hasattr(day, "date"):
                day = day.date()
            if day < cutoff:
                continue
            previous = safe_float(closes[index - 1]["equity"])
            current = safe_float(closes[index]["equity"])
            if previous is None or current is None:
                continue
            out.append({
                "day": str(day),
                "pnl": round(current - previous, 2),
                "pnl_pct": round((current - previous) / previous * 100.0, 3) if previous else None,
            })
        return out
