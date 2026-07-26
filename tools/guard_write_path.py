"""PreToolUse-хук: пускает запись chapter-reader'а только в три каталога.

Подключается НЕ в общий .claude/settings.json, а через
`--settings tools/chapter_reader_settings.json` в вызове claude из
tools/read_chapters.py — то есть действует только на сессии разбора глав и
не мешает обычной работе в проекте.

Зачем вообще: frontmatter субагента задаёт список инструментов, но не
разрешённые пути записи. Без хука `Write` мог бы перезаписать боевые
knowledge/rules/rules*.yaml или карту книги schwager_index.md. Инструкция в
.claude/agents/chapter-reader.md это запрещает, но инструкция — не гарантия.

Протокол хука: на stdin JSON с tool_name/tool_input/cwd, exit 0 = разрешить,
exit 2 = запретить (stderr уходит модели как объяснение). При любой
внутренней ошибке запрещаем: сломанный сторож не должен превращаться в
открытую дверь.
"""

import json
import os
import sys
from pathlib import Path

# Причину отказа читает модель, а Python на Windows отдал бы stderr в cp1251 —
# русский текст пришёл бы агенту кракозябрами.
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Куда chapter-reader'у писать можно. Пути относительно корня репозитория.
ALLOWED_DIRS = (
    "knowledge/cards",
    "knowledge/rules/candidates",
    "knowledge/processed",
)

# Перебивает ALLOWED_DIRS: карта книги лежит внутри разрешённого
# knowledge/processed/, но статусы глав в ней ставит только человек.
DENIED_FILES = (
    "knowledge/processed/market_theory/schwager_index.md",
)

# Инструменты, которые вообще создают/меняют файлы. Write агенту разрешён,
# остальные отключены флагом --disallowedTools; проверяем всё равно —
# на случай, если флаг забудут передать.
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

PATH_KEYS = ("file_path", "notebook_path", "path")


def repo_root() -> Path:
    """Корень репозитория. Хук лежит в tools/, корень — на уровень выше.

    Не полагаемся на cwd: под claude -p он равен корню, но опечатка в
    вызове раннера не должна тихо расширять разрешённую зону.
    """
    return Path(__file__).resolve().parent.parent


def normalize(path_str: str, cwd: str) -> Path:
    """Абсолютный путь без .. и симлинков.

    Относительный путь трактуем от cwd сессии, как это делает сам Write.
    resolve() обязателен: без него knowledge/cards/../../bot/main.py
    прошло бы проверку префикса.
    """
    path = Path(path_str)
    if not path.is_absolute():
        path = Path(cwd or os.getcwd()) / path
    return Path(os.path.normpath(str(path.resolve(strict=False))))


def relative_to_root(path: Path, root: Path) -> str:
    """Путь относительно корня в posix-виде, или "" если он вне корня."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return ""


def check(tool_name: str, tool_input: dict, cwd: str) -> str | None:
    """None — разрешить, строка — причина запрета."""
    if tool_name not in WRITE_TOOLS:
        return None

    raw = next((tool_input[k] for k in PATH_KEYS if tool_input.get(k)), None)
    if not raw:
        return f"{tool_name}: в аргументах нет пути к файлу — запись не разрешена"

    root = repo_root()
    target = normalize(str(raw), cwd)
    rel = relative_to_root(target, root)

    if not rel:
        return (f"Запись вне репозитория запрещена: {raw}\n"
                f"Разрешено только: {', '.join(ALLOWED_DIRS)}")

    # normcase — Windows: knowledge/Cards и KNOWLEDGE/cards это тот же путь.
    rel_cmp = os.path.normcase(rel)

    for denied in DENIED_FILES:
        if rel_cmp == os.path.normcase(denied):
            return (f"Файл {denied} менять запрещено: статусы глав в карте книги "
                    f"ставит человек после ревью карточки, не chapter-reader.")

    for allowed in ALLOWED_DIRS:
        prefix = os.path.normcase(allowed) + os.path.normcase("/")
        if rel_cmp.startswith(prefix):
            return None

    return (f"Запись в {rel} запрещена. chapter-reader пишет только в:\n"
            + "\n".join(f"  - {d}/" for d in ALLOWED_DIRS)
            + "\nКарточка главы, черновики правил и конспект — больше ничего.")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"guard_write_path: не разобрать вход хука ({exc}) — запись запрещена",
              file=sys.stderr)
        return 2

    try:
        reason = check(
            payload.get("tool_name", ""),
            payload.get("tool_input") or {},
            payload.get("cwd", ""),
        )
    except Exception as exc:      # сломанный сторож = закрытая дверь
        print(f"guard_write_path: внутренняя ошибка ({exc}) — запись запрещена",
              file=sys.stderr)
        return 2

    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
