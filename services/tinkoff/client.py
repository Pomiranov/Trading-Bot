"""
Tinkoff Invest SDK factory with typed error hierarchy.

Callers catch specific exception types to distinguish user-facing errors
(credential not set) from infrastructure errors (SDK missing, API failure).
"""
from __future__ import annotations

import logging

from config import config

logger = logging.getLogger(__name__)

try:
    from tinkoff.invest import Client, InstrumentIdType  # noqa: F401
    from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


class TinkoffSDKError(RuntimeError):
    """tinkoff-investments package is not installed."""


class TinkoffNotConfigured(ValueError):
    """TINKOFF_TOKEN or TINKOFF_ACCOUNT_ID is missing."""


class TinkoffAPIError(RuntimeError):
    """A call to the Tinkoff Invest API failed."""


def build_client():
    """Return a configured SDK client context manager (sandbox or production)."""
    if not SDK_AVAILABLE:
        raise TinkoffSDKError(
            "tinkoff-investments is not installed. "
            "Uncomment it in requirements.txt and run: pip install tinkoff-investments"
        )
    token = config.tinkoff.token
    if not token:
        raise TinkoffNotConfigured(
            "TINKOFF_TOKEN не настроен. Перейдите в Settings и введите токен."
        )
    if not config.tinkoff.account_id:
        raise TinkoffNotConfigured(
            "TINKOFF_ACCOUNT_ID не настроен. Перейдите в Settings и введите идентификатор счёта."
        )
    if config.tinkoff.sandbox:
        return Client(token, target=INVEST_GRPC_API_SANDBOX)
    return Client(token)


def require_account_id() -> str:
    account_id = config.tinkoff.account_id
    if not account_id:
        raise TinkoffNotConfigured(
            "TINKOFF_ACCOUNT_ID не настроен. Перейдите в Settings."
        )
    return account_id
