# QuantFlow — Windows Server 2019 Deployment Guide

## Target Environment

- **OS**: Windows Server 2019 (Standard or Datacenter)
- **Architecture**: x64
- **Deployment model**: Services via NSSM (Non-Sucking Service Manager)
- **No Linux, no Ubuntu, no WSL required**

---

## Prerequisites

Install on Windows Server 2019:

### 1. Python 3.11
- Download from https://www.python.org/downloads/windows/
- Choose "Windows installer (64-bit)"
- During install: ✅ "Add Python to PATH"
- Verify: `python --version` in PowerShell

### 2. Git
- Download from https://git-scm.com/download/win
- Verify: `git --version`

### 3. Docker Desktop for Windows
- Download from https://www.docker.com/products/docker-desktop
- Requires WSL2 backend (install WSL2 first: `wsl --install`)
- Alternative: PostgreSQL directly on Windows (see below)

### 4. Node.js 20 LTS (if deploying website)
- Download from https://nodejs.org/en/download
- Verify: `node --version`

### 5. NSSM (service manager)
- Download from https://nssm.cc/download
- Extract to `C:\tools\nssm\` and add to PATH

---

## Deployment Steps

### Step 1: Clone the repository

Open PowerShell as Administrator:

```powershell
cd C:\Apps
git clone https://github.com/Pomiranov/Trading-Bot.git
cd Trading-Bot
git checkout merge-learning-nik
```

### Step 2: Configure environment

```powershell
Copy-Item .env.example .env
notepad .env    # fill in all required values
```

**Windows-specific `.env` notes:**
- Paths in `.env` use forward slashes or escaped backslashes
- `DB_HOST=localhost` — works as-is on Windows
- `LOG_LEVEL=INFO` — recommended for production

### Step 3: Install Python dependencies

```powershell
pip install -r requirements.txt
```

### Step 4: Start database

**Option A: Docker Desktop (recommended)**
```powershell
docker-compose up -d
```

**Option B: PostgreSQL native on Windows**
- Install PostgreSQL 15 from https://www.postgresql.org/download/windows/
- Create user `trader` and database `trading_bot`
- Update `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` in `.env`

### Step 5: Initialise database schema

```powershell
$env:PGPASSWORD="your_db_password"
psql -h localhost -U trader -d trading_bot -f quantflow_schema.sql
```

### Step 6: Test startup manually

```powershell
.\start.ps1
```

Verify:
- Dashboard responds at http://127.0.0.1:5001
- Bot connects to Telegram (check `logs\bot.log`)

---

## Windows Services with NSSM

Run as Windows Services so they restart automatically on reboot.

### Install Dashboard service

```powershell
nssm install QuantFlowDashboard
# In the NSSM GUI:
#   Path:            C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe
#   Startup dir:     C:\Apps\Trading-Bot
#   Arguments:       bot\ui\dashboard.py
#   Env variables:   add path to .env content or set in System Env
```

Or via command line:
```powershell
nssm install QuantFlowDashboard "python" "C:\Apps\Trading-Bot\bot\ui\dashboard.py"
nssm set QuantFlowDashboard AppDirectory "C:\Apps\Trading-Bot"
nssm set QuantFlowDashboard AppEnvironmentExtra "PYTHONPATH=C:\Apps\Trading-Bot"
nssm set QuantFlowDashboard AppStdout "C:\Apps\Trading-Bot\logs\dashboard.log"
nssm set QuantFlowDashboard AppStderr "C:\Apps\Trading-Bot\logs\dashboard.log"
nssm set QuantFlowDashboard Start SERVICE_AUTO_START
nssm start QuantFlowDashboard
```

### Install Bot service

```powershell
nssm install QuantFlowBot "python" "C:\Apps\Trading-Bot\bot\main.py"
nssm set QuantFlowBot AppDirectory "C:\Apps\Trading-Bot"
nssm set QuantFlowBot AppEnvironmentExtra "PYTHONPATH=C:\Apps\Trading-Bot"
nssm set QuantFlowBot AppStdout "C:\Apps\Trading-Bot\logs\bot.log"
nssm set QuantFlowBot AppStderr "C:\Apps\Trading-Bot\logs\bot.log"
nssm set QuantFlowBot Start SERVICE_AUTO_START
nssm start QuantFlowBot
```

### Service management commands

```powershell
nssm status QuantFlowDashboard
nssm status QuantFlowBot
nssm restart QuantFlowDashboard
nssm restart QuantFlowBot
nssm stop QuantFlowBot
nssm remove QuantFlowBot confirm
```

---

## Windows Firewall

Open required ports (run as Administrator):

```powershell
# Dashboard (internal only — do NOT expose to internet without reverse proxy)
New-NetFirewallRule -DisplayName "QuantFlow Dashboard" -Direction Inbound -Protocol TCP -LocalPort 5001 -Action Allow -Profile Private

