"""Trade statistics — every one of them with its sample size.

The two defects this replaces:

* ``avg_profit_pct`` was ``AVG(ABS(pnl_pct))``. On the live account — 35 trades,
  zero wins, −₽2 373 454 — it reported **+16,07 %**. An average that discards the
  sign is the *average move*, which is a legitimate but different statistic; it is
  returned here under its own name, next to the signed mean.
* Statistics were shown without ``n``, so `0,00 %` from zero trades looked
  identical to a genuine 0 % over 48. Every figure below returns `None` at n=0 and
  carries its own ``n``.
"""

from __future__ import annotations

import logging
from typing import Optional

from qf_platform.contracts import (
    EmptyReason,
    Freshness,
    MIN_SAMPLE_FOR_RANKING,
    Units,
    is_mature_sample,
    mean_abs,
    profit_factor,
    safe_float,
    signed_mean,
    win_rate,
)
from qf_platform.environment import Environment
from qf_platform.repositories.trades_repository import PERIODS, TradesRepository

logger = logging.getLogger(__name__)

PERIOD_LABELS = {
    "1d": "сутки",
    "7d": "7 дней",
    "30d": "30 дней",
    "90d": "90 дней",
    "1y": "год",
    "all": "вся история",
}


class MetricsService:
    """Aggregates over ``paper_trades`` — the table the account actually traded.

    Deliberately does not mix in ``trades``: two rows of richer data and 35 rows
    of real fills are different populations, and averaging across them under one
    badge is what made three panels disagree in a single frame.
    """

    def __init__(self, engine):
        self._trades = TradesRepository(engine)

    def _resolve_account(self, account_id: Optional[int], mode: str) -> Optional[dict]:
        aid = account_id or self._trades.default_account_id(mode=mode)
        return self._trades.account(aid) if aid else None

    def trade_statistics(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        period: str = "all",
        environment: Environment = Environment.SANDBOX,
    ) -> dict:
        period = period if period in PERIODS else "all"
        account = self._resolve_account(account_id, mode)
        if account is None:
            return self._empty(period, Environment.coerce(environment), "RUB",
                               EmptyReason.NOT_CONFIGURED)

        env = Environment.coerce(environment)
        rows = self._trades.paper_pnl_values(
            int(account["id"]), period=period, environment=env
        )
        currency = account.get("currency") or "RUB"

        if not rows:
            reason = (
                EmptyReason.NO_TRADES_IN_PERIOD if period != "all"
                else EmptyReason.NO_TRADES_EVER
            )
            return self._empty(period, env, currency, reason)

        pnls = [safe_float(r["pnl"]) for r in rows]
        pnls = [p for p in pnls if p is not None]
        # `pnl_pct` is stored as a fraction (0.0123 = 1,23 %); ×100 exactly once,
        # here, so no consumer has to guess the unit.
        pct_values = [
            p * 100.0 for p in (safe_float(r["pnl_pct"]) for r in rows) if p is not None
        ]

        avg_pnl, n_pnl = signed_mean(pnls)
        avg_pct, n_pct = signed_mean(pct_values)
        avg_move_pct, _ = mean_abs(pct_values)
        pf, n_pf = profit_factor(pnls)
        wr, wins, n_wr = win_rate(pnls)

        losses = [p for p in pnls if p < 0]
        winners = [p for p in pnls if p > 0]
        avg_win, n_win = signed_mean(winners)
        avg_loss, n_loss = signed_mean(losses)
        commission = sum(
            c for c in (safe_float(r.get("commission")) for r in rows) if c is not None
        )

        # Expectancy per trade, from the components rather than from total/n, so it
        # stays interpretable when one side of the distribution is empty.
        expectancy = None
        if n_wr:
            win_share = wins / n_wr
            expectancy = (
                win_share * (avg_win or 0.0) + (1 - win_share) * (avg_loss or 0.0)
            )

        durations = [
            d for d in (safe_float(r.get("duration_seconds")) for r in rows) if d is not None
        ] if rows and "duration_seconds" in rows[0] else []

        return {
            "n": n_pnl,
            "period": period,
            "period_label": PERIOD_LABELS.get(period, period),
            "environment": env.value,
            "currency": currency,
            "mature_sample": is_mature_sample(n_pnl),
            "min_sample_for_ranking": MIN_SAMPLE_FOR_RANKING,

            "total_pnl": round(sum(pnls), 2),
            "gross_profit": round(sum(winners), 2),
            "gross_loss": round(abs(sum(losses)), 2),
            "commission_total": round(commission, 2),

            # Signed mean — the honest "average profit".
            "avg_pnl": None if avg_pnl is None else round(avg_pnl, 2),
            "avg_pnl_n": n_pnl,
            "avg_pnl_pct": None if avg_pct is None else round(avg_pct, 3),
            "avg_pnl_pct_n": n_pct,
            # Mean absolute move — the old AVG(ABS(...)) value, correctly named.
            "avg_abs_move_pct": None if avg_move_pct is None else round(avg_move_pct, 3),

            "avg_win": None if avg_win is None else round(avg_win, 2),
            "avg_win_n": n_win,
            "avg_loss": None if avg_loss is None else round(avg_loss, 2),
            "avg_loss_n": n_loss,
            "expectancy": None if expectancy is None else round(expectancy, 2),
            "expectancy_n": n_wr,

            "win_rate_pct": None if wr is None else round(wr, 1),
            "wins": wins,
            "losses": len(losses),
            "flat": n_wr - wins - len(losses),
            "win_rate_n": n_wr,

            "profit_factor": None if pf is None else round(pf, 2),
            "profit_factor_n": n_pf,
            # `None` is ambiguous on its own: no losses at all, or no trades?
            "profit_factor_undefined_reason": (
                None if pf is not None
                else ("нет убыточных сделок" if n_pf else "нет сделок")
            ),

            "avg_duration_seconds": (
                round(sum(durations) / len(durations)) if durations else None
            ),

            "units": {
                "total_pnl": Units.MONEY,
                "avg_pnl": Units.MONEY,
                "avg_pnl_pct": Units.PERCENT,
                "avg_abs_move_pct": Units.PERCENT,
                "win_rate_pct": Units.PERCENT,
                "profit_factor": Units.RATIO,
                "expectancy": Units.MONEY,
                "avg_duration_seconds": Units.SECONDS,
            },
        }

    @staticmethod
    def _empty(period: str, environment: Environment, currency: str, reason: str) -> dict:
        return {
            "n": 0,
            "period": period,
            "period_label": PERIOD_LABELS.get(period, period),
            "environment": environment.value,
            "currency": currency,
            "mature_sample": False,
            "min_sample_for_ranking": MIN_SAMPLE_FOR_RANKING,
            "empty_reason": reason,
            "total_pnl": None, "gross_profit": None, "gross_loss": None,
            "commission_total": None,
            "avg_pnl": None, "avg_pnl_n": 0,
            "avg_pnl_pct": None, "avg_pnl_pct_n": 0,
            "avg_abs_move_pct": None,
            "avg_win": None, "avg_win_n": 0, "avg_loss": None, "avg_loss_n": 0,
            "expectancy": None, "expectancy_n": 0,
            "win_rate_pct": None, "wins": 0, "losses": 0, "flat": 0, "win_rate_n": 0,
            "profit_factor": None, "profit_factor_n": 0,
            "profit_factor_undefined_reason": "нет сделок",
            "avg_duration_seconds": None,
            "units": {},
        }

    def pnl_windows(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
    ) -> dict:
        """Realised PnL for day / week / month, each with its own trade count.

        Three tiles all reading `+0,00 ₽` was the old Overview's first fold. A
        measured zero and an absent measurement now differ: `n=0` yields `None`.
        """
        account = self._resolve_account(account_id, mode)
        if account is None:
            return {"currency": "RUB", "windows": {}}

        row = self._trades.paper_pnl_periods(int(account["id"]))

        def window(pnl_key: str, n_key: str, label: str) -> dict:
            n = int(row.get(n_key) or 0)
            value = safe_float(row.get(pnl_key))
            return {
                "pnl": None if n == 0 else round(value or 0.0, 2),
                "n": n,
                "label": label,
                "empty_reason": None if n else EmptyReason.NO_TRADES_IN_PERIOD,
            }

        return {
            "currency": account.get("currency") or "RUB",
            "environment": account.get("environment") or Environment.SANDBOX.value,
            "windows": {
                "day": window("pnl_day", "n_day", "сегодня"),
                "week": window("pnl_week", "n_week", "7 дней"),
                "month": window("pnl_month", "n_month", "30 дней"),
            },
            "realized_pnl": safe_float(row.get("realized_pnl")),
            "commission_total": safe_float(row.get("commission_total")),
            "closed_count": int(row.get("closed_count") or 0),
            "units": {"pnl": Units.MONEY, "realized_pnl": Units.MONEY},
        }

    def ticker_breakdown(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        period: str = "all",
        environment: Environment = Environment.SANDBOX,
    ) -> list[dict]:
        account = self._resolve_account(account_id, mode)
        if account is None:
            return []
        rows = self._trades.paper_pnl_values(
            int(account["id"]), period=period, environment=Environment.coerce(environment)
        )
        buckets: dict[str, list[float]] = {}
        for row in rows:
            value = safe_float(row["pnl"])
            if value is None:
                continue
            buckets.setdefault(row["ticker"], []).append(value)

        out = []
        for ticker, values in buckets.items():
            wr, wins, n = win_rate(values)
            out.append({
                "ticker": ticker,
                "n": n,
                "total_pnl": round(sum(values), 2),
                "wins": wins,
                "win_rate_pct": None if wr is None else round(wr, 1),
                "mature_sample": is_mature_sample(n),
            })
        out.sort(key=lambda item: item["total_pnl"])
        return out

    def distribution(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        period: str = "all",
        bins: int = 12,
        environment: Environment = Environment.SANDBOX,
    ) -> dict:
        """PnL histogram with the bin width stated.

        A histogram whose bin width is unstated cannot be read; and with a handful
        of trades it should not be drawn at all, which is why `n` travels with it.
        """
        account = self._resolve_account(account_id, mode)
        if account is None:
            return {"bins": [], "n": 0, "bin_width": None}

        rows = self._trades.paper_pnl_values(
            int(account["id"]), period=period, environment=Environment.coerce(environment)
        )
        values = [v for v in (safe_float(r["pnl"]) for r in rows) if v is not None]
        if len(values) < 2:
            return {"bins": [], "n": len(values), "bin_width": None}

        low, high = min(values), max(values)
        if low == high:
            return {
                "bins": [{"from": low, "to": high, "count": len(values)}],
                "n": len(values), "bin_width": 0.0,
            }
        width = (high - low) / bins
        counts = [0] * bins
        for value in values:
            index = min(bins - 1, int((value - low) / width))
            counts[index] += 1
        return {
            "bins": [
                {
                    "from": round(low + i * width, 2),
                    "to": round(low + (i + 1) * width, 2),
                    "count": counts[i],
                }
                for i in range(bins)
            ],
            "n": len(values),
            "bin_width": round(width, 2),
            "units": {"from": Units.MONEY, "to": Units.MONEY},
        }
