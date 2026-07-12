"""DDL for platform tables — idempotent migrations."""

PLATFORM_SCHEMA_SQL = """
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
    trade_id   INTEGER REFERENCES trades(id),
    outcome    VARCHAR(16),
    signals    JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""