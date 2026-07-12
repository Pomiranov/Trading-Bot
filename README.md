# QuantFlow

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1+-000000?style=flat-square&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-TimescaleDB-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=flat-square&logo=telegram&logoColor=white)

**Professional crypto & equities trading ecosystem for algorithmic trading, paper sandbox, and Telegram-native UX.**

[Features](#features) · [Architecture](#system-architecture) · [Tech Stack](#tech-stack) · [Installation](#installation) · [Roadmap](#roadmap)

</div>

---

QuantFlow combines a trading terminal, Telegram bot, Telegram Mini App, rules-based signal engine, and paper-trading sandbox into one synchronized platform.

Built around **MOEX** market data and **Tinkoff Invest API**, with optional **Bybit** broker integration and a unified platform layer for portfolio, signals, and backtests.

---

## Features

### Trading Dashboard

Professional terminal-style web UI with:

- Portfolio overview, allocation, and position tracking
- Live signals monitoring with filters
- Backtest analytics (equity curve, drawdown, trade journal)
- Settings & broker credential management
- Real-time updates via **SSE** (Server-Sent Events)
- Responsive layout with collapsible sidebar

**Views:** Dashboard · Portfolio · Signals · Backtest · Settings · **Quant Hunter** (Mini App)

### Telegram Bot

Full trading companion with inline keyboards and command handlers:

- Portfolio, balance, positions, orders, and operations history
- Signal lookup and manual trading flows
- Bot control (start / pause / resume / stop / status / logs)
- Push notifications (trades, signals, risk limits, API errors)
- Authorized users only (`TELEGRAM_ALLOWED_IDS`)

### Telegram Mini App — CRYPTONITE Quant Hunter

Web3-style gamification layer (`bot/ui/static/miniapp/`):

- **Quant hunting** — catch Common, Rare, Epic, and Legendary particles
- **Energy system** — limited hunts with timed regeneration
- **Levels & XP** — progression from Crypto Rookie to Crypto Legend
- **Daily missions** — catch targets, streaks, legendary hunts
- **Leaderboard & achievements**
- **Trade tab** — live balance, positions, and signals from platform API

> Embedded in the Dashboard inline, or opened standalone / via BotFather Web App URL.  
> See [`bot/ui/static/miniapp/BOTFATHER.md`](bot/ui/static/miniapp/BOTFATHER.md) for Telegram setup.

### Trading Sandbox (Paper Trading)

Virtual portfolio for risk-free simulation:

- Virtual balance and paper positions
- Trade history and equity snapshots
- Signal-driven paper execution
- Aggregated with broker data in platform overview

### Signal Engine

Rules-based engine (not ML) powered by:

- Technical indicators: RSI, MACD, EMA, ATR, Bollinger Bands, ADX, VWAP
- **12 YAML rules** in `knowledge/rules.yaml` with weighted scoring
- Hot-reloadable rule definitions
- MOEX ISS historical data loader

### Synchronization

**Dashboard ↔ Telegram Bot ↔ Trading Engine**

Events stay in sync across clients:

| Event | Channels |
|-------|----------|
| Signals | SSE · REST · Telegram |
| Positions | SSE · REST · Telegram |
| Orders & trades | SSE · REST · Telegram notifications |
| Balance / portfolio | SSE · REST · Telegram |
| Backtest results | SSE · REST |

---

## System Architecture

```
User
  │
  ├── Dashboard (Flask SPA)
  ├── Telegram Bot (python-telegram-bot)
  └── Mini App (Quant Hunter + Trade)
          │
          ▼
   Platform API (/api/platform/*)
          │
          ├── Trading Engine (main.py loop)
          ├── Signal Engine (indicators + rules)
          ├── Risk Manager (ATR stops, position limits)
          └── Broker Layer (Tinkoff · Bybit)
          │
          ▼
   Sandbox Portfolio (paper_accounts / paper_positions)
          │
          ▼
   PostgreSQL / TimescaleDB
          │
          ▼
   Analytics (backtest · statistics · dashboard metrics)
```

---

## Tech Stack

### Frontend

| | |
|---|---|
| **UI** | Vanilla JavaScript · Custom design system CSS |
| **Charts** | [Lightweight Charts](https://tradingview.github.io/lightweight-charts/) · [ECharts](https://echarts.apache.org/) |
| **State** | `QFStore` · `QFSync` · `SidebarProvider` · `QFRender` |
| **Fonts** | Inter · JetBrains Mono · Orbitron (Mini App) |
| **Template** | Flask + Jinja2 (`dashboard.html`) |

### Backend

| | |
|---|---|
| **Runtime** | Python 3.11+ |
| **Framework** | Flask ≥ 3.1 |
| **ORM / DB** | SQLAlchemy · psycopg2-binary |
| **Database** | PostgreSQL 15 · TimescaleDB (Docker) |
| **Telegram** | python-telegram-bot ≥ 20 |
| **Brokers** | tinkoff-investments SDK · Bybit client |
| **Analysis** | pandas · ta · PyYAML |
| **Security** | Encrypted credential vault · API key auth · audit logging |

### Infrastructure

| | |
|---|---|
| **Containers** | Docker Compose (TimescaleDB + Adminer) |
| **Real-time** | SSE (`/api/platform/stream`) |
| **Market data** | MOEX ISS REST API |
| **Process** | `start.sh` — DB + Dashboard + Trading bot |

---

## Project Structure

```
Trading-Bot-main/
├── bot/                          # Application source
│   ├── main.py                   # Trading loop + Telegram bot
│   ├── config.py                 # Environment configuration
│   ├── signals/                  # Indicators + rules engine
│   ├── risk/                     # Risk management
│   ├── broker/                   # Tinkoff, Bybit clients
│   ├── backtest/                 # Backtest engines
│   ├── data/                     # MOEX data loader
│   ├── qf_platform/              # Platform services (portfolio, paper, signals)
│   ├── realtime/                 # SSE hub
│   ├── tg/                       # Telegram bot handlers & notifications
│   ├── security/                 # Auth, encryption, middleware
│   └── ui/
│       ├── dashboard.py          # Flask app entry point
│       ├── api/                    # Platform REST routes
│       ├── templates/              # dashboard.html
│       └── static/               # Frontend + miniapp/
│           ├── core/               # api.js, store.js, sync.js, layout.js
│           ├── views/              # render.js
│           └── miniapp/            # Quant Hunter game + trade shell
├── knowledge/
│   └── rules.yaml                # Trading rules
├── tests/                        # Platform tests
├── docs/                         # Extended documentation
├── docker-compose.yml
├── requirements.txt
├── start.sh                      # One-command local startup
└── .env.example
```

---

## Installation

### Requirements

- Python **3.11+**
- Docker & Docker Compose
- `pip` / `venv`

### Quick Start

```bash
git clone https://github.com/YOUR_ORG/Trading-Bot-main.git
cd Trading-Bot-main

cp .env.example .env
# Edit .env — DB_PASSWORD, TELEGRAM_TOKEN, TINKOFF_TOKEN, etc.

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d

# All-in-one (DB + Dashboard + Bot)
./start.sh
```

### Run Components Separately

```bash
# Database
docker compose up -d

# Web dashboard → http://127.0.0.1:5001
python3 bot/ui/dashboard.py

# Trading engine + Telegram bot
python3 bot/main.py

# Bot only (no auto-trading loop)
python3 bot/main.py --bot-only

# Load MOEX historical candles
python3 bot/data/loader.py SBER GAZP LKOH --interval 1d --days 365
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DB_*` | PostgreSQL connection |
| `TINKOFF_TOKEN` / `TINKOFF_ACCOUNT_ID` | Tinkoff Invest API |
| `TINKOFF_SANDBOX` | `true` = sandbox, `false` = live trading |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram bot |
| `DASHBOARD_HOST` / `DASHBOARD_PORT` | Dashboard bind (default `127.0.0.1:5001`) |
| `DASHBOARD_API_KEY` | API key for protected endpoints |
| `TICKERS` | Watched tickers (e.g. `SBER,GAZP,LKOH`) |
| `RISK_*` | Position size, ATR stop, daily loss limits |

Full list: [`.env.example`](.env.example)

> **Safety:** Keep `TINKOFF_SANDBOX=true` until you intentionally switch to live trading.

---

## Screenshots

> Add screenshots to `docs/screenshots/` and uncomment the lines below.

<!-- 
| Dashboard | Portfolio |
|:---:|:---:|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Portfolio](docs/screenshots/portfolio.png) |

| Signals | Backtest |
|:---:|:---:|
| ![Signals](docs/screenshots/signals.png) | ![Backtest](docs/screenshots/backtest.png) |

| Quant Hunter Mini App |
|:---:|
| ![Mini App](docs/screenshots/miniapp.png) |
-->

_Placeholder — screenshots coming soon._

---

## Roadmap

### Completed

- ✅ Dashboard redesign (terminal UI, CSS Grid layout)
- ✅ Platform layer (portfolio, signals, backtest, paper trading)
- ✅ Dashboard ↔ Telegram synchronization (SSE + shared services)
- ✅ Trading sandbox (paper accounts & positions)
- ✅ CRYPTONITE Quant Hunter Mini App (levels, missions, leaderboard)
- ✅ Security hardening (credential vault, API key auth)

### Upcoming

- ⏳ Enhanced signal models & scoring
- ⏳ Additional exchange integrations (Finam, expanded Bybit)
- ⏳ Advanced portfolio analytics
- ⏳ New Mini App game features & cloud save
- ⏳ WebSocket live quotes (currently SSE-based)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-change`
3. Make focused changes with tests where applicable
4. Run tests: `python3 -m pytest tests/`
5. Open a Pull Request with a clear description

Bug reports and feature proposals are welcome via GitHub Issues.

For security-related findings, avoid public issues — contact maintainers directly.

---

## License

No `LICENSE` file is included in the repository yet.  
Previous documentation referenced **MIT** — add a `LICENSE` file to make terms explicit.

---

## Disclaimer

QuantFlow is for educational and research purposes. Algorithmic trading carries financial risk.  
Always test in sandbox mode. Authors are not responsible for trading losses.