# PERMANENT CHAT POLICY — четыре постоянных рабочих чата

**Дата:** 2026-08-06. Решение владельца — `SCOPE_DECISIONS.md SD-002`
(`/Users/danila/OpenHands/audits/SCOPE_DECISIONS.md`).

Постоянных рабочих чатов **ровно четыре**. Всё остальное в списке беседы — история:
self-tests (`99 — TEST —`), инфраструктурные прогоны (`98 — SETUP —`), провалившиеся
попытки (`97 — FAILED —`). Инвентарь — `audits/CONVERSATION_INVENTORY.md`.

---

## 1. Главное правило

```
Постоянный чат
  → анализирует
  → создаёт Task Specification
  → выбирает Agent Profile
  → создаёт task conversation
  → создаёт branch + worktree
  → выполняет задачу
  → возвращает handoff
  → создаёт Pull Request
  → Постоянный чат принимает результат
```

Постоянный чат — это **место для анализа и управления**, а не место, где живёт правка.
Исполнение любой задачи, меняющей код, происходит в отдельной task conversation
со своим Task ID, своей ветвью и своим worktree.

---

## 2. Четыре чата

| № | Название беседы | Agent Profile | ACP / модель | Skills |
|---|---|---|---|---|
| 01 | `01 — Control Center — Project Manager & Business Analyst` | `Codex-Quant-Control-Center` | `codex` / `gpt-5.5` | `quant-project-manager`, `quant-business-analyst` |
| 02 | `02 — Engineering — Claude Opus 5` | `Claude-Opus-5-Quant-Engineering` | `claude-code` / `claude-opus-5[1m]` | `quant-engineering` |
| 03 | `03 — UI/UX Design — Gemini + Stitch` | `Gemini-Quant-UIUX-Stitch` | `gemini-cli` / `auto` | `quant-uiux-designer` |
| 04 | `04 — Marketing & SEO — Quant` | `OpenAI-Codex-Quant-Marketing` | `codex` / `gpt-5.5` | `quant-marketing` |

Всем четырём дополнительно доступны `quant-source-context` и `quant-handoff`,
а также правила репозитория (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) — их OpenHands
загружает как project skills независимо от провайдера.

**Имена профилей без пробелов** — API Canvas требует
`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`. Отображаемые имена из решения владельца
(«Codex — Quant Control Center», «OpenAI / Codex — Quant Marketing») соответствуют
профилям `Codex-Quant-Control-Center` и `OpenAI-Codex-Quant-Marketing`.

### Профили 01 и 04 используют один Codex auth source

Это допущено решением владельца, но профили обязаны различаться:

| Свойство | 01 Control Center | 04 Marketing |
|---|---|---|
| Profile ID | `33188f28-af59-49f6-a468-c04bffc89b07` | `2c6a0f30-8a05-4ed1-bf97-ed610db2afe2` |
| Имя | `Codex-Quant-Control-Center` | `OpenAI-Codex-Quant-Marketing` |
| Skills | PM + BA | Marketing |
| Рабочий каталог | `workspaces/control-center` | `workspaces/marketing` |
| MCP | `github_issues`, `github_pull_requests` | `github_readonly`, `github_issues` |
| Ответственность | приоритет, план, требования, приёмка | позиционирование, воронка, SEO, CRO, контент |

Backend этих профилей — **Codex ACP**, а не веб-ChatGPT. Называть его «обычным ChatGPT»
неверно. Прямой OpenAI LLM Profile через API — отдельная опциональная конфигурация,
настраивается только если владелец предоставит OpenAI API key и подтвердит отдельный
API-биллинг; на 2026-08-06 такого профиля нет.

Gemini CLI — **не** Stitch. Stitch подключён отдельным MCP-сервером (`stitch`,
stdio `npx -y @_davideast/stitch-mcp proxy`).

---

## 3. Изоляция рабочих областей

Ни два чата не используют один working tree.

