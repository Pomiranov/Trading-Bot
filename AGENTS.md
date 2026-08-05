# AGENTS.md — обязательные правила для всех агентов проекta Quant

**Это единственный источник общих правил.** `CLAUDE.md` и `GEMINI.md` содержат только дополнения, специфичные для своего агента, и не повторяют этот файл. Codex читает `AGENTS.md` как главный источник правил.

Если правило в любом другом документе противоречит этому файлу — действует этот файл. Если этот файл противоречит коду — действует код (см. §2).

---

## 1. Корень проекта и ветка

**Canonical root:**

```
/Users/danila/Downloads/Trading-Bot-merge-learning-nik
```

**Remote:** `https://github.com/Pomiranov/Trading-Bot.git` (`Pomiranov/Trading-Bot`)

Вторая копия репозитория — `/Users/danila/Documents/GitHub/Trading-Bot` — **не является canonical и агентам недоступна**. Она отстаёт более чем на 140 коммитов, не содержит `website/` и не смонтирована в OpenHands. Не читайте её, не правьте, не копируйте из неё.

> Историческая справка: до 2026-08-06 `CLAUDE.md`, `docs/PROJECT_STRUCTURE.md`, `docs/GIT_WORKFLOW.md` и `scripts/validate.sh` объявляли canonical `Documents/GitHub/Trading-Bot`. Это было ошибкой (`OQ-OPS-07`). Исправлено.

**Начало любой сессии — обязательно:**

```bash
git rev-parse --show-toplevel      # фактический корень; НЕ доверяйте пути из документации
git rev-parse --abbrev-ref HEAD    # ветка
git rev-parse --short HEAD         # базовый commit — попадёт в handoff
git status --porcelain             # чужих незакоммиченных правок быть не должно
```

Если `git status` показывает изменения, которых вы не делали — **не трогайте эти файлы** и сообщите владельцу.

---

## 2. Source of Truth

Приоритет источников, от высшего к низшему:

1. **Текущий код** — окончательная истина всегда.
2. **`docs/source/`** (Source Pack, 15 документов 00–14) — истина на момент своего commit.
3. Всё остальное — справочно, с обязательной проверкой.

Внутри Source Pack роли распределены в [`docs/source/00_SOURCE_INDEX.md` §5](docs/source/00_SOURCE_INDEX.md). Ключевое:

| Вопрос | Документ |
|---|---|
| Что за проект, как запустить, терминология | `docs/source/01_CURRENT_PROJECT_CONTEXT.md` |
| Как устроена система | `docs/source/02_REPOSITORY_AND_SYSTEM_ARCHITECTURE_AUDIT.md` |
| Что делать и в каком порядке | `docs/source/11_MASTER_ROADMAP.md` |
| Состояние компонента | `docs/source/10_CURRENT_DEVELOPMENT_STATUS.md` |
| Что решить до начала работы | `docs/source/14_OPEN_QUESTIONS_AND_DECISIONS.md` |
| Кто за что отвечает (домены) | `docs/source/12_AGENT_WORKSTREAMS_AND_RESPONSIBILITIES.md` |
| Можно ли верить старому документу | `docs/source/13_STALE_DOCUMENTS_REGISTER.md` |

**Файлы кода, авторитетнее любой документации:**

| Тема | Источник истины | Устаревший дубль — не использовать |
|---|---|---|
| Схема БД | `bot/qf_platform/schema.py` | `quantflow_schema.sql` |
| Дизайн-токены сайта | `website/src/styles/tokens/` | `design/DESIGN_SYSTEM.md` |
| Торговые правила | `knowledge/rules/rules.yaml` | `knowledge/rules.yaml` |
| Переменные окружения | `bot/config.py`, `.env.example` | `CLAUDE.md` |
| Контент сайта | `website/messages/{ru,en}.json` | — |

Документы из списка «не считать актуальными» (`docs/source/13`) **нельзя** использовать как основание для решений. Среди них — `README.md`, `docs/PROJECT_ARCHITECTURE.md`, `docs/PROJECT_STRUCTURE.md`, `docs/README.md`, `design/ROADMAP.md`, `design/AUDIT_REPORT.md`, `docs/windows-deployment.md`.

