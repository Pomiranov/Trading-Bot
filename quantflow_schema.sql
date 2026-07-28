-- ============================================================
-- QuantFlow — Схема базы данных
-- PostgreSQL + TimescaleDB
-- Запустить один раз: psql -U trader -d trading_bot -f quantflow_schema.sql
-- ============================================================


-- ============================================================
-- РАСШИРЕНИЯ
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- генерация UUID
CREATE EXTENSION IF NOT EXISTS timescaledb;     -- временные ряды


-- ============================================================
-- ENUM ТИПЫ
-- ============================================================

-- Рынок
CREATE TYPE market_type AS ENUM (
    'stocks',       -- акции MOEX (SBER, GAZP, LKOH)
    'futures',      -- фьючерсы MOEX (Si, RTS, BR)
    'crypto'        -- крипто Bybit (BTCUSDT, ETHUSDT)
);

-- Направление сделки
CREATE TYPE direction_type AS ENUM (
    'BUY',
    'SELL'
);

-- Режим рынка
CREATE TYPE regime_type AS ENUM (
    'trending',     -- направленное движение
    'ranging',      -- боковик
    'volatile'      -- высокая волатильность
);

-- Причина выхода из сделки
CREATE TYPE exit_reason_type AS ENUM (
    'stop_loss',    -- выбит стоп
    'take_profit',  -- достигнут тейк
    'signal',       -- сигнал на разворот
    'manual',       -- ручное закрытие
    'expiration'    -- экспирация (для фьючерсов)
);

-- Стадия гипотезы
CREATE TYPE hypothesis_stage AS ENUM (
    'observation',  -- 30+ сделок, только наблюдение
    'candidate',    -- 100+ сделок, статистические тесты
    'active',       -- 300+ сделок, влияет на торговлю
    'rejected'      -- отклонена по результатам тестов
);


-- ============================================================
-- ТАБЛИЦА 1: trades
-- Каждая сделка записывается навсегда, ничего не удаляется
-- ============================================================

CREATE TABLE trades (

    -- Идентификация
    trade_id            UUID            DEFAULT uuid_generate_v4() PRIMARY KEY,
    opened_at           TIMESTAMPTZ     NOT NULL,
    closed_at           TIMESTAMPTZ,

    -- Рыночный контекст
    market              market_type     NOT NULL,
    ticker              VARCHAR(20)     NOT NULL,
    timeframe           VARCHAR(10)     NOT NULL DEFAULT 'H1',
    market_regime       regime_type,
    market_features     JSONB,
    -- Пример market_features:
    -- {
    --   "rsi": 28.5,
    --   "atr": 12.3,
    --   "adx": 31.0,
    --   "volume_ratio": 1.8,
    --   "ema50_slope": 0.12,
    --   "bb_width": 0.045
    -- }

    -- Решение бота
    strategy_id         VARCHAR(50)     NOT NULL,
    direction           direction_type  NOT NULL,
    entry_reason        TEXT,
    exit_reason_type    exit_reason_type,
    exit_reason         TEXT,
    expected_value      DECIMAL(10,4),
    confidence          DECIMAL(5,4)    CHECK (confidence BETWEEN 0 AND 1),

    -- Цены и риск
    entry_price         DECIMAL(20,8)   NOT NULL,
    exit_price          DECIMAL(20,8),
    stop_loss           DECIMAL(20,8)   NOT NULL,
    take_profit         DECIMAL(20,8),
    position_size       DECIMAL(20,8)   NOT NULL,
    risk_amount         DECIMAL(20,4)   NOT NULL,
    risk_percent        DECIMAL(5,4),   -- % от капитала (обычно 0.01 = 1%)

    -- Результат
    pnl                 DECIMAL(20,4),  -- прибыль/убыток в рублях или USDT
    pnl_r               DECIMAL(10,4),  -- результат в R (1R = риск на сделку)
    commission          DECIMAL(20,4)   DEFAULT 0,
    slippage            DECIMAL(20,8)   DEFAULT 0,
    max_drawdown        DECIMAL(20,4),  -- макс просадка во время сделки

    -- Оценка качества решения (независимо от результата)
    decision_quality    DECIMAL(5,4)    CHECK (decision_quality BETWEEN 0 AND 1),
    strategy_followed   BOOLEAN         DEFAULT true,
    randomness_factor   DECIMAL(5,4)    CHECK (randomness_factor BETWEEN 0 AND 1),
    notes               TEXT,

    -- Режим торговли
    is_sandbox          BOOLEAN         DEFAULT true,

    -- Привязка к набору правил (долг №30, добавлено 2026-07-28).
    -- Колонки объявлены ЗДЕСЬ, а не в bot/learning/feedback.py, сознательно:
    -- этот файл — документированный первый шаг чистой установки
    -- (docs/LOCAL_DEVELOPMENT.md, docs/WINDOWS_DEPLOYMENT.md, psql -f), а
    -- легаси-DDL выполняется только при импорте feedback.py. До правки
    -- signal_rules существовала лишь как ALTER TABLE в легаси-модуле, поэтому на
    -- чистой БД запись из memory_writer упала бы, пока его никто не импортировал.
    signal_rules        TEXT[],         -- ИМЕНА сработавших правил
    rules_version       TEXT,           -- отпечаток разобранного yaml; 'unknown' =
                                        -- строка записана до введения отпечатка
    origin              TEXT,           -- 'forward' | 'backtest' | 'live'.
                                        -- is_sandbox различителем НЕ является:
                                        -- он про бумагу против реальных денег,
                                        -- а форвард тоже is_sandbox = true

    -- Служебные
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    broker_order_id     VARCHAR(100)    -- ID ордера в Tinkoff или Bybit

);

