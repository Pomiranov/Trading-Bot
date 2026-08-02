"""QuantFlow — сторож форвард-контура osc_range_moex_d1_fwd.

Запуск:
    python bot\\forward_healthcheck.py     # ежедневно в 09:00 (Task Scheduler)

Читает forward_state по набору FORWARD_TICKERS (20 бумаг с 2026-07-30, растёт) и
говорит в Telegram, жив контур или завис. Сообщение уходит каждый день, включая
статус «ок». Числа набора здесь НЕ приколочены: сторож ходит по константе, порогов
на размер набора у него нет.

Принципиально ничего не лечит: не поднимает docker, не перезапускает задачи,
не пишет в БД. Только SELECT и уведомление.

Почему вердикт по календарному возрасту, а не «forward_state отстаёт от
candles»: свечи пополняет сам run_forward_d1.py (его вызов
save_candles_to_db), поэтому при полной смерти прогона candles и
forward_state замерзают вместе и разница между ними остаётся нулевой.
max(candles.time) идёт в сообщение как диагностика, различающая два режима
отказа: «прогон стартует, но не обрабатывает тикеры» и «прогон не стартует».

Не импортирует run_forward_d1 / learning / ui.telegram_bot: сторож не должен
зависеть от того, что он охраняет (ui.telegram_bot к тому же тянет легаси
feedback_store, который ходит в БД на импорте — см. run_forward_d1.py:102).
Отправка в Telegram — в bot/notify.py, с тем же узким импорт-бюджетом.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from pathlib import Path
from typing import NamedTuple

import psycopg2
from dotenv import load_dotenv

# Скрипт живёт в bot/, конфиг тоже. Путь и .env — от расположения файла,
# а не от cwd: под Task Scheduler cwd легко оказывается не тем, и тогда
# .env не подхватится, DB_PASSWORD будет пустым, а причина сбоя — ложной.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))
load_dotenv(ROOT / ".env")

from config import config  # noqa: E402  — только после sys.path/.env
from universe import FORWARD_TICKERS, FORWARD_TICKERS_VERSION  # noqa: E402
# market_time импортируется, а не дублируется: модуль сознательно без импортов
# (только datetime), поэтому импорт-бюджет сторожа он не задевает — в отличие от
# run_forward_d1, который потянул бы pandas и весь learning-стек. Конвенция
# «закрытый бар» обязана быть у сторожа и у прогона ОДНА.
from market_time import MSK, session_date  # noqa: E402
# Модулем, а не только именами: приписка о прошлых недоставках берётся через
# notify.pending_notice(), и состояние накопителя обязано читаться В МОМЕНТ
# вызова, а не защёлкиваться на импорте.
import notify  # noqa: E402
from notify import credentials_ready, escape, first_line, send  # noqa: E402
# Слоты, льготный интервал и путь журнала — ОДНО место на проект (долг №46).
# Своей копии «00:15» у сторожа нет: две копии одного факта разъехались бы при
# переносе слота, и сторож начал бы врать молча — класс «список вместо
# предиката». Модуль сам stdlib-only, импорт-бюджет сторожа не задевает.
from run_schedule import (GRACE_SEC, SLOT_TOLERANCE_SEC,  # noqa: E402
                         journal_path, last_slot)
from schedule_check import describe_tasks  # noqa: E402

# Дублируется с run_forward_d1.py:107-111 осознанно: импорт того модуля потянул
# бы pandas и весь learning-стек в сторожа.
STRATEGY_ID = "osc_range_moex_d1_fwd"
# Набор РАСТЁТ (bot/universe.py). Единственный расширяемый: форвард и сторож
# ходят по нему, измерительные скрипты — по приколоченным наборам.
# list(), а не tuple: psycopg2 адаптирует tuple как SQL-запись, а не массив,
# и ANY(%s) в стороже сломался бы.
TICKERS = list(FORWARD_TICKERS)
# Допуск в календарных днях для проверки «свечи не поступают» (A2). В норме
# возраст последней свечи = 1 день: прогон в 00:15 грузит бар за прошлый день.
MAX_AGE_DEFAULT = 2

# Выше этого порог не поднять ничем. Сторож — защита, а защита не должна тихо
# ослабляться из файла с настройками: 26.07 ровно это и произошло — процесс с
# поднятым FWD_MAX_AGE_DAYS сказал «форвард жив» при возрасте бара 14 дней.
# .env может только УЖЕСТОЧИТЬ (1..3); значение выше игнорируется, и об этом
# пишется в само сообщение, а не только в лог.
MAX_AGE_HARD_LIMIT = 3

# Дублируется с run_forward_d1.py:CATCHUP_FLAG_BARS осознанно (см. выше про
# импорт-бюджет). Разрыв от этого числа баров зовёт человека: календарь такого
# не даёт — бары идут ~0.96 на календарный день, максимальный безобидный
# разрыв за 3 года = 2 бара. Разрыв 1-2 бара форвард догоняет молча, и это ℹ,
# а не тревога.
CATCHUP_FLAG_BARS = 3

DB_ATTEMPTS = 3      # Docker Desktop может дотягиваться после логона
DB_RETRY_SEC = 10
DB_CONNECT_TIMEOUT = 10

FORWARD_LOG = ROOT / "logs" / "forward_d1.log"

# ── Коды возврата ────────────────────────────────────────────────────────────
#
# Раздельные, потому что 02.08 код 1 означал сразу два разных события:
# «сторож посчитал верно, но доставка не удалась» и «сторож упал». Различить их
# по LastTaskResult было нельзя, а действия они требуют противоположные —
# в первом случае чинят канал, во втором сторожа.
EXIT_OK = 0
EXIT_NOT_DELIVERED = 1        # значение СОХРАНЕНО: человек уже знает этот код
EXIT_NO_CREDENTIALS = 3       # как и раньше
EXIT_CRASHED = 4              # новое: сторож упал, вердикта нет вовсе

# Память между запусками: чем было last_candle_time в прошлый раз. Нужна для
# проверки разрыва (A3) — прыжок состояния через даты свечей иначе не увидеть,
# forward_state истории не хранит. Своя таблица не заводится намеренно: сторож
# остаётся read-only по БД и не зависит от миграций того, что он охраняет.
STATE_FILE = ROOT / "bot" / "data" / "forward_healthcheck_state.json"

logger = logging.getLogger("quantflow.healthcheck")


def _max_age_days() -> tuple[int, str | None]:
    """(действующий порог, пометка для сообщения или None).

    Пометка возвращается наружу, а не только логируется: попытка ослабить
    сторожа должна быть видна в Telegram, иначе она снова потеряется.
    """
    raw = os.getenv("FWD_MAX_AGE_DAYS")
    if raw is None or raw.strip() == "":
        return MAX_AGE_DEFAULT, None
    try:
        value = int(raw)
    except ValueError:
        return (MAX_AGE_DEFAULT,
                f"⚠ FWD_MAX_AGE_DAYS={raw!r} — не число, взят дефолт {MAX_AGE_DEFAULT}")
    if value > MAX_AGE_HARD_LIMIT:
        return (MAX_AGE_HARD_LIMIT,
                f"⚠ порог из .env ({value}) проигнорирован, "
                f"взят жёсткий предел {MAX_AGE_HARD_LIMIT}")
    if value < 1:
        # 0 или отрицательное — тревога каждый день, то есть сторож в шуме.
        return 1, f"⚠ FWD_MAX_AGE_DAYS={value} поднято до 1"
    return value, None


MAX_AGE_DAYS, MAX_AGE_NOTE = _max_age_days()


def _setup_logging() -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "forward_healthcheck.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ── Чтение БД ────────────────────────────────────────────────────────────

class Snapshot(NamedTuple):
    """Всё, что сторож прочитал из БД за один заход."""
    rows: list[tuple[str, datetime]]        # forward_state
    candles_max: datetime | None            # max(candles.time) по нашим тикерам
    candle_dates: dict[str, list[date]]     # тикер → даты баров D1 (окно проверок)
    catchups: dict[str, dict]               # тикер → сводка догонов из журнала


def read_state(prev: dict[str, date] | None = None,
               log_since: datetime | None = None) -> Snapshot:
    """Снимок состояния. Только SELECT, ничего не пишем.

    prev — прошлые last_candle_time по тикерам: от них зависит, с какой даты
    выгружать даты свечей (окно должно накрыть и разрыв A3, и необработанные
    бары A1).

    Исключение наружу — его ловит main() и шлёт «БД недоступна».
    """
    last_exc: Exception | None = None
    for attempt in range(1, DB_ATTEMPTS + 1):
        try:
            conn = psycopg2.connect(config.db.dsn, connect_timeout=DB_CONNECT_TIMEOUT)
            break
        except Exception as exc:
            last_exc = exc
            logger.warning("Подключение к БД, попытка %d/%d: %s",
                           attempt, DB_ATTEMPTS, first_line(exc))
            if attempt < DB_ATTEMPTS:
                time.sleep(DB_RETRY_SEC)
    else:
        raise last_exc  # type: ignore[misc]

    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker, last_candle_time FROM forward_state
                WHERE strategy_id = %s ORDER BY ticker
                """,
                (STRATEGY_ID,),
            )
            rows = [(r[0], r[1]) for r in cur.fetchall()]

            cur.execute(
                "SELECT max(time) FROM candles WHERE timeframe = '1d' AND ticker = ANY(%s)",
                (TICKERS,),
            )
            candles_max = cur.fetchone()[0]

            # Даты баров начиная с самого раннего интересного момента: минимум
            # из прошлых и текущих last_candle_time. Раньше грузить незачем,
            # позже — потеряем разрыв.
            anchors = [ts for _, ts in rows]
            since = min(anchors).astimezone(timezone.utc) if anchors else None
            if prev:
                earliest_prev = min(prev.values())
                since_prev = datetime.combine(earliest_prev, dtime.min, tzinfo=timezone.utc)
                since = min(since, since_prev) if since else since_prev

            candle_dates: dict[str, list[date]] = {}
            if since is not None:
                cur.execute(
                    """
                    SELECT ticker, time FROM candles
                    WHERE timeframe = '1d' AND ticker = ANY(%s) AND time >= %s
                    ORDER BY ticker, time
                    """,
                    (TICKERS, since - timedelta(days=1)),
                )
                # Только ЗАКРЫТЫЕ бары. Догрузка свечей на внеурочном прогоне
                # тянет с ISS частичный бар за сегодня, а прогон его не
                # обрабатывает (market_time.last_closed_index). Без этого
                # фильтра A1 объявляет его «необработанным» и сторож 🚨-ит
                # каждый раз, когда днём кто-то запустил форвард руками.
                # candles_max для A2 считается отдельно и остаётся сырым:
                # частичный бар — законное доказательство, что загрузка жива.
                today_msk = datetime.now(MSK).date()
                for ticker, ts in cur.fetchall():
                    if ts.astimezone(MSK).date() >= today_msk:
                        continue
                    candle_dates.setdefault(ticker, []).append(_bar_date(ts))

            # Журнал догонов. Без него сторож не может отличить «форвард прошёл
            # бары насквозь, обработав выходы» от «форвард их перескочил»:
            # A3 видит только две конечные точки своей памяти, а после
            # внедрения догона обе картины дают один и тот же отпечаток.
            #
            # Окно журнала — от последней УСПЕШНОЙ доставки (saved_at), а не от
            # даты состояния: догон случается один раз, и доложить о нём нужно
            # тоже один раз. С окном по датам состояния разовый разрыв тревожил
            # бы каждые сутки, пока не выпадет из окна, — та же усталость от
            # ложных тревог, ради которой всё это и переписывается. Если
            # доставка не удалась, save_state не вызывается, saved_at остаётся
            # старым и событие повторится — так и надо (см. main()).
            catchups: dict[str, dict] = {}
            window_from = log_since or (since - timedelta(days=1) if since else None)
            if window_from is not None:
                cur.execute(
                    """
                    SELECT ticker, gap_bars, bars_processed, bars_discarded,
                           first_bar, last_bar,
                           COALESCE(jsonb_array_length(exits), 0) AS n_exits,
                           COALESCE(jsonb_array_length(duplicates), 0) AS n_dups
                    FROM forward_catchup_log
                    WHERE strategy_id = %s AND logged_at >= %s
                    ORDER BY ticker, logged_at
                    """,
                    (STRATEGY_ID, window_from),
                )
                for tk, gap, done, dropped, first_b, last_b, n_exits, n_dups in cur.fetchall():
                    agg = catchups.setdefault(tk, {
                        "max_gap": 0, "processed": 0, "discarded": 0,
                        "exits": 0, "duplicates": 0, "covered": set(),
                    })
                    agg["max_gap"] = max(agg["max_gap"], gap or 0)
                    agg["processed"] += done or 0
                    agg["discarded"] += dropped or 0
                    agg["exits"] += n_exits or 0
                    agg["duplicates"] += n_dups or 0
                    if first_b and last_b:
                        # Даты, которые догон объявил обработанными: по ним A3
                        # больше не тревога.
                        day = _bar_date(first_b)
                        while day <= _bar_date(last_b):
                            agg["covered"].add(day)
                            day += timedelta(days=1)
    finally:
        conn.close()
    return Snapshot(rows, candles_max, candle_dates, catchups)


