# Worktree Policy — изоляция агентов

Каждый агент работает в собственном Git worktree. Это единственный механизм, гарантирующий, что два агента не изменят один working tree.

Общие правила — [`AGENTS.md §3`](../../AGENTS.md).

---

## Топология

```
/Users/danila/Downloads/Trading-Bot-merge-learning-nik      ← canonical working tree (владелец)
/Users/danila/OpenHands/worktrees/Quant/                    ← корень worktree агентов
    agent-claude-rm-p0-002-execution-mode/
    agent-codex-rm-p0-003-add-ci/
    agent-gemini-rm-p1-021-core-tests/
    infra-openhands-multi-agent-setup/
```

Правила:

1. Canonical working tree — **только владельцу**. Агенты в нём не работают, не переключают ветки, не коммитят.
2. Каталог worktree = ветка с заменой `/` на `-`. Ветка `agent/codex/rm-p0-003-add-ci` → каталог `agent-codex-rm-p0-003-add-ci`.
3. Один worktree — одна ветка — одна задача — один агент.
4. Worktree создаются и удаляются **только** скриптами `scripts/agents/`.
5. Worktree живут **вне репозитория**, поэтому не попадают в `git status` canonical дерева и не требуют записи в `.gitignore`.

---

## Почему не встроенный worktree OpenHands Agent Canvas

У Canvas есть собственный режим `worktree`, который создаёт рабочий каталог вида `/home/openhands/workspace/project/<conversation-id>` **внутри файловой системы контейнера**.

Проект его **не использует**, потому что такой каталог:

- не виден с хоста — владелец не может посмотреть diff, а Control Center не может проверить состояние;
- не виден в `git worktree list` canonical репозитория — нет учёта параллельной работы;
- исчезает при пересоздании контейнера — результат теряется;
- не позволяет двум агентам ссылаться на один base commit проверяемым образом.

Вместо этого используются **host-visible worktree**: каталоги на macOS, смонтированные в контейнер по тем же абсолютным путям. Внутри контейнера `/Users/danila/OpenHands/worktrees/Quant/...` — это тот же каталог, что и на хосте, поэтому:

- git-пути (`.git` файл worktree указывает на `…/Downloads/Trading-Bot-merge-learning-nik/.git/worktrees/<name>`) разрешаются одинаково на хосте и в контейнере;
- команды из документации работают без трансляции путей;
- владелец видит всё, что делает агент, в реальном времени.

**Требование к монтированию:** canonical repository и worktree root монтируются по идентичным абсолютным путям. Монтировать `/Users/danila` целиком запрещено. `/Users/danila/Documents/GitHub/Trading-Bot` агентам недоступен.

---

## Что в новом worktree отсутствует (проверено)

Git worktree материализует **только отслеживаемые** файлы. Всё, что в `.gitignore`, в новый worktree не попадает. Практические следствия, измеренные на этой установке:

| Отсутствует | Следствие | Что делать |
|---|---|---|
| `.env` | **pytest даёт 132 passed / 101 skipped вместо 161 / 72.** Часть тестов молча пропускается — можно принять неполный прогон за полный | либо `create-worktree.sh … --link-env` (симлинк, не копия), либо честно указать в handoff, что прогон неполный, с обоими числами |
| `website/node_modules` | все 6 гейтов сайта не запускаются | `cd website && npm ci` в своём worktree (~600 МБ на worktree) |
| `logs/`, `bot/data/*.json` | приложение не имеет runtime-состояния | задачи, требующие живого запуска бота или Dashboard, выполняет владелец в каноническом дереве |
| `.next/`, `__pycache__`, `.coverage` | нет кэшей сборки | первая сборка дольше — это нормально |

**Обязательно к handoff:** если pytest запускался без `.env`, в поле «Tests and results» указываются оба числа и пометка «неполный прогон, `.env` отсутствует». Отчёт «161 passed» из worktree без `.env` невозможен и означает ошибку.

`--link-env` создаёт **символическую ссылку**, а не копию: секрет остаётся в единственном месте, `.env` покрыт `.gitignore`, поэтому в коммит не попадёт. Секрет при этом достижим из worktree — его содержимое всё равно нельзя выводить (`SECURITY_POLICY.md §1`).

---

## Скрипты

Все три лежат в `scripts/agents/`, требуют `bash`, работают с `set -euo pipefail`.

### `create-worktree.sh <branch> [base-branch] [--link-env]`

```bash
scripts/agents/create-worktree.sh agent/codex/rm-p0-003-add-ci quant-site-approved-reference-redesign
```

Что делает и что проверяет:

- валидирует имя ветки по разрешённому шаблону (`agent/{claude,codex,gemini,openhands}/…` или `infra/…`);
- запрещает `main`, `master`, `merge-learning-nik` и текущую активную ветку разработки как **целевую** ветку задачи;
- требует, чтобы canonical working tree не имел незакоммиченных **отслеживаемых** изменений (untracked-файлы допускаются и не переносятся в worktree);
- отказывается, если ветка или каталог worktree уже существуют (повторное использование worktree запрещено);
- создаёт ветку от base branch и worktree в `/Users/danila/OpenHands/worktrees/Quant/<slug>`;
- задаёт в новом worktree git identity `openhands-<роль>` **worktree-scoped**, не трогая общий `.git/config` — см. раздел «Git identity» ниже;
- печатает путь worktree, ветку и base commit — их агент вставляет в handoff.

