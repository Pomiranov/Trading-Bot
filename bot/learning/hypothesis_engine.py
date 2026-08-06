"""
QuantFlow — hypothesis_engine.py
================================
Ищет новые торговые паттерны в накопленных сделках и проводит их
через три стадии строгой статистической проверки.

Три стадии (из архитектуры проекта):
    observation (30 сделок)  — только наблюдение, в торговле НЕ используется
    candidate   (100 сделок) — статистические тесты (binomial, bootstrap)
    active      (300 сделок) — прошла все проверки, влияет на торговлю

Главный принцип:
    Недоказанные гипотезы НЕ используются в торговле.
    Малая выборка → никаких выводов.

Использование:
    engine = HypothesisEngine()
    await engine.connect()
    await engine.discover_patterns()   # найти новые паттерны
    await engine.evaluate_all()        # проверить и продвинуть гипотезы
"""

import logging
import statistics
from decimal import Decimal
from typing import Optional

import asyncpg

logger = logging.getLogger("quantflow.hypothesis")


# ============================================================
# ПОРОГИ СТАДИЙ
# ============================================================

STAGE_OBSERVATION_MIN = 30
STAGE_CANDIDATE_MIN   = 100
STAGE_ACTIVE_MIN      = 300

# Критерии перехода в active
ACTIVE_MIN_WIN_RATE      = Decimal("0.50")
ACTIVE_MIN_PROFIT_FACTOR = Decimal("1.2")
ACTIVE_MIN_EXPECTANCY    = Decimal("0.0")
ACTIVE_MAX_P_VALUE       = 0.05   # статистическая значимость 95%


# ============================================================
# КЛАСС: HypothesisEngine
# ============================================================

