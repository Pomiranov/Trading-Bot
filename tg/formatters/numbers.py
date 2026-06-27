"""Number and date formatting helpers for Telegram messages."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional


def fmt_money(value: Optional[float], currency: str = "₽", decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.{decimals}f} {currency}".replace(",", " ")


def fmt_pct(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_pnl(value: Optional[float], currency: str = "₽") -> str:
    if value is None:
        return "—"
    if value > 0:
        return f"🟢 +{value:,.2f} {currency}".replace(",", " ")
    if value < 0:
        return f"🔴 {value:,.2f} {currency}".replace(",", " ")
    return f"⚪ {value:,.2f} {currency}".replace(",", " ")


def fmt_float(value: Optional[float], decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", " ")


def fmt_datetime(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def fmt_date(d: Optional[date]) -> str:
    if d is None:
        return "—"
    return d.strftime("%d.%m.%Y")


def fmt_ratio(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def pnl_arrow(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if value > 0:
        return "↑"
    if value < 0:
        return "↓"
    return "→"


def instrument_type_emoji(itype: str) -> str:
    mapping = {
        "stock": "📈",
        "share": "📈",
        "etf": "🧺",
        "bond": "📊",
        "currency": "💱",
        "crypto": "₿",
        "futures": "📅",
        "option": "🎯",
    }
    return mapping.get(itype.lower(), "📌")


def operation_type_emoji(op_type: str) -> str:
    mapping = {
        "BUY": "🟢",
        "SELL": "🔴",
        "DIVIDEND": "💰",
        "COUPON": "🏦",
        "DEPOSIT": "💵",
        "WITHDRAWAL": "💸",
        "COMMISSION": "💳",
        "TAX": "🧾",
        "CONVERSION": "🔄",
        "OTHER": "📌",
    }
    return mapping.get(op_type, "📌")


def escape_md(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)
