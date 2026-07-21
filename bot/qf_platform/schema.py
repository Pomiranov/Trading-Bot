"""DDL for platform tables — idempotent migrations."""

PLATFORM_SCHEMA_SQL = """
-- ── Full trades table for learning system + platform ─────────────────────────
-- NOTE: This is the canonical trades schema used by both memory_writer.py and
-- the platform layer. Any simplified schema is superseded by this definition.
CREATE TABLE IF NOT EXISTS trades (
    -- Identification (UUID primary key for learning system)
    trade_id            VARCHAR(36)     DEFAULT gen_random_uuid()::text,
    opened_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,

    -- Market context
    market              VARCHAR(20)     NOT NULL DEFAULT 'stocks',
    ticker              VARCHAR(20)     NOT NULL,
    timeframe           VARCHAR(10)     NOT NULL DEFAULT 'H1',
    market_regime       VARCHAR(20),
    market_features     JSONB,

    -- Decision
    strategy_id         VARCHAR(50)     NOT NULL DEFAULT 'default',
    direction           VARCHAR(8)      NOT NULL DEFAULT 'BUY',
    entry_reason        TEXT,
    exit_reason_type    VARCHAR(20),
    exit_reason         TEXT,
    expected_value      NUMERIC(10,4),
    confidence          NUMERIC(5,4)    CHECK (confidence BETWEEN 0 AND 1),

    -- Prices and risk
    entry_price         NUMERIC(20,8)   NOT NULL DEFAULT 0,
    exit_price          NUMERIC(20,8),
    stop_loss           NUMERIC(20,8)   NOT NULL DEFAULT 0,
    take_profit         NUMERIC(20,8),
    position_size       NUMERIC(20,8)   NOT NULL DEFAULT 0,
    risk_amount         NUMERIC(20,4)   NOT NULL DEFAULT 0,
    risk_percent        NUMERIC(5,4),

    -- Result
    pnl                 NUMERIC(20,4),
    pnl_r               NUMERIC(10,4),
    commission          NUMERIC(20,4)   DEFAULT 0,
    slippage            NUMERIC(20,8)   DEFAULT 0,
    max_drawdown        NUMERIC(20,4),

    -- Quality evaluation
    decision_quality    NUMERIC(5,4)    CHECK (decision_quality BETWEEN 0 AND 1),
    strategy_followed   BOOLEAN         DEFAULT true,
    randomness_factor   NUMERIC(5,4)    CHECK (randomness_factor BETWEEN 0 AND 1),
    notes               TEXT,

    -- Mode
    is_sandbox          BOOLEAN         DEFAULT true,
    broker_order_id     VARCHAR(100),

    -- Platform compat (legacy integer id for foreign keys in other tables)
    id                  SERIAL,
    created_at          TIMESTAMPTZ     DEFAULT NOW(),

    PRIMARY KEY (trade_id)
);

-- Idempotent: add legacy integer id index if missing
CREATE INDEX IF NOT EXISTS idx_trades_id      ON trades (id);
CREATE INDEX IF NOT EXISTS idx_trades_closed  ON trades (closed_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_trades_ticker  ON trades (ticker);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades (strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_sandbox  ON trades (is_sandbox);

-- Idempotent migrations: add missing columns to existing simplified trades table
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trade_id         VARCHAR(36)   DEFAULT gen_random_uuid()::text;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market           VARCHAR(20)   NOT NULL DEFAULT 'stocks';
ALTER TABLE trades ADD COLUMN IF NOT EXISTS timeframe        VARCHAR(10)   NOT NULL DEFAULT 'H1';
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_regime    VARCHAR(20);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS market_features  JSONB;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS strategy_id      VARCHAR(50)   NOT NULL DEFAULT 'default';
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_reason_type VARCHAR(20);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_reason      TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS expected_value   NUMERIC(10,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS confidence       NUMERIC(5,4)  CHECK (confidence BETWEEN 0 AND 1);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exit_price       NUMERIC(20,8);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stop_loss        NUMERIC(20,8) NOT NULL DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS take_profit      NUMERIC(20,8);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS position_size    NUMERIC(20,8) NOT NULL DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS risk_amount      NUMERIC(20,4) NOT NULL DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS risk_percent     NUMERIC(5,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pnl_r            NUMERIC(10,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS commission       NUMERIC(20,4) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS slippage         NUMERIC(20,8) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS max_drawdown     NUMERIC(20,4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS decision_quality NUMERIC(5,4)  CHECK (decision_quality BETWEEN 0 AND 1);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS strategy_followed BOOLEAN      DEFAULT true;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS randomness_factor NUMERIC(5,4) CHECK (randomness_factor BETWEEN 0 AND 1);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS notes            TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS is_sandbox       BOOLEAN       DEFAULT true;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS broker_order_id  VARCHAR(100);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_reason     TEXT;

-- Unique index on trade_id for learning system lookups (idempotent)
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_trade_id ON trades (trade_id) WHERE trade_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS candles (
    id        BIGSERIAL PRIMARY KEY,
    ticker    VARCHAR(32)    NOT NULL,
    timeframe VARCHAR(8)     NOT NULL,
    time      TIMESTAMPTZ    NOT NULL,
    open      NUMERIC(18, 4) NOT NULL,
    high      NUMERIC(18, 4) NOT NULL,
    low       NUMERIC(18, 4) NOT NULL,
    close     NUMERIC(18, 4) NOT NULL,
    volume    BIGINT         NOT NULL DEFAULT 0,
    UNIQUE (ticker, timeframe, time)
);

CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles (ticker, timeframe, time DESC);

CREATE TABLE IF NOT EXISTS paper_accounts (
    id                SERIAL PRIMARY KEY,
    user_id           VARCHAR(64)   NOT NULL DEFAULT 'default',
    mode              VARCHAR(10)   NOT NULL DEFAULT 'rub',
    initial_balance   NUMERIC(18,4) NOT NULL,
    balance           NUMERIC(18,4) NOT NULL,
    available_balance NUMERIC(18,4) NOT NULL,
    margin_used       NUMERIC(18,4) NOT NULL DEFAULT 0,
    currency          VARCHAR(8)    NOT NULL,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, mode)
);

CREATE TABLE IF NOT EXISTS paper_positions (
    id              SERIAL PRIMARY KEY,
    account_id      INTEGER       NOT NULL REFERENCES paper_accounts(id) ON DELETE CASCADE,
    ticker          VARCHAR(32)   NOT NULL,
    exchange        VARCHAR(32)   NOT NULL DEFAULT 'paper',
    direction       VARCHAR(8)    NOT NULL,
    quantity        NUMERIC(18,8) NOT NULL,
    entry_price     NUMERIC(18,4) NOT NULL,
    stop_loss       NUMERIC(18,4),
    take_profit     NUMERIC(18,4),
    unrealized_pnl  NUMERIC(18,4) NOT NULL DEFAULT 0,
    opened_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_account ON paper_positions (account_id);

CREATE TABLE IF NOT EXISTS paper_trades (
    id              SERIAL PRIMARY KEY,
    account_id      INTEGER       NOT NULL REFERENCES paper_accounts(id) ON DELETE CASCADE,
    position_id     INTEGER,
    ticker          VARCHAR(32)   NOT NULL,
    exchange        VARCHAR(32)   NOT NULL DEFAULT 'paper',
    direction       VARCHAR(8)    NOT NULL,
    entry_price     NUMERIC(18,4) NOT NULL,
    exit_price      NUMERIC(18,4) NOT NULL,
    quantity        NUMERIC(18,8) NOT NULL,
    pnl             NUMERIC(18,4) NOT NULL,
    pnl_pct         NUMERIC(10,6) NOT NULL,
    opened_at       TIMESTAMPTZ   NOT NULL,
    closed_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_account ON paper_trades (account_id, closed_at DESC);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id          SERIAL PRIMARY KEY,
    account_id  INTEGER,
    source      VARCHAR(32)   NOT NULL,
    equity      NUMERIC(18,4) NOT NULL,
    snapshot_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_equity_snapshots_source ON equity_snapshots (source, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS trading_signals (
    id              SERIAL PRIMARY KEY,
    asset           VARCHAR(32)   NOT NULL,
    exchange        VARCHAR(32)   NOT NULL,
    timeframe       VARCHAR(16)   NOT NULL DEFAULT '1d',
    signal_type     VARCHAR(8)    NOT NULL,
    entry_price     NUMERIC(18,4),
    stop_loss       NUMERIC(18,4),
    take_profit_1   NUMERIC(18,4),
    take_profit_2   NUMERIC(18,4),
    take_profit_3   NUMERIC(18,4),
    risk_reward     NUMERIC(8,4),
    probability_pct NUMERIC(5,2),
    generated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    status          VARCHAR(20)   NOT NULL DEFAULT 'new',
    source          VARCHAR(32)   NOT NULL DEFAULT 'indicators',
    asset_class     VARCHAR(16)   NOT NULL DEFAULT 'stocks',
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_trading_signals_generated ON trading_signals (generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_trading_signals_exchange ON trading_signals (exchange, asset_class);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id               SERIAL PRIMARY KEY,
    strategy         VARCHAR(64)   NOT NULL DEFAULT 'rules_engine',
    exchange         VARCHAR(32)   NOT NULL DEFAULT 'moex',
    ticker           VARCHAR(32)   NOT NULL,
    period_start     DATE,
    period_end       DATE,
    initial_capital  NUMERIC(18,4) NOT NULL,
    risk_pct         NUMERIC(8,4)  NOT NULL DEFAULT 0.05,
    commission_pct   NUMERIC(8,6)  NOT NULL DEFAULT 0.0003,
    slippage_pct     NUMERIC(8,6)  NOT NULL DEFAULT 0.0001,
    leverage         NUMERIC(8,2)  NOT NULL DEFAULT 1,
    results          JSONB         NOT NULL,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_created ON backtest_runs (created_at DESC);

CREATE TABLE IF NOT EXISTS news (
    id           SERIAL PRIMARY KEY,
    published_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    source       VARCHAR(64),
    title        TEXT          NOT NULL,
    sentiment    NUMERIC(5,4)  DEFAULT 0,
    importance   INTEGER       DEFAULT 1,
    url          TEXT
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news (published_at DESC);

CREATE TABLE IF NOT EXISTS system_events (
    id         SERIAL PRIMARY KEY,
    level      VARCHAR(16) NOT NULL DEFAULT 'INFO',
    source     VARCHAR(64) NOT NULL,
    message    TEXT        NOT NULL,
    metadata   JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_events_created ON system_events (created_at DESC);

CREATE TABLE IF NOT EXISTS trade_feedback (
    id         SERIAL PRIMARY KEY,
    trade_id   INTEGER,
    outcome    VARCHAR(16),
    signals    JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_feedback_trade ON trade_feedback (trade_id);

-- ── Learning system tables ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS belief_system (
    strategy_id             VARCHAR(50)     PRIMARY KEY,
    strategy_name           VARCHAR(100)    NOT NULL,
    market                  VARCHAR(20)     NOT NULL,
    description             TEXT,
    total_trades            INTEGER         DEFAULT 0,
    winning_trades          INTEGER         DEFAULT 0,
    losing_trades           INTEGER         DEFAULT 0,
    win_rate                DECIMAL(5,4),
    profit_factor           DECIMAL(10,4),
    expectancy              DECIMAL(10,4),
    sharpe_ratio            DECIMAL(10,4),
    avg_win_r               DECIMAL(10,4),
    avg_loss_r              DECIMAL(10,4),
    max_consecutive_losses  INTEGER         DEFAULT 0,
    confidence              DECIMAL(5,4)    DEFAULT 0.5
                            CHECK (confidence BETWEEN 0 AND 1),
    best_regime             VARCHAR(20),
    best_timeframe          VARCHAR(10),
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     DEFAULT NOW(),
    last_trade_at           TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id   UUID            DEFAULT gen_random_uuid() PRIMARY KEY,
    description     TEXT            NOT NULL,
    market          VARCHAR(20),
    stage           VARCHAR(20)     DEFAULT 'observation'
                    CHECK (stage IN ('observation','candidate','active','rejected')),
    conditions      JSONB           NOT NULL DEFAULT '{}',
    total_trades    INTEGER         DEFAULT 0,
    winning_trades  INTEGER         DEFAULT 0,
    win_rate        DECIMAL(5,4),
    profit_factor   DECIMAL(10,4),
    expectancy      DECIMAL(10,4),
    confidence      DECIMAL(5,4)    CHECK (confidence BETWEEN 0 AND 1),
    stat_test_result JSONB,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    promoted_at     TIMESTAMPTZ,
    rejected_at     TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_stage  ON hypotheses (stage);
CREATE INDEX IF NOT EXISTS idx_hypotheses_market ON hypotheses (market);

-- ── Seed belief_system strategies (idempotent) ───────────────────────────────
INSERT INTO belief_system (strategy_id, strategy_name, market, description)
VALUES
    ('default_sandbox', 'Sandbox Default',    'stocks', 'Auto-generated signals from sandbox engine'),
    ('breakout_moex',   'Пробой уровня',      'stocks', 'Пробой ключевого уровня с объёмом'),
    ('trend_moex',      'Следование тренду',  'stocks', 'Вход по тренду на откате к EMA'),
    ('osc_range_moex',  'Осциллятор диапазон','stocks', 'RSI/MACD дивергенция в боковике'),
    ('default_moex',    'MOEX Default',       'stocks', 'Основная стратегия MOEX'),
    ('momentum_bybit',  'Моментум крипто',    'crypto', 'Вход на сильном импульсе с объёмом'),
    ('trend_bybit',     'Тренд крипто',       'crypto', 'Следование тренду BTC/ETH на H1')
ON CONFLICT (strategy_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS skipped_signals (
    skip_id         UUID            DEFAULT gen_random_uuid() PRIMARY KEY,
    skipped_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    strategy_id     VARCHAR(50)     NOT NULL,
    ticker          VARCHAR(20),
    timeframe       VARCHAR(10),
    direction       VARCHAR(8),
    skip_reason     VARCHAR(50)     NOT NULL,
    details         JSONB,
    is_sandbox      BOOLEAN         DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_skipped_strategy ON skipped_signals (strategy_id);
CREATE INDEX IF NOT EXISTS idx_skipped_reason   ON skipped_signals (skip_reason);

CREATE TABLE IF NOT EXISTS forward_state (
    strategy_id         VARCHAR(50)     NOT NULL,
    ticker              VARCHAR(20)     NOT NULL,
    last_candle_time    TIMESTAMPTZ     NOT NULL,
    updated_at          TIMESTAMPTZ     DEFAULT NOW(),
    PRIMARY KEY (strategy_id, ticker)
);

-- ── Paper engine enhancements (idempotent migrations) ─────────────────────
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS commission    NUMERIC(18,4) NOT NULL DEFAULT 0;
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS slippage      NUMERIC(18,4) NOT NULL DEFAULT 0;
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS close_reason  VARCHAR(32)   NOT NULL DEFAULT 'manual';
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS entry_reason  TEXT;
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS trailing_stop_pct NUMERIC(10,6);
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS signal_id         INTEGER;
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS entry_reason      TEXT;
"""