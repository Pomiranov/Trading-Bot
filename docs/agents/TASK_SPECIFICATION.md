# Task Specification — формат постановки задачи

Каждая задача приходит от ChatGPT Control Center в этом формате. Агент, получивший постановку без обязательных полей, **не начинает работу**, а запрашивает недостающее.

Формат сдачи — [`HANDOFF.md`](HANDOFF.md).

---

## Обязательные поля

| Поле | Что содержит |
|---|---|
| **Task ID** | ID из `docs/source/11_MASTER_ROADMAP.md` (`RM-P0-003`) или `INFRA-nn` для инфраструктурных задач |
| **Цель** | одно предложение: что должно стать правдой после выполнения |
| **Business context** | зачем это нужно, на какой Launch Blocker / finding влияет |
| **Исполнитель** | `claude` · `codex` · `gemini` · `openhands` (см. `AGENT_RESPONSIBILITIES.md`) |
| **Base branch** | от какой ветки создавать; по умолчанию активная ветка разработки, не `main` |
| **Branch** | `agent/<исполнитель>/<task-id>-<slug>` или `infra/<task-id>-<slug>` |
| **Worktree** | `/Users/danila/OpenHands/worktrees/Quant/<branch-slug>` |
| **Scope** | что именно разрешено менять: файлы, каталоги, модули |
| **Out of scope** | что трогать нельзя, даже если «попутно хочется» |
| **Acceptance criteria** | проверяемые условия приёмки, по пунктам |
| **Обязательные проверки** | какие гейты из `AGENTS.md §5` применимы к этой задаче |
| **Запрещённые действия** | сверх общих запретов `AGENTS.md §6–7`, если есть |
| **Ожидаемые артефакты** | код, документ, ADR, отчёт, PR — что должно появиться |
| **Handoff recipient** | кому уходит результат: Control Center и/или агент-рецензент |

---

## Шаблон

```markdown
## Task Specification

**Task ID:** RM-P0-003
**Цель:** В репозитории появляется CI, который на каждый PR прогоняет 6 гейтов сайта и pytest.
**Business context:** Launch Blocker №7 из docs/source/00 §9. Сейчас CI отсутствует полностью
(`.github/` нет), два гейта красные незамеченными — Q-01.

**Исполнитель:** codex
**Base branch:** quant-site-approved-reference-redesign
**Branch:** agent/codex/rm-p0-003-add-ci
**Worktree:** /Users/danila/OpenHands/worktrees/Quant/agent-codex-rm-p0-003-add-ci

**Scope:**
- создать `.github/workflows/ci.yml`
- при необходимости — `docs/source/11_MASTER_ROADMAP.md` (отметить задачу закрытой)

**Out of scope:**
- не исправлять сами красные гейты (`check-dashboard-tokens.mjs` Q-02, `qa:landing` Q-03)
- не менять `package.json`, `requirements.txt`
- не менять код приложения

**Acceptance criteria:**
1. Workflow запускается на `pull_request` в активную ветку разработки.
2. Прогоняет: `npm run typecheck`, `lint`, `check`, `build` в `website/`; `pytest tests/`;
   `node bot/ui/static/app/format.test.mjs`.
3. Красные на момент задачи гейты помечены `continue-on-error` со ссылкой на Q-02 / Q-03,
   а не удалены и не «починены» молча.
4. Workflow не имеет доступа к секретам репозитория.
5. Локальный прогон тех же команд даёт те же exit codes, что зафиксированы в handoff.

**Обязательные проверки:** website 6 гейтов · pytest · format.test.mjs
**Запрещённые действия:** сверх AGENTS.md §6–7 — не включать в workflow публикацию артефактов наружу.

**Ожидаемые артефакты:**
- `.github/workflows/ci.yml`
- Draft PR в base branch
- handoff по docs/agents/HANDOFF.md

**Handoff recipient:** Control Center; независимая проверка — claude (архитектура workflow).
```

---

## Правила для Control Center

1. **Не ставить задачу, заблокированную открытым вопросом.** Перед постановкой проверить `docs/source/14_OPEN_QUESTIONS_AND_DECISIONS.md`. Если задача зависит от `OQ-…`, вынести вопрос владельцу, а не поручать агенту решать за него.
2. **Один Task ID — одна ветка — один worktree — один исполнитель.** Задача, требующая двух агентов, разбивается на две задачи со своими ID (например реализация и независимый review).
3. **Scope формулируется списком файлов или каталогов**, а не описанием намерения. «Улучшить дашборд» — не scope.
4. **Acceptance criteria проверяемы.** Каждый пункт должен либо выполняться командой с exit code, либо проверяться глазами по конкретному артефакту.
5. **Файлы повышенного риска конфликта** (`docs/source/12 §5`) указываются в scope явно, и Control Center проверяет, что их не держит другая активная задача.
6. **Base branch указывается всегда явно** — пока не решено, какая ветка является главной dev-веткой.
7. Если задача значимо меняет систему (схема БД, маршрут, модель аутентификации, торговый цикл, заявления сайта, закрытие Launch Blocker), в Scope включается обновление соответствующих документов Source Pack (`docs/source/00 §8`).

---

## Что агент делает, получив постановку

1. Проверяет наличие всех обязательных полей. Нет поля — запрос, а не догадка.
2. Выполняет команды старта сессии (`AGENTS.md §1`).
3. Создаёт worktree строго указанной командой (`scripts/agents/create-worktree.sh`).
4. Сверяет, что acceptance criteria достижимы в пределах scope. Если нет — сообщает до начала работы, а не после.
5. Работает. Затем — handoff.
