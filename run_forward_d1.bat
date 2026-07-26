@echo off
rem QuantFlow: daily forward run osc_range D1 (Task Scheduler, 00:15)
cd /d D:\Trading-Bot-Nik
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8

rem TimescaleDB may not be up yet: "restart: always" in docker-compose only
rem applies once the Docker daemon itself is running, and Docker Desktop
rem starts at user logon - which can be seconds before this task fires.
rem Bring the stack up explicitly and wait for the DB to accept connections.
docker compose up -d >> logs\forward_d1.log 2>&1

set /a TRIES=0
:waitdb
docker exec trading_db pg_isready -U trader -d trading_bot >nul 2>&1
if %ERRORLEVEL% EQU 0 goto dbready
set /a TRIES+=1
if %TRIES% GEQ 30 (
    echo [%DATE% %TIME%] DB not ready after 60s - run aborted >> logs\forward_d1.log
    exit /b 1
)
rem ping instead of timeout: timeout fails when stdin is redirected,
rem which is how Task Scheduler runs this.
ping -n 3 127.0.0.1 >nul
goto waitdb

:dbready
rem Script lives in bot\, not the repo root. Python puts the SCRIPT's
rem directory on sys.path[0], so "from config import ..." resolves while
rem cwd stays at the repo root and the log keeps its existing location.
rem venv interpreter, not C:\Python314: dependencies live in one place.
D:\Trading-Bot-Nik\.venv\Scripts\python.exe bot\run_forward_d1.py >> logs\forward_d1.log 2>&1