-- TimescaleDB: превращаем trades в hypertable по времени открытия
SELECT create_hypertable('trades', 'opened_at');

-- Индексы для быстрых запросов
CREATE INDEX idx_trades_market     ON trades (market);
CREATE INDEX idx_trades_ticker     ON trades (ticker);
CREATE INDEX idx_trades_strategy   ON trades (strategy_id);
CREATE INDEX idx_trades_regime     ON trades (market_regime);
CREATE INDEX idx_trades_sandbox    ON trades (is_sandbox);


-- ============================================================
-- ТАБЛИЦА 2: belief_system
-- Статистика по каждой стратегии, обновляется после каждой сделки
-- Фундаментальные правила НЕ хранятся здесь — они в knowledge/
-- ============================================================

CREATE TABLE belief_system (

    -- Идентификация стратегии
    strategy_id         VARCHAR(50)     PRIMARY KEY,
    strategy_name       VARCHAR(100)    NOT NULL,
    market              market_type     NOT NULL,
    description         TEXT,

    -- Статистика (обновляется автоматически)
    total_trades        INTEGER         DEFAULT 0,
    winning_trades      INTEGER         DEFAULT 0,
    losing_trades       INTEGER         DEFAULT 0,

    win_rate            DECIMAL(5,4),   -- доля прибыльных сделок
    profit_factor       DECIMAL(10,4),  -- сумма прибылей / сумма убытков
    expectancy          DECIMAL(10,4),  -- среднее R на сделку
    sharpe_ratio        DECIMAL(10,4),  -- доходность / волатильность
    avg_win_r           DECIMAL(10,4),  -- средний выигрыш в R
    avg_loss_r          DECIMAL(10,4),  -- средний проигрыш в R
    max_consecutive_losses INTEGER DEFAULT 0,

    -- Уровень доверия (ключевое поле)
    -- Растёт когда стратегия работает, падает когда нет
    -- Бот использует стратегию реже если confidence низкий
    confidence          DECIMAL(5,4)    DEFAULT 0.5
                        CHECK (confidence BETWEEN 0 AND 1),

    -- Лучший контекст для стратегии
    best_regime         regime_type,
    best_timeframe      VARCHAR(10),

    -- Служебные
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     DEFAULT NOW(),
    last_trade_at       TIMESTAMPTZ

);

-- Стартовые стратегии для MOEX и Bybit
INSERT INTO belief_system
    (strategy_id, strategy_name, market, description) VALUES
    ('breakout_moex',   'Пробой уровня',        'stocks',  'Пробой ключевого уровня с объёмом'),
    ('trend_moex',      'Следование тренду',    'stocks',  'Вход по тренду на откате к EMA'),
    ('gap_moex',        'Торговля гэпа',        'stocks',  'Закрытие гэпа на открытии сессии'),
    ('momentum_bybit',  'Моментум',             'crypto',  'Вход на сильном импульсе с объёмом'),
    ('trend_bybit',     'Тренд крипто',         'crypto',  'Следование тренду BTC/ETH на H1'),
    ('funding_bybit',   'Funding Rate',         'crypto',  'Торговля против экстремального funding');


-- ============================================================
-- ТАБЛИЦА 3: hypotheses
-- Паттерны найденные ботом, три стадии зрелости
-- В торговле используются только active гипотезы
-- ============================================================

CREATE TABLE hypotheses (

    -- Идентификация
    hypothesis_id       UUID            DEFAULT uuid_generate_v4() PRIMARY KEY,
    description         TEXT            NOT NULL,
    market              market_type,

    -- Стадия: observation → candidate → active (или rejected)
    stage               hypothesis_stage DEFAULT 'observation',

    -- Условия гипотезы в JSON
    -- Пример:
    -- {
    --   "rsi_below": 30,
    --   "volume_ratio_above": 1.5,
    --   "market_regime": "trending",
    --   "day_of_week": "friday"
    -- }
    conditions          JSONB           NOT NULL,

    -- Статистика
    total_trades        INTEGER         DEFAULT 0,
    winning_trades      INTEGER         DEFAULT 0,
    win_rate            DECIMAL(5,4),
    profit_factor       DECIMAL(10,4),
    expectancy          DECIMAL(10,4),
    confidence          DECIMAL(5,4)    CHECK (confidence BETWEEN 0 AND 1),

    -- Результаты статистических тестов (Stage 2+)
    -- {
    --   "binomial_p_value": 0.03,
    --   "bootstrap_expectancy_ci": [0.12, 0.48],
    --   "walk_forward_passed": true
    -- }
    stat_test_result    JSONB,

    -- Временные метки
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    promoted_at         TIMESTAMPTZ,    -- когда переведена в следующую стадию
    rejected_at         TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ     DEFAULT NOW()

);

