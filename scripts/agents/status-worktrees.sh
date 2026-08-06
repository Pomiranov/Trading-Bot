#!/usr/bin/env bash
# status-worktrees.sh — состояние всех worktree агентов и canonical дерева.
#
# Использование:
#   scripts/agents/status-worktrees.sh
#
# Только чтение: ничего не создаёт, не удаляет и не изменяет.
# Секретов не читает и не выводит.

set -euo pipefail

WORKTREE_ROOT="${QUANT_WORKTREE_ROOT:-/Users/danila/OpenHands/worktrees/Quant}"

die() { printf 'ОШИБКА: %s\n' "$1" >&2; exit 1; }

git rev-parse --git-dir >/dev/null 2>&1 || die "скрипт запущен вне git-репозитория"
COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir)"
CANONICAL="$(dirname "$COMMON_DIR")"

# gh может быть не авторизован — это не ошибка, просто колонка PR останется пустой.
GH_OK=0
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then GH_OK=1; fi

printf '═══ Canonical working tree ═══════════════════════════════════════════\n'
printf '  path   : %s\n' "$CANONICAL"
printf '  branch : %s\n' "$(git -C "$CANONICAL" rev-parse --abbrev-ref HEAD)"
printf '  HEAD   : %s\n' "$(git -C "$CANONICAL" rev-parse --short HEAD)"

CANON_TRACKED="$(git -C "$CANONICAL" status --porcelain --untracked-files=no | wc -l | tr -d ' ')"
CANON_UNTRACKED="$(git -C "$CANONICAL" status --porcelain --untracked-files=all | grep -c '^??' || true)"
printf '  tracked изменения   : %s\n' "$CANON_TRACKED"
printf '  untracked файлы     : %s\n' "$CANON_UNTRACKED"

if [ "$CANON_TRACKED" -gt 0 ]; then
	printf '\n  ⚠ ВНИМАНИЕ: в canonical дереве есть незакоммиченные отслеживаемые изменения.\n'
	printf '    create-worktree.sh откажется работать, пока они не закоммичены или не отложены.\n'
	git -C "$CANONICAL" status --porcelain --untracked-files=no | sed 's/^/      /'
fi

printf '\n═══ Worktree агентов ═════════════════════════════════════════════════\n'

# Разбор `git worktree list --porcelain`: блоки, разделённые пустой строкой.
FOUND=0
while IFS= read -r line; do
	case "$line" in
	"worktree "*) WT_PATH="${line#worktree }" ;;
	"HEAD "*) WT_HEAD="${line#HEAD }" ;;
	"branch "*) WT_BRANCH="${line#branch refs/heads/}" ;;
	"detached") WT_BRANCH="(detached)" ;;
	"")
		[ -n "${WT_PATH:-}" ] || continue
		# canonical дерево уже показано выше
		if [ "$WT_PATH" = "$CANONICAL" ]; then WT_PATH=""; continue; fi
		FOUND=$((FOUND + 1))

		DIRTY="$(git -C "$WT_PATH" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"

		UPSTREAM="$(git -C "$WT_PATH" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
		if [ -n "$UPSTREAM" ]; then
			set +e
			COUNTS="$(git -C "$WT_PATH" rev-list --left-right --count "$UPSTREAM...HEAD" 2>/dev/null)"
			set -e
			BEHIND="$(printf '%s' "$COUNTS" | awk '{print $1}')"
			AHEAD="$(printf '%s' "$COUNTS" | awk '{print $2}')"
			SYNC="ahead ${AHEAD:-?} / behind ${BEHIND:-?} vs $UPSTREAM"
		else
			SYNC="upstream не задан — ветка не публиковалась"
		fi

		PR="—"
		if [ "$GH_OK" -eq 1 ] && [ "${WT_BRANCH:-}" != "(detached)" ]; then
			set +e
			PR="$(gh pr list --head "$WT_BRANCH" --state all --json number,state,isDraft \
				--jq '.[0] | if . == null then "нет" else "#\(.number) \(.state)\(if .isDraft then " (draft)" else "" end)" end' 2>/dev/null)"
			set -e
			[ -n "$PR" ] || PR="нет"
		elif [ "$GH_OK" -eq 0 ]; then
			PR="gh не авторизован"
		fi

		printf '\n  ● %s\n' "${WT_BRANCH:-?}"
		printf '      path      : %s\n' "$WT_PATH"
		printf '      HEAD      : %s\n' "$(printf '%s' "${WT_HEAD:-}" | cut -c1-7)"
		printf '      изменения : %s файл(ов) незакоммичено\n' "$DIRTY"
		printf '      sync      : %s\n' "$SYNC"
		printf '      PR        : %s\n' "$PR"

		WT_PATH=""
		WT_BRANCH=""
		WT_HEAD=""
		;;
	esac
done < <(git -C "$CANONICAL" worktree list --porcelain; printf '\n')

if [ "$FOUND" -eq 0 ]; then
	printf '\n  (нет активных worktree агентов)\n'
fi

printf '\n═══ Каталог worktree root ════════════════════════════════════════════\n'
printf '  %s\n' "$WORKTREE_ROOT"
if [ -d "$WORKTREE_ROOT" ]; then
	ORPHANS=0
	for d in "$WORKTREE_ROOT"/*/; do
		[ -d "$d" ] || continue
		p="${d%/}"
		if ! git -C "$CANONICAL" worktree list --porcelain | grep -Fxq "worktree $p"; then
			printf '  ⚠ не зарегистрирован в git (осиротевший каталог): %s\n' "$p"
			ORPHANS=$((ORPHANS + 1))
		fi
	done
	[ "$ORPHANS" -eq 0 ] && printf '  осиротевших каталогов нет\n'
else
	printf '  каталог ещё не создан\n'
fi

printf '\nПравила: docs/agents/WORKTREE_POLICY.md\n'
