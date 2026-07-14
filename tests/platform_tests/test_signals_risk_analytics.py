"""Unit tests for SignalsService, RiskManager, and AnalyticsService."""

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_BOT = Path(__file__).resolve().parents[2] / "bot"
sys.path.insert(0, str(_BOT))


# ─────────────────────────────────────────────────────────────────────────────
# SignalsService — classify_regime, detect_strategy, build_entry_reason
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalsServiceHelpers(unittest.TestCase):
    def setUp(self):
        from qf_platform.services.signals_service import SignalsService
        engine = MagicMock()
        with patch("qf_platform.services.signals_service.SignalsRepository"), \
             patch("qf_platform.services.signals_service.IndicatorEngine"), \
             patch("qf_platform.services.signals_service.RulesEngine"):
            self.svc = SignalsService(engine)

    # _classify_regime
    def test_classify_regime_trending(self):
        self.assertEqual(self.svc._classify_regime(30), "trending")

    def test_classify_regime_ranging(self):
        self.assertEqual(self.svc._classify_regime(15), "ranging")

    def test_classify_regime_volatile(self):
        self.assertEqual(self.svc._classify_regime(22), "volatile")

    def test_classify_regime_nan(self):
        self.assertEqual(self.svc._classify_regime(math.nan), "unknown")

    def test_classify_regime_none(self):
        self.assertEqual(self.svc._classify_regime(None), "unknown")

    # _detect_strategy
    def _make_triggered(self, names):
        rules = []
        for name in names:
            r = MagicMock()
            r.name = name
            rules.append(r)
        return rules

    def _make_signal(self, rule_names):
        sig = MagicMock()
        sig.triggered_rules = self._make_triggered(rule_names)
        return sig

    def test_detect_strategy_macd_rsi(self):
        sig = self._make_signal(["MACD_Crossover", "RSI_Oversold"])
        self.assertEqual(self.svc._detect_strategy(sig), "MACD+RSI Momentum")

    def test_detect_strategy_ema_trend(self):
        sig = self._make_signal(["EMA_Bearish_Cross"])
        self.assertEqual(self.svc._detect_strategy(sig), "EMA Trend Follow")

    def test_detect_strategy_bollinger(self):
        sig = self._make_signal(["BB_Squeeze"])
        self.assertEqual(self.svc._detect_strategy(sig), "Bollinger Reversal")

    def test_detect_strategy_adx(self):
        sig = self._make_signal(["ADX_Breakout"])
        self.assertEqual(self.svc._detect_strategy(sig), "ADX Breakout")

    def test_detect_strategy_macd_only(self):
        sig = self._make_signal(["MACD_Signal"])
        self.assertEqual(self.svc._detect_strategy(sig), "MACD Signal")

    def test_detect_strategy_rsi_only(self):
        sig = self._make_signal(["RSI_Oversold"])
        self.assertEqual(self.svc._detect_strategy(sig), "RSI Oscillator")

    def test_detect_strategy_fallback(self):
        sig = self._make_signal(["VWAP_Resistance_Sell"])
        self.assertEqual(self.svc._detect_strategy(sig), "Multi-Factor Rules")

    # _build_entry_reason
    def test_build_entry_reason_oversold(self):
        sig = self._make_signal(["RSI_Oversold"])
        iv = MagicMock()
        iv.rsi = 25.0
        iv.adx = 30.0
        iv.macd_hist = 0.1
        reason = self.svc._build_entry_reason(sig, iv)
        self.assertIn("RSI перепродан", reason)
        self.assertIn("Сильный тренд", reason)

    def test_build_entry_reason_overbought(self):
        sig = self._make_signal(["RSI_Overbought"])
        iv = MagicMock()
        iv.rsi = 75.0
        iv.adx = 15.0
        iv.macd_hist = -0.2
        reason = self.svc._build_entry_reason(sig, iv)
        self.assertIn("RSI перекуплен", reason)
        self.assertIn("медвежий", reason)

    def test_build_entry_reason_no_indicators(self):
        sig = self._make_signal([])
        iv = MagicMock()
        iv.rsi = None
        iv.adx = None
        iv.macd_hist = None
        reason = self.svc._build_entry_reason(sig, iv)
        self.assertEqual(reason, "Технические индикаторы")

    def test_build_entry_reason_nan_indicators(self):
        sig = self._make_signal([])
        iv = MagicMock()
        iv.rsi = math.nan
        iv.adx = math.nan
        iv.macd_hist = math.nan
        reason = self.svc._build_entry_reason(sig, iv)
        self.assertEqual(reason, "Технические индикаторы")

    # _compute_levels
    def test_compute_levels_long(self):
        levels = self.svc._compute_levels(100.0, 2.0, "BUY")
        self.assertAlmostEqual(levels["stop_loss"], 96.0)
        self.assertAlmostEqual(levels["take_profit_1"], 104.0)
        self.assertGreater(levels["risk_reward"], 0)

    def test_compute_levels_short(self):
        levels = self.svc._compute_levels(100.0, 2.0, "SELL")
        self.assertAlmostEqual(levels["stop_loss"], 104.0)
        self.assertAlmostEqual(levels["take_profit_1"], 96.0)

    # _parse_metadata
    def test_parse_metadata_dict(self):
        result = self.svc._parse_metadata({"k": "v"})
        self.assertEqual(result, {"k": "v"})

    def test_parse_metadata_json_string(self):
        result = self.svc._parse_metadata('{"k": 1}')
        self.assertEqual(result, {"k": 1})

    def test_parse_metadata_bad_string(self):
        result = self.svc._parse_metadata("not json")
        self.assertEqual(result, {})

    def test_parse_metadata_none(self):
        result = self.svc._parse_metadata(None)
        self.assertEqual(result, {})


