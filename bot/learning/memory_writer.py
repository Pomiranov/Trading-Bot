"""
QuantFlow — memory_writer.py
============================
Записывает каждую сделку в PostgreSQL после закрытия позиции.
Никакие данные не удаляются и не изменяются после записи.

Использование:
    writer = MemoryWriter()
    await writer.save_trade(trade)
"""

import json
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# НАСТРОЙКА ЛОГГЕРА
# ============================================================

logger = logging.getLogger("quantflow.memory")


# ============================================================
# ENUM ТИПЫ (совпадают с типами в БД)
# ============================================================

class Market(str, Enum):
    STOCKS  = "stocks"    # акции MOEX
    FUTURES = "futures"   # фьючерсы MOEX
    CRYPTO  = "crypto"    # крипто Bybit


class Direction(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING  = "ranging"
    VOLATILE = "volatile"


class ExitReasonType(str, Enum):
    STOP_LOSS   = "stop_loss"
    TAKE_PROFIT = "take_profit"
    SIGNAL      = "signal"
    MANUAL      = "manual"
    EXPIRATION  = "expiration"
    # Вынужденный выход после разрыва форварда: часть баров признана потерянной
    # (run_forward_d1.py, догон глубже CATCHUP_MAX_BARS), поэтому настоящее
    # пробитие стопа могло случиться на выброшенном баре по цене, которой мы не
    # видели. Отдельный тип, а не STOP_LOSS: иначе в статистику попадёт чистый
    # стоп, которого не было. И не MANUAL: тот занят paper-движком под
    # «человек закрыл вручную» (engine/paper_engine.py:463).
    GAP_FORCED  = "gap_forced"


# ============================================================
# DATACLASS: Trade
# Одна запись = одна завершённая сделка
# ============================================================

@dataclass
class Trade:
    """Полное описание одной сделки."""

    # --- Обязательные поля ---
    market:         Market
    ticker:         str
    direction:      Direction
    strategy_id:    str
    entry_price:    Decimal
    stop_loss:      Decimal
    position_size:  Decimal
    risk_amount:    Decimal

    # --- Время ---
    opened_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at:      Optional[datetime] = None

    # --- Рыночный контекст ---
    timeframe:      str = "H1"
    market_regime:  Optional[MarketRegime] = None
    market_features: Optional[dict] = None
    # Пример market_features:
    # {
    #   "rsi": 28.5,
    #   "atr": 12.3,
    #   "adx": 31.0,
    #   "volume_ratio": 1.8,
    #   "ema50_slope": 0.12
    # }

    # --- Решение ---
    take_profit:    Optional[Decimal] = None
    entry_reason:   Optional[str] = None
    exit_reason_type: Optional[ExitReasonType] = None
    exit_reason:    Optional[str] = None
    expected_value: Optional[Decimal] = None
    confidence:     Optional[Decimal] = None

    # --- Цены выхода ---
    exit_price:     Optional[Decimal] = None
    risk_percent:   Optional[Decimal] = None

    # --- Результат ---
    pnl:            Optional[Decimal] = None
    pnl_r:          Optional[Decimal] = None
    commission:     Decimal = Decimal("0")
    slippage:       Decimal = Decimal("0")
    max_drawdown:   Optional[Decimal] = None

    # --- Оценка качества ---
    decision_quality:   Optional[Decimal] = None
    strategy_followed:  bool = True
    randomness_factor:  Optional[Decimal] = None
    notes:              Optional[str] = None

    # --- Служебные ---
    is_sandbox:         bool = True
    broker_order_id:    Optional[str] = None

    # --- Привязка к набору правил (долг №30) ---
    # Без этих трёх полей строка не атрибутируема, а belief_system и hypotheses
    # описывают неизвестно что: до 28.07 так было во всех 7 532 строках.
    #
    # signal_rules  — ИМЕНА сработавших правил. Их одних недостаточно: две версии
    #                 одного правила с разными параметрами носят одно имя (ровно
    #                 случай trend_moex, EMA21 против EMA50).
    # rules_version — отпечаток всего разобранного yaml (RulesEngine.rules_version).
    #                 Штампуется при ОТКРЫТИИ: если yaml правится между открытием и
    #                 закрытием, выход исполнен по другим exit_rules, чем записанный
    #                 отпечаток. Отпечаток описывает РЕШЕНИЕ О ВХОДЕ — для метки
    #                 decision_quality это приемлемо, но знать об этом надо.
    # origin        — 'forward' | 'backtest' | 'live'. Отдельное поле, потому что
    #                 is_sandbox различителем НЕ является: он про бумагу против
    #                 реальных денег, и форвард тоже is_sandbox=true. Без origin
    #                 бэктестовые прогоны попадали бы в обучающую выборку как
    #                 полноправные.
    signal_rules:       Optional[list] = None
    rules_version:      Optional[str] = None
    origin:             Optional[str] = None

    # Генерируется автоматически
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def calculate_pnl_r(self) -> Optional[Decimal]:
        """Рассчитать результат в R (1R = риск на сделку)."""
        if self.pnl is not None and self.risk_amount and self.risk_amount != 0:
            return self.pnl / self.risk_amount
        return None

    def validate(self) -> list[str]:
        """Проверить что все обязательные поля заполнены. Вернуть список ошибок."""
        errors = []
        if not self.ticker:
            errors.append("ticker не может быть пустым")
        if self.entry_price <= 0:
            errors.append("entry_price должна быть больше 0")
        if self.stop_loss <= 0:
            errors.append("stop_loss должен быть больше 0")
        if self.position_size <= 0:
            errors.append("position_size должен быть больше 0")
        if self.risk_amount <= 0:
            errors.append("risk_amount должен быть больше 0")
        if self.confidence is not None and not (0 <= self.confidence <= 1):
            errors.append("confidence должен быть от 0 до 1")
        if self.decision_quality is not None and not (0 <= self.decision_quality <= 1):
            errors.append("decision_quality должен быть от 0 до 1")
        return errors


# ============================================================
# КЛАСС: MemoryWriter
# ============================================================

class MemoryWriter:
    """
    Записывает сделки в PostgreSQL.
    Использует asyncpg для асинхронной работы с БД.
    """

    def __init__(self, dsn: Optional[str] = None):
        """
        dsn — строка подключения к БД.
        Если не указана — берётся из переменных окружения.
        """
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Создать пул соединений с БД."""
        import os

        if self._dsn is None:
            # Берём параметры из .env
            host     = os.getenv("DB_HOST", "localhost")
            port     = os.getenv("DB_PORT", "5432")
            name     = os.getenv("DB_NAME", "trading_bot")
            user     = os.getenv("DB_USER", "trader")
            password = os.getenv("DB_PASSWORD", "")
            self._dsn = f"postgresql://{user}:{password}@{host}:{port}/{name}"

        async def _init_connection(conn: asyncpg.Connection) -> None:
            # asyncpg не преобразует dict <-> jsonb сам — нужен кодек
            await conn.set_type_codec(
                "jsonb",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
            )

        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=1,
            max_size=5,
            init=_init_connection,
        )
        logger.info("MemoryWriter: подключение к БД установлено")

    async def disconnect(self) -> None:
        """Закрыть пул соединений."""
        if self._pool:
            await self._pool.close()
            logger.info("MemoryWriter: подключение закрыто")

    # ----------------------------------------------------------
    # ГЛАВНЫЙ МЕТОД: сохранить сделку
    # ----------------------------------------------------------

    async def save_trade(self, trade: Trade) -> str:
        """
        Записать завершённую сделку в таблицу trades.
        Возвращает trade_id записанной сделки.
        """
        # 1. Валидация
        errors = trade.validate()
        if errors:
            raise ValueError(f"Сделка не прошла валидацию: {errors}")

        # 2. Автоматически рассчитать pnl_r если не задан
        if trade.pnl_r is None:
            trade.pnl_r = trade.calculate_pnl_r()

        # 3. Записать в БД
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO trades (
                    trade_id,
                    opened_at,
                    closed_at,
                    market,
                    ticker,
                    timeframe,
                    market_regime,
                    market_features,
                    strategy_id,
                    direction,
                    entry_reason,
                    exit_reason_type,
                    exit_reason,
                    expected_value,
                    confidence,
                    entry_price,
                    exit_price,
                    stop_loss,
                    take_profit,
                    position_size,
                    risk_amount,
                    risk_percent,
                    pnl,
                    pnl_r,
                    commission,
                    slippage,
                    max_drawdown,
                    decision_quality,
                    strategy_followed,
                    randomness_factor,
                    notes,
                    is_sandbox,
                    broker_order_id,
                    -- Привязка сделки к набору правил (долг №30). Без этих трёх
                    -- полей строка не атрибутируема: имена правил не различают
                    -- версии одного правила с разными параметрами, а origin
                    -- отличает форвард от бэктеста — is_sandbox этого не делает,
                    -- он про бумагу против реальных денег.
                    signal_rules,
                    rules_version,
                    origin
                ) VALUES (
                    $1,  $2,  $3,  $4,  $5,
                    $6,  $7,  $8,  $9,  $10,
                    $11, $12, $13, $14, $15,
                    $16, $17, $18, $19, $20,
                    $21, $22, $23, $24, $25,
                    $26, $27, $28, $29, $30,
                    $31, $32, $33, $34, $35,
                    $36
                )
            """,
                trade.trade_id,
                trade.opened_at,
                trade.closed_at,
                trade.market.value,
                trade.ticker,
                trade.timeframe,
                trade.market_regime.value if trade.market_regime else None,
                trade.market_features,
                trade.strategy_id,
                trade.direction.value,
                trade.entry_reason,
                trade.exit_reason_type.value if trade.exit_reason_type else None,
                trade.exit_reason,
                trade.expected_value,
                trade.confidence,
                trade.entry_price,
                trade.exit_price,
                trade.stop_loss,
                trade.take_profit,
                trade.position_size,
                trade.risk_amount,
                trade.risk_percent,
                trade.pnl,
                trade.pnl_r,
                trade.commission,
                trade.slippage,
                trade.max_drawdown,
                trade.decision_quality,
                trade.strategy_followed,
                trade.randomness_factor,
                trade.notes,
                trade.is_sandbox,
                trade.broker_order_id,
                trade.signal_rules,
                trade.rules_version,
                trade.origin,
            )

        logger.info(
            f"Сделка записана: {trade.trade_id} | "
            f"{trade.market.value} | {trade.ticker} | "
            f"{trade.direction.value} | PnL: {trade.pnl}"
        )

        return trade.trade_id

    # ----------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ----------------------------------------------------------

    async def get_last_trades(
        self,
        market: Optional[Market] = None,
        limit: int = 10
    ) -> list[dict]:
        """Получить последние сделки из БД."""
        if not self._pool:
            await self.connect()

        params: list = []

        if market:
            params.append(market.value)
            where = " WHERE market = $1"
        else:
            where = ""

        params.append(min(int(limit), 500))
        limit_placeholder = f"${len(params)}"

        query = f"SELECT * FROM trades{where} ORDER BY opened_at DESC LIMIT {limit_placeholder}"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_trade_count(self, strategy_id: Optional[str] = None) -> int:
        """Получить количество сделок (всего или по стратегии)."""
        if not self._pool:
            await self.connect()

        async with self._pool.acquire() as conn:
            if strategy_id:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM trades WHERE strategy_id = $1",
                    strategy_id
                )
            else:
                count = await conn.fetchval("SELECT COUNT(*) FROM trades")
            return count


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

