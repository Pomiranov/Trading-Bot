"""QuantFlow — сторож форвард-контура osc_range_moex_d1_fwd.

Запуск:
    python bot\\forward_healthcheck.py     # ежедневно в 09:00 (Task Scheduler)

Читает forward_state по 12 тикерам форвард-стратегии и говорит в Telegram,
жив контур или завис. Сообщение уходит каждый день, включая статус «ок».

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
feedback_store, который ходит в БД на импорте — см. run_forward_d1.py:59).
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import html
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

# Скрипт живёт в bot/, конфиг тоже. Путь и .env — от расположения файла,
# а не от cwd: под Task Scheduler cwd легко оказывается не тем, и тогда
# .env не подхватится, DB_PASSWORD будет пустым, а причина сбоя — ложной.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))
load_dotenv(ROOT / ".env")

from config import config  # noqa: E402  — только после sys.path/.env

# Дублируется с run_forward_d1.py:64-68 осознанно: импорт того модуля потянул
# бы pandas и весь learning-стек в сторожа.
STRATEGY_ID = "osc_range_moex_d1_fwd"
TICKERS = ["SBER", "GAZP", "LKOH", "NVTK", "ROSN", "TATN",
           "MGNT", "MOEX", "PLZL", "CHMF", "ALRS", "SNGS"]

# Допуск в календарных днях. В норме возраст последнего бара = 1 день:
# прогон в 00:15 обрабатывает бар за прошлый день. MOEX торгует и в выходные,
# так что бары есть почти каждый календарный день; допуск 2 переживает один
# пропущенный прогон и короткие праздники (длинные новогодние — дадут тревогу).
MAX_AGE_DAYS = int(os.getenv("FWD_MAX_AGE_DAYS", "2"))

DB_ATTEMPTS = 3      # Docker Desktop может дотягиваться после логона
DB_RETRY_SEC = 10
DB_CONNECT_TIMEOUT = 10

FORWARD_LOG = ROOT / "logs" / "forward_d1.log"

logger = logging.getLogger("quantflow.healthcheck")


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


# ── Telegram ─────────────────────────────────────────────────────────────

def notify(text: str) -> bool:
    """Отправить сообщение в Telegram. True — доставлено.

    Токен и chat_id — из config.telegram (env TELEGRAM_TOKEN /
    TELEGRAM_CHAT_ID), то есть тот же секрет, что у ui/telegram_bot.py.
    Отправка своя, а не через ui.telegram_bot._send: тот модуль на импорте
    тянет legacy feedback_store, risk, signals и ходит в БД.
    """
    token = config.telegram.token
    chat_id = config.telegram.chat_id
    if not token or not chat_id:
        logger.error("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID не заданы — сообщение не отправлено")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        # Текст ошибки requests содержит полный URL, то есть и токен —
        # в лог он попасть не должен.
        logger.error("Telegram: %s", _first_line(exc).replace(token, "<token>"))
        return False


def _first_line(exc: Exception) -> str:
    """Одна строка из исключения — без трейсбека, чтобы не пугать в Telegram."""
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:300]


# ── Чтение БД ────────────────────────────────────────────────────────────

def read_state() -> tuple[list[tuple[str, datetime]], datetime | None]:
    """(строки forward_state, max(candles.time)). Только SELECT.

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
                           attempt, DB_ATTEMPTS, _first_line(exc))
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
    finally:
        conn.close()
    return rows, candles_max


# ── Вердикт ──────────────────────────────────────────────────────────────

def _utc_date(value: datetime):
    """Дата в UTC. candles/forward_state — timestamptz, часть истории
    записана как 21:00+00 (московская полночь), часть как 00:00+00."""
    return value.astimezone(timezone.utc).date()


