#!/usr/bin/env bash
# create-worktree.sh — создать изолированный worktree и ветку для задачи агента.
#
# Использование:
#   scripts/agents/create-worktree.sh <branch> [base-branch] [--link-env]
#
# Пример:
#   scripts/agents/create-worktree.sh agent/codex/rm-p0-003-add-ci quant-site-approved-reference-redesign
#
# --link-env создаёт СИМВОЛИЧЕСКУЮ ССЫЛКУ на .env канонического дерева. Копии секрета
# не создаётся. Нужен только задачам, которым важен полный прогон pytest: без .env
# часть тестов пропускается (132 passed / 101 skipped вместо 161 / 72).
#
# Правила и обоснование — docs/agents/WORKTREE_POLICY.md
# Секретов этот скрипт не читает, не копирует и не выводит.

set -euo pipefail

WORKTREE_ROOT="${QUANT_WORKTREE_ROOT:-/Users/danila/OpenHands/worktrees/Quant}"

# Ветки, которые нельзя занимать под задачу агента: их держит владелец.
PROTECTED_BRANCHES=(main master merge-learning-nik quant-site-approved-reference-redesign quantflow-nik)

BRANCH_PATTERN='^(agent/(claude|codex|gemini|openhands)|infra)/[a-z0-9][a-z0-9._-]*$'

die() { printf 'ОШИБКА: %s\n' "$1" >&2; exit 1; }
note() { printf '  %s\n' "$1"; }

usage() {
	cat >&2 <<'EOF'
Использование: scripts/agents/create-worktree.sh <branch> [base-branch] [--link-env]

  <branch>       agent/{claude|codex|gemini|openhands}/<task-id>-<slug>
                 или infra/<task-id>-<slug>
                 только строчные буквы, цифры, дефис, точка, подчёркивание
  [base-branch]  от какой ветки создавать; по умолчанию — ветка,
                 на которой стоит canonical working tree
  --link-env     симлинк на .env канонического дерева (копии секрета не создаётся).
                 Нужен только для полного прогона pytest. По умолчанию выключено.

Переменные окружения:
  QUANT_AGENT_IDENTITY  роль в git identity нового worktree; по умолчанию берётся
                        из префикса ветки. Итог: user.name = openhands-<роль>
  QUANT_AGENT_EMAIL     полностью задаёт user.email
                        (по умолчанию openhands-<роль>@openhands.local)
  QUANT_WORKTREE_ROOT   корень каталогов worktree

Пример:
  scripts/agents/create-worktree.sh agent/codex/rm-p0-003-add-ci quant-site-approved-reference-redesign
EOF
	exit 2
}

LINK_ENV=0
ARGS=()
for a in "$@"; do
	case "$a" in
	--link-env) LINK_ENV=1 ;;
	-*) printf 'ОШИБКА: неизвестный флаг: %s\n\n' "$a" >&2; usage ;;
	*) ARGS+=("$a") ;;
	esac
done
set -- "${ARGS[@]+${ARGS[@]}}"

[ $# -ge 1 ] && [ $# -le 2 ] || usage
BRANCH="$1"

# ── Канонический working tree ───────────────────────────────────────────────
# --git-common-dir указывает на .git основного дерева даже при запуске из worktree.
git rev-parse --git-dir >/dev/null 2>&1 || die "скрипт запущен вне git-репозитория"
COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir)"
CANONICAL="$(dirname "$COMMON_DIR")"
[ -d "$CANONICAL" ] || die "не удалось определить canonical working tree (получено: $CANONICAL)"

BASE="${2:-$(git -C "$CANONICAL" rev-parse --abbrev-ref HEAD)}"

# ── 1. Имя ветки ────────────────────────────────────────────────────────────
# Сначала защищённые ветки — чтобы на `main` выдать понятную причину, а не общий
# отказ по шаблону (шаблон их тоже не пропустит, но сообщение было бы непонятным).
for p in "${PROTECTED_BRANCHES[@]}"; do
	if [ "$BRANCH" = "$p" ]; then
		die "'$BRANCH' — защищённая ветка, её нельзя занимать под задачу агента.
       Эти ветки принадлежат владельцу: ${PROTECTED_BRANCHES[*]}
       Создайте ветку задачи вида agent/<агент>/<task-id>-<slug>.
       Если нужен worktree ОТ этой ветки — передайте её вторым аргументом:
         scripts/agents/create-worktree.sh agent/codex/<task-id>-<slug> $BRANCH"
	fi
done

# [[ =~ ]] сопоставляет значение ЦЕЛИКОМ: в отличие от `printf | grep -Eq`, где ^…$
# привязаны к строке и многострочное значение прошло бы по одной удачной строке.
if ! [[ "$BRANCH" =~ $BRANCH_PATTERN ]]; then
	die "недопустимое имя ветки: '$BRANCH'
       Разрешено: agent/{claude|codex|gemini|openhands}/<task-id>-<slug> или infra/<task-id>-<slug>
       Только строчные буквы, цифры, дефис, точка, подчёркивание.
       Примеры: agent/claude/rm-p0-002-execution-mode, infra/openhands-multi-agent-setup"
