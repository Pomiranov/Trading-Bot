# QuantFlow — Local Development Guide

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| pip | latest | `pip3 --version` |
| Docker Desktop | latest | `docker --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | 2.x | `git --version` |

---

## First-Time Setup

### 1. Clone the repository

```bash
cd ~/Documents/GitHub
git clone https://github.com/Pomiranov/Trading-Bot.git
cd Trading-Bot
git checkout merge-learning-nik
```

### 2. Create `.env`

```bash
cp .env.example .env
# Edit .env and fill in all required values
```

Required values:
- `DB_PASSWORD` — choose a strong password for PostgreSQL
- `BOT_TOKEN` — from @BotFather on Telegram
- `TINKOFF_TOKEN` — from Tinkoff Invest API (tinkoff.ru/invest/open-api)
- `DASHBOARD_SECRET_KEY` — any random string (e.g. `openssl rand -hex 32`)

### 3. Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Start the database

```bash
docker-compose up -d
# Wait ~10 seconds for PostgreSQL to initialise
docker exec trading_db pg_isready   # should print: /var/run/postgresql:5432 - accepting connections
```

### 5. Initialise the database schema

```bash
PGPASSWORD="your_db_password" psql -h localhost -U trader -d trading_bot -f quantflow_schema.sql
```

### 6. Start everything

```bash
./start.sh
```

This starts:
- Dashboard at http://127.0.0.1:5001
- Telegram Bot (connected to your BOT_TOKEN)

---

## Running Individual Components

```bash
# Dashboard only
python3 bot/ui/dashboard.py

# Bot only (includes Telegram polling)
python3 bot/main.py

# Website (Next.js dev server)
cd website
npm install          # first time only
npm run dev          # http://localhost:3000

# Database UI (Adminer)
# Open http://localhost:8080
# Server: timescaledb, User: trader, Password: <DB_PASSWORD>, DB: trading_bot
```

---

## Running Tests

```bash
# All tests
python3 -m pytest tests/ -v

# Platform tests only
python3 -m pytest tests/platform_tests/ -v

# Security tests only
python3 -m pytest tests/security_tests/ -v
```

---

## Validation

Run before every commit:

```bash
./scripts/validate.sh
```

---

## Stopping Everything

```bash
# Stop bot and dashboard
pkill -f "python3 bot/main.py" 2>/dev/null || true
pkill -f "python3 bot/ui/dashboard.py" 2>/dev/null || true

# Stop database
docker-compose down
```

---

## Useful URLs (local)

| Service | URL |
|---|---|
| Dashboard | http://127.0.0.1:5001 |
| Adminer (DB UI) | http://127.0.0.1:8080 |
| Website (dev) | http://localhost:3000 |

---

## Environment Variable Reference

```bash
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=trading_bot
DB_USER=trader
DB_PASSWORD=<your_password>

# Tinkoff Invest
TINKOFF_TOKEN=<your_token>
TINKOFF_ACCOUNT_ID=<your_account_id>
TINKOFF_SANDBOX=true          # true = sandbox, false = live

# Bybit (optional)
BYBIT_API_KEY=<key>
BYBIT_API_SECRET=<secret>
BYBIT_TESTNET=false

# Telegram
BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>

# Dashboard
DASHBOARD_SECRET_KEY=<random_hex_string>
DASHBOARD_PORT=5001           # optional, default 5001

# Trading
TICKERS=SBER,GAZP,LKOH,NVTK
POLL_INTERVAL=60

# Risk
RISK_MAX_POSITION_PCT=0.05
RISK_ATR_STOP_MULT=2.0
RISK_MAX_DAILY_LOSS_PCT=0.02
RISK_MAX_OPEN_POSITIONS=5

# Logging
LOG_LEVEL=INFO
```

---

## Troubleshooting

**Dashboard won't start**  
→ Check `logs/dashboard.log`  
→ Ensure `.env` has all required variables  
→ Ensure `docker-compose up -d` ran successfully

**Bot won't connect to Telegram**  
→ Verify `BOT_TOKEN` in `.env`  
→ Check `logs/bot.log` for errors  
→ Ensure you can reach `api.telegram.org` (no firewall)

**Database connection refused**  
→ Run `docker ps` — `trading_db` must be in status `Up`  
→ Run `docker-compose up -d` if not running

**Tinkoff API errors (30052)**  
→ This is a sandbox limitation for certain tickers — normal behaviour  
→ Set `TINKOFF_SANDBOX=false` only when ready for live trading

**`Module not found` errors**  
→ Run `pip3 install -r requirements.txt`  
→ Make sure you're running from the project root, not from `bot/`
