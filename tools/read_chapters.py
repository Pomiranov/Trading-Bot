"""QuantFlow — батч-разбор глав книги субагентом chapter-reader.

    python tools\\read_chapters.py --dry-run          # что будет сделано
    python tools\\read_chapters.py --only 4           # одна глава
    python tools\\read_chapters.py --limit 3          # три первых pending
    python tools\\read_chapters.py --retry-failed

Берёт pending-главы из knowledge/queue/chapters.yaml, на каждую:
  1. извлекает страницы из PDF в knowledge/raw/books/chapters/chNN.txt
     с маркерами [стр. N] (ПЕЧАТНЫЕ номера — ими же ссылается агент);
  2. запускает chapter-reader (claude -p --agent chapter-reader) с
     хуком-сторожем записи из tools/chapter_reader_settings.json;
  3. проверяет, что получилось, и обновляет статус главы;
  4. в конце — одно сообщение в Telegram со сводкой.

Главы идут строго по одной: параллельный запуск — гонка на записи очереди,
а выигрыш по времени здесь не нужен.

Текст главы извлекает раннер, а не агент: у chapter-reader'а нет Bash (это
и закрывает ему доступ к БД и к запуску кода), поэтому PDF он открыть не
может. Разделение намеренное.

Бэктестов, БД и правки боевых rules*.yaml здесь нет и не будет: выход
конвейера — материал для ревью человеком.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):      # консоль Windows — cp1251
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import logging

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))

QUEUE = ROOT / "knowledge" / "queue" / "chapters.yaml"
EXTRACT_DIR = ROOT / "knowledge" / "raw" / "books" / "chapters"
CARDS_DIR = ROOT / "knowledge" / "cards"
CAND_DIR = ROOT / "knowledge" / "rules" / "candidates"
PROCESSED_DIR = ROOT / "knowledge" / "processed"
INDEX = PROCESSED_DIR / "market_theory" / "schwager_index.md"
AGENT_DEF = ROOT / ".claude" / "agents" / "chapter-reader.md"
AGENT_SETTINGS = "tools/chapter_reader_settings.json"

# Каталоги, изменения вне которых считаются нарушением. Дублирует
# tools/guard_write_path.py осознанно: хук — предупреждение на входе,
# эта проверка — контроль по факту, на случай если хук не подключился.
ALLOWED_PREFIXES = ("knowledge/cards/", "knowledge/rules/candidates/",
                    "knowledge/processed/")

# Меньше этого на страницу — страницы-картинки или обрыв извлечения.
# Агента не звать: платить за вызов ради пустого текста незачем.
MIN_CHARS_PER_PAGE = 500

AGENT_TIMEOUT_SEC = int(os.getenv("CHAPTER_READER_TIMEOUT", "900"))

ALLOWED_TOOLS = ["Read", "Grep", "Glob", "Write"]
DISALLOWED_TOOLS = ["Bash", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Task"]

CATEGORIES = ("technical", "risk", "strategies", "market_theory")

logger = logging.getLogger("quantflow.read_chapters")


def setup_logging() -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "read_chapters.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ── Очередь ──────────────────────────────────────────────────────────────

def load_queue() -> tuple[str, dict]:
    """(шапка-комментарий дословно, данные).

    Шапку сохраняем и переэмитим: PyYAML комментарии не сохраняет, а в
    шапке лежит инструкция, как задавать границы глав. ruamel.yaml ради
    этого в requirements не тянем.
    """
    if not QUEUE.exists():
        sys.exit(f"Очередь не найдена: {QUEUE}")
    raw = QUEUE.read_text(encoding="utf-8")
    header_lines = []
    for line in raw.splitlines(keepends=True):
        if line.startswith("#") or not line.strip():
            header_lines.append(line)
            continue
        break
    data = yaml.safe_load(raw)
    if not isinstance(data, dict) or "chapters" not in data:
        sys.exit(f"{QUEUE}: нет секции chapters")
    return "".join(header_lines), data


def save_queue(header: str, data: dict) -> None:
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    QUEUE.write_text(header + body, encoding="utf-8")


# ── Подготовка текста главы ──────────────────────────────────────────────

def open_pdf(rel_path: str):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("Нужен PyMuPDF: pip install pymupdf")
    path = (ROOT / rel_path).resolve()
    if not path.exists():
        sys.exit(f"PDF не найден: {path}\n"
                 f"Положи книгу в knowledge/raw/books/ (каталог в git не попадает).")
    return fitz.open(str(path))


def extract_chapter(doc, printed_pages: list[int], offset: int, n: int) -> tuple[Path, dict]:
    """Текст главы с маркерами [стр. N]. N — печатный номер страницы книги."""
    start, end = printed_pages
    phys_start, phys_end = start - offset, end - offset
    if phys_start < 1 or phys_end > doc.page_count:
        raise ValueError(
            f"страницы {start}–{end} при offset {offset} дают физические "
            f"{phys_start}–{phys_end}, а в PDF всего {doc.page_count}")

    chunks, total = [], 0
    for phys in range(phys_start, phys_end + 1):
        text = doc[phys - 1].get_text()
        total += len(text.strip())
        chunks.append(f"[стр. {phys + offset}]\n{text.rstrip()}\n")

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    out = EXTRACT_DIR / f"ch{n:02d}.txt"
    out.write_text("\n".join(chunks), encoding="utf-8")

    pages = phys_end - phys_start + 1
    return out, {"pages": pages, "chars": total, "per_page": total // max(pages, 1)}


def rel(path: Path) -> str:
    """Путь относительно корня для сообщений. Вне корня — как есть, без падения."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def index_excerpt(n: int) -> str:
    """Что по разведке ожидалось в главе — блок из schwager_index.md."""
    if not INDEX.exists():
        return "(schwager_index.md не найден)"
    lines = INDEX.read_text(encoding="utf-8").splitlines()
    head = re.compile(rf"^#{{0,4}}\s*\**\s*(?:🎯\s*)?Гл\.\s*{n}\.")
    other = re.compile(r"^#{0,4}\s*\**\s*(?:🎯\s*)?Гл\.\s*\d+\.|^#{1,3} ")
    out: list[str] = []
    for line in lines:
        if out:
            if other.match(line):
                break
            out.append(line)
        elif head.match(line):
            out.append(line)
    text = "\n".join(out).strip()
    return text or f"(в индексе нет блока по главе {n})"


