"""Чтение свечей для измерительных прогонов. НАЧАЛО ОКНА ОБЯЗАТЕЛЬНО.

`end` — МОСКОВСКАЯ ТОРГОВАЯ СЕССИЯ ВКЛЮЧИТЕЛЬНО, а НЕ внутренняя метка бара.
Это первая строка модуля, потому что путаница здесь стоит ровно одного дня и целой
сессии поиска несуществующего дефекта: у бара сессии D метка (D−1) 21:00 UTC, а её
наивная UTC-дата — вообще (D−1). Три разных даты на один бар (долг №26), и все три
уже встречались в документах проекта под словом «сессия».


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
from datetime import date, datetime, timedelta, timezone

import pandas as pd

# Граница окна — МОСКОВСКАЯ полночь даты начала, а не UTC-полночь. Тот же канон,
# что у loader.save_candles_to_db и у уникального индекса
# candles_d1_one_per_msk_session: каноничный бар сессии D стоит на (D−1) 21:00 UTC,
# и UTC-полночь отрезала бы первый бар окна. Ровно это создало 12 дублей 25.06
# (долг №16) — здесь ошибка была бы тише: не дубль, а молча потерянный бар.
from market_time import MSK, d1_bar_time, last_closed_index, session_date  # noqa: E402


def dsn() -> str:
    """DSN измерительного прогона. Одна копия вместо пяти."""
    from dotenv import load_dotenv

    load_dotenv()
    return "postgresql://{}:{}@{}:{}/{}".format(
        os.getenv("DB_USER", "trader"), os.getenv("DB_PASSWORD", ""),
        os.getenv("DB_HOST", "localhost"), os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "trading_bot"))


def window_bounds(
    start: date,
    end: date | None = None,
) -> tuple[datetime, datetime | None]:
    """Границы окна из СЕССИЙ в метки: [since, until). Отдельно — чтобы проверялось.

    Расчёт вынесен из load_candles_db не ради опрятности: границу нельзя проверить
    тестом, пока она живёт внутри функции, которой нужна БД. А проверять надо именно
    её — ошибка в один день здесь неотличима от отсутствия эффекта (правило 6 §8).

    ПРАВЫЙ КРАЙ ПОЛУОТКРЫТ, `time < until`, где until = полночь СЛЕДУЮЩЕЙ сессии.
    Сессия D занимает [d1_bar_time(D), d1_bar_time(D+1)). С `time <= d1_bar_time(end)`
    из последней сессии остался бы ровно ОДИН бар — её первый. На D1 это выглядело бы
    правильно (у сессии один бар и есть), а на H4/H1 молча срезало бы день до огарка:
    ошибка, которая на одном таймфрейме невидима, а на другом искажает всё.

    ЛЕВЫЙ КРАЙ ЗАКРЫТ, `time >= since` — тот же канон долга №16: каноничный бар
    сессии D стоит на (D−1) 21:00 UTC, и UTC-полночь отрезала бы первый бар окна.
    """
    if not isinstance(start, date):
        raise TypeError(
            f"start обязан быть datetime.date, получено {type(start).__name__}: "
            f"окно выборки — часть определения измерения, а не необязательный фильтр"
        )
    if end is not None and not isinstance(end, date):
        raise TypeError(
            f"end обязан быть datetime.date, получено {type(end).__name__}: "
            f"конец окна — московская СЕССИЯ, а не строка и не метка бара"
        )
    since = d1_bar_time(start)
    if end is None:
        return since, None
    until = d1_bar_time(end + timedelta(days=1))
    if until <= since:
        raise ValueError(
            f"пустое окно: конец {end.isoformat()} раньше начала {start.isoformat()}"
        )
    return since, until


async def load_candles_db(
    timeframe: str,
    tickers,
    start: date,
    end: date | None = None,
) -> dict[str, pd.DataFrame]:
    """Свечи по набору. Начало окна ОБЯЗАТЕЛЬНО, конец — по желанию.

    start — часть определения измерения наравне с набором. Передавать
    bot/universe.py:SAMPLE_START_2026_07, а не вычислять из данных.

    end — последняя МОСКОВСКАЯ СЕССИЯ ВКЛЮЧИТЕЛЬНО (не метка бара, см. шапку
    модуля). None = без обрезки, то есть по самые свежие данные в таблице.
    Граница выражена как `time < d1_bar_time(end + 1 день)`, а не `<= end`:
    сессия D занимает [d1_bar_time(D), d1_bar_time(D+1)), и с `<= d1_bar_time(end)`
    из последней сессии остался бы ровно один бар — её первый. На D1 это выглядело
    бы правильно (у сессии один бар), а на H4/H1 молча отрезало бы день до огарка.
    Симметрично `time >= d1_bar_time(start)` на левом краю.

    ПОЧЕМУ `end` НЕ ОБЯЗАТЕЛЕН, ХОТЯ `start` ОБЯЗАТЕЛЕН — асимметрия намеренная,
    см. bot/universe.py:SAMPLE_END_2026_07. Коротко: забытый start расширяет выборку
    в ПРОШЛОЕ и переписывает историю (лечится только падением), забытый end
    расширяет её в БУДУЩЕЕ и добавляет новые свидетельства (запрещать нельзя, гейт
    обязан показывать свежее). Механизм против забывания здесь — обязательная печать
    фактического конца через window_note(), а не TypeError.

    Индекс возвращаемых кадров НАИВНЫЙ (tz снят) — так его ждут BacktestEngine и
    IndicatorEngine, и так было во всех пяти копиях. Трактуется как UTC; смещение
    на московскую дату сессии — предмет отдельного долга №26 о чтении отчётов.
    """
    import asyncpg

    since, until = window_bounds(start, end)

    sql = """
                SELECT time, open, high, low, close, volume
                FROM candles
                WHERE ticker = $1 AND timeframe = $2 AND time >= $3
    """
    if until is not None:
        sql += " AND time < $4"
    sql += " ORDER BY time"

    conn = await asyncpg.connect(dsn())
    data: dict[str, pd.DataFrame] = {}
    try:
        for ticker in tickers:
            args = [ticker, timeframe, since]
            if until is not None:
                args.append(until)
            rows = await conn.fetch(sql, *args)
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


def _as_utc(ts) -> datetime:
    """Наивная метка кадра → tz-aware UTC. Кадры отдаются наивными (см. выше)."""
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _stamp(ts) -> str:
    """Бар в ОБОИХ видах сразу: внутренняя метка и московская сессия."""
    aware = _as_utc(ts)
    return f"{aware.strftime('%Y-%m-%d %H:%M')}+00 (сессия {session_date(aware)})"


def window_note(
    data: dict[str, pd.DataFrame],
    start: date,
    end: date | None = None,
) -> str:
    """Шапка прогона: ТРИ даты, а не две. Одна копия расчёта на все скрипты.

    Печатается наравне с набором и файлом правил, потому что отчёт без обоих концов
    окна через полгода нечитаем. Три даты, и каждая уже была спутана с другими:

      1. ДАТА ПРОГОНА — календарный день, когда прогон сделан. Именно ею помечено
         «данные по сессию 28.07» в PROJECT_STATE §2б, хотя последний бар того
         прогона относится к сессии 27.07.
      2. ПОСЛЕДНЯЯ СЕССИЯ В ДАННЫХ — московская торговая дата последнего бара.
         Ею помечен +77 851.57 в долге №25, и там пометка верна.
      3. ВНУТРЕННЯЯ МЕТКА БАРА — (сессия − 1) 21:00 UTC. Её наивная UTC-дата даёт
         третье значение и попадает в CSV отчётов (долг №26).

    Плюс отдельно печатается последняя ЗАКРЫТАЯ сессия: движок отбрасывает
    формирующуюся (engine.py:_drop_forming_bar), поэтому «последний загруженный бар»
    и «бар, на котором посчитаны числа» — разные вещи, и в день прогона они всегда
    разные. Считается тем же last_closed_index, что и в движке, а не своей копией.
    """
    from universe import sample_version   # локально: universe импортирует только stdlib

    lines = [
        f"Прогон: {datetime.now(MSK).date()} (МСК)",
        f"Окно запрошено: с сессии {start.isoformat()} "
        f"(граница {d1_bar_time(start).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')}+00) "
        + (f"по сессию {end.isoformat()} включительно" if end is not None
           else "по СЕГОДНЯ — конец не приколочен, новые сделки могут добавиться"),
        f"Отпечаток начала окна: {sample_version(start)}",
    ]
    if not data:
        lines.append("Фактически загружено: НИ ОДНОГО БАРА")
        return "\n".join(lines)

    firsts, lasts, closed = [], [], []
    for df in data.values():
        if df.empty:
            continue
        idx = list(df.index)
        firsts.append(idx[0])
        lasts.append(idx[-1])
        pos = last_closed_index([_as_utc(t) for t in idx])
        if pos >= 0:
            closed.append(idx[pos])
    if not firsts:
        lines.append("Фактически загружено: НИ ОДНОГО БАРА")
        return "\n".join(lines)

    lines.append(f"Фактически бары: с {_stamp(min(firsts))} по {_stamp(max(lasts))}")
    if closed:
        lines.append(f"Последняя ЗАКРЫТАЯ сессия (её и считает движок): "
                     f"{_stamp(max(closed))}")
    return "\n".join(lines)
