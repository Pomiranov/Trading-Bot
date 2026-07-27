"""PreToolUse-хук: пускает запись chapter-reader'а только в три каталога.

Подключается НЕ в общий .claude/settings.json, а через
`--settings tools/chapter_reader_settings.json` в вызове claude из
tools/read_chapters.py — то есть действует только на сессии разбора глав и
не мешает обычной работе в проекте.

Зачем вообще: frontmatter субагента задаёт список инструментов, но не
разрешённые пути записи. Без хука `Write` мог бы перезаписать боевые
knowledge/rules/rules*.yaml или карту книги schwager_index.md. Инструкция в
.claude/agents/chapter-reader.md это запрещает, но инструкция — не гарантия.

Протокол ответа (проверено на Claude Code 2.1.207)
─────────────────────────────────────────────────
На stdin приходит JSON с tool_name/tool_input/cwd. Решение уходит ОДНОЙ
строкой JSON в stdout:

    {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": "<причина>"}}

Код выхода всегда 0 — и на allow, и на deny. Документированный exit 2
(«blocking error») здесь НЕ РАБОТАЕТ: в транскриптах прогона 2026-07-27
(сессии 24a44e55, c876d102) видно, что sys.exit(2) доехал до харнесса как
exitCode 1, был помечен hook_non_blocking_error — и запись прошла. Тот же
хук с deny-JSON запись заблокировал. Не возвращать сюда ненулевой код: отказа
он не даёт, а на каждый deny вешает лишний attachment в транскрипте агента.

allow печатается явно, а не подразумевается молчанием: в транскрипте должно
быть видно, что сторож отработал, а не отвалился. Оговорка: явный allow
обходит остальные проверки прав — но подпроцесс и так идёт с
`--permission-mode acceptEdits`, а на обычные сессии этот settings-файл не
подключается, так что разницы нет.

При любой внутренней ошибке (не разобрался вход, упала проверка) — deny:
сломанный сторож не должен превращаться в открытую дверь.

Причина уезжает в stdout как \\uXXXX (ensure_ascii): харнесс читает вывод
хука системной кодировкой, и UTF-8 в нём превращается в мохабры — именно это
происходило со stderr до перехода на JSON.

Самопроверка протокола: python tools/guard_write_path.py --self-test
"""

import json
import os
import sys
from pathlib import Path

# Код выхода на отказ. Ноль — не опечатка, см. «Протокол ответа» выше:
# решение принимает JSON в stdout, а ненулевой код на 2.1.207 только шумит.
DENY_EXIT = 0

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


def emit(decision: str, reason: str) -> None:
    """Единственный канал ответа: одна строка JSON в stdout.

    Один print на весь скрипт — чтобы физически не получилось двух решений,
    если исключение вылетит уже после печати. ensure_ascii (дефолт
    json.dumps) не украшение: чистый ASCII не зависит от кодовой страницы,
    которой харнесс читает поток, и русская причина доезжает целой.
    """
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,      # "allow" | "deny"
        "permissionDecisionReason": reason,
    }}))
    sys.stdout.flush()


def mirror_stderr(text: str) -> None:
    """Дубль причины в лог хуков — информационно, решение принимает stdout.

    Без reconfigure на utf-8: харнесс декодирует stderr системной кодировкой,
    и принудительный UTF-8 давал мохабры. Любое исключение глотаем — сторож
    не имеет права ломать уже напечатанный ответ из-за строчки в логе.
    """
    try:
        print(text, file=sys.stderr)
    except Exception:
        pass


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
        reason = check(
            payload.get("tool_name", ""),
            payload.get("tool_input") or {},
            payload.get("cwd", ""),
        )
    except Exception as exc:      # сломанный сторож = закрытая дверь
        text = f"guard_write_path: внутренняя ошибка ({exc}) — запись запрещена"
        emit("deny", text)
        mirror_stderr(text)
        return DENY_EXIT

    if reason is None:
        emit("allow", "guard_write_path: путь в разрешённой зоне chapter-reader")
        return 0

    emit("deny", reason)
    mirror_stderr(reason)
    return DENY_EXIT


# ── Самопроверка протокола ───────────────────────────────────────────────
#
# Каждый кейс прогоняется ОТДЕЛЬНЫМ подпроцессом и сверяется по разобранному
# stdout, а не по коду выхода: код на 2.1.207 всё равно ничего не решает, а
# подпроцесс проверяет настоящий протокол вместе с печатью и кодировкой.

