#!/usr/bin/env bash
# QuantFlow — Project Validation Script
# Run before every commit or deployment to catch issues early.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0
WARNINGS=0

pass()  { echo "  ✓  $1"; }
warn()  { echo "  ⚠  $1"; WARNINGS=$((WARNINGS + 1)); }
fail()  { echo "  ✗  $1"; ERRORS=$((ERRORS + 1)); }
header(){ echo ""; echo "── $1 ──────────────────────────────────────────────"; }

echo "═══════════════════════════════════════════════════"
echo "  QuantFlow Project Validation"
echo "  Root: $REPO_ROOT"
echo "═══════════════════════════════════════════════════"

# ─── Git ────────────────────────────────────────────────────────────────────
header "Git"

# Correct repo root
if [[ "$REPO_ROOT" == *"Documents/GitHub/Trading-Bot"* ]]; then
    pass "Canonical repo path"
else
    fail "Wrong repo path: $REPO_ROOT — must be in Documents/GitHub/Trading-Bot"
fi

# Correct branch
BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
if [[ "$BRANCH" == "merge-learning-nik" ]]; then
    pass "Active branch: $BRANCH"
else
    warn "Active branch is '$BRANCH', expected 'merge-learning-nik'"
fi

# Remote configured
REMOTE=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || echo "")
if [[ "$REMOTE" == *"Pomiranov/Trading-Bot"* ]]; then
    pass "Remote: $REMOTE"
else
    fail "Wrong or missing remote: $REMOTE"
fi

# No stale .pyc in index
if git -C "$REPO_ROOT" ls-files | grep -q "\.pyc$"; then
    warn ".pyc files are tracked — run: git rm -r --cached '*.pyc'"
else
    pass "No .pyc files tracked"
fi

# ─── Required files ─────────────────────────────────────────────────────────
header "Required Files"

REQUIRED_FILES=(
    "bot/main.py"
    "bot/ui/dashboard.py"
    "bot/config.py"
    "requirements.txt"
    "docker-compose.yml"
    ".env.example"
    ".gitignore"
    "CLAUDE.md"
    "start.sh"
    "start.ps1"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$REPO_ROOT/$f" ]]; then
        pass "$f"
    else
        fail "Missing: $f"
    fi
done

# .env (not in git, but required to run)
if [[ -f "$REPO_ROOT/.env" ]]; then
    pass ".env present"
else
    warn ".env missing — copy from .env.example and fill in secrets"
fi

# ─── No duplicates ──────────────────────────────────────────────────────────
header "Duplicate Detection"

DUPLICATES=(
    "/Users/danila/Downloads/Trading-Bot-main"
    "/Users/danila/Downloads/Trading-Bot-quantflow-nik"
)
for dup in "${DUPLICATES[@]}"; do
    if [[ -d "$dup" ]]; then
        warn "Stale copy exists: $dup — safe to delete once work is confirmed committed"
    else
        pass "Stale copy removed: $dup"
    fi
done

# ─── Python environment ─────────────────────────────────────────────────────
header "Python"

PY=$(python3 --version 2>/dev/null || echo "")
if [[ -n "$PY" ]]; then
    pass "$PY"
else
    fail "python3 not found"
fi

# Check critical imports
python3 -c "import flask" 2>/dev/null && pass "flask installed" || warn "flask not installed — run: pip3 install -r requirements.txt"
python3 -c "import telegram" 2>/dev/null && pass "python-telegram-bot installed" || warn "python-telegram-bot not installed"
python3 -c "import psycopg2" 2>/dev/null && pass "psycopg2 installed" || warn "psycopg2 not installed"

# ─── Database ───────────────────────────────────────────────────────────────
header "Database"

if docker ps 2>/dev/null | grep -q "trading_db"; then
    pass "TimescaleDB container running"
else
    warn "TimescaleDB not running — run: docker-compose up -d"
fi

if docker ps 2>/dev/null | grep -q "trading_adminer"; then
    pass "Adminer container running (http://localhost:8080)"
else
    warn "Adminer not running"
fi

# ─── Node / Website ─────────────────────────────────────────────────────────
header "Node.js / Website"

NODE=$(node --version 2>/dev/null || echo "")
if [[ -n "$NODE" ]]; then
    pass "Node: $NODE"
else
    warn "Node.js not found — required for website"
fi

if [[ -d "$REPO_ROOT/website/node_modules" ]]; then
    pass "website/node_modules present"
else
    warn "website/node_modules missing — run: cd website && npm install"
fi

# ─── Port checks ────────────────────────────────────────────────────────────
header "Ports"

check_port() {
    local port=$1 name=$2
    if lsof -i ":$port" -sTCP:LISTEN -t &>/dev/null; then
        pass "Port $port in use ($name is running)"
    else
        warn "Port $port not listening ($name not running)"
    fi
}

check_port 5001 "Dashboard"
check_port 5432 "PostgreSQL/TimescaleDB"
check_port 8080 "Adminer"

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
if [[ $ERRORS -gt 0 ]]; then
    echo "  RESULT: $ERRORS ERROR(S), $WARNINGS WARNING(S)"
    echo "  Fix errors before committing or deploying."
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo "  RESULT: OK with $WARNINGS warning(s)"
else
    echo "  RESULT: All checks passed ✓"
fi
echo "═══════════════════════════════════════════════════"
