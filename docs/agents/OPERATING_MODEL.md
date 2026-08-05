# Operating Model — мультиагентная разработка Quant

Кто что решает, кто что делает и как результат возвращается. Обязательные правила для агентов — [`AGENTS.md`](../../AGENTS.md).

---

## Пять уровней

```
Уровень 0 — Владелец
   credentials · OAuth · разрешение на публикацию · merge
        │
Уровень 1 — ChatGPT Control Center
   roadmap · приоритеты · Task Specification · назначение исполнителя · приёмка
        │
Уровень 2 — OpenHands Agent Canvas   (http://127.0.0.1:8000/canvas/)
   Agent Profiles · беседы · workspace · логи · автоматизации · MCP
        │
Уровень 3 — Coding agents
   Claude Code · Codex · Gemini CLI · встроенный OpenHands Agent
        │
Уровень 4 — GitHub   (Pomiranov/Trading-Bot)
   единственный внешний источник истины
```

---

## Уровень 0 — Владелец

Только владелец:

- создаёт и подтверждает credentials (API keys, PAT, OAuth-логины);
- проходит browser OAuth;
- разрешает публикацию изменений наружу (первый push, первый PR);
- принимает решение о merge;
- меняет `TINKOFF_SANDBOX`, ресурсы Docker Desktop, branch protection.

Ни один агент не выполняет эти действия и не просит прислать секрет в чат.

---

## Уровень 1 — ChatGPT Control Center

Control Center:

- ведёт roadmap (единственная актуальная — `docs/source/11_MASTER_ROADMAP.md`);
- определяет приоритеты и порядок задач;
- формирует **Task Specification** ([формат](TASK_SPECIFICATION.md));
- назначает исполнителя и рецензентов;
- принимает **handoff** ([формат](HANDOFF.md));
- проводит финальную приёмку и готовит решение о merge для владельца.

**Control Center не изменяет код напрямую.** Он не коммитит, не пушит, не открывает PR — только ставит задачи и принимает результат.

Перед постановкой задачи Control Center обязан проверить `docs/source/14_OPEN_QUESTIONS_AND_DECISIONS.md`: если задача заблокирована открытым вопросом, она не ставится, а вопрос выносится владельцу.

---

## Уровень 2 — OpenHands Agent Canvas

Canvas — рабочая оболочка и точка запуска агентов. Он:

- хранит **Agent Profiles** (по одному на агента);
- запускает отдельные беседы;
- подключает workspace (worktree конкретной задачи);
- хранит логи и историю беседы;
- запускает автоматизации;
- предоставляет агентам MCP-инструменты.

**Жёсткие свойства, вытекающие из архитектуры Canvas:**

- Agent Profile **нельзя сменить внутри начатой беседы**. Отсюда: один агент = один профиль = одна беседа = одна ветка = один worktree.
- ACP-агенты запускаются подпроцессами **внутри контейнера**. Логины на хосте (`~/.claude`, `~/.codex`, `~/.gemini`) контейнеру не видны; аутентификация подаётся через OpenHands Secrets.
- Встроенный worktree-режим Canvas создаёт каталог внутри файловой системы контейнера, **не видимый с хоста**. Проект его не использует — см. [`WORKTREE_POLICY.md`](WORKTREE_POLICY.md).

Canvas не должен допускать работу двух агентов в одном working tree. Механизм — host-visible worktree на задачу, а не настройка Canvas.

---

## Уровень 3 — Coding agents

Распределение задач — [`AGENT_RESPONSIBILITIES.md`](AGENT_RESPONSIBILITIES.md). Кратко:

| Агент | Профиль в Canvas | Основное |
|---|---|---|
| **Claude Code** | `Claude Code — Quant Architecture` | архитектура, межмодульные изменения, рефакторинги, security, финальная интеграция |
| **Codex** | `Codex — Quant Implementation` | реализация по чёткому ТЗ, тесты, багфиксы, build/typecheck/lint, независимый review кода Claude |
| **Gemini CLI** | `Gemini — Quant Research` | исследование кодовой базы, альтернативы, большой контекст, документация, независимый UX/архитектурный review |
| **OpenHands Agent** | `OpenHands — Quant Maintenance` | issue triage, зависимости, повторяемые автоматизации, отчёты, мелкие изолированные задачи |

Каждый агент обязан:

1. Работать только в своём worktree.
2. Соблюдать `AGENTS.md`.
3. Вернуть handoff. Без handoff задача не считается выполненной.
4. Не выполнять merge и не публиковать наружу без разрешения (Уровень 0).

---

## Уровень 4 — GitHub

GitHub — единственный внешний источник истины для: Issues, ветвей, коммитов, Pull Requests, review, CI, истории merge.

Следствия:

- результат работы существует, только если он в ветке на `origin` и оформлен PR;
- обсуждение в беседе Canvas или в чате Control Center не является результатом;
- статус задачи определяется состоянием PR, а не утверждением агента.

> На 2026-08-06 CI в репозитории отсутствует (`RM-P0-003`, каталога `.github/` нет). До появления CI обязательные проверки выполняет агент локально и указывает exit codes в handoff.

---

## Полный цикл одной задачи

```
Control Center
  │  Task Specification (task-id, исполнитель, base branch, scope, acceptance)
  ▼
Агент
  │  scripts/agents/create-worktree.sh  →  своя ветка + свой worktree
  │  работа только внутри worktree
  │  обязательные проверки (AGENTS.md §5)
  │  коммит явно перечисленных файлов
  │  push своей ветки
  │  Draft PR
  ▼
Независимая проверка (другой агент, по назначению Control Center)
  │  свой worktree или review PR
  │  свой handoff
  ▼
Control Center
  │  приёмка по acceptance criteria
  ▼
Владелец
  │  merge · закрытие worktree
  ▼
scripts/agents/close-worktree.sh
```

---

## Границы, которые нельзя нарушать

| Действие | Кто |
|---|---|
| Изменить код | только агент, в своём worktree |
| Push ветки агента | агент |
| Открыть PR | агент |
| Approve / merge PR | только владелец |
| Создать credential | только владелец |
| Изменить `TINKOFF_SANDBOX` | только владелец |
| Изменить branch protection | только владелец |
| Поставить задачу | только Control Center |
| Признать задачу принятой | Control Center, затем владелец |
