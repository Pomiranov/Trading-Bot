"""Response contract for the operational dashboard API.

One envelope, one error shape, one place where units and freshness are declared.

Every successful response is::

    {"data": <payload>, "meta": {...}}

Every failure is::

    {"error": {"code": "...", "message": "...", "id": "<correlation-id>"}}

`meta` always carries `as_of` (server time). Anything derived from a market price
also carries `source_as_of` and `data_age_seconds`, so the client can render
staleness per slice instead of stamping one global "updated now" over a screen
that is partly 32 days old. Aggregates carry `n`. Numbers carry `units`.

Nothing here formats for humans — that is the frontend's single formatting
authority. This module only guarantees that the *meaning* of a number is never
implicit in its field name.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional

from qf_platform.environment import Environment

# ── Timezone policy ───────────────────────────────────────────────────────────
# The database stores TIMESTAMPTZ and runs in UTC. Every timestamp crosses into
# the view model exactly once, here, and always carries its offset. The client
# never converts; it renders what it is given plus the label in `meta.timezone`.
DISPLAY_TZ = timezone(timedelta(hours=3), name="MSK")
DISPLAY_TZ_LABEL = "MSK"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_display(value: Any) -> Optional[str]:
    """Normalise any timestamp-ish value to an ISO-8601 string with offset.

    Naive datetimes are assumed UTC — that is what the database returns for
    TIMESTAMPTZ through psycopg2 when the session timezone is UTC. Returning a
    naive string would let the client guess, and a three-hour silent shift on an
    equity x-axis is exactly the failure §9.4 of the audit describes.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(DISPLAY_TZ).isoformat(timespec="seconds")
    text = str(value)
    return text or None


def age_seconds(value: Any, *, reference: Optional[datetime] = None) -> Optional[int]:
    """Seconds between `value` and now. `None` when the input is not a time."""
    if not isinstance(value, datetime):
        return None
    ref = reference or now_utc()
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return max(0, int((ref - dt).total_seconds()))


# ── Units ─────────────────────────────────────────────────────────────────────
# A field name is not a unit. `max_drawdown` carried both a fraction and a
# percentage in the same codebase and rendered −23,73 % as «−0,2 %».


class Units:
    MONEY = "money"           # currency amount, `meta.currency` names the currency
    PERCENT = "percent"       # already multiplied by 100 — −23.73 means −23,73 %
    RATIO = "ratio"           # 0..1, never rendered as a percentage
    R_MULTIPLE = "r"          # risk multiples
    COUNT = "count"
    SECONDS = "seconds"
    MILLISECONDS = "ms"
    SHARES = "shares"
    PRICE = "price"           # instrument's own tick precision
    ENUM = "enum"
    NONE = "none"


# ── Error codes ───────────────────────────────────────────────────────────────
# Machine-readable and stable. The human message is safe by construction: it
# never contains SQL, a stack trace, a path or a credential.


class ErrorCode:
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    CSRF_INVALID = "CSRF_INVALID"
    READ_ONLY_MODE = "READ_ONLY_MODE"
    RATE_LIMITED = "RATE_LIMITED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    SCHEMA_OUT_OF_DATE = "SCHEMA_OUT_OF_DATE"
    BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    INTERNAL = "INTERNAL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


#: Safe, user-facing Russian text per code. Never interpolated with internals.
ERROR_MESSAGES = {
    ErrorCode.UNAUTHENTICATED: "Требуется вход в систему.",
    ErrorCode.FORBIDDEN: "Недостаточно прав для этого действия.",
    ErrorCode.CSRF_INVALID: "Сессия истекла. Обновите страницу и повторите.",
    ErrorCode.READ_ONLY_MODE: "Дашборд запущен в режиме только для чтения.",
    ErrorCode.RATE_LIMITED: "Слишком много попыток. Повторите позже.",
    ErrorCode.VALIDATION_FAILED: "Некорректные параметры запроса.",
    ErrorCode.NOT_FOUND: "Объект не найден.",
    ErrorCode.CONFLICT: "Действие уже выполняется или уже выполнено.",
    ErrorCode.DB_UNAVAILABLE: "База данных недоступна.",
    ErrorCode.SCHEMA_OUT_OF_DATE: "Схема базы данных устарела — требуется миграция.",
    ErrorCode.BROKER_UNAVAILABLE: "Брокер не отвечает.",
    ErrorCode.UPSTREAM_TIMEOUT: "Внешний сервис не ответил вовремя.",
    ErrorCode.INTERNAL: "Внутренняя ошибка. Обратитесь к журналу событий.",
    ErrorCode.NOT_IMPLEMENTED: "Функция ещё не реализована.",
}

#: Default HTTP status per code.
ERROR_STATUS = {
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.CSRF_INVALID: 403,
    ErrorCode.READ_ONLY_MODE: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.VALIDATION_FAILED: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.DB_UNAVAILABLE: 503,
    ErrorCode.SCHEMA_OUT_OF_DATE: 503,
    ErrorCode.BROKER_UNAVAILABLE: 502,
    ErrorCode.UPSTREAM_TIMEOUT: 504,
    ErrorCode.INTERNAL: 500,
    ErrorCode.NOT_IMPLEMENTED: 501,
}


