#!/usr/bin/env sh
# git credential helper для агентов OpenHands.
#
# Зачем он есть. Штатный совет OpenHands — положить токен в URL remote
# (`https://${GITHUB_TOKEN}@github.com/...`). Правилами проекта это запрещено
# (`AGENTS.md §6`, `§8`): токен в URL попадает в `.git/config` общего канонического
# дерева, в вывод `git remote -v`, в историю shell и в список процессов.
#
# Этот helper отдаёт credential из переменной окружения GITHUB_TOKEN и никуда её
# не записывает. Значение не появляется ни в argv, ни в конфиге, ни в логе.
#
# Использование — только per-command, без записи в конфиг:
#
#   git -c credential.helper=/Users/danila/Downloads/Trading-Bot-merge-learning-nik/scripts/agents/git-credential-openhands.sh \
#       push origin agent/claude/<task-id>-<slug>
#
# Или через переменные окружения, если нужно на несколько команд подряд:
#
#   export GIT_CONFIG_COUNT=1
#   export GIT_CONFIG_KEY_0=credential.helper
#   export GIT_CONFIG_VALUE_0=<путь к этому файлу>
#
# НИКОГДА не прописывайте helper через `git config` — в linked worktree это пишет
# в общий `.git/config` канонического дерева (`AGENTS.md §6`).

set -eu

# git вызывает helper с одним аргументом: get | store | erase.
# Отвечаем только на get; store и erase намеренно ничего не делают — кэшировать
# credential некуда и не нужно.
case "${1:-}" in
  get) ;;
  store|erase) exit 0 ;;
  *) exit 0 ;;
esac

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "git-credential-openhands: GITHUB_TOKEN не задан в окружении беседы." >&2
  echo "Это дефект среды: беседа должна создаваться с секретом GITHUB_TOKEN." >&2
  echo "Сообщите владельцу — не настраивайте credential самостоятельно." >&2
  exit 1
fi

# git читает пары ключ=значение до пустой строки.
# username для PAT может быть любым непустым; GitHub смотрит только на password.
echo "username=x-access-token"
echo "password=${GITHUB_TOKEN}"
echo ""
