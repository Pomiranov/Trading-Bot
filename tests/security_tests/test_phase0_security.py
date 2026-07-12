"""Phase 0 security regression tests."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# bot/ on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bot"))

from config import AppConfig, DashboardConfig, TelegramConfig
from broker.base import OrderDirection
from gateway.trade_gateway import TradeGateway
from risk.risk_manager import RiskManager
from tg.middlewares.auth import is_authorized, resolve_chat_id

try:
    from flask import Flask
    from security.dashboard_auth import register_dashboard_security
    _FLASK_IMPORT_ERROR = None
except ImportError as exc:
    register_dashboard_security = None  # type: ignore
    Flask = None  # type: ignore
    _FLASK_IMPORT_ERROR = exc


class _UpdateStub:
    def __init__(self, chat_id: int | None):
        self.effective_chat = MagicMock(id=chat_id) if chat_id is not None else None
        self.effective_user = None
        self.effective_message = None
        self.callback_query = None


class TelegramAuthTests(unittest.TestCase):
    def test_fail_closed_when_whitelist_empty(self):
        cfg = AppConfig(telegram=TelegramConfig(token="x", chat_id="", allowed_chat_ids=[]))
        with patch("tg.middlewares.auth.config", cfg):
            self.assertFalse(is_authorized(_UpdateStub(12345)))

    def test_allows_configured_chat_id(self):
        cfg = AppConfig(telegram=TelegramConfig(token="x", chat_id="42", allowed_chat_ids=[]))
        with patch("tg.middlewares.auth.config", cfg):
            self.assertTrue(is_authorized(_UpdateStub(42)))
            self.assertFalse(is_authorized(_UpdateStub(99)))

    def test_resolve_chat_id_from_chat(self):
        upd = _UpdateStub(100)
        self.assertEqual(resolve_chat_id(upd), 100)


class RiskManagerDirectionTests(unittest.TestCase):
    def test_sell_allowed_when_position_open(self):
        rm = RiskManager()
        rm._open_positions["SBER"] = MagicMock()
        rm._daily_pnl = 0.0
        result = rm.check_trade_allowed("SBER", 1_000_000, direction="sell")
        self.assertTrue(result.allowed)

    def test_buy_blocked_when_position_open(self):
        rm = RiskManager()
        rm._open_positions["SBER"] = MagicMock()
        result = rm.check_trade_allowed("SBER", 1_000_000, direction="buy")
        self.assertFalse(result.allowed)


class TradeGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocks_excessive_lot_count(self):
        gw = TradeGateway()
        with patch.object(gw, "_portfolio_balance_rub", AsyncMock(return_value=1_000_000)):
            ok, _, err = await gw.execute(
                broker_id="tinkoff",
                ticker="SBER",
                figi="BBG001",
                direction=OrderDirection.BUY,
                quantity=10_000,
            )
        self.assertFalse(ok)
        self.assertIn("лимит", (err or "").lower())


class DashboardAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _FLASK_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Flask unavailable: {_FLASK_IMPORT_ERROR}")

    def setUp(self):
        self.app = Flask(__name__)
        register_dashboard_security(self.app)
        self.client = self.app.test_client()

    def test_health_is_public(self):
        @self.app.route("/health")
        def health():
            return {"status": "ok"}

        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_post_tokens_denied_from_remote_without_key(self):
        cfg = AppConfig(dashboard=DashboardConfig(api_key="secret-key"))
        with patch("security.dashboard_auth.config", cfg):
            resp = self.client.post(
                "/api/settings/tokens",
                json={"key": "TINKOFF_TOKEN", "value": "t.test"},
                environ_overrides={"REMOTE_ADDR": "203.0.113.50"},
            )
        self.assertEqual(resp.status_code, 401)

    def test_post_tokens_allowed_from_localhost(self):
        cfg = AppConfig(dashboard=DashboardConfig(api_key="secret-key"))
        with patch("security.dashboard_auth.config", cfg):
            resp = self.client.post(
                "/api/settings/tokens",
                json={"key": "TINKOFF_TOKEN", "value": "t.test"},
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
        self.assertNotEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()