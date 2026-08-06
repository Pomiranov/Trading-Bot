# QuantFlow — Git Workflow

Правила ветвления, коммитов и Pull Request. Общие правила агентов — [`AGENTS.md`](../AGENTS.md); изоляция worktree — [`docs/agents/WORKTREE_POLICY.md`](agents/WORKTREE_POLICY.md).

---

## The Golden Rule

```
ONE repository  →  ONE canonical working tree  →  MANY isolated worktrees
canonical: /Users/danila/Downloads/Trading-Bot-merge-learning-nik
worktrees: /Users/danila/OpenHands/worktrees/Quant/<branch-slug>
```

- **Canonical working tree принадлежит владельцу.** Агенты в нём не работают.
- **Каждая задача получает свой worktree** под `/Users/danila/OpenHands/worktrees/Quant/`.
- Вторая копия репозитория `/Users/danila/Documents/GitHub/Trading-Bot` **не используется и агентам недоступна**. Она отстаёт более чем на 140 коммитов и не содержит `website/`.

> **Исправление от 2026-08-06.** Ранее этот документ и `CLAUDE.md` объявляли canonical `Documents/GitHub/Trading-Bot` и называли Downloads-копию «stale». Это было ошибкой (`OQ-OPS-07` в `docs/source/14`): фактическая разработка всё время шла в Downloads-копии. Определяйте корень только через `git rev-parse --show-toplevel`.

---

## Repository

- **Remote:** `https://github.com/Pomiranov/Trading-Bot.git`
- **GitHub owner:** `Pomiranov`
- **Canonical local path:** `/Users/danila/Downloads/Trading-Bot-merge-learning-nik`
- **Worktree root:** `/Users/danila/OpenHands/worktrees/Quant`

---

## Branch Strategy

| Ветка | Назначение | Кто пишет |
|---|---|---|
| `main` | стабильные релизы; **база PR для dev-ветки** | только владелец (merge) |
| `quant-site-approved-reference-redesign` | **активная ветка разработки**; отрезана от `main`, behind 0 / ahead 47 | владелец |
| `agent/<agent>/<task-id>-<slug>` | задача конкретного агента | агент (push своей ветки) |
| `infra/<task-id>-<slug>` | инфраструктура, тулинг, документация среды | агент или владелец |
| `merge-learning-nik` | **не использовать** — расхождение с dev-веткой 25/134 | никто |
| `quantflow-nik` | архив, предшественник | никто |

**Двухуровневая схема PR** (решение владельца, 2026-08-06):

```
agent/<agent>/<task-id>-<slug>   ──PR──▶   quant-site-approved-reference-redesign   ──PR──▶   main
infra/<task-id>-<slug>           ──PR──▶   quant-site-approved-reference-redesign
```

- ветки задач отрезаются от **активной ветки разработки** и PR-ятся в неё же;
- активная ветка разработки PR-ится в `main` — это делает владелец;
- `main` напрямую агентам недоступна: ни push, ни PR из ветки задачи в `main`.

**Base branch задаёт Control Center в Task Specification** и всегда указывает явно.

> `merge-learning-nik` исключена из работы: она разошлась с активной ветки разработки на 25/134 коммита. Историческая ссылка на неё в `.gitignore`, старых документах и имени каталога канонической копии значения не имеет.

**Именование ветвей агентов** (валидируется `scripts/agents/create-worktree.sh`):

```
agent/claude/<task-id>-<slug>
agent/codex/<task-id>-<slug>
agent/gemini/<task-id>-<slug>
agent/openhands/<task-id>-<slug>
infra/<task-id>-<slug>
```

`<task-id>` — ID от Control Center в нижнем регистре (`rm-p0-003`). `<slug>` — 2–5 слов через дефис, только `a-z0-9-`.

---

## Рабочий цикл агента

