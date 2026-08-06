#!/usr/bin/env bash
# close-worktree.sh — безопасно закрыть worktree завершённой задачи.
#
# Использование:
#   scripts/agents/close-worktree.sh <branch> [--force]
#
# По умолчанию удаление БЕЗОПАСНОЕ: скрипт отказывается удалять worktree с
# незакоммиченными изменениями — только они теряются безвозвратно.
# --force требуется явно и означает согласие потерять эту работу.
# Про коммиты, отсутствующие в origin, выдаётся предупреждение, но не отказ:
# `git worktree remove` не удаляет ветку, поэтому закоммиченное сохраняется.
#
# Локальную ветку скрипт НЕ удаляет (она может быть в открытом PR) и никогда
# не трогает удалённые ветки. Секретов не читает и не выводит.

set -euo pipefail

WORKTREE_ROOT="${QUANT_WORKTREE_ROOT:-/Users/danila/OpenHands/worktrees/Quant}"

die() { printf 'ОШИБКА: %s\n' "$1" >&2; exit 1; }

usage() {
	cat >&2 <<'EOF'
Использование: scripts/agents/close-worktree.sh <branch> [--force]

  <branch>   ветка задачи, например agent/codex/rm-p0-003-add-ci
  --force    удалить вместе с незакоммиченными изменениями (они будут потеряны)

Посмотреть состояние перед закрытием:
  scripts/agents/status-worktrees.sh
EOF
	exit 2
}

[ $# -ge 1 ] && [ $# -le 2 ] || usage
BRANCH="$1"
FORCE=0
if [ $# -eq 2 ]; then
	[ "$2" = "--force" ] || usage
	FORCE=1
fi

git rev-parse --git-dir >/dev/null 2>&1 || die "скрипт запущен вне git-репозитория"
COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir)"
CANONICAL="$(dirname "$COMMON_DIR")"

# ── Никогда не закрываем canonical дерево ───────────────────────────────────
CANON_BRANCH="$(git -C "$CANONICAL" rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" = "$CANON_BRANCH" ]; then
	die "'$BRANCH' — ветка canonical working tree ($CANONICAL).
       Canonical дерево не закрывается этим скриптом."
fi
for p in main master merge-learning-nik quant-site-approved-reference-redesign quantflow-nik; do
	if [ "$BRANCH" = "$p" ]; then
		die "'$BRANCH' — защищённая ветка, worktree для неё этим скриптом не управляется."
	fi
done

# ── Найти worktree по ветке ─────────────────────────────────────────────────
WT=""
while IFS= read -r line; do
	case "$line" in
	"worktree "*) cur="${line#worktree }" ;;
	"branch refs/heads/$BRANCH") WT="$cur" ;;
	esac
done < <(git -C "$CANONICAL" worktree list --porcelain)

if [ -z "$WT" ]; then
	printf 'ОШИБКА: не найден worktree для ветки '\''%s'\''.\n' "$BRANCH" >&2
	printf '        Зарегистрированные worktree:\n' >&2
	git -C "$CANONICAL" worktree list | sed 's/^/          /' >&2
	exit 1
fi

if [ "$WT" = "$CANONICAL" ]; then
	die "ветка '$BRANCH' занята canonical деревом — закрытие невозможно."
fi

printf 'Закрытие worktree\n'
printf '  branch   : %s\n' "$BRANCH"
printf '  worktree : %s\n' "$WT"
printf '\n'

# ── Проверка 1: незакоммиченные изменения ───────────────────────────────────
# Только они означают реальную потерю данных: `git worktree remove` удаляет рабочее
# дерево, но НЕ ветку — закоммиченное остаётся достижимым по имени ветки.
DIRTY="$(git -C "$WT" status --porcelain || true)"
BLOCK=0
WARN=0
if [ -n "$DIRTY" ]; then
	printf '  ⚠ незакоммиченные изменения (%s файл(ов)):\n' "$(printf '%s\n' "$DIRTY" | wc -l | tr -d ' ')"
	printf '%s\n' "$DIRTY" | sed 's/^/      /'
	BLOCK=1
else
	printf '  ✓ незакоммиченных изменений нет\n'
fi

# ── Проверка 2: неотправленные СОБСТВЕННЫЕ коммиты ──────────────────────────
# Важно: «не входит ни в одну remote-ветку» — негодный критерий. Базовая ветка владельца
# сама может иметь неотправленные коммиты, и тогда закрытие блокировалось бы даже у пустого
# worktree. Поэтому считаем только коммиты ПОСЛЕ точки ветвления, записанной при создании.
UPSTREAM="$(git -C "$WT" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
WT_ADMIN="$(git -C "$WT" rev-parse --path-format=absolute --git-dir)"
BASE_COMMIT=""
if [ -f "$WT_ADMIN/quant-base" ]; then
	BASE_COMMIT="$(sed -n 's/^base_commit=//p' "$WT_ADMIN/quant-base")"
