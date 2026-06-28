"""Управление рисками: размер позиции через ATR, стоп-лосс, дневной лимит убытков."""

import logging
from dataclasses import dataclass
from typing import Optional

from config import config

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
        self._daily_pnl: float = 0.0
        self._open_positions: dict[str, PositionSizing] = {}

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
    ) -> RiskCheckResult:
        """Проверить, разрешена ли новая сделка по правилам риск-менеджмента."""

        # Лимит открытых позиций
        if len(self._open_positions) >= self.cfg.max_open_positions:
            return RiskCheckResult(
                allowed=False,
                reason=f"Достигнут лимит открытых позиций: {self.cfg.max_open_positions}",
            )

        # Уже в позиции по этому тикеру
        if ticker in self._open_positions:
            return RiskCheckResult(
                allowed=False,
                reason=f"Позиция по {ticker} уже открыта",
            )

        # Дневной лимит убытков
        max_daily_loss = portfolio_value * self.cfg.max_daily_loss_pct
        if self._daily_pnl <= -max_daily_loss:
            return RiskCheckResult(
                allowed=False,
                reason=(
                    f"Достигнут дневной лимит убытков: "
                    f"{self._daily_pnl:.2f} руб. (лимит -{max_daily_loss:.2f} руб.)"
                ),
            )

        # Размер позиции не превышает max_position_pct
        if position and position.position_value > portfolio_value * self.cfg.max_position_pct * 20:
            return RiskCheckResult(
                allowed=False,
                reason="Размер позиции превышает допустимый лимит",
            )

        return RiskCheckResult(allowed=True)

    # ─── Управление состоянием ────────────────────────────────────────

    def register_open(self, position: PositionSizing) -> None:
        """Зарегистрировать открытие позиции."""
        self._open_positions[position.ticker] = position
        logger.info("Открыта позиция: %s", position.ticker)

    def register_close(self, ticker: str, exit_price: float) -> float:
        """Зарегистрировать закрытие позиции, вернуть PnL."""
        position = self._open_positions.pop(ticker, None)
        if position is None:
            return 0.0

        pnl = (exit_price - position.entry_price) * position.shares
        self._daily_pnl += pnl
        logger.info(
            "Закрыта позиция %s: вход %.2f, выход %.2f, PnL %.2f руб.",
            ticker, position.entry_price, exit_price, pnl,
        )
        return pnl

    def reset_daily(self) -> None:
        """Сбросить суточный PnL (вызывать в начале торговой сессии)."""
        self._daily_pnl = 0.0
        logger.info("Дневной PnL сброшен")

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def open_positions(self) -> dict[str, PositionSizing]:
        return dict(self._open_positions)

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
        position = self._open_positions.get(ticker)
        if position is None:
            return None

        new_stop = current_price - atr * self.cfg.atr_stop_multiplier
        if new_stop > position.stop_price:
            logger.info(
                "Trailing stop %s: %.2f → %.2f",
                ticker, position.stop_price, new_stop,
            )
            position.stop_price = new_stop

        return position.stop_price


risk_manager = RiskManager()
