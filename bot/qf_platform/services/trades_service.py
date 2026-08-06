"""Closed trades and the account summary.

The envelope defect this fixes: ``/api/platform/paper/trades`` returned a bare
JSON array while the client read ``payload.trades``, so 35 existing rows rendered
as zero and «История Paper Trades» was permanently empty. Everything here returns
``{"trades": [...], "total": N, ...}`` and a contract test asserts that N rows in
the database produce N rows in the response under the same filters.

The account summary also stops merging two different accounts under one label.
The Tinkoff brokerage portfolio and the simulated paper account are reported as
separate, named sources; ``available_balance`` greater than ``balance`` — which is
the live state — is surfaced as an inconsistency rather than silently displayed.
"""

from __future__ import annotations

import logging
from typing import Optional

from qf_platform.contracts import EmptyReason, Freshness, Units, safe_float, to_display
from qf_platform.environment import Environment
from qf_platform.repositories.trades_repository import PERIODS, TradesRepository
from qf_platform.services.metrics_service import PERIOD_LABELS

logger = logging.getLogger(__name__)

TRADES_STALE_AFTER_SECONDS = 300


class TradesService:
    def __init__(self, engine):
        self._repo = TradesRepository(engine)

    def _account(self, account_id: Optional[int], mode: str) -> Optional[dict]:
        aid = account_id or self._repo.default_account_id(mode=mode)
        return self._repo.account(aid) if aid else None

    def closed_trades(
        self,
        *,
        account_id: Optional[int] = None,
        mode: str = "rub",
        period: str = "30d",
        ticker: Optional[str] = None,
        direction: Optional[str] = None,
        result: Optional[str] = None,
        environment: Environment = Environment.SANDBOX,
        sort: str = "closed_at",
        descending: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        period = period if period in PERIODS else "30d"
        account = self._account(account_id, mode)
        if account is None:
            return {
                "trades": [], "total": 0, "returned": 0, "offset": offset,
                "empty_reason": EmptyReason.NOT_CONFIGURED,
                "period": period, "period_label": PERIOD_LABELS.get(period, period),
                "environment": Environment.coerce(environment).value, "currency": "RUB",
                "tickers": [],
            }

        aid = int(account["id"])
        env = Environment.coerce(environment)
        filters = {
            "period": period, "ticker": ticker, "direction": direction,
            "result": result, "environment": env,
        }
        total = self._repo.paper_trades_count(aid, **filters)
        rows = self._repo.paper_trades(
            aid, sort=sort, descending=descending, limit=limit, offset=offset, **filters
        )

        trades = [
            {
                "id": int(row["id"]),
                "ticker": row["ticker"],
                "exchange": row.get("exchange"),
                "direction": (row.get("direction") or "").lower(),
                "entry_price": safe_float(row["entry_price"]),
                "exit_price": safe_float(row["exit_price"]),
                "quantity": safe_float(row["quantity"]),
                "pnl": safe_float(row["pnl"]),
                # Stored as a fraction; ×100 exactly once, here.
                "pnl_pct": (
                    None if safe_float(row["pnl_pct"]) is None
                    else round(safe_float(row["pnl_pct"]) * 100.0, 3)
                ),
                # `pnl_r` does not exist on paper_trades. Reporting None rather
                # than 0 keeps «н/д» distinguishable from a genuine 0R.
                "pnl_r": None,
                "commission": safe_float(row.get("commission")),
                "slippage": safe_float(row.get("slippage")),
                "close_reason": row.get("close_reason"),
                "entry_reason": row.get("entry_reason"),
                "opened_at": to_display(row.get("opened_at")),
                "closed_at": to_display(row.get("closed_at")),
                "duration_seconds": (
                    None if row.get("duration_seconds") is None
                    else int(safe_float(row["duration_seconds"]) or 0)
                ),
                "environment": row.get("environment") or env.value,
            }
            for row in rows
        ]

        empty_reason = None
        if not trades:
            empty_reason = (
                EmptyReason.NO_TRADES_IN_PERIOD if (period != "all" or ticker or direction or result)
                else EmptyReason.NO_TRADES_EVER
            )

        newest = max((r.get("closed_at") for r in rows if r.get("closed_at")), default=None)
        return {
            "trades": trades,
            "total": total,
            "returned": len(trades),
            "offset": offset,
            "empty_reason": empty_reason,
            "period": period,
            "period_label": PERIOD_LABELS.get(period, period),
            "environment": env.value,
            "currency": account.get("currency") or "RUB",
            "tickers": self._repo.paper_trade_tickers(aid),
            "_source_as_of": newest,
            "units": {
                "pnl": Units.MONEY, "pnl_pct": Units.PERCENT, "pnl_r": Units.R_MULTIPLE,
                "entry_price": Units.PRICE, "quantity": Units.SHARES,
                "duration_seconds": Units.SECONDS,
            },
        }

    @staticmethod
    def freshness(payload: dict) -> Freshness:
        return Freshness(
            source_as_of=payload.get("_source_as_of"),
            source="paper_trades",
            stale_after_seconds=TRADES_STALE_AFTER_SECONDS,
        )

    def learning_trades(
        self,
        *,
        limit: int = 100,
        environment: Optional[Environment] = None,
        strategy_id: Optional[str] = None,
    ) -> dict:
        """The richer ``trades`` table — reported separately and labelled as such."""
        rows = self._repo.learning_trades(
            limit=limit, environment=environment, strategy_id=strategy_id
        )
        return {
            "trades": [
                {
                    "trade_id": row.get("trade_id"),
                    "ticker": row.get("ticker"),
                    "strategy_id": row.get("strategy_id"),
                    "direction": (row.get("direction") or "").lower(),
                    "timeframe": row.get("timeframe"),
                    "market_regime": row.get("market_regime"),
                    "entry_price": safe_float(row.get("entry_price")),
                    "exit_price": safe_float(row.get("exit_price")),
                    "pnl": safe_float(row.get("pnl")),
                    "pnl_r": safe_float(row.get("pnl_r")),
                    "confidence": safe_float(row.get("confidence")),
                    "decision_quality": safe_float(row.get("decision_quality")),
                    "strategy_followed": row.get("strategy_followed"),
                    "exit_reason_type": row.get("exit_reason_type"),
                    "entry_reason": row.get("entry_reason"),
                    "opened_at": to_display(row.get("opened_at")),
                    "closed_at": to_display(row.get("closed_at")),
                    "environment": row.get("environment") or Environment.UNKNOWN.value,
                }
                for row in rows
            ],
            "total": self._repo.learning_trades_count(environment=environment),
            "source": "trades",
            "note": (
                "Таблица trades — записи системы обучения. Счёт торговал в paper_trades; "
                "показатели счёта считаются по paper_trades."
            ),
        }

    def accounts_summary(self) -> dict:
        """Every account named separately, plus any internal inconsistency.

        ``available_balance`` (12 359 136,94) exceeding ``balance`` (7 626 545,68)
        is the live state of this database. It is incoherent, and displaying it
        under a single «Общий баланс» label is how a user ends up trusting a
        number nobody can reconcile.
        """
        accounts = []
        for row in self._repo.accounts():
            balance = safe_float(row.get("balance")) or 0.0
            available = safe_float(row.get("available_balance")) or 0.0
            initial = safe_float(row.get("initial_balance")) or 0.0
            inconsistencies = []
            if available > balance:
                inconsistencies.append(
                    "Доступные средства больше общего баланса — данные счёта несогласованы."
                )
            accounts.append({
                "id": int(row["id"]),
                "name": f"Paper · {str(row.get('mode') or '').upper()}",
                "source": "paper_accounts",
                "mode": row.get("mode"),
                "environment": row.get("environment") or Environment.SANDBOX.value,
                "currency": row.get("currency") or "RUB",
                "initial_balance": initial,
                "balance": balance,
                "available_balance": available,
                "margin_used": safe_float(row.get("margin_used")),
                "total_return_abs": round(balance - initial, 2) if initial else None,
                "total_return_pct": (
                    round((balance - initial) / initial * 100.0, 2) if initial else None
                ),
                "updated_at": to_display(row.get("updated_at")),
                "inconsistencies": inconsistencies,
            })
        return {
            "accounts": accounts,
            "count": len(accounts),
            "units": {
                "balance": Units.MONEY, "available_balance": Units.MONEY,
                "total_return_pct": Units.PERCENT,
            },
        }