# ─────────────────────────────────────────────────────────────────────────────
# RiskManager
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        from risk.risk_manager import RiskManager, PositionSizing
        self.PositionSizing = PositionSizing
        self.rm = RiskManager()

    def _make_position(self, ticker="SBER", entry=100.0, stop=95.0, value=50000.0):
        return self.PositionSizing(
            ticker=ticker,
            entry_price=entry,
            stop_price=stop,
            lot_size=1,
            shares=500,
            risk_amount=2500.0,
            position_value=value,
        )

    def test_check_allowed_when_empty(self):
        result = self.rm.check_trade_allowed("SBER", portfolio_value=1_000_000)
        self.assertTrue(result.allowed)

    def test_check_blocked_max_positions(self):
        for i in range(5):
            pos = self._make_position(ticker=f"TICK{i}")
            self.rm.register_open(pos)
        result = self.rm.check_trade_allowed("NEWT", portfolio_value=1_000_000)
        self.assertFalse(result.allowed)
        self.assertIn("лимит", result.reason)

    def test_check_blocked_duplicate_ticker(self):
        pos = self._make_position("SBER")
        self.rm.register_open(pos)
        result = self.rm.check_trade_allowed("SBER", portfolio_value=1_000_000)
        self.assertFalse(result.allowed)
        self.assertIn("SBER", result.reason)

    def test_check_blocked_daily_loss_limit(self):
        self.rm._daily_pnl = -25000.0
        result = self.rm.check_trade_allowed("GAZP", portfolio_value=1_000_000)
        self.assertFalse(result.allowed)
        self.assertIn("дневной лимит", result.reason)

    def test_register_open_and_close_pnl(self):
        pos = self._make_position("LKOH", entry=100.0, stop=95.0)
        self.rm.register_open(pos)
        self.assertIn("LKOH", self.rm.open_positions)
        pnl = self.rm.register_close("LKOH", exit_price=110.0)
        self.assertAlmostEqual(pnl, 5000.0)
        self.assertNotIn("LKOH", self.rm.open_positions)

    def test_register_close_updates_daily_pnl(self):
        pos = self._make_position("YNDX", entry=200.0, stop=190.0)
        self.rm.register_open(pos)
        self.rm.register_close("YNDX", exit_price=190.0)
        self.assertLess(self.rm.daily_pnl, 0)

    def test_reset_daily(self):
        self.rm._daily_pnl = -9999.0
        self.rm.reset_daily()
        self.assertEqual(self.rm.daily_pnl, 0.0)

    def test_calculate_position_sizing(self):
        ps = self.rm.calculate_position(
            ticker="SBER",
            entry_price=300.0,
            atr=5.0,
            portfolio_value=1_000_000,
            lot_size=10,
        )
        self.assertIsNotNone(ps)
        self.assertGreater(ps.shares, 0)
        self.assertGreater(ps.position_value, 0)
        self.assertAlmostEqual(ps.stop_price, 300.0 - 5.0 * 2.0, places=1)

    def test_trailing_stop_long(self):
        pos = self._make_position("SBER", entry=100.0, stop=95.0)
        original_stop = pos.stop_price
        self.rm.register_open(pos)
        stop = self.rm.trailing_stop(
            ticker="SBER",
            current_price=120.0,
            atr=5.0,
        )
        self.assertIsNotNone(stop)
        self.assertGreater(stop, original_stop)


