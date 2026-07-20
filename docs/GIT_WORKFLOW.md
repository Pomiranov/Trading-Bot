# QuantFlow — Git Workflow

## The Golden Rule

```
ONE project  →  ONE location  →  ONE truth
/Users/danila/Documents/GitHub/Trading-Bot/
```

Never edit files in `~/Downloads/Trading-Bot-*` — those are stale download copies.

---

## Repository

- **Remote**: `https://github.com/Pomiranov/Trading-Bot.git`
- **GitHub user**: `Pomiranov`
- **Canonical local path**: `/Users/danila/Documents/GitHub/Trading-Bot/`

---

## Branch Strategy

| Branch | Purpose | Who pushes |
|---|---|---|
| `merge-learning-nik` | **Main development branch** | Developer (daily work) |
| `main` | Stable releases | Merged from `merge-learning-nik` when ready |
| `quantflow-nik` | Archived (predecessor) | No new pushes |

**Always work on `merge-learning-nik`.**

---

## Daily Development Workflow

```bash
# 1. Open terminal in the project root
cd /Users/danila/Documents/GitHub/Trading-Bot

# 2. Verify you are in the right place
git status
git branch --show-current   # must show: merge-learning-nik

# 3. Pull latest changes before starting
git pull origin merge-learning-nik

# 4. Make changes (Claude Code edits files here)

# 5. Validate before committing
./scripts/validate.sh

# 6. Stage specific files (never "git add .")
git add bot/tg/handlers/portfolio.py bot/ui/dashboard.py

# 7. Commit
git commit -m "feat: describe what changed and why"

# 8. Push to GitHub
git push origin merge-learning-nik
```

---

## Commit Message Format

```
<type>: <short description>

Types:
  feat     — new feature
  fix      — bug fix
  refactor — code restructure (no behavior change)
  docs     — documentation only
  test     — test changes
  config   — config / infra changes
  security — security-related changes

Examples:
  feat: add portfolio export to CSV
  fix: handle Tinkoff sandbox error 30052 gracefully
  security: encrypt credential vault with AES-256
  config: update docker-compose for TimescaleDB 2.x
```

---

## What Never Goes into Git

These files are in `.gitignore` and must NEVER be committed:

| File/Pattern | Reason |
|---|---|
| `.env` | Contains API keys and passwords |
| `Password.env` | Contains credentials |
| `bot/data/credential_vault.json` | Encrypted broker credentials |
| `bot/data/user_prefs.json` | Runtime user state |
| `logs/` | Runtime logs |
| `__pycache__/`, `*.pyc` | Python bytecode |
| `node_modules/` | Node.js dependencies |
| `.next/` | Next.js build output |
| `.DS_Store` | macOS metadata |

---

## Merging to Main (Release)

When `merge-learning-nik` is stable and tested:

```bash
git checkout main
git merge merge-learning-nik
git push origin main
```

Then on the server: `git pull origin main`

---

## Fixing the Old Diverged `main` Branch

The local `main` branch has 3 commits that diverged from `origin/main`. These only contain README and docker-compose updates already superseded by `merge-learning-nik`. To clean up:

```bash
git checkout main
git reset --hard origin/main   # discard the 3 stale local commits
git push origin main --force-with-lease  # only if you need to push main
```

---

## Opening Claude Code Correctly

Always open Claude Code with the project root:

```bash
cd /Users/danila/Documents/GitHub/Trading-Bot
claude
```

Or in VS Code: `File → Open Folder → /Users/danila/Documents/GitHub/Trading-Bot`

The `CLAUDE.md` at the project root tells Claude Code exactly where it is and what this project is.
