"""
Portfolio and positions retrieval from Tinkoff Invest API.

Instrument metadata (ticker, name) is resolved lazily and cached for 1 hour.
Portfolio data is cached for 30 seconds.
"""
from __future__ import annotations

import logging

from .cache import TTLCache
from .client import TinkoffAPIError, TinkoffNotConfigured, TinkoffSDKError, build_client, require_account_id
from .mapper import money_value_currency, money_value_to_float, quotation_to_float
from .types import Position, PortfolioSummary

logger = logging.getLogger(__name__)

_SKIP_INSTRUMENT_TYPES = frozenset({"currency"})

_portfolio_cache: TTLCache = TTLCache(ttl_seconds=30)
_instrument_cache: TTLCache = TTLCache(ttl_seconds=3600)


def _resolve_instrument(client, figi: str) -> tuple[str, str]:
    """Return (ticker, name) for a figi. Cached 1 h; falls back to figi on error."""
    hit = _instrument_cache.get(figi)
    if hit is not None:
        return hit

    try:
        from tinkoff.invest import InstrumentIdType
        resp = client.instruments.get_instrument_by(
            id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
            id=figi,
            class_code="",
        )
        ticker = resp.instrument.ticker or figi
        name = resp.instrument.name or figi
    except Exception as exc:
        logger.debug("Cannot resolve figi=%s: %s", figi, exc)
        ticker = figi
        name = figi

    result = (ticker, name)
    _instrument_cache.set(figi, result)
    return result


def get_portfolio_summary() -> PortfolioSummary:
    """
    Fetch portfolio summary and enriched positions from Tinkoff Invest API.

    Raises:
        TinkoffSDKError        if the SDK is not installed
        TinkoffNotConfigured   if token / account_id is missing
        TinkoffAPIError        if the API call fails
    """
    account_id = require_account_id()
    cache_key = f"portfolio:{account_id}"

    hit = _portfolio_cache.get(cache_key)
    if hit is not None:
        return hit

    try:
        with build_client() as client:
            resp = client.operations.get_portfolio(account_id=account_id)

            total_value = money_value_to_float(resp.total_amount_portfolio)
            currency = money_value_currency(resp.total_amount_portfolio)

            positions: list[Position] = []
            total_yield = 0.0

            for p in resp.positions:
                if p.instrument_type in _SKIP_INSTRUMENT_TYPES:
                    continue

                quantity = quotation_to_float(p.quantity)
                if quantity <= 0:
                    continue

                avg_price = money_value_to_float(p.average_position_price)
                current_price = money_value_to_float(p.current_price)
                expected_yield = quotation_to_float(p.expected_yield)
                quantity_lots = quotation_to_float(p.quantity_lots)

                cost_basis = avg_price * quantity
                expected_yield_pct = (
                    round(expected_yield / cost_basis * 100, 2)
                    if cost_basis > 0
                    else 0.0
                )

                ticker, name = _resolve_instrument(client, p.figi)

                pos = Position(
                    figi=p.figi,
                    ticker=ticker,
                    name=name,
                    instrument_type=p.instrument_type,
                    quantity=round(quantity, 6),
                    quantity_lots=round(quantity_lots, 2),
                    average_price=round(avg_price, 4),
                    current_price=round(current_price, 4),
                    expected_yield=round(expected_yield, 2),
                    expected_yield_pct=expected_yield_pct,
                    current_value=round(current_price * quantity, 2),
                    currency=currency,
                )
                positions.append(pos)
                total_yield += expected_yield

            cost_basis_total = total_value - total_yield
            total_yield_pct = (
                round(total_yield / cost_basis_total * 100, 2)
                if cost_basis_total > 0
                else 0.0
            )

            summary = PortfolioSummary(
                total_value=round(total_value, 2),
                total_yield=round(total_yield, 2),
                total_yield_pct=total_yield_pct,
                positions_count=len(positions),
                currency=currency,
                positions=positions,
            )

    except (TinkoffSDKError, TinkoffNotConfigured):
        raise
    except Exception as exc:
        raise TinkoffAPIError(f"Ошибка получения портфеля: {exc}") from exc

    _portfolio_cache.set(cache_key, summary)
    return summary


def invalidate_portfolio_cache() -> None:
    """Clear all cached portfolio data (call after credentials change)."""
    _portfolio_cache.invalidate()
    _instrument_cache.invalidate()