# ── Вердикт ──────────────────────────────────────────────────────────────

def _bar_date(value: datetime):
    """МОСКОВСКАЯ дата сессии бара — единственно верная (долг №16).

    Было `.astimezone(timezone.utc).date()`. После нормализации данных к канону
    (метка = московская полночь сессии) UTC-дата даёт сессию МИНУС ОДИН день у
    ВСЕХ строк, а не у части. Замерено 28.07 сразу после ремонта: сторож писал
    «обработано до 2026-07-26» при фактически обработанной сессии 27.07 и
    возраст «2 дн. при пороге 2» вместо 1 — то есть весь запас порога был съеден
    молча, и первый же нерабочий день дал бы ложное ⚠.
    """
    return session_date(value)


# ── Память между запусками ───────────────────────────────────────────────

def read_saved_state() -> tuple[dict[str, date] | None, str | None, datetime | None]:
    """(прошлые даты по тикерам, пометка, время последней доставки).

    None в первом элементе — базы сравнения нет. Любая проблема с файлом =
    «базы нет»: сторож не должен падать из-за своей же памяти, а ложная тревога
    о разрыве хуже пропущенной.

    Третий элемент — saved_at: от него отсчитывается окно журнала догонов,
    чтобы каждый догон был доложен ровно один раз. None = докладываем всё, что
    нашли (первый запуск).
    """
    if not STATE_FILE.exists():
        return None, "база сравнения создана — разрыв проверяется со следующего запуска", None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if data.get("strategy_id") != STRATEGY_ID:
            return None, (f"база сравнения была по {data.get('strategy_id')!r} — "
                          f"перезаписана под {STRATEGY_ID}"), None
        saved = {t: date.fromisoformat(v) for t, v in (data.get("tickers") or {}).items()}
        saved_at = None
        raw_at = data.get("saved_at")
        if raw_at:
            try:
                saved_at = datetime.fromisoformat(raw_at)
                if saved_at.tzinfo is None:
                    saved_at = saved_at.replace(tzinfo=timezone.utc)
            except ValueError:
                saved_at = None      # битая метка = докладываем всё
        return ((saved or None),
                (None if saved else "база сравнения пуста — перезаписана"),
                saved_at)
    except Exception as exc:
        return None, f"база сравнения повреждена ({first_line(exc)}) — перезаписана", None