### `status-worktrees.sh`

```bash
scripts/agents/status-worktrees.sh
```

Показывает по каждому worktree: путь, ветку, HEAD, число незакоммиченных файлов, ahead/behind относительно upstream, наличие открытого PR (если `gh` авторизован). Отдельно предупреждает, если canonical working tree содержит незакоммиченные отслеживаемые изменения.

### `close-worktree.sh <branch> [--force]`

```bash
scripts/agents/close-worktree.sh agent/codex/rm-p0-003-add-ci
```

- отказывается удалять worktree с незакоммиченными изменениями или с неотправленными коммитами — если не передан `--force`;
- `--force` требуется всегда для потери данных, по умолчанию удаление безопасное;
- удаляет worktree, затем предлагает команду удаления локальной ветки (саму ветку не удаляет — она может быть в открытом PR);
- никогда не трогает удалённые ветки.

---

## Порядок работы агента

```bash
# 1. Создать
scripts/agents/create-worktree.sh agent/gemini/rm-p1-021-core-tests quant-site-approved-reference-redesign

# 2. Войти и подтвердить
cd /Users/danila/OpenHands/worktrees/Quant/agent-gemini-rm-p1-021-core-tests
git rev-parse --show-toplevel        # должен быть этот каталог
git rev-parse --abbrev-ref HEAD      # agent/gemini/rm-p1-021-core-tests
git rev-parse --short HEAD           # base commit → handoff
git status --porcelain               # пусто

# 3. Работать только здесь

# 4. Проверки, коммит, push, PR (docs/GIT_WORKFLOW.md)

# 5. Handoff (docs/agents/HANDOFF.md)

# 6. После приёмки
scripts/agents/close-worktree.sh agent/gemini/rm-p1-021-core-tests
```

---

## Git identity: почему агент её не настраивает

В linked worktree `git config --local` пишет **не** в конфиг worktree, а в общий `.git/config` канонического дерева. Это проверено на практике: агент без identity выполнил `git config --local user.name/user.email`, и канонический репозиторий стал подписывать коммиты владельца именем агента.

Поэтому:

- на репозитории включён `extensions.worktreeConfig = true`, поэтому `git config --worktree` пишет в `.git/worktrees/<name>/config.worktree`, а не в общий конфиг; если флаг окажется выключен, `create-worktree.sh` включает его сам, а при неудаче отказывается задавать identity вовсе;
- `create-worktree.sh` задаёт identity **worktree-scoped** (`git config --worktree`) по префиксу ветки: `openhands-claude`, `openhands-codex`, `openhands-gemini`, `openhands-openhands`, `openhands-infra`. Роль переопределяется переменной `QUANT_AGENT_IDENTITY` (`QUANT_AGENT_IDENTITY=control-center` → `openhands-control-center`), адрес — `QUANT_AGENT_EMAIL`;
- **агенту запрещено выполнять `git config` в любой области** (`AGENTS.md §6`). Отсутствие identity — дефект среды, о котором нужно сообщить, а не настраивать самому;
- canonical working tree сохраняет глобальную identity владельца;
- `close-worktree.sh` ничего дополнительно не чистит: `config.worktree` лежит в `.git/worktrees/<name>/` и удаляется вместе с worktree.

Проверка:

```bash
git -C /Users/danila/Downloads/Trading-Bot-merge-learning-nik config --local --get-regexp '^user\.'   # должно быть пусто
git -C <worktree> config --get user.name                                                              # openhands-<agent>
```

---

## Что запрещено

- Работать в canonical working tree.
- Выполнять `git config` (любая область) — см. предыдущий раздел.
- Создавать worktree вручную через `git worktree add`, минуя скрипт.
- Использовать один worktree для двух задач или двух агентов.
- Переключать ветку внутри существующего worktree (`git checkout <другая ветка>`).
- Удалять или править worktree другого агента.
- Создавать worktree внутри репозитория или внутри другого worktree.
- Монтировать в контейнер что-либо кроме canonical repository, worktree root и `~/.openhands`.

---

## Проверка изоляции

Провести после любого изменения монтирования или обновления Canvas:

```bash
# на хосте
scripts/agents/create-worktree.sh infra/wt-selftest-a <base>
scripts/agents/create-worktree.sh infra/wt-selftest-b <base>
git -C /Users/danila/Downloads/Trading-Bot-merge-learning-nik worktree list   # оба видны

# в контейнере — те же пути, независимый git status
docker exec openhands-agent-canvas git -C /Users/danila/OpenHands/worktrees/Quant/infra-wt-selftest-a status --porcelain
docker exec openhands-agent-canvas git -C /Users/danila/OpenHands/worktrees/Quant/infra-wt-selftest-b status --porcelain

# правка в A не видна в B, canonical дерево чисто
scripts/agents/close-worktree.sh infra/wt-selftest-a
scripts/agents/close-worktree.sh infra/wt-selftest-b
```

Реальные агентские задачи не начинаются, пока эта проверка не прошла.
