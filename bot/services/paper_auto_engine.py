"""Paper Trading Auto-Engine — background thread that mirrors live signals into paper trades."""
from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Ensure bot/ is on sys.path when this module is imported standalone or via main.py
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

_CYCLE_INTERVAL = 90  # seconds


def _push_sse_notification(event_type: str, data: dict) -> None:
    """Synchronous HTTP POST to dashboard SSE endpoint (fire-and-forget)."""
    try:
        import os
        import requests
        from config import config
        url = f"http://127.0.0.1:{config.dashboard.port}/api/internal/push"
        token = os.getenv("QF_INTERNAL_TOKEN", "")
        headers = {"X-Internal-Token": token} if token else {}
        requests.post(url, json={"event_type": event_type, **data}, headers=headers, timeout=2)
    except Exception:
        pass  # dashboard may not be running


def _is_market_open() -> bool:
    """Return True during Moscow exchange trading hours (UTC 07:00–15:59)."""
    now = datetime.utcnow()
    return 7 <= now.hour < 16


class PaperAutoEngine:
    """
    Background thread that runs every 90 seconds while the trading engine is
    active.  Each cycle it generates live signals via SignalsService and
    executes the best one against the paper account via PaperTradingService.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._sqlalchemy_engine = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_db_engine(self):
        if self._sqlalchemy_engine is None:
            from sqlalchemy import create_engine
            from config import config
            self._sqlalchemy_engine = create_engine(
                config.db.dsn,
                pool_size=2,
                max_overflow=2,
                pool_pre_ping=True,
            )
        return self._sqlalchemy_engine

    def _run_cycle(self) -> None:
        """Execute one paper-trading cycle."""
        if not _is_market_open():
            logger.debug("PaperAutoEngine: market closed, skipping cycle")
            return

        db = self._get_db_engine()

        # 1. Generate live signals
        try:
            from qf_platform.services.signals_service import SignalsService
            signals = SignalsService(db).generate_live_signals(persist=True)
        except Exception as exc:
            logger.warning("PaperAutoEngine: signal generation failed: %s", exc)
            return

        if not signals:
            logger.debug("PaperAutoEngine: no signals this cycle")
            return

        # 2. Pick the best signal (highest probability_pct)
        best = max(signals, key=lambda s: s.probability_pct)
        logger.info(
            "PaperAutoEngine: best signal — %s %s prob=%.1f%%",
            best.signal_type, best.asset, best.probability_pct,
        )

        # 3. Execute paper trade
        try:
            from qf_platform.services.paper_trading_service import PaperTradingService
            result = PaperTradingService(db).execute_from_signal({
                "asset": best.asset,
                "signal_type": best.signal_type,
                "stop_loss": best.stop_loss,
                "take_profit_1": best.take_profit_1,
                "exchange": best.exchange,
            })
            logger.info(
                "PaperAutoEngine: paper trade opened — %s qty=%s @ %s",
                best.asset, result.get("quantity"), result.get("entry_price"),
            )
        except ValueError as exc:
            # Covers "insufficient funds" and "no market data"
            logger.warning("PaperAutoEngine: could not open position: %s", exc)
            return
        except Exception as exc:
            logger.error(
                "PaperAutoEngine: unexpected error opening position: %s", exc, exc_info=True
            )
            return

        # 4. Push SSE notification to dashboard
        _push_sse_notification("paper_trade_executed", {
            "action": best.signal_type,
            "ticker": best.asset,
            "entry_price": result.get("entry_price"),
            "quantity": result.get("quantity"),
            "probability_pct": best.probability_pct,
            "source": "paper_auto_engine",
        })

    def _loop(self) -> None:
        from services.bot_engine import trading_engine
        logger.info("PaperAutoEngine thread started")
        while not self._stop_flag.is_set():
            if trading_engine.is_running():
                try:
                    self._run_cycle()
                except Exception as exc:
                    logger.error("PaperAutoEngine loop error: %s", exc, exc_info=True)
            # Sleep in 1-second increments so stop() is responsive
            for _ in range(_CYCLE_INTERVAL):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)
        logger.info("PaperAutoEngine thread stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        # Delegate to unified PaperEngine
        try:
            from engine.paper_engine import paper_engine
            paper_engine.start()
            return
        except Exception:
            pass
        # Legacy fallback
        if self._thread and self._thread.is_alive():
            logger.debug("PaperAutoEngine: already running, skipping start")
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="paper-auto-engine",
            daemon=True,
        )
        self._thread.start()
        logger.info("PaperAutoEngine started (legacy mode)")

    def stop(self) -> None:
        # Delegate to unified PaperEngine
        try:
            from engine.paper_engine import paper_engine
            paper_engine.stop()
            return
        except Exception:
            pass
        # Legacy fallback
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("PaperAutoEngine stopped (legacy mode)")


paper_auto_engine = PaperAutoEngine()
