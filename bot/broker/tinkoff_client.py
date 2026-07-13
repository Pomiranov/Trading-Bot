"""Клиент Т-Инвестиции (Tinkoff Invest API v2) через tinkoff-investments SDK."""

import logging
from decimal import Decimal
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

# Импорт SDK — если не установлен, работаем в режиме заглушки
try:
    from tinkoff.invest import (
        Client,
        OrderDirection,
        OrderType,
        Quotation,
        InstrumentStatus,
        CandleInterval,
    )
    from tinkoff.invest.sandbox.client import SandboxClient
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning(
        "SDK tinkoff-investments не установлен. "
        "Установите: pip install tinkoff-investments"
    )


def _quotation_to_decimal(q) -> Decimal:
    """Конвертировать Quotation в Decimal."""
    return Decimal(q.units) + Decimal(q.nano) / Decimal(10 ** 9)


def _decimal_to_quotation(value: Decimal):
    """Конвертировать Decimal в Quotation."""
    if not SDK_AVAILABLE:
        return None
    units = int(value)
    nano = int((value - units) * 10 ** 9)
    return Quotation(units=units, nano=nano)


class TinkoffClient:
    """
    Обёртка над Tinkoff Invest API.

    Поддерживает sandbox и боевой режим через config.tinkoff.sandbox.
    """

    def __init__(self):
        self.cfg = config.tinkoff
        self._client = None

    def _get_client(self):
        if not SDK_AVAILABLE:
            raise RuntimeError("SDK tinkoff-investments не установлен")
        if self.cfg.sandbox:
            return SandboxClient(self.cfg.token)
        return Client(self.cfg.token)

    # ─── Аккаунт и портфель ──────────────────────────────────────────

    def get_portfolio(self) -> dict:
        """Получить текущий портфель."""
        try:
            with self._get_client() as client:
                portfolio = client.operations.get_portfolio(
                    account_id=self.cfg.account_id
                )
                total = _quotation_to_decimal(portfolio.total_amount_portfolio)
                positions = [
                    {
                        "figi": p.figi,
                        "quantity": _quotation_to_decimal(p.quantity),
                        "current_price": _quotation_to_decimal(p.current_price),
                        "expected_yield": _quotation_to_decimal(p.expected_yield),
                    }
                    for p in portfolio.positions
                ]
                return {"total_value": float(total), "positions": positions}
        except Exception as exc:
            logger.error("Ошибка получения портфеля: %s", exc)
            return {"total_value": 0.0, "positions": []}

    def get_balance(self) -> float:
        """Получить свободный остаток денежных средств в рублях."""
        try:
            with self._get_client() as client:
                accounts = client.users.get_accounts()
                for acc in accounts.accounts:
                    if acc.id == self.cfg.account_id:
                        positions = client.operations.get_positions(
                            account_id=self.cfg.account_id
                        )
                        for money in positions.money:
                            if money.currency == "rub":
                                return float(_quotation_to_decimal(money))
                return 0.0
        except Exception as exc:
            logger.error("Ошибка получения баланса: %s", exc)
            return 0.0

    # ─── Инструменты ─────────────────────────────────────────────────

    def find_instrument(self, ticker: str) -> Optional[dict]:
        """Найти инструмент по тикеру, вернуть figi и lot.

        find_instrument() returns InstrumentShort which has no 'lot' field.
        A second call to get_instrument_by() fetches the full instrument data.
        """
        try:
            with self._get_client() as client:
                resp = client.instruments.find_instrument(query=ticker)
                figi = None
                for item in resp.instruments:
                    if item.ticker == ticker:
                        figi = item.figi
                        break

                if figi is None:
                    return None

                from tinkoff.invest import InstrumentIdType
                full = client.instruments.get_instrument_by(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                    id=figi,
                    class_code="",
                )
                instr = full.instrument
                return {
                    "figi": instr.figi,
                    "ticker": instr.ticker,
                    "name": instr.name,
                    "lot": instr.lot,
                    "currency": instr.currency,
                    "min_price_increment": float(
                        _quotation_to_decimal(instr.min_price_increment)
                    ),
                }
        except Exception as exc:
            logger.error("Ошибка поиска инструмента %s: %s", ticker, exc)
        return None

    # ─── Ордера ──────────────────────────────────────────────────────

    def place_market_order(
        self,
        figi: str,
        quantity: int,
        direction: str = "buy",
    ) -> Optional[str]:
        """
        Выставить рыночную заявку.

        direction: 'buy' или 'sell'
        Возвращает order_id или None при ошибке.
        """
        if not SDK_AVAILABLE:
            logger.warning("SDK не доступен — заявка не выставлена")
            return None

        order_direction = (
            OrderDirection.ORDER_DIRECTION_BUY
            if direction == "buy"
            else OrderDirection.ORDER_DIRECTION_SELL
        )

        try:
            with self._get_client() as client:
                resp = client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    direction=order_direction,
                    account_id=self.cfg.account_id,
                    order_type=OrderType.ORDER_TYPE_MARKET,
                )
                logger.info(
                    "Рыночная заявка %s: figi=%s, qty=%d, order_id=%s",
                    direction, figi, quantity, resp.order_id,
                )
                return resp.order_id
        except Exception as exc:
            exc_str = str(exc)
            if "30052" in exc_str or "forbidden for trading" in exc_str.lower():
                logger.warning(
                    "Инструмент figi=%s недоступен для торговли в sandbox (30052) — пропускаем",
                    figi,
                )
            else:
                logger.error("Ошибка выставления рыночной заявки: %s", exc)
            return None

    def place_limit_order(
        self,
        figi: str,
        quantity: int,
        price: Decimal,
        direction: str = "buy",
    ) -> Optional[str]:
        """Выставить лимитную заявку."""
        if not SDK_AVAILABLE:
            return None

        order_direction = (
            OrderDirection.ORDER_DIRECTION_BUY
            if direction == "buy"
            else OrderDirection.ORDER_DIRECTION_SELL
        )

        try:
            with self._get_client() as client:
                resp = client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    price=_decimal_to_quotation(price),
                    direction=order_direction,
                    account_id=self.cfg.account_id,
                    order_type=OrderType.ORDER_TYPE_LIMIT,
                )
                logger.info(
                    "Лимитная заявка %s: figi=%s, qty=%d, price=%s, order_id=%s",
                    direction, figi, quantity, price, resp.order_id,
                )
                return resp.order_id
        except Exception as exc:
            logger.error("Ошибка выставления лимитной заявки: %s", exc)
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Отменить заявку по order_id."""
        try:
            with self._get_client() as client:
                client.orders.cancel_order(
                    account_id=self.cfg.account_id,
                    order_id=order_id,
                )
                logger.info("Заявка %s отменена", order_id)
                return True
        except Exception as exc:
            logger.error("Ошибка отмены заявки %s: %s", order_id, exc)
            return False

    def get_order_state(self, order_id: str) -> Optional[dict]:
        """Получить статус заявки."""
        try:
            with self._get_client() as client:
                resp = client.orders.get_order_state(
                    account_id=self.cfg.account_id,
                    order_id=order_id,
                )
                return {
                    "order_id": resp.order_id,
                    "status": resp.execution_report_status.name,
                    "lots_requested": resp.lots_requested,
                    "lots_executed": resp.lots_executed,
                    "average_price": float(_quotation_to_decimal(resp.average_position_price)),
                }
        except Exception as exc:
            logger.error("Ошибка получения статуса заявки %s: %s", order_id, exc)
            return None


tinkoff_client = TinkoffClient()
