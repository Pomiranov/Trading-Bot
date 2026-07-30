"""Чтение свечей для измерительных прогонов. ОКНО ВЫБОРКИ ОБЯЗАТЕЛЬНО.

Зачем модуль. До 2026-07-30 этот запрос жил ПЯТЬЮ копиями (по одной в каждом
измерительном скрипте bot/backtest/), и все пять брали из БД всё, что там лежит:

    SELECT time, open, high, low, close, volume FROM candles
    WHERE ticker = $1 AND timeframe = $2 ORDER BY time

То есть дата НАЧАЛА выборки не фиксировалась нигде (долг №37). Опорная тройка
18 / 72.2% / 1.64 / +127 748 воспроизводилась ровно потому, что у 12 действующих
бумаг первый бар оказался 2023-07-12, — а не потому, что это где-то записано.
Докачай кто-нибудь историю глубже, и число изменилось бы МОЛЧА, а причину искали
бы в коде. Пять копий — та же болезнь, что девять копий списка тикеров и восемь
копий ставки комиссии.

ПОЧЕМУ `start` ОБЯЗАТЕЛЬНЫЙ, А НЕ СО ЗНАЧЕНИЕМ ПО УМОЛЧАНИЮ. Дефолт превратил бы
механизм обратно в дисциплину: скрипт, забывший окно, молча получил бы более
широкую выборку и напечатал бы правдоподобный, но невоспроизводимый результат.
С обязательным аргументом он падает `TypeError` на вызове — то есть отказ громкий
и мгновенный. Это тот же выбор, что у форварда между «предупредить» и «упасть»
при реплее в боевую БД.

ПОЧЕМУ НЕ АВТОРАСЧЁТ `max(first_bar)`. Он выглядит удобным и ровно поэтому опасен:
значение молча меняется при каждой догрузке. Это даёт не воспроизводимость, а её
видимость. Дата приколочена литералом в bot/universe.py:SAMPLE_START_2026_07.

Форвард этим модулем НЕ пользуется и пользоваться не должен: у него нет выборки,
он идёт вперёд по свежим барам (см. довод 1 в universe.py про окно).
"""

import os
from datetime import date, datetime, timezone

import pandas as pd

# Граница окна — МОСКОВСКАЯ полночь даты начала, а не UTC-полночь. Тот же канон,
# что у loader.save_candles_to_db и у уникального индекса
# candles_d1_one_per_msk_session: каноничный бар сессии D стоит на (D−1) 21:00 UTC,
# и UTC-полночь отрезала бы первый бар окна. Ровно это создало 12 дублей 25.06
# (долг №16) — здесь ошибка была бы тише: не дубль, а молча потерянный бар.
from market_time import d1_bar_time  # noqa: E402


def dsn() -> str:
    """DSN измерительного прогона. Одна копия вместо пяти."""
    from dotenv import load_dotenv

    load_dotenv()
    return "postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot"))


async def load_candles_db(
    timeframe: str,
    tickers,
    start: date,
) -> dict[str, pd.DataFrame]:
    """Свечи по набору с ОБЯЗАТЕЛЬНЫМ окном. tickers → DataFrame OHLCV.

    start — часть определения измерения наравне с набором. Передавать
    bot/universe.py:SAMPLE_START_2026_07, а не вычислять из данных.

    Индекс возвращаемых кадров НАИВНЫЙ (tz снят) — так его ждут BacktestEngine и
    IndicatorEngine, и так было во всех пяти копиях. Трактуется как UTC; смещение
    на московскую дату сессии — предмет отдельного долга №26 о чтении отчётов.
    """
    import asyncpg

    if not isinstance(start, date):
        raise TypeError(
            f"start обязан быть datetime.date, получено {type(start).__name__}: "
            f"окно выборки — часть определения измерения, а не необязательный фильтр"
        )
    since = d1_bar_time(start)

    conn = await asyncpg.connect(dsn())
    data: dict[str, pd.DataFrame] = {}
    try:
        for ticker in tickers:
            rows = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM candles
                WHERE ticker = $1 AND timeframe = $2 AND time >= $3
                ORDER BY time
            """, ticker, timeframe, since)
            if not rows:
                continue
            data[ticker] = pd.DataFrame(
                {
                    "open":   [float(r["open"]) for r in rows],
                    "high":   [float(r["high"]) for r in rows],
                    "low":    [float(r["low"]) for r in rows],
                    "close":  [float(r["close"]) for r in rows],
                    "volume": [int(r["volume"]) for r in rows],
                },
                index=pd.DatetimeIndex(
                    [r["time"].replace(tzinfo=None) for r in rows], name="datetime"
                ),
            )
    finally:
        await conn.close()
    return data