Для быстрого входа в проект без чтения всего репозитория: [`docs/agents/PROJECT_CONTEXT.md`](docs/agents/PROJECT_CONTEXT.md).

---

## 3. Изоляция работы: worktree обязателен

1. Один агент = один Agent Profile.
2. Один Agent Profile = одна отдельная беседа.
3. Одна задача = одна ветка.
4. Одна ветка = один Git worktree.
5. **Ни один агент не работает в основном working tree** (`/Users/danila/Downloads/Trading-Bot-merge-learning-nik`). Основной tree — только для владельца.
6. Два агента никогда не изменяют один worktree одновременно.

Worktree создаются под `/Users/danila/OpenHands/worktrees/Quant/` **только** через `scripts/agents/create-worktree.sh`. Полные правила и порядок работы — [`docs/agents/WORKTREE_POLICY.md`](docs/agents/WORKTREE_POLICY.md).

**Именование ветвей:**

```
agent/claude/<task-id>-<slug>
agent/codex/<task-id>-<slug>
agent/gemini/<task-id>-<slug>
agent/openhands/<task-id>-<slug>
infra/<task-id>-<slug>
```

`<task-id>` — ID задачи от Control Center (например `RM-P0-003`, в нижнем регистре и без спецсимволов: `rm-p0-003`). `<slug>` — 2–5 слов через дефис.

---

## 4. Единая терминология

Обязательна в коде, коммитах, документации и handoff. Полная таблица — `docs/source/12 §3`. Кратко:

| Термин | Значение | Чем **не** является |
|---|---|---|
| **Оператор** | Пользователь Dashboard из `dashboard_users` | Не клиент, не подписчик |
| **Клиент** | Конечный покупатель | **В коде не существует** |
| **Движок** | Торговый цикл `bot/main.py` + `bot/services/bot_engine.py` | Не Dashboard, не Telegram-бот |
| **Уверенность** (confidence) | Скаляр в `belief_system`, EMA α=0.15, границы [0.05, 0.95] | **Не** вероятность, **не** ML, **не** байесовская величина |
| **Правила** | YAML в `knowledge/rules/rules.yaml` | Не модель, не стратегия целиком |
| **Песочница** | `TINKOFF_SANDBOX=true` и/или paper-торговля | Не «демо-режим интерфейса» |
| **Paper trading** | Симуляция в `paper_*` таблицах с комиссией и проскальзыванием | Не бэктест |
| **Live** | `TINKOFF_SANDBOX=false`, реальные деньги | Не «продакшн-окружение» |
| **v2 / v1** | `/api/v2` — актуальный контракт; `/api/*`, `/api/platform/*` — legacy | — |

**Запрещённые формулировки** применительно к текущей системе: «AI», «машинное обучение», «нейросеть», «байесовский», «институциональная платформа». В проекте нет ни одной ML-библиотеки и ни одного байесовского вычисления.

---

## 5. Обязательные проверки перед сдачей результата

Выполняйте применимое к изменённой части. Exit codes идут в handoff.

```bash
# Сайт (6 гейтов — все должны быть exit 0)
cd website && npm run typecheck && npm run lint && npm run check && npm run build

# Python
python3 -m pytest tests/                      # ожидается 161 passed, 72 skipped
python3 -m qf_platform.migrate --check        # безопасно, только читает

# Dashboard
node bot/ui/static/app/format.test.mjs        # ожидается 27/27
node bot/ui/static/check-dashboard-tokens.mjs # ВНИМАНИЕ: красный до вашей правки (Q-02)
```

**Известные красные гейты** (не ваша ответственность, если падали до вашей правки): `check-dashboard-tokens.mjs` (exit 1, `Q-02` / `RM-P2-015`), `npm run qa:landing` (exit 2, нет Playwright, `Q-03` / `RM-P1-020`). Не «исправляйте» их молча внутри чужой задачи — зафиксируйте в handoff и сошлитесь на ID.

---

## 6. Git: что можно и что нельзя

**Можно:** создавать ветку по правилам §3, коммитить в свой worktree, `push` своей ветки, открывать Pull Request, читать любые ветки, `fetch`.

**Нельзя:**

