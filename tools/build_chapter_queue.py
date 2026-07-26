"""Черновик очереди глав из PDF: оглавление → fallback на заголовки в тексте.

    python tools\\build_chapter_queue.py --pdf "knowledge/raw/books/....pdf"
    python tools\\build_chapter_queue.py --detect-offset 20

Пишет knowledge/queue/chapters.draft.yaml. Рабочую очередь
knowledge/queue/chapters.yaml НЕ трогает: границы глав человек глазами
проверяет один раз, а ошибка здесь тихая — неверный диапазон отдаст
chapter-reader'у чужой текст, и тот честно отчитается «глава разобрана».

Два источника границ, в порядке дешевизны:

1. Закладки PDF (`pypdf` outline) — точные пары «заголовок → страница».
   В сканах издательской вёрстки их часто нет.
2. Заголовки в тексте страниц (`^Глава N` / `ГЛАВА N` в первых строках).
   Работает потому, что заголовки глав в книге однотипны. Совпадения
   помечаются `confidence`, чтобы было видно, где смотреть руками.

Про page_offset: печатный номер страницы книги ≠ индекс страницы в PDF
(обложка, титул, оглавление). Индекс книги и цитаты chapter-reader'а
работают в ПЕЧАТНЫХ номерах, поэтому смещение нужно замерить один раз:
`--detect-offset <физическая страница>` печатает, что на ней найдено.
"""

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "knowledge" / "queue"
DRAFT = QUEUE_DIR / "chapters.draft.yaml"

DEFAULT_PDF = ("knowledge/raw/books/"
               "Технический_анализ_Полный_курс_pdf.pdf")

# «Глава 15», «ГЛАВА 15.», «Глава пятнадцатая» не ловим намеренно: числовая
# форма — то, что есть в этой книге, а угадывание словесных номеров даёт
# ложные совпадения на оглавлении и колонтитулах.
CHAPTER_RE = re.compile(r"^\s*(?:ГЛАВА|Глава)\s+(\d{1,2})\b")

# Строк с начала страницы, где ищем заголовок. Больше — начнём цеплять
# упоминания «в главе 15 мы показали» из тела текста.
HEAD_LINES = 6


def load_pdf(path: Path):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("Нужен PyMuPDF: pip install pymupdf")
    if not path.exists():
        sys.exit(f"PDF не найден: {path}\n"
                 f"Положи книгу в knowledge/raw/books/ (каталог в git не попадает).")
    return fitz.open(str(path))


