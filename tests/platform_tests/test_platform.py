"""Unit tests for QuantFlow platform layer."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

_BOT = Path(__file__).resolve().parents[2] / "bot"
sys.path.insert(0, str(_BOT))

from backtest.advanced_engine import AdvancedBacktestEngine
from qf_platform.dto import BacktestRequestDTO, PortfolioSummaryDTO, to_dict
from realtime.sse_hub import SSEHub


class TestDTO(unittest.TestCase):
    def test_to_dict_portfolio(self):
        dto = PortfolioSummaryDTO(
            total_balance=1_000_000,
            available_funds=900_000,
            margin_used=100_000,
            total_pnl=50_000,
            pnl_day=1000,
            pnl_week=5000,
            pnl_month=20_000,
            unrealized_pnl=10_000,
            realized_pnl=40_000,
            return_pct=5.0,
            roi=5.0,
            open_positions_count=3,
            closed_trades_count=10,
            avg_risk_pct=5.0,
            avg_rr=2.0,
            avg_profit_pct=1.5,
            currency="RUB",
            source="paper",
        )
        d = to_dict(dto)
        self.assertEqual(d["total_balance"], 1_000_000)
        self.assertEqual(d["source"], "paper")


class TestSSEHub(unittest.TestCase):
    def test_publish_subscribe(self):
        hub = SSEHub()
        q = hub.subscribe()
        hub.publish("test_event", {"value": 42})
        payload = q.get(timeout=1)
        self.assertEqual(payload["type"], "test_event")
        self.assertEqual(payload["data"]["value"], 42)
        hub.unsubscribe(q)


class TestAdvancedBacktest(unittest.TestCase):
    def _make_df(self, n: int = 80) -> pd.DataFrame:
        import numpy as np
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        return pd.DataFrame({
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.random.randint(1000, 10000, n),
        }, index=dates)

    def test_run_advanced_returns_metrics(self):
        engine = AdvancedBacktestEngine(initial_capital=1_000_000)
        df = self._make_df()
        with patch.object(engine, "_indicators") as mock_ind:
            mock_ind.compute.return_value = df
            mock_iv = MagicMock()
            mock_iv.rsi = 50
            mock_iv.macd_hist = 0.1
            mock_iv.adx = 30
            mock_iv.atr = 2.0
            mock_iv.bb_pct = 0.5
            mock_ind.latest.return_value = mock_iv
            with patch.object(engine._rules, "evaluate") as mock_eval:
                from signals.rules_engine import Action, SignalResult
                mock_eval.return_value = SignalResult(action=Action.HOLD, score=0)
                result = engine.run_advanced("TEST", df)
        self.assertEqual(result.ticker, "TEST")
        self.assertIsInstance(result.equity_curve, list)


class TestBacktestRequestDTO(unittest.TestCase):
    def test_defaults(self):
        req = BacktestRequestDTO()
        self.assertEqual(req.ticker, "SBER")
        self.assertEqual(req.initial_capital, 1_000_000)


if __name__ == "__main__":
    unittest.main()