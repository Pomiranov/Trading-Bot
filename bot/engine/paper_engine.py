"""Unified Paper Trading Engine — single source of truth for paper trading."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from realtime.sse_hub import sse_hub

if TYPE_CHECKING:
    from learning.sandbox_learning_loop import SandboxLearningLoop

logger = logging.getLogger(__name__)

COMMISSION_PCT = 0.0003   # 0.03% per side
SLIPPAGE_PCT   = 0.0001   # 0.01% slippage
MONITOR_INTERVAL = 30     # seconds
SIGNAL_INTERVAL  = 90     # seconds


class _GateStage:
    """Local mirror of qf_platform.repositories.signals_gate_repository.GateStage.

    Duplicated deliberately: this module is imported by the bot process, where
    pulling in the platform repository layer at import time would drag in
    SQLAlchemy for a handful of string constants. The repository import stays
    inside the one method that writes.
    """

    RISK = "risk"
    LEARNING = "learning"
    FILTER = "filter"
    DUPLICATE = "duplicate"
    BROKER = "broker"
    MARKET_CLOSED = "market_closed"


def _risk_reason_code(text: str) -> str:
    """Map the gate's Russian message onto a stable machine-readable code.

    The message is what an operator reads; the code is what a filter and a chart
    group by. Deriving the code from the message keeps a single source for the
    wording while still giving the UI something it can aggregate.
    """
    lowered = (text or "").lower()
    if "уже открыта" in lowered:
        return "duplicate_position"
    if "лимит позиций" in lowered:
        return "max_open_positions"
    if "дневной лимит" in lowered:
        return "daily_loss_limit"
    return "risk_rejected"


def _is_market_open() -> bool:
    """Return True during Moscow exchange trading hours (UTC 07:00–15:59)."""
    now = datetime.utcnow()
    return 7 <= now.hour < 16


class PaperEngine:
    """
    Unified Paper Trading Engine with two background threads:
      - signal_loop: runs every 90 s, generates signals and executes top-3
      - monitor_loop: runs every 30 s, checks SL/TP/trailing-stop hits
    """

    def __init__(self) -> None:
        self._db_engine = None
        self._stop_flag = threading.Event()
        self._running = False
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._signal_thread: Optional[threading.Thread] = None

        # Learning integration: maps paper position_id → learning trade_id
        self._learning_loop: Optional["SandboxLearningLoop"] = None
        self._trade_learning_map: dict[int, str] = {}  # position_id → trade_id
        self._trade_open_context: dict[int, dict] = {}  # position_id → Trade kwargs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_db_engine(self):
        if self._db_engine is None:
            from sqlalchemy import create_engine
            from config import config
            self._db_engine = create_engine(
                config.db.dsn,
                pool_size=2,
                max_overflow=2,
                pool_pre_ping=True,
            )
        return self._db_engine

    def _push_sse(self, event_type: str, data: dict) -> None:
        # Try direct (same process as dashboard)
        try:
            sse_hub.publish(event_type, data)
            return
        except Exception:
            pass
        # Fallback via HTTP (if in bot process)
        try:
            import os
            import requests
            from config import config
            token = os.getenv("QF_INTERNAL_TOKEN", "")
            headers = {"X-Internal-Token": token} if token else {}
            requests.post(
                f"http://127.0.0.1:{config.dashboard.port}/api/internal/push",
                json={"event_type": event_type, **data},
                headers=headers,
                timeout=2,
            )
        except Exception:
            pass

    def _get_market_price(self, ticker: str) -> Optional[float]:
        """Resolve current market price via MarketDataHub."""
        try:
            from market.data_hub import MarketDataHub
            hub = MarketDataHub(self._get_db_engine())
            quote = hub.get_quote(ticker)
            return quote.last if quote else None
        except Exception as exc:
            logger.debug("PaperEngine._get_market_price error for %s: %s", ticker, exc)
            return None

    def _get_repo(self):
        from qf_platform.repositories.paper_repository import PaperRepository
        return PaperRepository(self._get_db_engine())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_trade(
        self,
        ticker: str,
        direction: str = "long",
        quantity: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        exchange: str = "paper",
        signal_id: Optional[int] = None,
        entry_reason: str = "",
        probability_pct: Optional[float] = None,
        # Learning context (optional, passed by _run_signal_cycle)
        strategy_id: str = "default_sandbox",
        market_features: Optional[dict] = None,
        learning_confidence: Optional[float] = None,
    ) -> dict:
        """Open a paper position with commission and slippage applied."""
        repo = self._get_repo()
        account = repo.get_or_create_account()
        account_id = int(account["id"])

        price = self._get_market_price(ticker)
        if price is None:
            raise ValueError(f"Нет рыночных данных для {ticker}")

        # Apply slippage (worse fill for the trader)
        if direction == "long":
            fill_price = price * (1 + SLIPPAGE_PCT)
        else:
            fill_price = price * (1 - SLIPPAGE_PCT)

        available = float(account["available_balance"])
        if quantity is None:
            risk_capital = available * 0.05
            quantity = max(1, int(risk_capital / fill_price))

        cost = fill_price * quantity
        commission = cost * COMMISSION_PCT

        if cost + commission > available:
            raise ValueError("Недостаточно средств на paper-счёте")

        if stop_loss is None:
            stop_loss = round(fill_price * 0.97, 4) if direction == "long" else round(fill_price * 1.03, 4)
        if take_profit is None:
            take_profit = round(fill_price * 1.06, 4) if direction == "long" else round(fill_price * 0.94, 4)

        pos_id = repo.insert_position(account_id, {
            "ticker": ticker.upper(),
            "exchange": exchange,
            "direction": direction,
            "quantity": quantity,
            "entry_price": fill_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        })

        # Update signal_id and entry_reason if provided
        if signal_id is not None or entry_reason:
            try:
                from sqlalchemy import text
                with self._get_db_engine().begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE paper_positions SET signal_id = :sid, entry_reason = :reason"
                            " WHERE id = :id"
                        ),
                        {"sid": signal_id, "reason": entry_reason or None, "id": pos_id},
                    )
            except Exception as exc:
                logger.debug("Could not set signal_id/entry_reason on position: %s", exc)

        new_available = available - cost - commission
        margin = float(account["margin_used"]) + cost
        repo.update_account_balances(account_id, float(account["balance"]), new_available, margin)

        result = {
            "position_id": pos_id,
            "ticker": ticker.upper(),
            "direction": direction,
            "entry_price": round(fill_price, 4),
            "quantity": quantity,
            "commission": round(commission, 4),
            "slippage": round(fill_price - price, 4),
            "entry_reason": entry_reason,
            "probability_pct": probability_pct,
        }

        self._push_sse("paper_trade_executed", result)
        self._push_sse("portfolio_updated", {"account_id": account_id})
        logger.info(
            "PaperEngine: opened %s %s qty=%s @ %s (commission=%.2f)",
            direction, ticker, quantity, fill_price, commission,
        )

        try:
            from tg.notifications.dispatcher import notify_paper_trade_open_sync
            entry_reason = result.get("entry_reason", "")
            notify_paper_trade_open_sync(
                ticker=ticker,
                direction=direction,
                price=fill_price,
                quantity=quantity,
                probability=result.get("probability_pct"),
                entry_reason=entry_reason,
            )
        except Exception as _exc:
            logger.debug("PaperEngine: telegram notify error: %s", _exc)

        # Learning: record trade open in TradingOrchestrator
        self._register_open_with_learning(
            pos_id=pos_id,
            ticker=ticker,
            direction=direction,
            fill_price=fill_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            quantity=quantity,
            commission=commission,
            strategy_id=strategy_id,
            market_features=market_features or {},
            entry_reason=result.get("entry_reason", ""),
            confidence=learning_confidence,
        )

        return result

    def _register_open_with_learning(
        self,
        pos_id: int,
        ticker: str,
        direction: str,
        fill_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        quantity: float,
        commission: float,
        strategy_id: str,
        market_features: dict,
        entry_reason: str,
        confidence: Optional[float],
    ) -> None:
        """Send trade-open event to SandboxLearningLoop (non-blocking)."""
        if not self._learning_loop or not self._learning_loop.is_running():
            return
        try:
            from learning.memory_writer import Trade, Market, Direction, ExitReasonType

            sl_decimal = Decimal(str(stop_loss)) if stop_loss else Decimal(str(fill_price * 0.97))
            tp_decimal = Decimal(str(take_profit)) if take_profit else None
            qty_decimal = Decimal(str(quantity))
            entry_decimal = Decimal(str(fill_price))
            risk_amount = abs(entry_decimal - sl_decimal) * qty_decimal

            trade = Trade(
                market=Market.STOCKS,
                ticker=ticker.upper(),
                direction=Direction.BUY if direction.lower() == "long" else Direction.SELL,
                strategy_id=strategy_id or "default_sandbox",
                entry_price=entry_decimal,
                stop_loss=sl_decimal,
                take_profit=tp_decimal,
                position_size=qty_decimal,
                risk_amount=max(risk_amount, Decimal("1")),
                commission=Decimal(str(commission)),
                market_features=market_features,
                entry_reason=entry_reason or None,
                confidence=Decimal(str(round(confidence, 4))) if confidence is not None else None,
                opened_at=datetime.now(timezone.utc),
                is_sandbox=True,
            )

            learning_trade_id = self._learning_loop.on_trade_opened(trade)
            if learning_trade_id:
                self._trade_learning_map[pos_id] = learning_trade_id
                self._trade_open_context[pos_id] = {
                    "trade": trade,
                    "strategy_id": strategy_id,
                }
                logger.debug(
                    "PaperEngine: learning trade_id=%s for pos=%d", learning_trade_id[:8], pos_id
                )
        except Exception as exc:
            logger.debug("PaperEngine: learning open error for pos %d: %s", pos_id, exc)

    def close_trade(
        self,
        position_id: int,
        reason: str = "manual",
        exit_price: Optional[float] = None,
    ) -> dict:
        """Close a paper position at current market price with commission + slippage."""
        repo = self._get_repo()
        pos = repo.get_position(position_id)
        if not pos:
            raise ValueError(f"Позиция {position_id} не найдена")

        direction = (pos["direction"] or "long").lower()
        qty = float(pos["quantity"])
        entry = float(pos["entry_price"])
        account_id = int(pos["account_id"])

        # Use actual current price (not entry_price)
        if exit_price is None:
            exit_price = self._get_market_price(pos["ticker"])
        if exit_price is None:
            exit_price = entry  # last resort fallback

        # Apply slippage on exit (worse fill)
        if direction == "long":
            fill_exit = exit_price * (1 - SLIPPAGE_PCT)
        else:
            fill_exit = exit_price * (1 + SLIPPAGE_PCT)

        commission = fill_exit * qty * COMMISSION_PCT

        if direction == "short":
            raw_pnl = (entry - fill_exit) * qty
        else:
            raw_pnl = (fill_exit - entry) * qty

        pnl = raw_pnl - commission
        pnl_pct = pnl / (entry * qty) if entry * qty else 0

        # Persist trade record with extra fields
        entry_reason = pos.get("entry_reason") or ""
        try:
            from sqlalchemy import text
            with self._get_db_engine().begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO paper_trades
                            (account_id, position_id, ticker, exchange, direction,
                             entry_price, exit_price, quantity, pnl, pnl_pct,
                             opened_at, commission, slippage, close_reason, entry_reason)
                        VALUES
                            (:aid, :pid, :ticker, :exchange, :direction,
                             :entry, :exit, :qty, :pnl, :pnl_pct,
                             :opened, :commission, :slippage, :reason, :entry_reason)
                        """
                    ),
                    {
                        "aid": account_id,
                        "pid": position_id,
                        "ticker": pos["ticker"],
                        "exchange": pos.get("exchange", "paper"),
                        "direction": direction,
                        "entry": entry,
                        "exit": fill_exit,
                        "qty": qty,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "opened": pos["opened_at"],
                        "commission": commission,
                        "slippage": round(abs(fill_exit - exit_price) * qty, 4),
                        "reason": reason,
                        "entry_reason": entry_reason or None,
                    },
                )
        except Exception:
            # Fallback: use basic insert without new columns (schema migration not yet run)
            repo.insert_trade(account_id, {
                "position_id": position_id,
                "ticker": pos["ticker"],
                "exchange": pos.get("exchange", "paper"),
                "direction": direction,
                "entry_price": entry,
                "exit_price": fill_exit,
                "quantity": qty,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "opened_at": pos["opened_at"],
            })

        repo.delete_position(position_id)

        # Update account balances
        account = repo._query("SELECT * FROM paper_accounts WHERE id = :id", {"id": account_id})[0]
        proceeds = fill_exit * qty - commission
        new_available = float(account["available_balance"]) + proceeds
        margin = max(0.0, float(account["margin_used"]) - entry * qty)
        realized = float(repo.pnl_periods(account_id).get("realized_pnl") or 0)
        initial = float(account["initial_balance"])
        positions = repo.list_positions(account_id)
        # Simple unrealized estimate (no price refresh here to avoid slow path)
        unrealized = sum(float(p.get("unrealized_pnl", 0)) for p in positions)
        balance = initial + realized + unrealized
        repo.update_account_balances(account_id, balance, new_available, margin)
        repo.record_equity_snapshot(account_id, "paper", balance)

        result = {
            "position_id": position_id,
            "ticker": pos["ticker"],
            "exit_price": round(fill_exit, 4),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct * 100, 4),
            "commission": round(commission, 4),
            "reason": reason,
        }

        self._push_sse("paper_position_closed", result)
        self._push_sse("portfolio_updated", {"account_id": account_id})
        logger.info(
            "PaperEngine: closed pos=%s %s pnl=%.2f reason=%s",
            position_id, pos["ticker"], pnl, reason,
        )

        try:
            from tg.notifications.dispatcher import notify_paper_trade_close_sync
            notify_paper_trade_close_sync(
                ticker=pos["ticker"],
                pnl=pnl,
                pnl_pct=round(pnl_pct * 100, 2),
                reason=reason,
                exit_price=fill_exit,
            )
        except Exception as _exc:
            logger.debug("PaperEngine: telegram notify (close) error: %s", _exc)

        # Learning: trigger full learning cycle on trade close
        self._trigger_learning_on_close(
            position_id=position_id,
            exit_price=fill_exit,
            pnl=pnl,
            reason=reason,
            opened_at=pos.get("opened_at"),
        )

        return result

    def _trigger_learning_on_close(
        self,
        position_id: int,
        exit_price: float,
        pnl: float,
        reason: str,
        opened_at,
    ) -> None:
        """Fire-and-forget: send trade-close event to SandboxLearningLoop."""
        if not self._learning_loop or not self._learning_loop.is_running():
            return

        learning_trade_id = self._trade_learning_map.pop(position_id, None)
        ctx = self._trade_open_context.pop(position_id, None)

        if not learning_trade_id or not ctx:
            return

        try:
            from learning.memory_writer import Trade, ExitReasonType

            reason_map = {
                "SL_HIT": ExitReasonType.STOP_LOSS,
                "TP_HIT": ExitReasonType.TAKE_PROFIT,
                "manual": ExitReasonType.MANUAL,
                "partial_full": ExitReasonType.MANUAL,
            }
            exit_reason_type = reason_map.get(reason.upper(), ExitReasonType.SIGNAL)

            trade: Trade = ctx["trade"]
            trade.trade_id = learning_trade_id
            trade.exit_price = Decimal(str(exit_price))
            trade.closed_at = datetime.now(timezone.utc)
            trade.pnl = Decimal(str(round(pnl, 4)))
            trade.exit_reason_type = exit_reason_type
            trade.exit_reason = reason

            self._learning_loop.on_trade_closed(trade)
            logger.info(
                "PaperEngine: learning cycle triggered for trade %s pnl=%.2f",
                learning_trade_id[:8], pnl,
            )

            # Also notify Telegram about learning result (async, will resolve later)
            self._learning_loop.notify_learning_event({
                "ticker": trade.ticker,
                "pnl": pnl,
                "reason": reason,
                "strategy_id": ctx.get("strategy_id", ""),
            })
        except Exception as exc:
            logger.debug("PaperEngine: learning close error for pos %d: %s", position_id, exc)

    def close_trade_partial(self, position_id: int, qty_pct: float) -> dict:
        """Close a fraction of a position (qty_pct in 0..1)."""
        repo = self._get_repo()
        pos = repo.get_position(position_id)
        if not pos:
            raise ValueError(f"Позиция {position_id} не найдена")

        qty_pct = max(0.01, min(1.0, qty_pct))
        full_qty = float(pos["quantity"])
        close_qty = full_qty * qty_pct
        remain_qty = full_qty - close_qty

        if remain_qty < 0.0001:
            return self.close_trade(position_id, reason="partial_full")

        exit_price = self._get_market_price(pos["ticker"]) or float(pos["entry_price"])
        direction = (pos["direction"] or "long").lower()
        entry = float(pos["entry_price"])
        account_id = int(pos["account_id"])

        if direction == "long":
            fill_exit = exit_price * (1 - SLIPPAGE_PCT)
        else:
            fill_exit = exit_price * (1 + SLIPPAGE_PCT)

        commission = fill_exit * close_qty * COMMISSION_PCT
        raw_pnl = (fill_exit - entry) * close_qty if direction == "long" else (entry - fill_exit) * close_qty
        pnl = raw_pnl - commission
        pnl_pct = pnl / (entry * close_qty) if entry * close_qty else 0

        # Update remaining quantity
        from sqlalchemy import text
        with self._get_db_engine().begin() as conn:
            conn.execute(
                text("UPDATE paper_positions SET quantity = :qty WHERE id = :id"),
                {"qty": remain_qty, "id": position_id},
            )

        # Record partial trade
        repo.insert_trade(account_id, {
            "position_id": position_id,
            "ticker": pos["ticker"],
            "exchange": pos.get("exchange", "paper"),
            "direction": direction,
            "entry_price": entry,
            "exit_price": fill_exit,
            "quantity": close_qty,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "opened_at": pos["opened_at"],
        })

        account = repo._query("SELECT * FROM paper_accounts WHERE id = :id", {"id": account_id})[0]
        proceeds = fill_exit * close_qty - commission
        new_available = float(account["available_balance"]) + proceeds
        margin = max(0.0, float(account["margin_used"]) - entry * close_qty)
        repo.update_account_balances(account_id, float(account["balance"]) + pnl, new_available, margin)

        result = {
            "position_id": position_id,
            "ticker": pos["ticker"],
            "closed_qty": close_qty,
            "remaining_qty": remain_qty,
            "exit_price": round(fill_exit, 4),
            "pnl": round(pnl, 2),
        }
        self._push_sse("paper_position_closed", {**result, "partial": True})
        return result

    def get_portfolio(self, mode: str = "rub") -> dict:
        """Return current paper account + open positions with live PnL."""
        repo = self._get_repo()
        account = repo.get_or_create_account(mode=mode)
        account_id = int(account["id"])
        positions = repo.list_positions(account_id)

        enriched = []
        for pos in positions:
            price = self._get_market_price(pos["ticker"]) or float(pos["entry_price"])
            qty = float(pos["quantity"])
            entry = float(pos["entry_price"])
            direction = (pos["direction"] or "long").lower()
            unrealized = (price - entry) * qty if direction == "long" else (entry - price) * qty
            enriched.append({
                **{k: v for k, v in pos.items()},
                "current_price": price,
                "unrealized_pnl": round(unrealized, 2),
                "pnl_pct": round(unrealized / (entry * qty) * 100, 4) if entry * qty else 0,
            })

        pnl_data = repo.pnl_periods(account_id)
        return {
            "account": {
                k: (float(v) if k in ("balance", "available_balance", "margin_used", "initial_balance") else v)
                for k, v in account.items()
            },
            "positions": enriched,
            "pnl": {k: float(v) if v is not None else 0 for k, v in pnl_data.items()},
        }

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    def _signal_loop(self) -> None:
        logger.info("PaperEngine signal_loop started")
        while not self._stop_flag.is_set():
            if _is_market_open():
                try:
                    self._run_signal_cycle()
                except Exception as exc:
                    logger.error("PaperEngine signal_loop error: %s", exc, exc_info=True)
            for _ in range(SIGNAL_INTERVAL):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)
        logger.info("PaperEngine signal_loop stopped")

    def _check_risk_limits(
        self, ticker: str, account_id: Optional[int], portfolio_value: float
    ) -> tuple[bool, str]:
        """Gate trade against risk rules. Returns (allowed, reason).

        Scoped to this paper account's own positions/PnL (paper_positions /
        paper_trades) — must NOT touch risk.risk_manager. That tracker holds
        real broker positions/PnL for main.py's live trading loop; paper
        trades registering into it meant simulated activity here counted
        against (and could trip) the real max_open_positions /
        max_daily_loss_pct limits, and vice versa — a cross-contamination
        bug between simulated and real risk accounting.
        """
        if account_id is None:
            return True, ""
        try:
            from config import config

            repo = self._get_repo()
            open_positions = repo.list_positions(account_id)

            if any((p.get("ticker") or "").upper() == ticker.upper() for p in open_positions):
                return False, f"Позиция по {ticker} уже открыта"

            if len(open_positions) >= config.risk.max_open_positions:
                return False, f"Лимит позиций ({config.risk.max_open_positions}) достигнут"

            daily_pnl = float(repo.pnl_periods(account_id).get("pnl_day", 0) or 0)
            max_daily_loss = portfolio_value * config.risk.max_daily_loss_pct
            if daily_pnl <= -max_daily_loss:
                return False, (
                    f"Дневной лимит убытков: "
                    f"{daily_pnl:.2f} ₽ (лимит -{max_daily_loss:.2f} ₽)"
                )
        except Exception as exc:
            logger.debug("Risk check error: %s", exc)
        return True, ""

    def _record_gate_rejection(
        self,
        *,
        signal,
        strategy_id: str,
        stage: str,
        reason_code: str,
        reason_text: str,
        confidence: Optional[float] = None,
        sample_size: Optional[int] = None,
    ) -> None:
        """Write one row to `skipped_signals` and stamp the signal's decision.

        Best-effort by design: the gate's job is to stop a trade, and a failure to
        record why must never prevent that. Both writes swallow their own errors
        and log instead.
        """
        try:
            from qf_platform.environment import Environment
            from qf_platform.repositories.signals_gate_repository import (
                GateDecision,
                SignalsGateRepository,
            )

            repo = SignalsGateRepository(self._get_db_engine())
            repo.record_skip(
                strategy_id=strategy_id,
                ticker=getattr(signal, "asset", None),
                direction=getattr(signal, "signal_type", None),
                timeframe=getattr(signal, "timeframe", None),
                gate_stage=stage,
                reason_code=reason_code,
                reason_text=reason_text,
                environment=Environment.SANDBOX,
                signal_id=getattr(signal, "id", None) or None,
                confidence=confidence,
                sample_size=sample_size,
                details={"probability_pct": getattr(signal, "probability_pct", None)},
            )
            signal_id = getattr(signal, "id", None)
            if signal_id:
                decision = (
                    GateDecision.DUPLICATE if stage == _GateStage.DUPLICATE
                    else GateDecision.REJECTED
                )
                repo.record_decision(
                    int(signal_id), decision=decision, stage=stage,
                    reason=reason_text, confidence=confidence, sample_size=sample_size,
                )
        except Exception:  # noqa: BLE001
            logger.warning("Не удалось записать отклонение сигнала", exc_info=True)

    def _run_signal_cycle(self) -> None:
        db = self._get_db_engine()
        try:
            from qf_platform.services.signals_service import SignalsService
            signals = SignalsService(db).generate_live_signals(persist=True)
        except Exception as exc:
            logger.warning("PaperEngine: signal generation failed: %s", exc)
            return

        if not signals:
            logger.debug("PaperEngine: no signals this cycle")
            return

        # Push signals update to dashboard
        self._push_sse("signals_updated", {"count": len(signals), "source": "paper_engine"})

        # Get portfolio value for risk checks
        account_id = None
        try:
            account = self._get_repo().get_or_create_account()
            account_id = int(account["id"])
            portfolio_value = float(account.get("available_balance", 100_000))
        except Exception:
            portfolio_value = 100_000.0

        # Execute top-3 signals by probability_pct with risk validation
        top3 = sorted(signals, key=lambda s: s.probability_pct, reverse=True)[:3]
        executed = 0
        for i, sig in enumerate(top3):
            if self._stop_flag.is_set():
                break

            direction = "short" if sig.signal_type.upper() in ("SELL", "SHORT") else "long"
            meta = sig.metadata if isinstance(sig.metadata, dict) else {}

            # Risk gate
            allowed, reject_reason = self._check_risk_limits(sig.asset, account_id, portfolio_value)
            if not allowed:
                logger.info("PaperEngine: REJECTED %s — %s", sig.asset, reject_reason)
                # Persist the rejection. `skipped_signals` had a schema and zero
                # rows because nothing ever wrote to it, which made "why was this
                # signal rejected?" unanswerable from data rather than merely
                # unrendered. A duplicate position and a breached limit are
                # different stages, so they are recorded as different stages.
                self._record_gate_rejection(
                    signal=sig,
                    strategy_id=meta.get("strategy", "default_sandbox"),
                    stage=(
                        _GateStage.DUPLICATE if "уже открыта" in reject_reason
                        else _GateStage.RISK
                    ),
                    reason_code=_risk_reason_code(reject_reason),
                    reason_text=reject_reason,
                )
                self._push_sse("signal_rejected", {
                    "ticker": sig.asset,
                    "reason": reject_reason,
                    "signal_type": sig.signal_type,
                    "probability_pct": sig.probability_pct,
                })
                try:
                    from tg.notifications.dispatcher import notify_risk_limit_sync
                    notify_risk_limit_sync(f"{sig.asset}: {reject_reason}")
                except Exception:
                    pass
                continue

            try:
                entry_reason = meta.get("entry_reason", "")
                strategy_id = meta.get("strategy", "default_sandbox")
                market_features = {
                    k: meta.get(k)
                    for k in ("rsi", "adx", "atr", "macd_hist", "volume_ratio", "regime")
                    if meta.get(k) is not None
                }

                # Learning gate: ask orchestrator if we should trade this signal
                learning_confidence: Optional[float] = None
                if self._learning_loop and self._learning_loop.is_running():
                    orch_signal = {
                        "strategy_id": strategy_id,
                        "ticker": sig.asset,
                        "direction": "BUY" if direction == "long" else "SELL",
                        "market_regime": meta.get("regime"),
                        "market_features": market_features,
                        "is_sandbox": True,
                    }
                    decision = self._learning_loop.check_signal(orch_signal)
                    if not decision.get("approved", True):
                        logger.info(
                            "PaperEngine: learning BLOCKED %s — %s",
                            sig.asset, decision.get("reason"),
                        )
                        self._record_gate_rejection(
                            signal=sig,
                            strategy_id=strategy_id,
                            stage=_GateStage.LEARNING,
                            reason_code="learning_blocked",
                            reason_text=decision.get("reason") or "Заблокировано системой обучения",
                            confidence=decision.get("confidence"),
                            sample_size=decision.get("sample_size"),
                        )
                        self._push_sse("signal_rejected", {
                            "ticker": sig.asset,
                            "reason": decision.get("reason", "learning blocked"),
                            "signal_type": sig.signal_type,
                            "source": "learning",
                            "confidence": float(decision.get("confidence", 0)),
                        })
                        continue
                    learning_confidence = float(decision.get("confidence", 0.5))

                # Resolve actual market price to validate signal SL/TP are on the correct side.
                # Signals can be stale (generated at a different price), so SL/TP may be
                # inverted relative to the actual fill price.
                actual_price = self._get_market_price(sig.asset)
                sig_sl = float(sig.stop_loss) if sig.stop_loss else None
                sig_tp = float(sig.take_profit_1) if sig.take_profit_1 else None
                if actual_price:
                    if direction == "long":
                        if sig_sl and sig_sl >= actual_price:
                            sig_sl = None  # wrong side — let open_trade() compute from fill
                        if sig_tp and sig_tp <= actual_price:
                            sig_tp = None
                    else:  # short
                        if sig_sl and sig_sl <= actual_price:
                            sig_sl = None  # wrong side — let open_trade() compute from fill
                        if sig_tp and sig_tp >= actual_price:
                            sig_tp = None
                result = self.open_trade(
                    ticker=sig.asset,
                    direction=direction,
                    stop_loss=sig_sl,
                    take_profit=sig_tp,
                    exchange=getattr(sig, "exchange", "paper"),
                    signal_id=sig.id,
                    entry_reason=entry_reason,
                    probability_pct=sig.probability_pct,
                    strategy_id=strategy_id,
                    market_features=market_features,
                    learning_confidence=learning_confidence,
                )
                result["strategy"] = strategy_id

                executed += 1
                logger.info(
                    "PaperEngine: executed signal %s/%s — %s %s prob=%.1f%% conf=%s",
                    i + 1, len(top3), sig.signal_type, sig.asset, sig.probability_pct,
                    f"{learning_confidence:.2f}" if learning_confidence is not None else "n/a",
                )
                if i < len(top3) - 1:
                    for _ in range(60):
                        if self._stop_flag.is_set():
                            break
                        time.sleep(1)
            except ValueError as exc:
                logger.warning("PaperEngine: could not open position for %s: %s", sig.asset, exc)
            except Exception as exc:
                logger.error("PaperEngine: unexpected error for %s: %s", sig.asset, exc, exc_info=True)

        logger.info("PaperEngine: cycle done — %d executed / %d candidates", executed, len(top3))

    def _monitor_loop(self) -> None:
        logger.info("PaperEngine monitor_loop started")
        while not self._stop_flag.is_set():
            try:
                self._run_monitor_cycle()
            except Exception as exc:
                logger.error("PaperEngine monitor_loop error: %s", exc, exc_info=True)
            for _ in range(MONITOR_INTERVAL):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)
        logger.info("PaperEngine monitor_loop stopped")

    def _run_monitor_cycle(self) -> None:
        repo = self._get_repo()
        # Get default account
        try:
            account = repo.get_or_create_account()
        except Exception as exc:
            logger.debug("PaperEngine monitor: could not get account: %s", exc)
            return

        account_id = int(account["id"])
        positions = repo.list_positions(account_id)

        for pos in positions:
            if self._stop_flag.is_set():
                break
            try:
                self._check_position(pos)
            except Exception as exc:
                logger.warning("PaperEngine monitor: error checking pos %s: %s", pos.get("id"), exc)

    def _check_position(self, pos: dict) -> None:
        """Check SL/TP/trailing-stop for a single position."""
        repo = self._get_repo()
        pos_id = int(pos["id"])
        ticker = pos["ticker"]
        direction = (pos["direction"] or "long").lower()
        entry = float(pos["entry_price"])
        qty = float(pos["quantity"])

        price = self._get_market_price(ticker)
        if price is None:
            return

        sl = float(pos["stop_loss"]) if pos.get("stop_loss") else None
        tp = float(pos["take_profit"]) if pos.get("take_profit") else None
        trailing_pct = float(pos["trailing_stop_pct"]) if pos.get("trailing_stop_pct") else None

        # Update unrealized PnL in DB
        unrealized = (price - entry) * qty if direction == "long" else (entry - price) * qty
        repo.update_position_pnl(pos_id, unrealized)

        # Trailing stop: update SL if price moved favorably > 0.5%
        if trailing_pct is not None and sl is not None:
            if direction == "long":
                new_sl = price * (1 - trailing_pct)
                if new_sl > sl and (price - entry) / entry > 0.005:
                    try:
                        from sqlalchemy import text
                        with self._get_db_engine().begin() as conn:
                            conn.execute(
                                text("UPDATE paper_positions SET stop_loss = :sl WHERE id = :id"),
                                {"sl": round(new_sl, 4), "id": pos_id},
                            )
                        sl = new_sl
                        logger.debug("PaperEngine: trailing stop raised to %.4f for pos %s", sl, pos_id)
                    except Exception as exc:
                        logger.debug("Could not update trailing stop: %s", exc)
            else:
                new_sl = price * (1 + trailing_pct)
                if new_sl < sl and (entry - price) / entry > 0.005:
                    try:
                        from sqlalchemy import text
                        with self._get_db_engine().begin() as conn:
                            conn.execute(
                                text("UPDATE paper_positions SET stop_loss = :sl WHERE id = :id"),
                                {"sl": round(new_sl, 4), "id": pos_id},
                            )
                        sl = new_sl
                    except Exception as exc:
                        logger.debug("Could not update trailing stop: %s", exc)

        # Check SL hit
        if sl is not None:
            sl_hit = (direction == "long" and price <= sl) or (direction == "short" and price >= sl)
            if sl_hit:
                logger.info("PaperEngine: SL hit for pos %s (%s) price=%.4f sl=%.4f", pos_id, ticker, price, sl)
                self.close_trade(pos_id, reason="SL_HIT", exit_price=sl)
                return

        # Check TP hit
        if tp is not None:
            tp_hit = (direction == "long" and price >= tp) or (direction == "short" and price <= tp)
            if tp_hit:
                logger.info("PaperEngine: TP hit for pos %s (%s) price=%.4f tp=%.4f", pos_id, ticker, price, tp)
                self.close_trade(pos_id, reason="TP_HIT", exit_price=tp)
                return

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, db_engine=None) -> None:
        with self._lock:
            if self._running:
                logger.debug("PaperEngine: already running")
                return
            if db_engine is not None:
                self._db_engine = db_engine

            # Start learning loop first so it's ready before first signal cycle
            if self._learning_loop and not self._learning_loop.is_running():
                try:
                    self._learning_loop.start()
                    logger.info("PaperEngine: SandboxLearningLoop started")
                except Exception as exc:
                    logger.warning("PaperEngine: could not start learning loop: %s", exc)

            self._stop_flag.clear()
            self._signal_thread = threading.Thread(
                target=self._signal_loop,
                name="paper-engine-signals",
                daemon=True,
            )
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="paper-engine-monitor",
                daemon=True,
            )
            self._signal_thread.start()
            self._monitor_thread.start()
            self._running = True
            self._push_sse("engine_started", {
                "engine": "paper",
                "ts": datetime.utcnow().isoformat(),
                "learning": self._learning_loop is not None,
            })
            logger.info(
                "PaperEngine started (signal=%ds, monitor=%ds, learning=%s)",
                SIGNAL_INTERVAL, MONITOR_INTERVAL,
                self._learning_loop is not None,
            )

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                logger.debug("PaperEngine: not running")
                return
            self._stop_flag.set()
            for t in (self._signal_thread, self._monitor_thread):
                if t and t.is_alive():
                    t.join(timeout=10)
            self._running = False

            if self._learning_loop and self._learning_loop.is_running():
                try:
                    self._learning_loop.stop()
                except Exception:
                    pass

            self._push_sse("engine_stopped", {"engine": "paper", "ts": datetime.utcnow().isoformat()})
            logger.info("PaperEngine stopped")

    def set_db_engine(self, db_engine) -> None:
        """Inject a db engine without starting background threads (used by dashboard routes)."""
        if self._db_engine is None:
            self._db_engine = db_engine

    def set_learning_loop(self, learning_loop: "SandboxLearningLoop") -> None:
        """Attach an autonomous learning loop to this engine."""
        self._learning_loop = learning_loop

    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict:
        return {
            "running": self._running,
            "learning_active": (
                self._learning_loop is not None and self._learning_loop.is_running()
            ),
            "commission_pct": COMMISSION_PCT,
            "slippage_pct": SLIPPAGE_PCT,
            "monitor_interval": MONITOR_INTERVAL,
            "signal_interval": SIGNAL_INTERVAL,
        }


paper_engine = PaperEngine()
