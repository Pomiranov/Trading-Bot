# QuantFlow — Деплой на Windows Server 2019

## Быстрый старт

```bat
REM Запуск всего (Docker + Dashboard + Bot)
start.bat

REM Или через PowerShell с дополнительными опциями
.\start.ps1                   # Полный запуск
.\start.ps1 -DashboardOnly    # Только Dashboard
.\start.ps1 -BotOnly          # Только бот
.\start.ps1 -Stop             # Остановить всё
```

## Установка зависимостей

```bat
REM 1. Python 3.11+  (python.org)
REM 2. Docker Desktop for Windows (docker.com)
REM 3. Зависимости Python
pip install -r requirements.txt
```

## Настройка .env

Скопировать `.env.example` в `.env` и заполнить:

```env
DB_PASSWORD=strong_password_here
TINKOFF_TOKEN=t.xxxxxxxx
TINKOFF_ACCOUNT_ID=xxxxxxxxxx
TELEGRAM_TOKEN=xxxx:yyyy
TELEGRAM_CHAT_ID=123456789
DASHBOARD_API_KEY=your_secure_random_key_32chars
DASHBOARD_REQUIRE_API_KEY=true   # true для production!
SECRETS_MASTER_KEY=              # 64-hex символа для шифрования токенов
```

Генерация SECRETS_MASTER_KEY:
```powershell
[System.BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).Replace("-","").ToLower()
```

## Автозапуск через NSSM (Windows Service)

NSSM — Non-Sucking Service Manager. Скачать: nssm.cc

### Dashboard как Windows Service

```bat
nssm install QuantFlow-Dashboard "C:\Python311\python.exe"
nssm set QuantFlow-Dashboard AppParameters "C:\QuantFlow\bot\ui\dashboard.py"
nssm set QuantFlow-Dashboard AppDirectory "C:\QuantFlow"
nssm set QuantFlow-Dashboard AppStdout "C:\QuantFlow\logs\dashboard.log"
nssm set QuantFlow-Dashboard AppStderr "C:\QuantFlow\logs\dashboard.log"
nssm set QuantFlow-Dashboard AppRotateFiles 1
nssm set QuantFlow-Dashboard AppRotateBytes 10485760
nssm set QuantFlow-Dashboard Start SERVICE_AUTO_START
nssm start QuantFlow-Dashboard
```

### Торговый бот как Windows Service

```bat
nssm install QuantFlow-Bot "C:\Python311\python.exe"
nssm set QuantFlow-Bot AppParameters "C:\QuantFlow\bot\main.py"
nssm set QuantFlow-Bot AppDirectory "C:\QuantFlow"
nssm set QuantFlow-Bot AppStdout "C:\QuantFlow\logs\bot.log"
nssm set QuantFlow-Bot AppStderr "C:\QuantFlow\logs\bot.log"
nssm set QuantFlow-Bot AppRotateFiles 1
nssm set QuantFlow-Bot AppRotateBytes 10485760
nssm set QuantFlow-Bot Start SERVICE_AUTO_START
nssm start QuantFlow-Bot
```

### Управление сервисами

```bat
nssm start QuantFlow-Dashboard
nssm stop QuantFlow-Dashboard
nssm restart QuantFlow-Bot
nssm status QuantFlow-Bot
```

## Docker (TimescaleDB)

Docker Compose запускает только базу данных:

```bat
docker-compose up -d         REM запуск
docker-compose down          REM остановка
docker-compose logs -f       REM логи
```

БД слушает на `127.0.0.1:5432` (только localhost).

## Доступ к Dashboard

- **Dashboard**: http://127.0.0.1:5001
- **Adminer** (DB UI): http://127.0.0.1:8080
- **Health check**: http://127.0.0.1:5001/health

Для доступа извне настройте nginx/IIS как reverse proxy.

## Firewall (Windows Defender Firewall)

Если нужен внешний доступ к Dashboard (через nginx):

```powershell
# Открыть порт 5001 только для localhost (безопасно)
# Для nginx — открыть 80/443, порт 5001 оставить закрытым
New-NetFirewallRule -DisplayName "QuantFlow Dashboard" -Direction Inbound -Protocol TCP -LocalPort 5001 -Action Allow -RemoteAddress 127.0.0.1
```

## Logrotate (Windows)

Используйте NSSM `AppRotateFiles` (уже настроено выше) или планировщик задач:

```powershell
# Ежедневная ротация логов через Task Scheduler
$action = New-ScheduledTaskAction -Execute "powershell" -Argument "-Command `"Get-ChildItem C:\QuantFlow\logs\*.log | Where Length -gt 10MB | Remove-Item -Force`""
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
Register-ScheduledTask -TaskName "QuantFlow-LogRotate" -Action $action -Trigger $trigger
```

## Переменные окружения для Production

```env
QF_HTTPS=1                        # Включить HSTS (если есть SSL)
DASHBOARD_HOST=127.0.0.1          # НЕ 0.0.0.0 без reverse proxy
DASHBOARD_REQUIRE_API_KEY=true    # Обязательно для production
DASHBOARD_API_KEY=<random_32>     # Сильный случайный ключ
LOG_LEVEL=INFO                    # DEBUG только при отладке
QF_DASHBOARD_DEBUG=0              # Никогда не 1 в production!
TINKOFF_SANDBOX=false             # false = боевой режим (осторожно!)
```

## Проверка здоровья

```powershell
# Health check
Invoke-RestMethod http://127.0.0.1:5001/health
Invoke-RestMethod http://127.0.0.1:5001/api/platform/health

# Проверить PID Dashboard
Get-Content logs\dashboard.pid | ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }
```
