#!/bin/bash
# Г3: воспроизведение парного контроля 30.07 после формы II.
# Боевая БД только читается. Боевой rules_osc_range.yaml НЕ правится.
set -u
cd /d/Trading-Bot-Nik
SP="$1"
WT="$SP/g3_worktree"
TARGET='2026-07-23 21:00:00+00'   # d1_bar_time(2026-07-24) — бар решения, сессия 24.07
PREV='2026-07-22 21:00:00+00'     # состояние на сессию 2026-07-23

# Доступ к БД — через переменные окружения, значение пароля в argv не попадает.
export DB_PASSWORD=$(sed -n 's/\r$//; s/^DB_PASSWORD=//p' .env | head -1 | sed 's/^"//; s/"$//')
export DB_USER=$(sed -n 's/\r$//; s/^DB_USER=//p' .env | head -1 | sed 's/^"//; s/"$//')
export DB_HOST=127.0.0.1 DB_PORT=5432
export TELEGRAM_TOKEN= TELEGRAM_CHAT_ID=
echo "DB_USER задан: $([ -n "$DB_USER" ] && echo да || echo НЕТ); DB_PASSWORD задан: $([ -n "$DB_PASSWORD" ] && echo да || echo НЕТ)  (значения не печатаются)"

psqlc() { docker exec -i trading_db psql -U trader -d forward_control -t -A -F'|' -v ON_ERROR_STOP=1; }

echo
echo "=== ЗАЩИТЫ ДО ==="
echo -n "  forward_runs.jsonl строк: "; wc -l < logs/forward_runs.jsonl
echo -n "  healthcheck_state mtime : "; date -r bot/data/forward_healthcheck_state.json '+%F %T'
echo -n "  боевой rules отпечаток  : "; git hash-object knowledge/rules/rules_osc_range.yaml

echo
echo "=== ПЕРЕСОЗДАНИЕ КЛОНА + СВЕРКА ОБЪЁМОВ ==="
docker exec -i trading_db psql -U trader -d postgres -q -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS forward_control;" \
  -c "CREATE DATABASE forward_control TEMPLATE trading_bot;" 2>&1 | tail -1
echo "  боевая:"
docker exec -i trading_db psql -U trader -d trading_bot -t -A -F'/' -c \
 "SELECT (SELECT count(*) FROM candles WHERE timeframe='1d'),(SELECT count(*) FROM forward_state),(SELECT count(*) FROM trades),(SELECT count(*) FROM skipped_signals);"
echo "  клон  :"
psqlc <<'SQL'
SELECT (SELECT count(*) FROM candles WHERE timeframe='1d')||'/'||(SELECT count(*) FROM forward_state)||'/'||(SELECT count(*) FROM trades)||'/'||(SELECT count(*) FROM skipped_signals);
SQL
echo "  ожидание из записи 30.07: 18182/20/7532/3"

prep() {   # усечь клон до целевой сессии
  {
    echo "DELETE FROM candles WHERE timeframe='1d' AND time > '$TARGET';"
    echo "UPDATE forward_state SET last_candle_time = '$PREV';"
    echo "DELETE FROM skipped_signals;"
    echo "DELETE FROM trades WHERE strategy_id LIKE '%_fwd';"
  } | psqlc > /dev/null
}

after() {
  psqlc <<'SQL'
SELECT 'skipped', count(*)::text FROM skipped_signals
UNION ALL SELECT 'last_close', COALESCE((SELECT details->>'last_close' FROM skipped_signals ORDER BY skipped_at DESC LIMIT 1),'—')
UNION ALL SELECT 'skip_reason', COALESCE((SELECT skip_reason FROM skipped_signals ORDER BY skipped_at DESC LIMIT 1),'—')
UNION ALL SELECT 'trades_fwd', count(*)::text FROM trades WHERE strategy_id LIKE '%_fwd'
UNION ALL SELECT 'entry', COALESCE((SELECT ticker||' @ '||entry_price::text FROM trades WHERE strategy_id LIKE '%_fwd' ORDER BY created_at DESC LIMIT 1),'—')
UNION ALL SELECT 'entry_rules', COALESCE((SELECT entry_reason FROM trades WHERE strategy_id LIKE '%_fwd' ORDER BY created_at DESC LIMIT 1),'—');
SQL
}

echo
echo "############ ПЛЕЧО 1: enabled: true (боевой файл, главное дерево) ############"
prep
DB_NAME=forward_control FWD_REPLAY=1 FWD_RUN_JOURNAL="$SP/g3_j1.jsonl" \
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
  .venv/Scripts/python.exe bot/run_forward_d1.py > "$SP/g3_arm_on.out" 2>&1
echo "  код возврата: $?"
after | sed 's/^/  /'
echo "  строки про SBER:"; grep -E 'SBER' "$SP/g3_arm_on.out" | grep -vE 'Бюджеты|Открытых' | head -3 | sed 's/^/    /'
echo -n "  rules_version прогона: "; grep -o -E 'rules_version[^ ]*|9f74487453fd0f85|db37689d5b9a6eab' "$SP/g3_arm_on.out" | head -1

echo
echo "############ ПЛЕЧО 2: enabled: false (отдельный worktree) ############"
rm -rf "$WT"
git worktree add --detach -q "$WT" HEAD 2>&1 | tail -1
python - "$WT" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]) / "knowledge" / "rules" / "rules_osc_range.yaml"
s = p.read_text(encoding="utf-8")
i = s.index("structural_downtrend:"); j = s.index("enabled: true", i)
p.write_text(s[:j] + "enabled: false" + s[j+len("enabled: true"):], encoding="utf-8")
print("  копия правил в worktree: фильтр выключен")
PY
echo -n "  боевой файл не тронут, отпечаток: "; git hash-object knowledge/rules/rules_osc_range.yaml
prep
DB_NAME=forward_control FWD_REPLAY=1 FWD_RUN_JOURNAL="$SP/g3_j2.jsonl" \
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
  "$PWD/.venv/Scripts/python.exe" "$WT/bot/run_forward_d1.py" > "$SP/g3_arm_off.out" 2>&1
echo "  код возврата: $?"
after | sed 's/^/  /'
echo "  строки про SBER:"; grep -E 'SBER' "$SP/g3_arm_off.out" | grep -vE 'Бюджеты|Открытых' | head -3 | sed 's/^/    /'

echo
echo "=== УБОРКА ==="
git worktree remove --force "$WT" 2>&1 | tail -1
rm -rf "$WT"
git worktree prune
echo "  worktree удалён: $([ -d "$WT" ] && echo '🚨 НЕТ' || echo да)"
docker exec -i trading_db psql -U trader -d postgres -q -c "DROP DATABASE IF EXISTS forward_control;" 2>&1 | tail -1
echo -n "  клонов осталось: "; docker exec -i trading_db psql -U trader -d postgres -t -A -c "SELECT count(*) FROM pg_database WHERE datname='forward_control';"
echo
echo "=== ЗАЩИТЫ ПОСЛЕ ==="
echo -n "  forward_runs.jsonl строк: "; wc -l < logs/forward_runs.jsonl
echo -n "  healthcheck_state mtime : "; date -r bot/data/forward_healthcheck_state.json '+%F %T'
echo -n "  боевой rules отпечаток  : "; git hash-object knowledge/rules/rules_osc_range.yaml
echo -n "  боевая БД skipped/trades: "; docker exec -i trading_db psql -U trader -d trading_bot -t -A -c "SELECT (SELECT count(*) FROM skipped_signals)||'/'||(SELECT count(*) FROM trades);"
echo "  git status рабочего дерева: $(git status --porcelain | wc -l) строк"
