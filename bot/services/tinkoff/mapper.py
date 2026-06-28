"""Converters from Tinkoff gRPC types to plain Python values."""
from __future__ import annotations


def quotation_to_float(q) -> float:
    """Quotation → float.  Works for both Quotation and MoneyValue."""
    if q is None:
        return 0.0
    return float(q.units) + float(q.nano) / 1_000_000_000.0


# MoneyValue has the same wire layout as Quotation plus a currency field.
money_value_to_float = quotation_to_float


def money_value_currency(mv) -> str:
    if mv is None:
        return "rub"
    return getattr(mv, "currency", "rub") or "rub"
