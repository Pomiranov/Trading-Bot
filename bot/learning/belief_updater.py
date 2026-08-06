"""
QuantFlow — belief_updater.py
=============================
После каждой сделки пересчитывает статистику стратегии в таблице belief_system.

Обновляет ТОЛЬКО:
    - win_rate, profit_factor, expectancy, sharpe_ratio
    - confidence (уровень доверия к стратегии)

НЕ трогает:
    - фундаментальные правила (они в knowledge/)
    - математические формулы
    - определения стратегий

Использование:
    updater = BeliefUpdater()
    await updater.connect()
    await updater.update_strategy("breakout_moex")
"""

import logging
import math
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

import asyncpg

logger = logging.getLogger("quantflow.belief")


# ============================================================
# КОНСТАНТЫ ОБУЧЕНИЯ
# ============================================================

# Минимум сделок прежде чем доверять статистике
MIN_TRADES_FOR_CONFIDENCE = 20

# Порог WinRate ниже которого confidence падает
NEUTRAL_WIN_RATE = Decimal("0.50")

# Насколько быстро меняется confidence (0-1, меньше = плавнее)
CONFIDENCE_LEARNING_RATE = Decimal("0.15")

# Границы confidence
MIN_CONFIDENCE = Decimal("0.05")
MAX_CONFIDENCE = Decimal("0.95")


# ============================================================
# КЛАСС: BeliefUpdater
# ============================================================

