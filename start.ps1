#Requires -Version 5.1
<#
.SYNOPSIS
    QuantFlow Trading Platform — Windows Server 2019 Startup Script
.DESCRIPTION
    Запускает Dashboard и торгового бота на Windows Server 2019.
    Использовать как: .\start.ps1
    Для NSSM-сервиса: nssm install QuantFlow "python" "C:\path\to\bot\main.py"
#>

param(
    [switch]$DashboardOnly,
    [switch]$BotOnly,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BOT_DIR     = Join-Path $PROJECT_DIR "bot"
$LOG_DIR     = Join-Path $PROJECT_DIR "logs"
$DASHBOARD_LOG = Join-Path $LOG_DIR "dashboard.log"
$BOT_LOG       = Join-Path $LOG_DIR "bot.log"
$DASHBOARD_PID_FILE = Join-Path $LOG_DIR "dashboard.pid"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " QuantFlow — Professional Trading Bot" -ForegroundColor Cyan
Write-Host " Windows Server 2019" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── Создать директорию логов ─────────────────────────────────────────────
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR | Out-Null }

# ─── Команда остановки ────────────────────────────────────────────────────
if ($Stop) {
    Write-Host "[STOP] Остановка QuantFlow процессов..." -ForegroundColor Yellow
    Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $_.MainModule.FileName -like "*python*"
    } | Stop-Process -Force
    if (Test-Path $DASHBOARD_PID_FILE) { Remove-Item $DASHBOARD_PID_FILE -Force }
    Write-Host "[OK] Процессы остановлены." -ForegroundColor Green
    exit 0
}

# ─── Проверить Python ─────────────────────────────────────────────────────
Write-Host "[1/4] Проверка Python..." -NoNewline
try {
    $pyVer = python --version 2>&1
    Write-Host " OK ($pyVer)" -ForegroundColor Green
} catch {
    Write-Host " ОШИБКА" -ForegroundColor Red
    Write-Host "Python 3.11+ не найден. Установите с python.org и добавьте в PATH." -ForegroundColor Red
    exit 1
}

# ─── Проверить Docker (опционально) ───────────────────────────────────────
Write-Host "[2/4] Проверка Docker Desktop..." -NoNewline
try {
    docker info 2>&1 | Out-Null
    Write-Host " OK" -ForegroundColor Green
    Write-Host "[3/4] Запуск TimescaleDB..." -NoNewline
    docker-compose -f "$PROJECT_DIR\docker-compose.yml" up -d 2>&1 | Out-Null
    Write-Host " OK" -ForegroundColor Green
    Start-Sleep -Seconds 3
} catch {
    Write-Host " ПРОПУЩЕНО (Docker недоступен — БД должна быть запущена отдельно)" -ForegroundColor Yellow
}

# ─── Запустить Dashboard ──────────────────────────────────────────────────
if (-not $BotOnly) {
    Write-Host "[4/4] Запуск Dashboard..." -NoNewline
    $dashProc = Start-Process -FilePath python `
        -ArgumentList "`"$BOT_DIR\ui\dashboard.py`"" `
        -RedirectStandardOutput $DASHBOARD_LOG `
        -RedirectStandardError $DASHBOARD_LOG `
        -WindowStyle Hidden `
        -PassThru
    $dashProc.Id | Out-File -FilePath $DASHBOARD_PID_FILE -Encoding UTF8
    Start-Sleep -Seconds 3
    if ($dashProc.HasExited) {
        Write-Host " ОШИБКА (смотри $DASHBOARD_LOG)" -ForegroundColor Red
        Get-Content $DASHBOARD_LOG -Tail 10
    } else {
        Write-Host " OK (PID=$($dashProc.Id))" -ForegroundColor Green
        Write-Host "   Dashboard: http://127.0.0.1:5001" -ForegroundColor Cyan
    }
}

if ($DashboardOnly) {
    Write-Host ""
    Write-Host "Dashboard запущен. Нажмите Enter для выхода (Dashboard продолжит работу)."
    Read-Host
    exit 0
}

# ─── Запустить Торговый бот ───────────────────────────────────────────────
Write-Host ""
Write-Host "Запуск торгового бота (Ctrl+C для остановки)..." -ForegroundColor White
Write-Host "Логи: $BOT_LOG" -ForegroundColor Gray
Write-Host ""

try {
    python "$BOT_DIR\main.py" 2>&1 | Tee-Object -FilePath $BOT_LOG
} finally {
    Write-Host ""
    Write-Host "QuantFlow остановлен." -ForegroundColor Yellow
}
