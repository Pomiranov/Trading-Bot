"""Bybit broker client via pybit unified trading SDK."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

try:
    from pybit.unified_trading import HTTP
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("pybit не установлен. Установите: pip install pybit")


class BybitClient:
    """
    Обёртка над Bybit Unified Trading API (pybit v5).

    Поддерживает testnet и mainnet через config.bybit.testnet.
    """

    def __init__(self):
        self.cfg = config.bybit

    def _session(self) -> "HTTP":
        if not SDK_AVAILABLE:
            raise RuntimeError("pybit не установлен")
        if not self.cfg.api_key or not self.cfg.api_secret:
            raise ValueError("BYBIT_API_KEY / BYBIT_API_SECRET не настроены в .env")
        return HTTP(
            testnet=self.cfg.testnet,
            api_key=self.cfg.api_key,
            api_secret=self.cfg.api_secret,
        )

    # ─── Аккаунт ─────────────────────────────────────────────────

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> dict:
        """Получить баланс кошелька. account_type: UNIFIED, SPOT, CONTRACT."""
        try:
            session = self._session()
            resp = session.get_wallet_balance(accountType=account_type)
            if resp.get("retCode") != 0:
                logger.error("Bybit balance error: %s", resp.get("retMsg"))
                return {}
            coins = []
            for item in resp["result"]["list"]:
                for coin in item.get("coin", []):
                    coins.append({
                        "coin": coin["coin"],
                        "wallet_balance": float(coin.get("walletBalance", 0)),
                        "available": float(coin.get("availableToWithdraw", 0)),
                        "unrealized_pnl": float(coin.get("unrealisedPnl", 0)),
                    })
            return {"account_type": account_type, "coins": coins}
        except Exception as exc:
            logger.error("Ошибка получения баланса Bybit: %s", exc)
            return {}

    def get_positions(self, category: str = "linear", settle_coin: str = "USDT") -> list[dict]:
        """Получить открытые позиции (фьючерсы)."""
        try:
            session = self._session()
            resp = session.get_positions(category=category, settleCoin=settle_coin)
            if resp.get("retCode") != 0:
                logger.error("Bybit positions error: %s", resp.get("retMsg"))
                return []
            positions = []
            for p in resp["result"]["list"]:
                if float(p.get("size", 0)) == 0:
                    continue
                positions.append({
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "size": float(p["size"]),
                    "entry_price": float(p.get("avgPrice", 0)),
                    "mark_price": float(p.get("markPrice", 0)),
                    "unrealized_pnl": float(p.get("unrealisedPnl", 0)),
                    "leverage": p.get("leverage"),
                })
            return positions
        except Exception as exc:
            logger.error("Ошибка получения позиций Bybit: %s", exc)
            return []

    # ─── Инструменты ─────────────────────────────────────────────

    def get_ticker(self, symbol: str, category: str = "spot") -> Optional[dict]:
        """Получить текущую цену по символу."""
        try:
            session = self._session()
            resp = session.get_tickers(category=category, symbol=symbol)
            if resp.get("retCode") != 0:
                return None
            items = resp["result"]["list"]
            if not items:
                return None
            t = items[0]
            return {
                "symbol": t["symbol"],
                "last_price": float(t.get("lastPrice", 0)),
                "bid": float(t.get("bid1Price", 0)),
                "ask": float(t.get("ask1Price", 0)),
                "volume_24h": float(t.get("volume24h", 0)),
                "price_change_pct": float(t.get("price24hPcnt", 0)) * 100,
            }
        except Exception as exc:
            logger.error("Ошибка получения тикера %s: %s", symbol, exc)
            return None

    # ─── Ордера ──────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        category: str = "spot",
    ) -> Optional[str]:
        """
        Выставить рыночную заявку.

        side: 'Buy' или 'Sell'
        Возвращает orderId или None при ошибке.
        """
        try:
            session = self._session()
            resp = session.place_order(
                category=category,
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
            )
            if resp.get("retCode") != 0:
                logger.error("Bybit order error: %s", resp.get("retMsg"))
                return None
            order_id = resp["result"]["orderId"]
            logger.info("Bybit %s %s qty=%s order_id=%s", side, symbol, qty, order_id)
            return order_id
        except Exception as exc:
            logger.error("Ошибка выставления ордера Bybit: %s", exc)
            return None

    def cancel_order(self, symbol: str, order_id: str, category: str = "spot") -> bool:
        """Отменить ордер."""
        try:
            session = self._session()
            resp = session.cancel_order(
                category=category,
                symbol=symbol,
                orderId=order_id,
            )
            return resp.get("retCode") == 0
        except Exception as exc:
            logger.error("Ошибка отмены ордера Bybit %s: %s", order_id, exc)
            return False

    def get_order_history(self, symbol: str = "", category: str = "spot", limit: int = 20) -> list[dict]:
        """История ордеров."""
        try:
            session = self._session()
            kwargs = {"category": category, "limit": limit}
            if symbol:
                kwargs["symbol"] = symbol
            resp = session.get_order_history(**kwargs)
            if resp.get("retCode") != 0:
                return []
            return [
                {
                    "order_id": o["orderId"],
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "qty": float(o.get("qty", 0)),
                    "price": float(o.get("price", 0)) if o.get("price") else None,
                    "status": o["orderStatus"],
                    "created_time": o.get("createdTime"),
                }
                for o in resp["result"]["list"]
            ]
        except Exception as exc:
            logger.error("Ошибка получения истории ордеров: %s", exc)
            return []

    def ping(self) -> bool:
        """Проверить подключение (публичный endpoint, без авторизации)."""
        try:
            from pybit.unified_trading import HTTP as _HTTP
            session = _HTTP(testnet=self.cfg.testnet)
            resp = session.get_server_time()
            return resp.get("retCode") == 0
        except Exception as exc:
            logger.error("Bybit ping failed: %s", exc)
            return False


bybit_client = BybitClient()
