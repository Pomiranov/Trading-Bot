"""Движок торговых правил — читает rules.yaml и оценивает сигналы.

Поддерживаемые секции rules.yaml:
  rules          — основные сигналы BUY / SELL
  filters        — блокировки торговли (action: BLOCK)
  exit_rules     — выходы из открытой позиции (action: EXIT)
  ticker_specific — правила для конкретного тикера (поле ticker:)
  macro_filters  — рыночный режим: BLOCK (↓50% весов) / ALLOW (+20% весов)

SignalResult содержит:
  action     — BUY | SELL | HOLD | BLOCK | EXIT
  confidence — 0.0 … 1.0
  reason     — объяснение сигнала на русском языке
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

from config import config
from signals.indicators import IndicatorValues

logger = logging.getLogger(__name__)


# ── Классификация рыночного режима ───────────────────────────────────────
# Пороги ADX совпадают с разметкой market_regime сделок в learning/
# (см. _regime_from_adx в backtest/engine.py) — иначе фильтр
# market_regime_in сравнивал бы несовместимые классификации.

ADX_TRENDING_MIN = 25
ADX_RANGING_MAX  = 20


def classify_regime(adx: Optional[float]) -> Optional[str]:
    """ADX → режим рынка: trending / ranging / volatile (переходная зона)."""
    if adx is None or not math.isfinite(adx):
        return None
    if adx >= ADX_TRENDING_MIN:
        return "trending"
    if adx < ADX_RANGING_MAX:
        return "ranging"
    return "volatile"


# ── Действия ─────────────────────────────────────────────────────────────

class Action(str, Enum):
    BUY   = "BUY"
    SELL  = "SELL"
    HOLD  = "HOLD"
    BLOCK = "BLOCK"   # фильтр запретил открывать новые позиции
    EXIT  = "EXIT"    # правило выхода требует закрыть открытую позицию
    ALLOW = "ALLOW"   # макро-режим risk-on (внутреннее, не возвращается пользователю)


# ── Результат одного правила ─────────────────────────────────────────────

@dataclass
class RuleResult:
    name: str
    action: Action
    triggered: bool
    weight: float
    description: str = ""
    ticker: str = ""          # для ticker_specific правил


# ── Итоговый сигнал ──────────────────────────────────────────────────────

@dataclass
class SignalResult:
    action: Action
    score: float
    confidence: float = 0.0          # 0.0 … 1.0
    reason: str = ""                 # объяснение на русском
    triggered_rules: list[RuleResult] = field(default_factory=list)
    buy_score: float = 0.0
    sell_score: float = 0.0
    blocked: bool = False            # True если сработал filter или macro BLOCK
    exit_triggered: bool = False     # True если сработал exit_rule

    def __str__(self) -> str:
        rules_str = ", ".join(r.name for r in self.triggered_rules)
        return (
            f"Сигнал: {self.action.value} | "
            f"Уверенность: {self.confidence:.0%} | "
            f"Покупка: {self.buy_score:.2f} | "
            f"Продажа: {self.sell_score:.2f} | "
            f"Правила: [{rules_str}]"
        )


# ── Движок правил ────────────────────────────────────────────────────────

class RulesEngine:
    """Оценивает торговые правила из YAML-файла на основе значений индикаторов.

    Параметр extended=False включает legacy-режим: используется только секция
    «rules» (поведение идентично исходному движку до добавления новых секций).
    """

    def __init__(self, rules_file: Path = None, extended: bool = True):
        self.rules_file = rules_file or config.rules_file
        self.extended = extended
        self._rules: list[dict] = []
        self._filters: list[dict] = []
        self._named_filters: dict = {}
        self._divergence: dict = {}
        self._swing_stop: dict = {}
        self._wrd: dict = {}
        self._indicators_cfg: dict = {}
        self._exit_rules: list[dict] = []
        self._ticker_specific: list[dict] = []
        self._macro_filters: list[dict] = []
        self._settings: dict = {}
        self._load()

    # ── Загрузка/перезагрузка ────────────────────────────────────────

    def _load(self) -> None:
        if not self.rules_file.exists():
            logger.error("Файл правил не найден: %s", self.rules_file)
            return
        with open(self.rules_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._rules   = data.get("rules", [])
        self._settings = data.get("settings", {})
        self._divergence = data.get("divergence") or {}
        self._swing_stop = data.get("swing_stop") or {}
        self._wrd = data.get("wrd") or {}
        self._indicators_cfg = data.get("indicators") or {}

        if self.extended:
            raw_filters = data.get("filters") or []
            # Две формы секции filters:
            #   список  — generic BLOCK-правила (evaluate() проверяет условия);
            #   словарь — именованные фильтры с параметрами, которые применяет
            #             вызывающий код (бэктест/оркестратор), напр.
            #             structural_downtrend для osc_range_moex.
            if isinstance(raw_filters, dict):
                self._filters = []
                self._named_filters = raw_filters
            else:
                self._filters = raw_filters
                self._named_filters = {}
            self._exit_rules      = data.get("exit_rules", [])
            self._ticker_specific = data.get("ticker_specific", [])
            self._macro_filters   = data.get("macro_filters", [])
        else:
            self._filters = self._exit_rules = self._ticker_specific = self._macro_filters = []
            self._named_filters = {}

        logger.info(
            "Загружено правил: основных=%d, фильтров=%d, выходов=%d, тикерных=%d, макро=%d",
            len(self._rules), len(self._filters), len(self._exit_rules),
            len(self._ticker_specific), len(self._macro_filters),
        )

    def reload(self) -> None:
        """Горячая перезагрузка правил из файла."""
        self._load()

    @property
    def divergence_params(self) -> dict:
        """Параметры детектора расхождений → kwargs для IndicatorEngine.

        Маппинг yaml-имён (swing_window, max_gap, pair_search_max) на
        аргументы IndicatorEngine (pivot_strength, pivot_max_age,
        pair_search_max). {} — если секции divergence в rules-файле нет
        (используются дефолты движка индикаторов).
        """
        mapping = {
            "swing_window":    "pivot_strength",
            "max_gap":         "pivot_max_age",
            "pair_search_max": "pair_search_max",
        }
        return {
            arg: int(self._divergence[key])
            for key, arg in mapping.items()
            if key in self._divergence
        }

    @property
    def swing_stop_params(self) -> dict:
        """Параметры трейлинга по свинг-минимумам (Швагер, гл. 9, метод 5)
        → kwargs для IndicatorEngine. {} — секции swing_stop в rules-файле
        нет (колонка swing_low не считается, правило по ней молчит)."""
        if "window" not in self._swing_stop:
            return {}
        return {"swing_stop_window": int(self._swing_stop["window"])}

    @property
    def wrd_params(self) -> dict:
        """Параметры системы ШД-дня (Швагер, гл. 18) → kwargs для
        IndicatorEngine. {} — секции wrd в rules-файле нет (колонки
        wrd_day/ptr_high/ptr_low не считаются, правила по ним молчат)."""
        if "k" not in self._wrd:
            return {}
        mapping = {
            "k":     ("wrd_k", float),
            "atr_n": ("wrd_atr_n", int),
            "n1":    ("wrd_n1", int),
            "n2":    ("wrd_n2", int),
        }
        return {
            arg: cast(self._wrd[key])
            for key, (arg, cast) in mapping.items()
            if key in self._wrd
        }

    @property
    def indicator_params(self) -> dict:
        """Переопределения периодов индикаторов из секции indicators
        rules-файла → kwargs для IndicatorEngine. {} — секции нет,
        используются дефолты движка индикаторов.

        Пропускаются только известные IndicatorEngine аргументы, чтобы
        опечатка в yaml не роняла конструктор."""
        allowed = {
            "rsi_period", "macd_fast", "macd_slow", "macd_signal",
            "ema_fast", "ema_slow", "atr_period", "bb_period", "bb_std",
            "adx_period",
        }
        return {
            k: (float(v) if k == "bb_std" else int(v))
            for k, v in self._indicators_cfg.items()
            if k in allowed
        }

    @property
    def structural_downtrend_filter(self) -> dict:
        """Конфиг фильтра структурного даунтренда ({} если выключен/нет).

        Параметры для signals.indicators.structural_downtrend_series
        плюс служебные ключи enabled и apply_to.
        """
        cfg = self._named_filters.get("structural_downtrend") or {}
        return cfg if cfg.get("enabled") else {}

    # ── Основная оценка ──────────────────────────────────────────────

    def evaluate(self, indicators: IndicatorValues, ticker: str = "") -> SignalResult:
        """Оценить все правила и вернуть агрегированный сигнал.

        Возвращаемый SignalResult содержит:
          action     — BUY | SELL | HOLD | BLOCK
          confidence — 0.0 … 1.0
          reason     — строка на русском языке
        """
        ind = self._to_dict(indicators)
        min_buy   = self._settings.get("min_buy_score", 2.0)
        min_sell  = self._settings.get("min_sell_score", 2.0)
        min_rules = self._settings.get("confirmation_rules", 2)

        # ── 1. Фильтры блокировки (проверяются первыми) ──────────────
        for f_rule in self._filters:
            res = self._eval_rule(f_rule, ind)
            if res.triggered:
                return SignalResult(
                    action=Action.BLOCK,
                    score=0.0,
                    confidence=1.0,
                    reason=f"Торговля заблокирована: {res.description or res.name}",
                    triggered_rules=[res],
                    blocked=True,
                )

        # ── 2. Макро-фильтры (корректируют веса основных правил) ─────
        macro_modifier = 1.0
        macro_block    = False
        macro_allow    = False
        macro_hit: list[RuleResult] = []

        for mf in self._macro_filters:
            res = self._eval_rule(mf, ind)
            if res.triggered:
                macro_hit.append(res)
                if res.action == Action.BLOCK:
                    macro_block = True
                elif res.action == Action.ALLOW:
                    macro_allow = True

        if macro_block and not macro_allow:
            macro_modifier = 0.5        # широкий рынок падает — снижаем доверие
        elif macro_allow and not macro_block:
            macro_modifier = 1.2        # risk-on режим — усиливаем сигналы
        elif macro_block and macro_allow:
            macro_modifier = 0.85       # противоречие — умеренная осторожность

        # ── 3. Основные правила BUY / SELL ───────────────────────────
        buy_score  = 0.0
        sell_score = 0.0
        triggered: list[RuleResult] = []

        for rule in self._rules:
            res = self._eval_rule(rule, ind)
            if res.triggered:
                triggered.append(res)
                if res.action == Action.BUY:
                    buy_score  += res.weight * macro_modifier
                elif res.action == Action.SELL:
                    sell_score += res.weight * macro_modifier

        # ── 4. Тикер-специфичные правила ─────────────────────────────
        ticker_blocked = False
        for tr in self._ticker_specific:
            if tr.get("ticker", "") != ticker:
                continue
            res = self._eval_rule(tr, ind)
            if not res.triggered:
                continue
            triggered.append(res)
            if res.action == Action.BLOCK:
                ticker_blocked = True
            elif res.action == Action.BUY:
                buy_score  += res.weight
            elif res.action == Action.SELL:
                sell_score += res.weight

        if ticker_blocked:
            block_rule = next((r for r in triggered if r.action == Action.BLOCK), None)
            desc = block_rule.description if block_rule else "условие тикера"
            return SignalResult(
                action=Action.BLOCK,
                score=0.0,
                confidence=1.0,
                reason=f"Блокировка для {ticker}: {desc}",
                triggered_rules=triggered + macro_hit,
                blocked=True,
            )

        # ── 5. Итоговый сигнал ────────────────────────────────────────
        buy_rules  = [r for r in triggered if r.action == Action.BUY]
        sell_rules = [r for r in triggered if r.action == Action.SELL]

        if buy_score >= min_buy and len(buy_rules) >= min_rules and buy_score > sell_score:
            action = Action.BUY
            score  = buy_score
        elif sell_score >= min_sell and len(sell_rules) >= min_rules and sell_score > buy_score:
            action = Action.SELL
            score  = sell_score
        else:
            action = Action.HOLD
            score  = max(buy_score, sell_score)

        confidence = self._calc_confidence(action, buy_score, sell_score, min_buy, min_sell)
        reason     = self._build_reason(
            action, triggered, macro_hit, buy_score, sell_score, macro_block, macro_allow
        )

        return SignalResult(
            action=action,
            score=score,
            confidence=confidence,
            reason=reason,
            triggered_rules=triggered + macro_hit,
            buy_score=buy_score,
            sell_score=sell_score,
        )

    # ── Оценка правил выхода ─────────────────────────────────────────

    def evaluate_exit(self, indicators: IndicatorValues, ticker: str = "") -> SignalResult:
        """Проверить exit_rules для открытой позиции.

        Возвращает SignalResult с action=EXIT если правило сработало,
        иначе action=HOLD.
        """
        if not self._exit_rules:
            return SignalResult(
                action=Action.HOLD,
                score=0.0,
                confidence=0.0,
                reason="Правила выхода не загружены",
            )

        ind = self._to_dict(indicators)
        for rule in self._exit_rules:
            res = self._eval_rule(rule, ind)
            if res.triggered:
                return SignalResult(
                    action=Action.EXIT,
                    score=res.weight,
                    confidence=0.9,
                    reason=f"Выход из позиции: {res.description or res.name}",
                    triggered_rules=[res],
                    exit_triggered=True,
                )

        return SignalResult(
            action=Action.HOLD,
            score=0.0,
            confidence=0.5,
            reason="Условия выхода не выполнены — держим позицию",
        )

    # ── Вычисление уверенности ───────────────────────────────────────

    @staticmethod
    def _calc_confidence(
        action: Action,
        buy_score: float,
        sell_score: float,
        min_buy: float,
        min_sell: float,
    ) -> float:
        """Рассчитать уверенность в диапазоне 0.0 … 1.0.

        BUY/SELL: доля доминирующего счёта + бонус за превышение порога.
        HOLD:     насколько далеко от порога (чем дальше — тем увереннее HOLD).
        """
        if action == Action.BLOCK:
            return 1.0

        if action in (Action.BUY, Action.SELL):
            dominant  = buy_score  if action == Action.BUY else sell_score
            threshold = min_buy    if action == Action.BUY else min_sell
            total     = buy_score + sell_score
            dominance = dominant / total if total > 0 else 0.5
            excess    = max(0.0, dominant - threshold) / max(threshold, 1.0)
            raw       = dominance * 0.55 + min(excess * 0.25, 0.3) + 0.15
            return round(min(1.0, max(0.0, raw)), 3)

        # HOLD
        max_score = max(buy_score, sell_score)
        threshold = max(min_buy, min_sell)
        return round(max(0.0, 1.0 - max_score / threshold) if threshold else 0.0, 3)

    # ── Формирование объяснения ──────────────────────────────────────

    @staticmethod
    def _build_reason(
        action: Action,
        triggered: list[RuleResult],
        macro_hit: list[RuleResult],
        buy_score: float,
        sell_score: float,
        macro_block: bool,
        macro_allow: bool,
    ) -> str:
        parts: list[str] = []

        if action == Action.BUY:
            buy_rules = [r for r in triggered if r.action == Action.BUY]
            parts.append(f"Сигнал на покупку (счёт {buy_score:.1f})")
            if buy_rules:
                descs = "; ".join(r.description or r.name for r in buy_rules[:3])
                parts.append(f"Правила: {descs}")

        elif action == Action.SELL:
            sell_rules = [r for r in triggered if r.action == Action.SELL]
            parts.append(f"Сигнал на продажу (счёт {sell_score:.1f})")
            if sell_rules:
                descs = "; ".join(r.description or r.name for r in sell_rules[:3])
                parts.append(f"Правила: {descs}")

        elif action == Action.HOLD:
            if not triggered:
                parts.append("Нет достаточных сигналов — ждём")
            else:
                parts.append(
                    f"Конфликт сигналов (покупка {buy_score:.1f} vs продажа {sell_score:.1f}) — ждём"
                )

        if macro_block:
            descs = [r.description or r.name for r in macro_hit if r.action == Action.BLOCK]
            if descs:
                parts.append("Макро-осторожность: " + "; ".join(descs))
        elif macro_allow:
            parts.append("Рыночный режим risk-on — веса повышены на 20%")

        return ". ".join(parts) if parts else "Нет данных"

    # ── Вспомогательные методы ───────────────────────────────────────

    def _eval_rule(self, rule: dict, ind: dict[str, Any]) -> RuleResult:
        raw_action = rule.get("action", "HOLD")
        try:
            action = Action(raw_action)
        except ValueError:
            action = Action.HOLD

        conditions = rule.get("conditions", [])

        # Фильтр по рыночному режиму (источник — belief_system.best_regime):
        # правило срабатывает только в перечисленных режимах.
        # Неизвестный режим (нет ADX) считается несовпадением.
        allowed_regimes = rule.get("market_regime_in")
        regime_ok = (
            ind.get("market_regime") in allowed_regimes
            if allowed_regimes else True
        )

        triggered  = regime_ok and bool(conditions) and all(
            self._check_cond(c, ind) for c in conditions
        )

        return RuleResult(
            name=rule.get("name", "unknown"),
            action=action,
            triggered=triggered,
            weight=float(rule.get("weight", 1.0)),
            description=rule.get("description", ""),
            ticker=rule.get("ticker", ""),
        )

    @staticmethod
    def _check_cond(condition: dict, ind: dict[str, Any]) -> bool:
        indicator = condition.get("indicator")
        operator  = condition.get("operator")
        raw_value = condition.get("value")

        lhs = ind.get(indicator)
        if lhs is None or (isinstance(lhs, float) and math.isnan(lhs)):
            return False

        rhs = ind.get(raw_value, raw_value) if isinstance(raw_value, str) else raw_value
        if rhs is None or (isinstance(rhs, float) and math.isnan(rhs)):
            return False

        try:
            if operator == ">":
                return float(lhs) > float(rhs)
            if operator == "<":
                return float(lhs) < float(rhs)
            if operator == ">=":
                return float(lhs) >= float(rhs)
            if operator == "<=":
                return float(lhs) <= float(rhs)
            if operator == "==":
                if isinstance(rhs, bool) or rhs in (True, False, "true", "false"):
                    rhs_bool = rhs if isinstance(rhs, bool) else rhs == "true"
                    return bool(lhs) == rhs_bool
                return lhs == rhs
            logger.warning("Неизвестный оператор: %s", operator)
            return False
        except (TypeError, ValueError) as exc:
            logger.debug("Ошибка условия %s %s %s: %s", indicator, operator, rhs, exc)
            return False

    @staticmethod
    def _to_dict(iv: IndicatorValues) -> dict[str, Any]:
        return {
            "rsi":                  iv.rsi,
            "macd":                 iv.macd,
            "macd_signal":          iv.macd_signal,
            "macd_hist":            iv.macd_hist,
            "ema_fast":             iv.ema_fast,
            "ema_slow":             iv.ema_slow,
            "atr":                  iv.atr,
            "bb_upper":             iv.bb_upper,
            "bb_middle":            iv.bb_middle,
            "bb_lower":             iv.bb_lower,
            "bb_pct":               iv.bb_pct,
            "adx":                  iv.adx,
            "adx_pos":              iv.adx_pos,
            "adx_neg":              iv.adx_neg,
            "vwap":                 iv.vwap,
            "close":                iv.close,
            # рыночный режим (для market_regime_in в правилах)
            "market_regime":        classify_regime(iv.adx),
            # осцилляторный блок (Швагер/Бировиц, гл. 15)
            "rsi9":                 iv.rsi9,
            "stoch_k":              iv.stoch_k,
            "stoch_d":              iv.stoch_d,
            "mac_high":             iv.mac_high,
            "mac_low":              iv.mac_low,
            "bull_div_count":       iv.bull_div_count,
            "bear_div_count":       iv.bear_div_count,
            "micro_w_trigger":      iv.micro_w_trigger,
            "micro_m_trigger":      iv.micro_m_trigger,
            "div_low":              iv.div_low,
            "div_high":             iv.div_high,
            # трейлинг по свинг-минимумам (Швагер, гл. 9, метод 5)
            "swing_low":            iv.swing_low,
            # система ШД-дня (Швагер, гл. 18): границы действующего PTR
            "ptr_high":             iv.ptr_high,
            "ptr_low":              iv.ptr_low,
            # вычисляемые свойства
            "macd_bullish_cross":   iv.macd_bullish_cross,
            "macd_bearish_cross":   iv.macd_bearish_cross,
            "price_above_ema_fast": iv.price_above_ema_fast,
            "price_above_ema_slow": iv.price_above_ema_slow,
            "trend_strong":         iv.trend_strong,
            "rsi_oversold":         iv.rsi_oversold,
            "rsi_overbought":       iv.rsi_overbought,
        }


rules_engine = RulesEngine()