# ── Вызов агента ─────────────────────────────────────────────────────────

def build_prompt(ch: dict, txt_path: Path, stats: dict) -> str:
    n = ch["n"]
    category = ch["category"]
    return f"""\
Разбери главу {n} книги «Швагер, Технический анализ. Полный курс».

Глава: {n}. {ch.get('title', '')}
Печатные страницы: {ch['pages'][0]}–{ch['pages'][1]} ({stats['pages']} стр. текста)
Категория конспекта: {category}
Текст главы: {rel(txt_path)}
  (перед каждой страницей маркер [стр. N] — ПЕЧАТНЫЙ номер страницы книги,
   ссылайся только на эти номера)

Что писать:
  1. knowledge/cards/ch{n:02d}.md — карточка, все 7 разделов, status: read_pending_review
  2. knowledge/rules/candidates/ch{n:02d}_<name>.yaml — по одному файлу на
     правило-кандидат; ноль файлов допустимо, если формализуемых правил нет
  3. knowledge/processed/{category}/<name>_schwager.md — конспект по шаблону
     для категории «{category}» из knowledge/HOW_TO_ADD_KNOWLEDGE.md

Больше никуда не писать. Боевые knowledge/rules/rules*.yaml и карту книги
knowledge/processed/market_theory/schwager_index.md не трогать.

Числа: либо цитата из книги + страница, либо REQUIRES_DECISION. Фичи для
market_features выписывать всегда. Неоднозначности — в раздел «Вопросы к Нику».

Что по разведке ожидалось в этой главе (из schwager_index.md) — сверь и
отметь в разделе «Чего в главе НЕТ» то, чего не нашёл:
---
{index_excerpt(n)}
---
"""


