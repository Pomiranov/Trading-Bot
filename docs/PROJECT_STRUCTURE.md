# QuantFlow — Project Structure

## Directory Map

```
Trading-Bot/                         ← Git root & project root (ONE location)
│
├── bot/                             ← Core Python application
│   ├── main.py                      ← Unified entry point (bot + platform)
│   ├── config.py                    ← Config loader (reads .env)
│   ├── reliability.py               ← Health-check helpers
│   │
│   ├── tg/                          ← Telegram Bot layer
│   │   ├── bot.py                   ← Bot application setup & dispatcher
│   │   ├── handlers/                ← Command handlers (start, portfolio, signals…)
│   │   ├── fsm/                     ← FSM states (aiogram FSM)
│   │   ├── menus/                   ← Inline keyboard builders
│   │   ├── middlewares/             ← Auth, rate-limit, error handling
│   │   ├── notifications/           ← Push notification dispatcher
│   │   └── formatters/              ← Message formatters (numbers, text)
│   │
│   ├── ui/                          ← Web Dashboard (Flask)
│   │   ├── dashboard.py             ← Flask app entry point (port 5001)
│   │   ├── telegram_bot.py          ← Telegram integration for dashboard
│   │   ├── api/                     ← REST API routes (/api/*)
│   │   ├── templates/               ← Jinja2 HTML templates
│   │   └── static/                  ← Frontend assets
│   │       ├── app.js               ← Main JS application
│   │       ├── charts.js            ← Chart rendering
│   │       ├── style.css            ← Main stylesheet
│   │       ├── design-system.css    ← Design tokens
│   │       ├── core/                ← Core modules (api, store, format, layout)
│   │       ├── views/               ← View renderers
│   │       └── miniapp/             ← Telegram Mini App
│   │           ├── index.html       ← Mini App entry
│   │           ├── miniapp.js       ← Mini App logic
│   │           └── miniapp.css      ← Mini App styles
│   │
│   ├── qf_platform/                 ← Platform core (DB access, business logic)
│   │   ├── bootstrap.py             ← App bootstrap / DI wiring
│   │   ├── schema.py                ← DB schema definitions
│   │   ├── dto.py                   ← Data transfer objects
│   │   ├── repositories/            ← DB repositories (signals, paper, backtest…)
│   │   └── services/                ← Business services (analytics, portfolio…)
│   │
│   ├── learning/                    ← AI Learning System
│   │   ├── trading_orchestrator.py  ← Orchestrates learning loop
│   │   ├── hypothesis_engine.py     ← Generates & tests hypotheses
│   │   ├── belief_updater.py        ← Updates beliefs from trade outcomes
│   │   ├── decision_evaluator.py    ← Evaluates past decisions
│   │   ├── feedback.py              ← Feedback ingestion
│   │   └── memory_writer.py         ← Persists learning to DB
│   │
│   ├── backtest/                    ← Backtesting Engine
│   │   ├── engine.py                ← Core backtest engine
│   │   ├── advanced_engine.py       ← Extended engine with more metrics
│   │   └── run_*.py                 ← Backtest runner scripts
│   │
│   ├── broker/                      ← Broker Abstraction Layer
│   │   ├── base.py                  ← Abstract broker interface
│   │   ├── tinkoff_client.py        ← Tinkoff Invest API client
│   │   ├── bybit_client.py          ← Bybit API client
│   │   └── providers/               ← Additional providers (Finam, Tinkoff alt)
│   │
│   ├── services/                    ← Application Services
│   │   ├── bot_engine.py            ← Trading bot engine service
│   │   ├── broker_service.py        ← Broker abstraction service
│   │   ├── trading_service.py       ← Trade execution service
│   │   ├── paper_auto_engine.py     ← Paper trading automation
│   │   ├── statistics_service.py    ← Statistics aggregation
│   │   ├── user_store.py            ← User data persistence
│   │   └── tinkoff/                 ← Tinkoff-specific services
│   │
│   ├── security/                    ← Security Module
│   │   ├── bootstrap.py             ← Security initialization
│   │   ├── dashboard_auth.py        ← Dashboard JWT auth
│   │   ├── credential_vault.py      ← Encrypted credential storage
│   │   ├── encryption.py            ← AES encryption helpers
│   │   ├── audit.py                 ← Security audit logger
│   │   ├── http_middleware.py       ← HTTP security headers
│   │   └── secrets.py               ← Secret management
│   │
│   ├── signals/                     ← Signal Engine
│   │   ├── indicators.py            ← Technical indicators (RSI, ATR, MA…)
│   │   └── rules_engine.py          ← Rule-based signal evaluation
│   │
│   ├── risk/
│   │   └── risk_manager.py          ← Position sizing, stop-loss, daily limits
│   │
│   ├── market/
│   │   └── data_hub.py              ← Market data aggregator
│   │
│   ├── engine/
│   │   └── paper_engine.py          ← Paper trading simulator
│   │
│   ├── realtime/
│   │   └── sse_hub.py               ← Server-Sent Events hub (live dashboard)
│   │
│   ├── gateway/
│   │   └── trade_gateway.py         ← Unified trade execution gateway
│   │
│   ├── auth/                        ← Authentication
│   │   ├── jwt_service.py           ← JWT token management
│   │   ├── session_manager.py       ← Session lifecycle
│   │   ├── brute_force.py           ← Brute-force protection
│   │   └── redis_client.py          ← Redis client (for session store)
│   │
│   └── data/                        ← Runtime data (git-ignored)
│       ├── user_prefs.json          ← User preferences (per-user settings)
│       └── credential_vault.json    ← Encrypted broker credentials
│
├── website/                         ← Next.js Marketing Website
│   ├── src/
│   │   ├── app/[locale]/            ← Next.js app router (i18n: ru/en)
│   │   ├── components/              ← React components
│   │   │   ├── sections/            ← Page sections (hero, dashboard-preview…)
│   │   │   ├── scene/               ← Three.js 3D belief-network visualization
│   │   │   ├── motion/              ← Animation components (Lenis scroll)
│   │   │   └── ui/                  ← Shared UI primitives
│   │   ├── content-layer/           ← MDX content source definitions
│   │   ├── lib/                     ← Utilities, i18n, analytics, fonts
│   │   └── styles/tokens/           ← Design tokens (color, spacing, motion…)
│   ├── content/                     ← MDX content files (ru/en)
│   ├── messages/                    ← i18n translation files
│   ├── public/                      ← Static assets (fonts, images, og)
│   ├── package.json
│   └── next.config.ts
│
├── knowledge/                       ← Trading Knowledge Base
│   ├── rules.yaml                   ← Active trading rules
│   ├── rules/                       ← Rule sets (oscillators, WRD, MOEX)
│   ├── processed/                   ← Processed market theory (Schwager etc.)
│   │   ├── market_theory/
│   │   ├── strategies/
│   │   ├── technical/
│   │   └── risk/
│   ├── theory/                      ← Trading theory (nik_theory.md)
│   └── raw/                         ← Raw source material for processing
│
├── tests/                           ← Test Suite
│   ├── platform_tests/              ← Platform integration tests
│   └── security_tests/              ← Security tests (phase 0 & 1)
│
├── docs/                            ← Documentation
│   ├── PROJECT_STRUCTURE.md         ← This file
│   ├── PROJECT_ARCHITECTURE.md      ← System architecture
│   ├── LOCAL_DEVELOPMENT.md         ← Local dev setup guide
│   ├── WINDOWS_DEPLOYMENT.md        ← Windows Server 2019 deployment
│   ├── GIT_WORKFLOW.md              ← Git branching & workflow
│   └── security/                    ← Security audit reports
│
├── infra/                           ← Infrastructure Configs
│   └── logrotate/
│       └── quantflow.conf           ← Log rotation config (Linux/WSL)
│
├── data/                            ← Shared data files
│   └── tinkoff_loader.py            ← Historical data loader script
│
├── scripts/                         ← Dev utility scripts
│   └── validate.sh                  ← Pre-deploy validation
│
├── logs/                            ← Runtime logs (git-ignored)
│   ├── bot.log
│   └── dashboard.log
│
├── Projects/trading-bot/            ← Legacy (DB docker-compose only)
│   └── docker-compose.yml           ← Kept for historical reference
│
├── docker-compose.yml               ← TimescaleDB + Adminer
├── requirements.txt                 ← Python dependencies
├── quantflow_schema.sql             ← Database schema SQL
├── start.sh                         ← macOS/Linux startup script
├── start.ps1                        ← Windows PowerShell startup
├── start.bat                        ← Windows batch startup
├── run_forward_d1.bat               ← Windows: run forward test
├── CLAUDE.md                        ← Claude Code configuration
├── .env                             ← Secrets (git-ignored)
├── .env.example                     ← Secret template
├── .gitignore
└── README.md
```

## Component Ownership

| Component | Technology | Purpose |
|---|---|---|
| Telegram Bot | Python, aiogram | User interface via Telegram |
| Dashboard | Python, Flask, vanilla JS | Web monitoring UI |
| Mini App | HTML/CSS/JS | Telegram Mini App embedded UI |
| Trading Engine | Python | Signal generation, order execution |
| Learning System | Python | AI hypothesis testing & belief updates |
| Backtest Engine | Python, pandas | Strategy backtesting |
| Database | TimescaleDB (PostgreSQL) | Time-series trade & signal storage |
| Website | Next.js, TypeScript, Three.js | Public marketing site |
| Knowledge Base | YAML, Markdown | Trading rules & theory |
