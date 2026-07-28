"""Trading environment as a first-class enum.

`trades.is_sandbox` is a boolean, and a boolean cannot express the four states
the product actually has. Worse, a boolean has no way to say "I do not know",
so an unset column reads as `false` — which would silently label a live row as
sandbox, or a sandbox row as live, depending on which way the default fell.

Four real environments plus an explicit unknown:

* ``SANDBOX``  — paper account, simulated fills, broker sandbox
* ``FORWARD``  — forward test on live data, no orders sent
* ``BACKTEST`` — historical replay
* ``LIVE``     — real money
* ``UNKNOWN``  — provenance could not be established

The rule that makes this safe: **UNKNOWN is never coerced to SANDBOX**. An
unlabelled row is a configuration fault and renders as one. Guessing "probably
sandbox" is how a live number ends up on a sandbox screen.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class Environment(str, Enum):
    SANDBOX = "sandbox"
    FORWARD = "forward"
    BACKTEST = "backtest"
    LIVE = "live"
    UNKNOWN = "unknown"

    @property
    def is_real_money(self) -> bool:
        return self is Environment.LIVE

    @property
    def is_fault(self) -> bool:
        """UNKNOWN is a fault, not a neutral state."""
        return self is Environment.UNKNOWN

    @classmethod
    def coerce(cls, value: Any) -> "Environment":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().lower()
        if not text:
            return cls.UNKNOWN
        for member in cls:
            if member.value == text:
                return member
        aliases = {
            "paper": cls.SANDBOX,
            "sim": cls.SANDBOX,
            "simulated": cls.SANDBOX,
            "demo": cls.SANDBOX,
            "fwd": cls.FORWARD,
            "forward_test": cls.FORWARD,
            "bt": cls.BACKTEST,
            "historical": cls.BACKTEST,
            "real": cls.LIVE,
            "prod": cls.LIVE,
            "production": cls.LIVE,
        }
        return aliases.get(text, cls.UNKNOWN)

    @classmethod
    def from_sandbox_flag(
        cls,
        is_sandbox: Optional[bool],
        *,
        explicit: Any = None,
        exchange: Optional[str] = None,
    ) -> "Environment":
        """Derive an environment for a row that only has the legacy boolean.

        Precedence: an explicit environment column beats everything; then the
        exchange marker (`paper`/`backtest` are unambiguous); then the boolean;
        then UNKNOWN. `is_sandbox IS NULL` yields UNKNOWN, never SANDBOX — that
        is the whole point of the enum.
        """
        resolved = cls.coerce(explicit)
        if resolved is not cls.UNKNOWN:
            return resolved

        marker = (exchange or "").strip().lower()
        if marker in {"paper", "sandbox"}:
            return cls.SANDBOX
        if marker == "backtest":
            return cls.BACKTEST
        if marker == "forward":
            return cls.FORWARD

        if is_sandbox is True:
            return cls.SANDBOX
        if is_sandbox is False:
            return cls.LIVE
        return cls.UNKNOWN


#: Russian labels. Identifiers and tickers are never translated; environment
#: names are, because they are the one thing an operator must read instantly.
ENVIRONMENT_LABELS = {
    Environment.SANDBOX: "ПЕСОЧНИЦА",
    Environment.FORWARD: "ФОРВАРД",
    Environment.BACKTEST: "БЭКТЕСТ",
    Environment.LIVE: "LIVE · РЕАЛЬНЫЕ СРЕДСТВА",
    Environment.UNKNOWN: "СРЕДА НЕ ОПРЕДЕЛЕНА",
}

#: Short form for a table cell, where the band's full text will not fit.
ENVIRONMENT_SHORT_LABELS = {
    Environment.SANDBOX: "песочница",
    Environment.FORWARD: "форвард",
    Environment.BACKTEST: "бэктест",
    Environment.LIVE: "LIVE",
    Environment.UNKNOWN: "неизвестно",
}


def sql_filter(
    environments: Optional[list[Environment]],
    *,
    column: str = "is_sandbox",
) -> tuple[str, dict]:
    """Build a WHERE fragment restricting a legacy boolean column.

    Only SANDBOX and LIVE are expressible against a boolean; FORWARD and
    BACKTEST need their own provenance and are filtered in the service layer
    against the exchange/source marker. Returning `("1=1", {})` for anything
    else is deliberate: silently returning nothing would look like "no trades"
    rather than "this filter cannot be applied here".
    """
    if not environments:
        return "1=1", {}
    wants_sandbox = Environment.SANDBOX in environments
    wants_live = Environment.LIVE in environments
    if wants_sandbox and wants_live:
        return "1=1", {}
    if wants_sandbox:
        return f"COALESCE({column}, true) = true", {}
    if wants_live:
        return f"{column} = false", {}
    return "1=1", {}