async def example():
    """Пример: записать тестовую сделку по SBER."""
    from decimal import Decimal
    from datetime import datetime, timezone

    writer = MemoryWriter()
    await writer.connect()

    # Создаём сделку
    trade = Trade(
        market          = Market.STOCKS,
        ticker          = "SBER",
        direction       = Direction.BUY,
        strategy_id     = "breakout_moex",
        entry_price     = Decimal("285.50"),
        exit_price      = Decimal("291.20"),
        stop_loss       = Decimal("282.00"),
        take_profit     = Decimal("292.00"),
        position_size   = Decimal("100"),
        risk_amount     = Decimal("350.00"),
        risk_percent    = Decimal("0.01"),

        opened_at       = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        closed_at       = datetime(2024, 1, 15, 14, 45, tzinfo=timezone.utc),

        market_regime   = MarketRegime.TRENDING,
        timeframe       = "H1",

        market_features = {
            "rsi": 45.2,
            "atr": 3.8,
            "adx": 28.5,
            "volume_ratio": 1.9,
            "ema50_slope": 0.08
        },

        pnl             = Decimal("570.00"),
        commission      = Decimal("28.55"),
        slippage        = Decimal("0.10"),

        entry_reason    = "Пробой уровня 285 с объёмом выше среднего в 1.9x",
        exit_reason     = "Достигнут тейк-профит 292.00",
        exit_reason_type = ExitReasonType.TAKE_PROFIT,

        expected_value  = Decimal("0.85"),
        confidence      = Decimal("0.72"),
        decision_quality = Decimal("0.80"),
        strategy_followed = True,
        randomness_factor = Decimal("0.15"),

        notes           = "Чистый пробой, хороший объём, режим тренд",
        is_sandbox      = True,
    )

    # Записываем
    trade_id = await writer.save_trade(trade)
    print(f"Записана сделка: {trade_id}")

    # Проверяем
    count = await writer.get_trade_count()
    print(f"Всего сделок в БД: {count}")

    await writer.disconnect()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