def save_state(dates: dict[str, date]) -> None:
    """Атомарная запись: tmp + replace, как в bot/risk/state_store.py:48-52.

    Без portalocker: писатель один (сторож, раз в сутки), а лишняя зависимость
    расширила бы импорт-бюджет сторожа.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "strategy_id": STRATEGY_ID,
        "tickers": {t: d.isoformat() for t, d in sorted(dates.items())},
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ── Диагностика ночного прогона ──────────────────────────────────────────

_LOG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
LOG_TAIL_BYTES = 64 * 1024


def _last_log_entry() -> datetime | None:
    """Время последней датированной строки forward_d1.log.

    Читается хвост, а не весь файл: лог растёт, а нужна одна строка.
    """
    with FORWARD_LOG.open("rb") as fh:
        fh.seek(0, 2)
        fh.seek(max(0, fh.tell() - LOG_TAIL_BYTES))
        tail = fh.read().decode("utf-8", errors="replace")
    for line in reversed(tail.splitlines()):
        match = _LOG_TS.match(line)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return None


def _forward_log_line() -> str:
    """Когда ночной прогон писал в лог — сигнал «стартовал ли он вообще»,
    независимый от БД. Чистое чтение, docker не трогаем.

    По содержимому, а не по mtime: 26.07 mtime показал «обновлён 25.07 00:15»,
    хотя последняя запись в логе была от 20.07 (ротация или touch). Врала
    диагностика ровно там, где она важнее всего — когда прогон мёртв.
    Расхождение больше суток печатается явно, чтобы такие случаи было видно.
    """
    try:
        mtime = datetime.fromtimestamp(FORWARD_LOG.stat().st_mtime)
        entry = _last_log_entry()
        if entry is None:
            return (f"Ночной прогон: в forward_d1.log нет датированных строк "
                    f"(mtime {mtime:%d.%m %H:%M})")
        line = f"Ночной прогон: последняя запись {entry:%d.%m %H:%M}"
        if abs((mtime - entry).total_seconds()) > 86400:
            line += f" (mtime файла {mtime:%d.%m %H:%M} — расходится)"
        return line
    except FileNotFoundError:
        return "Ночной прогон: forward_d1.log отсутствует"
    except Exception as exc:
        return f"Ночной прогон: лог не прочитать ({first_line(exc)})"


# ── A5: состоялся ли прогон в свой слот ──────────────────────────────────
#
# Проверка стоит на ПОЛОЖИТЕЛЬНОМ свидетельстве — записи, которую прогон делает
# о себе сам (bot/run_journal.py), — а не на выводе из пустоты. Вывод по пустоте
# уже подвёл: 01.08 прогон уехал с слота 00:15 на 11:38, к моменту проверки бар
# был на месте, и сторож сказал «✅ Форвард жив» (долг №46).
#
# Торгового календаря здесь НЕТ и не нужно: задача стоит на каждый день, значит
# запись обязана быть и в биржевой праздник. Календарь нужен ДРУГОЙ проверке —
# «прогон был, но сессию не обработал», — и она сознательно вынесена: календаря
# в проекте нет, а без него она дала бы ложные тревоги на праздниках.
#
# 🚩 ГРАНИЦА ЭТОГО ЛЕКАРСТВА, записанная явно (долг №46, пункт 3): проверка
# живёт на ТОЙ ЖЕ машине, что и прогон, и потому срабатывает только ПОСЛЕ её
# включения. Выключенная машина по-прежнему не скажет ничего — ровно как 29.07
# (холодная загрузка, BootType=0) и 31.07 (Быстрый запуск, BootType=1). Остаётся человеческая процедура: ОТСУТСТВИЕ
# сообщения в 09:00 есть тревога, и замечает её человек. Кодом на этой машине
# не лечится; это же — измеренный довод за внешний хост (§10).


class SlotReport(NamedTuple):
    alarm: bool
    headline: str | None      # заголовок сообщения, если тревога
    lines: list[str]          # строки подробностей (уходят в тело всегда)


def _read_journal() -> tuple[list[dict], str | None]:
    """(записи журнала прогонов, причина недоступности или None).

    Битые строки НЕ пропускаются молча: журнал — свидетельство, и «часть строк
    не разобралась» обязано быть видно, иначе пропуск прогона спрячется за
    испорченной строкой.
    """
    path = Path(journal_path(ROOT))
    if not path.exists():
        return [], "файла нет"
    records: list[dict] = []
    broken = 0
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                broken += 1
    except OSError as exc:
        return [], first_line(exc)
    if broken:
        return records, f"{broken} строк не разобрано"
    return records, None


def _parse_at(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _slot_report(now: datetime) -> SlotReport:
    """Вердикт по последнему прошедшему слоту 00:15. Шесть состояний.

    Пятое состояние — «прогон ИДЁТ» — не роскошь: замерено 01.08, что при
    догоне после включения планировщик стартует форвард и сторожа ОДНОЙ секундой
    (форвард 11:38:44, сторож 11:38:45, финиш прогона 11:38:56). Без льготного
    интервала сторож объявлял бы собственный живой прогон мёртвым, и не разово,
    а на КАЖДОЙ догнанной ночи.
    """
    slot = last_slot(now)
    slot_txt = f"{slot:%d.%m %H:%M}"
    records, unreadable = _read_journal()

    if unreadable == "файла нет":
        return SlotReport(True, "🚨 <b>Журнал прогонов потерян</b>",
                          [f"Слот {slot_txt}: проверить нечем — "
                           f"{escape(str(journal_path(ROOT)))} отсутствует.",
                           "  ⇒ это НЕ «прогона не было»: свидетельство утрачено, "
                           "и различить два случая нельзя"])
    if unreadable:
        return SlotReport(True, "🚨 <b>Журнал прогонов не читается</b>",
                          [f"Слот {slot_txt}: {escape(unreadable)}"])

    created = next((_parse_at(r.get("at")) for r in records
                    if r.get("event") == "journal_created"), None)
    if created is None:
        return SlotReport(True, "🚨 <b>Журнал прогонов без метки создания</b>",
                          [f"Слот {slot_txt}: строки journal_created нет — "
                           "журнал усечён или подменён"])
    if created > slot:
        return SlotReport(True, "🚨 <b>Журнал прогонов пересоздан после слота</b>",
                          [f"Слот {slot_txt}: журнал создан {created:%d.%m %H:%M}, "
                           f"то есть ПОЗЖЕ слота — свидетельство утрачено.",
                           "  ⇒ при вводе журнала в строй это ожидаемо ОДИН раз "
                           "(раздел 2з); второй раз — дефект"])

    # Пары старт→финиш: финиш относится к ближайшему предшествующему старту.
    # Позиционно, а не по полю: у финиша слота нет и быть не может — .bat пишет
    # его, не зная о слотах, и вторая копия этого знания была бы лишней.
    runs: list[dict] = []
    for rec in records:
        event = rec.get("event")
        if event == "start":
            runs.append({"at": _parse_at(rec.get("at")),
                         "slot": _parse_at(rec.get("slot")),
                         "rc": None, "done": None, "session": None})
        elif event == "finish" and runs:
            runs[-1]["rc"] = rec.get("rc")
            runs[-1]["done"] = _parse_at(rec.get("at"))
        elif event == "session" and runs:
            runs[-1]["session"] = rec.get("session")

    mine = [r for r in runs if r["slot"] == slot and r["at"] is not None]
    if not mine:
        return SlotReport(True, "🚨 <b>Форвард НЕ СТАРТОВАЛ в слот 00:15</b>",
                          [f"Слот {slot_txt} пуст: прогона до сих пор нет, "
                           "записи о старте в журнале нет.",
                           "  ⇒ смотреть, выключалась ли машина; долг №45"])

    run = mine[-1]
    late = (run["at"] - slot).total_seconds() > SLOT_TOLERANCE_SEC
    started_txt = f"{run['at']:%d.%m %H:%M:%S}"
    # Время финиша печатается рядом со стартом: по двум меткам видно, сколько
    # прогон шёл, и потому «код 0» перестаёт быть единственным свидетельством.
    finish_txt = f", финиш {run['done']:%H:%M:%S}" if run["done"] else ""
    session_txt = (f", обработана московская сессия {run['session']}"
                   if run["session"] else "")

    if run["rc"] is None:
        elapsed = int((now - run["at"]).total_seconds())
        detail = (f"старт {started_txt}, финиша нет, "
                  f"прошло {elapsed} с из {GRACE_SEC}")
        if elapsed >= GRACE_SEC:
            if late:
                return SlotReport(
                    True, "🚨 <b>Слот 00:15 пропущен, ДОГОН УМЕР</b>",
                    [f"Слот {slot_txt} пуст; {detail}.",
                     "  ⇒ прогон умер: запустился и не дошёл до конца; долг №45"])
            return SlotReport(
                True, "🚨 <b>Прогон умер</b>",
                [f"Слот {slot_txt}: {detail}.",
                 "  ⇒ прогон умер: запустился и не дошёл до конца"])
        # Прогон ИДЁТ. Тревога — только если при этом пропущен слот: сам факт
        # «идёт» нормален и составляет пятое состояние (см. докстринг).
        if late:
            return SlotReport(
                True, "🚨 <b>Слот 00:15 пропущен, ДОГОН ИДЁТ</b>",
                [f"Слот {slot_txt} пуст; {detail}.",
                 "  ⇒ смотреть, выключалась ли машина; долг №45"])
        return SlotReport(False, None,
                          [f"Прогон слота {slot_txt}: старт {started_txt}, "
                           f"идёт {elapsed} с из {GRACE_SEC}"])

    if run["rc"] != 0:
        return SlotReport(True, "🚨 <b>Прогон завершился с ошибкой</b>",
                          [f"Слот {slot_txt}: старт {started_txt}"
                           f"{finish_txt}, код завершения {run['rc']}"
                           f"{session_txt}"])
    if late:
        return SlotReport(True, "🚨 <b>Слот 00:15 пропущен, ДОГОН СОСТОЯЛСЯ</b>",
                          [f"Слот {slot_txt} пуст; старт {started_txt}"
                           f"{finish_txt}, код 0{session_txt}.",
                           "  ⇒ данные на месте, чинить расписание, а не прогон; "
                           "долг №45"])
    if not run["session"]:
        return SlotReport(True, "🚨 <b>Прогон отчитался успехом без сессии</b>",
                          [f"Слот {slot_txt}: старт {started_txt}"
                           f"{finish_txt}, код 0, но записи об обработанной "
                           "московской сессии нет",
                           "  ⇒ прогон завершился, не дойдя до обработки тикеров"])
    return SlotReport(False, None,
                      [f"Прогон слота {slot_txt}: старт {started_txt}"
                       f"{finish_txt}, код 0{session_txt}"])


def _compact(per_ticker: dict[str, int]) -> str:
    """«13 по всем 20 тикерам» вместо двадцати одинаковых строк.

    Тикеры почти всегда идут в ногу, и полный список в такой ситуации — шум,
    в котором теряется единственное важное число.
    """
    counts = set(per_ticker.values())
    if len(counts) == 1 and len(per_ticker) == len(TICKERS):
        return f"{counts.pop()} по всем {len(TICKERS)} тикерам"
    items = sorted(per_ticker.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = ", ".join(f"{t} {n}" for t, n in items[:6])
    return shown + (f" и ещё {len(items) - 6}" if len(items) > 6 else "")


def build_message(snap: Snapshot, prev: dict[str, date] | None,
                  prev_note: str | None = None) -> str:
    """Текст сообщения по состоянию форварда.

    Четыре независимые проверки вместо одного смешанного условия:
      A1 🚨 есть бары новее обработанного — форвард не обрабатывает свечи;
      A2 ⚠  свечи не поступают N дн. — рынок закрыт ИЛИ сломалась загрузка;
      A3 ℹ/🚨 состояние прошло через даты свечей — норма (догон), если это
            подтверждено forward_catchup_log; тревога, если бары выброшены,
            продвижение не объяснено журналом или разрыв >= CATCHUP_FLAG_BARS;
      A4 🚨 тикер исчез из forward_state;
      A5 🚨 прогон НЕ СОСТОЯЛСЯ в свой слот — по журналу прогонов, шесть
            состояний, включая «идёт» (см. _slot_report).

    A1 не зависит от календаря (закрыт рынок → новых дат нет → тихо), поэтому
    ложных тревог на праздниках не даёт. A2 зависит и потому только ⚠ и с
    честно неоднозначной формулировкой: различить «рынок закрыт» от «загрузка
    умерла» без торгового календаря нельзя, а человек различает за секунду.
    Вместе они закрывают оба режима отказа: при полной смерти прогона candles
    и forward_state замерзают вместе, A1 слепнет — ловит A2.

    A5 не заменяет их, а закрывает то, что все четыре пропускали по построению:
    они судят о ДАННЫХ, а не о том, случился ли прогон. 01.08 данные были на
    месте (прогон отработал в 11:38 вместо 00:15), и все четыре молчали
    законно. A5 календаря не требует и потому от праздников не зависит вовсе.

    Тревога A5 НЕ добавляется в `alarm`: тот флаг включает поимённый дамп баров
    по тикерам, а пропуск прогона про тикеры ничего не говорит — дамп был бы
    двадцатью строками шума.
    """
    now = datetime.now(MSK)
    today = now.date()   # МСК, не UTC: сравнивается с московскими датами сессий (долг №16)
    log_line = _forward_log_line()
    slot = _slot_report(now)
    tasks_alarm, tasks_line = describe_tasks()
    tail = slot.lines + [tasks_line] \
        + ([MAX_AGE_NOTE] if MAX_AGE_NOTE else []) \
        + ([prev_note] if prev_note else []) + [log_line]

    # Заголовки тревог, которые к состоянию тикеров не относятся и потому
    # выносятся вперёд основного вердикта.
    top: list[str] = []
    if slot.alarm:
        top.append(f"{slot.headline} — {STRATEGY_ID}")
    if tasks_alarm:
        top.append(f"🚨 <b>Расписание задач уехало</b> — {STRATEGY_ID}")

    if not snap.rows:
        return "\n".join([
            *top,
            f"🚨 <b>Форвард не запускался</b> — {STRATEGY_ID}",
            "В forward_state нет ни одной строки по стратегии.",
            *tail,
        ])

    dates = {ticker: _bar_date(ts) for ticker, ts in snap.rows}
    fwd_max = max(dates.values())
    age = (today - fwd_max).days

    # A4 — тикеры, которых вообще нет в состоянии.
    missing = [t for t in TICKERS if t not in dates]
    behind = sorted(t for t, d in dates.items() if d < fwd_max)

    # A1 — даты баров новее обработанного, по каждому тикеру.
    unprocessed = {}
    for ticker, processed in dates.items():
        newer = [d for d in snap.candle_dates.get(ticker, []) if d > processed]
        if newer:
            unprocessed[ticker] = len(newer)

    # A2 — свечи не поступают (по календарю, с жёстко ограниченным порогом).
    candles_date = _bar_date(snap.candles_max) if snap.candles_max else None
    candles_age = (today - candles_date).days if candles_date else None
    # `>=`, а НЕ `>`. Со строгим сравнением порог, названный «2», стрелял с 3:
    # 01.08 сообщение сказало «✅ Форвард жив» при «2 дн. назад, порог 2», потому
    # что `2 > 2` = False. Класс «проглоченный порог» §8, второй раз в проекте.
    # Норма этим не задета: в норме возраст последней свечи = 1 день (см.
    # MAX_AGE_DEFAULT), то есть запас остаётся, но он теперь тот, который назван.
    stale_feed = candles_date is None or candles_age >= MAX_AGE_DAYS

    # A3 — многобарное продвижение состояния. С внедрением догона (долг №14)
    # это НОРМА, а не тревога: форвард проходит пропущенные бары насквозь,
    # обрабатывая на них выходы. По двум конечным точкам своей памяти сторож
    # «прошёл» от «перескочил» отличить не может — поэтому здесь читается
    # forward_catchup_log, а не угадывается по датам.
    #
    # Тревога остаётся ровно для трёх случаев:
    #   - бары ВЫБРОШЕНЫ (разрыв глубже предела догона);
    #   - продвижение НЕ ОБЪЯСНЕНО журналом — после фикса это может значить
    #     только ручное вмешательство в forward_state или регрессию в коде,
    #     потому что дальше предела прогон отказывается двигаться сам;
    #   - разрыв >= CATCHUP_FLAG_BARS, даже полностью догнанный: календарь
    #     такого не даёт, значит прогон несколько дней не состоялся.
    walked: dict[str, list[date]] = {}      # догнано — ℹ
    orphan: dict[str, list[date]] = {}      # не объяснено журналом — 🚨
    if prev:
        for ticker, current in dates.items():
            was = prev.get(ticker)
            if was is None or current <= was:
                continue
            skipped = [d for d in snap.candle_dates.get(ticker, []) if was < d < current]
            if not skipped:
                continue
            covered = snap.catchups.get(ticker, {}).get("covered", set())
            unexplained = [d for d in skipped if d not in covered]
            if unexplained:
                orphan[ticker] = unexplained
            explained = [d for d in skipped if d in covered]
            if explained:
                walked[ticker] = explained

    discarded = {t: c["discarded"] for t, c in snap.catchups.items() if c["discarded"]}
    wide_gaps = {t: c["max_gap"] for t, c in snap.catchups.items()
                 if c["max_gap"] >= CATCHUP_FLAG_BARS}
    dup_bars = {t: c["duplicates"] for t, c in snap.catchups.items() if c["duplicates"]}

    alarm = bool(unprocessed or orphan or discarded or wide_gaps or missing)

    lines: list[str] = list(top)
    if discarded:
        lines.append(f"🚨 <b>Форвард выбросил бары разрыва</b> — {STRATEGY_ID}")
    elif orphan:
        lines.append(f"🚨 <b>Форвард пропустил бары</b> — {STRATEGY_ID}")
    elif wide_gaps:
        lines.append(f"🚨 <b>Форвард догнал широкий разрыв</b> — {STRATEGY_ID}")
    elif unprocessed:
        lines.append(f"🚨 <b>Форвард не обрабатывает свечи</b> — {STRATEGY_ID}")
    elif missing:
        lines.append(f"🚨 <b>Форвард потерял тикеры</b> — {STRATEGY_ID}")
    elif stale_feed:
        lines.append(f"⚠ <b>Свечи не поступают</b> — {STRATEGY_ID}")
    elif not top:
        # ✅ только когда молчат И тикеры, И A5, И расписание. Иначе строка
        # «Форвард жив» стояла бы рядом с 🚨 о непроизошедшем прогоне.
        lines.append(f"✅ <b>Форвард жив</b> — {STRATEGY_ID}")

    # Возраст обработанного — БЕЗ подписи «порог»: он с этим порогом не
    # сравнивается. До 01.08 подпись стояла именно здесь, а сравнивался возраст
    # СВЕЧЕЙ (см. stale_feed) — две разные величины, совпавшие в тот день на
    # числе 2, из-за чего сообщение выглядело связным. Долг №46, пункт 2б.
    lines.append(f"Обработано до: <b>{fwd_max}</b> ({age} дн. назад)")
    lines.append(f"Тикеров в состоянии: {len(dates)}/{len(TICKERS)}")

    if discarded:
        lines.append(f"🚨 Выброшено баров: {_compact(discarded)}")
        lines.append("  ⇒ разрыв глубже предела догона: по этим барам выходы НЕ "
                     "проверялись, решение за человеком")

    if orphan:
        all_skipped = sorted({d for days in orphan.values() for d in days})
        span = (f"{all_skipped[0]}" if len(all_skipped) == 1
                else f"{all_skipped[0]}–{all_skipped[-1]}")
        lines.append(f"🚨 Не объяснено журналом: "
                     f"{_compact({t: len(v) for t, v in orphan.items()})} ({span})")
        lines.append("  ⇒ состояние двинулось без записи в forward_catchup_log: "
                     "ручная правка forward_state или регрессия в коде")

    if walked:
        all_walked = sorted({d for days in walked.values() for d in days})
        span = (f"{all_walked[0]}" if len(all_walked) == 1
                else f"{all_walked[0]}–{all_walked[-1]}")
        exits = sum(snap.catchups.get(t, {}).get("exits", 0) for t in walked)
        icon = "🚨" if wide_gaps else "ℹ"
        lines.append(f"{icon} Догнано баров: "
                     f"{_compact({t: len(v) for t, v in walked.items()})} ({span}), "
                     f"выходов сработало {exits}")
        if wide_gaps:
            lines.append(f"  ⇒ разрыв {max(wide_gaps.values())} баров — прогон "
                         f"несколько дней не состоялся, календарь такого не даёт")

    if dup_bars:
        lines.append(f"⚠ Бары-двойники на одну сессию: {_compact(dup_bars)}")
        lines.append("  ⇒ окна индикаторов сдвинуты фантомным баром, данные "
                     "требуют ремонта")

    if unprocessed:
        lines.append(f"🚨 Не обработано баров: {_compact(unprocessed)}")
        lines.append("  ⇒ прогон стартует, но не обрабатывает тикеры")

    # Порог печатается ВСЕГДА и РЯДОМ С ТЕМ ЧИСЛОМ, которое с ним сравнивается.
    # Оба требования куплены замерами: 26.07 неоднозначность «жив при 14 днях»
    # существовала потому, что ветка ✅ порога не показывала; 01.08 подпись
    # стояла у возраста forward_state, а сравнивался возраст свечей.
    if candles_date is None:
        lines.append(f"⚠ Свечи D1 в БД: нет ни одной по этим тикерам "
                     f"(порог {MAX_AGE_DAYS})")
    else:
        lines.append(f"Свечи D1 в БД: до {candles_date} "
                     f"({candles_age} дн. назад, порог {MAX_AGE_DAYS})")
        if stale_feed:
            lines.append("  ⇒ либо рынок закрыт, либо сломалась загрузка свечей")

    if missing:
        lines.append("🚨 Нет в forward_state: " + ", ".join(missing))
    if behind:
        lines.append("Отстают: " + ", ".join(f"{t} {dates[t]}" for t in behind))

    if alarm:
        lines.append("Последний бар по тикерам:")
        lines += [f"  {t} {dates[t]}" for t in sorted(dates)]

    lines += tail
    return "\n".join(lines)


# ── Точка входа ──────────────────────────────────────────────────────────

def _with_pending_notice(text: str) -> str:
    """Приписать сверху список ВСЕХ прошлых недоставок, если они были.

    Сверху, а не снизу: сообщение сторожа длинное, и строка о том, что вчера
    человек чего-то НЕ ПОЛУЧИЛ, обязана попасться на глаза раньше вердикта.
    Отдельной функцией — чтобы её можно было проверить тестом, не поднимая ни
    БД, ни планировщик.
    """
    notice = notify.pending_notice()
    return f"{notice}\n{text}" if notice else text


def main() -> int:
    _setup_logging()

    # Слать некуда — проверять нечего: код 3, как и раньше.
    if not credentials_ready():
        return EXIT_NO_CREDENTIALS

    prev, prev_note, saved_at = read_saved_state()
    if prev_note:
        logger.info("Память сторожа: %s", prev_note)

    try:
        snap = read_state(prev, log_since=saved_at)
    except Exception as exc:
        # Требование: отдельное сообщение, выход без трейсбека.
        # Состояние НЕ трогаем: сравнивать будет не с чем, а разрыв,
        # случившийся за это время, должен обнаружиться в следующий раз.
        reason = first_line(exc)
        logger.error("БД недоступна: %s", reason)
        text = _with_pending_notice(
            "⚠️ <b>БД недоступна, форвард не проверить</b>\n"
            f"{STRATEGY_ID} — проверка пропущена\n"
            f"Ошибка: {escape(reason)}"
        )
        if send(text):
            notify.clear_pending()
            return EXIT_OK
        return EXIT_NOT_DELIVERED

    text = _with_pending_notice(build_message(snap, prev, prev_note))
    logger.info("Вердикт:\n%s", text)
    delivered = send(text)

    # Запись только после успешной доставки: иначе тревога о разрыве была бы
    # «прочитана» сторожем и забыта, хотя человек её не видел. Пока Telegram
    # недоступен, разрыв будет повторяться в каждом сообщении — так и надо.
    if delivered and snap.rows:
        try:
            save_state({t: _bar_date(ts) for t, ts in snap.rows})
        except Exception as exc:
            logger.error("Состояние сторожа не сохранено: %s", first_line(exc))

    # Накопитель чистит ТОТ, КТО ПОКАЗАЛ приписку человеку, и только после
    # подтверждённой доставки. Тот же довод, что у save_state выше: пока
    # сообщение не дошло, «прочитано и забыто» недопустимо.
    if delivered:
        notify.clear_pending()

    return EXIT_OK if delivered else EXIT_NOT_DELIVERED


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:      # последний барьер: без трейсбека наружу
        logger.error("Сторож упал: %s", first_line(exc))
        sys.exit(EXIT_CRASHED)