fi

if [ -n "$UPSTREAM" ]; then
	AHEAD="$(git -C "$WT" rev-list --count "$UPSTREAM..HEAD" 2>/dev/null || echo '?')"
	if [ "$AHEAD" != "0" ]; then
		printf '  ⚠ неотправленных коммитов: %s (upstream %s) — сохранятся в ветке\n' "$AHEAD" "$UPSTREAM"
		git -C "$WT" log --oneline "$UPSTREAM..HEAD" | sed 's/^/      /'
		WARN=1
	else
		printf '  ✓ все коммиты отправлены в %s\n' "$UPSTREAM"
	fi
elif [ -n "$BASE_COMMIT" ] && git -C "$WT" rev-parse --verify --quiet "$BASE_COMMIT" >/dev/null; then
	OWN="$(git -C "$WT" rev-list --count "$BASE_COMMIT..HEAD" 2>/dev/null || echo '?')"
	if [ "$OWN" != "0" ]; then
		printf '  ⚠ ветка не публиковалась; собственных коммитов после base: %s — сохранятся в ветке\n' "$OWN"
		git -C "$WT" log --oneline "$BASE_COMMIT..HEAD" | sed 's/^/      /'
		WARN=1
	else
		printf '  ✓ собственных коммитов нет (HEAD совпадает с base commit)\n'
	fi
else
	# Точка ветвления неизвестна: worktree создан не скриптом либо запись утеряна.
	# Осторожный путь — считать коммиты, отсутствующие в origin, и предупредить о неточности.
	UNREACHABLE="$(git -C "$WT" rev-list --count HEAD --not --remotes 2>/dev/null || echo '?')"
	printf '  ⚠ точка ветвления неизвестна (worktree создан не через create-worktree.sh).\n'
	if [ "$UNREACHABLE" != "0" ]; then
		printf '    коммитов, отсутствующих в origin: %s — среди них могут быть чужие\n' "$UNREACHABLE"
		git -C "$WT" log --oneline -10 HEAD --not --remotes | sed 's/^/      /'
		WARN=1
	else
		printf '    все коммиты есть в origin\n'
	fi
fi

printf '\n'

if [ "$BLOCK" -eq 1 ] && [ "$FORCE" -eq 0 ]; then
	cat >&2 <<EOF
ОШИБКА: закрытие остановлено — в worktree есть НЕЗАКОММИЧЕННЫЕ изменения (см. выше).
        Они будут потеряны безвозвратно: git worktree remove удаляет рабочее дерево.
        (Закоммиченное не теряется — оно остаётся в ветке.)

Безопасные варианты:
  1) закоммитить и отправить:
       cd "$WT"
       git add <файлы>            # никогда git add .
       git commit -m "..."
       git push -u origin "$BRANCH"
  2) отложить: cd "$WT" && git stash
  3) если работа действительно не нужна — повторите с явным флагом:
       scripts/agents/close-worktree.sh "$BRANCH" --force

--force удаляет эту работу безвозвратно.
EOF
	exit 1
fi

if [ "$WARN" -eq 1 ]; then
	printf 'ВНИМАНИЕ: у ветки есть коммиты, отсутствующие в origin. Они НЕ пропадут —\n'
	printf '          останутся в ветке %s, но исчезнут из поля зрения до push.\n' "$BRANCH"
	printf '          Не забудьте: git push -u origin %s\n\n' "$BRANCH"
fi

# ── Удаление ────────────────────────────────────────────────────────────────
if [ "$FORCE" -eq 1 ] && [ "$BLOCK" -eq 1 ]; then
	printf '  --force: удаляю worktree вместе с незавершённой работой\n'
	git -C "$CANONICAL" worktree remove --force "$WT"
else
	git -C "$CANONICAL" worktree remove "$WT"
fi

git -C "$CANONICAL" worktree prune

printf '\nworktree удалён: %s\n' "$WT"

# ── Ветка остаётся ──────────────────────────────────────────────────────────
cat <<EOF

Локальная ветка '$BRANCH' СОХРАНЕНА — она может быть в открытом Pull Request.
Удалять её самостоятельно агент не должен. После merge владельцем:

  git -C "$CANONICAL" branch -d "$BRANCH"

Удалённую ветку в origin этот скрипт не трогает никогда.
EOF
