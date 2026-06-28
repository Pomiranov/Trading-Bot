"""All FSM states used across ConversationHandlers."""
from enum import IntEnum, auto


class TradeStates(IntEnum):
    SELECT_BROKER = auto()
    ENTER_TICKER = auto()
    ENTER_QUANTITY = auto()
    CONFIRM_ORDER = auto()


class SettingsStates(IntEnum):
    SELECT_SECTION = auto()
    ENTER_TINKOFF_TOKEN = auto()
    ENTER_TINKOFF_ACCOUNT = auto()
    ENTER_TICKER_LIST = auto()
    ENTER_POLL_INTERVAL = auto()


class SignalStates(IntEnum):
    ENTER_TICKER = auto()