| Чат | Рабочая область | Режим относительно production code |
|---|---|---|
| 01 Control Center | `/Users/danila/OpenHands/worktrees/Quant/chat-01-control-center` | **read-only** |
| 02 Engineering | `/Users/danila/OpenHands/worktrees/Quant/chat-02-engineering` | **read-only** в постоянном чате; правка — только в task worktree |
| 03 UI/UX | `/Users/danila/OpenHands/worktrees/Quant/chat-03-uiux` | **read-only** |
| 04 Marketing | `/Users/danila/OpenHands/worktrees/Quant/chat-04-marketing` | **read-only** |

Каждая область — **отдельный `git worktree` в состоянии detached HEAD**. Два обстоятельства
делают именно такой выбор единственным работающим:

1. **OpenHands загружает project skills только из git-репозитория.** `load_project_skills()`
   ищет `.agents/skills/` в рабочем каталоге и в корне его git-репозитория. Рабочая область
   вне репозитория означает, что ни один `quant-*` skill в беседу не попадёт.
2. **В контейнер смонтированы не все пути.** Смонтированы `worktrees/Quant`,
   `~/OpenHands/projects` → `/projects`, `~/.openhands` и канонический репозиторий.
   Каталог вида `~/OpenHands/workspaces/<name>` контейнеру не виден.

`detached HEAD` выбран сознательно: постоянный чат не коммитит, поэтому ветка ему не нужна,
а detached-состояние физически лишает его «своей» ветки, в которую можно было бы случайно
записать. Ветка при этом не занимается — её может взять task worktree.

**Цена решения, которую надо знать:** detached worktree заморожен на том коммите, на котором
создан. Когда `infra/openhands-multi-agent-setup` уходит вперёд, области надо обновить:

```bash
git -C /Users/danila/OpenHands/worktrees/Quant/chat-0X-<name> checkout <новый-commit>
```

Для чтения **текущего** состояния production-кода постоянный чат обращается напрямую
к каноническому репозиторию `/Users/danila/Downloads/Trading-Bot-merge-learning-nik` —
он смонтирован и доступен на чтение. Своя область нужна для правил, skills и контекста,
а не как копия кода.

Канонический working tree `/Users/danila/Downloads/Trading-Bot-merge-learning-nik`
принадлежит **владельцу**. Ни один постоянный чат в нём не работает и ничего в нём
не меняет. Читать канонический репозиторий постоянные чаты могут — он смонтирован
в контейнер.

> Канонический репозиторий смонтирован `rw` осознанно: коммит из linked worktree пишет
> в общий `.git`, поэтому `ro` технически невозможен. Изоляция держится **правилами**,
> а не правами файловой системы. Это известное свойство установки, а не недосмотр.

### Task worktree

Создаётся **только** через `scripts/agents/create-worktree.sh`, под
`/Users/danila/OpenHands/worktrees/Quant/`. Правила — [`WORKTREE_POLICY.md`](WORKTREE_POLICY.md).

- одна задача = одна ветка = один worktree;
- разные несвязанные изменения **не накапливаются** в одном долгоживущем worktree;
- флаг `--link-env` нужен, иначе `pytest` даёт 132 passed / 101 skipped вместо 161 / 72;
- `git config` агентам запрещён в любой области: в linked worktree `--local` пишет
  в общий `.git/config` канонического дерева и подписывает будущие коммиты владельца
  чужим именем.

Именование ветвей (`AGENTS.md §3`):

```
agent/claude/<task-id>-<slug>
agent/codex/<task-id>-<slug>
agent/gemini/<task-id>-<slug>
infra/<task-id>-<slug>
```

---

## 4. Права GitHub по ролям

Разграничение сделано на уровне MCP-эндпойнтов GitHub и **проверено фактически**
(`tools/list` на каждом эндпойнте):

