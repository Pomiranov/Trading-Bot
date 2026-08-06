# QuantFlow Operational Dashboard — Approved-Reference Alignment Audit

**Date:** 2026‑07‑29 · **Repository:** `/Users/danila/Downloads/Trading-Bot-merge-learning-nik` ·
**Branch:** `quant-site-approved-reference-redesign` · **HEAD:** `80ec121`

**Nature of this document.** An evidence-based senior design + architecture review of the
**operational** QuantFlow dashboard, specifying how it should later be aligned with the shipped
marketing site and the approved Stitch reference. **It is an analysis, not an implementation.** No
production code, template, stylesheet, script, schema, migration or configuration was modified; no
dependency was installed; no database write, trade or trading process was initiated. Exactly one
file was created — this one. §37 records the verification.

**How to read the findings.** Every factual claim carries a repo-relative `path:LINE` citation or
names the read-only query that produced it. Claims derived from reasoning are labelled INFERENCE.
Claims that could not be verified at runtime — because launching the dashboard would have executed a
database migration (§1.6) — are marked as requiring runtime verification.

---

## 0. Executive Summary

### 0.1 The one-paragraph answer

The dashboard works, in the sense that it renders and most of its endpoints return 200. It is not
close to the site — not in palette, typeface, geometry, motion or restraint — but that gap is the
*cheapest* problem in this document to fix, because `dashboard.html` contains no server-side
templating at all and a full restyle requires zero Python changes. The expensive problems are
underneath: **the primary chart on the landing screen plots SBER's share price and calls it portfolio
equity; every price on the screen is 32 days old and nothing says so; an all-losing account reports
an average profit of +16,07 %; a −23,7 % drawdown renders as −0,2 %; sandbox and live results are
never separated; and under shipped defaults not one of 52 routes requires a credential.** Restyling
first would make an untrustworthy instrument look trustworthy. Fix the data and the locks, then apply
the brand — in that order.

### 0.2 Maturity scores

| Dimension | Score | Justification |
|---|---:|---|
| **Brand alignment** | **2 / 10** | Orange `#F7931A` across 130 occurrences against a white-accent monochrome site; Inter + JetBrains Mono + **Orbitron** against self-hosted Geist; blue-cast surfaces against neutrals. Only the easing curve matches — and it matches exactly. |
| **Visual consistency** | **3 / 10** | 36 distinct hex literals (129 uses), 126 distinct rgba (183), 65 distinct px (983), **20 rendered font sizes**, 11 radii, 34 shadows, 71 tokens of which 9 are dead. The mini-app's stylesheet leaks a second global `:root` and silently overrides the topbar's `pulse` keyframe. |
| **Information architecture** | **3 / 10** | No `<h1>`; no routing, so no view can be linked or restored; a **game** sits in the trading rail; the site promises a **Risk** section that does not exist; the Overview leads with three tiles that all read `+0,00 ₽`. |
| **Trader usability** | **2 / 10** | **3 of 22** core workflows answerable without ambiguity. Sandbox-vs-live is displayed nowhere. Three panels report the open-position count as 1, 3 and 3/5 in a single frame. |
| **Data correctness** | **1 / 10** | Four independent blockers (§27.2), each of which alone would invalidate a trading decision. |
| **Responsive quality** | **3 / 10** | The balance tile already wraps its `₽` at 1600px. A 14-column table's entire mobile strategy is `overflow-x: auto`. *Confidence: Medium — source-derived.* |
| **Accessibility** | **1 / 10** | The **most-used colour token fails contrast on every surface it is used on** and renders every label in the product. The primary CTA is 2.30:1. No `aria-live` anywhere. 13 infinite animations. Nothing reaches 44×44. |
| **Performance** | **2 / 10** | 1.3 MiB of render-blocking JS, compression off (77.6 % of transfer avoidable), 45–54 req/min at idle with no tab-hide gating, 8 640 `docker ps` spawns/day on the request path, and a self-inflicted 16 017-row table that the Analytics view full-scans. |
| **Security** | **1 / 10** | IP-based auth, no CSRF, 31 unescaped `innerHTML` sinks, no audit trail, and a documented JWT stack that is dead code. |
| **Production readiness** | **1 / 10** | Ceiling of ~3 concurrent viewers (5-connection pool); SSE pins a worker per client so the dev server is load-bearing; the trading engine runs inside the web process; zero route test coverage. |

### 0.3 The ten findings that matter

1. **The Equity Curve is fiction.** `/api/equity` falls through to a candle-derived path — SBER's
   price — presented as portfolio equity. It ends at ₽919 224 while the paper account went
   ₽10 000 000 → **₽7 626 546** (verified read-only). This is the largest element on the landing screen.
2. **Every price is 32 days stale, and the UI claims it is fresh.** `max(candles.time)` =
   `2026‑06‑26`; DB `now()` = `2026‑07‑28`. Worse, `fullSync` drops failed slices silently and then
   **unconditionally** stamps «обновлено HH:MM:SS» with a green dot.
3. **Two statistics are simply wrong.** `avg_profit_pct` is `AVG(ABS(pnl_pct))`, so an account with
   **35 trades, 0 wins, −₽2 373 454** reports **+16,07 %**. `max_drawdown` carries two units under one
   name, rendering −23,73 % as **«−0,2 %»**.
4. **There is no authentication.** Access control is one `before_request` IP check
   (`dashboard_auth.py:73-100`); under shipped defaults **zero of 52 routes require a secret**, there
   is **no CSRF**, and the JWT/Argon2 stack `CLAUDE.md` describes is **dead code**. 10 of 12 mutating
   endpoints — including engine start/stop and credential writes — are drive-by exploitable.
5. **Sandbox and live are indistinguishable.** `is_sandbox` exists on `trades` and is **filtered
   nowhere** in `bot/ui/**` or `bot/qf_platform/**`. No badge, no filter, no column. The marketing
   site puts `РЕЖИМ · ПЕСОЧНИЦА` permanently in its terminal's chrome; the real terminal says «Live».
6. **The palettes are irreconcilable as they stand.** The site is monochrome by written doctrine,
   with cold blue permitted only as light at ≤0.28 alpha and enforced by a lint rule. The dashboard's
   identity is Bitcoin orange, used simultaneously for brand, focus, hover, progress, "online" and
   "warning" — five meanings, one colour, and `#fff` on `#F7931A` measures **2.30:1**.
7. **Six trader questions are unanswerable from data, not merely unrendered.** `skipped_signals`,
   `forward_state` and `system_events` are **all empty**, and `audit_events` holds 12 rows, all
   `auth.denied`. "Why was this signal rejected?", "what is `osc_range_moex_d1_fwd` doing?", "what
   went wrong?" and "who did what?" have no data behind them.
8. **The Learning section over-claims against a population of 2.** `trades` holds **2 rows** and
   `hypotheses` holds **0**, while the account executed 35 paper trades. Confidence appears without
   sample size; `н/д` and a genuine `0,00 %` render identically.
9. **A latent migration defect will reproduce on every fresh deploy.** The committed `schema.py`
   creates two indexes on columns that the *later* ALTER block adds, inside a single transaction
   (`bootstrap.py:16-30`), so the whole DDL rolls back and the Learning endpoints 500 forever with a
   clean browser console. This was observed live at the start of this audit. The fix exists in the
   working tree, **uncommitted**. Meanwhile legacy `feedback.py` runs a *second* migration on the same
   table in the same process.
10. **The redesign is cheap; the groundwork is not.** `dashboard.html` has **18 Jinja expressions,
    all `url_for`** — no server data, no loops, no conditionals. The dashboard is already an SPA.
    A complete visual alignment touches one template, two stylesheets and the render functions,
    and needs **no Python change**. That is the good news buried under everything above.

### 0.4 Recommended sequence

**Phase 0 — Reality and Safety.** Fix the four data blockers; make every GET read-only; add real
authentication and CSRF; escape the 31 sinks; populate the four empty tables; ship and harden the
migration. *Nothing visual happens here.*
**Phase 1 — Design Foundations.** Extract the site's tokens into a shared package (fixing the site's
own six token violations at the source), self-host Geist, replace `design-system.css`, and extend
`check-design-tokens.mjs` to lint the dashboard. *This is where the brand actually lands.*
**Phase 2 — Core Monitoring.** Overview per §13, Positions, Trades, Signals-with-gate, System Health.
**Phase 3 — Strategy Intelligence.** Strategy board, confidence with sample size, frozen states.
**Phase 4 — Operations.** Event log, audit trail, the operator action set behind a real safety model.
**Phase 5 — Hardening.** WCAG 2.2 AA, performance, responsive, visual regression.

The user's stated goal — *the dashboard should feel like the internal, professional part of the same
product as the site* — is achieved in Phase 1, and Phase 1 is inexpensive. It is placed second, not
first, because a credible-looking instrument that reports +16 % on a losing account is more dangerous
than an ugly one.


---

## 1. Audit Scope and Constraints

### 1.1 Repository state at audit start

| Field | Value |
|---|---|
| Working directory | `/Users/danila/Downloads/Trading-Bot-merge-learning-nik` |
| `git rev-parse --show-toplevel` | `/Users/danila/Downloads/Trading-Bot-merge-learning-nik` |
| Branch | `quant-site-approved-reference-redesign` — **matches the expected branch** |
| HEAD | `80ec1218051203427148437fa124330bdbe39497` |
| HEAD subject | `website: polish landing transitions and interaction states` |
| Remote `origin` | `https://github.com/Pomiranov/Trading-Bot.git` |
| Audit date | 2026‑07‑29 |
| Auditor | Claude Code, acting as a combined senior design / architecture / security review |

### 1.2 Pre-existing working-tree changes — NOT created by this audit

`git status --short` at audit start:

```
 M .gitignore
 M bot/qf_platform/schema.py
?? .coverage
?? approved-stitch-reference.jpg
```

These four entries were already present before any audit work began and were left untouched.
Two of them are materially relevant to the findings and are analysed rather than ignored:

- **`M bot/qf_platform/schema.py`** — an uncommitted fix that reorders two `CREATE INDEX`
  statements to run *after* the `ALTER TABLE … ADD COLUMN` block. This is the exact fix for the
  defect described in §27. It is currently unshipped, which is itself a finding (F‑DATA‑02).
- **`?? approved-stitch-reference.jpg`** — the approved reference at repo root is untracked; a
  tracked duplicate exists at `website/docs/design-references/approved-stitch-reference.jpg`.
  Byte-identical content in two places, one of them outside version control, is a provenance risk
  for the art direction that the whole redesign is anchored to (F‑GOV‑02).

### 1.3 Governance conflict — the canonical repository path

`CLAUDE.md` states:

> **Canonical location**: `/Users/danila/Documents/GitHub/Trading-Bot/` … All Claude Code edits MUST
> happen in this directory. Never edit files in ~/Downloads/Trading-Bot-* (those are stale copies).

That directory does exist. However, the branch this audit was commissioned against
(`quant-site-approved-reference-redesign`), the approved reference image, and every recent commit in
the redesign trajectory live in the **Downloads** copy. `CLAUDE.md` also names
`merge-learning-nik` as the active branch, which is not the branch checked out here.

The audit was therefore performed where the user directed it and where the work actually is. The
divergence is recorded as **F‑GOV‑01** (§30, §35) because a redesign handed to a second team against
a stale canonical path would silently produce work against the wrong tree.

### 1.4 Directories inspected

```
bot/ui/                     dashboard entry, routes, templates, static assets     [primary object]
bot/ui/api/                 platform blueprint
bot/qf_platform/            schema, bootstrap, services, repositories
bot/security/, bot/auth/    dashboard auth surface
website/src/styles/tokens/  the site's shipped design tokens                      [source of truth]
website/src/app/globals.css the site's shipped utility/component layer
website/src/components/     site primitives + the marketing terminal preview
website/scripts/            design-token enforcement
website/docs/, design/      prior audits and prior dashboard specs
quantflow_schema.sql        design-time schema
logs/                       runtime evidence (read only)
live PostgreSQL             read-only introspection
```

### 1.5 The three distinct artefacts — do not confuse them

This is stated first because the single largest hand-off risk in this programme is a team
redesigning the wrong surface.

| Layer | What it is | Where it lives | Status in this audit |
|---|---|---|---|
| **A. Operational Dashboard** | The real Flask/Jinja trading terminal a trader logs into | `bot/ui/dashboard.py`, `bot/ui/api/platform_routes.py`, `bot/ui/templates/dashboard.html`, `bot/ui/static/**` | **The object of this audit.** Everything in §2–§30 refers to this. |
| **B. Marketing terminal preview** | A static, tabbed React mock of a terminal, inside the public site | `website/src/components/sections/dashboard/dashboard-section.tsx`, `dashboard-terminal.tsx` | A **design reference and a promise to the market**. Never to be mistaken for A. Its own copy says *«Значения демонстрационные и не являются результатами торговли»*. |
| **C. Approved Stitch reference** | A JPG contact sheet of the approved site art direction | `approved-stitch-reference.jpg`, `website/docs/design-references/approved-stitch-reference.jpg` | The **art-direction authority**: brand character, palette discipline, panel language, rhythm. It is a marketing composition and its *layout* must not be copied into a terminal. |

**Rule for the implementation team:** B and C define *how the product should feel*. Only A is to be
rebuilt. No task in the redesign backlog may modify B or C without a separate marketing decision.

### 1.6 Runtime verification — what was and was not possible

**Performed.** The Next.js site (`website/`, dependencies already installed) was started, measured,
and stopped. `git status --short` was byte-identical before and after; `.next/` and `*.tsbuildinfo`
are gitignored (`website/.gitignore:17,40`). Every design token reported in §7 was read from
`getComputedStyle` on the **running** site, not inferred from source.

**Refused, with cause.** The Flask dashboard was **not relaunched**. Starting it executes DDL:
`bot/ui/dashboard.py:70` calls `ensure_platform_schema(_engine)` at module import time, and
`bot/qf_platform/bootstrap.py:16-30` executes the whole of `PLATFORM_SCHEMA_SQL` — which contains
~27 `ALTER TABLE trades ADD COLUMN IF NOT EXISTS …` statements (`bot/qf_platform/schema.py:67-94`).
Launching the dashboard is therefore a **schema migration** against the live database, which the
audit brief explicitly forbids ("не запускай миграции", "база используется только для чтения").
Per the brief's own fallback instruction, the audit proceeded source-based.

**Runtime evidence that *is* available**, captured earlier in this same session before those
constraints were issued, and treated as valid:

- One full desktop screenshot of the Overview view (1600×900 CSS px).
- The dashboard process's own request log for a complete cold page load — every endpoint and its
  HTTP status, including the four HTTP 500s.
- `logs/dashboard.log` (749 KB) for a separate, longer run on 2026‑07‑28 19:15→20:09.
- Read-only PostgreSQL introspection: table list, `trades` column list, row counts.
- Browser console state (`onlyErrors`) for the loaded Overview.

**Marked as requiring runtime verification.** Every claim about the dashboard at 1280×800,
1024×768, 768×1024 and 390×844, every computed-contrast measurement, every keyboard-traversal order,
and every loading/empty/error/stale rendering is derived from source and is tagged
`Confidence: Medium — requires runtime verification` in the finding tables. §32 Phase 0 includes the
task of re-running this pass once the schema defect is fixed and a read-only launch mode exists.

### 1.7 Change constraints observed

No production code, template, stylesheet, script, SQL, schema, migration, Docker config, `.env`,
`CLAUDE.md`, manifest, lock file, linter config or test was modified. No dependency was installed.
No migration was run. No trade was created. No write was issued to PostgreSQL. No trading loop,
sandbox session or broker command was started. No file was deleted or renamed. No prototype,
mockup or UI component was created. Known defects — including the four HTTP 500s and the layout
break in the balance tile — were deliberately left unfixed.

Exactly one file was created: this document. §37 records the verification.


---

## 2. Current-State Repository Map

### 2.1 The shape of the thing

The single most important structural fact, and the one that changes the cost of every recommendation
in this document:

> **`dashboard.html` is 911 lines and contains exactly 18 Jinja expressions, all of them
> `{{ url_for('static', …) }}`. There is no `{% for %}`, no `{% if %}`, no server-side variable.
> `index()` at `bot/ui/dashboard.py:392-394` is `return render_template("dashboard.html")` with no
> context.**

This is not a Flask/Jinja application. It is a **static HTML shell plus ~5 900 lines of vanilla
client-side JavaScript that fetches JSON** — already a single-page app, with client-side routing
(`app.js:130,158`), a store (`core/store.js`), an API layer (`core/api.js`) and a sync layer with
SSE + polling (`core/sync.js`). Flask is already a pure JSON API as far as the dashboard is
concerned.

Consequence: **a full visual redesign requires zero Python changes.** That single fact reframes the
architecture question in §31.

### 2.2 File map

```
Operational dashboard
├── entry / server
│   ├── bot/ui/dashboard.py                751  Flask app, 23 routes, DB engine, DDL bootstrap,
│   │                                           Sharpe/drawdown maths, engine lifecycle
│   ├── bot/ui/api/platform_routes.py      676  platform blueprint, 30 routes, 17 inline SQL strings
│   └── bot/security/dashboard_auth.py      99  the entire access-control surface (one before_request)
├── service / data layer
│   ├── bot/qf_platform/schema.py          344  runtime DDL  [UNCOMMITTED CHANGES]
│   ├── bot/qf_platform/bootstrap.py        31  executes the DDL in ONE transaction
│   ├── bot/qf_platform/services/          dashboard_service, portfolio_service, signals_service,
│   │                                      analytics_service, paper_trading_service, system_health_service
│   ├── bot/qf_platform/repositories/      signals_repository, paper_repository
│   └── quantflow_schema.sql               319  design-time schema — DIVERGENT from the above
├── template
│   └── bot/ui/templates/dashboard.html    911  8 views, 41 inline style="…", 18 script tags
├── CSS
│   ├── bot/ui/static/design-system.css    873  71 --qf-* tokens + component primitives
│   ├── bot/ui/static/style.css           1044  app shell, layout, per-view
│   └── bot/ui/static/miniapp/miniapp.css  449  the game — LOADED GLOBALLY, leaks a 2nd :root
├── JavaScript
│   ├── app.js                             747  view switching, keyboard, settings, ticker chart
│   ├── platform.js                        252  platform API orchestration
│   ├── components.js                      217  badge/table cell factories (XSS sinks)
│   ├── charts.js                          293  lightweight-charts + echarts wrappers
│   ├── views/render.js                    446  32 innerHTML assignments, 0 escaping
│   ├── views/learning.js                  386  own 20 s timer, injects runtime CSS
│   └── core/{api,store,sync,layout,format,assets,enhance}.js   695 total
├── chart layer (third-party, CDN, no SRI)
│   ├── lightweight-charts@4.2.0           163 551 B raw / 50 847 B gzip
│   └── echarts@5.5.0                    1 029 203 B raw / 334 508 B gzip
└── tests
    └── tests/platform_tests/              ZERO coverage of any dashboard route
```

### 2.3 Per-file disposition

| File | Responsibility | Status | Impact on redesign |
|---|---|---|---|
| `bot/ui/dashboard.py` | App, 23 routes, engine lifecycle, financial maths | **Active, overloaded** | Contains `_sharpe()` and `_max_drawdown()` in a route file; hosts the trading engine in the web process |
| `bot/ui/api/platform_routes.py` | 30 platform routes | **Active, overloaded** | 17 inline SQL strings in handlers |
| `bot/security/dashboard_auth.py` | IP-based gate | **Active — and the whole of security** | Must be replaced before anything is exposed |
| `bot/auth/**` | JWT / Argon2 / sessions | **DEAD CODE** — missing module, missing config, missing deps | `CLAUDE.md` describes it as live. It is not. Delete or complete. |
| `bot/qf_platform/schema.py` | Runtime DDL | **Active, uncommitted fix pending** | Ordering defect, see §27 |
| `quantflow_schema.sql` | Design-time schema | **Stale / divergent** | Enums, hypertable, UUID PK — none of which the live DB has |
| `dashboard.html` | Shell | **Active** | The redesign's main file |
| `design-system.css` | Tokens + primitives | **Active, to be replaced** | 71 tokens, 9 dead |
| `style.css` | Shell + layout | **Active, to be replaced** | 27 selectors duplicated with design-system.css |
| `miniapp/miniapp.css` + `game.js` + `miniapp.js` | Quant Hunter game | **Active but mis-scoped** | 66 937 B (21 % of local payload) loaded eagerly on every dashboard load for a hidden view; leaks a global `:root`; its `pulse` keyframe silently overrides the dashboard's |
| `views/render.js`, `components.js` | Rendering | **Active, security-critical** | 31 unescaped `innerHTML` interpolations |
| `core/store.js` | Store | **Active, partly broken** | `on()` returns a no-op unsubscribe (`:108-111`) |
| `bot/learning/feedback.py` | Legacy learning | **Active on the dashboard's import path** | Runs its own schema migration at dashboard startup — a second DDL authority on `trades` |
| `tests/` | — | **No dashboard coverage** | Every redesign change is unverified by construction |

---

## 3. Dashboard Architecture Audit

### 3.1 What is actually there