def claude_argv(extra: list[str]) -> list[str]:
    exe = shutil.which("claude")
    if not exe:
        sys.exit("claude CLI не найден в PATH")
    # На Windows npm ставит shim claude.CMD, а CreateProcess батники напрямую
    # не запускает — нужен cmd /c. На macOS/Linux запускается как есть.
    prefix = (["cmd", "/c", exe]
              if os.name == "nt" and exe.lower().endswith((".cmd", ".bat"))
              else [exe])
    return prefix + extra


def run_agent(prompt: str, timeout: int) -> dict:
    """Запуск chapter-reader. Промпт — через stdin: длинный многострочный
    текст в argv на Windows проходит через cmd.exe и калечится кавычками."""
    argv = claude_argv([
        "-p",
        "--agent", "chapter-reader",
        "--allowedTools", *ALLOWED_TOOLS,
        "--disallowedTools", *DISALLOWED_TOOLS,
        "--settings", AGENT_SETTINGS,
        "--permission-mode", "acceptEdits",
        "--output-format", "json",
    ])
    try:
        proc = subprocess.run(
            argv, input=prompt, cwd=str(ROOT), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"таймаут {timeout} с", "result": ""}

    payload = {}
    for line in reversed((proc.stdout or "").strip().splitlines()):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue

    if not payload:
        tail = (proc.stderr or proc.stdout or "").strip()[-300:]
        return {"ok": False, "error": f"CLI не вернул JSON (rc={proc.returncode}): {tail}",
                "result": ""}
    if payload.get("is_error"):
        return {"ok": False, "error": str(payload.get("result", ""))[:300], "result": ""}

    return {
        "ok": True,
        "result": str(payload.get("result", "")),
        "cost": payload.get("total_cost_usd"),
        "turns": payload.get("num_turns"),
        "denials": len(payload.get("permission_denials") or []),
    }


# ── Проверка результата ──────────────────────────────────────────────────

def git_snapshot() -> set[str]:
    try:
        out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=str(ROOT),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
        return {line[3:].strip().strip('"') for line in out.stdout.splitlines() if line[3:].strip()}
    except Exception as exc:
        logger.warning("git status не прочитать (%s) — проверка путей записи пропущена", exc)
        return set()


def parse_card(card: Path) -> dict:
    """Статистика из карточки. Формат задан в .claude/agents/chapter-reader.md;
    если агент его нарушил — считаем то, что удалось, и сообщаем."""
    text = card.read_text(encoding="utf-8")
    stats: dict = {"rules": [], "features": None, "questions": None,
                   "decisions": None, "status": None, "problems": []}

    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if front:
        try:
            meta = yaml.safe_load(front.group(1)) or {}
            stats["status"] = meta.get("status")
        except yaml.YAMLError:
            stats["problems"].append("frontmatter карточки не разбирается")
    else:
        stats["problems"].append("в карточке нет frontmatter")

    for line in text.splitlines():
        if re.match(r"^###\s*R\d+", line):
            ref = re.search(r"`([^`]*candidates/[^`]+\.yaml)`", line)
            stats["rules"].append(ref.group(1) if ref else "")

    sections = {}
    current = None
    for line in text.splitlines():
        head = re.match(r"^##\s+(\d)\.", line)
        if head:
            current = int(head.group(1))
            sections[current] = []
        elif current:
            sections[current].append(line)

    def table_rows(num: int) -> int | None:
        if num not in sections:
            return None
        rows = [s for s in sections[num] if s.strip().startswith("|")]
        return max(len(rows) - 2, 0)      # минус заголовок и разделитель

    stats["features"] = table_rows(3)
    stats["decisions"] = table_rows(7)
    if 5 in sections:
        stats["questions"] = sum(1 for s in sections[5] if re.match(r"^\s*\d+\.", s))

    missing = [num for num in range(1, 8) if num not in sections]
    if missing:
        stats["problems"].append(f"нет разделов карточки: {missing}")
    return stats