```bash
# 1. Создать worktree и ветку (единственный разрешённый способ)
scripts/agents/create-worktree.sh agent/codex/rm-p0-003-add-ci quant-site-approved-reference-redesign

# 2. Перейти в свой worktree и подтвердить контекст
cd /Users/danila/OpenHands/worktrees/Quant/agent-codex-rm-p0-003-add-ci
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git rev-parse --short HEAD          # base commit → в handoff
git status --porcelain              # должно быть пусто

# 3. Работа только внутри этого каталога

# 4. Обязательные проверки (AGENTS.md §5) — exit codes идут в handoff
cd website && npm run typecheck && npm run lint && npm run check && npm run build
python3 -m pytest tests/
node bot/ui/static/app/format.test.mjs

# 5. Стейджить только явно перечисленные файлы — никогда `git add .`
git add docs/agents/HANDOFF.md scripts/agents/create-worktree.sh

# 6. Коммит
git commit -m "config: add worktree tooling for multi-agent setup"

# 7. Push своей ветки
git push -u origin agent/codex/rm-p0-003-add-ci

# 8. Pull Request (не merge)
gh pr create --base quant-site-approved-reference-redesign --draft \
  --title "RM-P0-003: add CI" --body-file <handoff>

# 9. Handoff в Control Center (docs/agents/HANDOFF.md)

# 10. После приёмки владельцем — закрыть worktree
scripts/agents/close-worktree.sh agent/codex/rm-p0-003-add-ci
```

---

## Commit Message Format

```
<type>: <короткое описание>

Types:
  feat     — новая функциональность
  fix      — исправление
  refactor — реструктуризация без изменения поведения
  docs     — только документация
  test     — тесты
  config   — конфигурация / инфраструктура
  security — безопасность

Примеры:
  feat: add portfolio export to CSV
  fix: handle Tinkoff sandbox error 30052 gracefully
  security: encrypt credential vault with AES-256
  config: establish host-visible worktree architecture
```

Коммит, закрывающий задачу Roadmap, упоминает её ID: `feat: add CI pipeline (RM-P0-003)`.

---

## Pull Request

- PR — **единственный** путь возврата изменений. Прямой push в `main`, `merge-learning-nik` или `quant-site-approved-reference-redesign` агентам запрещён.
- PR открывается как **Draft**, если работа не прошла независимую проверку другим агентом.
- Тело PR содержит handoff по `docs/agents/HANDOFF.md`.
- **Merge выполняет только владелец.** Агент не мержит, не закрывает чужие PR, не меняет branch protection.

---

## Что агентам запрещено в git

- `merge` в любую не свою ветку;
- `push --force` и `--force-with-lease` в любую ветку;
- `rebase` / `commit --amend` уже отправленных коммитов;
- `git add .`, `git commit -a`;
- `git checkout` / `switch` внутри canonical working tree;
- удаление ветвей и worktree других агентов;
- изменение настроек репозитория, branch protection, workflow-прав;
- вставка токена в URL remote.

---

## What Never Goes into Git

Покрыто `.gitignore` (проверено — корректно). Не коммитить никогда:

| Файл / шаблон | Причина |
|---|---|
| `.env`, `*.env.local` | токены и пароли |
| `bot/data/credential_vault.json` (+ `.tmp`) | зашифрованные брокерские креды |
| `data/credential_vault.json` | то же |
| `data/user_prefs.json` | runtime-состояние |
| `logs/` | runtime-логи |
| `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage` | артефакты Python |
| `node_modules/`, `.next/`, `*.tsbuildinfo` | артефакты Node |
| `.DS_Store` | метаданные macOS |

Отдельно: **backup-архивы и отчёты установки OpenHands в репозиторий не попадают** — они живут в `/Users/danila/OpenHands/{backups,audits}/`, вне репозитория.

---

## Merge в main (релиз)

Выполняет **только владелец**:

```bash
# из canonical working tree
git checkout main
git merge <dev-branch>
git push origin main
```

Затем на сервере: `git pull origin main`.

---

## Расхождение локального `main`

Локальный `main` имеет коммиты, разошедшиеся с `origin/main`. Приведение в порядок — операция владельца, требует `--force-with-lease` и потому агентам запрещена. Порядок действий согласуется отдельно.

---

## Как открывать Claude Code / агентов

Через OpenHands Agent Canvas (`http://127.0.0.1:8000/canvas/`), выбрав Agent Profile и указав рабочим каталогом **свой worktree**, а не canonical root.

Прямой запуск на хосте (для владельца):

```bash
cd /Users/danila/OpenHands/worktrees/Quant/<your-worktree>
claude
```

`AGENTS.md` в корне репозитория сообщает любому агенту, где он находится и какие правила действуют.
