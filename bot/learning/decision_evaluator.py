"""
QuantFlow — decision_evaluator.py
=================================
Оценивает КАЧЕСТВО торгового решения независимо от его результата.

Главный принцип (из системного промпта):
    "Самообучение никогда не должно основываться только на прибыли или убытке."

Хорошее решение может привести к убытку (рынок пошёл против).
Плохое решение может принести прибыль (просто повезло).
Этот модуль отличает одно от другого.

Заполняет поля в таблице trades:
    - decision_quality   (0.0–1.0) — насколько хорошим было решение
    - strategy_followed  (bool)    — соблюдена ли стратегия
    - randomness_factor  (0.0–1.0) — сколько в результате случайности

Использование:
    evaluator = DecisionEvaluator()
    await evaluator.connect()
    await evaluator.evaluate_trade(trade_id)
"""

import logging
from decimal import Decimal
from typing import Optional

import asyncpg

logger = logging.getLogger("quantflow.evaluator")


# ============================================================
# ВЕСА КОМПОНЕНТОВ ОЦЕНКИ
# Сумма = 1.0
# ============================================================

WEIGHT_STRATEGY_FOLLOWED = Decimal("0.30")  # соблюдение стратегии
WEIGHT_ENTRY_QUALITY     = Decimal("0.20")  # качество входа
WEIGHT_RISK_DISCIPLINE   = Decimal("0.25")  # дисциплина риска
WEIGHT_REGIME_MATCH      = Decimal("0.15")  # соответствие режиму
WEIGHT_EXECUTION         = Decimal("0.10")  # качество исполнения


# ============================================================
# КЛАСС: DecisionEvaluator
# ============================================================

