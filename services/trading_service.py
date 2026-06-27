"""Trading service — order execution with risk checks and trade logging."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from broker.base import BrokerOrder, OrderDirection, OrderType
from broker.registry import broker_registry
from risk.risk_manager import risk_manager

logger = logging.getLogger(__name__)


@dataclass
class TradeRequest:
    broker_id: str
    ticker: str
    figi: str
    direction: OrderDirection
    quantity: int
    price: Optional[float] = None
    order_type: OrderType = OrderType.MARKET


@dataclass
class TradeResult:
    success: bool
    order: Optional[BrokerOrder] = None
    error: Optional[str] = None

    @property
    def order_id(self) -> Optional[str]:
        return self.order.order_id if self.order else None


async def execute_trade(req: TradeRequest) -> TradeResult:
    adapter = broker_registry.get(req.broker_id)

    if not adapter.supports_trading():
        return TradeResult(
            success=False,
            error=f"Брокер {adapter.broker_name} не поддерживает торговые операции",
        )

    try:
        if req.order_type == OrderType.LIMIT and req.price is not None:
            order = await adapter.place_limit_order(
                figi=req.figi,
                quantity=req.quantity,
                price=req.price,
                direction=req.direction,
            )
        else:
            order = await adapter.place_market_order(
                figi=req.figi,
                quantity=req.quantity,
                direction=req.direction,
            )
        logger.info(
            "Order placed: broker=%s ticker=%s dir=%s qty=%d order_id=%s",
            req.broker_id, req.ticker, req.direction.value, req.quantity, order.order_id,
        )
        return TradeResult(success=True, order=order)
    except Exception as exc:
        logger.error("Order failed: %s", exc)
        return TradeResult(success=False, error=str(exc))


async def cancel_order(broker_id: str, order_id: str) -> TradeResult:
    adapter = broker_registry.get(broker_id)
    try:
        ok = await adapter.cancel_order(order_id)
        if ok:
            return TradeResult(success=True)
        return TradeResult(success=False, error="Не удалось отменить заявку")
    except Exception as exc:
        return TradeResult(success=False, error=str(exc))


async def resolve_instrument(broker_id: str, ticker: str) -> Optional[dict]:
    adapter = broker_registry.get(broker_id)
    return await adapter.find_instrument(ticker)


def get_risk_summary() -> dict:
    return {
        "open_positions": len(risk_manager.open_positions),
        "max_open_positions": risk_manager.cfg.max_open_positions,
        "daily_pnl": risk_manager.daily_pnl,
        "max_daily_loss_pct": risk_manager.cfg.max_daily_loss_pct,
        "positions": {
            ticker: {
                "entry_price": pos.entry_price,
                "stop_price": pos.stop_price,
                "lot_size": pos.lot_size,
                "position_value": pos.position_value,
            }
            for ticker, pos in risk_manager.open_positions.items()
        },
    }