class BeliefUpdater:
    """Пересчитывает статистику и уровень доверия стратегий."""

    def __init__(self, dsn: Optional[str] = None):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Подключиться к БД."""
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
        logger.info("BeliefUpdater: подключение к БД установлено")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()

    # ----------------------------------------------------------
    # ГЛАВНЫЙ МЕТОД: обновить статистику стратегии
    # ----------------------------------------------------------

    async def update_strategy(self, strategy_id: str) -> dict:
        """
        Пересчитать всю статистику стратегии по её сделкам.
        Вызывается после каждой закрытой сделки.
        Возвращает обновлённую статистику.
        """
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            # 1. Забираем все закрытые сделки стратегии
            trades = await conn.fetch("""
                SELECT pnl, pnl_r, decision_quality
                FROM trades
                WHERE strategy_id = $1
                  AND closed_at IS NOT NULL
                  AND pnl IS NOT NULL
                ORDER BY opened_at
            """, strategy_id)

            if not trades:
                logger.warning(f"Нет закрытых сделок для стратегии {strategy_id}")
                return {}

            # 2. Считаем метрики
            stats = self._calculate_stats(trades)

            # 3. Считаем новый confidence
            current_confidence = await conn.fetchval(
                "SELECT confidence FROM belief_system WHERE strategy_id = $1",
                strategy_id
            )
            new_confidence = self._update_confidence(
                current_confidence or Decimal("0.5"),
                stats
            )

            # 4. Определяем в каком режиме стратегия работает лучше
            best_regime = await self._find_best_regime(conn, strategy_id)

            # 5. Записываем обновлённую статистику
            await conn.execute("""
                UPDATE belief_system SET
                    total_trades          = $2,
                    winning_trades        = $3,
                    losing_trades         = $4,
                    win_rate              = $5,
                    profit_factor         = $6,
                    expectancy            = $7,
                    sharpe_ratio          = $8,
                    avg_win_r             = $9,
                    avg_loss_r            = $10,
                    max_consecutive_losses = $11,
                    confidence            = $12,
                    best_regime           = $13,
                    last_trade_at         = NOW()
                WHERE strategy_id = $1
            """,
                strategy_id,
                stats["total_trades"],
                stats["winning_trades"],
                stats["losing_trades"],
                stats["win_rate"],
                stats["profit_factor"],
                stats["expectancy"],
                stats["sharpe_ratio"],
                stats["avg_win_r"],
                stats["avg_loss_r"],
                stats["max_consecutive_losses"],
                new_confidence,
                best_regime,
            )

        result = {**stats, "confidence": new_confidence, "best_regime": best_regime}
        logger.info(
            f"Стратегия {strategy_id} обновлена: "
            f"trades={stats['total_trades']}, "
            f"win_rate={stats['win_rate']:.2%}, "
            f"PF={stats['profit_factor']:.2f}, "
            f"confidence={new_confidence:.2f}"
        )
        return result

    # ----------------------------------------------------------
    # РАСЧЁТ МЕТРИК
    # ----------------------------------------------------------

    def _calculate_stats(self, trades: list) -> dict:
        """Рассчитать все статистические метрики по списку сделок."""

        total = len(trades)
        wins   = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]

        n_wins   = len(wins)
        n_losses = len(losses)

        # WinRate
        win_rate = Decimal(n_wins) / Decimal(total) if total > 0 else Decimal(0)

        # Profit Factor = сумма прибылей / сумма убытков
        gross_profit = sum((t["pnl"] for t in wins), Decimal(0))
        gross_loss   = abs(sum((t["pnl"] for t in losses), Decimal(0)))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = Decimal(999) if gross_profit > 0 else Decimal(0)

        # Средний результат в R
        r_values = [t["pnl_r"] for t in trades if t["pnl_r"] is not None]
        expectancy = (
            sum(r_values, Decimal(0)) / Decimal(len(r_values))
            if r_values else Decimal(0)
        )

        # Средний выигрыш и проигрыш в R
        win_r  = [t["pnl_r"] for t in wins   if t["pnl_r"] is not None]
        loss_r = [t["pnl_r"] for t in losses if t["pnl_r"] is not None]
        avg_win_r  = sum(win_r,  Decimal(0)) / Decimal(len(win_r))  if win_r  else Decimal(0)
        avg_loss_r = sum(loss_r, Decimal(0)) / Decimal(len(loss_r)) if loss_r else Decimal(0)

        # Sharpe Ratio (упрощённый, по R-значениям)
        sharpe = self._calculate_sharpe(r_values)

        # Максимальная серия убытков подряд
        max_consec = self._max_consecutive_losses(trades)

        return {
            "total_trades":           total,
            "winning_trades":         n_wins,
            "losing_trades":          n_losses,
            "win_rate":               win_rate.quantize(Decimal("0.0001")),
            "profit_factor":          profit_factor.quantize(Decimal("0.0001")),
            "expectancy":             expectancy.quantize(Decimal("0.0001")),
            "sharpe_ratio":           sharpe.quantize(Decimal("0.0001")),
            "avg_win_r":              avg_win_r.quantize(Decimal("0.0001")),
            "avg_loss_r":             avg_loss_r.quantize(Decimal("0.0001")),
            "max_consecutive_losses": max_consec,
        }

    def _calculate_sharpe(self, r_values: list) -> Decimal:
        """
        Sharpe Ratio по R-значениям сделок.
        Sharpe = среднее / стандартное отклонение.
        """
        if len(r_values) < 2:
            return Decimal(0)

        floats = [float(r) for r in r_values]
        mean = sum(floats) / len(floats)
        variance = sum((x - mean) ** 2 for x in floats) / (len(floats) - 1)
        std = math.sqrt(variance)

        if std == 0:
            return Decimal(0)

        return Decimal(str(mean / std))

    def _max_consecutive_losses(self, trades: list) -> int:
        """Найти максимальную серию убыточных сделок подряд."""
        max_streak = 0
        current = 0
        for t in trades:
            if t["pnl"] <= 0:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    # ----------------------------------------------------------
    # ОБНОВЛЕНИЕ CONFIDENCE — ядро обучения
    # ----------------------------------------------------------

    def _update_confidence(self, current: Decimal, stats: dict) -> Decimal:
        """
        Обновить уровень доверия к стратегии.

        Логика:
        - Мало сделок → confidence остаётся около 0.5 (нейтрально)
        - WinRate выше 50% и Profit Factor выше 1 → confidence растёт
        - WinRate ниже 50% или Profit Factor ниже 1 → confidence падает
        - Изменение плавное (learning rate), без резких скачков
        """
        total = stats["total_trades"]

        # Пока мало данных — не меняем резко
        if total < MIN_TRADES_FOR_CONFIDENCE:
            # Плавно двигаем к 0.5 (нейтральная зона)
            return self._clamp(
                current + (Decimal("0.5") - current) * Decimal("0.1")
            )

        # Целевой confidence на основе метрик
        win_rate      = stats["win_rate"]
        profit_factor = stats["profit_factor"]
        expectancy    = stats["expectancy"]

        # Компонент 1: WinRate относительно 50%
        wr_score = (win_rate - NEUTRAL_WIN_RATE) * Decimal(2)  # от -1 до +1

        # Компонент 2: Profit Factor (1.0 = нейтрально)
        # PF 1.5 → +0.5, PF 0.5 → -0.5
        pf_score = self._clamp_range(
            (profit_factor - Decimal(1)),
            Decimal("-1"), Decimal("1")
        )

        # Компонент 3: положительное ожидание
        exp_score = self._clamp_range(
            expectancy,
            Decimal("-1"), Decimal("1")
        )

        # Целевой confidence: среднее трёх компонентов, сдвинутое в диапазон 0-1
        target_raw = (wr_score + pf_score + exp_score) / Decimal(3)  # от -1 до +1
        target = (target_raw + Decimal(1)) / Decimal(2)  # от 0 до 1

        # Плавное движение к цели
        new_confidence = current + (target - current) * CONFIDENCE_LEARNING_RATE

        return self._clamp(new_confidence)

    def _clamp(self, value: Decimal) -> Decimal:
        """Ограничить confidence границами MIN..MAX."""
        value = max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, value))
        return value.quantize(Decimal("0.0001"))

    def _clamp_range(self, value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
        """Ограничить значение произвольным диапазоном."""
        return max(lo, min(hi, value))

    # ----------------------------------------------------------
    # ЛУЧШИЙ РЕЖИМ ДЛЯ СТРАТЕГИИ
    # ----------------------------------------------------------

    async def _find_best_regime(self, conn, strategy_id: str) -> Optional[str]:
        """
        Найти рыночный режим где стратегия показывает лучший результат.
        Помогает боту применять стратегию только в подходящих условиях.
        """
        rows = await conn.fetch("""
            SELECT
                market_regime,
                AVG(pnl_r) AS avg_r,
                COUNT(*)   AS n
            FROM trades
            WHERE strategy_id = $1
              AND market_regime IS NOT NULL
              AND pnl_r IS NOT NULL
              AND closed_at IS NOT NULL
            GROUP BY market_regime
            HAVING COUNT(*) >= 5
            ORDER BY avg_r DESC
            LIMIT 1
        """, strategy_id)

        if rows:
            return rows[0]["market_regime"]
        return None

    # ----------------------------------------------------------
    # ОБНОВИТЬ ВСЕ СТРАТЕГИИ СРАЗУ
    # ----------------------------------------------------------

    async def update_all(self) -> dict:
        """Пересчитать статистику всех стратегий."""
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            strategy_ids = await conn.fetch(
                "SELECT strategy_id FROM belief_system"
            )

        results = {}
        for row in strategy_ids:
            sid = row["strategy_id"]
            results[sid] = await self.update_strategy(sid)

        return results


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

async def example():
    """Пример: обновить статистику всех стратегий."""
    updater = BeliefUpdater()
    await updater.connect()

    print("Обновляю статистику всех стратегий...\n")
    results = await updater.update_all()

    for strategy_id, stats in results.items():
        if stats:
            print(f"── {strategy_id}")
            print(f"   Сделок:      {stats.get('total_trades', 0)}")
            print(f"   WinRate:     {stats.get('win_rate', 0):.1%}")
            print(f"   ProfitFactor:{stats.get('profit_factor', 0):.2f}")
            print(f"   Confidence:  {stats.get('confidence', 0):.2f}")
            print(f"   Лучший режим:{stats.get('best_regime', '—')}")
            print()
        else:
            print(f"── {strategy_id}: нет данных\n")

    await updater.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
