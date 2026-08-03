#!/bin/bash
# Г2: ПАРНЫЙ КОНТРОЛЬ долга №48 на ПЕРЕСОЗДАННОМ клоне forward_control.
#
# Боевая БД только читалась (клон сделан TEMPLATE). Все записи — в клон.
# Боевой logs/forward_runs.jsonl не касается: журнал пишется только под
# расписанием (FWD_IN_SLOT_RUN не выставлен), плюс путь перекрыт на scratch.
# Telegram заглушён пустым TELEGRAM_TOKEN. Сторож вручную не запускается,
# bot/data/forward_healthcheck_state.json не трогается.
set -u
cd /d/Trading-Bot-Nik
SP="$1"
DEC_BAR='2026-07-30 21:00:00+00'      # бар решения, сессия 2026-07-31
SYN_BAR='2026-08-02 21:00:00+00'      # синтетический ФОРМИРУЮЩИЙСЯ бар сессии 2026-08-03 (сегодня)
PREV='2026-07-29 21:00:00+00'         # состояние на сессию 2026-07-30

psqlc() { docker exec -i trading_db psql -U trader -d forward_control -t -A -F'|' -v ON_ERROR_STOP=1; }

reset_clone() {   # $1 = close синтетического бара или "none"
  {
    echo "UPDATE forward_state SET last_candle_time = '$PREV';"
    echo "DELETE FROM candles WHERE timeframe='1d' AND time > '$DEC_BAR';"
    echo "DELETE FROM skipped_signals;"
    echo "DELETE FROM trades WHERE strategy_id LIKE '%_fwd';"
    if [ "$1" != "none" ]; then
      # синтетический НЕЗАКРЫТЫЙ бар сессии 2026-08-01 — только у TATN
      echo "INSERT INTO candles (time,ticker,timeframe,open,high,low,close,volume)"
      echo "VALUES ('$SYN_BAR','TATN','1d',525.9,$1,525.0,$1,1000);"
    fi
  } | psqlc > /dev/null
}

snap() {   # печатает состояние клона
  {
    echo "SELECT 'trades_fwd', count(*)::text FROM trades WHERE strategy_id LIKE '%_fwd'"
    echo "UNION ALL SELECT 'skipped', count(*)::text FROM skipped_signals"
    echo "UNION ALL SELECT 'last_close', COALESCE((SELECT (details->>'last_close') FROM skipped_signals WHERE ticker='TATN' ORDER BY skipped_at DESC LIMIT 1),'—')"
    echo "UNION ALL SELECT 'rows_1d_TATN', count(*)::text FROM candles WHERE ticker='TATN' AND timeframe='1d'"
    echo "UNION ALL SELECT 'max_1d', max(time)::text FROM candles WHERE timeframe='1d';"
  } | psqlc
}

run_case() {   # $1 = метка, $2 = close синтетики или none, $3 = описание
  echo "############################################################"
  echo "ПРОГОН $1 — $3"
  echo "############################################################"
  reset_clone "$2"
  echo "-- клон подготовлен:"; snap | sed 's/^/     /'
  DB_NAME=forward_control \
  FWD_REPLAY=1 \
  TELEGRAM_TOKEN= \
  TELEGRAM_CHAT_ID= \
  FWD_RUN_JOURNAL="$SP/control_journal_$1.jsonl" \
  PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
    .venv/Scripts/python.exe bot/run_forward_d1.py > "$SP/d48_case_$1.out" 2>&1
  echo "-- код возврата прогона: $?"
  echo "-- ПОСЛЕ прогона:"; snap | sed 's/^/     /'
  echo "-- строки про TATN из лога прогона:"
  grep -E 'TATN' "$SP/d48_case_$1.out" | head -6 | sed 's/^/     /'
  echo
}

echo "=== ЗАЩИТЫ, проверенные ПЕРЕД прогонами ==="
echo "  DB_NAME для прогонов        : forward_control (реплей в боевую падает по построению)"
echo "  TELEGRAM_TOKEN              : пустой -> _send выходит сразу"
echo "  FWD_RUN_JOURNAL             : $SP (боевой logs/forward_runs.jsonl не тронут)"
echo "  FWD_IN_SLOT_RUN             : НЕ выставлен -> строка session не пишется вовсе"
echo -n "  боевой forward_runs.jsonl, строк ДО: "; wc -l < logs/forward_runs.jsonl 2>/dev/null || echo "нет файла"
echo -n "  mtime forward_healthcheck_state.json ДО: "; date -r bot/data/forward_healthcheck_state.json '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "нет файла"
echo

run_case A none     "ночь: строки за сессию 2026-08-01 НЕТ"
run_case B 526.50   "день: бар почти не сдвинулся, close 526.50"
run_case C 700.00   "день: бар ВЫШЕ SMA200, close 700.00"

echo "=== ЗАЩИТЫ, проверенные ПОСЛЕ прогонов ==="
echo -n "  боевой forward_runs.jsonl, строк ПОСЛЕ: "; wc -l < logs/forward_runs.jsonl 2>/dev/null || echo "нет файла"
echo -n "  mtime forward_healthcheck_state.json ПОСЛЕ: "; date -r bot/data/forward_healthcheck_state.json '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "нет файла"
echo -n "  боевая БД: skipped_signals (было 3): "
docker exec -i trading_db psql -U trader -d trading_bot -t -A -c "SELECT count(*) FROM skipped_signals;" 2>&1
echo -n "  боевая БД: trades (было 7532): "
docker exec -i trading_db psql -U trader -d trading_bot -t -A -c "SELECT count(*) FROM trades;" 2>&1
echo -n "  переменных окружения не осталось: FWD_REPLAY='${FWD_REPLAY:-<не задана>}' DB_NAME='${DB_NAME:-<не задана>}'"
echo