class DecisionEvaluator:
    """Оценивает качество торговых решений."""

    def __init__(self, dsn: Optional[str] = None):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        import os
        from dotenv import load_dotenv
        load_dotenv()

        if self._dsn is None:
            host     = os.getenv("DB_HOST", "localhost")
            port     = os.getenv("DB_PORT", "5432")
            name     = os.getenv("DB_NAME", "trading_bot")
            user     = os.getenv("DB_USER", "trader")
            password = os.getenv("DB_PASSWORD", "")
            self._dsn = f"postgresql://{user}:{password}@{host}:{port}/{name}"

        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        logger.info("DecisionEvaluator: подключение к БД установлено")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()

    # ----------------------------------------------------------
    # ГЛАВНЫЙ МЕТОД: оценить сделку
    # ----------------------------------------------------------

    async def evaluate_trade(self, trade_id: str) -> dict:
        """
        Оценить качество решения по сделке.
        Записывает результат обратно в таблицу trades.
        """
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            trade = await conn.fetchrow("""
                SELECT * FROM trades WHERE trade_id = $1
            """, trade_id)

            if not trade:
                raise ValueError(f"Сделка {trade_id} не найдена")

            # Считаем все компоненты
            evaluation = self._evaluate(trade)

            # Записываем обратно
            await conn.execute("""
                UPDATE trades SET
                    decision_quality  = $2,
                    strategy_followed = $3,
                    randomness_factor = $4
                WHERE trade_id = $1
            """,
                trade_id,
                evaluation["decision_quality"],
                evaluation["strategy_followed"],
                evaluation["randomness_factor"],
            )

        logger.info(
            f"Сделка {str(trade_id)[:8]} оценена: "
            f"quality={evaluation['decision_quality']:.2f}, "
            f"randomness={evaluation['randomness_factor']:.2f}"
        )
        return evaluation

    # ----------------------------------------------------------
    # ЛОГИКА ОЦЕНКИ
    # ----------------------------------------------------------

    def _evaluate(self, trade) -> dict:
        """Оценить решение по пяти компонентам."""

        # --- Компонент 1: Соблюдение стратегии ---
        strategy_followed = self._check_strategy_followed(trade)
        score_strategy = Decimal("1.0") if strategy_followed else Decimal("0.0")

        # --- Компонент 2: Качество входа ---
        score_entry = self._evaluate_entry(trade)

        # --- Компонент 3: Дисциплина риска ---
        score_risk = self._evaluate_risk_discipline(trade)

        # --- Компонент 4: Соответствие режиму ---
        score_regime = self._evaluate_regime_match(trade)

        # --- Компонент 5: Качество исполнения ---
        score_execution = self._evaluate_execution(trade)

        # Итоговое качество решения (взвешенная сумма)
        decision_quality = (
            score_strategy   * WEIGHT_STRATEGY_FOLLOWED +
            score_entry      * WEIGHT_ENTRY_QUALITY +
            score_risk       * WEIGHT_RISK_DISCIPLINE +
            score_regime     * WEIGHT_REGIME_MATCH +
            score_execution  * WEIGHT_EXECUTION
        )

        # Фактор случайности — насколько результат объясняется удачей
        randomness = self._evaluate_randomness(trade, decision_quality)

        return {
            "decision_quality":  decision_quality.quantize(Decimal("0.0001")),
            "strategy_followed": strategy_followed,
            "randomness_factor": randomness.quantize(Decimal("0.0001")),
            "components": {
                "strategy":  float(score_strategy),
                "entry":     float(score_entry),
                "risk":      float(score_risk),
                "regime":    float(score_regime),
                "execution": float(score_execution),
            }
        }

    # ----------------------------------------------------------
    # КОМПОНЕНТ 1: Соблюдение стратегии
    # ----------------------------------------------------------

    def _check_strategy_followed(self, trade) -> bool:
        """
        Проверить что сделка соответствовала своей стратегии.
        Основной критерий: был ли задан стоп-лосс и причина входа.
        """
        # Стоп-лосс обязателен всегда (железное правило)
        if trade["stop_loss"] is None or trade["stop_loss"] <= 0:
            return False

        # Причина входа должна быть указана
        if not trade["entry_reason"]:
            return False

        # Confidence должен быть выше минимального порога
        if trade["confidence"] is not None and trade["confidence"] < Decimal("0.1"):
            return False

        return True

    # ----------------------------------------------------------
    # КОМПОНЕНТ 2: Качество входа
    # ----------------------------------------------------------

    def _evaluate_entry(self, trade) -> Decimal:
        """
        Оценить качество точки входа.
        Смотрим на соотношение риск/прибыль (R:R).
        """
        entry = trade["entry_price"]
        stop  = trade["stop_loss"]
        take  = trade["take_profit"]

        if not all([entry, stop, take]) or entry == stop:
            return Decimal("0.5")  # нейтрально если нет данных

        # Риск и потенциальная прибыль
        risk   = abs(entry - stop)
        reward = abs(take - entry)

        if risk == 0:
            return Decimal("0.5")

        rr_ratio = reward / risk

        # Хороший вход: R:R >= 2.0 → score 1.0
        # R:R = 1.0 → score 0.5
        # R:R < 1.0 → плохо
        if rr_ratio >= Decimal("2.0"):
            return Decimal("1.0")
        elif rr_ratio >= Decimal("1.5"):
            return Decimal("0.8")
        elif rr_ratio >= Decimal("1.0"):
            return Decimal("0.5")
        else:
            return Decimal("0.2")

    # ----------------------------------------------------------
    # КОМПОНЕНТ 3: Дисциплина риска
    # ----------------------------------------------------------

    def _evaluate_risk_discipline(self, trade) -> Decimal:
        """
        Проверить что риск на сделку был в допустимых пределах.
        Железное правило: не более 2% от капитала на сделку.
        """
        risk_percent = trade["risk_percent"]

        if risk_percent is None:
            return Decimal("0.5")

        # Идеально: риск 0.5%–1.5%
        if Decimal("0.005") <= risk_percent <= Decimal("0.015"):
            return Decimal("1.0")
        # Приемлемо: до 2%
        elif risk_percent <= Decimal("0.02"):
            return Decimal("0.7")
        # Нарушение: риск больше 2%
        else:
            return Decimal("0.1")

    # ----------------------------------------------------------
    # КОМПОНЕНТ 4: Соответствие режиму
    # ----------------------------------------------------------

    def _evaluate_regime_match(self, trade) -> Decimal:
        """
        Оценить подходила ли стратегия к рыночному режиму.
        Пока упрощённо — если режим определён, это уже плюс.
        Позже здесь будет проверка по belief_system.best_regime.
        """
        if trade["market_regime"] is None:
            return Decimal("0.5")  # режим не определён — нейтрально

        # Режим определён — уже хорошо, минимум 0.7
        return Decimal("0.7")

    # ----------------------------------------------------------
    # КОМПОНЕНТ 5: Качество исполнения
    # ----------------------------------------------------------

    def _evaluate_execution(self, trade) -> Decimal:
        """
        Оценить качество исполнения ордера.
        Смотрим на проскальзывание относительно цены входа.
        """
        slippage = trade["slippage"]
        entry    = trade["entry_price"]

        if slippage is None or entry is None or entry == 0:
            return Decimal("0.7")  # нет данных — нейтрально-хорошо

        # Проскальзывание в процентах от цены
        slippage_pct = abs(slippage) / entry

        # Отличное исполнение: проскальзывание < 0.05%
        if slippage_pct < Decimal("0.0005"):
            return Decimal("1.0")
        # Хорошее: < 0.1%
        elif slippage_pct < Decimal("0.001"):
            return Decimal("0.8")
        # Приемлемое: < 0.3%
        elif slippage_pct < Decimal("0.003"):
            return Decimal("0.5")
        # Плохое исполнение
        else:
            return Decimal("0.2")

    # ----------------------------------------------------------
    # ФАКТОР СЛУЧАЙНОСТИ
    # ----------------------------------------------------------

    def _evaluate_randomness(self, trade, decision_quality: Decimal) -> Decimal:
        """
        Оценить сколько в результате сделки было случайности.

        Ключевая идея:
        - Хорошее решение + прибыль = мало случайности (заслуженно)
        - Плохое решение + прибыль = много случайности (повезло)
        - Хорошее решение + убыток = много случайности (не повезло)
        - Плохое решение + убыток = мало случайности (закономерно)

        Высокий randomness_factor = результату нельзя доверять для обучения.
        """
        pnl = trade["pnl"]

        if pnl is None:
            return Decimal("0.5")

        was_profitable = pnl > 0
        good_decision = decision_quality >= Decimal("0.6")

        # Согласованность решения и результата
        if good_decision and was_profitable:
            # Хорошее решение → прибыль: закономерно
            return Decimal("0.2")
        elif not good_decision and not was_profitable:
            # Плохое решение → убыток: закономерно
            return Decimal("0.2")
        elif good_decision and not was_profitable:
            # Хорошее решение → убыток: не повезло
            return Decimal("0.75")
        else:
            # Плохое решение → прибыль: повезло
            return Decimal("0.85")

    # ----------------------------------------------------------
    # ОЦЕНИТЬ ВСЕ НЕОЦЕНЁННЫЕ СДЕЛКИ
    # ----------------------------------------------------------

    async def evaluate_pending(self) -> int:
        """
        Оценить все закрытые сделки у которых ещё нет оценки.
        Возвращает количество оценённых сделок.
        """
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT trade_id FROM trades
                WHERE closed_at IS NOT NULL
                  AND decision_quality IS NULL
            """)

        count = 0
        for row in rows:
            await self.evaluate_trade(row["trade_id"])
            count += 1

        logger.info(f"Оценено сделок: {count}")
        return count

    # ----------------------------------------------------------
    # ЛОГ ОТКЛОНЁННЫХ СИГНАЛОВ
    # ----------------------------------------------------------

    async def log_skip(
        self,
        strategy_id: str,
        skip_reason: str,
        ticker: Optional[str] = None,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        details: Optional[dict] = None,
        is_sandbox: bool = True,
    ) -> None:
        """Записать сигнал, отклонённый до открытия позиции (таблица skipped_signals).

        Отказы — тоже данные для обучения: по ним видно, сколько сигналов
        и почему режет каждый фильтр (напр. skip_reason='structural_downtrend').
        """
        if not self._pool:
            await self.connect()

        import json
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skipped_signals
                    (strategy_id, ticker, timeframe, direction,
                     skip_reason, details, is_sandbox)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                strategy_id, ticker, timeframe, direction,
                skip_reason, json.dumps(details) if details else None,
                is_sandbox,
            )
        logger.info(
            f"Сигнал отклонён: {strategy_id} {ticker or ''} — {skip_reason}"
        )


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

async def example():
    """Пример: оценить все неоценённые сделки."""
    evaluator = DecisionEvaluator()
    await evaluator.connect()

    print("Оцениваю все неоценённые сделки...\n")
    count = await evaluator.evaluate_pending()

    if count == 0:
        print("Нет сделок для оценки (таблица trades пуста или все оценены)")
    else:
        print(f"Оценено сделок: {count}")

    await evaluator.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
