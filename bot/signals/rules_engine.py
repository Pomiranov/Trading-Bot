"""Движок торговых правил — читает rules.yaml и оценивает сигналы."""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from config import config
from signals.indicators import IndicatorValues

logger = logging.getLogger(__name__)


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class RuleResult:
    name: str
    action: Action
    triggered: bool
    weight: float
    description: str = ""


@dataclass
class SignalResult:
    action: Action
    score: float
    triggered_rules: list[RuleResult] = field(default_factory=list)
    buy_score: float = 0.0
    sell_score: float = 0.0

    def __str__(self) -> str:
        rules_str = ", ".join(r.name for r in self.triggered_rules)
        return (
            f"Сигнал: {self.action.value} | "
            f"Покупка: {self.buy_score:.2f} | "
            f"Продажа: {self.sell_score:.2f} | "
            f"Правила: [{rules_str}]"
        )


class RulesEngine:
    """Оценивает торговые правила из YAML-файла на основе значений индикаторов."""

    def __init__(self, rules_file: Path = None):
        self.rules_file = rules_file or config.rules_file
        self._rules: list[dict] = []
        self._settings: dict = {}
        self._load()

    def _load(self) -> None:
        if not self.rules_file.exists():
            logger.error("Файл правил не найден: %s", self.rules_file)
            return
        with open(self.rules_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._rules = data.get("rules", [])
        self._settings = data.get("settings", {})
        logger.info("Загружено %d правил из %s", len(self._rules), self.rules_file)

    def reload(self) -> None:
        """Перезагрузить правила из файла (горячая перезагрузка)."""
        self._load()

    def evaluate(self, indicators: IndicatorValues) -> SignalResult:
        """Оценить все правила и вернуть агрегированный сигнал."""
        ind_dict = self._indicators_to_dict(indicators)

        min_buy = self._settings.get("min_buy_score", 2.0)
        min_sell = self._settings.get("min_sell_score", 2.0)
        min_rules = self._settings.get("confirmation_rules", 2)

        buy_score = 0.0
        sell_score = 0.0
        triggered: list[RuleResult] = []

        for rule in self._rules:
            result = self._evaluate_rule(rule, ind_dict)
            if result.triggered:
                triggered.append(result)
                if result.action == Action.BUY:
                    buy_score += result.weight
                elif result.action == Action.SELL:
                    sell_score += result.weight

        buy_rules = [r for r in triggered if r.action == Action.BUY]
        sell_rules = [r for r in triggered if r.action == Action.SELL]

        if buy_score >= min_buy and len(buy_rules) >= min_rules and buy_score > sell_score:
            action = Action.BUY
            score = buy_score
        elif sell_score >= min_sell and len(sell_rules) >= min_rules and sell_score > buy_score:
            action = Action.SELL
            score = sell_score
        else:
            action = Action.HOLD
            score = max(buy_score, sell_score)

        return SignalResult(
            action=action,
            score=score,
            triggered_rules=triggered,
            buy_score=buy_score,
            sell_score=sell_score,
        )

    def _evaluate_rule(self, rule: dict, ind: dict[str, Any]) -> RuleResult:
        action = Action(rule.get("action", "HOLD"))
        weight = float(rule.get("weight", 1.0))
        name = rule.get("name", "unknown")
        description = rule.get("description", "")

        conditions = rule.get("conditions", [])
        triggered = all(self._check_condition(c, ind) for c in conditions)

        return RuleResult(
            name=name,
            action=action,
            triggered=triggered,
            weight=weight,
            description=description,
        )

    @staticmethod
    def _check_condition(condition: dict, ind: dict[str, Any]) -> bool:
        indicator = condition.get("indicator")
        operator = condition.get("operator")
        raw_value = condition.get("value")

        lhs = ind.get(indicator)
        if lhs is None:
            return False
        if isinstance(lhs, float) and math.isnan(lhs):
            return False

        # Значение может ссылаться на другой индикатор
        if isinstance(raw_value, str) and raw_value in ind:
            rhs = ind[raw_value]
        else:
            rhs = raw_value

        if rhs is None or (isinstance(rhs, float) and math.isnan(rhs)):
            return False

        try:
            if operator == ">":
                return float(lhs) > float(rhs)
            elif operator == "<":
                return float(lhs) < float(rhs)
            elif operator == ">=":
                return float(lhs) >= float(rhs)
            elif operator == "<=":
                return float(lhs) <= float(rhs)
            elif operator == "==":
                if isinstance(rhs, bool) or rhs in (True, False, "true", "false"):
                    rhs_bool = rhs if isinstance(rhs, bool) else rhs == "true"
                    return bool(lhs) == rhs_bool
                return lhs == rhs
            else:
                logger.warning("Неизвестный оператор: %s", operator)
                return False
        except (TypeError, ValueError) as exc:
            logger.debug("Ошибка проверки условия %s %s %s: %s", indicator, operator, rhs, exc)
            return False

    @staticmethod
    def _indicators_to_dict(iv: IndicatorValues) -> dict[str, Any]:
        return {
            "rsi": iv.rsi,
            "macd": iv.macd,
            "macd_signal": iv.macd_signal,
            "macd_hist": iv.macd_hist,
            "ema_fast": iv.ema_fast,
            "ema_slow": iv.ema_slow,
            "atr": iv.atr,
            "bb_upper": iv.bb_upper,
            "bb_middle": iv.bb_middle,
            "bb_lower": iv.bb_lower,
            "bb_pct": iv.bb_pct,
            "adx": iv.adx,
            "adx_pos": iv.adx_pos,
            "adx_neg": iv.adx_neg,
            "vwap": iv.vwap,
            "close": iv.close,
            # Вычисляемые свойства
            "macd_bullish_cross": iv.macd_bullish_cross,
            "macd_bearish_cross": iv.macd_bearish_cross,
            "price_above_ema_fast": iv.price_above_ema_fast,
            "price_above_ema_slow": iv.price_above_ema_slow,
            "trend_strong": iv.trend_strong,
            "rsi_oversold": iv.rsi_oversold,
            "rsi_overbought": iv.rsi_overbought,
        }


rules_engine = RulesEngine()