class ApiError(Exception):
    """Raised anywhere below the HTTP layer; rendered by one error handler."""

    def __init__(
        self,
        code: str,
        *,
        detail: Optional[str] = None,
        status: Optional[int] = None,
        field_name: Optional[str] = None,
    ):
        self.code = code
        # `detail` is appended to the safe message only when the caller has
        # explicitly vetted it as user-facing. Exception text never lands here.
        self.detail = detail
        self.status = status or ERROR_STATUS.get(code, 500)
        self.field_name = field_name
        super().__init__(code)

    def message(self) -> str:
        base = ERROR_MESSAGES.get(self.code, ERROR_MESSAGES[ErrorCode.INTERNAL])
        return f"{base} {self.detail}".strip() if self.detail else base


# ── Empty / non-fresh reasons ─────────────────────────────────────────────────
# «Нет данных» is eight different situations, each with a different action.
# The reason travels in `meta.empty_reason` so the client picks the right text
# rather than collapsing all of them into a dash.


class EmptyReason:
    NO_TRADES_EVER = "NO_TRADES_EVER"
    NO_TRADES_IN_PERIOD = "NO_TRADES_IN_PERIOD"
    NO_POSITIONS = "NO_POSITIONS"
    NO_SIGNALS = "NO_SIGNALS"
    NO_EQUITY_HISTORY = "NO_EQUITY_HISTORY"
    NO_EVENTS = "NO_EVENTS"
    STRATEGY_NEVER_RAN = "STRATEGY_NEVER_RAN"
    MARKET_CLOSED = "MARKET_CLOSED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass
class Freshness:
    """Age of the newest input a slice was built from.

    `source_as_of` is the timestamp of the *data*, not of the request. A panel
    served in 4 ms from a candle recorded 32 days ago is not fresh, and the two
    numbers must never be conflated.
    """

    source_as_of: Optional[datetime] = None
    source: Optional[str] = None
    stale_after_seconds: Optional[int] = None

    def as_meta(self, *, reference: Optional[datetime] = None) -> dict:
        age = age_seconds(self.source_as_of, reference=reference)
        out: dict[str, Any] = {
            "source_as_of": to_display(self.source_as_of),
            "data_age_seconds": age,
            "source": self.source,
        }
        if self.stale_after_seconds is not None:
            out["stale_after_seconds"] = self.stale_after_seconds
            # `is_stale` is None — not False — when the age is unknown. Unknown
            # freshness must never render as fresh.
            out["is_stale"] = None if age is None else age > self.stale_after_seconds
        return out

    @staticmethod
    def worst(items: Iterable["Freshness"]) -> "Freshness":
        """Combine slices: the oldest input wins, because that is what the
        operator is actually looking at."""
        chosen: Optional[Freshness] = None
        for item in items:
            if item is None or item.source_as_of is None:
                continue
            if chosen is None or item.source_as_of < chosen.source_as_of:
                chosen = item
        return chosen or Freshness()


@dataclass
class Meta:
    """Everything a number needs in order to be honest."""

    environment: Environment = Environment.UNKNOWN
    units: Optional[str] = None
    currency: Optional[str] = None
    n: Optional[int] = None
    window: Optional[str] = None
    freshness: Freshness = field(default_factory=Freshness)
    empty_reason: Optional[str] = None
    partial: bool = False
    #: Field name → reason, for slices that arrived incomplete.
    missing: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "as_of": to_display(now_utc()),
            "timezone": DISPLAY_TZ_LABEL,
            "environment": Environment.coerce(self.environment).value,
        }
        out.update(self.freshness.as_meta())
        if self.units is not None:
            out["units"] = self.units
        if self.currency is not None:
            out["currency"] = self.currency
        if self.n is not None:
            out["n"] = self.n
        if self.window is not None:
            out["window"] = self.window
        if self.empty_reason is not None:
            out["empty_reason"] = self.empty_reason
        if self.partial:
            out["partial"] = True
        if self.missing:
            out["missing"] = dict(self.missing)
        out.update(self.extra)
        return out


def envelope(data: Any, meta: Optional[Meta] = None, **meta_kwargs: Any) -> dict:
    """Wrap a payload in the single success envelope."""
    m = meta or Meta(**meta_kwargs)
    return {"data": data, "meta": m.to_dict()}


def error_envelope(code: str, message: str, correlation_id: str) -> dict:
    return {"error": {"code": code, "message": message, "id": correlation_id}}


