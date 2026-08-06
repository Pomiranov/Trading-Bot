@echo off
setlocal EnableDelayedExpansion
title QuantFlow — Trading Platform

set "PROJECT_DIR=%~dp0"
set "LOG_DIR=%PROJECT_DIR%logs"
set "BOT_DIR=%PROJECT_DIR%bot"

echo.
echo ========================================
echo  QuantFlow — Professional Trading Bot
echo  Windows Server 2019 / Windows 10+
echo ========================================
echo.

:: ─── Создать директорию логов ─────────────────────────────────────────────
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: ─── 1. Проверить Docker Desktop ──────────────────────────────────────────
echo [1/4] Проверка Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
    echo   [WARN] Docker недоступен — база данных может быть уже запущена отдельно.
) else (
    echo   [OK] Docker доступен
    echo [2/4] Запуск TimescaleDB...
    docker-compose -f "%PROJECT_DIR%docker-compose.yml" up -d
    if errorlevel 1 (
        echo   [WARN] docker-compose вернул ошибку. Проверьте docker-compose.yml
    ) else (
        echo   [OK] База данных запущена
    )
    timeout /t 3 /nobreak >nul
)

:: ─── 2. Проверить Python ──────────────────────────────────────────────────
echo [3/4] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python не найден. Установите Python 3.11+ и добавьте в PATH.
    pause
    exit /b 1
)
echo   [OK] Python найден

:: ─── 3. Запустить Dashboard (фоновый процесс) ─────────────────────────────
echo [4/4] Запуск Dashboard...
start "QF-Dashboard" /B python "%BOT_DIR%\ui\dashboard.py" >> "%LOG_DIR%\dashboard.log" 2>&1
timeout /t 3 /nobreak >nul
echo   [OK] Dashboard запущен — http://127.0.0.1:5001
echo   [LOG] %LOG_DIR%\dashboard.log

:: ─── 4. Запустить Торговый бот ────────────────────────────────────────────
echo.
echo Запуск торгового бота (Ctrl+C для остановки)...
echo Логи: %LOG_DIR%\bot.log
echo.

python "%BOT_DIR%\main.py" 2>&1 | tee "%LOG_DIR%\bot.log"

echo.
echo QuantFlow остановлен.
pause