def validate(ch: dict, changed: set[str], result_text: str) -> tuple[list[str], dict]:
    """(проблемы, статистика). Пустой список проблем = глава принята."""
    n, category = ch["n"], ch["category"]
    problems: list[str] = []

    if "MISMATCH" in result_text:
        line = next((s for s in result_text.splitlines() if "MISMATCH" in s), "MISMATCH")
        problems.append(f"агент сообщил о несоответствии текста: {line.strip()[:200]}")

    card = CARDS_DIR / f"ch{n:02d}.md"
    if not card.exists():
        problems.append(f"нет карточки {rel(card)}")
        return problems, {}

    stats = parse_card(card)
    problems += stats.pop("problems")

    if stats["status"] != "read_pending_review":
        problems.append(f"status карточки = {stats['status']!r}, "
                        f"ожидался 'read_pending_review'")

    for ref in stats["rules"]:
        if not ref:
            problems.append("R-заголовок в карточке без ссылки на файл кандидата")
        elif not (ROOT / ref).exists():
            problems.append(f"карточка ссылается на несуществующий {ref}")

    if not any(p.startswith(f"knowledge/processed/{category}/") for p in changed):
        problems.append(f"конспект в knowledge/processed/{category}/ не появился")

    outside = sorted(p for p in changed if not p.startswith(ALLOWED_PREFIXES))
    if outside:
        problems.append("записи вне разрешённых каталогов: " + ", ".join(outside[:5]))

    stats["decisions_in_yaml"] = decisions_in_yaml(n)
    return problems, stats


def decisions_in_yaml(n: int) -> dict[str, int]:
    """{файл кандидата: сколько REQUIRES_DECISION} — ответ на «где решать»."""
    found = {}
    for path in sorted(CAND_DIR.glob(f"ch{n:02d}_*.yaml")):
        count = path.read_text(encoding="utf-8").count("REQUIRES_DECISION")
        if count:
            found[path.name] = count
    return found


# ── Сводка ───────────────────────────────────────────────────────────────

def build_summary(results: list[dict], dry_run: bool) -> str:
    done = [r for r in results if r["status"] == "done"]
    failed = [r for r in results if r["status"] == "failed"]
    questions = sum(r["stats"].get("questions") or 0 for r in done)
    decisions = sum(sum(r["stats"].get("decisions_in_yaml", {}).values()) for r in done)

    head = "🧪 <b>Разбор глав (dry-run)</b>" if dry_run else "📚 <b>Разбор глав</b>"
    lines = [f"{head}: {len(done)} done, {len(failed)} failed",
             f"Вопросов к тебе: {questions} · REQUIRES_DECISION: {decisions}"]

    for r in results:
        if r["status"] == "done":
            s = r["stats"]
            lines.append(
                f"гл. {r['n']} ✅ правил {len(s.get('rules') or [])}, "
                f"фич {s.get('features') if s.get('features') is not None else '?'}, "
                f"вопросов {s.get('questions') if s.get('questions') is not None else '?'}"
                + (f", REQUIRES_DECISION {sum(s['decisions_in_yaml'].values())} "
                   f"({', '.join(s['decisions_in_yaml'])})" if s.get("decisions_in_yaml") else "")
            )
        elif r["status"] == "failed":
            lines.append(f"гл. {r['n']} ❌ {r['error'][:160]}")
        else:
            lines.append(f"гл. {r['n']} ⏭ {r['error'][:160]}")

    if done:
        lines.append("Карточки в knowledge/cards/ — ждут ревью, статусы глав "
                     "в schwager_index.md не менялись.")
    return "\n".join(lines)


