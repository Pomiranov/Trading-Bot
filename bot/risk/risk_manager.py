"""Управление рисками: размер позиции через ATR, стоп-лосс, дневной лимит убытков.

Open-position and daily-PnL state is persisted via risk/state_store.py
(a lock-guarded JSON file) rather than kept in an in-process dict: the
dashboard and the bot run as separate OS processes (start.sh), so two
independent in-memory copies would each enforce max_open_positions /
max_daily_loss_pct against an incomplete view. See state_store.py.
"""

import logging
from dataclasses import asdict, dataclass, fields
from typing import Optional

from config import config
from risk.state_store import transaction

logger = logging.getLogger(__name__)


@dataclass
class PositionSizing:
    ticker: str
    entry_price: float
    stop_price: float
    lot_size: int          # количество лотов
    shares: int            # количество акций
    risk_amount: float     # рублёвый риск на сделку
    position_value: float  # стоимость позиции

    @property
    def risk_reward_needed(self) -> float:
        """Минимальный R:R 2:1 подразумевает тейк-профит на этом уровне."""
        distance = abs(self.entry_price - self.stop_price)
        return self.entry_price + 2 * distance

    @classmethod
    def from_dict(cls, data: dict) -> "PositionSizing":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: str = ""


class RiskManager:
    """
    Управляет рисками торговой сессии.

    - Размер позиции через метод фиксированного процента риска (% капитала / риск на акцию).
    - Стоп-лосс рассчитывается как ATR × множитель.
    - Ограничивает дневные убытки и максимальное количество открытых позиций.
    """

    def __init__(self):
        self.cfg = config.risk

    # ─── Размер позиции ───────────────────────────────────────────────

    def calculate_position(
        self,
        ticker: str,
        entry_price: float,
        atr: float,
        portfolio_value: float,
        lot_size: int = 1,
        direction: str = "long",
    ) -> Optional[PositionSizing]:
        """
        Рассчитать размер позиции по методу ATR-стоп.

        Риск на сделку = portfolio_value × max_position_pct.
        Стоп-лосс = ATR × atr_stop_multiplier.
        Количество акций = риск / расстояние до стопа.
        """
        if not (atr > 0) or not (entry_price > 0) or not (portfolio_value > 0):
            logger.warning("Некорректные параметры для расчёта позиции: %s", ticker)
            return None

        stop_distance = atr * self.cfg.atr_stop_multiplier

        if direction == "long":
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return None

        max_risk_amount = portfolio_value * self.cfg.max_position_pct
        raw_shares = max_risk_amount / risk_per_share

        # Округляем до целого числа лотов
        lots = max(1, int(raw_shares / lot_size))
        shares = lots * lot_size

        position_value = shares * entry_price
        actual_risk = shares * risk_per_share

        # Ограничиваем позицию доступным капиталом (некредитная стратегия)
        if position_value > portfolio_value:
            lots = max(1, int(portfolio_value / (entry_price * lot_size)))
            shares = lots * lot_size
            position_value = shares * entry_price
            actual_risk = shares * risk_per_share

        logger.info(
            "Позиция %s: %d лотов (%d акций), вход %.2f, стоп %.2f, риск %.2f руб.",
            ticker, lots, shares, entry_price, stop_price, actual_risk,
        )

        return PositionSizing(
            ticker=ticker,
            entry_price=entry_price,
            stop_price=stop_price,
            lot_size=lots,
            shares=shares,
            risk_amount=actual_risk,
            position_value=position_value,
        )

    # ─── Проверки перед сделкой ───────────────────────────────────────

    def check_trade_allowed(
        self,
        ticker: str,
        portfolio_value: float,
        position: Optional[PositionSizing] = None,
        direction: str = "buy",
    ) -> RiskCheckResult:
        """Проверить, разрешена ли сделка по правилам риск-менеджмента."""

        is_buy = direction.lower() in ("buy", "long")

        with transaction() as state:
            pos_count = len(state["open_positions"])
            has_ticker = ticker in state["open_positions"]
            daily_pnl = state["daily_pnl"]

        if is_buy:
            # Лимит открытых позиций
            if pos_count >= self.cfg.max_open_positions:
                return RiskCheckResult(
                    allowed=False,
                    reason=f"Достигнут лимит открытых позиций: {self.cfg.max_open_positions}",
                )

            # Уже в позиции по этому тикеру
            if has_ticker:
                return RiskCheckResult(
                    allowed=False,
                    reason=f"Позиция по {ticker} уже открыта",
                )

        # Дневной лимит убытков
        max_daily_loss = portfolio_value * self.cfg.max_daily_loss_pct
        if daily_pnl <= -max_daily_loss:
            return RiskCheckResult(
                allowed=False,
                reason=(
                    f"Достигнут дневной лимит убытков: "
                    f"{daily_pnl:.2f} руб. (лимит -{max_daily_loss:.2f} руб.)"
                ),
            )

        # Размер позиции не превышает разумный множитель риска на сделку.
        # max_position_pct — это доля капитала, которой готовы рискнуть (риск
        # до стопа), а не сама заявка: при узком стопе номинал позиции
        # закономерно в разы больше риска. 20x — грубый потолок "не более
        # 20 таких риск-порций в одной позиции", подобранный эмпирически;
        # если стратегия сама требует иного, править здесь.
        if position and position.position_value > portfolio_value * self.cfg.max_position_pct * _POSITION_VALUE_SANITY_MULTIPLIER:
            return RiskCheckResult(
                allowed=False,
                reason="Размер позиции превышает допустимый лимит",
            )

        return RiskCheckResult(allowed=True)

    # ─── Управление состоянием ────────────────────────────────────────

    def register_open(self, position: PositionSizing) -> None:
        """Зарегистрировать открытие позиции."""
        with transaction() as state:
            state["open_positions"][position.ticker] = asdict(position)
        logger.info("Открыта позиция: %s", position.ticker)

    def register_close(self, ticker: str, exit_price: float) -> float:
        """Зарегистрировать закрытие позиции, вернуть PnL."""
        with transaction() as state:
            data = state["open_positions"].pop(ticker, None)
            if data is None:
                return 0.0
            position = PositionSizing.from_dict(data)
            pnl = (exit_price - position.entry_price) * position.shares
            state["daily_pnl"] += pnl

        logger.info(
            "Закрыта позиция %s: вход %.2f, выход %.2f, PnL %.2f руб.",
            ticker, position.entry_price, exit_price, pnl,
        )
        return pnl

    def reset_daily(self) -> None:
        """Сбросить суточный PnL (вызывать в начале торговой сессии)."""
        with transaction() as state:
            state["daily_pnl"] = 0.0
        logger.info("Дневной PnL сброшен")

    @property
    def daily_pnl(self) -> float:
        with transaction() as state:
            return state["daily_pnl"]

    @property
    def open_positions(self) -> dict[str, PositionSizing]:
        with transaction() as state:
            return {
                ticker: PositionSizing.from_dict(data)
                for ticker, data in state["open_positions"].items()
            }

    def trailing_stop(
        self,
        ticker: str,
        current_price: float,
        atr: float,
    ) -> Optional[float]:
        """
        Рассчитать скользящий стоп для открытой позиции.
        Возвращает новый уровень стоп-лосса или None если позиция не найдена.
        """
        with transaction() as state:
            data = state["open_positions"].get(ticker)
            if data is None:
                return None
            position = PositionSizing.from_dict(data)

            new_stop = current_price - atr * self.cfg.atr_stop_multiplier
            if new_stop > position.stop_price:
                logger.info(
                    "Trailing stop %s: %.2f → %.2f",
                    ticker, position.stop_price, new_stop,
                )
                position.stop_price = new_stop
                state["open_positions"][ticker] = asdict(position)

            return position.stop_price

    def reconcile_with_broker(self, broker_positions: dict[str, dict]) -> list[str]:
        """
        Выровнять внутренний трекер с реальными позициями у брокера.

        Защищает от главного риска рассинхронизации: сетевая ошибка при
        выставлении заявки может означать как "заявка не прошла", так и
        "заявка прошла, но ответ не дошёл" — во втором случае трекер думает,
        что позиции нет, и на следующем цикле стратегия открывает такую же
        позицию повторно. Источник истины — брокер; трекер подстраивается
        под него, расхождения возвращаются как сообщения для алерта.

        broker_positions: {ticker: {"avg_price": float, "lots": int}} —
        текущие реальные позиции у брокера.
        """
        messages: list[str] = []
        with transaction() as state:
            tracked = state["open_positions"]
            tracked_tickers = set(tracked)
            broker_tickers = set(broker_positions)

            for ticker in sorted(broker_tickers - tracked_tickers):
                info = broker_positions[ticker]
                avg_price = float(info.get("avg_price") or 0)
                lots = int(info.get("lots") or 0)
                # Стоп неизвестен — используем цену входа как временный,
                # консервативный (более тесный, а не более широкий) стоп до
                # ручной проверки оператором, а не гадаем реальный уровень.
                tracked[ticker] = asdict(PositionSizing(
                    ticker=ticker,
                    entry_price=avg_price,
                    stop_price=avg_price,
                    lot_size=lots,
                    shares=lots,
                    risk_amount=0.0,
                    position_value=avg_price * lots,
                ))
                messages.append(
                    f"{ticker}: позиция у брокера отсутствовала во внутреннем трекере — "
                    f"импортирована (стоп-лосс требует ручной проверки)"
                )

            for ticker in sorted(tracked_tickers - broker_tickers):
                del tracked[ticker]
                messages.append(
                    f"{ticker}: позиция закрыта у брокера, но оставалась во внутреннем "
                    f"трекере — снята"
                )

        for msg in messages:
            logger.warning("Risk reconciliation: %s", msg)
        return messages


_POSITION_VALUE_SANITY_MULTIPLIER = 20

risk_manager = RiskManager()