def _forward_log_line() -> str:
    """mtime лога ночного прогона — сигнал «стартовал ли он вообще»,
    независимый от БД. Чистое чтение, docker не трогаем."""
    try:
        mtime = datetime.fromtimestamp(FORWARD_LOG.stat().st_mtime)
        return f"Ночной прогон: forward_d1.log обновлён {mtime:%d.%m %H:%M}"
    except FileNotFoundError:
        return "Ночной прогон: forward_d1.log отсутствует"
    except Exception as exc:
        return f"Ночной прогон: лог не прочитать ({_first_line(exc)})"


def build_message(rows: list[tuple[str, datetime]], candles_max: datetime | None) -> str:
    """Текст сообщения по состоянию форварда."""
    today = datetime.now(timezone.utc).date()
    log_line = _forward_log_line()

    if not rows:
        return (
            f"🚨 <b>Форвард не запускался</b> — {STRATEGY_ID}\n"
            f"В forward_state нет ни одной строки по стратегии.\n"
            f"{log_line}"
        )

    dates = {ticker: _utc_date(ts) for ticker, ts in rows}
    fwd_max = max(dates.values())
    age = (today - fwd_max).days

    missing = [t for t in TICKERS if t not in dates]
    behind = sorted(t for t, d in dates.items() if d < fwd_max)

    alarm = age > MAX_AGE_DAYS or bool(missing)

    lines: list[str] = []
    if alarm:
        lines.append(f"🚨 <b>Форвард завис</b> — {STRATEGY_ID}")
        lines.append(f"Последний обработанный бар: <b>{fwd_max}</b> "
                     f"({age} дн. назад, порог {MAX_AGE_DAYS})")
    else:
        lines.append(f"✅ <b>Форвард жив</b> — {STRATEGY_ID}")
        lines.append(f"Последний бар: <b>{fwd_max}</b> ({age} дн. назад)")

    lines.append(f"Тикеров в состоянии: {len(dates)}/{len(TICKERS)}")

    # Диагностика: есть ли в БД свечи, которые прогон не обработал.
    if candles_max is None:
        lines.append("Свечи D1 в БД: нет ни одной по этим тикерам")
    else:
        candles_date = _utc_date(candles_max)
        lag = (candles_date - fwd_max).days
        lines.append(f"Свечи D1 в БД: до {candles_date}"
                     + (f" — {lag} необработанных дн." if lag > 0 else ""))
        if alarm:
            if lag > 0:
                lines.append("  ⇒ прогон стартует, но не обрабатывает тикеры")
            else:
                lines.append("  ⇒ свечи тоже не обновляются: прогон не стартует "
                             "(либо праздники на MOEX)")

    if missing:
        lines.append("Нет в forward_state: " + ", ".join(missing))
    if behind:
        lines.append("Отстают: " + ", ".join(f"{t} {dates[t]}" for t in behind))

    if alarm:
        lines.append("Последний бар по тикерам:")
        lines += [f"  {t} {dates[t]}" for t in sorted(dates)]

    lines.append(log_line)
    return "\n".join(lines)


# ── Точка входа ──────────────────────────────────────────────────────────

def main() -> int:
    _setup_logging()

    # Заглушки из .env.example — тот же случай, что «не задано»: слать некуда.
    if (not config.telegram.token or not config.telegram.chat_id
            or config.telegram.token.startswith("your_")
            or config.telegram.chat_id.startswith("your_")):
        logger.error("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID не заданы (или остались "
                     "заглушками из .env.example) — некому уведомлять")
        return 3

    try:
        rows, candles_max = read_state()
    except Exception as exc:
        # Требование: отдельное сообщение, выход без трейсбека.
        reason = _first_line(exc)
        logger.error("БД недоступна: %s", reason)
        text = (
            "⚠️ <b>БД недоступна, форвард не проверить</b>\n"
            f"{STRATEGY_ID} — проверка пропущена\n"
            f"Ошибка: {html.escape(reason)}"
        )
        return 0 if notify(text) else 1

    text = build_message(rows, candles_max)
    logger.info("Вердикт:\n%s", text)
    return 0 if notify(text) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:      # последний барьер: без трейсбека наружу
        logger.error("Сторож упал: %s", _first_line(exc))
        sys.exit(1)