# ── Точка входа ──────────────────────────────────────────────────────────

def select(chapters: list[dict], args) -> list[dict]:
    if args.only:
        wanted = {int(x) for x in args.only.replace(" ", "").split(",") if x}
        picked = [c for c in chapters if c["n"] in wanted]
        missing = wanted - {c["n"] for c in picked}
        if missing:
            sys.exit(f"В очереди нет глав: {sorted(missing)}")
        return picked
    statuses = {"pending", "failed"} if args.retry_failed else {"pending"}
    picked = [c for c in chapters if c.get("status") in statuses]
    return picked[: args.limit] if args.limit else picked


def preflight(dry_run: bool) -> None:
    if not AGENT_DEF.exists():
        sys.exit(f"Нет определения агента: {rel(AGENT_DEF)}")
    if not (ROOT / AGENT_SETTINGS).exists():
        sys.exit(f"Нет настроек с хуком-сторожем: {AGENT_SETTINGS}")
    if dry_run:
        return
    logger.info("Preflight: проверяю, что claude CLI отвечает…")
    probe = run_agent_probe()
    if not probe:
        sys.exit("claude CLI не отвечает (проверь авторизацию: запусти `claude` "
                 "в терминале один раз, либо задай ANTHROPIC_API_KEY). "
                 "Прогон прерван, чтобы не пометить главы failed из-за среды.")
    logger.info("Preflight: ок")