def from_outline(pdf_path: Path) -> list[dict]:
    """Главы из закладок PDF. Пустой список — закладок нет или они не про главы."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf не установлен — пропускаю оглавление, иду по тексту")
        return []

    try:
        outline = PdfReader(str(pdf_path)).outline
    except Exception as exc:
        print(f"Оглавление не прочитать ({exc}) — иду по тексту")
        return []

    found: list[dict] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            title = str(getattr(item, "title", "") or "").strip()
            match = CHAPTER_RE.match(title)
            if not match:
                continue
            try:
                page = PdfReader(str(pdf_path)).get_destination_page_number(item)
            except Exception:
                continue
            found.append({
                "n": int(match.group(1)),
                "title": CHAPTER_RE.sub("", title).strip(" .—-:") or title,
                "physical_start": page + 1,     # 1-based, как в просмотрщике
                "confidence": "high",
            })

    try:
        walk(outline)
    except Exception as exc:
        print(f"Обход оглавления сорвался ({exc}) — иду по тексту")
        return []
    return found


def from_text(doc) -> list[dict]:
    """Главы по заголовкам в первых строках страниц."""
    hits: dict[int, list[dict]] = {}
    for idx in range(doc.page_count):
        lines = doc[idx].get_text().splitlines()
        for line in lines[:HEAD_LINES]:
            match = CHAPTER_RE.match(line)
            if not match:
                continue
            n = int(match.group(1))
            # Заголовок обычно продолжается следующей непустой строкой.
            rest = CHAPTER_RE.sub("", line).strip(" .—-:")
            if not rest:
                tail = [s.strip() for s in lines[:HEAD_LINES] if s.strip()]
                pos = next((i for i, s in enumerate(tail) if CHAPTER_RE.match(s)), None)
                rest = tail[pos + 1] if pos is not None and pos + 1 < len(tail) else ""
            hits.setdefault(n, []).append({
                "n": n, "title": rest, "physical_start": idx + 1,
            })
            break

    chapters: list[dict] = []
    for n, found in sorted(hits.items()):
        # Несколько совпадений на главу — норма: оглавление в начале книги плюс
        # сам заголовок. Берём ПОСЛЕДНЕЕ (оглавление идёт раньше текста), но
        # помечаем низкой уверенностью — проверять руками.
        pick = dict(found[-1])
        pick["confidence"] = "high" if len(found) == 1 else "low"
        pick["_hits"] = [f["physical_start"] for f in found]
        chapters.append(pick)
    return chapters


def add_ends(chapters: list[dict], page_count: int) -> list[dict]:
    """Конец главы = страница перед началом следующей."""
    chapters = sorted(chapters, key=lambda c: c["physical_start"])
    for i, ch in enumerate(chapters):
        nxt = chapters[i + 1]["physical_start"] - 1 if i + 1 < len(chapters) else page_count
        ch["physical_end"] = max(nxt, ch["physical_start"])
    return sorted(chapters, key=lambda c: c["n"])


def guess_category(n: int) -> str:
    """Черновая категория конспекта. Человек правит в очереди перед прогоном."""
    if n in (9, 10, 21, 22, 23):
        return "risk"
    if n in (15, 16, 13, 2, 6):
        return "technical"
    if n in (17, 18, 20, 11, 4, 5, 8):
        return "strategies"
    return "market_theory"


HEADER = """\
# ЧЕРНОВИК очереди — сгенерирован tools/build_chapter_queue.py.
# Проверить глазами и скопировать нужные главы в chapters.yaml:
#   - pages — ПЕЧАТНЫЕ номера страниц книги (см. book.page_offset);
#   - confidence: low — совпадений заголовка было несколько, проверить;
#   - _hits — все физические страницы, где нашёлся заголовок главы.
"""


def dump(chapters: list[dict], pdf_rel: str, offset: int, source: str) -> None:
    import yaml

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "book": {"id": "schwager_ta_full", "pdf": pdf_rel, "page_offset": offset},
        "detected_by": source,
        "chapters": [
            {
                "n": ch["n"],
                "title": ch.get("title", ""),
                "pages": [ch["physical_start"] + offset, ch["physical_end"] + offset],
                "physical": [ch["physical_start"], ch["physical_end"]],
                "category": guess_category(ch["n"]),
                "status": "pending",
                "confidence": ch.get("confidence", "low"),
                "_hits": ch.get("_hits", []),
            }
            for ch in chapters
        ],
    }
    DRAFT.write_text(
        HEADER + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", default=DEFAULT_PDF, help="путь к PDF от корня репозитория")
    ap.add_argument("--page-offset", type=int, default=0,
                    help="печатная = физическая + offset (обычно отрицательный)")
    ap.add_argument("--detect-offset", type=int, metavar="PHYS",
                    help="показать текст физической страницы PHYS, чтобы "
                         "увидеть её печатный номер, и выйти")
    args = ap.parse_args()

    pdf_path = (ROOT / args.pdf).resolve()
    doc = load_pdf(pdf_path)
    print(f"PDF: {pdf_path.name}, страниц {doc.page_count}")

    if args.detect_offset:
        page = doc[args.detect_offset - 1]
        text = page.get_text().strip().splitlines()
        print(f"\n--- физическая страница {args.detect_offset}, первые/последние строки ---")
        for line in text[:6]:
            print("  ", line)
        print("   …")
        for line in text[-4:]:
            print("  ", line)
        print("\nНайди здесь печатный номер страницы (обычно в колонтитуле) и "
              f"посчитай: page_offset = печатный - {args.detect_offset}")
        return 0

    chapters = from_outline(pdf_path)
    source = "outline"
    if not chapters:
        print("Закладок с главами нет — ищу заголовки по тексту")
        chapters = from_text(doc)
        source = "text-regex"
    if not chapters:
        sys.exit("Ни закладок, ни заголовков «Глава N» не найдено — "
                 "границы придётся задать руками в chapters.yaml")

    chapters = add_ends(chapters, doc.page_count)
    dump(chapters, args.pdf, args.page_offset, source)

    low = [c["n"] for c in chapters if c.get("confidence") != "high"]
    print(f"\nНайдено глав: {len(chapters)} (источник: {source})")
    print(f"Черновик: {DRAFT.relative_to(ROOT)}")
    for ch in chapters:
        mark = " ⚠" if ch.get("confidence") != "high" else "  "
        print(f"{mark} гл. {ch['n']:>2}  физ. {ch['physical_start']:>3}–{ch['physical_end']:<3}"
              f"  {ch.get('title', '')[:50]}")
    if low:
        print(f"\n⚠ Проверить руками: главы {low}")
    if args.page_offset == 0:
        print("\npage_offset = 0: если печатные номера в книге не совпадают с "
              "физическими, замерь через --detect-offset 20 и перегенерируй.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
