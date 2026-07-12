"""Unified trade execution gateway with mandatory risk checks."""
from __future__ import annotations

import logging
import os
from typing import Optional

from broker.base import BrokerOrder, OrderDirection, OrderType
from broker.registry import broker_registry
from risk.risk_manager import PositionSizing, risk_manager

logger = logging.getLogger(__name__)

_MAX_MANUAL_LOTS = int(os.getenv("RISK_MAX_MANUAL_LOTS", "50"))


class TradeGateway:
    """
    Single entry point for placing orders from Telegram, Web API, and services.

    All paths must pass risk validation before the broker adapter is called.
    """

    async def _portfolio_balance_rub(self, broker_id: str) -> float:
        adapter = broker_registry.get(broker_id)
        balances = await adapter.get_balance()
        total = 0.0
        for bal in balances:
            currency = (bal.currency or "").lower()
            if currency in ("rub", "rur"):
                total += float(bal.available or 0)
        return total

    def _validate_quantity(self, quantity: int) -> Optional[str]:
        if quantity <= 0:
            return "Количество лотов должно быть положительным"
        if quantity > _MAX_MANUAL_LOTS:
            return f"Превышен лимит лотов на заявку ({_MAX_MANUAL_LOTS})"
        return None

    async def _validate_risk(
        self,
        broker_id: str,
        ticker: str,
        direction: OrderDirection,
        quantity: int,
        entry_price: Optional[float],
        atr: Optional[float],
        lot_size: int,
    ) -> Optional[str]:
        qty_error = self._validate_quantity(quantity)
        if qty_error:
            return qty_error

        try:
            balance = await self._portfolio_balance_rub(broker_id)
        except Exception as exc:
            logger.error("Risk check: balance fetch failed: %s", exc)
            return "Не удалось получить баланс для проверки риска"

        position: Optional[PositionSizing] = None

        if direction == OrderDirection.BUY:
            if entry_price and atr and entry_price > 0 and atr > 0:
                position = risk_manager.calculate_position(
                    ticker=ticker,
                    entry_price=entry_price,
                    atr=atr,
                    portfolio_value=balance,
                    lot_size=max(lot_size, 1),
                    direction="long",
                )
                if position is None:
                    return "Не удалось рассчитать размер позиции"
                if position.lot_size < quantity:
                    return (
                        f"Запрошено {quantity} лотов, "
                        f"риск-менеджмент разрешает максимум {position.lot_size}"
                    )
            check = risk_manager.check_trade_allowed(
                ticker, balance, position, direction="buy"
            )
            if not check.allowed:
                return check.reason

        elif direction == OrderDirection.SELL:
            check = risk_manager.check_trade_allowed(
                ticker, balance, None, direction="sell"
            )
            if not check.allowed:
                return check.reason

        return None

    async def execute(
        self,
        broker_id: str,
        ticker: str,
        figi: str,
        direction: OrderDirection,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        entry_price: Optional[float] = None,
        atr: Optional[float] = None,
        lot_size: int = 1,
    ) -> tuple[bool, Optional[BrokerOrder], Optional[str]]:
        risk_error = await self._validate_risk(
            broker_id=broker_id,
            ticker=ticker,
            direction=direction,
            quantity=quantity,
            entry_price=entry_price,
            atr=atr,
            lot_size=lot_size,
        )
        if risk_error:
            logger.info("Trade blocked by gateway: %s %s — %s", direction.value, ticker, risk_error)
            return False, None, risk_error

        adapter = broker_registry.get(broker_id)
        if not adapter.supports_trading():
            return False, None, f"Брокер {adapter.broker_name} не поддерживает торговые операции"

        try:
            if order_type == OrderType.LIMIT and price is not None:
                order = await adapter.place_limit_order(
                    figi=figi,
                    quantity=quantity,
                    price=price,
                    direction=direction,
                )
            else:
                order = await adapter.place_market_order(
                    figi=figi,
                    quantity=quantity,
                    direction=direction,
                )
            logger.info(
                "Gateway order placed: broker=%s ticker=%s dir=%s qty=%d order_id=%s",
                broker_id, ticker, direction.value, quantity, order.order_id,
            )

            if direction == OrderDirection.BUY and entry_price and atr:
                pos = risk_manager.calculate_position(
                    ticker=ticker,
                    entry_price=entry_price,
                    atr=atr,
                    portfolio_value=await self._portfolio_balance_rub(broker_id),
                    lot_size=max(lot_size, 1),
                    direction="long",
                )
                if pos is not None:
                    pos.lot_size = quantity
                    pos.shares = quantity * max(lot_size, 1)
                    risk_manager.register_open(pos)

            return True, order, None
        except Exception as exc:
            logger.error("Gateway order failed: %s", exc)
            return False, None, str(exc)


trade_gateway = TradeGateway()