# CLAUDE.md — дополнения для Claude Code

> **Сначала прочитай [`AGENTS.md`](AGENTS.md).** Там находятся все общие обязательные правила: canonical root, source of truth, worktree-изоляция, терминология, обязательные проверки, git-запреты, работа с секретами, формат сдачи. Этот файл их **не повторяет** — только дополняет.
>
> Затем, если контекст проекта ещё не загружен: [`docs/agents/PROJECT_CONTEXT.md`](docs/agents/PROJECT_CONTEXT.md).

---

## Что изменилось в этом файле (важно)

До 2026-08-06 этот файл содержал ошибки, на которые опирались агенты. Все они исправлены; если ты помнишь старые утверждения из предыдущих сессий — они неверны:

| Было (неверно) | Стало (проверено по коду) |
|---|---|
| canonical root — `Documents/GitHub/Trading-Bot`, «Downloads — stale copies» | canonical root — `/Users/danila/Downloads/Trading-Bot-merge-learning-nik`; недоступной является копия в `Documents` |
| активная ветка `merge-learning-nik` | фактическая работа идёт в `quant-site-approved-reference-redesign`; ветку задачи определяет Control Center |
| Telegram-фреймворк — aiogram 3.x | `python-telegram-bot>=20` (`aiogram` — 0 вхождений в коде) |
| токен бота — `BOT_TOKEN` | `TELEGRAM_TOKEN` (`bot/config.py:37`) |
| Dashboard auth — «JWT-based» | серверные сессии + Argon2id (`bot/security/session_auth.py`, `bot/auth/session_manager.py`); `bot/auth/jwt_service.py` — legacy |
| `.env`: `DASHBOARD_SECRET_KEY`, `BYBIT_API_KEY/SECRET` | таких ключей в `.env.example` нет; фактический список — `.env.example` и `bot/config.py` |
| «Никогда не работай в Downloads» | никогда не работай в **основном** working tree — только в своём worktree (`AGENTS.md §3`) |

Правило на будущее: **любой путь и любое имя переменной проверяй по коду, а не по этому файлу.**

---

## Роль Claude Code в проекте

Основные задачи (полная матрица — [`docs/agents/AGENT_RESPONSIBILITIES.md`](docs/agents/AGENT_RESPONSIBILITIES.md)):

- архитектура и решения, затрагивающие более одного модуля;
- сложные межмодульные изменения;
- системные рефакторинги;
- security-sensitive задачи;
- финальная техническая интеграция результатов других агентов.

Claude — единственный агент, которому Control Center поручает архитектурные решения. Каждое такое решение оформляется как ADR в `docs/adr/` (`AGENTS.md §9`).

Claude **не** является приёмщиком собственной работы: независимую проверку делают Codex (реализация, тесты, сборка) и Gemini (архитектурная и UX-альтернатива).

---

## Особенности запуска

Claude Code работает как ACP-агент внутри контейнера OpenHands Agent Canvas:

- Agent Profile: `Claude Code — Quant Architecture`;
- ACP-сервер: `claude-agent-acp` (вложен в образ, `/opt/acp-node/bin/`);
- аутентификация: backend-секрет `CLAUDE_CODE_OAUTH_TOKEN` в хранилище OpenHands. Keychain хоста контейнеру не виден — это ожидаемо.

Пути внутри контейнера совпадают с путями на macOS (`/Users/danila/...`), поэтому команды из документации применимы без трансляции. Проверяй фактический корень через `git rev-parse --show-toplevel`.

---

## Локальный контекст Claude в репозитории

- `.claude/launch.json` — конфигурация запуска, коммитится.
- Пользовательские настройки Claude Code (`~/.claude/`) в репозиторий не попадают и не должны.
- Skills, hooks и MCP-серверы хоста в контейнерной беседе недоступны: набор MCP задаётся профилем OpenHands.

---

## Что Claude делает в начале каждой задачи

1. Команды из `AGENTS.md §1` (корень, ветка, commit, статус).
2. Прочитать Task Specification от Control Center (формат — `docs/agents/TASK_SPECIFICATION.md`).
3. Убедиться, что работа идёт в выделенном worktree, а не в основном дереве:
   ```bash
   git rev-parse --show-toplevel   # должен быть под /Users/danila/OpenHands/worktrees/Quant/
   ```
4. Если задача архитектурная — проверить `docs/source/14_OPEN_QUESTIONS_AND_DECISIONS.md`: возможно, решение заблокировано открытым вопросом и задачу нельзя начинать.
5. В конце — handoff по `docs/agents/HANDOFF.md`, без исключений.
