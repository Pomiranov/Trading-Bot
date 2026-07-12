#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "=== QuantFlow — запуск ==="
echo "Проект: $PROJECT_DIR"

# ─── 1. Останавливаем старые процессы ─────────────────────────────────────
echo ""
echo "[1/4] Остановка старых процессов..."
pkill -9 -f "Python.*main.py" 2>/dev/null && echo "  ✓ Старые main.py остановлены" || true
pkill -9 -f "Python.*dashboard.py" 2>/dev/null && echo "  ✓ Старый dashboard.py остановлен" || true
rm -f "$PROJECT_DIR/.bot.pid" "$PROJECT_DIR/bot/.bot.pid"
sleep 2

# ─── 2. База данных ───────────────────────────────────────────────────────
echo ""
echo "[2/4] Запуск базы данных..."
cd "$PROJECT_DIR"
docker-compose up -d 2>&1 | grep -E "Starting|Running|healthy|error" || true
sleep 2

# ─── 3. Dashboard ─────────────────────────────────────────────────────────
echo ""
echo "[3/4] Запуск Dashboard..."
cd "$PROJECT_DIR"
nohup python3 bot/ui/dashboard.py > "$LOG_DIR/dashboard.log" 2>&1 &
DASH_PID=$!
sleep 3
if kill -0 $DASH_PID 2>/dev/null; then
    echo "  ✓ Dashboard запущен  PID=$DASH_PID  http://127.0.0.1:${DASHBOARD_PORT:-5001}"
    echo $DASH_PID > "$LOG_DIR/dashboard.pid"
else
    echo "  ✗ Dashboard не запустился — смотри logs/dashboard.log"
    cat "$LOG_DIR/dashboard.log" | tail -5
fi

# ─── 4. Торговый бот (включает Telegram) ──────────────────────────────────
echo ""
echo "[4/4] Запуск торгового бота..."
echo "  Логи: logs/bot.log"
echo "  Остановить: pkill -f bot/main.py"
echo ""

cd "$PROJECT_DIR"
exec python3 bot/main.py 2>&1 | tee "$LOG_DIR/bot.log"