class HypothesisEngine:
    """Находит и проверяет торговые гипотезы."""

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
        logger.info("HypothesisEngine: подключение к БД установлено")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()

    # ==========================================================
    # ЧАСТЬ 1: ПОИСК НОВЫХ ПАТТЕРНОВ
    # ==========================================================

    async def discover_patterns(self, min_trades: int = STAGE_OBSERVATION_MIN) -> list:
        """
        Ищет повторяющиеся паттерны в закрытых сделках.
        Создаёт новые гипотезы в стадии observation.

        Паттерн = комбинация условий (режим + признаки) которая
        встречается достаточно часто.
        """
        if not self._pool:
            await self.connect()

        # Проверяем достаточно ли вообще данных
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("""
                SELECT COUNT(*) FROM trades
                WHERE closed_at IS NOT NULL AND pnl IS NOT NULL
            """)

        if total < min_trades:
            logger.info(
                f"Недостаточно данных для поиска паттернов: "
                f"{total} < {min_trades}"
            )
            return []

        discovered = []

        # Паттерн-кандидаты: ищем по рыночному режиму
        discovered += await self._discover_by_regime()

        # Паттерн-кандидаты: ищем по признакам (RSI зоны, объём)
        discovered += await self._discover_by_features()

        logger.info(f"Найдено потенциальных паттернов: {len(discovered)}")
        return discovered

    async def _discover_by_regime(self) -> list:
        """Ищет: какая стратегия + режим дают преимущество."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    strategy_id,
                    market_regime,
                    market,
                    COUNT(*)      AS n,
                    AVG(pnl_r)    AS avg_r,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS win_rate
                FROM trades
                WHERE closed_at IS NOT NULL
                  AND pnl_r IS NOT NULL
                  AND market_regime IS NOT NULL
                GROUP BY strategy_id, market_regime, market
                HAVING COUNT(*) >= $1
            """, STAGE_OBSERVATION_MIN)

        created = []
        for row in rows:
            conditions = {
                "strategy_id":   row["strategy_id"],
                "market_regime": row["market_regime"],
            }
            description = (
                f"Стратегия '{row['strategy_id']}' в режиме "
                f"'{row['market_regime']}'"
            )
            hyp_id = await self._create_or_update_hypothesis(
                description, conditions, row["market"]
            )
            if hyp_id:
                created.append(hyp_id)
        return created

    async def _discover_by_features(self) -> list:
        """Ищет паттерны по значениям признаков (RSI, объём)."""
        async with self._pool.acquire() as conn:
            # Пример: сделки с высоким объёмом (volume_ratio > 1.5)
            rows = await conn.fetch("""
                SELECT
                    strategy_id,
                    COUNT(*)   AS n,
                    AVG(pnl_r) AS avg_r,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS win_rate
                FROM trades
                WHERE closed_at IS NOT NULL
                  AND pnl_r IS NOT NULL
                  AND (market_features->>'volume_ratio')::FLOAT > 1.5
                GROUP BY strategy_id
                HAVING COUNT(*) >= $1
            """, STAGE_OBSERVATION_MIN)

        created = []
        for row in rows:
            conditions = {
                "strategy_id": row["strategy_id"],
                "volume_ratio_above": 1.5,
            }
            description = (
                f"Стратегия '{row['strategy_id']}' при объёме выше среднего в 1.5x"
            )
            hyp_id = await self._create_or_update_hypothesis(
                description, conditions, None
            )
            if hyp_id:
                created.append(hyp_id)
        return created

    async def _create_or_update_hypothesis(
        self, description: str, conditions: dict, market: Optional[str]
    ) -> Optional[str]:
        """Создать гипотезу если её ещё нет (по description)."""
        import json

        async with self._pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT hypothesis_id FROM hypotheses WHERE description = $1",
                description
            )
            if existing:
                return None  # уже есть

            hyp_id = await conn.fetchval("""
                INSERT INTO hypotheses (description, conditions, market, stage)
                VALUES ($1, $2, $3, 'observation')
                RETURNING hypothesis_id
            """, description, json.dumps(conditions), market)

            logger.info(f"Новая гипотеза: {description}")
            return str(hyp_id)

    # ==========================================================
    # ЧАСТЬ 2: ПРОВЕРКА И ПРОДВИЖЕНИЕ ГИПОТЕЗ
    # ==========================================================

    async def evaluate_all(self) -> dict:
        """
        Проверить все гипотезы и продвинуть их между стадиями.
        Возвращает сводку по действиям.
        """
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            hypotheses = await conn.fetch("""
                SELECT * FROM hypotheses
                WHERE stage != 'rejected' AND stage != 'active'
            """)

        summary = {"promoted": [], "rejected": [], "unchanged": []}

        for hyp in hypotheses:
            result = await self._evaluate_hypothesis(hyp)
            summary[result["action"]].append({
                "description": hyp["description"],
                "stage": result["new_stage"],
            })

        return summary

    async def _evaluate_hypothesis(self, hyp) -> dict:
        """Проверить одну гипотезу и решить её судьбу."""
        import json

        conditions = json.loads(hyp["conditions"]) if isinstance(hyp["conditions"], str) else hyp["conditions"]

        # Собираем сделки соответствующие условиям гипотезы
        trades = await self._get_matching_trades(conditions)
        n = len(trades)

        # Считаем статистику
        stats = self._compute_stats(trades)

        # Обновляем статистику гипотезы
        await self._save_hypothesis_stats(hyp["hypothesis_id"], stats, n)

        current_stage = hyp["stage"]

        # --- Логика продвижения по стадиям ---

        # observation → candidate (100 сделок + положительное ожидание)
        if current_stage == "observation":
            if n >= STAGE_CANDIDATE_MIN:
                # Выборка набрана, но гипотеза убыточна — статистически
                # проверять нечего, отклоняем сразу
                if stats["expectancy"] <= 0:
                    await self._reject(hyp["hypothesis_id"])
                    return {"action": "rejected", "new_stage": "rejected"}
                await self._promote(hyp["hypothesis_id"], "candidate")
                return {"action": "promoted", "new_stage": "candidate"}
            return {"action": "unchanged", "new_stage": "observation"}

        # candidate → active (300 сделок + статтесты)
        if current_stage == "candidate":
            # Пересчёт сделал кандидата убыточным — отклоняем,
            # не дожидаясь 300 сделок
            if n > 0 and stats["expectancy"] <= 0:
                await self._reject(hyp["hypothesis_id"])
                return {"action": "rejected", "new_stage": "rejected"}

            if n >= STAGE_ACTIVE_MIN:
                # Проводим статистические тесты
                passed, test_result = self._run_statistical_tests(trades, stats)
                await self._save_test_result(hyp["hypothesis_id"], test_result)

                if passed:
                    await self._promote(hyp["hypothesis_id"], "active")
                    return {"action": "promoted", "new_stage": "active"}
                else:
                    await self._reject(hyp["hypothesis_id"])
                    return {"action": "rejected", "new_stage": "rejected"}
            return {"action": "unchanged", "new_stage": "candidate"}

        return {"action": "unchanged", "new_stage": current_stage}

    async def _get_matching_trades(self, conditions: dict) -> list:
        """Найти сделки соответствующие условиям гипотезы."""
        query = """
            SELECT pnl, pnl_r FROM trades
            WHERE closed_at IS NOT NULL AND pnl_r IS NOT NULL
        """
        params = []
        param_idx = 1

        if "strategy_id" in conditions:
            query += f" AND strategy_id = ${param_idx}"
            params.append(conditions["strategy_id"])
            param_idx += 1

        if "market_regime" in conditions:
            query += f" AND market_regime = ${param_idx}"
            params.append(conditions["market_regime"])
            param_idx += 1

        if "volume_ratio_above" in conditions:
            query += f" AND (market_features->>'volume_ratio')::FLOAT > ${param_idx}"
            params.append(conditions["volume_ratio_above"])
            param_idx += 1

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    # ==========================================================
    # СТАТИСТИКА И ТЕСТЫ
    # ==========================================================

    def _compute_stats(self, trades: list) -> dict:
        """Посчитать базовую статистику по сделкам."""
        if not trades:
            return {
                "win_rate": Decimal(0),
                "profit_factor": Decimal(0),
                "expectancy": Decimal(0),
            }

        total = len(trades)
        wins = [t for t in trades if t["pnl"] > 0]
        n_wins = len(wins)

        win_rate = Decimal(n_wins) / Decimal(total)

        gross_profit = sum((t["pnl"] for t in wins), Decimal(0))
        gross_loss = abs(sum((t["pnl"] for t in trades if t["pnl"] <= 0), Decimal(0)))
        profit_factor = (
            gross_profit / gross_loss if gross_loss > 0
            else Decimal(999) if gross_profit > 0 else Decimal(0)
        )

        r_values = [t["pnl_r"] for t in trades if t["pnl_r"] is not None]
        expectancy = (
            sum(r_values, Decimal(0)) / Decimal(len(r_values))
            if r_values else Decimal(0)
        )

        return {
            "win_rate": win_rate.quantize(Decimal("0.0001")),
            "profit_factor": profit_factor.quantize(Decimal("0.0001")),
            "expectancy": expectancy.quantize(Decimal("0.0001")),
        }

    def _run_statistical_tests(self, trades: list, stats: dict) -> tuple:
        """
        Провести статистические тесты для стадии candidate → active.

        Тесты:
        1. Binomial test — WinRate статистически выше случайного?
        2. Bootstrap — доверительный интервал expectancy положительный?
        3. Базовые критерии — PF, expectancy

        Возвращает (passed: bool, test_result: dict)
        """
        n = len(trades)
        n_wins = len([t for t in trades if t["pnl"] > 0])

        # --- Тест 1: Binomial test ---
        # H0: win_rate = 0.5 (случайность)
        # H1: win_rate > 0.5
        p_value = self._binomial_test(n_wins, n, 0.5)

        # --- Тест 2: Bootstrap доверительный интервал expectancy ---
        r_values = [float(t["pnl_r"]) for t in trades if t["pnl_r"] is not None]
        ci_low, ci_high = self._bootstrap_ci(r_values)

        # --- Критерии прохождения ---
        passed = (
            stats["win_rate"] >= ACTIVE_MIN_WIN_RATE and
            stats["profit_factor"] >= ACTIVE_MIN_PROFIT_FACTOR and
            stats["expectancy"] > ACTIVE_MIN_EXPECTANCY and
            p_value < ACTIVE_MAX_P_VALUE and
            ci_low > 0  # нижняя граница CI положительна
        )

        test_result = {
            "binomial_p_value": round(p_value, 4),
            "bootstrap_ci": [round(ci_low, 4), round(ci_high, 4)],
            "win_rate": float(stats["win_rate"]),
            "profit_factor": float(stats["profit_factor"]),
            "expectancy": float(stats["expectancy"]),
            "passed": passed,
        }

        return passed, test_result

    def _binomial_test(self, successes: int, trials: int, p: float) -> float:
        """
        Односторонний биномиальный тест.
        Вероятность получить >= successes при случайности p.
        Возвращает p-value.
        """
        if trials == 0:
            return 1.0

        try:
            from scipy import stats as scipy_stats
            result = scipy_stats.binomtest(successes, trials, p, alternative='greater')
            return float(result.pvalue)
        except ImportError:
            # Fallback: нормальная аппроксимация если scipy недоступен
            import math
            mean = trials * p
            std = math.sqrt(trials * p * (1 - p))
            if std == 0:
                return 1.0
            z = (successes - mean) / std
            # Приблизительный p-value через функцию ошибок
            p_value = 0.5 * (1 - math.erf(z / math.sqrt(2)))
            return max(0.0, min(1.0, p_value))

    def _bootstrap_ci(
        self, values: list, n_iterations: int = 1000, ci: float = 0.95
    ) -> tuple:
        """
        Bootstrap доверительный интервал для среднего.
        Возвращает (нижняя граница, верхняя граница).
        """
        if len(values) < 2:
            return (0.0, 0.0)

        import random
        means = []
        n = len(values)
        for _ in range(n_iterations):
            sample = [random.choice(values) for _ in range(n)]
            means.append(sum(sample) / n)

        means.sort()
        lower_idx = int((1 - ci) / 2 * n_iterations)
        upper_idx = int((1 + ci) / 2 * n_iterations)
        return (means[lower_idx], means[upper_idx])

    # ==========================================================
    # РАБОТА С БД
    # ==========================================================

    async def _save_hypothesis_stats(self, hyp_id, stats: dict, n: int) -> None:
        """Сохранить статистику гипотезы."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE hypotheses SET
                    total_trades = $2,
                    win_rate = $3,
                    profit_factor = $4,
                    expectancy = $5
                WHERE hypothesis_id = $1
            """, hyp_id, n, stats["win_rate"],
                stats["profit_factor"], stats["expectancy"])

    async def _save_test_result(self, hyp_id, test_result: dict) -> None:
        """Сохранить результаты статистических тестов."""
        import json
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE hypotheses SET stat_test_result = $2
                WHERE hypothesis_id = $1
            """, hyp_id, json.dumps(test_result))

    async def _promote(self, hyp_id, new_stage: str) -> None:
        """Продвинуть гипотезу на следующую стадию."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE hypotheses SET stage = $2, promoted_at = NOW()
                WHERE hypothesis_id = $1
            """, hyp_id, new_stage)
        logger.info(f"Гипотеза {str(hyp_id)[:8]} продвинута → {new_stage}")

    async def _reject(self, hyp_id) -> None:
        """Отклонить гипотезу (не прошла тесты)."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE hypotheses SET stage = 'rejected', rejected_at = NOW()
                WHERE hypothesis_id = $1
            """, hyp_id)
        logger.info(f"Гипотеза {str(hyp_id)[:8]} отклонена")

    # ==========================================================
    # ПОЛУЧИТЬ АКТИВНЫЕ ГИПОТЕЗЫ (для торговли)
    # ==========================================================

    async def get_active_hypotheses(self) -> list:
        """
        Вернуть только active гипотезы — те что прошли все проверки
        и могут влиять на торговые решения.
        """
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM hypotheses WHERE stage = 'active'
                ORDER BY confidence DESC
            """)
            return [dict(r) for r in rows]


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

