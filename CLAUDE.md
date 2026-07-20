# QuantFlow Trading Bot — CLAUDE.md

## Project Root

**Canonical location**: `/Users/danila/Documents/GitHub/Trading-Bot/`  
**GitHub remote**: `https://github.com/Pomiranov/Trading-Bot.git`  
**Active branch**: `merge-learning-nik`

> All Claude Code edits MUST happen in this directory.  
> Never edit files in ~/Downloads/Trading-Bot-* (those are stale copies).

---

## Project Layout

```
Trading-Bot/
├── bot/                    — Core application (Python)
│   ├── main.py            — Unified entry point (Telegram bot + platform)
│   ├── config.py          — Centralised configuration via .env
│   ├── tg/                — Telegram bot (handlers, FSM, menus, middlewares, notifications)
│   ├── ui/                — Web dashboard (Flask) + Mini App + static assets
│   ├── qf_platform/       — Platform layer (repositories, services, DTOs, schema)
│   ├── learning/          — AI learning system (belief updater, hypothesis engine)
│   ├── backtest/          — Backtesting engine
│   ├── broker/            — Broker clients (Tinkoff, Bybit)
│   ├── services/          — High-level services (Tinkoff data, trading, stats)
│   ├── security/          — Auth, encryption, audit, credentials vault
│   ├── signals/           — Signal indicators + rules engine
│   ├── risk/              — Risk manager
│   ├── market/            — Market data hub
│   ├── engine/            — Paper trading engine
│   ├── realtime/          — SSE real-time hub
│   ├── auth/              — JWT, sessions, brute-force protection
│   ├── gateway/           — Trade gateway
│   └── data/              — Data loaders
├── website/               — Next.js marketing website (TypeScript)
├── knowledge/             — Trading knowledge base (rules.yaml, market theory)
├── tests/                 — Test suite (platform + security)
├── docs/                  — Project documentation
├── infra/                 — Infrastructure configs (logrotate, etc.)
├── data/                  — Shared data files
├── logs/                  — Runtime logs (git-ignored)
├── docker-compose.yml     — TimescaleDB (TimescaleDB/pg15) + Adminer
├── requirements.txt       — Python dependencies
├── start.sh               — macOS startup script
├── start.ps1              — Windows PowerShell startup script
├── start.bat              — Windows batch startup
├── .env                   — Secrets (git-ignored — copy from .env.example)
└── .env.example           — Environment variable template
```

---

## Key Entry Points

| Component | File | Port |
|---|---|---|
| Trading Bot + Telegram | `bot/main.py` | — |
| Dashboard (Flask) | `bot/ui/dashboard.py` | 5001 |
| Mini App (HTML) | `bot/ui/static/miniapp/index.html` | (served via dashboard) |
| Website (Next.js) | `website/` | 3000 (dev) |
| Database (TimescaleDB) | `docker-compose.yml` | 5432 |
| Adminer (DB UI) | `docker-compose.yml` | 8080 |

---

## Development Commands

```bash
# Start everything (macOS)
./start.sh

# Start database only
docker-compose up -d

# Start dashboard only
python3 bot/ui/dashboard.py

# Start bot only
python3 bot/main.py

# Run tests
python3 -m pytest tests/

# Website (Next.js dev)
cd website && npm run dev
```

---

## Environment Setup

Copy `.env.example` → `.env` and fill in:
- `DB_PASSWORD` — PostgreSQL password
- `BOT_TOKEN` — Telegram bot token
- `TINKOFF_TOKEN` — T-Invest API token
- `DASHBOARD_SECRET_KEY` — Flask secret key
- `BYBIT_API_KEY` / `BYBIT_API_SECRET` — Bybit credentials (optional)

---

## Git Workflow

```
Edit code here
  ↓
git add <files>
  ↓
git commit -m "description"
  ↓
git push origin merge-learning-nik
  ↓
GitHub (Pomiranov/Trading-Bot, branch: merge-learning-nik)
  ↓
Deploy to Windows Server 2019
```

**Branch strategy**:
- `merge-learning-nik` — main development branch (use this)
- `main` — stable releases only
- `quantflow-nik` — archived (predecessor to merge-learning-nik)

---

## Windows Server 2019 Deployment

Use `start.ps1` (PowerShell) or `start.bat`.  
See `docs/windows-deployment.md` for full instructions.

Services run as Windows Services via NSSM.

---

## Important Notes

- **Secrets**: Never commit `.env`, `Password.env`, or credential vault files
- **Broker mode**: `TINKOFF_SANDBOX=true` by default — set to `false` for live trading
- **Database**: TimescaleDB (PostgreSQL + time-series extension) on port 5432
- **No Redis**: Not currently used; session data via PostgreSQL
- **Dashboard auth**: JWT-based; credentials stored in `bot/data/credential_vault.json` (git-ignored)