# PostgreSQL (localhost only — already bound to 127.0.0.1 in docker-compose)
# No firewall rule needed if using Docker binding

# Website (if deployed locally)
New-NetFirewallRule -DisplayName "QuantFlow Website" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow -Profile Private
```

**Important**: Dashboard at port 5001 should only be accessible from trusted networks. Use a reverse proxy (IIS or nginx for Windows) if exposing externally.

---

## Environment Variables on Windows Server

Preferred: set via System Environment Variables (survives reboots):

```powershell
[System.Environment]::SetEnvironmentVariable("BOT_TOKEN", "your_token", "Machine")
[System.Environment]::SetEnvironmentVariable("TINKOFF_TOKEN", "your_token", "Machine")
[System.Environment]::SetEnvironmentVariable("DB_PASSWORD", "your_password", "Machine")
[System.Environment]::SetEnvironmentVariable("DASHBOARD_SECRET_KEY", "your_key", "Machine")
```

Or use `.env` file — `python-dotenv` loads it automatically.

---

## Updating the Deployment

```powershell
cd C:\Apps\Trading-Bot

# Stop services
nssm stop QuantFlowBot
nssm stop QuantFlowDashboard

# Pull latest code
git pull origin merge-learning-nik

# Update dependencies if requirements.txt changed
pip install -r requirements.txt

# Restart services
nssm start QuantFlowDashboard
nssm start QuantFlowBot
```

---

## Log Management

Logs are in `C:\Apps\Trading-Bot\logs\`:

```powershell
# View live bot log
Get-Content C:\Apps\Trading-Bot\logs\bot.log -Wait -Tail 50

# View dashboard log
Get-Content C:\Apps\Trading-Bot\logs\dashboard.log -Wait -Tail 50
```

Set up Windows Task Scheduler for log rotation:
```powershell
# Create a scheduled task to truncate logs weekly
$action = New-ScheduledTaskAction -Execute "powershell" -Argument "-Command `"Get-ChildItem C:\Apps\Trading-Bot\logs\*.log | Where-Object {`$_.Length -gt 50MB} | ForEach-Object { Clear-Content `$_.FullName }`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "03:00"
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "QuantFlowLogRotate" -RunLevel Highest
```

---

## Website Deployment (Next.js)

```powershell
cd C:\Apps\Trading-Bot\website
npm install
npm run build       # creates .next/ production build
npm start           # serves on port 3000
```

For production: use `npm start` behind IIS reverse proxy or serve as NSSM service:

```powershell
nssm install QuantFlowWebsite "node" "C:\Apps\Trading-Bot\website\node_modules\.bin\next"
nssm set QuantFlowWebsite AppParameters "start"
nssm set QuantFlowWebsite AppDirectory "C:\Apps\Trading-Bot\website"
nssm set QuantFlowWebsite Start SERVICE_AUTO_START
nssm start QuantFlowWebsite
```

---

## Quick Status Check (PowerShell)

```powershell
# Check all services
nssm status QuantFlowBot
nssm status QuantFlowDashboard

# Check database
docker ps | Select-String "trading"

# Test dashboard
Invoke-WebRequest -Uri "http://localhost:5001" -UseBasicParsing | Select-Object StatusCode
```