def _case(tool: str, path: str | None, expect: str, label: str) -> dict:
    tool_input: dict = {} if path is None else {"file_path": path}
    return {
        "label": label,
        "expect": expect,
        "stdin": json.dumps({"tool_name": tool, "tool_input": tool_input,
                             "cwd": str(repo_root())}),
    }


def self_test_cases() -> list[dict]:
    root = repo_root()
    outside = (root.parent / "guard_outside.py").as_posix()
    return [
        _case("Write", (root / "knowledge/cards/ch04.md").as_posix(),
              "allow", "карточка главы"),
        _case("Write", (root / "knowledge/rules/candidates/ch04_trend.yaml").as_posix(),
              "allow", "черновик правила"),
        _case("Write", (root / "knowledge/processed/market_theory/ch04.md").as_posix(),
              "allow", "конспект"),
        _case("Write", "knowledge/cards/ch05.md",
              "allow", "относительный путь от cwd"),
        _case("Write", (root / "knowledge/rules/rules.yaml").as_posix(),
              "deny", "боевые rules.yaml"),
        _case("Write", (root / "knowledge/processed/market_theory/schwager_index.md").as_posix(),
              "deny", "карта книги (DENIED_FILES)"),
        _case("Write", "knowledge/cards/../../bot/main.py",
              "deny", "traversal через .."),
        _case("Write", outside,
              "deny", "абсолютный путь вне репозитория"),
        _case("Write", None,
              "deny", "нет пути в tool_input"),
        _case("Edit", (root / "knowledge/rules/rules.yaml").as_posix(),
              "deny", "Edit по боевым правилам"),
        _case("Read", (root / "bot/main.py").as_posix(),
              "allow", "не write-инструмент"),
        # normcase лечит регистр только на Windows; на posix это другой путь.
        _case("Write", (root / "knowledge/Cards/ch04.md").as_posix(),
              "allow" if os.name == "nt" else "deny", "регистр каталога"),
        # Флаг самопроверки разбирается только из sys.argv. Если бы он мог
        # прийти из пейлоада, подпроцесс напечатал бы отчёт вместо вердикта —
        # и разбор stdout упал бы на «не JSON».
        _case("Write", "--self-test", "deny", "--self-test из stdin — не флаг"),
        {"label": "битый JSON на stdin", "expect": "deny", "stdin": "{ не json"},
    ]


def verify_case(case: dict) -> str | None:
    """None — кейс прошёл, строка — что именно не так."""
    import subprocess      # нужен только самопроверке, не горячему пути хука

    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        input=case["stdin"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60,
    )

    if proc.returncode != 0:
        return f"код выхода {proc.returncode}, ожидался 0"

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if len(lines) != 1:
        return f"в stdout {len(lines)} непустых строк, ожидалась ровно одна"

    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        return f"stdout не разбирается как JSON ({exc})"

    out = payload.get("hookSpecificOutput")
    if not isinstance(out, dict):
        return "нет объекта hookSpecificOutput"
    if out.get("hookEventName") != "PreToolUse":
        return f"hookEventName = {out.get('hookEventName')!r}"

    decision = out.get("permissionDecision")
    if decision != case["expect"]:
        return f"решение {decision!r}, ожидалось {case['expect']!r}"
    if decision == "deny" and not (out.get("permissionDecisionReason") or "").strip():
        return "deny без причины — модели нечего показать"
    return None


def self_test() -> int:
    cases = self_test_cases()
    # Под каким интерпретатором прогонялись кейсы: хук в
    # chapter_reader_settings.json вызывается через «py -3», и полезно видеть,
    # что это тот же Python, а не другой из PATH.
    print(f"интерпретатор: {sys.executable}")
    failures = []
    for num, case in enumerate(cases, 1):
        problem = verify_case(case)
        mark = "ok  " if problem is None else "FAIL"
        print(f"  {mark} {num:>2}. {case['label']}"
              + ("" if problem is None else f" — {problem}"))
        if problem is not None:
            failures.append(num)

    total = len(cases)
    if failures:
        print(f"self-test: {total - len(failures)}/{total} ok, "
              f"упали: {', '.join(map(str, failures))}")
        return 1
    print(f"self-test: {total}/{total} ok")
    return 0


if __name__ == "__main__":
    try:
        if "--self-test" in sys.argv[1:]:
            sys.exit(self_test())
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        # Сюда попадаем, если упал уже сам emit (закрытый stdout, BrokenPipe).
        # Литерал, а не json.dumps: на этом уровне полагаться уже не на что.
        print('{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
              '"permissionDecision":"deny","permissionDecisionReason":'
              '"guard_write_path crashed"}}')
        sys.exit(DENY_EXIT)
