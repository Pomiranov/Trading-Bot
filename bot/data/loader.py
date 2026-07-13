"""Загрузка OHLCV данных с MOEX ISS REST API."""

import sys
from pathlib import Path

# Позволяет запускать файл напрямую: python3 data/loader.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from config import config

logger = logging.getLogger(__name__)

# Маппинг интервалов MOEX ISS
INTERVAL_MAP = {
    "1m": 1,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "1d": 24,
    "1w": 7,
    "1M": 31,
}


class MoexLoader:
    """Загрузчик исторических и потоковых данных с MOEX ISS."""

    BASE_URL = config.moex_base_url
    SESSION = requests.Session()
    SESSION.headers.update({"Accept": "application/json"})

    def get_candles(
        self,
        ticker: str,
        interval: str = "1h",
        start: Optional[date] = None,
        end: Optional[date] = None,
        board: str = "TQBR",
        market: str = "shares",
        engine: str = "stock",
    ) -> pd.DataFrame:
        """
        Загрузить OHLCV свечи для тикера с MOEX ISS.

        Возвращает DataFrame с колонками: open, high, low, close, volume, datetime.
        """
        if start is None:
            start = date.today() - timedelta(days=365)
        if end is None:
            end = date.today()

        iss_interval = INTERVAL_MAP.get(interval)
        if iss_interval is None:
            raise ValueError(f"Неизвестный интервал: {interval}. Доступные: {list(INTERVAL_MAP)}")

        all_frames: list[pd.DataFrame] = []
        start_index = 0

        while True:
            url = (
                f"{self.BASE_URL}/engines/{engine}/markets/{market}"
                f"/boards/{board}/securities/{ticker}/candles.json"
            )
            params = {
                "from": start.isoformat(),
                "till": end.isoformat(),
                "interval": iss_interval,
                "start": start_index,
            }

            try:
                resp = self.SESSION.get(url, params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Ошибка запроса к MOEX ISS (%s): %s", ticker, exc)
                break

            data = resp.json()
            candles = data.get("candles", {})
            columns = [c.lower() for c in candles.get("columns", [])]
            rows = candles.get("data", [])

            if not rows:
                break

            df = pd.DataFrame(rows, columns=columns)
            all_frames.append(df)

            # ISS возвращает максимум 500 свечей за раз
            if len(rows) < 500:
                break
            start_index += len(rows)

        if not all_frames:
            logger.warning("Нет данных для %s за период %s — %s", ticker, start, end)
            return pd.DataFrame()

        result = pd.concat(all_frames, ignore_index=True)
        result = self._normalize(result)
        logger.info("Загружено %d свечей для %s", len(result), ticker)
        return result

    def get_last_quote(self, ticker: str, board: str = "TQBR") -> dict:
        """Получить последнюю котировку тикера."""
        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities/{ticker}.json"
        )
        try:
            resp = self.SESSION.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Ошибка получения котировки %s: %s", ticker, exc)
            return {}

        data = resp.json()
        marketdata = data.get("marketdata", {})
        columns = [c for c in marketdata.get("columns", [])]
        rows = marketdata.get("data", [])

        if not rows:
            return {}

        row = dict(zip(columns, rows[0]))
        return {
            "ticker": ticker,
            "last": row.get("LAST"),
            "open": row.get("OPEN"),
            "high": row.get("HIGH"),
            "low": row.get("LOW"),
            "close": row.get("CLOSEPRICE"),
            "volume": row.get("VOLTODAY"),
            "time": row.get("SYSTIME"),
        }

    def search_securities(self, query: str) -> pd.DataFrame:
        """Поиск ценных бумаг по названию или тикеру."""
        url = f"{self.BASE_URL}/securities.json"
        params = {"q": query, "limit": 20}
        try:
            resp = self.SESSION.get(url, params=params, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Ошибка поиска бумаги: %s", exc)
            return pd.DataFrame()

        data = resp.json()
        securities = data.get("securities", {})
        columns = [c.lower() for c in securities.get("columns", [])]
        rows = securities.get("data", [])
        return pd.DataFrame(rows, columns=columns)

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        rename = {
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "begin": "datetime",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime").sort_index()

        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna(subset=["close"])


loader = MoexLoader()


def save_candles_to_db(
    tickers: list[str],
    interval: str = "1d",
    days: int = 365,
    verbose: bool = True,
) -> int:
    """Догрузить свечи с MOEX ISS в таблицу candles (delete+insert по периоду).

    За период [today-days, today] существующие строки тикера/таймфрейма
    заменяются свежими — безопасно вызывать ежедневно с перекрытием.
    Возвращает количество сохранённых строк.
    """
    import psycopg2
    from psycopg2.extras import execute_values
    from config import config as _config

    def _say(msg: str) -> None:
        if verbose:
            print(msg)
        else:
            logger.info(msg)

    end_dt   = date.today()
    start_dt = end_dt - timedelta(days=days)
    conn = psycopg2.connect(_config.db.dsn)

    total_saved = 0
    try:
        for ticker in tickers:
            _say(f"[{ticker}] Запрос к MOEX ISS…")
            df = loader.get_candles(ticker, interval=interval, start=start_dt, end=end_dt)

            if df.empty:
                _say(f"[{ticker}] Нет данных — пропускаем")
                continue

            df = df.reset_index()
            df = df.rename(columns={"datetime": "time"})
            records = [
                (row.time.to_pydatetime(), ticker, interval,
                 float(row.open), float(row.high), float(row.low),
                 float(row.close), int(row.volume))
                for row in df.itertuples(index=False)
            ]

            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM candles
                    WHERE ticker    = %s
                      AND timeframe = %s
                      AND time BETWEEN %s AND %s
                """, (ticker, interval, start_dt, end_dt))
                if cur.rowcount:
                    _say(f"[{ticker}] Удалено {cur.rowcount} старых строк")
                execute_values(cur, """
                    INSERT INTO candles (time, ticker, timeframe, open, high, low, close, volume)
                    VALUES %s
                """, records, page_size=500)
            conn.commit()

            total_saved += len(records)
            _say(f"[{ticker}] Сохранено {len(records)} свечей "
                 f"({df['time'].min().date()} → {df['time'].max().date()})")
    finally:
        conn.close()

    return total_saved


if __name__ == "__main__":
    import argparse
    from sqlalchemy import create_engine, text

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Загрузить OHLCV с MOEX и сохранить в PostgreSQL")
    parser.add_argument("tickers", nargs="*", default=["SBER", "GAZP", "LKOH", "YNDX", "NVTK"])
    parser.add_argument("--interval", default="1d", choices=list(INTERVAL_MAP))
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    end_dt   = date.today()
    start_dt = end_dt - timedelta(days=args.days)

    print(f"\nПараметры загрузки:")
    print(f"  Тикеры   : {', '.join(args.tickers)}")
    print(f"  Интервал : {args.interval}")
    print(f"  Период   : {start_dt} → {end_dt}")
    print(f"  База     : {config.db.dsn.split('@')[-1]}\n")

    engine = create_engine(config.db.dsn, pool_pre_ping=True)

    total_saved = 0
    for ticker in args.tickers:
        print(f"[{ticker}] Запрос к MOEX ISS…")
        df = loader.get_candles(ticker, interval=args.interval, start=start_dt, end=end_dt)

        if df.empty:
            print(f"[{ticker}] Нет данных — пропускаем\n")
            continue

        # Привести DataFrame к схеме таблицы candles
        df = df.reset_index()                          # datetime-индекс → колонка
        df = df.rename(columns={"datetime": "time"})
        df["ticker"]    = ticker
        df["timeframe"] = args.interval
        df["volume"]    = df["volume"].astype("int64")
        df = df[["time", "ticker", "timeframe", "open", "high", "low", "close", "volume"]]

        # Удалить существующие строки за этот период, затем вставить свежие
        with engine.begin() as conn:
            deleted = conn.execute(text("""
                DELETE FROM candles
                WHERE ticker    = :ticker
                  AND timeframe = :tf
                  AND time BETWEEN :start AND :end
            """), {"ticker": ticker, "tf": args.interval,
                   "start": start_dt, "end": end_dt}).rowcount

            if deleted:
                print(f"[{ticker}] Удалено {deleted} старых строк")

        df.to_sql("candles", engine, if_exists="append", index=False, method="multi", chunksize=500)
        total_saved += len(df)
        print(f"[{ticker}] Сохранено {len(df)} свечей  "
              f"({df['time'].min().date()} → {df['time'].max().date()})\n")

    print(f"Готово. Итого сохранено: {total_saved} строк в таблицу candles.")