# ─────────────────────────────────────────────────────────────────────────────
# AnalyticsService.trade_stats (via mocked DB)
# ─────────────────────────────────────────────────────────────────────────────

def _trade_row(pnl):
    return {"pnl": pnl, "pnl_pct": pnl / 10000, "opened_at": None, "closed_at": None}


def _make_query_side_effect(trades):
    """side_effect: first call returns trades, second call returns account row."""
    account_row = [{"initial_balance": 1_000_000.0, "balance": 1_010_000.0}]
    results = iter([trades, account_row])
    return lambda *a, **kw: next(results)


class TestAnalyticsService(unittest.TestCase):
    def test_trade_stats_no_trades(self):
        from qf_platform.services.analytics_service import AnalyticsService
        svc = AnalyticsService(MagicMock())
        with patch.object(svc, "_get_account_id", return_value=None):
            stats = svc.trade_stats()
        self.assertEqual(stats["total_trades"], 0)
        self.assertEqual(stats["win_rate"], 0.0)

    def test_trade_stats_with_mock_data(self):
        from qf_platform.services.analytics_service import AnalyticsService
        svc = AnalyticsService(MagicMock())
        fake_trades = [_trade_row(1000), _trade_row(500), _trade_row(-300), _trade_row(200)]
        with patch.object(svc, "_get_account_id", return_value=1), \
             patch.object(svc, "_query", side_effect=_make_query_side_effect(fake_trades)), \
             patch.object(svc, "_compute_sharpe", return_value=1.5), \
             patch.object(svc, "_compute_sortino", return_value=2.0), \
             patch.object(svc, "_compute_max_drawdown", return_value=0.05):
            stats = svc.trade_stats()
        self.assertEqual(stats["total_trades"], 4)
        self.assertAlmostEqual(stats["win_rate"], 75.0, places=2)
        self.assertAlmostEqual(stats["total_pnl"], 1400.0, places=2)
        self.assertAlmostEqual(stats["avg_win"], (1000 + 500 + 200) / 3, places=2)
        self.assertAlmostEqual(stats["avg_loss"], -300.0, places=2)

    def test_trade_stats_all_wins(self):
        from qf_platform.services.analytics_service import AnalyticsService
        svc = AnalyticsService(MagicMock())
        fake_trades = [_trade_row(500), _trade_row(800)]
        with patch.object(svc, "_get_account_id", return_value=1), \
             patch.object(svc, "_query", side_effect=_make_query_side_effect(fake_trades)), \
             patch.object(svc, "_compute_sharpe", return_value=0.0), \
             patch.object(svc, "_compute_sortino", return_value=0.0), \
             patch.object(svc, "_compute_max_drawdown", return_value=0.0):
            stats = svc.trade_stats()
        self.assertAlmostEqual(stats["win_rate"], 100.0, places=1)

    def test_trade_stats_all_losses(self):
        from qf_platform.services.analytics_service import AnalyticsService
        svc = AnalyticsService(MagicMock())
        fake_trades = [_trade_row(-200), _trade_row(-400)]
        with patch.object(svc, "_get_account_id", return_value=1), \
             patch.object(svc, "_query", side_effect=_make_query_side_effect(fake_trades)), \
             patch.object(svc, "_compute_sharpe", return_value=0.0), \
             patch.object(svc, "_compute_sortino", return_value=0.0), \
             patch.object(svc, "_compute_max_drawdown", return_value=0.0):
            stats = svc.trade_stats()
        self.assertAlmostEqual(stats["win_rate"], 0.0, places=1)
        self.assertLess(stats["total_pnl"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