| Чат | MCP-серверы | Инструментов | Что может |
|---|---|---|---|
| 01 Control Center | `github_issues` + `github_pull_requests` | 9 + 10 | Issues, комментарии к Issues и PR, метаданные PR (в т.ч. Draft) |
| 02 Engineering | `github` (полный `/mcp/`) | 44 | ветки, файлы, commit, push, Pull Request, review |
| 03 UI/UX | `github_readonly` + `github_issues` | 27 + 9 | чтение всего; комментарии к Issues и PR; **изменение кода недоступно** |
| 04 Marketing | `github_readonly` + `github_issues` | 27 + 9 | чтение всего; Issues и комментарии к PR; **изменение кода недоступно** |

`/mcp/readonly` содержит 27 инструментов и **ни одной** операции записи в код
(единственный «write-ish» — `run_secret_scanning`, это запуск сканирования).
Комментарии к PR у ролей 03 и 04 работают через `add_issue_comment` из toolset `issues`:
в GitHub Pull Request является Issue, поэтому комментарий в обсуждение PR доступен
**без** права менять код, ветви или мержить.

### Известное ограничение — зафиксировано честно

1. **Токен один и он широкий.** `GITHUB_TOKEN` — classic PAT со scope `admin:org`,
   `admin:enterprise`, `delete_repo`, `workflow`, `repo`. На уровне **токена**
   ограничений по ролям нет; разграничение держится на выборе MCP-эндпойнта и на
   запретах в skills. Полноценное разграничение требует fine-grained PAT с минимальными
   правами на `Pomiranov/Trading-Bot` — это OWNER CHECKPOINT.
2. **У 01 Control Center в toolset `pull_requests` присутствует `merge_pull_request`.**
   Merge выполняет владелец (`AGENTS.md §6`); запрет зафиксирован в skill, но технически
   инструмент доступен. Устраняется branch protection на `main` — тоже OWNER CHECKPOINT.

---

## 5. Что постоянный чат делает и чего не делает

| Чат | Делает | Не делает |
|---|---|---|
| 01 | статус, план, roadmap, backlog, приоритеты, зависимости, бизнес-требования, декомпозиция, Task Specification, выбор исполнителя, приёмка handoff | production code; SEO (это 04) |
| 02 | чтение кодовой базы, архитектура, implementation plan, реализация в task worktree, тесты, миграции, безопасность, commit, PR | правку в постоянном чате; merge в `main`; `git config` |
| 03 | UI/UX-аудит, состояния, дизайн-система, a11y, responsive QA, Stitch, дизайн-бриф, визуальная приёмка | production code; изменение ветвей |
| 04 | позиционирование, воронка, SEO, metadata, OG, CRO, аналитические события, контент, тарифная коммуникация | код; правовой текст; изменение ветвей |

---

## 6. Переход между чатами

Полная механика — skill [`quant-handoff`](../../.agents/skills/quant-handoff/SKILL.md).
Кратко: у задачи всегда один владелец постановки и один исполнитель; переход явный;
без handoff по 17 полям задача не сдана; спор о принадлежности решает 01 Control Center.

Правило разрешения: **как выглядит** → 03; **как объясняется и продаётся** → 04;
**как работает** → 02; **что и в каком порядке** → 01; мандат, деньги, merge,
юридический текст, секреты → **владелец**.

---

## 7. Что делать со старыми беседами

- Не удалять ничего без отдельного подтверждения владельца.
- `98 — SETUP — INFRA-01 …` и `98 — SETUP — INFRA-01-REVIEW …` хранят единственное
  доказательство работоспособности полного цикла задачи (`8e5cf09`) — сохранять.
- `99 — TEST —` хранят подтверждённые ID моделей — сохранять.
- Archive в API установленной версии Canvas **отсутствует**: `PATCH /api/conversations/{id}`
  принимает только `title` и `tags`. Поэтому «архивация» реализована переименованием
  и тегами `archived=true`, `category=<...>`, `evidence=true`.