- `merge` в `main`, в активную ветку разработки или в любую чужую ветку — merge выполняет владелец;
- `push --force` / `--force-with-lease` в любую ветку;
- менять branch protection, настройки репозитория, workflow-права;
- `git add .` и `git commit -a` — стейджить только явно перечисленные файлы;
- `git checkout` / `switch` в основном working tree;
- удалять ветки и worktree других агентов;
- `rebase` или `amend` уже отправленных коммитов;
- коммитить `.env`, `bot/data/credential_vault.json`, `data/credential_vault.json`, `data/user_prefs.json`, содержимое `logs/`, любые ключи и токены.

Формат сообщения коммита — `docs/GIT_WORKFLOW.md`. Коммит, закрывающий задачу Roadmap, упоминает её ID.

---

## 7. Запреты, действующие для всех

- **Не переключайте `TINKOFF_SANDBOX` в `false`** — это реальные деньги. Только владелец, только явным решением.
- **Не запускайте Telegram-бота**, если может работать другой экземпляр: Telegram допускает один polling-консьюмер на токен (`A-05`).
- **Не выполняйте `python3 -m qf_platform.migrate` без `--check`** на боевой БД без бэкапа и согласования.
- **Не выполняйте `npm audit fix --force`** — тянет мажорный апгрейд Next (`S-03`).
- **Не удаляйте существующие документы** — помечайте `DEPRECATED` со ссылкой на замену (`docs/source/13`).
- **Не ослабляйте честность контента сайта** и не добавляйте цифры доходности — это ключевой актив продукта (`P-07`).
- **Не начинайте работу над клиентским кабинетом, подписками, онбордингом** до решения `OQ-ARCH-01` — это работа по неизвестному ТЗ.
- **Не правьте файлы повышенного риска конфликта** без проверки, что их не правит другое направление (список — `docs/source/12 §5`).
- **Не выводите секреты** — см. §8.

---

## 8. Секреты

Полные правила — [`docs/agents/SECURITY_POLICY.md`](docs/agents/SECURITY_POLICY.md). Минимум:

- Никогда не открывайте `.env`, `bot/data/credential_vault.json`, `~/.codex/auth.json`, credential-файлы Gemini/Claude, Keychain, хранилище секретов OpenHands.
- Никогда не выводите значение секрета — ни в ответ, ни в лог, ни в коммит, ни в PR, ни в handoff.
- Не передавайте секрет аргументом команды (он попадает в историю shell и в список процессов).
- Не вставляйте токен в URL git-remote.
- Про credential допустимо сообщать только: существует ли, тип, путь, права, дату изменения, прошла ли проверка подключения.
- Нужен новый секрет — это OWNER CHECKPOINT: опишите, что именно требуется и куда владелец должен это вставить. Не запрашивайте значение в чат.

---

## 9. Завершение задачи

Задача не считается выполненной без handoff. Формат обязателен и полон — 17 полей, [`docs/agents/HANDOFF.md`](docs/agents/HANDOFF.md).

Значимое изменение обязывает обновить Source Pack (`docs/source/00 §8`). Значимым считается: изменение схемы БД, добавление/удаление маршрута, изменение модели аутентификации, изменение поведения торгового цикла, изменение заявлений на сайте, закрытие Launch Blocker, изменение состава направлений.

Архитектурное решение, затрагивающее более одного модуля, оформляется как ADR в `docs/adr/` (формат — `website/docs/adr/0001-monogram.md`).

---

## 10. Карта документов агентской среды

| Документ | О чём |
|---|---|
| `AGENTS.md` | этот файл — общие обязательные правила |
| `CLAUDE.md` | дополнения для Claude Code |
| `GEMINI.md` | дополнения для Gemini CLI |
| `docs/agents/OPERATING_MODEL.md` | уровни ответственности, кто что решает |
| `docs/agents/AGENT_RESPONSIBILITIES.md` | какой агент какие задачи берёт |
| `docs/agents/PROJECT_CONTEXT.md` | контекст проекта для быстрого входа |
| `docs/agents/WORKTREE_POLICY.md` | изоляция, порядок работы с worktree |
| `docs/agents/TASK_SPECIFICATION.md` | формат постановки задачи |
| `docs/agents/HANDOFF.md` | формат сдачи результата |
| `docs/agents/SECURITY_POLICY.md` | секреты, границы доступа |
| `docs/GIT_WORKFLOW.md` | ветки, коммиты, PR |