- **No app factory.** The Flask app is created at module scope in `bot/ui/dashboard.py`; importing
  the module connects to the database, runs DDL, instantiates an `IndicatorEngine` and a
  `RulesEngine`, registers security, and starts background engine threads. Import has side effects
  that reach the database and the broker.
- **Two route families**: 23 legacy routes in `dashboard.py` and 30 in `platform_routes.py` under
  `/api/platform`. They overlap: `/api/portfolio` and `/api/platform/portfolio` are different code
  paths returning different shapes from different tables.
- **Separation of concerns: weak.** 25 raw SQL strings live in the HTTP layer, 17 of them inside
  route handlers. `_sharpe()` (`dashboard.py:109-118`) and `_max_drawdown()` (`:121-130`) are
  financial calculations implemented in a route module. There are **three existing implementations
  of Sharpe** in the repo (`dashboard.py`, `analytics_service.py:229-237`, `backtest/engine.py`).
- **No view-model layer.** Routes serialise rows more or less directly; the client re-derives
  meaning.
- **Error handling: five different conventions.** 16 blueprint routes have no `try/except` and
  return an HTML 500 to a JSON client; 7 `dashboard.py` routes swallow every exception and return
  `200 []` — a silent lie. There is no `@app.errorhandler`, no error envelope.
- **GET routes that write.** `/api/platform/paper/account`, `/portfolio`, `/overview` each INSERT an
  `equity_snapshots` row and UPDATE `paper_accounts`/`paper_positions`. `/api/platform/signals`
  INSERTs into `trading_signals`. This violates HTTP semantics and makes the polling loop a writer.

### 3.2 The architectural ceiling — named precisely

**`create_engine(..., pool_size=2, max_overflow=3)` at `bot/ui/dashboard.py:65`. Five connections,
total, for everything.**

Demand against those five:

- `core/sync.js:4` `POLL_MS = 12000`, issuing a **9-request batch** each cycle (`sync.js:79-89`).
  Four of the nine independently recompute the whole paper portfolio; `/overview` alone is ≈15
  sequential pool checkouts.
- `views/learning.js:9` adds an independent 20 s timer firing five more.
- The **same process** runs `paper-engine-signals` every 90 s and `paper-engine-monitor` every 30 s
  against the **same engine** (`dashboard.py:86`), plus the learning loop.

**The ceiling is roughly three concurrent viewers, and it is in the data layer, not the view layer.**
No amount of front-end work moves it. Queued immediately behind it:

1. **SSE holds a worker per client forever** (`platform_routes.py:411-437` blocks on
   `q.get(timeout=25)` inside `stream_with_context`). The Werkzeug dev server's threading is
   currently load-bearing; the first time this runs behind gunicorn's default sync worker,
   *N workers = N total viewers* and everything else 503s.
2. **Read paths that write** — 16 016 `equity_snapshots` rows for one open position, growing with
   viewing time, polluting the series the equity chart reads back.
3. **Blocking non-DB I/O on the poll path** — `subprocess.run(["docker","ps"], timeout=3)` and
   `psutil.cpu_percent(interval=0.1)` (a hard 100 ms sleep in the request thread) on
   `/api/platform/health`, `/overview` and `/brokers`, every 12 s, per tab. ≈130 ms of pure blocking
   before any application data is read; **8 640 process spawns per day** to render a container count.

### 3.3 The seven questions, answered

**(1) Can the dashboard be safely modernised inside the existing Flask/Jinja architecture?**
**Yes — and more cheaply than the file layout suggests.** Because Jinja interpolates nothing, a
visual redesign touches `dashboard.html`, the two CSS files, and the render functions. Zero Python
change. Three caveats: the CSP in `security/http_middleware.py:10-18` must be updated for any new
font/asset host; `?v=16` cache-busting is hardcoded 18 times and must be bumped together; and
`http_middleware.py:49` has a live bug — it tests `request.path.startswith("/static/miniapp/")` while
the mini-app is served from `/miniapp`, so the Telegram Mini App gets `frame-ancestors 'none'` and
**cannot be framed by Telegram Web**.

**(2) Where is the architectural limit?** §3.2 — the 5-connection pool, then SSE-per-worker, then
read-paths-that-write, then blocking subprocess I/O.

**(3) Is a separate frontend application needed?** **Not for the reasons usually given.** The
dashboard is already an SPA; what is missing is a build step and a component model, not React. The
surface is 8 views, ~53 endpoints, and a data model that does not contemplate a second user
(`paper_repository.py:17` `user_id: str = "default"`; `portfolio_service.py:208` `LIMIT 1`).

**(4) Is there a case for moving the operational dashboard to Next.js?** Only one honest case:
*sharing tokens and components with the marketing site*. That is a real benefit and it is the
user's actual goal here. It is not, however, a reason to move **first** — see §31.

**(5) Benefits and risks of that move?** See §31 Option B/C in full.

**(6) Can one design-token package serve both surfaces?** **Yes, and it is the recommended
mechanism.** The site's tokens are already plain CSS custom properties emitted from Tailwind v4
`@theme` plus a `:root` mirror; the dashboard consumes plain custom properties. A single
`tokens.css` published as the source of truth, imported by both, with the site's
`scripts/check-design-tokens.mjs` extended to lint the dashboard's CSS, gives one palette and one
enforcement gate with no framework coupling whatsoever. This is Phase 1's core deliverable.

**(7) How to avoid duplicating business logic?** By moving the derivations server-side into typed
view models before any client rewrite. The concrete risk list, all currently computed in Python and
all currently re-derivable in the client: Sharpe, max drawdown, Sortino, win rate, profit factor,
expectancy, unrealized PnL, exposure, distance-to-stop, R multiples. **Sharpe already exists three
times in this repo.** A TypeScript fourth is the default outcome of a naïve port.

---

## 4. Current Information Architecture

### 4.1 Views actually shipped

| # | `data-view` | Nav label | Section id | Notes |
|---|---|---|---|---|
| 1 | `dashboard` | Dashboard | `#view-dashboard` | Landing; active by default |
| 2 | `portfolio` | Portfolio | `#view-portfolio` | |
| 3 | `signals` | Signals | `#view-signals` | |
| 4 | `backtest` | Backtest | `#view-backtest` | |
| 5 | `analytics` | Analytics | `#view-analytics` | |
| 6 | `learning` | Learning | `#view-learning` | Tooltip literally reads `Learning (7)` |
| 7 | `miniapp` | Quant Hunter | `#view-miniapp` | A **game**, in the trading rail |
| 8 | `settings` | Settings | `#view-settings` | Writes broker credentials |

**There is no Risk view**, although the marketing site promises one. **There is no Positions,
Orders, Strategies, System Health or Event Log view.**

### 4.2 Structural findings

| ID | Finding | Evidence |
|---|---|---|
| F‑IA‑01 | **No `<h1>` anywhere** in the 911-line document; exactly one `<h2>`; every other view title is a `<div class="section-title">` | `dashboard.html:666` vs `:249,:335,:370,:434,:541` |
| F‑IA‑02 | **No `aria-live` region anywhere.** Toasts, sync status, engine status and every price/PnL update are announced to nobody | only 3 `aria-*` attributes exist in the whole template (`:26,:39,:102`) |
| F‑IA‑03 | **No routing.** No `history.pushState`, no `location.hash`, no `document.title` update. A view cannot be linked, bookmarked, or restored after reload | grep across all of `bot/ui/static/**/*.js` → 0 hits |
| F‑IA‑04 | **`.num` alignment broken in 3 of 8 tables** — 12 columns right-aligned in the header, left-aligned in the body | `components.js:76-84,103` emits `class="mono"` (no alignment) under `<th class="num">`; `app.js:601` emits neither |
| F‑IA‑05 | Learning view injects runtime CSS referencing **7 custom properties defined nowhere**, and 2 that come from the *Mini App* palette | `views/learning.js:322-384` |
| F‑IA‑06 | Analytics "engine strip" presents **4 hardcoded literals** (commission, slippage, data source, mode) as live telemetry | `dashboard.html:557-572` |
| F‑IA‑07 | `QFApi.closePosition` / `closePaperPosition` exist but are wired to **no control**. There is no way to close a position from the dashboard | `core/api.js:79-93`; grep for callers → none |
| F‑IA‑08 | Mixed language: 113 Cyrillic vs 224 Latin-only user-facing strings, **zero i18n layer**, while `website/` ships two locale files with 254 keys each | §9.5 |
| F‑IA‑09 | The Mini App's stylesheet leaks a **second global `:root`** into the dashboard document, and its `pulse` keyframe (`miniapp.css:101`) silently overrides the topbar's (`style.css:244`) | `dashboard.html:13` |

### 4.3 Block inventory — Dashboard (Overview) view

| Block | Purpose | Data source | Current quality | Problems |
|---|---|---|---|---|
| Balance tile | Account size | Tinkoff portfolio | Poor | `₽` wraps to a second line; badge says «Т-БАНК» while the sub-line counts paper positions; contradicts the right rail |
| PnL today / week / month | Performance | `/api/stats` | Poor | Three tiles, all `+0,00 ₽`; a measured zero is indistinguishable from no data |
| Sharpe 252d | Risk-adjusted return | `trades` (2 rows) | Meaningless | Renders `—`; a 252-day annualised Sharpe over 2 trades would be noise even if it computed |
| Risk · drawdown gauge | Risk | `/api/platform/risk/status` | Poor | Renders `–`; severity encoded by hue alone |
| Equity Curve | Capital over time | **`candles`, not equity** | **Wrong** | See §27 |
| Риск-метрики | Exposure | mixed | Poor | «Позиции 3/5» contradicts «Активные позиции 1» |
| Активные позиции | Holdings | `paper_positions` | Adequate | No distance-to-stop, no quote age |
| Брокеры | Connectivity | `/api/platform/brokers` | Poor | Status by hue only; "Online" pulses forever |
| Последние сигналы | Recent signals | `trading_signals` (8 rows) | Adequate | No gate decision, no reason |

---

## 5. Trader Workflow Audit

Each scenario is scored by the number of interactions from a cold load, and by whether the answer is
**unambiguous**. "Steps" counts view switches and scrolls, not eye movements.

| # | Scenario | Steps today | Answer available? | Verdict |
|---:|---|---:|---|---|
| 1 | Is the bot running? | ∞ | **No.** Engine state exists at `/api/platform/engine/status` but is not on the Overview; the Analytics view has a Start/Stop button whose label is the only hint | **Fails** |
| 2 | Is the database working? | ∞ | **No.** `/api/platform/health` reports it; nothing renders it on Overview | **Fails** |
| 3 | Is the broker connected? | 1 | Partially — «Брокеры» shows Online/Offline by hue, no timestamp, no reason, no latency | Weak |
| 4 | Sandbox or live? | ∞ | **No. This is not displayed anywhere in the UI.** | **Critical failure** |
| 5 | Current open positions | 1 | Yes, but three panels give three different counts (1, 3, 3/5) | **Contradictory** |
| 6 | Recent trades | 2 | «История Paper Trades» is **permanently empty** — 35 rows exist, 0 render (envelope mismatch) | **Fails** |
| 7 | Latest signal | 1 | Yes — time, ticker, direction, price, confidence | OK |
| 8 | Why was a signal accepted? | ∞ | **No.** No gate/decision trail in the UI | **Fails** |
| 9 | Why was a signal rejected? | ∞ | **No — and not answerable from data.** `skipped_signals` has **0 rows** | **Critical failure** |
| 10 | Strategy confidence | 2 | Learning view reads `belief_system` (8 rows) | OK |
| 11 | Strategy statistics | 2 | Yes, but win rate/profit factor come from `trades` (2 rows) while the account traded 35 paper trades | **Misleading** |
| 12 | Sample size | — | **Never shown next to any statistic** | **Fails** |
| 13 | Distinguish backtest / forward / sandbox / live | ∞ | **No.** `is_sandbox` is **never filtered anywhere** — zero occurrences outside DDL | **Critical failure** |
| 14 | State of `osc_range_moex_d1_fwd` | ∞ | **No.** `forward_state` has **0 rows**; the id appears only in a hardcoded Python list | **Fails** |
| 15 | State of `trend_moex_live` | ∞ | **No.** No live-vs-forward distinction exists | **Fails** |
| 16 | Frozen strategies | ∞ | **No.** No frozen state is rendered | **Fails** |
| 17 | Detect stale data | ∞ | **No — and the UI actively lies.** `fullSync` uses `Promise.allSettled`, silently drops rejected slices, then unconditionally sets `syncStatus:'live'` and stamps a fresh «обновлено HH:MM:SS» with a green dot. **All market data is currently 32 days old** and nothing says so | **Critical failure** |
| 18 | Find a system error | ∞ | **No.** `system_events` has 0 rows; there is no log or event view; four endpoints can 500 with a clean browser console | **Fails** |
| 19 | Telegram delivery status | ∞ | **No** | **Fails** |
| 20 | Stop a dangerous action | 2 | Engine Start/Stop exists — with **no confirmation and no disabled state** | **Unsafe** |
| 21 | Audit trail | ∞ | **No.** `audit_events` holds 12 rows, all `api.auth.denied`. No trade, engine or credential event was ever recorded | **Fails** |
| 22 | Real portfolio risk | 1 | Exposure and drawdown are shown but drawdown renders **−0.2 %** where the account is **−23.7 %** (unit bug, §27) | **Wrong** |

**Score: 3 of 22 scenarios answerable without ambiguity.** Six of the failures are not UI problems —
they are missing data (`skipped_signals`, `forward_state`, `system_events` are all empty tables) and
must be fixed in Phase 0, before any pixel is moved.


---

## 6. Brand and Visual Alignment

### 6.1 Alignment matrix

| Parameter | Site (shipped, runtime-verified) | Approved reference | Dashboard now | Gap | Recommendation |
|---|---|---|---|---|---|
| **Background** | `#030303` neutral | Near-black, neutral | `#08090d` — **blue-cast** (B>R at every step of a 6-step ramp) | Hue + 3 extra steps | Adopt the site's 4 neutrals: `#030303 / #0a0a0a / #111111 / #171717` |
| **Surface** | `#0a0a0a`, `#111111`, `#171717`, graphite `#131313` on paper | Graphite cards on both grounds | `#111318`, `#161a22`, `#1c212b` + a glass layer with `backdrop-filter: blur(20px) saturate(1.5)` | Glass is decorative cost with no meaning; saturate(1.5) amplifies the blue cast | Flat surfaces. Reserve glass for genuine overlays (modals, tooltips) |
| **Typography** | Geist / Geist Mono, self-hosted, 6+2 roles, enforced | Single sans, mono eyebrows | Inter / JetBrains Mono / **Orbitron**, Google CDN, 8 tokens → **20 rendered sizes** | Different faces, 3× the sizes, render-blocking third-party | Geist + Geist Mono self-hosted; 6 roles; build fails on a 7th |
| **Border** | `rgba(255,255,255,.10)` hairline; `.35` for interactive edges | Hairline, visible | `rgba(255,255,255,.07)` ≈1.3:1 — **fails 3:1 for any control border** | Too faint; no strong variant | Adopt both site values |
| **Radius** | 4/8/12/16/20/24 | ~16–24 on cards | 4/6/10/14/18 → **11 distinct rendered radii** | Different scale, uncontrolled | Adopt the site scale; nesting rule inner = outer − 4 |
| **Accent** | **`#ffffff`** | White pills on dark, dark on paper | **`#F7931A`** — 130 occurrences across 5 hexes | Total conflict | White. Orange deleted entirely |
| **Spacing** | 4px base + 3 semantic vertical steps + `--space-content-max: 1280px` | Generous but structured | 4px base, `--qf-space-1` dead, **983 raw px literals across 65 distinct values** | No rhythm, no max width | Token-only spacing; terminal-specific density scale |
| **Grid** | 1280px content max, one left edge at every viewport | One consistent edge | Sidebar 240/64px + fluid main, no max width, per-view ad-hoc grids | No shared edge | 12-col grid, `--space-content-max` for reading views, full-bleed for data views |
| **Depth** | One soft panel shadow; hover = border + faint glow | Flat cards, hairline separation | **34 distinct box-shadow definitions**, glass rings, orange glows | Uncontrolled | 3 shadows max: rest, hover, overlay |
| **Motion** | `--ease-out-expo` identical to the dashboard's; 150/300/800ms; reveal is scroll-driven | Static | Same easing (good); **13 infinite animations**, 6 reachable | Infinite pulsation on healthy states | §24 |
| **Iconography** | Thin line SVG, currentColor | Thin line | Mixed line + filled SVG, some hardcoded `#F7931A` strokes | Inconsistent weight, hardcoded fill | One line set, 1.5px, currentColor only |
| **Status colors** | `#7fd8a8` / `#f08a9c` / `#8a8a8a`, always with a text label | Labelled pills | `#00c076` / `#f6465d` + orange-as-online + blue + purple; **hue-only** | Meaning carried by colour alone | §8 |
| **Tables** | Not a site pattern (the preview shows dense rows) | Dense, hairline, right-aligned numerics | 7px padding, sticky header, `rgba(0,0,0,.22)` header bg, orange row hover, **no tabular numerals** | Alignment broken in 3 of 8 | §18 |
| **Charts** | None on the site | A single restrained line | lightweight-charts + ECharts, hardcoded colours, TradingView watermark | Third-party branding on a product surface | §17 |
| **Controls** | White pill CTA; outline secondary; focus = white ring | White / dark pills | Orange gradient CTA at **2.30:1 contrast** (`#fff` on `#F7931A`) — fails AA-large | Unreadable primary button | §19 |

### 6.2 What transfers, what adapts, what must not cross

**Transfers directly** — surfaces, text ramp with its certified ratios, border pair, radius scale,
the two trade semantics, `--ease-out-expo`, the mono-eyebrow label idiom, the "status always carries
a word" rule, and the discipline itself (a token file, a lint gate, a documented doctrine).

**Adapts** — type sizes compress (14px body, 12px caption); spacing compresses; the paper band
becomes a **live-mode safety device** rather than editorial punctuation; the cold blue survives only
on the sign-in screen and empty-state geometry, as stroke, ≤0.28 alpha.

**Must not cross** —

| Site device | Why it is disqualified on a terminal |
|---|---|
| Scroll-driven reveal (`--duration-reveal: 800ms`) | Measured live: content sits at `opacity: .0456` until driven. A risk figure that is invisible until an animation agrees to run is disqualifying. |
| Lenis smooth scrolling | Breaks the wheel↔row relationship in a dense grid; it broke programmatic scrolling during this audit. |
| Q-aperture orbits, ambient glow pools | Ambient light behind live data is indistinguishable from a system-state highlight. |
| Magnetic cursor | An element that moves away from the pointer, next to «Закрыть позицию». |
| Whole-panel hover glow / bloom | The site's `.panel-bloom:hover` repaints an entire frame; on a table that is 60 rows of noise. |
| Round curated numbers | The preview shows `12`, `5%`, `2.0 × ATR`. Real data is not round, and the preview's own disclaimer says so. |
| Section-scale vertical rhythm (96–232px) | A terminal that spends 176px between blocks shows four rows per screen. |

### 6.3 Findings against the site's own system

The site is not flawless, and the dashboard must not inherit its defects:

- **The 0.28 cyan ceiling is already violated in shipped code** — seven literals in `globals.css`
  exceed it, peaking at `drop-shadow(0 0 5px rgba(124,200,255,0.55))` at `globals.css:1377`, plus an
  off-palette `rgba(56,132,184,0.45)` at `:1327`.
- **The `cyan-as-ink` gate cannot see where cyan actually lives.** `check-design-tokens.mjs:22` sets
  `ROOT = src/components`, while `globals.css:775` contains a literal `color: var(--color-signal);`.
  `src/app`, `src/lib` and `globals.css` are entirely unguarded.
- **`src/lib/strategy-status.ts:72-93`** is an unguarded sixth colour surface — a `TONE_STYLE` map
  with six raw `rgba()` values corresponding to no token.
- **Two retired colours still ship**: `button.tsx:39` uses `rgba(255,77,109,0.26)` (a different red
  from `--color-danger`), and `access-form.tsx:85` uses `rgba(34,229,139,0.28)` — the exact
  `#22e58b` green the token file says was desaturated away.
- **`::selection` breaks on the paper bands** — `globals.css:105-108` hard-codes `color: #ffffff`
  globally and nothing overrides it where the ground turns near-white.
- **Five `@theme`-only z-index tokens are tree-shaken to the empty string** in the production
  bundle: only `--z-nav` survives.

Any shared token package must fix these at the source, not copy them into a second consumer.

---

## 7. Exact Design Token Extraction

All values below were read from the **running** site via `getComputedStyle`, not inferred.

### 7.1 Colour tokens