fi

# Значения identity применяются на шаге 7, но проверяются здесь — до того, как что-либо
# создано: иначе отказ оставил бы worktree без identity.
if [ -n "${QUANT_AGENT_IDENTITY:-}" ] &&
	! [[ "$QUANT_AGENT_IDENTITY" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
	die "недопустимое значение QUANT_AGENT_IDENTITY: '$QUANT_AGENT_IDENTITY'
       Разрешены строчные буквы, цифры и дефис. Пример: QUANT_AGENT_IDENTITY=control-center"
fi
if [ -n "${QUANT_AGENT_EMAIL:-}" ] &&
	! [[ "$QUANT_AGENT_EMAIL" =~ ^[^[:space:]]+@[^[:space:]]+$ ]]; then
	die "недопустимое значение QUANT_AGENT_EMAIL: '$QUANT_AGENT_EMAIL'
       Ожидается адрес вида openhands-<роль>@openhands.local, без пробелов."
fi

# ── 2. Base branch должен существовать ──────────────────────────────────────
if ! git -C "$CANONICAL" rev-parse --verify --quiet "refs/heads/$BASE" >/dev/null &&
	! git -C "$CANONICAL" rev-parse --verify --quiet "refs/remotes/origin/$BASE" >/dev/null; then
	die "base branch '$BASE' не найдена ни локально, ни в origin.
       Доступные локальные ветки:
$(git -C "$CANONICAL" for-each-ref --format='         %(refname:short)' refs/heads)"
fi

# ── 3. Canonical working tree должен быть чист по отслеживаемым файлам ──────
# Untracked-файлы допускаются: они не переносятся в worktree и не мешают.
DIRTY="$(git -C "$CANONICAL" status --porcelain --untracked-files=no)"
if [ -n "$DIRTY" ]; then
	printf 'ОШИБКА: canonical working tree содержит незакоммиченные отслеживаемые изменения.\n' >&2
	printf '        %s\n' "$CANONICAL" >&2
	printf '        Создание worktree от «грязного» дерева даёт агенту неопределённый base commit.\n' >&2
	printf '        Незакоммиченные файлы:\n' >&2
	printf '%s\n' "$DIRTY" | sed 's/^/          /' >&2
	printf '        Действие владельца: закоммитить или отложить (git stash) эти изменения.\n' >&2
	exit 1
fi

# ── 4. Ветка не должна существовать (повторное использование запрещено) ─────
if git -C "$CANONICAL" rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null; then
	die "ветка '$BRANCH' уже существует локально.
       Повторное использование ветки и worktree запрещено: одна задача — одна ветка.
       Если предыдущая задача завершена: scripts/agents/close-worktree.sh '$BRANCH'
       затем удалите ветку вручную:      git -C '$CANONICAL' branch -d '$BRANCH'"
fi
if git -C "$CANONICAL" rev-parse --verify --quiet "refs/remotes/origin/$BRANCH" >/dev/null; then
	die "ветка '$BRANCH' уже существует в origin — задача с таким ID уже публиковалась.
       Возьмите новый task-id или slug."
fi

# ── 5. Каталог worktree не должен существовать ──────────────────────────────
SLUG="${BRANCH//\//-}"
WT="$WORKTREE_ROOT/$SLUG"

case "$WT" in
"$CANONICAL"/*) die "каталог worktree не может находиться внутри репозитория: $WT" ;;
esac

if [ -e "$WT" ]; then
	die "каталог уже существует: $WT
       Повторное использование worktree запрещено. Закройте предыдущий:
         scripts/agents/close-worktree.sh <его-ветка>"
fi

if git -C "$CANONICAL" worktree list --porcelain | grep -Fxq "worktree $WT"; then
	die "worktree по пути $WT уже зарегистрирован в git.
       Выполните: git -C '$CANONICAL' worktree prune  — затем повторите."
fi

# ── 6. Создание ─────────────────────────────────────────────────────────────
mkdir -p "$WORKTREE_ROOT"

if git -C "$CANONICAL" rev-parse --verify --quiet "refs/heads/$BASE" >/dev/null; then
	BASE_REF="$BASE"
else
	BASE_REF="origin/$BASE"
fi

printf 'Создание worktree\n'
note "canonical : $CANONICAL"
note "base      : $BASE_REF"
note "branch    : $BRANCH"
note "worktree  : $WT"
printf '\n'

git -C "$CANONICAL" worktree add "$WT" -b "$BRANCH" "$BASE_REF"

BASE_COMMIT="$(git -C "$WT" rev-parse --short HEAD)"

# Запомнить точку ветвления в административном каталоге worktree (НЕ в рабочем дереве —
# иначе файл попал бы в git status). close-worktree.sh отличает по нему собственные
# коммиты агента от неотправленных коммитов базовой ветки владельца.
WT_ADMIN="$(git -C "$WT" rev-parse --path-format=absolute --git-dir)"
{
	printf 'base_branch=%s\n' "$BASE_REF"
	printf 'base_commit=%s\n' "$(git -C "$WT" rev-parse HEAD)"
	printf 'branch=%s\n' "$BRANCH"
} >"$WT_ADMIN/quant-base"

# ── 7. Git identity агента: ТОЛЬКО worktree-scoped ──────────────────────────
# Без этого шага identity в worktree нет вовсе, и оба исхода плохи:
#   — в контейнере OpenHands глобального git-конфига нет, и коммит падает с
#     "Author identity unknown";
#   — на хосте identity резолвится в глобальный конфиг владельца, и коммит агента
#     подписывается его именем.
# Сам агент это чинить не должен: `git config --local` в linked worktree пишет в
# ОБЩИЙ .git/config канонического дерева, и тогда уже коммит владельца окажется
# подписан агентом. Проверено на практике.
# extensions.worktreeConfig=true включает per-worktree конфиг (git >= 2.31):
# запись уходит в .git/worktrees/<name>/config.worktree, общий конфиг не затрагивая.
case "$BRANCH" in
agent/claude/*) AGENT_ID=claude ;;
agent/codex/*) AGENT_ID=codex ;;
agent/gemini/*) AGENT_ID=gemini ;;
agent/openhands/*) AGENT_ID=openhands ;;
*) AGENT_ID=infra ;;
esac

# QUANT_AGENT_IDENTITY переопределяет только роль — соглашение openhands-<роль>
# на домене openhands.local сохраняется (openhands-control-center, openhands-uiux, …).
# Оба значения уже проверены на шаге 1.
AGENT_ID="${QUANT_AGENT_IDENTITY:-$AGENT_ID}"
AGENT_NAME="openhands-$AGENT_ID"
AGENT_EMAIL="${QUANT_AGENT_EMAIL:-$AGENT_NAME@openhands.local}"

if [ "$(git -C "$CANONICAL" config --local --type=bool --get extensions.worktreeConfig 2>/dev/null)" != "true" ]; then
	if git -C "$CANONICAL" config --local extensions.worktreeConfig true; then
		note "включён extensions.worktreeConfig (per-worktree git config)"
	else
		die "не удалось включить extensions.worktreeConfig в $CANONICAL.
       Без него запись identity ушла бы в ОБЩИЙ .git/config канонического дерева —
       этого делать нельзя, поэтому identity не задана.
       Worktree уже создан: $WT
       Действие владельца: включить флаг вручную и задать identity, либо закрыть worktree:
         scripts/agents/close-worktree.sh '$BRANCH'"
	fi
fi

git -C "$WT" config --worktree user.name "$AGENT_NAME"
git -C "$WT" config --worktree user.email "$AGENT_EMAIL"

# Контроль: identity обязана лежать в административном каталоге worktree. Если файла
# нет — запись ушла в общий конфиг, и это нужно увидеть сразу, а не после коммита.
if [ ! -f "$WT_ADMIN/config.worktree" ]; then
	die "identity записана не в config.worktree этого worktree ($WT_ADMIN).
       Проверьте общий конфиг канонического дерева и уберите оттуда user.*, если они появились:
         git -C '$CANONICAL' config --local --get-regexp '^user\.'"
fi
note "identity  : $AGENT_NAME <$AGENT_EMAIL> (worktree-scoped)"

# ── 8. Необязательный симлинк на .env ───────────────────────────────────────
# Симлинк, а не копия: секрет остаётся в единственном месте. .env покрыт .gitignore,
# поэтому симлинк не попадёт в коммит.
ENV_STATE="не связан (часть pytest будет пропущена: ~132 passed / 101 skipped)"
if [ "$LINK_ENV" -eq 1 ]; then
	if [ -f "$CANONICAL/.env" ]; then
		ln -s "$CANONICAL/.env" "$WT/.env"
		ENV_STATE="симлинк на $CANONICAL/.env (значения не копировались)"
		printf '\n  --link-env: создан симлинк на .env канонического дерева.\n'
		printf '  Секрет достижим из этого worktree — не выводите его содержимое.\n'
	else
		printf '\n  --link-env: .env в каноническом дереве не найден — симлинк не создан.\n' >&2
		ENV_STATE="запрошен --link-env, но .env отсутствует"
	fi
fi

# ── 9. Итог ─────────────────────────────────────────────────────────────────
cat <<EOF

Готово. Для handoff (docs/agents/HANDOFF.md):

  Branch      : $BRANCH
  Worktree    : $WT
  Base branch : $BASE_REF
  Base commit : $BASE_COMMIT
  .env        : $ENV_STATE

Дальше:
  cd "$WT"
  git rev-parse --show-toplevel     # подтвердить, что вы в своём worktree
  git status --porcelain            # должно быть пусто

Если задача затрагивает website — в новом worktree нет node_modules:
  cd "$WT/website" && npm ci        # ~600 МБ на worktree, см. WORKTREE_POLICY.md

Работайте ТОЛЬКО в этом каталоге. Canonical working tree не трогайте.
EOF
