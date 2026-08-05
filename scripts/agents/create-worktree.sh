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

if ! printf '%s' "$BRANCH" | grep -Eq "$BRANCH_PATTERN"; then
	die "недопустимое имя ветки: '$BRANCH'
       Разрешено: agent/{claude|codex|gemini|openhands}/<task-id>-<slug> или infra/<task-id>-<slug>
       Только строчные буквы, цифры, дефис, точка, подчёркивание.
       Примеры: agent/claude/rm-p0-002-execution-mode, infra/openhands-multi-agent-setup"
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

# ── Git identity агента: ТОЛЬКО worktree-scoped ─────────────────────────────
# Без этого агент, у которого нет identity, выполнит `git config --local user.*`,
# а в linked worktree это пишет в ОБЩИЙ .git/config канонического дерева — и
# следующий коммит владельца окажется подписан агентом. Проверено на практике.
# extensions.worktreeConfig=true включает per-worktree конфиг (git >= 2.31).
case "$BRANCH" in
agent/claude/*) AGENT_ID=claude ;;
agent/codex/*) AGENT_ID=codex ;;
agent/gemini/*) AGENT_ID=gemini ;;
agent/openhands/*) AGENT_ID=openhands ;;
*) AGENT_ID=infra ;;
esac
if [ "$(git -C "$CANONICAL" config --local --get extensions.worktreeConfig 2>/dev/null)" != "true" ]; then
	git -C "$CANONICAL" config --local extensions.worktreeConfig true
	printf '  включён extensions.worktreeConfig (per-worktree git config)\n'
fi
git -C "$WT" config --worktree user.name "openhands-$AGENT_ID"
git -C "$WT" config --worktree user.email "openhands-$AGENT_ID@openhands.local"

# ── 7. Необязательный симлинк на .env ───────────────────────────────────────
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

# ── 8. Итог ─────────────────────────────────────────────────────────────────
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
