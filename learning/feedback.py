"""Запись результатов сделок в БД PostgreSQL для последующего анализа и обучения."""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from config import config

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(20)   NOT NULL,
    direction       VARCHAR(4)    NOT NULL,   -- BUY / SELL
    entry_price     NUMERIC(18,4) NOT NULL,
    exit_price      NUMERIC(18,4),
    shares          INTEGER       NOT NULL,
    stop_price      NUMERIC(18,4),
    pnl             NUMERIC(18,4),
    pnl_pct         NUMERIC(10,6),
    entry_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    exit_at         TIMESTAMPTZ,
    signal_rules    TEXT[],        -- список правил, сформировавших сигнал
    buy_score       NUMERIC(8,4),
    sell_score      NUMERIC(8,4),
    rsi             NUMERIC(8,4),
    macd_hist       NUMERIC(18,6),
    adx             NUMERIC(8,4),
    atr             NUMERIC(18,6),
    status          VARCHAR(20)   DEFAULT 'OPEN',  -- OPEN / CLOSED / STOPPED
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker  ON trades (ticker);
CREATE INDEX IF NOT EXISTS idx_trades_entry_at ON trades (entry_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_status   ON trades (status);
"""


@dataclass
class TradeRecord:
    ticker: str
    direction: str
    entry_price: float
    shares: int
    stop_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    entry_at: Optional[datetime] = None
    exit_at: Optional[datetime] = None
    signal_rules: Optional[list] = None
    buy_score: Optional[float] = None
    sell_score: Optional[float] = None
    rsi: Optional[float] = None
    macd_hist: Optional[float] = None
    adx: Optional[float] = None
    atr: Optional[float] = None
    status: str = "OPEN"
    notes: str = ""
    db_id: Optional[int] = None


class FeedbackStore:
    """Хранилище результатов сделок в PostgreSQL."""

    def __init__(self):
        self._conn = None
        self._ensure_schema()

    def _connect(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(config.db.dsn)
            self._conn.autocommit = False
        return self._conn

    def _ensure_schema(self) -> None:
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
            conn.commit()
            logger.info("Схема БД проверена/создана")
        except Exception as exc:
            logger.error("Ошибка инициализации схемы БД: %s", exc)

    # ─── Запись сделок ────────────────────────────────────────────────

    def record_open(self, trade: TradeRecord) -> Optional[int]:
        """Записать открытие сделки, вернуть id строки в БД."""
        sql = """
            INSERT INTO trades (
                ticker, direction, entry_price, shares, stop_price,
                entry_at, signal_rules, buy_score, sell_score,
                rsi, macd_hist, adx, atr, status, notes
            ) VALUES (
                %(ticker)s, %(direction)s, %(entry_price)s, %(shares)s, %(stop_price)s,
                %(entry_at)s, %(signal_rules)s, %(buy_score)s, %(sell_score)s,
                %(rsi)s, %(macd_hist)s, %(adx)s, %(atr)s, %(status)s, %(notes)s
            ) RETURNING id
        """
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "ticker": trade.ticker,
                    "direction": trade.direction,
                    "entry_price": trade.entry_price,
                    "shares": trade.shares,
                    "stop_price": trade.stop_price,
                    "entry_at": trade.entry_at or datetime.utcnow(),
                    "signal_rules": trade.signal_rules,
                    "buy_score": trade.buy_score,
                    "sell_score": trade.sell_score,
                    "rsi": trade.rsi,
                    "macd_hist": trade.macd_hist,
                    "adx": trade.adx,
                    "atr": trade.atr,
                    "status": "OPEN",
                    "notes": trade.notes,
                })
                trade_id = cur.fetchone()[0]
            conn.commit()
            trade.db_id = trade_id
            logger.info("Сделка записана в БД: id=%d %s %s", trade_id, trade.ticker, trade.direction)
            return trade_id
        except Exception as exc:
            logger.error("Ошибка записи открытия сделки: %s", exc)
            self._conn and self._conn.rollback()
            return None

    def record_close(
        self,
        trade_id: int,
        exit_price: float,
        status: str = "CLOSED",
    ) -> None:
        """Обновить запись с результатом закрытой сделки."""
        sql = """
            UPDATE trades
            SET exit_price = %(exit_price)s,
                exit_at    = %(exit_at)s,
                pnl        = (%(exit_price)s - entry_price) * shares,
                pnl_pct    = (%(exit_price)s - entry_price) / entry_price,
                status     = %(status)s
            WHERE id = %(id)s
        """
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "exit_price": exit_price,
                    "exit_at": datetime.utcnow(),
                    "status": status,
                    "id": trade_id,
                })
            conn.commit()
            logger.info("Сделка %d закрыта: выход=%.2f, статус=%s", trade_id, exit_price, status)
        except Exception as exc:
            logger.error("Ошибка обновления закрытой сделки: %s", exc)
            self._conn and self._conn.rollback()

    # ─── Аналитика ────────────────────────────────────────────────────

    def get_recent_trades(self, limit: int = 50) -> list[dict]:
        """Получить последние сделки."""
        sql = """
            SELECT id, ticker, direction, entry_price, exit_price,
                   shares, pnl, pnl_pct, entry_at, exit_at, status
            FROM trades
            ORDER BY entry_at DESC
            LIMIT %(limit)s
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, {"limit": limit})
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Ошибка получения сделок: %s", exc)
            return []

    def get_stats(self) -> dict:
        """Агрегированная статистика по всем закрытым сделкам."""
        sql = """
            SELECT
                COUNT(*)                         AS total_trades,
                COUNT(*) FILTER (WHERE pnl > 0)  AS winning_trades,
                COUNT(*) FILTER (WHERE pnl <= 0) AS losing_trades,
                ROUND(SUM(pnl)::numeric, 2)      AS total_pnl,
                ROUND(AVG(pnl)::numeric, 2)      AS avg_pnl,
                ROUND(MAX(pnl)::numeric, 2)      AS max_win,
                ROUND(MIN(pnl)::numeric, 2)      AS max_loss,
                ROUND(AVG(pnl_pct) * 100, 3)     AS avg_pnl_pct
            FROM trades
            WHERE status IN ('CLOSED', 'STOPPED')
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return dict(row) if row else {}
        except Exception as exc:
            logger.error("Ошибка получения статистики: %s", exc)
            return {}

    def get_rule_performance(self) -> list[dict]:
        """Оценить эффективность каждого торгового правила."""
        sql = """
            SELECT
                rule,
                COUNT(*)                         AS total,
                COUNT(*) FILTER (WHERE pnl > 0)  AS wins,
                ROUND(SUM(pnl)::numeric, 2)      AS total_pnl
            FROM trades, UNNEST(signal_rules) AS rule
            WHERE status IN ('CLOSED', 'STOPPED')
            GROUP BY rule
            ORDER BY total_pnl DESC
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Ошибка получения статистики правил: %s", exc)
            return []


feedback_store = FeedbackStore()