-- Индексы
CREATE INDEX idx_hypotheses_stage  ON hypotheses (stage);
CREATE INDEX idx_hypotheses_market ON hypotheses (market);


-- ============================================================
-- ТАБЛИЦА 4: skipped_signals
-- Сигналы, отклонённые ДО открытия позиции (фильтры, confidence).
-- Нужна чтобы обучение видело не только сделки, но и отказы.
-- ============================================================

CREATE TABLE skipped_signals (
    skip_id             UUID            DEFAULT uuid_generate_v4() PRIMARY KEY,
    skipped_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    strategy_id         VARCHAR(50)     NOT NULL,
    ticker              VARCHAR(20),
    timeframe           VARCHAR(10),
    direction           direction_type,

    skip_reason         VARCHAR(50)     NOT NULL,   -- напр. 'structural_downtrend'
    details             JSONB,                      -- параметры фильтра, значения индикаторов

    is_sandbox          BOOLEAN         DEFAULT true
);

CREATE INDEX idx_skipped_strategy ON skipped_signals (strategy_id);
CREATE INDEX idx_skipped_reason   ON skipped_signals (skip_reason);


-- ============================================================
-- ТАБЛИЦА 5: forward_state
-- Идемпотентность форвард-контура (run_forward_d1.py):
-- какая последняя свеча тикера уже обработана.
-- ============================================================

CREATE TABLE forward_state (
    strategy_id         VARCHAR(50)     NOT NULL,
    ticker              VARCHAR(20)     NOT NULL,
    last_candle_time    TIMESTAMPTZ     NOT NULL,
    updated_at          TIMESTAMPTZ     DEFAULT NOW(),
    PRIMARY KEY (strategy_id, ticker)
);


-- ============================================================
-- ТАБЛИЦА 6: forward_catchup_log
-- Постоянная запись каждого догона пропущенных баров
-- (run_forward_d1.py). Сторож (forward_healthcheck.py) — сигнализация,
-- а не запись: он видит только две конечные точки своего файла состояния
-- и назавтра разрыв уже не отличит. Улика должна жить здесь.
--
-- Строка пишется, когда gap_bars >= 1 или найдены дубли — не каждый день,
-- иначе журнал утонет в 12 пустых строках в сутки. В норме разрыва нет.
--
-- Побочная цель: накопить РАСПРЕДЕЛЕНИЕ длин разрывов. Сейчас известны
-- две точки (безобидные <=2 бара, один реальный сбой 13 баров), и предел
-- догона CATCHUP_MAX_BARS выбран в диапазоне, где наблюдений нет вовсе.
-- Через полгода этих строк хватит, чтобы выбрать его по данным.
-- ============================================================

CREATE TABLE forward_catchup_log (
    log_id          BIGSERIAL       PRIMARY KEY,
    logged_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    strategy_id     VARCHAR(50)     NOT NULL,
    ticker          VARCHAR(20)     NOT NULL,

    state_before    TIMESTAMPTZ,                    -- NULL = первый прогон тикера
    gap_bars        INTEGER         NOT NULL,       -- исторических баров в разрыве
    bars_processed  INTEGER         NOT NULL,       -- из них догнано (только выходы)
    bars_discarded  INTEGER         NOT NULL,       -- признано потерянными
    first_bar       TIMESTAMPTZ,                    -- первый догнанный бар
    last_bar        TIMESTAMPTZ,                    -- последний догнанный бар
    flagged         BOOLEAN         NOT NULL DEFAULT false,

    exits           JSONB,      -- [{bar, price, reason_type, reason, trade_id}]
    duplicates      JSONB       -- [{date, times: [...]}] — бары-двойники в разрыве
);

CREATE INDEX idx_catchup_ticker ON forward_catchup_log (strategy_id, ticker, logged_at DESC);


-- ============================================================
-- ФУНКЦИЯ: автообновление updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_belief_updated_at
    BEFORE UPDATE ON belief_system
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_hypotheses_updated_at
    BEFORE UPDATE ON hypotheses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ============================================================
-- ПРОВЕРКА: убеждаемся что всё создалось
-- ============================================================

SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_name = t.table_name) AS columns_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('trades', 'belief_system', 'hypotheses')
ORDER BY table_name;
