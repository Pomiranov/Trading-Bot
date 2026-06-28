"""Tinkoff Invest broker adapter — wraps services/tinkoff service layer."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from broker.base import (
    BrokerAdapter,
    BrokerBalance,
    BrokerConnectionError,
    BrokerInfo,
    BrokerNotConfigured,
    BrokerOperation,
    BrokerOrder,
    BrokerPortfolio,
    BrokerPosition,
    OperationType,
    OrderDirection,
    OrderStatus,
    OrderType,
)
from config import config
from services.tinkoff.client import (
    TinkoffAPIError,
    TinkoffNotConfigured,
    TinkoffSDKError,
    build_client,
    require_account_id,
)
from services.tinkoff.mapper import money_value_to_float, money_value_currency, quotation_to_float
from services.tinkoff.portfolio import get_portfolio_summary

logger = logging.getLogger(__name__)

_OPERATION_TYPE_MAP: dict[str, OperationType] = {
    "OPERATION_TYPE_BUY": OperationType.BUY,
    "OPERATION_TYPE_BUY_CARD": OperationType.BUY,
    "OPERATION_TYPE_SELL": OperationType.SELL,
    "OPERATION_TYPE_SELL_CARD": OperationType.SELL,
    "OPERATION_TYPE_DIVIDEND": OperationType.DIVIDEND,
    "OPERATION_TYPE_DIVIDEND_TAX": OperationType.TAX,
    "OPERATION_TYPE_COUPON": OperationType.COUPON,
    "OPERATION_TYPE_INPUT": OperationType.DEPOSIT,
    "OPERATION_TYPE_OUTPUT": OperationType.WITHDRAWAL,
    "OPERATION_TYPE_BROKER_FEE": OperationType.COMMISSION,
    "OPERATION_TYPE_MARGIN_FEE": OperationType.COMMISSION,
    "OPERATION_TYPE_TAX": OperationType.TAX,
    "OPERATION_TYPE_BOND_TAX": OperationType.TAX,
    "OPERATION_TYPE_BENEFIT_TAX": OperationType.TAX,
    "OPERATION_TYPE_WRITING_OFF_VARMARGIN": OperationType.OTHER,
    "OPERATION_TYPE_ACCRUING_VARMARGIN": OperationType.OTHER,
    "OPERATION_TYPE_CASH_FEE": OperationType.COMMISSION,
    "OPERATION_TYPE_OUT_FEE": OperationType.COMMISSION,
    "OPERATION_TYPE_OUT_STAMP_DUTY": OperationType.COMMISSION,
    "OPERATION_TYPE_OVERNIGHT": OperationType.OTHER,
    "OPERATION_TYPE_TRACK_DEFAULT": OperationType.OTHER,
    "OPERATION_TYPE_CURRENCY_EXCHANGE": OperationType.CONVERSION,
}

_ORDER_STATUS_MAP: dict[str, OrderStatus] = {
    "EXECUTION_REPORT_STATUS_NEW": OrderStatus.NEW,
    "EXECUTION_REPORT_STATUS_PARTIALLYFILL": OrderStatus.PARTIALLY_FILLED,
    "EXECUTION_REPORT_STATUS_FILL": OrderStatus.FILLED,
    "EXECUTION_REPORT_STATUS_CANCELLED": OrderStatus.CANCELLED,
    "EXECUTION_REPORT_STATUS_REJECTED": OrderStatus.REJECTED,
    "EXECUTION_REPORT_STATUS_UNSPECIFIED": OrderStatus.NEW,
}


class TinkoffBrokerAdapter(BrokerAdapter):

    @property
    def broker_id(self) -> str:
        return "tinkoff"

    @property
    def broker_name(self) -> str:
        return "Т-Банк (Tinkoff Invest)"

    async def get_info(self) -> BrokerInfo:
        is_configured = bool(config.tinkoff.token and config.tinkoff.account_id)
        if not is_configured:
            return BrokerInfo(
                broker_id=self.broker_id,
                name=self.broker_name,
                description="Tinkoff Invest API v2 (MOEX, СПБ)",
                is_connected=False,
                is_configured=False,
                error="Токен или ID счёта не настроены",
            )
        try:
            await asyncio.to_thread(self._ping)
            return BrokerInfo(
                broker_id=self.broker_id,
                name=self.broker_name,
                description="Tinkoff Invest API v2 (MOEX, СПБ)"
                + (" [SANDBOX]" if config.tinkoff.sandbox else " [LIVE]"),
                is_connected=True,
                is_configured=True,
                last_sync=datetime.now(timezone.utc),
            )
        except Exception as exc:
            return BrokerInfo(
                broker_id=self.broker_id,
                name=self.broker_name,
                description="Tinkoff Invest API v2",
                is_connected=False,
                is_configured=True,
                error=str(exc),
            )

    def _ping(self) -> None:
        with build_client() as client:
            client.users.get_accounts()

    async def get_portfolio(self) -> BrokerPortfolio:
        try:
            summary = await asyncio.to_thread(get_portfolio_summary)
        except TinkoffNotConfigured as exc:
            raise BrokerNotConfigured(str(exc)) from exc
        except (TinkoffSDKError, TinkoffAPIError) as exc:
            raise BrokerConnectionError(str(exc)) from exc

        positions = [
            BrokerPosition(
                broker_id=self.broker_id,
                figi=p.figi,
                ticker=p.ticker,
                name=p.name,
                instrument_type=p.instrument_type,
                quantity=p.quantity,
                quantity_lots=p.quantity_lots,
                average_price=p.average_price,
                current_price=p.current_price,
                unrealized_pnl=p.expected_yield,
                unrealized_pnl_pct=p.expected_yield_pct,
                current_value=p.current_value,
                currency=p.currency,
            )
            for p in summary.positions
        ]
        return BrokerPortfolio(
            broker_id=self.broker_id,
            broker_name=self.broker_name,
            total_value=summary.total_value,
            total_yield=summary.total_yield,
            total_yield_pct=summary.total_yield_pct,
            currency=summary.currency,
            positions_count=summary.positions_count,
            positions=positions,
        )

    async def get_positions(self) -> list[BrokerPosition]:
        portfolio = await self.get_portfolio()
        return portfolio.positions

    async def get_orders(
        self,
        status_filter: Optional[list[OrderStatus]] = None,
    ) -> list[BrokerOrder]:
        return await asyncio.to_thread(self._fetch_orders, status_filter)

    def _fetch_orders(self, status_filter: Optional[list[OrderStatus]]) -> list[BrokerOrder]:
        try:
            account_id = require_account_id()
            with build_client() as client:
                resp = client.orders.get_orders(account_id=account_id)
                orders = []
                for o in resp.orders:
                    status = _ORDER_STATUS_MAP.get(
                        o.execution_report_status.name, OrderStatus.NEW
                    )
                    if status_filter and status not in status_filter:
                        continue
                    direction = (
                        OrderDirection.BUY
                        if "BUY" in o.direction.name
                        else OrderDirection.SELL
                    )
                    order_type = (
                        OrderType.LIMIT
                        if "LIMIT" in o.order_type.name
                        else OrderType.MARKET
                    )
                    price = quotation_to_float(o.initial_security_price) or None
                    avg_price = money_value_to_float(o.average_position_price) or None
                    created_at = (
                        o.order_date.ToDatetime(tzinfo=timezone.utc)
                        if hasattr(o, "order_date") and o.order_date
                        else datetime.now(timezone.utc)
                    )
                    orders.append(BrokerOrder(
                        broker_id=self.broker_id,
                        order_id=o.order_id,
                        ticker=o.figi,
                        figi=o.figi,
                        direction=direction,
                        order_type=order_type,
                        status=status,
                        quantity=o.lots_requested,
                        filled_quantity=o.lots_executed,
                        price=price,
                        average_price=avg_price,
                        currency=money_value_currency(o.initial_order_price),
                        created_at=created_at,
                    ))
                return orders
        except TinkoffNotConfigured as exc:
            raise BrokerNotConfigured(str(exc)) from exc
        except Exception as exc:
            logger.error("Ошибка получения заявок: %s", exc)
            raise BrokerConnectionError(str(exc)) from exc

    async def get_operations(
        self,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[BrokerOperation]:
        return await asyncio.to_thread(self._fetch_operations, from_dt, to_dt, limit)

    def _fetch_operations(
        self,
        from_dt: Optional[datetime],
        to_dt: Optional[datetime],
        limit: int,
    ) -> list[BrokerOperation]:
        try:
            from google.protobuf.timestamp_pb2 import Timestamp

            account_id = require_account_id()
            if from_dt is None:
                from_dt = datetime.now(timezone.utc) - timedelta(days=30)
            if to_dt is None:
                to_dt = datetime.now(timezone.utc)

            if from_dt.tzinfo is None:
                from_dt = from_dt.replace(tzinfo=timezone.utc)
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=timezone.utc)

            with build_client() as client:
                resp = client.operations.get_operations(
                    account_id=account_id,
                    from_=from_dt,
                    to=to_dt,
                )
                ops = []
                for op in resp.operations[:limit]:
                    op_type = _OPERATION_TYPE_MAP.get(
                        op.operation_type.name, OperationType.OTHER
                    )
                    payment = money_value_to_float(op.payment)
                    price = money_value_to_float(op.price) if hasattr(op, "price") else None
                    currency = money_value_currency(op.payment)
                    executed_at = (
                        op.date.ToDatetime(tzinfo=timezone.utc)
                        if hasattr(op, "date") and op.date
                        else datetime.now(timezone.utc)
                    )
                    qty = quantation_to_float_safe(op)
                    ops.append(BrokerOperation(
                        broker_id=self.broker_id,
                        operation_id=op.id,
                        operation_type=op_type,
                        ticker=op.figi or None,
                        figi=op.figi or None,
                        quantity=qty,
                        price=price,
                        payment=payment,
                        currency=currency,
                        executed_at=executed_at,
                        description=getattr(op, "description", ""),
                    ))
                return ops
        except TinkoffNotConfigured as exc:
            raise BrokerNotConfigured(str(exc)) from exc
        except Exception as exc:
            logger.error("Ошибка получения операций: %s", exc)
            raise BrokerConnectionError(str(exc)) from exc

    async def get_balance(self) -> list[BrokerBalance]:
        return await asyncio.to_thread(self._fetch_balance)

    def _fetch_balance(self) -> list[BrokerBalance]:
        try:
            account_id = require_account_id()
            with build_client() as client:
                positions = client.operations.get_positions(account_id=account_id)
                balances = []
                for money in positions.money:
                    available = quotation_to_float(money)
                    currency = getattr(money, "currency", "rub")
                    balances.append(BrokerBalance(
                        broker_id=self.broker_id,
                        currency=currency,
                        available=round(available, 2),
                    ))
                for blocked in positions.blocked:
                    currency = getattr(blocked, "currency", "rub")
                    amount = quotation_to_float(blocked)
                    existing = next((b for b in balances if b.currency == currency), None)
                    if existing:
                        existing.blocked = round(amount, 2)
                    else:
                        balances.append(BrokerBalance(
                            broker_id=self.broker_id,
                            currency=currency,
                            available=0.0,
                            blocked=round(amount, 2),
                        ))
                return balances
        except TinkoffNotConfigured as exc:
            raise BrokerNotConfigured(str(exc)) from exc
        except Exception as exc:
            raise BrokerConnectionError(str(exc)) from exc

    async def place_market_order(
        self,
        figi: str,
        quantity: int,
        direction: OrderDirection,
    ) -> BrokerOrder:
        return await asyncio.to_thread(self._do_market_order, figi, quantity, direction)

    def _do_market_order(self, figi: str, quantity: int, direction: OrderDirection) -> BrokerOrder:
        try:
            from tinkoff.invest import OrderDirection as TDir, OrderType as TType
            account_id = require_account_id()
            t_direction = (
                TDir.ORDER_DIRECTION_BUY
                if direction == OrderDirection.BUY
                else TDir.ORDER_DIRECTION_SELL
            )
            with build_client() as client:
                resp = client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    direction=t_direction,
                    account_id=account_id,
                    order_type=TType.ORDER_TYPE_MARKET,
                )
                return BrokerOrder(
                    broker_id=self.broker_id,
                    order_id=resp.order_id,
                    ticker=figi,
                    figi=figi,
                    direction=direction,
                    order_type=OrderType.MARKET,
                    status=OrderStatus.NEW,
                    quantity=quantity,
                    filled_quantity=0,
                    price=None,
                    average_price=money_value_to_float(resp.initial_order_price) or None,
                    currency=money_value_currency(resp.initial_order_price),
                    created_at=datetime.now(timezone.utc),
                )
        except TinkoffNotConfigured as exc:
            raise BrokerNotConfigured(str(exc)) from exc
        except Exception as exc:
            raise BrokerConnectionError(str(exc)) from exc

    async def place_limit_order(
        self,
        figi: str,
        quantity: int,
        price: float,
        direction: OrderDirection,
    ) -> BrokerOrder:
        return await asyncio.to_thread(self._do_limit_order, figi, quantity, price, direction)

    def _do_limit_order(
        self, figi: str, quantity: int, price: float, direction: OrderDirection
    ) -> BrokerOrder:
        try:
            from decimal import Decimal
            from tinkoff.invest import OrderDirection as TDir, OrderType as TType, Quotation
            account_id = require_account_id()
            d = Decimal(str(price))
            units = int(d)
            nano = int((d - units) * 10 ** 9)
            q_price = Quotation(units=units, nano=nano)
            t_direction = (
                TDir.ORDER_DIRECTION_BUY
                if direction == OrderDirection.BUY
                else TDir.ORDER_DIRECTION_SELL
            )
            with build_client() as client:
                resp = client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    price=q_price,
                    direction=t_direction,
                    account_id=account_id,
                    order_type=TType.ORDER_TYPE_LIMIT,
                )
                return BrokerOrder(
                    broker_id=self.broker_id,
                    order_id=resp.order_id,
                    ticker=figi,
                    figi=figi,
                    direction=direction,
                    order_type=OrderType.LIMIT,
                    status=OrderStatus.NEW,
                    quantity=quantity,
                    filled_quantity=0,
                    price=price,
                    average_price=None,
                    currency=money_value_currency(resp.initial_order_price),
                    created_at=datetime.now(timezone.utc),
                )
        except TinkoffNotConfigured as exc:
            raise BrokerNotConfigured(str(exc)) from exc
        except Exception as exc:
            raise BrokerConnectionError(str(exc)) from exc

    async def cancel_order(self, order_id: str) -> bool:
        return await asyncio.to_thread(self._do_cancel_order, order_id)

    def _do_cancel_order(self, order_id: str) -> bool:
        try:
            account_id = require_account_id()
            with build_client() as client:
                client.orders.cancel_order(account_id=account_id, order_id=order_id)
                return True
        except Exception as exc:
            logger.error("Ошибка отмены заявки %s: %s", order_id, exc)
            return False

    async def find_instrument(self, ticker: str) -> Optional[dict]:
        return await asyncio.to_thread(self._do_find_instrument, ticker)

    def _do_find_instrument(self, ticker: str) -> Optional[dict]:
        try:
            with build_client() as client:
                resp = client.instruments.find_instrument(query=ticker)
                for item in resp.instruments:
                    if item.ticker == ticker:
                        return {
                            "figi": item.figi,
                            "ticker": item.ticker,
                            "name": item.name,
                            "lot": item.lot,
                            "currency": item.currency,
                        }
        except Exception as exc:
            logger.error("Ошибка поиска инструмента %s: %s", ticker, exc)
        return None


def quantation_to_float_safe(op) -> Optional[float]:
    qty = getattr(op, "quantity", None)
    if qty is None:
        return None
    try:
        return float(qty)
    except (TypeError, ValueError):
        return None