def run_agent_probe() -> bool:
    """Дешёвый вызов без агента и без инструментов: жив ли CLI и авторизация.
    Иначе 24 главы подряд упадут с ошибкой среды и разметятся как failed."""
    argv = claude_argv(["-p", "--output-format", "json",
                        "--disallowedTools", *ALLOWED_TOOLS, *DISALLOWED_TOOLS])
    try:
        proc = subprocess.run(argv, input="ответь одним словом: ок", cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        logger.error("Preflight: CLI не ответил за 120 с")
        return False
    for line in reversed((proc.stdout or "").strip().splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("is_error"):
            logger.error("Preflight: %s", str(payload.get("result"))[:200])
            return False
        return True
    logger.error("Preflight: CLI не вернул JSON (rc=%s) %s",
                 proc.returncode, (proc.stderr or "")[-200:])
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="номера глав через запятую, игнорируя статус")
    ap.add_argument("--limit", type=int, help="сколько pending-глав взять")
    ap.add_argument("--retry-failed", action="store_true", help="брать и failed")
    ap.add_argument("--dry-run", action="store_true",
                    help="извлечь текст и показать промпт, агента не звать")
    ap.add_argument("--no-notify", action="store_true", help="без Telegram")
    ap.add_argument("--timeout", type=int, default=AGENT_TIMEOUT_SEC,
                    help=f"таймаут на главу, с (по умолчанию {AGENT_TIMEOUT_SEC})")
    args = ap.parse_args()

    setup_logging()
    preflight(args.dry_run)

    header, data = load_queue()
    offset = int(data["book"].get("page_offset", 0))
    queue = select(data["chapters"], args)
    if not queue:
        logger.info("Нечего разбирать: pending-глав в очереди нет")
        return 0

    logger.info("К разбору: %s (offset %d)", [c["n"] for c in queue], offset)
    doc = open_pdf(data["book"]["pdf"])
    results: list[dict] = []

    for ch in queue:
        n = ch["n"]
        logger.info("── глава %d. %s ──", n, ch.get("title", ""))

        if ch.get("category") not in CATEGORIES:
            results.append({"n": n, "status": "failed",
                            "error": f"category={ch.get('category')!r} не из {CATEGORIES}",
                            "stats": {}})
            ch["status"] = "failed"
            ch["last_error"] = results[-1]["error"]
            save_queue(header, data)
            logger.error("гл. %d: %s", n, results[-1]["error"])
            continue

        pages = ch.get("pages") or []
        if len(pages) != 2 or not all(isinstance(p, int) for p in pages):
            error = ("границы страниц не заданы — прогони "
                     "tools/build_chapter_queue.py и перенеси pages в очередь")
            results.append({"n": n, "status": "skipped", "error": error, "stats": {}})
            logger.error("гл. %d: %s", n, error)
            continue

        try:
            txt_path, ex = extract_chapter(doc, pages, offset, n)
        except Exception as exc:
            ch["status"], ch["last_error"] = "failed", str(exc)[:300]
            ch["attempts"] = int(ch.get("attempts", 0)) + 1
            save_queue(header, data)
            results.append({"n": n, "status": "failed", "error": str(exc)[:300], "stats": {}})
            logger.error("гл. %d: извлечение сорвалось: %s", n, exc)
            continue

        logger.info("гл. %d: %d стр., %d симв. (%d на страницу)",
                    n, ex["pages"], ex["chars"], ex["per_page"])

        if ex["per_page"] < MIN_CHARS_PER_PAGE:
            error = (f"текста {ex['per_page']} симв./стр. (порог {MIN_CHARS_PER_PAGE}) — "
                     f"похоже, страницы-картинки, нужен OCR")
            ch["status"], ch["last_error"] = "failed", error
            ch["attempts"] = int(ch.get("attempts", 0)) + 1
            save_queue(header, data)
            results.append({"n": n, "status": "failed", "error": error, "stats": {}})
            logger.error("гл. %d: %s — агента не запускаю", n, error)
            continue

        prompt = build_prompt(ch, txt_path, ex)
        if args.dry_run:
            print(f"\n{'=' * 70}\n{prompt}\n{'=' * 70}")
            results.append({"n": n, "status": "skipped", "error": "dry-run", "stats": {}})
            continue

        before = git_snapshot()
        started = datetime.now()
        run = run_agent(prompt, args.timeout)
        elapsed = (datetime.now() - started).total_seconds()

        if not run["ok"]:
            ch["status"], ch["last_error"] = "failed", run["error"][:300]
            ch["attempts"] = int(ch.get("attempts", 0)) + 1
            save_queue(header, data)
            results.append({"n": n, "status": "failed", "error": run["error"], "stats": {}})
            logger.error("гл. %d: агент не отработал: %s", n, run["error"])
            continue

        logger.info("гл. %d: агент отработал за %.0f с (ходов %s, $%.2f, отказов записи %s)",
                    n, elapsed, run.get("turns"), run.get("cost") or 0, run.get("denials"))
        logger.info("гл. %d: ответ агента:\n%s", n, run["result"][:1500])

        changed = git_snapshot() - before
        problems, stats = validate(ch, changed, run["result"])
        ch["attempts"] = int(ch.get("attempts", 0)) + 1

        if problems:
            ch["status"] = "failed"
            ch["last_error"] = "; ".join(problems)[:500]
            # Файлы не удаляем: по ним и разбираться, что пошло не так.
            logger.error("гл. %d: результат не принят: %s", n, "; ".join(problems))
            results.append({"n": n, "status": "failed",
                            "error": "; ".join(problems), "stats": stats})
        else:
            ch["status"] = "done"
            ch["last_error"] = ""
            ch["card"] = f"knowledge/cards/ch{n:02d}.md"
            logger.info("гл. %d: принята", n)
            results.append({"n": n, "status": "done", "error": "", "stats": stats})

        save_queue(header, data)      # после каждой главы, а не в конце

    summary = build_summary(results, args.dry_run)
    logger.info("Сводка:\n%s", summary)

    if not args.no_notify and not args.dry_run:
        try:
            from notify import credentials_ready, send
            if credentials_ready():
                send(summary)
        except Exception as exc:
            logger.error("Уведомление не отправлено: %s", str(exc)[:200])

    return 0 if all(r["status"] != "failed" for r in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Прервано с клавиатуры")
        sys.exit(130)