| Role | Site variable | Value | Source | Use in dashboard? | Trader-semantic variant needed |
|---|---|---|---|---|---|
| Page background | `--color-bg` | `#030303` | `tokens/color.css:35` | **Yes, directly** | — |
| Elevated ground | `--color-bg-elevated` | `#060607` | `:125` | Yes — modal scrim base | — |
| Surface | `--color-surface` | `#0a0a0a` | `:36` | Yes — sidebar, topbar | — |
| Card | `--color-panel` | `#111111` | `:37` | Yes — every panel | — |
| Hover / selected surface | `--color-panel-raised` | `#171717` | `:39` | Yes | Add `--row-selected` at the same value + a 2px left rule |
| Nested row | `--color-graphite` | `#131313` | `:150` | Yes | — |
| Border subtle | `--color-border` | `rgba(255,255,255,.10)` | `:46` | Yes | — |
| Border strong | `--color-border-strong` | `rgba(255,255,255,.35)` | `:47` | **Yes — mandatory** for every control edge (3:1) | — |
| Text primary | `--color-text-primary` | `#ffffff` (20.4:1) | `:51` | Yes | — |
| Text secondary | `--color-text-secondary` | `rgba(255,255,255,.72)` (10.4:1) | `:52` | Yes | — |
| Text tertiary | `--color-text-tertiary` | `rgba(255,255,255,.56)` (6.5:1) | `:53` | Yes | — |
| Text quaternary (floor) | `--color-text-quaternary` | `rgba(255,255,255,.48)` (4.9:1) | `:54` | Yes — **hard floor** | — |
| Brand accent | `--color-accent` | `#ffffff` | `:60` | Yes | Never a status |
| Accent hover | `--color-accent-hover` | `rgba(255,255,255,.88)` | `:62` | Yes | — |
| Success | `--color-success` | `#7fd8a8` (11.6:1) | `:79` | Yes | `profit`, `healthy` |
| Success dim | `--color-success-dim` | `rgba(127,216,168,.14)` | `:80` | Yes | — |
| Danger | `--color-danger` | `#f08a9c` (8.9:1) | `:83` | Yes | `loss`, `failed`, `disconnected`, `destructive` |
| Danger dim | `--color-danger-dim` | `rgba(240,138,156,.14)` | `:84` | Yes | — |
| Neutral status | `--color-neutral` | `#8a8a8a` (5.6:1) | `:89` | Yes | `stale`, `paused`, `frozen`, `unknown` — **differentiated by shape, not hue** |
| Warning | *does not exist* | — | — | **New** | `#d9c187` (11.2:1) — see §8.3, owner decision D‑05 |
| Focus | uses `--color-accent` | `#ffffff` | — | Yes | 2px ring, 2px offset |
| Selection | hard-coded `#ffffff` | — | `globals.css:105` | **Fix before adopting** | — |
| Overlay / glass | `--color-glass-surface` | `rgba(12,12,14,.62)` | `:92` | Overlays only | — |
| Paper | `--color-paper` | `#f4f2ec` | `:43` | **Live-mode banner only** | — |
| On-paper ink | `--color-on-paper` | `#0a0a0a` (17.4:1) | `:136` | With the above | — |
| Signal (light only) | `--color-signal` | `#7cc8ff` | `:162` | Sign-in + empty-state stroke only, ≤0.28α | **Never** a status or a series |

### 7.2 Typography

| | Site | Terminal target |
|---|---|---|
| Interface face | Geist (self-hosted, latin+cyrillic) | **Same** |
| Mono face | Geist Mono | **Same** |
| Display face | none | **none** — Orbitron removed |
| Weights | 400 / 500 / 600 | Same |
| Roles | 6 `@theme` + 2 `:root` | 6, enforced (§9.6) |
| Line-height | 1.4 / 1.5 / 1.65 / 1.6 / 1.35 / 1.06 | 1.4 / 1.45 / 1.55 / 1.15 / 1.05 / 1.3 |
| Tracking | `.14em` label → `-.03em` hero | Same direction, compressed |
| Casing | uppercase for eyebrows only | **Same — this is a change**: today every label is uppercase |
| Numeric alignment | not configured (defect) | `font-variant-numeric: tabular-nums lining` on every numeric context |
| Tabular numerals | **0 occurrences in the dashboard** | Mandatory |

### 7.3 Geometry

| Property | Site | Dashboard now | Target |
|---|---|---|---|
| Radius | 4/8/12/16/20/24/full | 4/6/10/14/18 → 11 rendered | Site scale; inner = outer − 4 |
| Spacing | 4px base + `--space-block`, `--space-card-gap: 20px` | 65 distinct px literals | 4px base; card gap 12px; panel padding 16px |
| Container | `--space-content-max: 1280px` | none | 1280px for reading views; full-bleed for data views |
| Border width | 1px; 3px accent rules | 1px, 2px, 3px | 1px only; 2px for the selected-row rule |
| Shadows | `--shadow-card-rest`, `--shadow-card-hover`, `--shadow-panel` | **34 distinct** | 3 total |
| Blur | `--blur-glass: 24px` | `20px` + `28px` + `saturate(1.5)` | Overlays only |
| Panel padding | — | 10–16px, inconsistent | 16px header, 12px body |
| Control height | 48px (site inputs) | 32px icon, ~34px button | 32px compact / 36px default — **never below 24×24 hit area**, 44×44 on touch |
| Table row height | — | 5–7px padding → ~28–32px | 28 compact / 36 comfortable / 44 monitoring |

### 7.4 Motion

| | Site | Terminal target |
|---|---|---|
| Micro | `150ms` | `150ms` |
| Base | `300ms` | `220ms` (documented divergence — density) |
| Panel | `500ms` | `400ms` |
| Reveal | `800ms` scroll-driven | **Forbidden** |
| Easing | `cubic-bezier(.16,1,.3,1)` | **Identical** |
| Bounce | none | **Delete `--qf-ease-bounce`** |
| Reduced motion | present | present **and** must set `animation-iteration-count: 1` — today it only sets duration, so infinite loops keep looping |

---



---

## 8. Color Strategy for a Trading Interface

The site is monochrome by doctrine. A trading terminal cannot be. This section resolves that tension
without reintroducing the orange identity and without weakening the site's discipline.

### 8.1 The doctrine being inherited

`website/src/styles/tokens/color.css:1-31` states the rule the whole brand is built on:

- The palette is monochrome **for everything that carries meaning**; emphasis is luminance and
  weight, never a tint.
- Cold blue exists as **light, not as ink** — permitted in `box-shadow`, `radial-gradient`, and SVG
  `stroke` on decorative geometry. Forbidden as `color`, `background-color`, any status colour, any
  CTA fill. Peak alpha `0.28`, stroke or shadow only (`color.css:153-165`).
- Trade semantics are *the only other colour*: `--color-success: #7fd8a8` and
  `--color-danger: #f08a9c`, both deliberately desaturated "so they read as data"
  (`color.css:77-84`).
- Every status also carries a text label "so the page survives greyscale and colour-blindness"
  (`color.css:24-25`).
- Nothing carrying text may fall below **4.5:1** (`color.css:27-30`).

The `cyan-as-ink` rule in `website/scripts/check-design-tokens.mjs` enforces the blue boundary
mechanically, so it "cannot drift back into the palette one component at a time".

**This doctrine transfers to the dashboard in full.** It is not a marketing constraint — it is the
reason the product reads as an instrument rather than as a crypto dashboard.

### 8.2 The nine rules for the operational surface

**R1 — The brand accent must never mean profit.**
Today the dashboard's brand accent *is* orange and orange is simultaneously the logo, the active nav
item, the focus ring, the table row hover, the scrollbar, the progress fill, the "online" status dot
and the section-header underline. A colour that means "our brand", "you are here", "this is
focused", "this is healthy" and "this is a warning" at once means nothing. In the target system the
brand accent is **white**, exactly as on the site (`--color-accent: #ffffff`), and white means
*action / emphasis / focus* — never a market or system outcome.

**R2 — Green is reserved for a positive financial or system state.** Profit, a healthy connection, a
passed check. Nothing decorative may be green.

**R3 — Red is reserved for loss, a critical fault, or a destructive action.** Nothing decorative may
be red. A red that also decorates trains the eye to ignore red.

**R4 — Warning must be distinguishable from the brand accent.** This is the direct trap in the
current system: `--qf-accent` (orange) is *also* `.badge-warn` and *also* `.qf-progress.warn`. Once
the accent becomes white, warning needs its own value — and it must not be a second yellow-orange
that re-imports the old identity through the back door. See §8.3.

**R5 — `frozen`, `disabled`, `stale`, `paused` and `disconnected` are five different states and must
be five different renderings.** The current CSS collapses all inactive states onto
`--qf-text-muted` with no dot, no label distinction and no timestamp. A frozen strategy is a
deliberate decision; a stale feed is a fault; a disconnected broker is an outage; a paused engine is
an operator action. Rendering them identically is the difference between "the system is working as
configured" and "you are trading blind".

**R6 — Colour is never the sole carrier of meaning.** Every status renders as
`dot + text label`, and the text label must survive greyscale. This is already the site's rule
(`color.css:24-25`) and the reference honours it — its pills read «Активная», «Заморожена»,
«Планируется» in words.

**R7 — Chart series colour must not imply a verdict.** The current equity chart draws a **green**
area line while its own header reports **−80 776,12 ₽ (−8,08 %)** in red. A green line under a
losing curve is a false positive signal read before any number is. Series colour encodes *identity*
(which series), not *outcome* (good/bad). Outcome is encoded by the value's own sign colour, by the
zero baseline, and by fill direction relative to that baseline.

**R8 — Decorative glow must never resemble an active system state.** The dashboard currently applies
`box-shadow: 0 0 8px var(--qf-accent-glow)` with a 2 s infinite `pulse-dot` to the "online"
indicator, and the same glow language to the logo mark on hover. A pulsing glow is the strongest
attention signal a dark UI has; spending it on "nothing is wrong" leaves nothing in reserve for
"something is wrong". On the site the cold-blue glow is explicitly *decorative light* — on the
terminal, glow is either removed or reserved for genuine alerts.

**R9 — Cold blue does not enter the terminal as ink.** It may appear on the sign-in surface and on
empty-state illustration geometry as a stroke, at ≤0.28 alpha, to keep brand continuity. It may
never colour a metric, a status, a chart series or a control.

### 8.3 Proposed semantic palette — derived from the site, not invented

Every value below is either an existing site token or a value chosen to sit inside the site's stated
contrast floor. Nothing here is a new hue family.

#### Surfaces — direct adoption from the site

| Role | Token | Value | Source |
|---|---|---|---|
| App ground | `--qf-bg` | `#030303` | `--color-bg` |
| Shell chrome (sidebar, topbar) | `--qf-surface` | `#0a0a0a` | `--color-surface` |
| Panel / card | `--qf-panel` | `#111111` | `--color-panel` |
| Panel raised (hover, selected row) | `--qf-panel-raised` | `#171717` | `--color-panel-raised` |
| Nested row inside a panel | `--qf-graphite` | `#131313` | `--color-graphite` |
| Hairline border | `--qf-border` | `rgba(255,255,255,0.10)` | `--color-border` |
| Interactive edge | `--qf-border-strong` | `rgba(255,255,255,0.35)` | `--color-border-strong` |

This replaces the current five-step blue-tinted ramp (`#050508 → #08090d → #0c0e14 → #111318 →
#161a22 → #1c212b`). Note that the current ramp is *not* neutral — every step carries a blue cast
(B > R in every value), which is why the dashboard reads cooler and cheaper than the site's true
neutrals at the same luminance.

#### Text — direct adoption, ratios already certified

| Role | Value | Ratio on `#030303` |
|---|---|---|
| Primary | `#ffffff` | 20.4:1 |
| Secondary | `rgba(255,255,255,0.72)` | 10.4:1 |
| Tertiary | `rgba(255,255,255,0.56)` | 6.5:1 |
| Quaternary — hard floor | `rgba(255,255,255,0.48)` | 4.9:1 |

**Nothing below 0.48 alpha may carry text.** The current `--qf-text-muted: #5e6673` is used for every
metric label, every table header, every timestamp and every empty-state description. On `#111318` it
measures ≈3.4:1 — below AA for normal text, and it is applied at 10–11px with `letter-spacing:
0.05–0.07em` and `text-transform: uppercase`, which is the least legible configuration available.
That single token is the largest accessibility defect in the interface.

#### Financial semantics — adopt the site's desaturated pair

| Role | Value | Replaces | Rationale |
|---|---|---|---|
| Profit / long / healthy | `#7fd8a8` (11.6:1) | `#00c076` | `#00c076` is a saturated Binance green measuring ≈5.9:1 on `#111318`. It reads as a *brand* colour and competes with the data. |
| Loss / short / critical | `#f08a9c` (8.9:1) | `#f6465d` | `#f6465d` measures ≈4.6:1 — barely AA, and at 11px in a dense table it vibrates against the dark ground. |
| Dimmed fills | `rgba(127,216,168,0.14)` / `rgba(240,138,156,0.14)` | `…,0.12` | Match the site's `--color-success-dim` / `--color-danger-dim`. |

There is a legitimate objection: desaturating long/short weakens the instant red/green read a trader
relies on. The answer is that the *distinction* is preserved (hue separation is unchanged) while the
*loudness* drops, and the pair is reinforced by sign (`+`/`−`), by direction arrows, and by
right-aligned tabular figures. The site's values are 11.6:1 and 8.9:1 — both are **more** legible
than the current pair, not less. This should still be confirmed with the product owner (§35, D‑04).

#### Neutral / non-financial statuses — the new work

The site has exactly one neutral status token, `--color-neutral: #8a8a8a` (5.6:1). A terminal needs
a graded set. All values below are achromatic or minimally tinted, and all clear 4.5:1 on `#030303`:

| State | Value | Dot | Required text label | Meaning |
|---|---|---|---|---|
| `healthy` | `#7fd8a8` | filled | «Работает» | Fresh data, connection up |
| `degraded` | `#d9c187` (11.2:1) | filled | «Деградация» | Working but outside normal parameters |
| `stale` | `#8a8a8a` | hollow ring | «Устарело · 14 мин» | Last update older than the widget's threshold |
| `paused` | `#8a8a8a` | square | «Пауза (оператор)» | Deliberate operator action |
| `frozen` | `#8a8a8a` | hollow ring + diagonal | «Заморожена» | Deliberate strategy state — *not* a fault |
| `disconnected` | `#f08a9c` | hollow ring | «Нет связи» | Transport down |
| `failed` | `#f08a9c` | filled | «Ошибка» | Operation errored |
| `unknown` | `#5e6673` on a lifted surface | dashed ring | «Неизвестно» | Never reported — must never render as "healthy" |

`#d9c187` is the one genuinely new value. It is a low-chroma warm grey, not an amber: it must read
as "attention" without reading as a brand colour. It is deliberately far from `#F7931A` in both
chroma and luminance so that no reviewer can mistake the new system for a survival of the old one.
Choosing it is a product-owner decision (§35, D‑05); the alternative — a pure achromatic warning
carried entirely by icon and label — is defensible and even more disciplined, at the cost of slower
peripheral detection.

#### What is deleted outright

| Token | Value | Disposition |
|---|---|---|
| `--qf-accent` and its four relatives | `#F7931A`, `#e07d0a`, `#c9701a`, `#ff9e24` | **Removed.** 17 hardcoded occurrences of `#F7931A` alone, plus the `rgba(247,147,26,·)` family. Replaced per-role: brand→white, focus→white ring, hover→`--qf-panel-raised`, progress→role colour, warn→`degraded`, "online"→`healthy`. |
| `--qf-blue` | `#3861fb` | **Removed.** A saturated ink blue is the single most direct violation of the `cyan-as-ink` rule. |
| `--qf-purple` | `#8b5cf6` | **Removed.** 11 occurrences. No semantic meaning exists for purple in this product. |
| `--qf-cyan` | `#06b6d4` | **Removed as ink.** If a cold accent is wanted, it is `--color-signal #7cc8ff` as *stroke or shadow only*, ≤0.28 alpha. |
| `#f7c948`, `#ff4d4d`, `#bac`, and the remaining ad-hoc literals | — | **Removed.** 36 distinct hex literals across 129 occurrences currently exist in the dashboard's CSS/JS. Target: zero literals outside the token file. |

### 8.4 Contrast obligations

WCAG 2.2 AA is the floor, matching the site's own stated floor:

- Body and data text ≥ **4.5:1**.
- Text ≥18.66px bold or ≥24px regular ≥ **3:1**.
- Non-text UI: control borders, focus indicators, chart series strokes, status dots ≥ **3:1** against
  their adjacent surface. The current `--qf-border: rgba(255,255,255,0.07)` measures ≈1.3:1 and
  fails this for any border that delimits an interactive control; `--color-border-strong` at 0.35
  exists on the site precisely for that case.
- Focus indicator ≥ **3:1** against both the focused element and its background, ≥2px thick.

Every one of these must be an automated check in CI, not a review opinion — the site already proves
the pattern works (`website/scripts/check-design-tokens.mjs`). See §34.

### 8.5 The greyscale test

The acceptance test for the whole colour system is one screenshot. Render each screen in greyscale.
If a trader can still answer *"is anything wrong, and is my position up or down"*, the system passes.
If they cannot, colour is doing work that a label, an icon, a sign or a position should be doing.

Applied to the current Overview, it fails in at least three places: the broker list distinguishes
Online from Offline by hue alone; the equity header distinguishes profit from loss by hue alone; and
the risk gauge's arc encodes severity by hue alone.


---

## 9. Typography and Numerical Data Audit

### 9.1 The two type systems side by side

| | Site (shipped) | Dashboard (shipped) |
|---|---|---|
| Interface / display face | **Geist**, self-hosted via `next/font`, latin + cyrillic, no runtime request | **Inter**, fetched from `fonts.googleapis.com` at runtime (`bot/ui/templates/dashboard.html:9`) |
| Mono face | **Geist Mono**, self-hosted | **JetBrains Mono**, Google Fonts |
| Third face | none — *"No serif: the previous Cormorant accent … cost four extra font files on every request"* (`typography.css:1-7`) | **Orbitron** 500/700, a decorative display face, loaded from Google Fonts on every page load (`dashboard.html:11`) |
| Number of type roles | **6 + 2**, enforced | **8 raw sizes** (`--qf-text-xs` 11 → `--qf-text-3xl` 36) plus ad-hoc literals |
| Enforcement | `scripts/check-design-tokens.mjs` fails the build on arbitrary `text-[Npx]` | none |
| Tabular figures | to be confirmed per §7 | **absent** — no `font-variant-numeric` anywhere in `bot/ui/static` |

Four observations follow directly.

**Two different typefaces means two different products.** Geist and Inter are both neo-grotesques and
a casual observer might not name the difference, but their Cyrillic drawing, their metrics and their
tone are not the same. A user moving from the marketing site to the terminal will feel a
discontinuity they cannot articulate. Adopting Geist + Geist Mono is the single highest
brand-alignment-per-effort change available in the entire audit — one `@font-face` block and two
token values.

**The dashboard pays a render-blocking, third-party font cost the site deliberately eliminated.**
Three Google Fonts requests (`preconnect` + two stylesheet links) before first paint, against the
site's zero. The site's own comment states the reasoning.

**Orbitron is loaded and must be justified or removed.** It is a wide, geometric, sci-fi display face
— categorically incompatible with a brand whose reference is austere and institutional. If it is
used only by the Quant Hunter mini-app, it must not be loaded by the main terminal document.

**Eight sizes is not a scale, it is a menu.** The site's system exists precisely because a previous
version *"declared three fixed and three fluid steps but shipped 13 distinct rendered sizes"*
(`typography.css:6-11`). The dashboard is in that pre-reform state.

### 9.2 The numeric-typography defect — the most consequential finding in this section

**No tabular figures anywhere.** The dashboard sets numeric cells in JetBrains Mono
(`.qf-table td.num`, `.ticker-cell`, `.price-cell`, `.qf-metric-value`, `.qf-strip-value`,
`.stat-val` in `design-system.css`), which is a monospaced face, so *within those cells* digits do
align. But every proportional-font numeric — every metric tile value that is not `.num`, every
inline figure in a card body, every value in a `stat-row` — is set in Inter without
`font-variant-numeric: tabular-nums`. Inter's default figures are proportional: `1` is narrower than
`8`. A column of proportionally-set numbers cannot be scanned vertically, and a value that
re-renders on a poll will *shift horizontally* as digits change.

The correct rule is not "use a mono face for numbers". It is:

```
font-variant-numeric: tabular-nums lining;
```

on every numeric context, in **both** faces. Mono is then a *semantic* choice (identifiers, tickers,
raw values, code) rather than a workaround for a missing OpenType feature.

Secondary numeric defects visible in the shipped UI:

- `letter-spacing: -0.01em` is applied to `.qf-strip-value` and `.qf-table td.num`
  (`design-system.css:286, 818`). Negative tracking on tabular figures partially defeats the
  alignment the mono face was chosen to provide.
- The balance tile renders `1 038 050,` on one line and `₽` on the next at 1600 px. The currency
  symbol is being treated as part of the wrapping text run. A monetary value and its unit are one
  atom and must never break.
- `SHARPE 252Д` displays `—` and `RISK · ПРОСАДКА` displays `—`, while `PNL СЕГОДНЯ` displays
  `+0,00 ₽`. Three different renderings of "there is no data": an em dash, a zero with a plus sign,
  and (elsewhere) an empty cell. `+0,00 ₽` is the dangerous one — it asserts a measured result of
  zero where none was measured.

### 9.3 Formatting rules — the specification