# ── Numeric hygiene ───────────────────────────────────────────────────────────


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Convert to float, mapping NaN/Inf to `default`.

    JSON has no NaN. `jsonify` emits the literal `NaN`, which every strict JSON
    parser rejects — and a panel that fails to parse renders as an empty panel,
    which the operator reads as "no data" rather than "broken".
    """
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out) or math.isinf(out):
        return default
    return out


def signed_mean(values: Iterable[float]) -> tuple[Optional[float], int]:
    """Arithmetic mean preserving sign, with its sample size.

    Returns `(None, 0)` for an empty sample rather than 0.0 — a measured zero
    and an absent measurement are different facts and must render differently.
    """
    nums = [v for v in (safe_float(x) for x in values) if v is not None]
    if not nums:
        return None, 0
    return sum(nums) / len(nums), len(nums)


def mean_abs(values: Iterable[float]) -> tuple[Optional[float], int]:
    """Mean of absolute values — the *average move*, which is a different
    statistic from average profit and must be labelled as such."""
    nums = [abs(v) for v in (safe_float(x) for x in values) if v is not None]
    if not nums:
        return None, 0
    return sum(nums) / len(nums), len(nums)


def profit_factor(pnls: Iterable[float]) -> tuple[Optional[float], int]:
    """Gross profit / gross loss. `None` when undefined, never 0.

    With no losses the ratio is unbounded; the caller decides whether the sample
    is large enough to call that «∞» or whether it should read «н/д».
    """
    nums = [v for v in (safe_float(x) for x in pnls) if v is not None]
    if not nums:
        return None, 0
    gross_profit = sum(v for v in nums if v > 0)
    gross_loss = abs(sum(v for v in nums if v < 0))
    if gross_loss == 0:
        return None, len(nums)
    return gross_profit / gross_loss, len(nums)


def win_rate(pnls: Iterable[float]) -> tuple[Optional[float], int, int]:
    """`(percent, wins, n)`. Percent is `None` at n=0, so «н/д (0 сделок)» and
    «0,0 % (0 из 14)» cannot render identically."""
    nums = [v for v in (safe_float(x) for x in pnls) if v is not None]
    if not nums:
        return None, 0, 0
    wins = sum(1 for v in nums if v > 0)
    return wins / len(nums) * 100.0, wins, len(nums)


#: Below this sample size a statistic is labelled «мало данных» and excluded
#: from every ranking. §16 of the audit; the value is a product decision, so it
#: lives in exactly one place.
MIN_SAMPLE_FOR_RANKING = 30


def is_mature_sample(n: Optional[int]) -> bool:
    return bool(n) and n >= MIN_SAMPLE_FOR_RANKING


def drawdown_from_equity(
    equities: list[float],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Maximum drawdown as `(percent, absolute, peak)`.

    Percent is negative and already ×100 — `-23.73` means −23,73 %. Absolute is
    negative and in account currency. Returning both under separate names is the
    fix for the unit collision that rendered −23,73 % as «−0,2 %».

    `(None, None, None)` for fewer than two observations: a drawdown over one
    point is not zero, it is unmeasured.
    """
    nums = [v for v in (safe_float(e) for e in equities) if v is not None]
    if len(nums) < 2:
        return None, None, None

    peak = nums[0]
    worst_pct = 0.0
    worst_abs = 0.0
    worst_peak = peak
    for value in nums:
        if value > peak:
            peak = value
        drop_abs = value - peak
        drop_pct = (drop_abs / peak * 100.0) if peak > 0 else 0.0
        if drop_pct < worst_pct:
            worst_pct = drop_pct
            worst_abs = drop_abs
            worst_peak = peak
        elif drop_pct == worst_pct and drop_abs < worst_abs:
            worst_abs = drop_abs
            worst_peak = peak
    return worst_pct, worst_abs, worst_peak


def sharpe_from_returns(returns: list[float], periods_per_year: int = 252) -> Optional[float]:
    """Annualised Sharpe over a return series, or `None` when undefined.

    This is the *only* Sharpe implementation the dashboard uses. Three others
    exist in the repository for the backtest and legacy paths; the API must not
    add a fourth, and the frontend must not derive it at all.
    """
    nums = [v for v in (safe_float(r) for r in returns) if v is not None]
    if len(nums) < 2:
        return None
    mean = sum(nums) / len(nums)
    variance = sum((r - mean) ** 2 for r in nums) / (len(nums) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return mean / std * math.sqrt(periods_per_year)


def sortino_from_returns(returns: list[float], periods_per_year: int = 252) -> Optional[float]:
    nums = [v for v in (safe_float(r) for r in returns) if v is not None]
    if len(nums) < 2:
        return None
    mean = sum(nums) / len(nums)
    downside = [r for r in nums if r < 0]
    if not downside:
        return None
    dstd = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
    if dstd == 0:
        return None
    return mean / dstd * math.sqrt(periods_per_year)


def clamp_limit(raw: Any, default: int, maximum: int, minimum: int = 1) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name="limit")
    return max(minimum, min(value, maximum))


def pick_enum(raw: Any, allowed: Mapping[str, Any] | set[str], field_name: str, default=None):
    if raw in (None, ""):
        return default
    key = str(raw).lower()
    if key not in allowed:
        raise ApiError(ErrorCode.VALIDATION_FAILED, field_name=field_name)
    return key
