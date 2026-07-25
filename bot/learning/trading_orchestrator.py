"""
QuantFlow — trading_orchestrator.py
====================================
Единая точка входа для всего цикла обучения.
Связывает торговлю с четырьмя модулями learning/.

Философия:
    Оркестратор ничего не знает о конкретном источнике сделок.
    Ему одинаково — приходит сделка из backtest/engine.py
    или из main.py (реальная торговля через брокера).
    Это позволяет сначала обкатать обучение на истории,
    а потом подключить к живой торговле без изменений.

Три главных метода:
    check_signal(signal)     — стоит ли открывать позицию?
    on_trade_opened(trade)   — сделка открыта, запомнить контекст
    on_trade_closed(trade)   — сделка закрыта, запустить цикл обучения

Использование:
    orchestrator = TradingOrchestrator()
    await orchestrator.connect()

    # в момент когда rules_engine нашёл сигнал:
    decision = await orchestrator.check_signal(signal)
    if decision["approved"]:
        trade = broker.open_position(...)
        await orchestrator.on_trade_opened(trade)

    # когда позиция закрылась:
    await orchestrator.on_trade_closed(trade)
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

import asyncpg

# Импортируем наши модули обучения.
# Двойной вариант: пакетный импорт (запуск из корня проекта)
# и плоский (прямой запуск: python learning/trading_orchestrator.py).
try:
    from learning.memory_writer      import MemoryWriter, Trade
    from learning.decision_evaluator import DecisionEvaluator
    from learning.belief_updater     import BeliefUpdater
    from learning.hypothesis_engine  import HypothesisEngine
except ImportError:
    from memory_writer      import MemoryWriter, Trade
    from decision_evaluator import DecisionEvaluator
    from belief_updater     import BeliefUpdater
    from hypothesis_engine  import HypothesisEngine

logger = logging.getLogger("quantflow.orchestrator")


# ============================================================
# ПОРОГИ И ПАРАМЕТРЫ
# ============================================================

# Минимальный confidence стратегии чтобы её использовать
MIN_STRATEGY_CONFIDENCE = Decimal("0.20")

# Rules-файлы стратегий, у которых есть именованные фильтры
# (filters.structural_downtrend и т.п.). Ключ — префикс strategy_id.
_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "rules"
STRATEGY_RULES_FILES = {
    "osc_range_moex": _RULES_DIR / "rules_osc_range.yaml",
}

# Как часто искать новые паттерны (каждые N закрытых сделок)
HYPOTHESIS_DISCOVERY_INTERVAL = 50

# Как часто проверять гипотезы на продвижение
HYPOTHESIS_EVALUATION_INTERVAL = 20


# ============================================================
# КЛАСС: TradingOrchestrator
# ============================================================

class TradingOrchestrator:
    """
    Оркестратор торгового цикла с обучением.

    Управляет всей цепочкой:
    сигнал → решение → открытие → закрытие → оценка → обучение
    """

    def __init__(self, dsn: Optional[str] = None):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

        # Модули обучения
        self.memory     = MemoryWriter(dsn)
        self.evaluator  = DecisionEvaluator(dsn)
        self.beliefs    = BeliefUpdater(dsn)
        self.hypotheses = HypothesisEngine(dsn)

        # Счётчик закрытых сделок за сессию (для триггеров обучения)
        self._trades_closed_count = 0

        # Кеш конфигов именованных фильтров: путь к rules-файлу → dict
        self._filter_cfg_cache: dict = {}

    async def connect(self) -> None:
        """Подключить все модули к БД."""
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

        # Общий пул для оркестратора
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)

        # Подключаем все модули
        await self.memory.connect()
        await self.evaluator.connect()
        await self.beliefs.connect()
        await self.hypotheses.connect()

        logger.info("TradingOrchestrator: все модули подключены")

    async def disconnect(self) -> None:
        """Закрыть все соединения."""
        await self.memory.disconnect()
        await self.evaluator.disconnect()
        await self.beliefs.disconnect()
        await self.hypotheses.disconnect()
        if self._pool:
            await self._pool.close()

    # ==========================================================
    # ГЛАВНЫЙ МЕТОД 1: проверить сигнал перед открытием
    # ==========================================================

    async def check_signal(self, signal: dict) -> dict:
        """
        Проверить торговый сигнал перед открытием позиции.

        Учитывает:
        - Текущий confidence стратегии
        - Активные гипотезы, усиливающие сигнал
        - Лучший режим для стратегии

        signal должен содержать:
            strategy_id, market_regime, market_features

        Возвращает:
            {
                "approved": bool,
                "confidence": Decimal,
                "position_size_multiplier": Decimal,
                "reason": str,
                "matched_hypotheses": list
            }
        """
        strategy_id   = signal.get("strategy_id")
        market_regime = signal.get("market_regime")

        # 0. Фильтры стратегии: структурный даунтренд (только лонги).
        # Проверяется ПЕРЕД остальными проверками — фильтр жёсткий,
        # confidence и гипотезы его не перевешивают.
        skip_reason = await self._check_structural_downtrend(signal)
        if skip_reason:
            return {
                "approved": False,
                "confidence": Decimal("0"),
                "position_size_multiplier": Decimal("1"),
                "reason": skip_reason,
                "skip_reason": "structural_downtrend",
                "matched_hypotheses": [],
            }

        # 1. Смотрим текущее доверие к стратегии
        strategy_stats = await self._get_strategy_stats(strategy_id)

        if not strategy_stats:
            # New strategy — bootstrap it with neutral confidence and approve
            # This allows the system to accumulate trades before making judgements
            logger.info(
                "Стратегия %s не найдена в belief_system — "
                "разрешаем с базовым confidence 0.5", strategy_id
            )
            await self._bootstrap_strategy(strategy_id)
            return {
                "approved": True,
                "confidence": Decimal("0.5"),
                "position_size_multiplier": Decimal("1"),
                "reason": f"Стратегия {strategy_id} создана с базовым confidence",
                "matched_hypotheses": [],
            }

        confidence = strategy_stats["confidence"] or Decimal("0.5")

        # 2. Проверяем минимальный порог
        if confidence < MIN_STRATEGY_CONFIDENCE:
            return {
                "approved": False,
                "confidence": confidence,
                "position_size_multiplier": Decimal("1"),
                "reason": (
                    f"Confidence {confidence:.2f} ниже порога "
                    f"{MIN_STRATEGY_CONFIDENCE}"
                ),
                "matched_hypotheses": [],
            }

        # 3. Проверяем совпадение с лучшим режимом
        best_regime = strategy_stats["best_regime"]
        regime_bonus = Decimal("1.0")

        if best_regime and market_regime:
            if best_regime == market_regime:
                regime_bonus = Decimal("1.2")  # +20% размер позиции
            else:
                regime_bonus = Decimal("0.7")  # -30% размер позиции

        # 4. Проверяем активные гипотезы
        matched = await self._find_matching_hypotheses(signal)

        hypothesis_bonus = Decimal("1.0")
        if matched:
            # Каждая усиливающая гипотеза даёт +10% (максимум +30%)
            hypothesis_bonus = min(
                Decimal("1.3"),
                Decimal("1.0") + Decimal(len(matched)) * Decimal("0.1")
            )

        # 5. Итоговый множитель размера позиции
        # Больше confidence и лучше условия → больше позиция
        size_multiplier = confidence * regime_bonus * hypothesis_bonus

        # Ограничиваем разумными пределами
        size_multiplier = max(Decimal("0.3"), min(Decimal("1.5"), size_multiplier))

        logger.info(
            f"Сигнал одобрен: {strategy_id} | "
            f"confidence={confidence:.2f} | "
            f"размер×{size_multiplier:.2f} | "
            f"гипотез={len(matched)}"
        )

        return {
            "approved": True,
            "confidence": confidence,
            "position_size_multiplier": size_multiplier,
            "reason": "Сигнал прошёл все проверки",
            "matched_hypotheses": matched,
            "best_regime_match": best_regime == market_regime if best_regime else None,
        }

    # ==========================================================
    # ГЛАВНЫЙ МЕТОД 2: сделка открыта
    # ==========================================================

    async def on_trade_opened(self, trade: Trade) -> str:
        """
        Записать факт открытия сделки.

        Пока сделка открыта — pnl не заполнен, closed_at пустой.
        Полная запись произойдёт в on_trade_closed.
        Здесь только фиксируем что сделка началась.
        """
        # Просто пишем в БД с closed_at=NULL
        trade_id = await self.memory.save_trade(trade)

        logger.info(
            f"Открыта сделка: {trade.ticker} {trade.direction.value} @ "
            f"{trade.entry_price} | strategy={trade.strategy_id}"
        )
        return trade_id

    # ==========================================================
    # ГЛАВНЫЙ МЕТОД 3: сделка закрыта → запуск обучения
    # ==========================================================

    async def on_trade_closed(self, trade: Trade) -> dict:
        """
        Запустить полный цикл обучения после закрытия сделки.

        Порядок:
        1. Обновить запись сделки (цена выхода, pnl, closed_at)
        2. Оценить качество решения (decision_evaluator)
        3. Пересчитать статистику стратегии (belief_updater)
        4. Периодически: искать новые паттерны (hypothesis_engine)

        Возвращает сводку по всем этапам.
        """
        result = {
            "trade_id":        trade.trade_id,
            "trade_updated":   False,
            "quality":         None,
            "confidence_before": None,
            "confidence_after":  None,
            "hypotheses_discovered": 0,
        }

        # ЭТАП 1: Обновить запись сделки (или создать если её нет)
        result["trade_updated"] = await self._update_or_insert_trade(trade)

        # ЭТАП 2: Оценка качества решения
        evaluation = await self.evaluator.evaluate_trade(trade.trade_id)
        result["quality"] = float(evaluation["decision_quality"])
        result["randomness"] = float(evaluation["randomness_factor"])

        # ЭТАП 3: Пересчёт статистики стратегии
        # Сохраняем confidence "до" и "после" — увидим сдвиг
        before = await self._get_strategy_stats(trade.strategy_id)
        result["confidence_before"] = float(before["confidence"]) if before else None

        await self.beliefs.update_strategy(trade.strategy_id)

        after = await self._get_strategy_stats(trade.strategy_id)
        result["confidence_after"] = float(after["confidence"]) if after else None

        # ЭТАП 4: Периодически запускаем hypothesis_engine
        self._trades_closed_count += 1

        # Каждые N сделок — проверяем гипотезы на продвижение
        if self._trades_closed_count % HYPOTHESIS_EVALUATION_INTERVAL == 0:
            eval_summary = await self.hypotheses.evaluate_all()
            result["hypotheses_evaluated"] = {
                "promoted": len(eval_summary.get("promoted", [])),
                "rejected": len(eval_summary.get("rejected", [])),
            }

        # Каждые M сделок — ищем новые паттерны
        if self._trades_closed_count % HYPOTHESIS_DISCOVERY_INTERVAL == 0:
            discovered = await self.hypotheses.discover_patterns()
            result["hypotheses_discovered"] = len(discovered)

        # Логируем итог цикла
        conf_change = ""
        if result["confidence_before"] is not None and result["confidence_after"] is not None:
            delta = result["confidence_after"] - result["confidence_before"]
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
            conf_change = f"conf {result['confidence_before']:.3f} {arrow} {result['confidence_after']:.3f}"

        logger.info(
            f"Цикл обучения завершён: {trade.ticker} | "
            f"quality={result['quality']:.2f} | {conf_change}"
        )

        return result

    # ==========================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ==========================================================

    def _structural_filter_config(self, strategy_id: str) -> dict:
        """Конфиг filters.structural_downtrend из rules-файла стратегии.

        {} — если у стратегии нет фильтра или он выключен. Кешируется.
        """
        for prefix, rules_path in STRATEGY_RULES_FILES.items():
            if not (strategy_id or "").startswith(prefix):
                continue
            key = str(rules_path)
            if key not in self._filter_cfg_cache:
                cfg = {}
                try:
                    import yaml
                    with open(rules_path, encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    filters = data.get("filters") or {}
                    if isinstance(filters, dict):
                        cand = filters.get("structural_downtrend") or {}
                        if cand.get("enabled"):
                            cfg = cand
                except OSError as exc:
                    logger.warning("Не прочитан rules-файл %s: %s", rules_path, exc)
                self._filter_cfg_cache[key] = cfg
            return self._filter_cfg_cache[key]
        return {}

    async def _check_structural_downtrend(self, signal: dict) -> Optional[str]:
        """Проверить сигнал на структурный даунтренд по D1 (независимо от TF сигнала).

        Возвращает причину отказа (строку) или None, если торговать можно.
        Сам факт отказа пишется в skipped_signals через decision_evaluator.
        """
        strategy_id = signal.get("strategy_id") or ""
        ticker      = signal.get("ticker")
        direction   = (signal.get("direction") or "BUY").upper()

        cfg = self._structural_filter_config(strategy_id)
        if not cfg or not ticker:
            return None
        # apply_to: long — шорты не фильтруем
        if cfg.get("apply_to", "long") == "long" and direction not in ("BUY", "LONG"):
            return None
        direction = "BUY" if direction in ("BUY", "LONG") else "SELL"   # direction_type в БД

        sma_long = int(cfg.get("sma_long", 200))
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT time, close FROM candles
                WHERE ticker = $1 AND timeframe = '1d'
                ORDER BY time
            """, ticker)
        if len(rows) < sma_long:
            return None    # мало истории — фильтр не применяем

        import pandas as pd
        from signals.indicators import is_structural_downtrend

        df_d1 = pd.DataFrame(
            {"close": [float(r["close"]) for r in rows]},
            index=pd.DatetimeIndex([r["time"] for r in rows]),
        )
        params = {
            k: cfg[k]
            for k in ("sma_short", "sma_long", "lower_low_lookback", "lower_low_window")
            if k in cfg
        }
        if not is_structural_downtrend(df_d1, **params):
            return None

        await self.evaluator.log_skip(
            strategy_id = strategy_id,
            skip_reason = "structural_downtrend",
            ticker      = ticker,
            timeframe   = signal.get("timeframe"),
            direction   = direction,
            details     = {**params, "last_close": float(df_d1["close"].iloc[-1])},
            is_sandbox  = bool(signal.get("is_sandbox", True)),
        )
        return f"Структурный даунтренд {ticker} (D1): лонги запрещены фильтром"

    async def _get_strategy_stats(self, strategy_id: str) -> Optional[dict]:
        """Получить текущую статистику стратегии из belief_system."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM belief_system WHERE strategy_id = $1",
                strategy_id
            )
            return dict(row) if row else None

    async def _bootstrap_strategy(self, strategy_id: str) -> None:
        """Create a new strategy entry in belief_system with neutral confidence."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO belief_system
                        (strategy_id, strategy_name, market, confidence)
                    VALUES ($1, $2, 'stocks', 0.5)
                    ON CONFLICT (strategy_id) DO NOTHING
                """, strategy_id, strategy_id.replace("_", " ").title())
            logger.info("Bootstrapped belief_system entry for %s", strategy_id)
        except Exception as exc:
            logger.warning("Could not bootstrap strategy %s: %s", strategy_id, exc)

    async def _find_matching_hypotheses(self, signal: dict) -> list:
        """
        Найти active гипотезы, чьи условия совпадают с текущим сигналом.
        Эти гипотезы усиливают уверенность в сигнале.
        """
        active = await self.hypotheses.get_active_hypotheses()
        if not active:
            return []

        matched = []
        for hyp in active:
            import json
            conditions = hyp["conditions"]
            if isinstance(conditions, str):
                conditions = json.loads(conditions)

            # Проверяем совпадение основных условий
            if self._conditions_match(conditions, signal):
                matched.append({
                    "hypothesis_id": str(hyp["hypothesis_id"]),
                    "description":   hyp["description"],
                    "win_rate":      float(hyp["win_rate"]) if hyp["win_rate"] else None,
                })

        return matched

    def _conditions_match(self, conditions: dict, signal: dict) -> bool:
        """Проверить, совпадают ли условия гипотезы с параметрами сигнала."""
        # strategy_id
        if "strategy_id" in conditions:
            if conditions["strategy_id"] != signal.get("strategy_id"):
                return False

        # market_regime
        if "market_regime" in conditions:
            if conditions["market_regime"] != signal.get("market_regime"):
                return False

        # volume_ratio_above
        if "volume_ratio_above" in conditions:
            features = signal.get("market_features", {})
            vol = features.get("volume_ratio")
            if vol is None or vol <= conditions["volume_ratio_above"]:
                return False

        # bull/bear_div_count_min — минимальный кворум расхождений (0-3);
        # позволяет гипотезам вида «полный кворум 3/3 надёжнее» матчиться
        # с сигналами osc_range
        for key in ("bull_div_count_min", "bear_div_count_min"):
            if key in conditions:
                features = signal.get("market_features", {})
                val = features.get(key.removesuffix("_min"))
                if val is None or val < conditions[key]:
                    return False

        return True

    async def _update_or_insert_trade(self, trade: Trade) -> bool:
        """
        Обновить существующую сделку или создать новую.
        Используется при закрытии — сделка могла быть уже создана в on_trade_opened.
        """
        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM trades WHERE trade_id = $1",
                trade.trade_id
            )

            if exists:
                # Обновляем существующую запись
                if trade.pnl_r is None:
                    trade.pnl_r = trade.calculate_pnl_r()

                await conn.execute("""
                    UPDATE trades SET
                        closed_at        = $2,
                        exit_price       = $3,
                        exit_reason_type = $4,
                        exit_reason      = $5,
                        pnl              = $6,
                        pnl_r            = $7,
                        commission       = $8,
                        slippage         = $9,
                        max_drawdown     = $10
                    WHERE trade_id = $1
                """,
                    trade.trade_id,
                    trade.closed_at,
                    trade.exit_price,
                    trade.exit_reason_type.value if trade.exit_reason_type else None,
                    trade.exit_reason,
                    trade.pnl,
                    trade.pnl_r,
                    trade.commission,
                    trade.slippage,
                    trade.max_drawdown,
                )
                return True
            else:
                # Сделки нет — создаём полностью
                await self.memory.save_trade(trade)
                return False

    # ==========================================================
    # РУЧНОЙ ЗАПУСК ОБУЧЕНИЯ (для отладки)
    # ==========================================================

    async def run_full_learning_cycle(self) -> dict:
        """
        Запустить полный цикл обучения на всех накопленных сделках.
        Полезно после массовой загрузки исторических сделок из бэктеста.
        """
        logger.info("Запуск полного цикла обучения...")

        # 1. Оценить все неоценённые сделки
        evaluated = await self.evaluator.evaluate_pending()

        # 2. Пересчитать статистику всех стратегий
        belief_results = await self.beliefs.update_all()

        # 3. Найти новые паттерны
        discovered = await self.hypotheses.discover_patterns()

        # 4. Проверить все гипотезы на продвижение
        eval_summary = await self.hypotheses.evaluate_all()

        summary = {
            "trades_evaluated":     evaluated,
            "strategies_updated":   len(belief_results),
            "hypotheses_found":     len(discovered),
            "hypotheses_promoted":  len(eval_summary.get("promoted", [])),
            "hypotheses_rejected":  len(eval_summary.get("rejected", [])),
        }

        logger.info(f"Полный цикл обучения: {summary}")
        return summary


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

async def example():
    """Демонстрация работы оркестратора."""
    from decimal import Decimal
    from datetime import datetime, timezone
    try:
        from learning.memory_writer import Market, Direction, MarketRegime, ExitReasonType
    except ImportError:
        from memory_writer import Market, Direction, MarketRegime, ExitReasonType

    orchestrator = TradingOrchestrator()
    await orchestrator.connect()

    print("═══ TradingOrchestrator ═══\n")

    # 1. Проверяем сигнал (стоит ли открывать позицию?)
    signal = {
        "strategy_id": "breakout_moex",
        "market_regime": "trending",
        "market_features": {
            "rsi": 55.0,
            "volume_ratio": 1.8,
        }
    }

    print("1. Проверка сигнала...")
    decision = await orchestrator.check_signal(signal)
    print(f"   Одобрен: {decision['approved']}")
    print(f"   Confidence: {decision['confidence']:.2f}")
    print(f"   Множитель размера: {decision['position_size_multiplier']:.2f}")
    print(f"   Причина: {decision['reason']}")
    print(f"   Усиливающих гипотез: {len(decision['matched_hypotheses'])}\n")

    if not decision["approved"]:
        print("Сигнал не одобрен, торговля не начата")
        await orchestrator.disconnect()
        return

    # 2. Симулируем открытие сделки
    print("2. Открываем сделку...")
    trade = Trade(
        market          = Market.STOCKS,
        ticker          = "SBER",
        direction       = Direction.BUY,
        strategy_id     = "breakout_moex",
        entry_price     = Decimal("285.50"),
        stop_loss       = Decimal("282.00"),
        take_profit     = Decimal("292.00"),
        position_size   = Decimal("100"),
        risk_amount     = Decimal("350"),
        risk_percent    = Decimal("0.01"),
        market_regime   = MarketRegime.TRENDING,
        market_features = signal["market_features"],
        entry_reason    = "Пробой уровня с объёмом 1.8x",
        confidence      = decision["confidence"],
        opened_at       = datetime.now(timezone.utc),
        is_sandbox      = True,
    )
    trade_id = await orchestrator.on_trade_opened(trade)
    print(f"   Сделка открыта: {trade_id[:8]}...\n")

    # 3. Симулируем закрытие сделки
    print("3. Закрываем сделку (прибыль)...")
    trade.exit_price       = Decimal("291.20")
    trade.closed_at        = datetime.now(timezone.utc)
    trade.pnl              = Decimal("570")
    trade.commission       = Decimal("28.55")
    trade.slippage         = Decimal("0.10")
    trade.exit_reason_type = ExitReasonType.TAKE_PROFIT
    trade.exit_reason      = "Достигнут тейк"

    result = await orchestrator.on_trade_closed(trade)
    print(f"   Качество решения: {result['quality']:.2f}")
    print(f"   Случайность:      {result['randomness']:.2f}")
    print(f"   Confidence: {result['confidence_before']:.3f} → "
          f"{result['confidence_after']:.3f}\n")

    print("Цикл обучения отработал!")

    await orchestrator.disconnect()


if __name__ == "__main__":
    import asyncio
    import sys

    # Windows-консоль по умолчанию в cp1251 — символы ═ ↑ → не печатаются
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")

    asyncio.run(example())