async def example():
    """Пример полного цикла работы Hypothesis Engine."""
    engine = HypothesisEngine()
    await engine.connect()

    print("═══ Hypothesis Engine ═══\n")

    # 1. Ищем новые паттерны
    print("1. Поиск новых паттернов...")
    discovered = await engine.discover_patterns()
    print(f"   Найдено: {len(discovered)} новых гипотез\n")

    # 2. Проверяем и продвигаем существующие
    print("2. Проверка и продвижение гипотез...")
    summary = await engine.evaluate_all()
    print(f"   Продвинуто:  {len(summary['promoted'])}")
    print(f"   Отклонено:   {len(summary['rejected'])}")
    print(f"   Без изменений: {len(summary['unchanged'])}\n")

    # 3. Показываем активные гипотезы
    print("3. Активные гипотезы (влияют на торговлю):")
    active = await engine.get_active_hypotheses()
    if active:
        for h in active:
            print(f"   ── {h['description']}")
            print(f"      WinRate: {h['win_rate']:.1%}, "
                  f"PF: {h['profit_factor']:.2f}")
    else:
        print("   Пока нет активных гипотез (нужно 300+ сделок)")

    await engine.disconnect()


if __name__ == "__main__":
    import asyncio
    import sys

    # Windows-консоль по умолчанию в cp1251 — символы ═ не печатаются
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")

    asyncio.run(example())
