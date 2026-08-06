# QuantFlow — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                             │
│                                                                     │
│   Telegram App          Web Browser          Marketing Website      │
│       │                     │                      │                │
│   Telegram Bot          Dashboard               Next.js             │
│   (bot/tg/)           (bot/ui/)              (website/)             │
└────────────┬────────────────┬──────────────────────────────────────┘
             │                │
             └────────┬───────┘
                      │
┌─────────────────────▼───────────────────────────────────────────────┐
│                     APPLICATION CORE (bot/)                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Trading      │  │ Learning     │  │ Security                 │  │
│  │ Engine       │  │ System       │  │ (auth, encryption,       │  │
│  │              │  │              │  │  vault, audit)           │  │
│  │ • Signals    │  │ • Hypotheses │  │                          │  │
│  │ • Rules      │  │ • Beliefs    │  └──────────────────────────┘  │
│  │ • Risk       │  │ • Feedback   │                                 │
│  │ • Gateway    │  │ • Memory     │  ┌──────────────────────────┐  │
│  └──────┬───────┘  └──────┬───────┘  │ QF Platform              │  │
│         │                 │          │ (repositories, services, │  │
│  ┌──────▼───────┐         │          │  DTOs, schema)           │  │
│  │ Broker Layer │         │          └──────────────────────────┘  │
│  │              │         │                                         │
│  │ • Tinkoff    │         │          ┌──────────────────────────┐  │
│  │ • Bybit      │         │          │ Backtest Engine          │  │
│  │ • Paper      │         │          └──────────────────────────┘  │
│  └──────┬───────┘         │                                         │
└─────────┼─────────────────┼─────────────────────────────────────────┘
          │                 │
┌─────────▼─────────────────▼─────────────────────────────────────────┐
│                        DATA LAYER                                   │
│                                                                     │
│   TimescaleDB (PostgreSQL + time-series)       Redis (optional)     │
│   • signals          • paper trades                                 │
│   • events           • backtest results                             │
│   • portfolios       • learning memory                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Signal → Trade

```
Market Data (Tinkoff API / Bybit)
    │
    ▼
Market Data Hub (bot/market/data_hub.py)
    │
    ▼
Signal Engine (bot/signals/)
    ├── indicators.py   — RSI, ATR, MA, volume indicators
    └── rules_engine.py — evaluate rules from knowledge/rules.yaml
    │
    ▼
Risk Manager (bot/risk/risk_manager.py)
    ├── position sizing (ATR-based)
    ├── stop-loss calculation
    ├── daily loss limit check
    └── max open positions check
    │
    ▼
[SIGNAL APPROVED]
    │
    ▼
Trade Gateway (bot/gateway/trade_gateway.py)
    ├── Paper mode → Paper Engine (bot/engine/paper_engine.py)
    └── Live mode  → Broker Client (Tinkoff / Bybit)
    │
    ▼
Event logged to TimescaleDB
    │
    ▼
Learning System (bot/learning/)
    ├── memory_writer.py   — store trade outcome
    ├── belief_updater.py  — update strategy confidence
    └── decision_evaluator.py — score past decisions
    │
    ▼
Telegram notification (bot/tg/notifications/dispatcher.py)
Dashboard SSE update (bot/realtime/sse_hub.py)
```

---

## Data Flow: User → Telegram Bot

```
User sends Telegram message
    │
    ▼
aiogram Dispatcher (bot/tg/bot.py)
    │
    ├── Middleware: Auth check (bot/tg/middlewares/auth.py)
    ├── Middleware: Rate limit (bot/tg/middlewares/rate_limit.py)
    │
    ▼
Handler (bot/tg/handlers/<command>.py)
    │
    ├── Reads data via QF Platform Services
    │   (bot/qf_platform/services/)
    │   └── Services use Repositories
    │       (bot/qf_platform/repositories/)
    │       └── Repositories query TimescaleDB
    │
    └── Returns formatted message (bot/tg/formatters/)
```

---

## Data Flow: Dashboard

```
Browser → GET http://localhost:5001
    │
    ▼
Flask App (bot/ui/dashboard.py)
    ├── Auth: JWT cookie check (bot/security/dashboard_auth.py)
    ├── Static: HTML/CSS/JS (bot/ui/static/)
    └── API: REST endpoints (bot/ui/api/platform_routes.py)
                │
                ▼
        QF Platform Services
                │
                ▼
        TimescaleDB
        
Browser → EventSource http://localhost:5001/stream
    │
    ▼
SSE Hub (bot/realtime/sse_hub.py) — real-time price & signal updates
```

---

## Learning System Architecture

```
Trade executed
    │
    ▼
memory_writer.py → stores: signal, context, outcome
    │
    ▼ (background, daily)
decision_evaluator.py → scores past decisions
    │
    ▼
belief_updater.py → updates confidence for each strategy/rule
    │
    ▼
hypothesis_engine.py → generates new rule hypotheses
    │
    ▼
rules_engine.py → tests hypotheses in backtest
    │
    ▼
feedback.py → applies validated hypotheses to knowledge/rules.yaml
```

---

## Security Architecture

```
Request enters (Telegram or HTTP)
    │
    ▼
Authentication
    ├── Telegram: user whitelist + JWT (bot/auth/)
    └── Dashboard: JWT cookie (bot/security/dashboard_auth.py)
    │
    ▼
Authorization (role check)
    │
    ▼
Rate limiting (bot/tg/middlewares/rate_limit.py)
    │
    ▼
Input validation (bot/security/config_validation.py)
    │
    ▼
Business logic
    │
    ▼
Audit log (bot/security/audit.py)
```

Sensitive credentials (API keys) stored in:
- `bot/data/credential_vault.json` — AES-256 encrypted at rest
- `.env` — loaded at startup, never committed to git

---

## Infrastructure

```
Docker (local/server)
    ├── trading_db   — TimescaleDB/pg15 (port 5432, bound to 127.0.0.1)
    └── trading_adminer — Adminer web DB UI (port 8080, bound to 127.0.0.1)

Processes (as NSSM services on Windows)
    ├── QuantFlowBot          — python bot/main.py
    ├── QuantFlowDashboard    — python bot/ui/dashboard.py
    └── QuantFlowWebsite      — node (website, optional)
```

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Bot framework | aiogram | 3.x |
| Dashboard | Flask | 3.1+ |
| Database | TimescaleDB (PostgreSQL) | 15 |
| ORM / DB driver | SQLAlchemy + asyncpg + psycopg2 | 2.x |
| HTTP client | httpx | 0.27+ |
| Data processing | pandas | 2.x |
| Technical indicators | ta (pandas-ta) | 0.11+ |
| Encryption | cryptography (AES-256) | 42+ |
| Website | Next.js | 15 |
| Website language | TypeScript | 5 |
| 3D visualization | Three.js / @react-three/fiber | latest |
| Animation | Framer Motion / Lenis | latest |
| Broker API (stocks) | tinkoff-investments SDK | 0.2.x |
| Broker API (crypto) | Bybit REST API | v5 |
| Service manager (Windows) | NSSM | latest |
| Containerisation | Docker Desktop | 29+ |
