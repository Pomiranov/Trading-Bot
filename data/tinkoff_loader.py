"""Загрузка исторических свечей через Tinkoff Invest API v2 (REST).

SDK tinkoff-investments не поддерживает Python 3.14, поэтому используется
REST-интерфейс API v2 напрямую (те же методы, JSON вместо gRPC).

Запуск:
    python data/tinkoff_loader.py

Грузит H1/H4/D1 за ~3 года по ликвидным акциям MOEX и сохраняет в таблицу
candles (создаёт её при отсутствии). Повторный запуск дозаписывает только
новые свечи (ON CONFLICT DO NOTHING).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from config import config

logger = logging.getLogger(__name__)

# ── Хосты REST API ───────────────────────────────────────────────────
PROD_HOST    = "https://invest-public-api.tinkoff.ru/rest"
SANDBOX_HOST = "https://sandbox-invest-public-api.tinkoff.ru/rest"
API_PREFIX   = "tinkoff.public.invest.api.contract.v1"

# ── Параметры загрузки ───────────────────────────────────────────────
HISTORY_DAYS = 1095            # ~3 года — максимум разумной глубины
REQUEST_PAUSE = 0.15           # пауза между запросами (защита от rate limit)

# таймфрейм → (интервал API, максимальное окно одного запроса)
TIMEFRAMES = {
    "1h": ("CANDLE_INTERVAL_HOUR",   timedelta(days=7)),    # лимит API: 1 неделя
    "4h": ("CANDLE_INTERVAL_4_HOUR", timedelta(days=25)),   # лимит API: 1 месяц
    "1d": ("CANDLE_INTERVAL_DAY",    timedelta(days=360)),  # лимит API: 1 год
}


class TinkoffHistoryLoader:
    """REST-загрузчик исторических свечей Tinkoff Invest API v2."""

    def __init__(self, token: str = None, sandbox: bool = None):
        self._token = token if token is not None else config.tinkoff.token
        use_sandbox = sandbox if sandbox is not None else config.tinkoff.sandbox
        self._host = SANDBOX_HOST if use_sandbox else PROD_HOST
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        })

    # ── Базовый вызов с обработкой rate limit ────────────────────────

    def _post(self, service: str, method: str, payload: dict) -> dict:
        url = f"{self._host}/{API_PREFIX}.{service}/{method}"
        for attempt in range(5):
            resp = self._session.post(url, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("x-ratelimit-reset", 5)) + 1
                logger.warning("Rate limit: пауза %d с", wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"{service}/{method} → HTTP {resp.status_code}: {resp.text[:300]}"
                )
            return resp.json()
        raise RuntimeError(f"{service}/{method}: rate limit не отпустил после 5 попыток")

    # ── Инструменты ──────────────────────────────────────────────────

    def resolve_figi(self, ticker: str) -> str | None:
        """Найти FIGI акции MOEX (класс TQBR) по тикеру."""
        data = self._post("InstrumentsService", "FindInstrument", {
            "query": ticker,
            "instrumentKind": "INSTRUMENT_TYPE_SHARE",
        })
        for item in data.get("instruments", []):
            if item.get("ticker") == ticker and item.get("classCode") == "TQBR":
                return item.get("figi")
        return None

    # ── Свечи ────────────────────────────────────────────────────────

    @staticmethod
    def _q(value: dict) -> float:
        """Quotation {units, nano} → float."""
        return int(value.get("units", 0)) + int(value.get("nano", 0)) / 1e9

    def get_candles(self, figi: str, timeframe: str, days: int = HISTORY_DAYS) -> list[dict]:
        """Скачать свечи, чанкуя период под лимиты API. Возвращает список dict."""
        interval, window = TIMEFRAMES[timeframe]
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        rows = []
        cursor = start
        while cursor < end:
            chunk_end = min(cursor + window, end)
            data = self._post("MarketDataService", "GetCandles", {
                "figi": figi,
                "from": cursor.isoformat().replace("+00:00", "Z"),
                "to":   chunk_end.isoformat().replace("+00:00", "Z"),
                "interval": interval,
            })
            for c in data.get("candles", []):
                if not c.get("isComplete", False):
                    continue
                rows.append({
                    "time":   datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                    "open":   self._q(c["open"]),
                    "high":   self._q(c["high"]),
                    "low":    self._q(c["low"]),
                    "close":  self._q(c["close"]),
                    "volume": int(c.get("volume", 0)),
                })
            cursor = chunk_end
            time.sleep(REQUEST_PAUSE)
        return rows


# ── Сохранение в PostgreSQL ──────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS candles (
    time      TIMESTAMPTZ   NOT NULL,
    ticker    VARCHAR(20)   NOT NULL,
    timeframe VARCHAR(10)   NOT NULL,
    open      NUMERIC(18,6) NOT NULL,
    high      NUMERIC(18,6) NOT NULL,
    low       NUMERIC(18,6) NOT NULL,
    close     NUMERIC(18,6) NOT NULL,
    volume    BIGINT        NOT NULL DEFAULT 0,
    PRIMARY KEY (ticker, timeframe, time)
);
CREATE INDEX IF NOT EXISTS idx_candles_ticker_tf_time
    ON candles (ticker, timeframe, time DESC);
"""


async def save_candles(conn, ticker: str, timeframe: str, rows: list[dict]) -> int:
    """Вставить свечи; дубликаты молча пропускаются."""
    if not rows:
        return 0
    inserted = await conn.executemany("""
        INSERT INTO candles (time, ticker, timeframe, open, high, low, close, volume)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (ticker, timeframe, time) DO NOTHING
    """, [
        (r["time"], ticker, timeframe,
         r["open"], r["high"], r["low"], r["close"], r["volume"])
        for r in rows
    ])
    return len(rows)


async def main() -> None:
    import os
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")

    tickers = [
        # уже использовались в бэктестах
        "SBER", "GAZP", "LKOH", "NVTK",
        # добавленные ликвидные акции MOEX
        "ROSN", "TATN", "MGNT", "MOEX", "PLZL", "CHMF", "ALRS", "SNGS",
    ]

    loader = TinkoffHistoryLoader()
    conn = await asyncpg.connect("postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot")))

    try:
        await conn.execute(CREATE_TABLE_SQL)

        for ticker in tickers:
            figi = loader.resolve_figi(ticker)
            if not figi:
                print(f"[{ticker}] FIGI не найден — пропуск")
                continue
            for timeframe in TIMEFRAMES:
                t0 = time.time()
                rows = loader.get_candles(figi, timeframe)
                n = await save_candles(conn, ticker, timeframe, rows)
                print(f"[{ticker}] {timeframe}: получено {n} свечей "
                      f"за {time.time() - t0:.0f} с")

        # ── Итоговая таблица ──────────────────────────────────────────
        print(f"\n{'Тикер':<8} {'ТФ':<5} {'Свечей':>8}  {'С':<12} {'По':<12}")
        for r in await conn.fetch("""
            SELECT ticker, timeframe, COUNT(*) AS n,
                   MIN(time) AS t0, MAX(time) AS t1
            FROM candles GROUP BY ticker, timeframe
            ORDER BY ticker, timeframe
        """):
            print(f"{r['ticker']:<8} {r['timeframe']:<5} {r['n']:>8}  "
                  f"{r['t0'].date()}   {r['t1'].date()}")
        total = await conn.fetchval("SELECT COUNT(*) FROM candles")
        print(f"\nВсего свечей в БД: {total}")
    finally:
        await conn.close()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