Locale is `ru-RU`: space as the thousands separator (U+00A0, non-breaking), comma as the decimal
separator. Every rule below applies identically in every view; the current code formats the same
quantity differently in different places (see the frontend dossier's `core/format.js` findings).

| Quantity | Format | Precision | Sign | Notes |
|---|---|---|---|---|
| **PnL (money)** | `+12 480,50 ₽` / `−3 200,00 ₽` | 2 dp always | Always explicit `+` / `−` (U+2212 minus, not hyphen) | Colour by sign, but the sign carries it in greyscale. Never `0,00` when the value is unknown. |
| **PnL (%)** | `+1,24 %` | 2 dp | explicit | NBSP before `%`. |
| **PnL (R)** | `+1,8R` / `−1,0R` | 1 dp | explicit | `R` is a unit, never a colour. Requires `trades.pnl_r` — **absent from the live DB**. |
| **Equity / balance** | `1 038 050,00 ₽` | 2 dp | none | Never abbreviated to `1,04M` on a trading surface. |
| **Drawdown** | `−8,08 %` and `−80 776,12 ₽` | 2 dp | always negative or `0,00 %` | Must state its window: `макс. за 90 дней`. |
| **Profit factor** | `1,64` | 2 dp | none | `∞` when there are no losses **and** n ≥ threshold; otherwise `н/д`. Never `0`. |
| **Win rate** | `54,2 % (26 из 48)` | 1 dp | none | **The count is mandatory.** `0,00 %` from zero trades is currently indistinguishable from a genuine 0 % over 48 trades. |
| **Confidence** | `0,61 · выборка 12` | 2 dp | none | Never `61 %` — see §16, it is not a probability. Sample size is mandatory and inseparable. |
| **Position size** | `10 шт` / `0,25 BTC` | instrument precision | none | Lots vs units must be labelled per instrument. |
| **Entry / current price** | `299,50` | instrument tick size, not a global 2 dp | none | Ticker's own precision. `29,9500` for a 4-dp instrument is not "more accurate", it is noise. |
| **Stop / take profit** | `287,30` + `−4,1 %` | tick size + 1 dp | distance signed | Always show **distance**, not just the level. |
| **Timestamp — recent** | `14:07:22` | seconds | — | Same-day only. |
| **Timestamp — older** | `28.07 14:07` | minutes | — | Day-month for the current year. |
| **Timestamp — absolute** | `2026‑07‑28 14:07:22 MSK` | — | — | On hover / in detail views. Timezone label is **never** optional. |
| **Data age** | `42 с` / `14 мин` / `1 ч 12 мин` | — | — | The staleness primitive. Relative, counting up, always paired with the absolute on hover. |
| **Latency** | `240 мс` | integer | — | Never sub-millisecond precision. |
| **Sample size** | `n = 12` or `выборка 12` | integer | — | Rendered in the *same visual unit* as the statistic it qualifies, never as a footnote. |

### 9.4 Timezone — an unresolved correctness question

The topbar renders `21:53:16 MSK`. The database stores `TIMESTAMPTZ`. Between those two there is a
conversion, and the audit could not establish from the UI alone whether it is applied consistently
to every rendered timestamp or only to the clock. Because `trades.opened_at`/`closed_at` and
`equity_snapshots` timestamps drive both the equity curve's x-axis and every "last event" figure, a
mismatch would silently shift the entire chart by three hours without any visible error.

**Requirement:** one timezone policy, declared once, applied at one boundary (server-side, into the
view model), with the tz label rendered next to every absolute time. Never convert in two places.
Never render a naive datetime.

### 9.5 Casing, labels and density

- Uppercase + `letter-spacing: 0.05–0.07em` is applied to every metric label, every table header and
  every strip label at 10–11px (`.qf-metric-label`, `.metric-mini-label`, `.qf-strip-label`,
  `.as-label`, `table thead th`). Uppercase Cyrillic at 10px with positive tracking, in
  `--qf-text-muted` (≈3.4:1), is the least legible combination the system can produce, and it is
  used for *every label on every screen*. The site's equivalent role, `--text-label`, is 11px with
  `0.14em` tracking but is used **sparingly**, as an eyebrow — not as the default label style.
- **10px text should not exist.** `.metric-mini-label`, `.qf-strip-label`, `.qf-strip-sub`,
  `.as-label` and `.tp-more` (9px) are all below any reasonable floor. Minimum for any text carrying
  meaning: **12px**; the site's own floor for a caption is 13px.
- Labels are inconsistently bilingual: the nav is English (`Dashboard`, `Portfolio`, `Signals`,
  `Backtest`, `Analytics`, `Learning`, `Settings`) while the content is Russian (`ОБЩИЙ БАЛАНС`,
  `Активные позиции`, `Риск-метрики`, `Последние сигналы`, `Брокеры`). The site is fully bilingual
  with `messages/ru.json` + `messages/en.json`; the dashboard is `lang="ru"` with hardcoded strings
  and an accidental English nav. Pick one and mean it.

### 9.6 Target type scale for the terminal

Derived from the site's roles, compressed where operational density requires it. Six roles, and the
build must fail on a seventh.

| Role | Size / line-height / tracking | Face | Used for |
|---|---|---|---|
| `label` | 11px / 1.4 / `0.14em`, uppercase | Geist Mono | Eyebrows and section labels **only** — not every field label |
| `caption` | 12px / 1.45 / `0` | Geist | Table cells, metadata, timestamps, field labels |
| `body` | 14px / 1.55 / `-0.006em` | Geist | Card body, descriptions, reasons |
| `metric` | 20px / 1.15 / `-0.02em`, tabular | Geist | Panel metric values |
| `metric-lg` | 28px / 1.05 / `-0.03em`, tabular | Geist | The two or three hero values on a screen |
| `heading` | 16px / 1.3 / `-0.02em`, 600 | Geist | Panel and section titles |

Note the deliberate divergences from the site: the terminal's `body` is 14px rather than 16px and
its `caption` is 12px rather than 13px, because a terminal's job is density. The *relationships* —
the ratios, the tracking direction, the single-family discipline — are preserved, which is what makes
it read as the same product. Copying the site's absolute sizes into a data grid would produce a
marketing page with tables in it.


---

## 10. Layout and Density Audit

### 10.1 Current shell

Sidebar 240px (64px collapsed), topbar 52px, fluid main with no maximum width, per-view ad-hoc
grids (`analytics-charts-row` is `2fr 1fr`; `analytics-bottom-row` is `1fr 1fr 1fr`), 10px gaps.
There is no shared left edge between views and no content ceiling, so on a 2560px monitor a
three-column card row stretches to 800px per card.

### 10.2 The density problem, stated precisely

The Overview spends its entire first fold on **six tiles, five of which display no value**
(`+0,00 ₽` ×3, `—` ×2). Below them a 280px chart shows the wrong series. The first genuinely useful
row — open positions — begins below the fold at 1440×900. Meanwhile the panels themselves are
*tight*: 7px cell padding, 10–11px uppercase labels, 4px scrollbars.

That combination — **generous where nothing is shown, cramped where data is shown** — is the exact
inversion of what a terminal needs, and it is why the interface simultaneously reads as empty and
feels cluttered.

> Minimalism on a dashboard is not empty space. It is the absence of elements that do not answer a
> question, at the highest clarity the data allows.

### 10.3 Target density model

| Context | Row height | Body / caption | Panel padding | Card gap | Above-fold rows | Max width |
|---|---|---|---|---|---|---|
| Desktop workstation ≥1680 | 28px compact | 14 / 12 | 16 / 12 | 12 | ≥14 | none (12-col) |
| Laptop 1280–1679 | 32px | 14 / 12 | 16 / 12 | 12 | ≥10 | none |
| Tablet 768–1279 | 36px | 15 / 13 | 16 | 16 | ≥6 | 1024 |
| Mobile monitoring <768 | 44px card rows | 15 / 13 | 16 | 12 | 3 blocks | 100 % |

Recommended region sizes (documentation, not CSS): sidebar 240 expanded / 64 rail; topbar 48;
environment band 36; fault row 44 each; panel header 40; chart panel 240–320 with the panel, not the
canvas, owning the height; table viewport ≥8 rows before internal scroll; **never nest a scroll
inside a scroll inside a scroll** — the current `.paper-feed` (`max-height: 220px; overflow-y:auto`)
sits inside a card inside the main scroll.

---

## 11. Navigation Audit

**Current model.** Persistent 240px sidebar, three groups (TRADING / APPS / SYSTEM), 8 items,
collapse toggle, keyboard `1`–`8`, tooltips via a body-level portal. No tabs, no breadcrumbs beyond
a static "Overview · Live" string, no routing, no mode indicator, no account context.

**Defects.**

1. **No URL state** (F‑IA‑03). Cannot bookmark, cannot deep-link an alert, cannot restore after
   reload, cannot open two views in two tabs. For an operational tool this is a functional gap, not
   a nicety.
2. **The keyboard handler hijacks browser shortcuts.** `app.js:167-178` calls `preventDefault()` on
   bare `r`/`R` and `1`–`8` **with no modifier guard**, so **⌘R / Ctrl+R page reload is blocked** and
   ⌘1–⌘8 tab switching is blocked.
3. **A game sits in the operational rail.** «Quant Hunter» is one keystroke from «Learning», and its
   assets are 21 % of the local payload on every load.
4. **The breadcrumb is a lie.** "Overview · Live" is static markup; it says *Live* while the system
   is in sandbox.
5. **No mode, no account, no environment** anywhere in the navigation chrome.

**Recommended model: persistent sidebar that collapses to a rail below 1360px, plus context tabs
inside data-heavy views.** Justification from the real sections: the target set is 9–11 items
grouped in three tiers, which is above the ~7-item ceiling where top navigation stays scannable;
several items (Positions, Orders, Trades) are sub-views of Portfolio and belong on context tabs, not
in the rail; and an operator needs the rail's persistent status affordances (per-item state dots)
that a top bar cannot carry. Add: URL routing, a permanent environment badge in the topbar, and
account context next to it.

---

## 12. Dashboard Screen Inventory and Target Structure

Each section below is justified before it is proposed. Sections that cannot be justified from real
data are named as such and deferred.

| Section | Keep / add? | Justification | Blocking dependency |
|---|---|---|---|
| **Overview** | **Keep, rebuild** | The 5-second question (§13) | Fault endpoint, engine state, mode |
| **Portfolio** | **Keep** | Equity, cash, exposure, attribution | Real equity series (§27) |
| **Positions** | **Split out of Portfolio** | Distinct task, distinct cadence, needs its own filters and a close action that currently has no UI (F‑IA‑07) | Quote timestamps |
| **Orders** | **Defer** | No order table exists; `broker_order_id` is a column on `trades`, not an entity | New schema |
| **Trades** | **Keep, fix** | 35 paper trades exist and render as zero today | Envelope fix |
| **Signals** | **Keep, extend** | 8 rows exist; the gate decision is the missing half | `skipped_signals` must be populated |
| **Strategies** | **Add** | `belief_system` has 8 rows and is currently buried inside Learning | — |
| **Learning** | **Keep, reframe** | Real, but must stop over-claiming (§16) | `hypotheses` is empty |
| **Hypotheses** | **Fold into Learning** | 0 rows. A dedicated section for an empty table is a promise the product cannot keep | Data |
| **Sandbox / Forward Testing** | **Not a section — a filter** | Environment is an attribute of every row, not a place. Making it a section guarantees someone reads a live number on a sandbox screen | `is_sandbox` filtering everywhere |
| **Risk** | **Add** | Promised by the marketing site; today drawdown is wrong by two orders of magnitude and exposure is on the Overview only | Correct drawdown units |
| **System Health** | **Add** | 22-scenario audit: 8 failures are health questions | Health model (§20) |
| **Event Log** | **Add** | `system_events` = 0 rows, `audit_events` = 12 rows all `auth.denied`. Nothing is recorded, so nothing can be reviewed | Event writing must exist first |
| **Notifications** | **Defer** | Telegram delivery status is not exposed by any endpoint | New endpoint |
| **Settings** | **Keep, harden** | Currently writes broker credentials with no confirmation | §19, §26 |
| **Quant Hunter** | **Remove from the operational rail** | A game. Move to a separate route, lazy-load its 67 KB | — |

Per-section specification (goal, user, key question, primary/secondary metrics, tables, charts,
filters, actions, and the five required states) is carried in §21 for states and §28 for data
contracts, to avoid restating the same matrix three times.


---

## 13. Overview Screen — Detailed Future Specification

This is documentation. Nothing here is implemented in this session.

### 13.1 The five-second question

A trader opening the terminal is not asking *"how much money do I have"*. They are asking, in this
order:

1. **Is the system actually running, and is what I'm looking at current?**
2. **Am I exposed, and how badly can it hurt?**
3. **Did anything happen that I need to act on?**
4. *Then*, and only then: how is the account doing?

The current Overview answers these in reverse. Its first and largest element is ОБЩИЙ БАЛАНС; engine
state is not shown at all; sandbox-vs-live is not shown at all; data freshness is a small grey
timestamp in the topbar. The site's own preview gets this right — its overview panel leads with
`ДВИЖОК`, `РЕЖИМ`, `ТИКЕРОВ В ОЧЕРЕДИ`, `ПОСЛЕДНЕЕ СОБЫТИЕ`
(`website/src/components/sections/dashboard/dashboard-terminal.tsx`). The redesign must adopt the
site's ordering, because the site's ordering is correct.

### 13.2 Status hierarchy — three tiers, and only three

**Tier 1 — Environment banner.** Persistent, full-width, immediately under the topbar. Never
dismissible. States what environment you are in and what the engine is doing:

```
ПЕСОЧНИЦА · Т-Банк · Движок: ПАУЗА (оператор, 14:02) · Данные: 42 с назад
```

In `LIVE` this band inverts to the paper surface (`#f4f2ec` ground, `#0a0a0a` ink) — the one place
the site's inverted-band device earns its keep on an operational screen, because "you are trading
real money" deserves a visual discontinuity that no dark-on-dark treatment can deliver. This is a
brand device converted into a safety device.

**Tier 2 — Unmissable faults.** A single stacked region directly beneath. Zero rows when healthy;
the region collapses entirely. One row per fault, each carrying: state chip, subject, human reason,
timestamp, and one recommended action. Never more than five; a sixth collapses into "+N more →".

**Tier 3 — Everything else.** Normal panels, which may only render *fresh* data or an explicit
non-fresh state.

### 13.3 Above the fold — the contract

At 1440×900 with the sidebar expanded, the following must be visible without scrolling. Anything not
on this list is below the fold by design.

| Priority | Element | Why it earns the space |
|---:|---|---|
| 1 | Environment + engine + data-age band | Answers "is this real and is it current" |
| 2 | Fault region (zero-height when healthy) | Answers "do I need to act" |
| 3 | Risk & exposure block | Answers "how badly can this hurt" |
| 4 | Open positions table (first 5 rows) | The actual object of attention |
| 5 | Equity sparkline + today's PnL | Account state, compressed |
| 6 | Last signal + its gate decision | Answers "did the system just do something" |
| 7 | System health strip | Six services, one line |

Removed from above the fold relative to today: the four-across PNL tile row (today/week/month were
each `+0,00 ₽` — three tiles spending ~40 % of the fold to say "nothing happened"), the Sharpe tile
(`—`, no data), and the oversized balance tile.

### 13.4 Desktop wireframe — 1440×900, sidebar expanded

```
┌────────────┬──────────────────────────────────────────────────────────────────────────────┐
│ ▸ QUANT    │ Обзор                                        14:07:22 MSK   [↻]  [Профиль ▾] │
│            │ Терминал · Т-Банк                                                            │
│ ТОРГОВЛЯ   ├──────────────────────────────────────────────────────────────────────────────┤
│ ▪ Обзор    │  ПЕСОЧНИЦА · Движок: ПАУЗА (оператор, 14:02) · Данные: 42 с            [Стоп]│
│   Портфель ├──────────────────────────────────────────────────────────────────────────────┤
│   Позиции  │  ⬤ НЕТ СВЯЗИ   Bybit — не отвечает 8 мин            14:59   [Переподключить] │
│   Сигналы  │  ○ УСТАРЕЛО    Свеча SBER H1 — 71 мин назад         13:56   [Открыть данные] │
│   Стратегии├──────────────────────────────────────────────────────────────────────────────┤
│   Бэктест  │ ┌── РИСК И ЭКСПОЗИЦИЯ ────────────┐ ┌── ОТКРЫТЫЕ ПОЗИЦИИ ─────── 1 из 5 ───┐ │
│   Аналитика│ │ Экспозиция   142 300 ₽   13,7 % │ │ ТИКЕР  НАПР  КОЛ  ВХОД   ТЕК   ДО SL │ │
│            │ │ Риск в рынке   8 400 ₽    0,8 % │ │ SBER   LONG   10  299,50 299,50 −2,1%│ │
│ СИСТЕМА    │ │ Просадка          —      н/д    │ │                                      │ │
│   Обучение │ │ Позиции         1 / 5           │ │ ○ нет данных о котировке 71 мин      │ │
│   Здоровье │ │ Дневной лимит   не задан        │ │                                      │ │
│   Журнал   │ └─────────────────────────────────┘ └──────────────────────────────────────┘ │
│   Настройки│ ┌── КАПИТАЛ ──────────────────────┐ ┌── ПОСЛЕДНИЙ СИГНАЛ ──────────────────┐ │
│            │ │ 1 038 050,00 ₽        песочница │ │ 13:00  SBER  LONG  trend_moex        │ │
│ ────────── │ │ ▁▂▃▅▄▆▇▆▅▃▂▁▂▃▄▅▄▃▂▁  90 точек  │ │ ⬤ ОТКЛОНЁН риск-шлюзом               │ │
│ Daniil     │ │ Сегодня  0,00 ₽    ·   0,00 %   │ │ Превышен дневной лимит позиций       │ │
│ Оператор   │ │ 90 дней −80 776,12 ₽ · −8,08 %  │ │ Уверенность 0,61 · выборка 12        │ │
│            │ └─────────────────────────────────┘ └──────────────────────────────────────┘ │
│ 1–9 · R    │ ┌── ЗДОРОВЬЕ СИСТЕМЫ ────────────────────────────────────────────────────┐  │
│ [‹ Свернуть│ │ БД ⬤  Свечи ○71м  Т-Банк ⬤  Bybit ⬤  Форвард ⬤  Telegram ⬤  API 240мс │  │
│            │ └────────────────────────────────────────────────────────────────────────┘  │
└────────────┴──────────────────────────────────────────────────────────────────────────────┘
```

Notes on the wireframe:

- The fault region shows two rows here to demonstrate the pattern. **When everything is healthy it
  has zero height** — it must not degrade into a permanent green "all clear" band, which would
  become invisible within a day.
- «ДО SL» (distance to stop) is shown instead of a second price column. Distance to stop is the only
  number on the row that tells a trader how much room they have; the current UI shows entry and
  current price and makes the trader subtract.
- The position row carries its own staleness marker. A price that is 71 minutes old must not render
  as if it were live, and it must not be the *panel* that is marked stale — the *cell* is stale.
- «Уверенность 0,61 · выборка 12» — confidence never appears without its sample size (§16).
- The equity block shows both the day and the window, and labels the window («90 дней»). Today the
  header reads "90 точек · −80 776,12 ₽ (−8,08 %)" — "points" is an implementation detail and the
  period is unstated.
- Sidebar gains «Позиции», «Стратегии», «Здоровье», «Журнал» and renames «Dashboard»→«Обзор». It
  loses «Quant Hunter» from the operational rail (§12).

### 13.5 Laptop wireframe — 1280×800, sidebar collapsed to a rail

Below 1360px the sidebar collapses to a 64px icon rail by default. The two-column body becomes a
priority stack: risk and positions stay side by side; capital and last-signal drop to full width.

```
┌──┬───────────────────────────────────────────────────────────────────────────┐
│▸ │ Обзор · Терминал · Т-Банк                    14:07:22 MSK   [↻] [Профиль ▾]│
│  ├───────────────────────────────────────────────────────────────────────────┤
│▪ │ ПЕСОЧНИЦА · Движок: ПАУЗА · Данные: 42 с                            [Стоп] │
│▫ ├───────────────────────────────────────────────────────────────────────────┤
│▫ │ ⬤ НЕТ СВЯЗИ  Bybit — не отвечает 8 мин          14:59  [Переподключить]    │
│▫ ├──────────────────────────────┬────────────────────────────────────────────┤
│▫ │ РИСК И ЭКСПОЗИЦИЯ            │ ОТКРЫТЫЕ ПОЗИЦИИ                   1 из 5  │
│▫ │ Экспозиция  142 300 ₽  13,7 %│ SBER  LONG  10  299,50  299,50  −2,1 %  ○  │
│  │ Риск          8 400 ₽   0,8 %│                                            │
│▫ │ Просадка         —      н/д  │                                            │
│▫ │ Позиции       1 / 5          │                                            │
│▫ ├──────────────────────────────┴────────────────────────────────────────────┤
│  │ КАПИТАЛ  1 038 050,00 ₽  песочница   ▁▂▃▅▄▆▇▆▅▃▂▁  сегодня 0,00 ₽ · 0,00 %│
│  ├───────────────────────────────────────────────────────────────────────────┤
│  │ ПОСЛЕДНИЙ СИГНАЛ  13:00 SBER LONG trend_moex  ⬤ ОТКЛОНЁН риск-шлюзом      │
│  ├───────────────────────────────────────────────────────────────────────────┤
│  │ БД ⬤  Свечи ○71м  Т-Банк ⬤  Bybit ⬤  Форвард ⬤  Telegram ⬤  API 240 мс   │
└──┴───────────────────────────────────────────────────────────────────────────┘
```

### 13.6 Mobile monitoring wireframe — 390×844

Mobile is **monitoring, not operating**. The only action permitted is the emergency stop, and it is
behind a typed confirmation (§19). No table is horizontally scrolled; rows become cards.

```
┌─────────────────────────────────┐
│ ☰  Quant · Обзор          14:07 │
├─────────────────────────────────┤
│ ПЕСОЧНИЦА                       │
│ Движок: ПАУЗА · Данные: 42 с    │
├─────────────────────────────────┤
│ ⬤ НЕТ СВЯЗИ                     │
│ Bybit — не отвечает 8 мин       │
│ 14:59        [Переподключить →] │
├─────────────────────────────────┤
│ ○ УСТАРЕЛО                      │
│ Свеча SBER H1 — 71 мин назад    │
├─────────────────────────────────┤
│ ЭКСПОЗИЦИЯ                      │
│ 142 300 ₽              13,7 %   │
│ Риск в рынке   8 400 ₽   0,8 %  │
│ Позиции                 1 / 5   │
├─────────────────────────────────┤
│ ОТКРЫТЫЕ ПОЗИЦИИ          1     │
│ ┌─────────────────────────────┐ │
│ │ SBER            LONG · 10шт │ │
│ │ Вход 299,50   Тек 299,50 ○  │ │
│ │ До стопа            −2,1 %  │ │
│ │ PnL                 0,00 ₽  │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ КАПИТАЛ                         │
│ 1 038 050,00 ₽       песочница  │
│ Сегодня      0,00 ₽ ·  0,00 %   │
│ ▁▂▃▅▄▆▇▆▅▃▂▁▂▃▄▅▄▃▂▁            │
├─────────────────────────────────┤
│ ПОСЛЕДНИЙ СИГНАЛ                │
│ 13:00 · SBER · LONG             │
│ ⬤ ОТКЛОНЁН риск-шлюзом          │
│ Превышен дневной лимит позиций  │
├─────────────────────────────────┤
│ ЗДОРОВЬЕ                        │
│ БД ⬤   Свечи ○   Т-Банк ⬤       │
│ Bybit ⬤  Форвард ⬤  TG ⬤        │
├─────────────────────────────────┤
│      [ ОСТАНОВИТЬ ТОРГОВЛЮ ]    │
└─────────────────────────────────┘
```

The emergency stop is the only control on the mobile Overview, it is placed last so it cannot be hit
while scrolling, it uses the danger token as an **outline** rather than a fill (a red-filled button
at the end of every scroll is an accident waiting to happen), and it requires typed confirmation.

### 13.7 Block-by-block specification

| Block | Answers | Data source today | Gap |
|---|---|---|---|
| Environment band | "Am I in sandbox or live? Is the engine running?" | `/api/platform/engine/status` exists; sandbox flag from `config` — **not currently surfaced in the UI at all** | New view-model field; no schema change |
| Fault region | "Do I need to act right now?" | No aggregate fault endpoint exists | **New backend endpoint required** (§28) |
| Risk & exposure | "How badly can this hurt?" | `/api/platform/risk/status`; positions from `/api/platform/portfolio/positions` | Drawdown and daily limit are **not in the schema** — derived or roadmap |
| Open positions | "What am I holding?" | `/api/platform/portfolio/positions`, `paper_positions` (live rows exist) | «До стопа» is derived; per-cell quote age requires a quote timestamp — **new field** |
| Capital | "How is the account doing?" | `/api/equity` over `equity_snapshots` (**16 016 rows — the one well-populated series**) | Period labelling only |
| Last signal + gate | "What did the system just decide, and why?" | `/api/platform/signals`; `trading_signals` (8 rows) | The *rejection reason* lives in `skipped_signals`, which has **0 rows** — the gate decision is currently unanswerable (§15) |
| System health | "Which parts are alive?" | `/api/platform/health`, `/api/platform/brokers` | Candle age, forward-runner state and Telegram delivery are **not exposed**; `forward_state` has **0 rows** |

### 13.8 What the Overview must never do

- Show a number without its unit, its currency, its period and its environment.
- Show an average without its sample size.
- Show a stale value styled identically to a fresh one.
- Render a failed endpoint as a zero. Today four Learning endpoints return HTTP 500 and the browser
  console is **clean** — the failure is swallowed and the user sees empty panels that are
  indistinguishable from "no data yet".
- Contradict itself across panels. The current Overview shows «3 открытых» in the balance tile,
  «Активные позиции 1» in the right rail, and «Позиции 3/5» in risk metrics — in one screenshot.
- Animate a value on every poll. Motion means *something changed*, and if everything animates
  every 5 seconds, nothing does.


---

## 14. Portfolio and Positions Audit

Availability legend: **A** = available today · **D** = derivable from available data · **B** = requires
broker API · **S** = requires a new schema field · **R** = roadmap.

| Requirement | Status | Evidence / note |
|---|---|---|
| Total equity | **A**, but wrong source | `paper_accounts.balance = 7 626 545,68` while the Overview tile shows `1 038 050 ₽` from the Tinkoff portfolio. Two different accounts under one label. |
| Available cash | **A** | `paper_accounts.available_balance = 12 359 136,94` — **greater than `balance`**, which is incoherent and must be reconciled before it is displayed. |
| Margin | **A** | `paper_accounts.margin_used = 2 995,00` |
| Unrealized PnL | **D** | Requires a mark price; the newest candle is **32 days old** |
| Realized PnL | **A** | `paper_trades`: 35 trades, **0 wins**, −2 373 454,32 |
| Daily PnL | **D** | Needs a session boundary + timezone policy (§9.4) |
| Drawdown | **A but broken** | Renders **−0,2 %** where the account is **−23,7 %** — `max_drawdown` carries two different units under one name |
| Exposure | **D** | Σ(position_size × mark) / equity |
| Concentration | **D** | Largest position as % of equity |
| Direction | **A** | `paper_positions` |
| Average entry | **A** | |
| Current price | **A but 32 days stale** | `candles.time` max = `2026-06-26`; DB now = `2026-07-28` |
| Stop | **A** | `trades.stop_loss` exists |
| **Distance to stop** | **D — and mandatory** | The single most useful derived number on a position row; not shown today |
| Strategy attribution | **A** | `trades.strategy_id` exists (46-column table) |
| Sandbox / live origin | **A but never used** | `is_sandbox` exists and is **filtered nowhere** — zero occurrences in `bot/ui/**` or `bot/qf_platform/**` outside DDL |
| Broker | **A** | |
| Stale quotes | **S** | No per-quote timestamp reaches the UI. Requires a `quote_ts` on the position DTO |
| Data timestamp | **S** | Every panel needs `as_of`; today only a global «обновлено» exists, and it lies (§5, scenario 17) |

**Required rendering rules.** Every position row shows: ticker · direction · size · avg entry ·
mark **with its age** · distance to stop (signed %) · unrealized PnL (₽ and R) · strategy · environment
chip. Any cell whose input is older than its threshold renders in the stale treatment — **the cell,
not the panel**. A position whose mark is 32 days old must be visually impossible to mistake for live.

---

## 15. Signals Audit

**What a "signal" is in this code.** `trading_signals` holds 8 rows and is **written by a GET
request** — `/api/platform/signals` INSERTs as a side effect of being read. So the signal table is
partly an artefact of dashboard polling, not purely of market events. That must be fixed before the
table is presented as a decision record.

**Target signal table.**

| Column | Source | Status |
|---|---|---|
| Timestamp (+ tz) | `trading_signals` | A |
| Ticker | `trading_signals` | A |
| Strategy | `trades.strategy_id` / rules engine | A |
| Direction | A | |
| Timeframe | `trades.timeframe` | A |
| Regime | `trades.market_regime` | A |
| Raw signal / rule hits | `trades.signal_rules`, `buy_score`, `sell_score` | A |
| **Confidence + sample size** | `belief_system.confidence`, `total_trades` | A — must never appear apart |
| Multiplier | risk manager | D |
| **Risk decision** | risk gateway | **S** |
| **Accepted / rejected / skipped** | `skipped_signals` | **Table exists, 0 rows** |
| **Reason** | `skipped_signals.reason` | **0 rows** |
| Resulting trade | `trades.trade_id` | A |
| Data freshness | candle age | **S** |
| Source candle | `candles.time` | A |

**The central gap.** Scenario 9 — *why was this signal rejected* — is the question the whole learning
narrative rests on, and it is **unanswerable from data**, not merely unrendered. `skipped_signals` is
empty. Until the risk gateway writes a row for every rejection with a machine-readable reason code
plus human text, no UI can answer it. **This is a Phase 0 backend task, not a design task.**

Six cases must be visually distinct, and today none of them are: accepted-and-filled;
accepted-but-unfilled (broker error); rejected by the risk gate; skipped by a filter;
duplicate-suppressed; errored. Note also that **`/api/tinkoff/positions` returned HTTP 502 thirty-one
times** in one logged session (broker DNS failure) — the "accepted but not filled" case is real and
frequent.

**Naming.** Never label this "AI confidence". It is a statistical confidence per strategy, derived
from that strategy's own trade history. See §16.

---

## 16. Strategies and Learning Audit

**Real entities:** `belief_system` (8 rows: `strategy_id, confidence, win_rate, total_trades,
profit_factor, expectancy, sharpe_ratio, best_regime, updated_at`), `hypotheses` (**0 rows**),
`trades.decision_quality` / `randomness_factor` / `strategy_followed` (columns exist; **2 trades**).

**The honesty problem.** The dashboard renders a "Learning" section whose underlying population is 2
trades and 0 hypotheses, alongside strategy statistics computed from `trades` (2 rows) while the
account actually executed 35 paper trades. A win rate over n=2 is not a statistic; presented in the
same visual weight as a real metric, it is a fabrication.

**Nine binding principles for the future UI.**

1. Confidence is **not** the probability of a profitable trade. Label it, in the UI, as a
   strategy-level statistical score.
2. Confidence renders **only** as `0,61 · выборка 12`. The sample size is part of the value, not a
   tooltip.
3. Small samples are marked explicitly. Below a declared threshold (recommend n<30) the value renders
   in the tertiary text colour with an «мало данных» chip, and is **excluded from any ranking**.
4. Backtest, forward, sandbox and live confidence are **never** merged. Today nothing distinguishes
   them because `is_sandbox` is filtered nowhere.
5. Different `strategy_id` values are never visually merged. The hardcoded list
   (`['default_moex','osc_range_moex','osc_range_moex_d1_fwd','breakout_moex','trend_moex',
   'momentum_bybit','trend_bybit']`) must come from the database, not from a Python literal.
6. **Frozen ≠ broken.** A frozen strategy is a decision and renders as a neutral, shaped state with
   its reason and its freeze timestamp.
7. **No trades ≠ confidence 0.** Today `win_rate` renders `0,00 %` for both. They must be `н/д (0
   сделок)` and `0,0 % (0 из 14)` respectively.
8. Confidence changes need history and cause. A number that moved without an explanation is not
   evidence of learning; it is an unexplained mutation.
9. System confidence must never be styled like AI certainty — no gauges implying calibration, no
   percentages implying probability, no glow implying activity.

**Proposed views** — confidence timeline (needs a new `belief_history` table — **S**); sample
maturity (**D** from `total_trades`); strategy status board (**A**, plus a `frozen` flag — **S**);
regime breakdown (**A** via `best_regime`, thin); hypothesis lifecycle (**blocked — 0 rows**);
decision-quality distribution (**A** in schema, **n=2** in practice — do not ship a histogram of two
points).

**Recommendation:** rename the section «Стратегии», make the strategy board its primary content, and
place learning artefacts inside it as evidence. Ship the hypothesis lifecycle only when the table has
data.

---

## 17. Charts and Data Visualization Audit

**Correction to the brief: Chart.js is not used.** Repo-wide grep for `new Chart(`, `chart.js`,
`chartjs` returns zero hits. The two libraries are `lightweight-charts@4.2.0` and `echarts@5.5.0`,
both loaded synchronously in `<head>` from third-party CDNs
(`dashboard.html:14-15`), **both without `integrity=` (SRI)**, both with no local fallback.
ECharts alone is **1 029 203 B uncompressed**.

| # | Chart | Library | Question it should answer | Verdict |
|---|---|---|---|---|
| 1 | Equity Curve | lightweight-charts | "How is my capital doing?" | **Wrong data.** It renders a candle-derived path (SBER's price) relabelled as portfolio equity — 2025‑06‑26→2025‑09‑29, ending ₽919 224, while the paper account went ₽10 000 000 → ₽7 626 546. **Blocker.** |
| 2 | Ticker chart | lightweight-charts | Price context for a ticker | Justified, but every candle is ≥32 days old and nothing says so |
| 3 | Analytics charts | ECharts | Mixed | ECharts is loaded for these; 1 MB for a handful of panels is not justified |
| 4 | Radial gauge | CSS `conic-gradient` | Risk severity | Severity by hue only; unreadable in greyscale |

**Cross-cutting defects.**

- **TradingView branding on a product surface.** The lightweight-charts attribution watermark renders
  inside the equity panel. It is a licence condition of the free build, and it puts a third-party
  brand on an operator's screen. Either accept it deliberately or move to a library without it.
- **Colours are hardcoded**, not tokenised, and the equity area is **green under a losing curve**
  whose own header reads `−80 776,12 ₽ (−8,08 %)` in red.
- **No disposal.** Chart instances are re-created without `.remove()` / `.dispose()`, so every view
  switch leaks one.
- **No `ResizeObserver`** on the containers.
- **Sample size never accompanies any series.**
- **The equity series is sampled by polling, not by market time.** 16 016 snapshots hold **49
  distinct values**, with 2 987 gaps of exactly 12 000 ms — that is `QFSync.POLL_MS`.
  `equity_curve(limit=200)` therefore returns 200 points spanning **30 minutes**, all identical. The
  x-axis is a record of how long someone left the tab open.

**Standards for future charts.** Equity: real `equity_snapshots`, market-time x-axis, zero baseline,
window label, `n` shown. Drawdown: underwater plot beneath equity, shared axis. PnL: signed bars, zero
line, never a pie. Exposure: stacked area by instrument with a limit line. Confidence: step line with
sample-size band; never a smooth curve, because confidence updates discretely. Trade distribution:
histogram with n and bin width stated. Regime performance: small multiples, not a radar. Latency:
p50/p95 lines, never a mean alone. **No candlestick chart** unless a named workflow requires it —
"it looks like TradingView" is not a workflow.

---

## 18. Tables Audit

**Current state.** 8 tables. Sticky headers (good). Header background `rgba(0,0,0,.22)` (good). 7px
cell padding. Orange row hover. `.num` right-aligns and switches to mono. **No sorting, no filtering,
no pagination, no virtualisation, no selected state, no keyboard interaction, no column hiding, no
per-table empty state.**

**Defects.**

| ID | Finding | Evidence |
|---|---|---|
| F‑TBL‑01 | Header/body alignment broken in **3 of 8 tables**, 12 columns total: headers right-aligned via `<th class="num">`, bodies emitted with `class="mono"` (no alignment) or no class at all | `components.js:76-84,103`; `app.js:601` |
| F‑TBL‑02 | **No tabular numerals anywhere** — proportional digits in every non-mono numeric cell | 0 occurrences of `font-variant-numeric` |
| F‑TBL‑03 | «История Paper Trades» is **permanently empty** — 35 rows exist, 0 render, envelope mismatch | §27 |
| F‑TBL‑04 | Row hover is `rgba(247,147,26,.03)` — an orange wash on every row the pointer crosses | `design-system.css:288-291` |
| F‑TBL‑05 | No selected state ⇒ keyboard traversal is impossible | — |
| F‑TBL‑06 | Timestamps render inconsistently across tables (three formats observed) | §9.3 |
| F‑TBL‑07 | Mobile: `overflow-x: auto` on a 14-column table is the entire responsive strategy | `design-system.css:261` |

**The QuantFlow table standard — three modes.**

| Mode | Row height | Font | Density | Where |
|---|---|---|---|---|
| **Compact** | 28px | 12px caption | Maximum rows | Signals, Trades, Event Log — long scannable histories |
| **Comfortable** | 36px | 14px body | Balanced | Positions, Strategies — rows that are read, not scanned |
| **Monitoring** | 44px card rows | 15px | One record per card | Mobile, and any table shown on a wall display |

Every table, in every mode, must have: right-aligned tabular numerics with a shared decimal column;
sticky header; sortable columns with a persisted preference; an explicit empty state distinct from
error and from loading (§21); a selected state with a 2px left rule; full keyboard traversal
(↑↓ row, ←→ column, Enter to open, Space to select); virtualisation above 200 rows; and a
per-cell staleness treatment rather than a per-panel one.

---

## 19. Controls and Actions Audit

**Census of state-mutating controls and their safety properties.**

| Control | Endpoint | Method | Confirm? | Disabled state? | Loading? | Audit? |
|---|---|---|---|---|---|---|
| Engine **Start/Stop** | `/api/platform/engine/{start,stop}` | POST | **No** | **No** | **No** | **No** |
| Credential **Clear** ×4 | `/api/settings/tokens` | POST | **No** | **No** | **No** | **No** |
| Save tokens | `/api/settings/tokens` | POST | No | No | No | **No** |
| Execute signal | `/api/platform/signals/<id>/execute` | POST | No | No | No | **No** |
| Paper trade | `/api/platform/paper/trade` | POST | No | No | No | **No** |
| Close position | `/api/platform/paper/position/<id>/close` | POST | — | — | — | **No control exists in the UI** (F‑IA‑07) |
| Run learning cycle | `/api/platform/learning/run_cycle` | POST | No | No | **Silent** — `window.QFToast` is never defined, so success and failure are both invisible | **No** |
| Run backtest | `/api/platform/backtest/run` | POST | No | No | No | **No** |

**Two findings deserve emphasis.** The **credential Clear buttons write an empty value straight to
`.env`** with no confirmation (`dashboard.html:470,481,510,521` → `app.js:396` → `dashboard.py:502`).
And **`audit_events` contains 12 rows, all `api.auth.denied`** — no trade, engine, or credential
action has ever been recorded. There is no trail to review.

**Required safety model for any trading-capable action.**

| Tier | Examples | Requirements |
|---|---|---|
| **Read-only** | every GET | None beyond authentication |
| **Operator** | pause/resume engine, reconnect, acknowledge alert | Single confirmation naming the effect; disabled while in flight; audit row |
| **Administrative** | credentials, thresholds, strategy freeze | Confirmation + reason field (free text, stored); audit row with actor, before/after; never clears a secret without typed confirmation |
| **Trading** | execute signal, close position, switch to live | **Typed confirmation** (type the ticker, or the word `LIVE`); reason field; explicit permission check; **idempotency key** so a double-click cannot double-fire; audit row; a rollback or compensating action documented in the dialog; a failure message that states what did and did not happen |

Every such control must be visually distinct from a marketing CTA: outline rather than fill, danger
tokens used as *stroke*, never a gradient, never a glow, never a scale-on-press. The site's white
pill CTA is for «Получить доступ»; a button that closes a position must not look like it.

---

## 20. System Health and Observability Audit

| Signal | Available today? | Where |
|---|---|---|
| Application | Partially | `/health`, `/api/platform/health` |
| Database | Yes | health service |
| TimescaleDB specifics | No | — |
| Broker | Yes | `/api/platform/brokers`; a real 502 path exists |
| Market data freshness | **Derivable and critical** | `max(candles.time)` — currently 32 days stale, surfaced nowhere |
| Forward runner | **No** | `forward_state` = 0 rows |
| Live runner | **No** | — |
| Telegram delivery | **No** | — |
| Last candle / signal / trade | Derivable | Not rendered as health |
| Scheduler / background tasks | **No** | Threads started at import, unobserved |
| Docker | Yes — via `subprocess.run(["docker","ps"])` **on the request path, 8 640×/day** | `system_health_service.py:78-81` |
| API latency | **No** | — |
| Data staleness | **No** | The single biggest gap |

**Health model — seven states, each with all seven properties.**

| State | Word | Icon | Colour | Timestamp | Reason | Action |
|---|---|---|---|---|---|---|
| Healthy | Работает | filled dot | success | last check | — | — |
| Degraded | Деградация | half dot | warning | since | "p95 1 240 мс" | Открыть метрики |
| Stale | Устарело | hollow ring | neutral | age, counting up | "последняя свеча 32 дн назад" | Проверить загрузчик |
| Disconnected | Нет связи | hollow ring | danger | since | "DNS lookup failed" | Переподключить |
| Failed | Ошибка | filled dot | danger | at | error class | Открыть журнал |
| Unknown | Неизвестно | dashed ring | neutral | never | "нет отчёта" | Проверить сервис |
| Paused | Пауза | square | neutral | since, by whom | "оператор" | Возобновить |

`Unknown` must never collapse into `Healthy`. A service that has never reported is not a service
that is fine — today the absence of a signal renders as nothing at all, which the eye reads as
"no problem".

---

## 21. Empty, Loading, Error and Stale States

**Current state, measured.** `fullSync` (`core/sync.js:79-111`) uses `Promise.allSettled`, silently
drops rejected slices, then **unconditionally** sets `syncStatus:'live'` and `lastSync:Date.now()`.
`QFRender.dashboard()` (`views/render.js:118-120`) then writes «обновлено HH:MM:SS» and sets a green
status dot regardless of what failed. **A screen full of stale numbers is stamped with a fresh
timestamp and a green light.** That is the most dangerous behaviour in the entire interface.

Meanwhile the Learning view's four panels sit on the literal string `Loading…` forever when their
endpoints fail (`views/learning.js:214-227` uses `Promise.all`, so one failure kills all four; the
only handler is `console.warn`). In the logs those endpoints returned HTTP 500 **57 times**.

**Required: ten distinct states per data region.**

| State | Rule |
|---|---|
| Loading (first) | Skeleton at the final layout's dimensions; max 3 shimmer cycles then static |
| Loading (refresh) | Previous data stays, a subtle progress hairline appears. **Never blank a populated panel** |
| Loaded | — |
| Empty | States *what* is empty and *why*, and offers the next action |
| Partial | Renders what arrived and names what did not, per field |
| Stale | Per-cell treatment + age + the absolute timestamp on hover |
| Disconnected | Transport-level banner; data frozen and visibly marked, not cleared |
| Permission denied | Names the permission and who can grant it |
| Backend error | Error id, retry, and a link to the event log. **Never a zero** |
| Malformed / timeout | Distinct from a 500; states which field failed validation |

**Eight messages that must never be merged into «Нет данных»:**

`Сделок пока нет` · `Нет сделок за выбранный период` · `Не удалось загрузить сделки` ·
`База данных недоступна` · `Стратегия ещё не запускалась` · `Стратегия заморожена` ·
`Форвард-раннер не обновлялся 3 дня` · `Рынок закрыт`

Each carries a different action. Collapsing them is how «у меня всё нулями» becomes an unreported
outage.

---

## 22. Responsive Audit

> **Confidence: Medium.** Source-derived. The dashboard could not be relaunched (§1.6), so the
> viewport-by-viewport behaviour below is read from CSS, not measured. Phase 0 must re-run this.

| Viewport | Expected behaviour | Risk |
|---|---|---|
| 1440×900 | Sidebar 240 + fluid main | Balance tile already wraps `₽` at **1600px** — it will wrap harder here |
| 1280×800 | Same | 14-column positions table overflows; `analytics-charts-row` at `2fr 1fr` gives a ~380px right panel |
| 1024×768 | Sidebar still 240px = 23 % of width | Content squeezed; no breakpoint collapses the rail automatically |
| 768×1024 | Overlay sidebar (`.sidebar-overlay` exists) | Tables scroll horizontally — the entire mobile table strategy |
| 390×844 | Same | 14 columns in a 390px viewport; 4px scrollbars are untappable; nothing reaches a 44×44 touch target |

**Additional risks:** no `env(safe-area-inset-*)` handling; sticky topbar + sticky table header + the
`.paper-feed` inner scroll create three nested scroll contexts; long tickers and long strategy names
(`osc_range_moex_d1_fwd` is 21 characters) have no truncation strategy with a title/tooltip; landscape
phone is not addressed at all.

**Mobile monitoring priorities**, in order: overall status → risk/exposure → open positions →
critical alerts → latest signal → emergency stop → system health. Nothing else. Mobile is **not** a
scaled desktop terminal, and no mobile control except the emergency stop should mutate trading state.

---

## 23. Accessibility Audit

Target: **WCAG 2.2 AA**. Current state fails it broadly and structurally.

| ID | Criterion | Finding | Evidence |
|---|---|---|---|
| A‑01 | 1.3.1 Info & Relationships | **No `<h1>`**; one `<h2>` in 911 lines; all view titles are `<div>` | `dashboard.html:666` |
| A‑02 | 4.1.3 Status Messages | **No `aria-live` anywhere.** Toasts, sync status, engine state, every price update are silent to assistive tech | 3 `aria-*` total |
| A‑03 | 1.4.3 Contrast (text) | `--qf-text-muted #5e6673` is the **most-used colour token (48 uses)** and fails on **every** surface (2.78–3.51:1). It renders every table header, metric label, timestamp and empty state — at 10–11px, uppercase | `design-system.css:42` |
| A‑04 | 1.4.3 Contrast (text) | Primary CTA: `#fff` on `#F7931A` = **2.30:1** — fails even AA-large | `design-system.css:154-155` |
| A‑05 | 1.4.11 Non-text Contrast | `--qf-border rgba(255,255,255,.07)` ≈1.3:1 on every control edge | `design-system.css:14` |
| A‑06 | 1.4.1 Use of Colour | Broker status, PnL sign, risk severity and chart series are all **hue-only** | §8.5 |
| A‑07 | 2.1.1 Keyboard | Tables have no keyboard interaction; no selected state | §18 |
| A‑08 | 2.1.2 / 2.1.4 | Bare `r`/`1`–`8` shortcuts with **no modifier guard** hijack ⌘R and ⌘1–⌘8; no way to disable them | `app.js:167-178` |
| A‑09 | 2.4.7 Focus Visible | `:focus-visible` exists and is correctly scoped — **the one thing done right** — but the ring is orange | `design-system.css:628-637` |
| A‑10 | 2.2.2 Pause/Stop/Hide | **13 infinite animations**, 6 reachable, no pause control | §24.3 |
| A‑11 | 2.3.x + 2.2.2 | `prefers-reduced-motion` sets duration but **not `animation-iteration-count`** — infinite loops keep looping | `design-system.css:760-765` |
| A‑12 | 2.5.8 Target Size | **Nothing reaches 44×44**; the scrollbar thumb is 4px | `design-system.css:493` |
| A‑13 | 1.4.4 Resize Text | 10px and 9px text exists (`metric-mini-label`, `qf-strip-label`, `tp-more`) | §9.5 |
| A‑14 | 1.1.1 Non-text Content | Charts are canvas with no text alternative and no data table equivalent | §17 |
| A‑15 | 3.3.1 Error Identification | Errors are `console.warn` only; nothing is announced or displayed | §21 |
| A‑16 | 1.3.1 | Tables lack `scope`, `<caption>`, and header/body alignment agreement | §18 |
| A‑17 | 1.4.12 Text Spacing | Uppercase + positive tracking at 10px in Cyrillic is the least legible configuration available | §9.5 |
| A‑18 | — | **Zero** `prefers-color-scheme`, `forced-colors`, or `prefers-contrast` blocks | §3 census |

**A‑03 alone is disqualifying.** The single most-used colour in the interface fails contrast on every
background it is used on, and it is used for the labels that tell a trader what every number means.


---

## 24. Motion and Interaction Audit

### 24.1 What the two systems already share

One thing transfers with no work at all. The dashboard's primary easing is

```css
--qf-ease: cubic-bezier(0.16, 1, 0.3, 1);        /* bot/ui/static/design-system.css:73 */
```

and the site's is

```css
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);  /* website/src/styles/tokens/motion.css */
```

They are byte-identical. The site's stated rule — *"Never bounce/spring-past-target; ease-out-expo /
ease-out-quart only"* (`motion.css:1-6`) — is already 90 % honoured by the dashboard, with one
violation: `--qf-ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1)` (`design-system.css:75`) overshoots
its target by design. An overshoot on a numeric readout makes a value appear to exceed itself before
settling; on a price or a PnL figure that is a misread waiting to happen. **Delete
`--qf-ease-bounce`.**

Durations map almost as cleanly:

| Dashboard | Site | Verdict |
|---|---|---|
| `--qf-duration-fast: 120ms` | `--duration-micro: 150ms` | Adopt 150ms |
| `--qf-duration: 220ms` | `--duration-base: 300ms` | Keep 220ms for the terminal — a dense grid at 300ms feels sluggish under repeated interaction. Document the deliberate divergence. |
| `--qf-duration-slow: 400ms` | `--duration-panel: 500ms` | Adopt 400ms for panel swaps; 500ms is a marketing pace. |
| — | `--duration-reveal: 800ms` | **Do not port.** See §24.4. |

### 24.2 Functional motion — the only motion a terminal is allowed

Motion in an operational surface has exactly one job: to tell the eye *that something changed and
where*. Every animation below earns its place by that test.

| Event | Treatment | Duration | Rule |
|---|---|---|---|
| Value changed (price, PnL, count) | Background tick flash on the **cell**, colour by direction, decaying to transparent | 600 ms, ease-out | Never animate the digits themselves. Never animate a value that is merely re-fetched and unchanged. |
| Row inserted (new signal, new trade) | 8 px slide-in + fade, **top of list only** | 220 ms | Existing rows must not reflow. Reserve the row's height before insert. |
| Row removed | Fade to 0 in place, then collapse height | 150 ms + 150 ms | Never animate a removal during an active scroll. |
| Connection state changed | The status chip cross-fades between states, once | 150 ms | One transition per real change. Never a loop. |
| Data became stale | The affected cell's staleness marker fades in, once | 300 ms | The marker is then **static**. |
| Panel / tab swap | Cross-fade only, no translate | 220 ms | No slide: a slide implies spatial relationship between tabs that does not exist. |
| Loading | Skeleton shimmer, only for the first load of a region | 1.5 s loop, max 3 cycles then a static skeleton | A shimmer that runs for 30 s is a hang, rendered as a feature. |
| Alert raised | Chip appears; **no motion at all after the first frame** | 150 ms in | The novelty *is* the signal. |

### 24.3 The infinite-animation census — the core motion defect

`bot/ui/static/design-system.css` currently runs the following **forever**, on a screen a trader
keeps open all day:

| Rule | Definition | Applied to |
|---|---|---|
| `pulse-dot` — 2 s, infinite, opacity 1→0.65 **and** a box-shadow that grows and shrinks | `design-system.css:387-390` | `.status-pill.live .dot`, `.status-pill.online .dot` (`:371-375`), `.live-dot` (`:784-792`), `.status-dot-inline.online` glow (`:382-385`) |
| `qf-shimmer` — 1.5 s, infinite | `design-system.css:352-355` | every `.skeleton` |
| `pulse` — 1.5 s, infinite, opacity 1→0.45 | `design-system.css:519-522` | any element given `.pulse` |
| `.qf-logo-mark` drop-shadow glow | `design-system.css:642-646` | brand mark, intensifying on hover |

Three separate problems compound here.

**It spends the alarm on "normal".** `pulse-dot` is attached to `.online` and `.live` — the *healthy*
states. Pulsing is the strongest peripheral-attention device a dark UI has. Spending it on "nothing
is wrong" means that when something *is* wrong there is no escalation available, and the eye has
already learned to filter that exact motion out. The screenshot confirms the pattern is live: the
"Live" and "Connected" chips in the topbar and the "Online" broker dot all pulse continuously while
the system is idle.

**It is a sustained-attention cost.** A 2 s luminance oscillation in peripheral vision, present for
an eight-hour session, is a documented source of visual fatigue and a genuine trigger risk for
vestibular- and photosensitivity-affected users. WCAG 2.2 SC 2.2.2 (Pause, Stop, Hide) applies to
any auto-updating motion that runs for more than five seconds and is presented in parallel with
other content — there is no pause control anywhere in this interface.

**Reduced-motion is handled, but crudely.** `design-system.css:760-765` does:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

This is the right instinct and the wrong mechanism. Collapsing *all* durations to 0.01 ms also kills
the functional signals — the tick flash and the row-insert cue become invisible, so a reduced-motion
user loses the information those cues carry rather than receiving it in a calmer form. The correct
pattern replaces motion with a non-moving equivalent: a tick becomes a 600 ms static background hold,
a pulsing dot becomes a solid dot with a text label, a shimmer becomes a static grey block.

**Recommendation:** no infinite animation on any state that means "healthy". If a live indicator must
convey liveness, do it with a value that visibly changes — a data-age counter counting up is
honest, informative, and reads as motion without being decoration.

### 24.4 What must NOT be ported from the site

| Site behaviour | Where | Verdict for the terminal |
|---|---|---|
| Scroll-driven reveal (`--duration-reveal: 800ms`, `motion/reveal.tsx`, `scroll-driver.ts`) | every section | **Forbidden.** Measured live: reveal wrappers inside `#dashboard` sit at `opacity: 0.0456` with `translateY(26.7px)` until the reveal is driven. Content that is invisible until an animation agrees to run is disqualifying on a surface where a risk figure may be the thing hidden. |
| Lenis smooth scrolling (`motion/lenis-provider.tsx`) | whole page | **Forbidden.** Smooth-scroll inertia in a dense table breaks the relationship between wheel input and row position, and it broke programmatic `scrollTo` during this very audit. |
| Q-aperture orbits (`--duration-orbit-a/b/c: 32s/46s/61s`, three coprime periods) | hero | **Forbidden in the terminal.** Legitimate on the sign-in screen and on a genuinely empty first-run state, where there is no data to compete with. |
| Ambient cold-blue glow pools (`--glow-signal-lg`) | hero, pipeline | **Forbidden.** Ambient glow behind live data is indistinguishable from a system-state highlight. |
| Card hover lift (`translateY(-1px)` + shadow) | cards | **Adapt.** Acceptable on genuinely clickable cards. **Remove from table rows** — the current `.qf-metric:hover { transform: translateY(-2px) }` and `.signal-card:hover { translateY(-2px) }` make a dense grid twitch as the pointer crosses it. |
| Magnetic cursor (`ui/magnetic.tsx`) | CTAs | **Forbidden.** An element that moves away from the pointer is a hostile affordance next to a "close position" button. |
| Click ripple (`qf-ripple`, `design-system.css:743-755`) | dashboard's own | **Remove.** A radial ripple on a terminal control is a Material-Design idiom that belongs to neither the site nor the reference. |
| Button `transform: scale(0.96)` on `:active` (`design-system.css:147-150`) | dashboard's own | **Remove for trading controls.** A shrink-on-press on a destructive button reads as "the click registered" even when the request failed. Press feedback must come from the *result*, not the gesture. |

### 24.5 Explicit prohibitions for the future implementation

1. No permanent bright pulsation on any element.
2. No glow that could be mistaken for a system state; decorative glow does not exist on the terminal.
3. No parallax, anywhere, ever, inside a working table.
4. No animation of every digit on every poll — animate on *change*, and only the changed cell.
5. No layout shift on refresh. Every panel reserves its own height; a value arriving must not move
   the thing below it. (This is currently violated: the balance tile's `₽` wraps to a second line at
   1600 px, which means the tile's height is content-dependent.)
6. No decorative effect that uses the warning or danger vocabulary.
7. No motion that impedes sustained observation — the test is an eight-hour session, not a demo.
8. No scroll-triggered entrance for data that already exists on screen.
9. Every loop must be bounded or must be pausable; nothing runs forever without a control.

### 24.6 Interaction states — what is missing

Present and adequate: `:hover` on cards, rows, strip items and buttons; `:focus-visible` with a
2 px outline (`design-system.css:628-637`) — the right selector, wrong colour once the accent
becomes white, and `outline-offset: -2px` inside the clipped sidebar is a correct detail worth
keeping.

Absent, and required:

- **`:disabled`** exists only as `opacity: 0.45` (`design-system.css:146`), which fails contrast and
  is indistinguishable from "loading". A disabled trading control must state *why* it is disabled.
- **Selected row.** No selected state exists on any table. Keyboard traversal of a table without a
  selected state is unusable.
- **Loading (per control).** No `aria-busy`, no in-button spinner, no optimistic-lock. A double-click
  on «Выполнить» currently issues two POSTs.
- **Pressed vs. in-flight.** The scale-down `:active` is the only feedback; there is no state that
  means "sent, waiting".
- **Error (per control).** No inline error rendering next to the control that failed.


---

## 25. Performance Audit

Documentation only. Nothing was optimised.

### 25.1 Ranked by what a trader on a laptop actually feels

**P1 — The dashboard writes to the database 6–27 times a minute just for being open, then chokes on
what it wrote.**
`paper_trading_service.py:73` calls `record_equity_snapshot()` inside `refresh_positions`, which sits
on the path of **four GET endpoints**. Measured insert rate: **6/min** healthy, **24–27/min** when the
broker is failing. Result: `equity_snapshots` = **16 017 rows / 2 848 kB** accumulated since
2026‑07‑12, against **35** paper trades in the same period.
`AnalyticsService._compute_max_drawdown` (`analytics_service.py:258-267`) full-scans that table with
**no LIMIT** (`EXPLAIN`: Index Scan Backward, rows=16 055). `_daily_equity_returns` (`:212-222`) is a
**Seq Scan + Sort over 16 055 rows** because `DATE(snapshot_at)` defeats the index. Both run on every
`trade_stats()` call — i.e. on `/api/platform/analytics` *and* `/analytics/summary`, the latter polled
every 12 s by the mini-app. **The Analytics view measurably slows every day the tab stays open, and
the degradation is self-inflicted. There is no retention policy.**

**P2 — 1.3 MiB of render-blocking JavaScript and 0.80 MiB of cold-load transfer, with compression
off.**
ECharts **1 029 203 B** raw / 334 508 B gzip; lightweight-charts **163 551 B** / 50 847 B. Both are
`<script>` in `<head>` with **no `defer`, no `async`, no SRI**. Local assets total **326 301 B served
uncompressed** — no Flask-Compress, no gzip anywhere. Measured gzip would give 72 951 B, so
**253 350 B (77.6 %) of every cold load is avoidable**. Nothing is minified. **66 937 B (21 % of the
local payload) is the Quant Hunter game**, eagerly loaded for a hidden view. 19 static assets →
**418/418 responses were 304**, i.e. 19 blocking conditional round-trips per load, caused by
`SEND_FILE_MAX_AGE_DEFAULT=0` (`dashboard.py:43`). Four third-party origins on the critical path;
one `preconnect`.

**P3 — Four separate endpoints each open a fresh gRPC channel to the broker every 10 seconds.**
Log evidence: **4 `GetPortfolio` in the same second** with 4 distinct correlation ids
(`logs/dashboard.log:3572-3586`); **12 `GetInstrumentBy` in one second** (`:73-85`); session totals
336 and 12. Root cause: `_portfolio_cache.get()` (`portfolio.py:61`) and `.set()` (`:135`) with
nothing between them to dedupe concurrent misses; `build_client()` (`client.py:35-53`) creates a new
channel per call; `TTLCache` (`cache.py:8-30`) is a bare dict with **no lock**. **No negative
caching** — `portfolio.py:130-133` re-raises without caching, so failures retry at full rate forever
(**31 × HTTP 502** observed). A fullSync batch spans **13 s** against a **12 s** poll, so the UI is
permanently mid-load, and the client's 12 s abort (`core/api.js:23`) can cancel the paper-account
call.

**P4 — `/api/platform/overview` forks `docker ps` and sleeps 100 ms, six times a minute.**
`system_health_service.py:78-81` runs `subprocess.run(["docker","ps",...])`; `:25` calls
`psutil.cpu_percent(interval=0.1)` — **a hard 100 ms sleep in the request thread**; `:45-51` opens two
separate DB connections; `:70` builds a Redis client with a 1 s connect timeout **for a Redis this
project does not use**. ≈130 ms of pure blocking before any application data is read, ×6/min per tab
= **8 640 process spawns per day** to render a container count.

**P5 — 45–54 requests/minute at idle, ~360/min while navigating, nothing pauses on tab hide.**
`POLL_MS = 12000` × a 9-request batch (`sync.js:79-89`), plus Learning's own 20 s timer (5 more) and
the mini-app's 12 s timer. `grep visibilitychange` over `bot/ui/static/` → **no matches**. A
backgrounded tab keeps polling, keeps calling the broker, and keeps inserting equity snapshots.

### 25.2 Memory-leak candidates

Chart instances re-created without `.remove()`/`.dispose()`; intervals not cleared on view change;
`EventSource` never closed; listeners added inside render functions that re-run on every poll;
`QFStore.on()` returns an unsubscribe closure that removes the **wrong function reference**
(`core/store.js:108-111`) — it is a permanent no-op, so every subscriber ever registered stays
registered.

### 25.3 Two renderers fighting over one node

`views/render.js:291-307` and `app.js:325-351` both write `#tickerGrid` with incompatible markup,
sequenced by `platform.js:18-22`. The 12 s poller makes them alternate. Whichever ran last wins.

### 25.4 Caching

There is none. No in-process cache beyond the unlocked Tinkoff `TTLCache`, no HTTP caching, no
ETags, no `Cache-Control` (actively defeated by `SEND_FILE_MAX_AGE_DEFAULT=0`).

---

## 26. Security Audit

> Authorized defensive review, documentation only. No mutating request was sent; `.env` was never
> read; no secret value is reproduced here.

### 26.1 The five that matter

| ID | Finding | Severity |
|---|---|---|
| **S1** | **Authentication is source-IP-based, not credential-based. Under shipped defaults, zero of 52 routes require a secret.** There is no decorator; the entire access-control surface is one `before_request` hook (`bot/security/dashboard_auth.py:73-100`) registered at `bot/ui/dashboard.py:48`, which allows any request whose source IP passes `_read_allowed()` / `_write_allowed()`. | **Critical** |
| **S2** | **No CSRF protection anywhere.** Because auth is IP-based rather than cookie-based, `SameSite` provides no protection at all. **10 of 12 mutating endpoints are drive-by exploitable from any web page the operator visits** — including engine start/stop, signal execution, paper trades and credential writes. | **Critical** |
| **S3** | **`bot/auth/` is entirely dead code** — missing module, missing config sections, missing dependencies. The JWT / Argon2 / session / CSRF stack that `CLAUDE.md` describes as live **does not exist at runtime**. This is worse than absent security: it is documented false assurance. | **Critical** |
| **S4** | **No audit trail for any action.** `audit_events` holds **12 rows, all `api.auth.denied`**. No trade, engine, or credential event has ever been recorded. | **High** |
| **S5** | **XSS: 31 unescaped `innerHTML` interpolations across `views/render.js` and `components.js`, with zero escaping helpers** (`grep -c "esc("` → 0). Ticker strings are interpolated into `onclick="loadTickerChart('${a.ticker}')"` — a JS string inside an HTML attribute (`render.js:301,303,314`); `QFUI.badge()` interpolates server data raw (`components.js:29`). Meanwhile the API key that guards remote writes sits in `sessionStorage`, readable by exactly that XSS. | **High** |

### 26.2 Additional findings

- **Error disclosure.** The learning endpoints log the full SQL text, the parameter list and a
  SQLAlchemy documentation URL at WARNING level; 16 blueprint routes have no `try/except` and return
  an HTML 500 (including a Werkzeug traceback if debug is ever enabled) to a JSON client.
- **Debug / binding.** `app.run(host=host, port=port, debug=use_debug, use_reloader=use_debug)`
  (`dashboard.py:751`) — both are env-driven. With debug on, the Werkzeug console is an RCE.
- **Supply chain.** Two CDN scripts with **no SRI** (`dashboard.html:14-15`) plus two Google Fonts
  stylesheets. The CSP (`security/http_middleware.py:10-18`) permits `unsafe-inline` for both
  script and style, which materially weakens it against S5.
- **CSP scoping bug.** `http_middleware.py:49` tests `request.path.startswith("/static/miniapp/")`
  while the Mini App is served from `/miniapp` (`dashboard.py:351-360`), so it receives
  `frame-ancestors 'none'` and **cannot be framed by Telegram Web**. A correctness bug hiding inside
  a security control.
- **Credentials.** `/api/settings/tokens` GET/POST is the credential surface; the four «Clear»
  buttons write an empty value to `.env` with no confirmation. Masking behaviour must be verified
  before the endpoint is exposed to anything but loopback.
- **GET routes that mutate** (§3.1) are, separately from performance, a CSRF amplifier: a plain
  `<img src>` can drive them.

### 26.3 Proposed permission matrix (documentation only)

| Tier | Can | Endpoints |
|---|---|---|
| **Observer** | Read everything, mutate nothing | all GET, once the mutating GETs are fixed |
| **Operator** | Pause/resume engine, reconnect, acknowledge | `engine/stop`, `engine/start`, reconnect |
| **Administrator** | Credentials, thresholds, strategy freeze | `settings/tokens`, threshold writes |
| **Trading-authorized** | Execute signals, close positions, switch to live | `signals/<id>/execute`, `paper/trade`, `paper/position/*/close`, live-mode switch |

Live-mode entry should require a second factor regardless of tier.

---

## 27. Data Contract Audit

### 27.1 The migration defect — real, latent, and currently self-healed

This finding changed shape during the audit and the sequence matters, so it is recorded honestly.

**Observed at the start of this session (first-hand):** `trades` had **22 columns**, and the four
Learning endpoints returned **HTTP 500** with `UndefinedColumn: column "decision_quality" does not
exist` (also `strategy_id`, `trade_id`). The failing SQL was logged verbatim.

**Observed later in the same session (first-hand, re-verified):** `trades` has **46 columns**. All
the previously-missing columns exist, and the Learning queries execute. No bot or dashboard process
was running at the time of the second check.

**Mechanism.** `bot/ui/dashboard.py:70` calls `ensure_platform_schema(_engine)` at **module import
time**. `bot/qf_platform/bootstrap.py:16-30` executes the whole of `PLATFORM_SCHEMA_SQL` by splitting
on `;` and running every statement **inside one `engine.begin()` transaction**. The committed
`schema.py` places `CREATE INDEX idx_trades_strategy ON trades (strategy_id)` and
`CREATE INDEX idx_trades_sandbox ON trades (is_sandbox)` **before** the `ALTER TABLE … ADD COLUMN
IF NOT EXISTS` block. On a legacy `trades` table those indexes reference columns that do not yet
exist, the statement raises, and **the single transaction rolls back every ALTER with it**. The
uncommitted working-tree diff moves exactly those two statements after the ALTER block, with the
comment *"must come AFTER the ALTER TABLE block above, otherwise they abort the whole DDL script on a
legacy simplified trades table"* — an in-tree admission of this precise failure mode.

**Status.** The defect is **still committed on this branch**. This particular database has since been
migrated (by an app run carrying the uncommitted fix), so the symptom is currently absent here. **Any
fresh deploy against a legacy database reproduces it**, and the failure is silent: the four Learning
panels sit on the string `Loading…` forever while the browser console stays clean.

**Aggravating factor.** `logs/dashboard.log:3` shows `learning.feedback … Схема БД
проверена/создана` at dashboard startup — legacy `feedback.py` runs **its own** schema migration in
the same process. There are **two independent DDL authorities racing on `trades`**, and
`quantflow_schema.sql` is a **third, divergent** definition (UUID PK, Postgres enums, a hypertable) that
matches neither.

**F‑DATA‑02: ship the fix.** Commit the reorder, and change `bootstrap.py` to run each statement in
its own transaction (or at minimum log which statement aborted) so a partial failure is visible.

### 27.2 The seven correctness defects, ranked

| # | Defect | Evidence | Impact |
|---|---|---|---|
| **1** | **The Equity Curve is SBER's share price relabelled as portfolio equity.** `/api/equity` falls through to a candle-derived fabrication: it renders 2025‑06‑26 → 2025‑09‑29 ending at ₽919 224, while the paper account went ₽10 000 000 → ₽7 626 546 (verified: `paper_accounts`) | §17 | **Blocker.** The primary chart on the landing screen is fiction. |
| **2** | **All market prices are 32 days stale.** `max(candles.time)` = `2026-06-26`; DB `now()` = `2026-07-28`. Every mark price, unrealized PnL, live signal and paper fill derives from it. **Nothing in the UI shows the candle timestamp.** | verified read-only | **Blocker.** |
| **3** | **`avg_profit_pct` is `AVG(ABS(pnl_pct))`.** On the live account — 35 trades, **0 wins**, −₽2 373 454 (verified) — it reports **+16,07 %**. | dossier §5.3 | **Blocker.** A losing account reports a positive average. |
| **4** | **`max_drawdown` carries two different units under one name.** Analytics renders the real −23,73 % drawdown as **«−0,2 %»**. | dossier §5.4 | **Blocker.** |
| **5** | **The equity series is sampled by polling, not by market time.** 16 016 snapshots hold **49 distinct values**; 2 987 gaps are exactly 12 000 ms = `POLL_MS`. `equity_curve(limit=200)` returns 200 points spanning **30 minutes**, all identical. | §25.1 | The x-axis measures how long the tab was open. |
| **6** | **Three tables feed one card grid under one source badge.** Balance ← `paper_trades`; Sharpe/DD/WinRate ← `trades`; recent trades ← `trades`; equity chart ← `candles`. The tile is badged «Т-БАНК». | dossier §5.6 | Numbers that cannot be reconciled by the user. |
| **7** | **`is_sandbox` is never filtered.** Zero occurrences in `bot/ui/**` or `bot/qf_platform/**` outside DDL. | verified | Sandbox and live results are indistinguishable — the single largest correctness risk once live trading is enabled. |

Plus: **«История Paper Trades» renders 0 of 35 rows** due to a response-envelope mismatch; and
**GET endpoints mutate state** — `/paper/account`, `/portfolio`, `/overview` each INSERT an
`equity_snapshots` row and UPDATE `paper_accounts`/`paper_positions`; `/signals` INSERTs into
`trading_signals`.

### 27.3 Tables the dashboard ignores

| Table | Rows | Read by the dashboard? | What the trader loses |
|---|---|---|---|
| `skipped_signals` | **0** | No | Scenario 9 — why a signal was rejected |
| `forward_state` | **0** | No | Scenarios 14–15 — forward/live runner state |
| `system_events` | **0** | No | Scenario 18 — system errors |
| `audit_events` | 12 (all `auth.denied`) | No | Scenario 21 — audit trail |
| `belief_system` | 8 | Yes (Learning) | — |
| `trade_feedback` | ? | No | Legacy path, unclear ownership |
| `news` | ? | No | Unused |

Four of the seven are empty **and** unread. Populating them is backend work that must precede the UI
that displays them.

### 27.4 Timezone

DB `SHOW TimeZone` → **UTC**; the topbar renders **MSK**. The conversion boundary was not established
from the UI alone, and `equity_snapshots` plus `candles.time` drive both the chart x-axis and every
"last event" figure. A mismatch shifts the entire chart by three hours with no visible error.
**Requirement:** one policy, applied once, server-side, into the view model, with the tz label
rendered beside every absolute time.

---

## 28. Target Data Contract

Legend: **A** available · **D** derived · **B** broker · **E** new endpoint · **S** new schema field ·
**R** roadmap.

| Widget | Source | Endpoint | Units | Refresh | Stale threshold | Empty | Error | Permission |
|---|---|---|---|---|---|---|---|---|
| Environment band | config + engine | `GET /api/v2/environment` **E** | enum | 5 s | 15 s | n/a | **fail closed → render `UNKNOWN`, never `SANDBOX`** | Observer |
| Fault region | aggregate | `GET /api/v2/faults` **E** | list | 5 s | 15 s | zero-height | banner | Observer |
| Data freshness | `max(candles.time)` | in `/environment` **D** | seconds | 5 s | **60 s** | — | `UNKNOWN` | Observer |
| Equity series | `equity_snapshots` | `GET /api/v2/equity?window=` **A**, needs market-time resampling | ₽ | 30 s | 5 min | «нет истории» | error id | Observer |
| Balance / cash / margin | `paper_accounts` | `GET /api/v2/account` **A** | ₽ | 10 s | 60 s | — | — | Observer |
| Positions | `paper_positions` + mark | `GET /api/v2/positions` **A** + `quote_ts` **S** | mixed | 5 s | **30 s per quote** | «нет позиций» | — | Observer |
| Distance to stop | derived | in `/positions` **D** | % | with positions | — | `н/д` | — | Observer |
| Trades | `paper_trades` | `GET /api/v2/trades` **A** (fix envelope) | ₽ / R | 30 s | 5 min | period-specific | — | Observer |
| Signals + gate | `trading_signals` + `skipped_signals` | `GET /api/v2/signals` **A + S** | — | 10 s | 60 s | «сигналов нет» | — | Observer |
| Strategy board | `belief_system` | `GET /api/v2/strategies` **A** + `frozen` **S** | ratio + n | 60 s | 10 min | «не запускалась» | — | Observer |
| Confidence history | — | `GET /api/v2/strategies/<id>/history` **S** (`belief_history`) | ratio | 60 s | — | «нет истории» | — | Observer |
| Risk | risk service | `GET /api/v2/risk` **A**, drawdown units **fixed** | ₽ / % | 10 s | 60 s | — | — | Observer |
| System health | health service | `GET /api/v2/health` **A**, minus `docker ps` from the request path | enum | 15 s | 60 s | `UNKNOWN` | — | Observer |
| Event log | `system_events` | `GET /api/v2/events` **A schema / 0 rows** | — | 30 s | — | «событий нет» | — | Observer |
| Audit trail | `audit_events` | `GET /api/v2/audit` **A schema / not written** | — | on demand | — | — | — | Administrator |
| Telegram delivery | — | **R** | — | — | — | — | — | Observer |
| Orders | — | **R** — no entity exists | — | — | — | — | — | Trading |

**Contract rules.** Every response carries `as_of` (server time, ISO 8601 with offset) and, where
applicable, `source` and `environment`. Every aggregate carries its `n`. Every error is a structured
envelope `{error: {code, message, id}}` — never an HTML 500, never `200 []`. No GET mutates. Units are
explicit in the payload, never implied by a field name (`max_drawdown_pct` and `max_drawdown_abs`, not
`max_drawdown`).


---

## 29. Target Component Architecture

Not to be built in this session. Each component's token contract references §7.

| Component | Purpose | Variants | States | Key tokens | A11y | Data | Used in |
|---|---|---|---|---|---|---|---|
| `AppShell` | Grid owner: rail, topbar, band, content | expanded / rail | — | surface, border | `<header> <nav> <main>` landmarks, skip-link | — | all |
| `Sidebar` | Primary nav | expanded 240 / rail 64 | item: rest/hover/active/focus + per-item status dot | surface, panel-raised, accent | `aria-current="page"`, roving tabindex | health per section | all |
| `Topbar` | Context, clock, refresh, account | — | — | surface | `<h1>` lives here | — | all |
| **`EnvironmentBadge`** | Sandbox / live / unknown | sandbox / live / unknown | — | neutral / **paper inversion** / neutral | `role="status"`, always a word | `/environment` | shell |
| **`SystemStatus`** | One service's health | dot / chip / row | 7 states (§20) | success/danger/neutral + **shape** | word + icon + `aria-label` | `/health` | Overview, Health |
| `StaleBanner` / `StaleMark` | Age of a value | panel banner / **inline cell mark** | fresh / stale / unknown | neutral | `<time datetime>` + `title` | `as_of` | everywhere |
| `MetricCard` | One number | sm / md / lg | loading / value / empty / stale / error | panel, text ramp, tabular | `<dl>`; unit in the accessible name | any | all |
| `StatusCard` | State + reason + action | — | 7 states | as `SystemStatus` | — | any | Overview, Health |
| `DataTable` | Tabular data | **compact / comfortable / monitoring** | loading / rows / empty / partial / error | panel, border, tabular | `scope`, `<caption>`, full keyboard, selected row | any | most |
| `ChartPanel` | Chart + its metadata | line / area / bar / underwater | loading / data / empty / stale / error | panel; series from tokens | text alternative + a data-table toggle | series + `n` | Overview, Portfolio, Analytics |
| `EmptyState` | Nothing here, and why | 8 messages (§21) | — | text-tertiary | — | — | everywhere |
| `ErrorState` | Failure + id + retry | inline / panel / page | — | danger as stroke | `role="alert"` | error envelope | everywhere |
| `StrategyBadge` | Identifies a strategy | — | active / frozen / candidate / retired | neutral + shape | word | `belief_system` | Strategies, Signals |
| **`ConfidenceIndicator`** | Confidence **+ sample size** | inline / bar | mature / **immature (n<30)** / none | text ramp | reads "0,61, выборка 12" | `belief_system` | Strategies, Signals |
| `ModeBadge` | Row-level environment | sandbox / live / backtest / forward | — | neutral | word | `is_sandbox` | tables |
| `RiskIndicator` | Exposure vs limit | bar / gauge | ok / warn / breach | success/warning/danger + **position** | numeric text always present | `/risk` | Overview, Risk |
| `EventTimeline` | Ordered events | compact / detailed | loading / events / empty | panel | `<ol>`, `<time>` | `system_events` | Event Log |
| **`ConfirmActionDialog`** | Gate for mutations | confirm / **typed-confirm** / typed+reason | idle / in-flight / error | danger as stroke | focus trap, `aria-modal`, Esc | action descriptor | all trading controls |
| `Toast` | Transient result | info / success / error | — | panel | **`aria-live="polite"`** | — | everywhere |

Note `Toast`: `window.QFToast` is referenced twice and **never defined**, so the "Run Cycle" button
currently gives no feedback at all. The component does not exist.

---

## 30. File-by-File Future Change Map

| File | Now | Future role | Action | Risk | Depends on |
|---|---|---|---|---|---|
| `bot/ui/dashboard.py` | App + 23 routes + Sharpe/drawdown + engine lifecycle | Thin app factory | **SPLIT** | High — import side effects | Engine extraction |
| `bot/ui/api/platform_routes.py` | 30 routes + 17 inline SQL | Thin HTTP over services | **REWORK** | Med | Repositories |
| `bot/qf_platform/services/*` | Partial logic | The only home for derivations | **REWORK** | Med | — |
| `bot/qf_platform/repositories/*` | Two repos | All SQL lives here | **REWORK** | Med | — |
| `bot/qf_platform/schema.py` | Runtime DDL, ordering bug | Versioned migrations (Alembic) | **REPLACE** | **High** | F‑DATA‑02 first |
| `bot/qf_platform/bootstrap.py` | One-transaction DDL runner | Delete once migrations exist | **DEPRECATE** | Med | Above |
| `quantflow_schema.sql` | Third divergent schema | Reference or deleted | **DEPRECATE** | Low | Above |
| `bot/security/dashboard_auth.py` | IP allowlist = all security | Real auth | **REPLACE** | **High** | S1–S3 |
| `bot/auth/**` | Dead code, documented as live | — | **DELETE LATER** | Low | Decision D‑09 |
| `bot/learning/feedback.py` | Second DDL authority at startup | Off the dashboard import path | **REWORK** | Med | Migrations |
| `bot/ui/templates/dashboard.html` | 911-line shell, 41 inline styles | Shell only | **REWORK** | Low | Tokens |
| `bot/ui/static/design-system.css` | 71 `--qf-*`, 9 dead | Consumer of the shared token package | **REPLACE** | Med | Phase 1 |
| `bot/ui/static/style.css` | Shell + layout, 27 dup selectors | Layout only | **REWORK** | Med | Above |
| `bot/ui/static/miniapp/**` | Loaded globally, leaks `:root`, 67 KB | Own route, lazy | **MOVE** | Low | Routing |
| `bot/ui/static/views/render.js` | 32 `innerHTML`, 0 escaping | Component renderers | **REWORK** | **High — S5** | Escaping first |
| `bot/ui/static/components.js` | Raw interpolation | Primitives | **REWORK** | **High — S5** | Escaping first |
| `bot/ui/static/core/store.js` | Broken unsubscribe | Store | **REWORK** | Low | — |
| `bot/ui/static/core/sync.js` | 9-request batch, no visibility gating | Sync + backoff | **REWORK** | Med | Endpoint consolidation |
| `bot/ui/static/core/format.js` | 51 lines, inconsistent | Single formatting authority | **REWORK** | Low | §9.3 |
| `bot/ui/static/charts.js` | Two CDN libs, no disposal | One library, tokenised, disposed | **REWORK** | Med | Library decision |
| `website/src/styles/tokens/*` | Site-only | **Shared package** | **MOVE** | Med | Phase 1 |
| `website/scripts/check-design-tokens.mjs` | `ROOT = src/components` only | Lints both surfaces | **REWORK** | Low | Above |
| `design/DESIGN_SYSTEM.md` | Orange v3 | Superseded | **DEPRECATE** | Low | This audit |
| `design/screens/*` | Screen intents (still useful) | Fold into new specs | **KEEP** | Low | — |
| `CLAUDE.md` | Wrong canonical path, describes dead auth | Corrected | **REWORK** | **High — governance** | Decision D‑01 |
| `tests/` | No dashboard coverage | Route + contract + visual regression | **CREATE LATER** | Med | Phase 5 |

---

## 31. Architecture Options

### Option A — improve the existing Flask/Jinja dashboard

Speed **high** (a visual redesign needs zero Python). Cost **low**. Risk **low**. Design-system reuse
**good** via a shared token CSS file. Real-time **already there** (SSE), though it pins a worker per
client. Testing **poor** — no build step, no component boundaries, no existing coverage.
Scalability **capped at ~3 concurrent viewers** by the connection pool (§3.2). Maintainability
**mediocre** — 5 900 lines of untyped, unbundled JS with two renderers fighting over one DOM node.

### Option B — Flask API + separate Next.js dashboard

Reuse of the site's components and tokens **excellent** — this is the only option that gives literal
component sharing. Deployment **two targets**. Auth **must be built properly** (which S1–S3 require
anyway). API boundary **forced, which is a benefit** — it would end the 25 inline SQL strings.
Real-time **cleaner** (SSE/WS behind a proper server). Complexity **high**. Migration risk **high**:
8 views, ~53 endpoints, and a named duplication hazard — Sharpe already exists **three times** in
this repo, and drawdown, Sortino, win rate, profit factor, expectancy, exposure and R-multiples are
all currently computed in Python and trivially re-derived in TypeScript.

### Option C — one Next.js app for both the site and the authenticated dashboard

Routing **clean** (`/` public, `/app` authenticated). Public/private boundary **the main risk** — a
single misconfigured route or a leaked server action exposes trading controls to the marketing
surface. Bundle **must be split hard** or the marketing page carries terminal code. Deployment
**one target**. Design consistency **maximal**. Coupling **maximal, and dangerous**: a marketing
deploy would then be able to break the operator's terminal. Operational risk **highest** — the
public site's release cadence is not the terminal's.

### Recommendation

**Option A now; Option B later, and only under stated conditions.**

The visual alignment the user is asking for — the actual subject of this audit — is achievable in
Option A at a fraction of the cost, because Jinja interpolates nothing and the dashboard is already
a client-rendered SPA. Moving to Next.js first would spend the entire budget on a port and deliver
the same pixels.

Move to **Option B** when at least two of these become true: (1) more than three concurrent operators
need the dashboard; (2) a second user/tenant enters the data model; (3) the team wants literal React
component sharing with the site rather than shared tokens; (4) the Python API boundary from Phase 0
is already in place and typed.

**Do not choose Option C.** Coupling the operator's terminal to the marketing site's deployment is an
operational risk with no compensating benefit that Option B does not also provide.

**Prerequisite for any option:** the four data blockers in §27.2 and the three critical security
findings in §26.1. A beautiful dashboard displaying SBER's share price as portfolio equity, with no
authentication, is worse than the current one — it is more credible.

---

## 32. Phased Implementation Plan

### Phase 0 — Reality and Safety *(blocks everything)*

**Goal:** make the dashboard's numbers true and its controls safe.
**Scope:** ship the `schema.py` reorder and make DDL failures visible; consolidate on one migration
tool; fix `/api/equity` to read `equity_snapshots`; fix `avg_profit_pct`; fix `max_drawdown` units
and split the field into `_pct`/`_abs`; surface candle age; make every GET read-only; fix the paper
trades envelope; add `is_sandbox` filtering everywhere; populate `skipped_signals`, `forward_state`,
`system_events`, `audit_events`; replace IP auth with real authentication; add CSRF; escape every
`innerHTML` sink; delete or complete `bot/auth/`; add one error envelope and one `@app.errorhandler`;
raise the pool and move the engine out of the web process; re-run the runtime QA pass.
**Files:** `schema.py`, `bootstrap.py`, `dashboard.py`, `platform_routes.py`, services, repositories,
`dashboard_auth.py`, `render.js`, `components.js`.
**Deliverables:** a data-contract document; a read-only launch mode; a green security review.
**Acceptance:** every number on Overview traceable to a query that returns it; zero mutating GETs;
zero unescaped sinks; 100 % of mutating endpoints authenticated + CSRF-protected; four Learning
endpoints green on a **fresh** database.
**Out of scope:** all visual work.

### Phase 1 — Design Foundations

**Goal:** one palette, one type system, one geometry, mechanically enforced.
**Scope:** extract `website/src/styles/tokens/*` into a shared package; fix the site's own six token
violations (§6.3) at the source; author terminal-specific semantic tokens (§8.3); self-host Geist +
Geist Mono, drop Orbitron and the Google Fonts requests; replace `design-system.css`; extend
`check-design-tokens.mjs` to lint `bot/ui/static/**`; add contrast and touch-target checks to CI.
**Acceptance:** zero raw hex/rgba outside the token file (from 36/126); ≤6 rendered font sizes (from
20); ≤7 radii (from 11); ≤3 shadows (from 34); zero infinite animations; every text token ≥4.5:1;
every control edge ≥3:1; CI fails on a violation.
**Out of scope:** new screens.

### Phase 2 — Core Monitoring

Overview per §13; Positions split out with a working close action; Trades fixed; Signals with the
gate decision; System Health. Environment band and fault region shipped first.
**Acceptance:** the 5-second question answered; scenarios 1–7, 17, 20, 22 pass; no panel contradicts
another; every panel has all ten states (§21).

### Phase 3 — Strategy Intelligence

Strategy board from `belief_system`; confidence **always** with sample size; immature-sample
treatment; `belief_history` for the confidence timeline; frozen state; decision evaluation.
Hypotheses only once the table has rows.
**Acceptance:** no statistic without `n`; no merged environments; frozen ≠ broken ≠ no-data; every
confidence change traceable to a cause.

### Phase 4 — Operations

Event log; alerts; Telegram delivery status; the operator action set behind the §19 safety model;
audit trail actually written and viewable.
**Acceptance:** every mutating action produces an `audit_events` row with actor, before/after and
reason; every trading action requires typed confirmation and carries an idempotency key.

### Phase 5 — Hardening

WCAG 2.2 AA; performance (gzip, defer, lazy mini-app, retention on `equity_snapshots`, broker request
coalescing, `visibilitychange` gating); responsive at all five viewports; visual regression;
production observability.
**Acceptance:** zero AA violations in automated + manual audit; cold load <400 KB transferred; idle
request rate ≤12/min; no unbounded table growth; visual regression covers every screen × every state.

---

## 33. Prioritized Backlog

**P0 — blocker**

| ID | Title | Problem | Evidence | Solution | Effort | Owner |
|---|---|---|---|---|---|---|
| P0‑01 | Equity chart shows the wrong series | Renders SBER candles as portfolio equity | §27.2 #1 | Read `equity_snapshots`, resample on market time | M | Backend |
| P0‑02 | All prices 32 days stale, unlabelled | `max(candles.time)` = 2026‑06‑26 | §27.2 #2 | Fix the loader; surface candle age everywhere | M | Backend |
| P0‑03 | `avg_profit_pct` = `AVG(ABS(...))` | An all-losing account reports +16,07 % | §27.2 #3 | Correct the aggregate | S | Backend |
| P0‑04 | `max_drawdown` unit collision | −23,7 % renders as −0,2 % | §27.2 #4 | Split `_pct` / `_abs` | S | Backend |
| P0‑05 | No authentication | IP-based; 0 of 52 routes need a secret | S1 | Real auth + session | L | Backend |
| P0‑06 | No CSRF | 10 of 12 mutating endpoints drive-by exploitable | S2 | Tokens + no mutating GETs | M | Backend |
| P0‑07 | 31 unescaped `innerHTML` sinks | Ticker → `onclick` attribute | S5 | Escape helper + audit every sink | M | Frontend |
| P0‑08 | Migration aborts on a legacy DB | Index before ALTER, one transaction | §27.1 | Ship the reorder; per-statement transactions | S | Backend |
| P0‑09 | Sandbox/live indistinguishable | `is_sandbox` filtered nowhere; no UI badge | §27.2 #7 | Filter everywhere + `EnvironmentBadge` | M | Both |
| P0‑10 | Stale data stamped as fresh | `allSettled` + unconditional `syncStatus:'live'` | §21 | Per-slice status; never claim fresh on partial | M | Frontend |

**P1 — required**

`P1‑01` orange → white accent, full token replacement · `P1‑02` Geist self-hosted, Orbitron removed ·
`P1‑03` `--qf-text-muted` contrast fix (48 uses) · `P1‑04` CTA contrast 2.30:1 · `P1‑05` tabular
numerals everywhere · `P1‑06` engine Start/Stop confirmation + disabled state · `P1‑07` credential
Clear confirmation · `P1‑08` paper-trades envelope fix (35 rows → 0 rendered) · `P1‑09` populate
`skipped_signals` · `P1‑10` `aria-live` regions · `P1‑11` remove the 13 infinite animations ·
`P1‑12` `document.title` + URL routing · `P1‑13` keyboard-shortcut modifier guard (⌘R is blocked) ·
`P1‑14` confidence always with `n` · `P1‑15` audit trail written for every mutation.

**P2 — important**

Table alignment in 3 tables · position close UI (API exists, no control) · gzip + `defer` + lazy
mini-app · `equity_snapshots` retention · broker request coalescing + negative caching ·
`visibilitychange` gating · `docker ps` off the request path · chart disposal + `ResizeObserver` ·
per-cell staleness · the eight distinct empty states · selected row + keyboard table traversal ·
Risk section · System Health section · Event Log · mini-app out of the operational rail · CSP
`/miniapp` path bug · SRI on CDN scripts.

**P3 — polish**

Radius/shadow consolidation · glass → flat · icon set unification · bilingual parity with the site ·
`prefers-contrast` / `forced-colors` · monitoring table mode · wall-display density · sparkline
polish.

---

## 34. Acceptance Criteria for the Future Redesign

**Visual** — every colour resolves through a shared token; **zero** raw hex/rgba outside the token
file (baseline 36 hex / 126 rgba); no orange anywhere without an explicit owner decision; ≤6 rendered
font sizes (baseline 20); ≤7 radii (baseline 11); ≤3 shadows (baseline 34); status semantics identical
on every screen; CI fails the build on any violation, with the dashboard inside the linter's `ROOT`.

**Data** — every metric traceable to a documented source; no fabricated or placeholder value in any
shipped screen; sandbox/live/backtest/forward visibly separated on every row; stale data always
visibly stale, per cell; every average accompanied by its sample size; no GET mutates state.

**UX** — system health readable in 5 seconds; open positions one interaction from landing; the reason
for a rejected signal available without reading logs; a critical state impossible to miss; no two
panels contradict each other; every data region implements all ten states.

**Accessibility** — WCAG 2.2 AA with no exceptions; full keyboard operation including tables; visible
focus at ≥3:1; no colour-only status; `prefers-reduced-motion` honoured including iteration count;
all interactive targets ≥24×24 (≥44×44 on touch); `aria-live` for every asynchronous update.

**Engineering** — every endpoint documented with a typed contract; zero SQL in HTTP handlers; zero
business logic in templates; one structured error envelope; one formatting authority; visual
regression covering every screen × every state; route-level test coverage where there is currently
none.

---

## 35. Decisions Required from the Product Owner

| ID | Decision | Options | Recommendation | Consequence | Blocks |
|---|---|---|---|---|---|
| **D‑01** | Canonical repository path | Downloads copy · `Documents/GitHub` copy · consolidate | **Consolidate onto one, update `CLAUDE.md`** | A second team will otherwise work against a tree with no `website/` at all | Everything |
| **D‑02** | Dashboard stays Flask or moves | A · B · C | **A now, B under §31 conditions** | Choosing B first spends the budget on a port and ships the same pixels | Phase 1 scope |
| **D‑03** | Is a cold accent wanted at all? | None · light-only ≤0.28α · as ink | **Light only, sign-in + empty states** | As ink it breaks the site's doctrine and its lint rule | Token package |
| **D‑04** | Fully monochrome, or keep saturated trade colours? | Site's `#7fd8a8`/`#f08a9c` · keep `#00c076`/`#f6465d` · hybrid | **Adopt the site's pair** (11.6:1 and 8.9:1 — *more* legible than today's) | Traders may report the greens feel "quieter"; the distinction is preserved and reinforced by sign | §8 |
| **D‑05** | Warning colour | `#d9c187` · fully achromatic + icon | **`#d9c187`**, far from `#F7931A` in chroma and luminance | Achromatic is more disciplined but slower to detect peripherally | §8.3 |
| **D‑06** | Which operator actions are allowed from the web dashboard at all? | Read-only · +operator · +trading | **Read-only + operator until Phase 4** | Trading actions today have no auth, no CSRF, no audit, no idempotency | §19, §26 |
| **D‑07** | Is live mode in scope for v1? | No · yes behind 2FA | **No** | Live with `is_sandbox` unfiltered is a financial-loss risk | §27.2 #7 |
| **D‑08** | Landing screen | Overview · Positions | **Overview**, restructured per §13 | — | Phase 2 |
| **D‑09** | Delete or complete `bot/auth/` | Delete · complete | **Delete, then build real auth in Phase 0** | Keeping dead code that `CLAUDE.md` describes as live is active misinformation | P0‑05 |
| **D‑10** | Mobile: monitoring only, or control? | Monitoring + emergency stop · full control | **Monitoring + emergency stop** | Full control on a phone with no confirmation model is an accident | §22 |
| **D‑11** | What is confidential on this surface? | Broker tokens · balances · strategy logic | **Define explicitly** | Drives masking, the permission matrix, and what may appear in logs | §26.3 |
| **D‑12** | Quant Hunter's place | Operational rail · separate route · removed | **Separate lazy route** | 67 KB on every terminal load, and a game one keystroke from Learning | §11 |


---

## 36. Final Recommendation

### 36.1 How far is the dashboard from the site?

**Visually: far, but shallowly.** Every difference is a value in a token file or a class in a
template. Nothing structural prevents alignment — the two systems already share an easing curve
byte-for-byte, and `dashboard.html` interpolates no server data at all. The measurable distance is
36 hex literals, 20 rendered font sizes, 11 radii, 34 shadows and three typefaces, against a site
that ships four surfaces, six type roles, seven radii, three shadows and one family.

**Substantively: much further, and deeply.** The site promises «Терминал оператора, а не витрина» —
an operator's terminal, not a showcase — and its own preview leads with engine state, mode, queue
depth and last event, under a permanent `ПЕСОЧНИЦА` badge. The real terminal leads with a balance
tile and three zero-value PnL tiles, shows no mode at all, and plots the wrong series. **The gap that
matters is not that the dashboard looks unlike the site. It is that the dashboard does not yet keep
the promise the site makes about it.**

### 36.2 Can it be aligned stylistically without replacing the architecture?

**Yes, unambiguously.** `dashboard.html` contains 18 Jinja expressions, all `url_for`; `index()`
renders it with no context. The dashboard is already a client-rendered SPA with its own store, API
layer and sync layer. A complete visual alignment touches one template, two stylesheets and the
render functions — **zero Python**.

Three caveats, none blocking: the CSP in `security/http_middleware.py:10-18` must be updated for any
new asset host; the `?v=16` cache-buster is hardcoded 18 times and must be bumped together; and
`http_middleware.py:49` has a live path bug that currently prevents the Telegram Mini App from being
framed.

### 36.3 The three things to fix before any visual work

1. **Data truth.** The four blockers in §27.2 — the fabricated equity curve, the 32-day-stale prices
   with no age indicator, `AVG(ABS())` reporting profit on a losing account, and the drawdown unit
   collision. A redesign renders these more convincingly, which makes them more dangerous.
2. **Environment separation.** `is_sandbox` filtered everywhere, plus a permanent environment badge.
   Until a trader can tell sandbox from live at a glance, no amount of polish is safe — and the site
   has already promised this badge to the market.
3. **Authentication and CSRF.** S1–S3. There is currently no credential requirement on any route and
   no CSRF anywhere, while `bot/auth/` — dead code — is documented as the live security stack. Fix
   the reality and fix the documentation together.

### 36.4 Recommended architecture

**Improve in place (Option A) now. Move to a Flask API + Next.js dashboard (Option B) later, and only
under the stated conditions in §31.**

The migration one *should* plan for is not a framework migration — it is a **shared design-token
package**: one `tokens.css` owned by the site, consumed by both surfaces, with
`check-design-tokens.mjs` extended to lint the dashboard's CSS. That delivers the user's actual goal
— one visual identity across two surfaces — with no framework coupling, no duplicated business logic,
and no second deployment target. **Do not choose Option C**; coupling the operator's terminal to the
marketing site's release cadence is an operational risk with no benefit that Option B does not also
provide.

### 36.5 The first implementation prompt to run after this audit is approved

Not a redesign prompt. **Phase 0, item one:**

> Fix the QuantFlow dashboard's data contract. In `bot/`: (1) make `/api/equity` read
> `equity_snapshots` resampled on market time instead of falling through to candle data; (2) correct
> `avg_profit_pct` from `AVG(ABS(pnl_pct))` to a signed mean; (3) split `max_drawdown` into
> `max_drawdown_pct` and `max_drawdown_abs` and fix the unit mismatch in the Analytics renderer;
> (4) expose `max(candles.time)` as a `data_age_seconds` field on every endpoint that returns a
> price-derived value; (5) make `/api/platform/paper/account`, `/portfolio`, `/overview` and
> `/signals` read-only — move the `equity_snapshots` insert and the `trading_signals` insert onto the
> engine's own schedule. Add a regression test per item. Change no CSS, no template, no JS.

Ship that, verify it against the live database, and only then start Phase 1. **D‑01** (the canonical
repository path) must be answered before anything is committed, or the work may land in a tree the
next team does not use.

### 36.6 What must categorically not be done in the redesign

- **Do not restyle before Phase 0.** A trustworthy-looking instrument reporting +16 % on a losing
  account is strictly worse than the current one.
- **Do not port the site's motion.** No scroll-driven reveal on data — measured live, those wrappers
  sit at `opacity: 0.0456` until an animation runs. No Lenis inertia in a table. No magnetic cursor
  near a control that closes a position.
- **Do not keep any infinite animation on a healthy state.** 13 exist today, and they spend the
  interface's only peripheral-alarm channel on "nothing is wrong".
- **Do not reintroduce orange under a new name.** The warning token must be visibly distant from
  `#F7931A` in both chroma and luminance, or the redesign reads as a repaint.
- **Do not let colour be the only carrier of meaning.** Every status ships with a word. The
  acceptance test is a greyscale screenshot (§8.5), which the current Overview fails in three places.
- **Do not make mobile a scaled desktop terminal.** Monitoring plus one emergency stop, behind typed
  confirmation.
- **Do not merge the marketing preview with the operational dashboard.** They are separate artefacts
  (§1.5). No redesign task may modify `website/src/components/sections/dashboard/**`.
- **Do not add a candlestick chart for visual resemblance to TradingView.** A named workflow, or it
  does not ship.
- **Do not show a number without its unit, its period, its environment and — for any average — its
  sample size.**


---

## No-Change Verification

### Initial repository state (captured before any audit work)

```
branch  quant-site-approved-reference-redesign
HEAD    80ec1218051203427148437fa124330bdbe39497

git status --short
 M .gitignore
 M bot/qf_platform/schema.py
?? .coverage
?? approved-stitch-reference.jpg
```

All four entries **pre-existed** this audit. They are the user's own working-tree changes and were
not touched, staged, reverted or reformatted. `.gitignore` (+8 lines) and
`bot/qf_platform/schema.py` (+5/−2) carry byte-identical diffs before and after.

### Final repository state

```
git status --short
 M .gitignore                                        <- pre-existing, untouched
 M bot/qf_platform/schema.py                         <- pre-existing, untouched
?? .coverage                                         <- pre-existing, untouched
?? approved-stitch-reference.jpg                     <- pre-existing, untouched
?? design/DASHBOARD_APPROVED_REFERENCE_AUDIT.md      <- created by this audit

git diff --stat
 .gitignore                | 8 ++++++++
 bot/qf_platform/schema.py | 7 +++++--
 2 files changed, 13 insertions(+), 2 deletions(-)
```

`git diff --stat` is unchanged from the initial state — the audit contributed **zero** modifications
to tracked files. The single new entry is the untracked audit document.

### File created

```
design/DASHBOARD_APPROVED_REFERENCE_AUDIT.md
```

`design/DASHBOARD_APPROVED_REFERENCE_AUDIT.md` did not exist at audit start, so the
`_2026-07` fallback filename was not required.

### Confirmations

| Statement | Status |
|---|---|
| Production code (Python, Flask routes, Jinja/HTML, CSS, JS, TS, React, Next.js) modified | **No** |
| SQL, database schema, or migrations modified | **No** |
| Docker configuration, `.env`, `CLAUDE.md`, manifests, lock files, linter configs modified | **No** |
| Tests, Telegram interface, trading logic, learning modules, or API modified | **No** |
| Documentation modified | **No** — one new file created, nothing existing edited |
| Automatic formatting run | **No** |
| Dependencies installed | **No** |
| Migrations executed | **No** — and the dashboard was deliberately **not launched** because doing so runs DDL (§1.6) |
| Data written to PostgreSQL | **No** — read-only `SELECT` and `\d` introspection only |
| Test trades created | **No** |
| Trading loop / sandbox trading / broker commands started | **No** |
| Database seeded | **No** |
| Files deleted or renamed | **No** |
| UI prototype, Figma mockup, or new UI component created | **No** |
| Known defects fixed | **No** — including the four HTTP 500s and the balance-tile wrap, deliberately left in place |
| Git mutations (`checkout`, `switch`, `reset`, `clean`, `stash`, `rebase`, `merge`, `commit`, `push`) | **No** |

### Runtime checks performed

| Check | Detail |
|---|---|
| **Next.js site launched and stopped** | `npm run dev` on port 3000 with dependencies already installed. Design tokens read via `getComputedStyle` on the running site; page structure and the terminal preview's copy measured live; the site was then stopped. `.next/` and `*.tsbuildinfo` are gitignored (`website/.gitignore:17,40`) — `git status --short` was byte-identical before and after. |
| **Flask dashboard — NOT launched** | Starting it calls `ensure_platform_schema()` at import (`bot/ui/dashboard.py:70`), which executes ~27 `ALTER TABLE` statements. That is a migration, which this audit is forbidden from running. |
| **Read-only PostgreSQL introspection** | `docker exec trading_db psql -U trader -d trading_bot` — `\d`, `information_schema` queries, `SELECT count(*)`, `SELECT max(...)`. No `INSERT`/`UPDATE`/`DELETE`/DDL was issued. |
| **Log files read** | `logs/dashboard.log` (749 KB) read, not written. |
| **Runtime evidence from earlier in the session** | One desktop screenshot of the Overview view and one complete request log for a cold page load, both captured before the audit constraints were issued, and treated as valid runtime evidence. |
| **Temporary artefacts** | All working files were written to the session scratchpad outside the repository. No screenshot, log or intermediate file was written into the repository. |

### Scope limitation to carry forward

Because the dashboard could not be safely launched, every claim about viewport behaviour at
1280×800, 1024×768, 768×1024 and 390×844, every computed-contrast measurement, every
keyboard-traversal order, and every loading/empty/error/stale rendering is **source-derived** and is
marked `Confidence: Medium — requires runtime verification`. Phase 0 (§32) includes re-running this
pass once the schema defect is shipped and a read-only launch mode exists.
