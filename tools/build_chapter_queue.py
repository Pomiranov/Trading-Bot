"""Черновик очереди глав из PDF: закладки → титулы по шрифту → текст.

    python tools\\build_chapter_queue.py --pdf "knowledge/raw/books/....pdf"
    python tools\\build_chapter_queue.py --detect-offset 20
    python tools\\build_chapter_queue.py --audit        # отчёт по рабочей очереди
    python tools\\build_chapter_queue.py --self-test    # якоря границ

Пишет knowledge/queue/chapters.draft.yaml. Рабочую очередь
knowledge/queue/chapters.yaml НЕ трогает: границы глав человек глазами
проверяет один раз, а ошибка здесь тихая — неверный диапазон отдаст
chapter-reader'у чужой текст, и тот честно отчитается «глава разобрана».

Источники границ, в порядке доверия:

1. Закладки PDF (`pypdf` outline) — точные пары «заголовок → страница».
   В сканах издательской вёрстки их часто нет.
2. **Титульные страницы по размеру шрифта.** Номер и название главы набраны
   26–33pt, тело книги и подзаголовки — не больше 13.6pt (замерено на этом
   PDF). Различие надёжнее любого регекса: ловит и «4 / Торговые диапазоны»
   (номер отдельной строкой), и «12 Графики ближайших» (номер в одной строке
   с названием), и титул без номера вообще (гл. 7 «Эффективен ли еще
   графический анализ?»).
3. Титульный паттерн по тексту — тот же смысл, но без информации о шрифтах:
   одинокое число первой строкой + короткие строки названия.
4. Колонтитулы `ГЛАВА N` — последний рубеж, всё помечается `confidence: low`.

Почему не колонтитул как основной источник (так было и так врало): строка
«ГЛАВА 4. ТОРГОВЫЕ ДИАПАЗОНЫ» печатается на нечётных страницах ВНУТРИ главы,
а не на титуле. Первый колонтитул гл. 4 — физ. 81 при реальном начале 77.
Плюс OCR рвёт цифры: на физ. 749 стоит «ГЛАВА 2 1 . ИЗМЕРЕНИЕ…», и старый
регекс читал это как главу 2 — отсюда мусорные диапазоны в районе 750.

**Оглавление как второй голос.** Оглавление лежит в начале книги (физ. 4–16)
и машинно читаемо: «5. Поддержка и сопротивление» → «85». Границы из него не
берём (там печатные номера и нет концов), но сверяем: сошлось с титулом —
`confidence: high`, разошлось — `low` с показом обеих цифр. Заодно это
независимая проверка `page_offset`: если все главы разъехались на одну и ту же
величину, значит offset задан неверно.

Про page_offset: печатный номер страницы книги ≠ индекс страницы в PDF
(обложка, титул, оглавление). Индекс книги и цитаты chapter-reader'а
работают в ПЕЧАТНЫХ номерах, поэтому смещение нужно замерить один раз:
`--detect-offset <физическая страница>` печатает, что на ней найдено.
Для «Технический анализ. Полный курс» offset = 0 (подтверждён оглавлением).
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
QUEUE = QUEUE_DIR / "chapters.yaml"

DEFAULT_PDF = ("knowledge/raw/books/"
               "Технический_анализ_Полный_курс_pdf.pdf")

# Колонтитул главы или части. Цифры допускаем с пробелами внутри: OCR
# печатает «ГЛАВА 2 1 .» вместо «ГЛАВА 21.», и без этого номер читается как 2.
RUN_HEADER = re.compile(r"^\s*(?:ГЛАВА|Глава|ЧАСТЬ|Часть)\s+(\d(?:\s*\d)?)\b")
CHAPTER_HEADER = re.compile(r"^\s*(?:ГЛАВА|Глава)\s+(\d(?:\s*\d)?)\b")

NUM_ONLY = re.compile(r"^(\d{1,2})\s*$")          # «4» — номер главы отдельно
NUM_LEAD = re.compile(r"^(\d{1,2})\s+(\S.*)$")    # «12 Графики ближайших»
TOC_ENTRY = re.compile(r"^(\d{1,2})\.\s+(\S.*?)(?:\s+(\d{1,3}))?\s*$")
PAGE_ONLY = re.compile(r"^(\d{1,3})\s*$")

# Кегль, выше которого текст на странице — заголовок, а не проза. Тело этой
# книги ≤13.6pt, титулы ≥26pt; 20 — с запасом в обе стороны.
TITLE_FONT_PT = 20.0

# Строк с начала страницы, где ищем титульный паттерн (ярус 3).
HEAD_LINES = 3

# Длиннее — это уже эпиграф, а не строка названия.
TITLE_LINE_MAX = 45

# Больше глав в книге не бывает; отсекает печатные номера страниц, попавшие
# в разбор оглавления («85» — это страница, а не глава 85).
MAX_CHAPTER = 40

# Меньше этого на странице — картинка или обрыв извлечения, не текст.
TEXT_PAGE_MIN_CHARS = 50

# Страниц с начала книги, где ищем оглавление.
TOC_SCAN_PAGES = 18

# Столько знаков на главу chapter-reader ещё переваривает за один вызов;
# больше — предупредить, что глава просится на разрез.
CHARS_WARN = 45_000


def load_pdf(path: Path):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("Нужен PyMuPDF: pip install pymupdf")
    if not path.exists():
        sys.exit(f"PDF не найден: {path}\n"
                 f"Положи книгу в knowledge/raw/books/ (каталог в git не попадает).")
    return fitz.open(str(path))


# ── Разбор страниц ───────────────────────────────────────────────────────

def page_lines(page) -> list[str]:
    """Непустые строки страницы без отступов."""
    return [line.strip() for line in page.get_text().splitlines() if line.strip()]


def all_lines(doc) -> list[list[str]]:
    """Строки всех страниц. Отдельной функцией, чтобы ярусы по тексту можно
    было прогнать на синтетике в --self-test, без PDF."""
    return [page_lines(doc[idx]) for idx in range(doc.page_count)]


def big_spans(page, min_pt: float = TITLE_FONT_PT) -> list[str]:
    """Куски текста крупнее min_pt, в порядке вёрстки."""
    found = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"].strip()
                if text and span["size"] >= min_pt:
                    found.append(text)
    return found


def split_number(parts: list[str]) -> tuple[int | None, str]:
    """(номер главы или None, название) из строк титульной страницы.

    None вместо номера — не ошибка: у титула гл. 7 номера нет, а титулы частей
    его и не должны иметь. Такая страница становится маркером границы.
    """
    number: int | None = None
    title: list[str] = []
    for part in parts:
        if number is None:
            solo = NUM_ONLY.match(part)
            if solo:
                number = int(solo.group(1))
                continue
            lead = NUM_LEAD.match(part)
            if lead:
                number = int(lead.group(1))
                title.append(lead.group(2))
                continue
        title.append(part)
    if number is not None and number > MAX_CHAPTER:
        return None, " ".join(title).strip()
    return number, " ".join(title).strip()


def looks_like_title(line: str) -> bool:
    """Строка названия, а не начало эпиграфа."""
    return len(line) <= TITLE_LINE_MAX and not line.endswith((".", ",", ":", ";"))


# ── Ярус 1: закладки ─────────────────────────────────────────────────────

def from_outline(pdf_path: Path) -> list[dict]:
    """Главы из закладок PDF. Пустой список — закладок нет или они не про главы."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf не установлен — пропускаю закладки, иду по титулам")
        return []

    try:
        reader = PdfReader(str(pdf_path))
        outline = reader.outline
    except Exception as exc:
        print(f"Закладки не прочитать ({exc}) — иду по титулам")
        return []

    found: list[dict] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            title = str(getattr(item, "title", "") or "").strip()
            match = CHAPTER_HEADER.match(title)
            if not match:
                continue
            try:
                page = reader.get_destination_page_number(item)
            except Exception:
                continue
            found.append({
                "n": int(match.group(1).replace(" ", "")),
                "title": CHAPTER_HEADER.sub("", title).strip(" .—-:") or title,
                "physical_start": page + 1,     # 1-based, как в просмотрщике
                "detected_by": "outline",
            })

    try:
        walk(outline)
    except Exception as exc:
        print(f"Обход закладок сорвался ({exc}) — иду по титулам")
        return []
    return found


# ── Ярус 2: титулы по шрифту ─────────────────────────────────────────────

def from_title_pages(doc) -> tuple[list[dict], list[dict]]:
    """(главы, маркеры границ) по крупному шрифту.

    Маркер — титульная страница без номера главы: титул части, полутитул,
    титул главы, номер которой в вёрстке не набран (гл. 7). В главы он не
    превращается, но конец предыдущей главы задаёт: без этого гл. 6 забрала бы
    шесть страниц гл. 7.
    """
    chapters: list[dict] = []
    markers: list[dict] = []
    for idx in range(doc.page_count):
        parts = big_spans(doc[idx])
        if not parts:
            continue
        number, title = split_number(parts)
        # «Часть 3 / ОСЦИЛЛЯТОРЫ И ЦИКЛЫ» — граница, но не глава, даже если
        # номер части распознался: нумерации глав он не принадлежит.
        if number is None or any(RUN_HEADER.match(p) for p in parts):
            markers.append({"physical_start": idx + 1, "title": title})
            continue
        chapters.append({"n": number, "title": title,
                         "physical_start": idx + 1, "detected_by": "font"})
    return chapters, markers


# ── Ярус 3: титулы по тексту ─────────────────────────────────────────────

def from_title_text(pages: list[list[str]]) -> list[dict]:
    """Титулы без информации о шрифтах: номер первой строкой + название.

    Номер обязан стоять именно первой непустой строкой. Допуск «в первых трёх»
    выглядит безобиднее, но ловит оглавление: там номер печатной страницы
    стоит отдельной строкой под названием главы, и «85» читается как глава 85.
    """
    chapters: list[dict] = []
    for idx, lines in enumerate(pages):
        if len(lines) < 2:
            continue                     # страница-картинка: только номер
        if any(RUN_HEADER.match(line) for line in lines[:HEAD_LINES]):
            continue                     # колонтитул — значит, тело главы
        if not (NUM_ONLY.match(lines[0]) or NUM_LEAD.match(lines[0])):
            continue
        parts = [lines[0]]
        for line in lines[1:HEAD_LINES]:
            if not looks_like_title(line):
                break
            parts.append(line)
        number, title = split_number(parts)
        if number is None or not title:
            continue
        if number == idx + 1:
            continue                     # это номер страницы в колонтитуле
        chapters.append({"n": number, "title": title,
                         "physical_start": idx + 1, "detected_by": "text"})
    return chapters


# ── Ярус 4: колонтитулы ──────────────────────────────────────────────────

def from_running_headers(pages: list[list[str]]) -> list[dict]:
    """Последний рубеж: первый колонтитул «ГЛАВА N» как оценка начала главы.

    Оценка заведомо смещена вперёд (колонтитула на титуле нет), поэтому всё
    найденное этим ярусом уезжает с confidence: low.
    """
    chapters: list[dict] = []
    for idx, lines in enumerate(pages):
        for line in lines[:HEAD_LINES + 3]:
            match = CHAPTER_HEADER.match(line)
            if not match:
                continue
            number = int(match.group(1).replace(" ", ""))
            if number > MAX_CHAPTER:
                break
            rest = CHAPTER_HEADER.sub("", line).strip(" .—-:")
            chapters.append({"n": number, "title": rest,
                             "physical_start": idx + 1,
                             "detected_by": "running-header"})
            break
    return chapters


# ── Оглавление как второй голос ──────────────────────────────────────────

def from_toc(pages: list[list[str]]) -> dict[int, int]:
    """{номер главы: ПЕЧАТНАЯ страница} из оглавления в начале книги."""
    toc: dict[int, int] = {}
    for lines in pages[:TOC_SCAN_PAGES]:
        for i, line in enumerate(lines):
            match = TOC_ENTRY.match(line)
            if not match:
                continue
            number = int(match.group(1))
            if number > MAX_CHAPTER or number in toc:
                continue
            page = match.group(3)
            if not page:
                # Название могло перенестись, номер страницы — ниже.
                for nxt in lines[i + 1:i + 4]:
                    hit = PAGE_ONLY.match(nxt)
                    if hit:
                        page = hit.group(1)
                        break
            if page:
                toc[number] = int(page)
    return toc


def toc_titles(pages: list[list[str]]) -> dict[int, str]:
    """{номер главы: название из оглавления} — полнее, чем на титуле.

    У гл. 22 в вёрстке первое слово названия потерялось при извлечении
    («подход к торговле»), в оглавлении оно есть («Плановый подход к торговле»).
    """
    titles: dict[int, str] = {}
    for lines in pages[:TOC_SCAN_PAGES]:
        for line in lines:
            match = TOC_ENTRY.match(line)
            if match and int(match.group(1)) <= MAX_CHAPTER:
                titles.setdefault(int(match.group(1)), match.group(2).strip())
    return titles


def apply_toc(chapters: list[dict], toc: dict[int, int], offset: int) -> list[str]:
    """Проставляет confidence по согласию с оглавлением. Возвращает замечания."""
    notes: list[str] = []
    deltas: list[int] = []
    for ch in chapters:
        printed = ch["physical_start"] + offset
        if ch["n"] not in toc:
            ch.setdefault("confidence", "medium")
            continue
        ch["_toc_page"] = toc[ch["n"]]
        delta = toc[ch["n"]] - printed
        deltas.append(delta)
        if delta == 0:
            ch["confidence"] = "high"
        else:
            ch["confidence"] = "low"
            notes.append(f"гл. {ch['n']}: титул даёт печатную {printed}, "
                         f"оглавление — {toc[ch['n']]}")
    if deltas and len(set(deltas)) == 1 and deltas[0] != 0:
        notes.append(f"Все главы разъехались с оглавлением на {deltas[0]} — "
                     f"это не границы, а page_offset: попробуй "
                     f"--page-offset {offset + deltas[0]}")
    return notes


# ── Сборка ───────────────────────────────────────────────────────────────

def dedupe(chapters: list[dict]) -> list[dict]:
    """Одна глава — одно начало. Дубликаты складываем в _hits."""
    best: dict[int, dict] = {}
    for ch in sorted(chapters, key=lambda c: c["physical_start"]):
        kept = best.setdefault(ch["n"], dict(ch))
        kept.setdefault("_hits", []).append(ch["physical_start"])
    return sorted(best.values(), key=lambda c: c["n"])


def fill_gaps(chapters: list[dict], markers: list[dict]) -> list[dict]:
    """Титул без номера в разрыве нумерации — вероятно, пропущенная глава.

    Гл. 7 набрана без номера, поэтому в нумерации между 6 и 8 дыра, а между их
    титулами стоит бесхозный маркер. Берём последний маркер в разрыве: перед
    титулом главы могут стоять титул части и полутитул, и глава начинается на
    последнем из них.
    """
    if not chapters:
        return markers and [] or []
    by_n = {ch["n"]: ch for ch in chapters}
    used: list[dict] = []
    for number in range(min(by_n) + 1, max(by_n)):
        if number in by_n:
            continue
        prev, nxt = by_n.get(number - 1), by_n.get(number + 1)
        if not prev or not nxt:
            continue
        inside = [m for m in markers
                  if prev["physical_start"] < m["physical_start"] < nxt["physical_start"]]
        if not inside:
            continue
        pick = inside[-1]
        chapters.append({"n": number, "title": pick["title"],
                         "physical_start": pick["physical_start"],
                         "detected_by": "gap", "confidence": "low"})
        used.append(pick)
    return [m for m in markers if m not in used]


def flag_non_monotonic(chapters: list[dict]) -> list[dict]:
    """Глава N, начинающаяся не раньше N+1 — мусорная находка.

    Границей её начало не считаем (иначе предыдущая глава оборвётся на чужой
    странице), но из черновика не выбрасываем: пусть человек видит, что нашлось.
    """
    suspicious: list[dict] = []
    ordered = sorted(chapters, key=lambda c: c["n"])
    for prev, nxt in zip(ordered, ordered[1:]):
        if prev["physical_start"] >= nxt["physical_start"]:
            for ch in (prev, nxt):
                ch["confidence"] = "low"
                ch["_note"] = "нарушен порядок глав — проверить руками"
            suspicious.append(prev)
    return suspicious


def add_ends(chapters: list[dict], boundaries: list[int], page_count: int) -> list[dict]:
    """Конец главы = страница перед ближайшей следующей границей."""
    stops = sorted(set(boundaries))
    for ch in chapters:
        start = ch["physical_start"]
        nxt = next((b for b in stops if b > start), page_count + 1)
        ch["physical_end"] = max(nxt - 1, start)
    return sorted(chapters, key=lambda c: c["n"])


def detect(doc, pdf_path: Path, offset: int) -> tuple[list[dict], str, list[str]]:
    """(главы с границами, источник, замечания)."""
    notes: list[str] = []
    pages = all_lines(doc)

    chapters = from_outline(pdf_path)
    markers: list[dict] = []
    source = "outline"
    if not chapters:
        chapters, markers = from_title_pages(doc)
        source = "title-font"
    if not chapters:
        notes.append("Крупных заголовков не нашлось — иду по тексту")
        chapters = from_title_text(pages)
        source = "title-text"
    if not chapters:
        notes.append("Титульных страниц не нашлось — иду по колонтитулам, "
                     "границы будут смещены вперёд")
        chapters = from_running_headers(pages)
        source = "running-header"
    if not chapters:
        sys.exit("Ни закладок, ни титулов, ни колонтитулов «ГЛАВА N» не найдено — "
                 "границы придётся задать руками в chapters.yaml")

    chapters = dedupe(chapters)
    markers = fill_gaps(chapters, markers)
    chapters = dedupe(chapters)

    titles = toc_titles(pages)
    for ch in chapters:
        better = titles.get(ch["n"], "")
        if better and len(better) > len(ch.get("title", "")):
            ch["title"] = better

    notes += apply_toc(chapters, from_toc(pages), offset)
    untrusted = flag_non_monotonic(chapters)

    boundaries = [ch["physical_start"] for ch in chapters if ch not in untrusted]
    boundaries += [m["physical_start"] for m in markers]
    return add_ends(chapters, boundaries, doc.page_count), source, notes


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
#   - confidence: high — титул и оглавление сошлись; medium — главы нет в
#     оглавлении; low — расхождение, номер выведен из пропуска или порядок глав
#     нарушен: смотреть руками;
#   - _toc_page — что про начало главы говорит оглавление;
#   - _hits — все физические страницы, где нашёлся титул главы.
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
                "confidence": ch.get("confidence", "medium"),
                "detected_by": ch.get("detected_by", source),
                "_toc_page": ch.get("_toc_page"),
                "_hits": ch.get("_hits", []),
                **({"_note": ch["_note"]} if ch.get("_note") else {}),
            }
            for ch in chapters
        ],
    }
    DRAFT.write_text(
        HEADER + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


# ── Отчёт по рабочей очереди ─────────────────────────────────────────────

def page_stats(doc, phys_from: int, phys_to: int) -> tuple[int, int, int]:
    """(страниц с текстом, всего страниц, знаков) в физическом диапазоне."""
    total = 0
    with_text = 0
    chars = 0
    for phys in range(phys_from, phys_to + 1):
        if not (1 <= phys <= doc.page_count):
            continue
        text = doc[phys - 1].get_text()
        total += 1
        chars += len(text)
        if len(text.strip()) > TEXT_PAGE_MIN_CHARS:
            with_text += 1
    return with_text, total, chars


def draft_confidence() -> dict[int, str]:
    """{глава: confidence} из черновика, если он есть."""
    try:
        import yaml
        data = yaml.safe_load(DRAFT.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return {c["n"]: c.get("confidence", "?") for c in data.get("chapters", [])
            if isinstance(c, dict) and "n" in c}


def audit(doc) -> int:
    """Отчёт по рабочей очереди: границы, уверенность, сколько там текста."""
    import yaml

    if not QUEUE.exists():
        sys.exit(f"Очередь не найдена: {QUEUE}")
    data = yaml.safe_load(QUEUE.read_text(encoding="utf-8")) or {}
    offset = int((data.get("book") or {}).get("page_offset", 0))
    conf = draft_confidence()

    print(f"Очередь: {QUEUE.relative_to(ROOT)}  (page_offset = {offset})")
    print(f"{'гл.':>4} {'печатные':>11} {'физические':>11} {'conf':>7} "
          f"{'с текстом':>11} {'знаков':>9}  статус")
    warnings: list[str] = []
    for ch in data.get("chapters", []):
        pages = ch.get("pages") or []
        n = ch.get("n")
        if len(pages) != 2:
            print(f"{n:>4} {'—':>11} {'—':>11} {'—':>7} {'—':>11} {'—':>9}  "
                  f"{ch.get('status', '?')} (границы не заданы)")
            continue
        phys_from, phys_to = pages[0] - offset, pages[1] - offset
        with_text, total, chars = page_stats(doc, phys_from, phys_to)
        print(f"{n:>4} {f'{pages[0]}–{pages[1]}':>11} "
              f"{f'{phys_from}–{phys_to}':>11} {conf.get(n, '?'):>7} "
              f"{f'{with_text} / {total}':>11} {chars:>9}  {ch.get('status', '?')}")
        if total and with_text * 2 < total:
            warnings.append(f"гл. {n}: текста меньше чем на половине страниц "
                            f"({with_text}/{total}) — много картинок или обрыв извлечения")
        if chars > CHARS_WARN:
            warnings.append(f"гл. {n}: {chars} знаков — один вызов агента может "
                            f"не уложиться в таймаут, глава просится на разрез")
    for line in warnings:
        print(f"⚠ {line}")
    print("\nГраницы сверяются глазами ДО запуска: неверный диапазон отдаст "
          "агенту чужой текст, и тот честно разберёт не ту главу.")
    return 0


# ── Самопроверка ─────────────────────────────────────────────────────────

# Границы, проверенные глазами в PDF. Не трогать без книги в руках: это
# единственное, что отличает «детектор работает» от «детектор сошёлся сам с
# собой». Гл. 4 = 77–84 и гл. 5 = 85 сверены вручную по печатным страницам.
ANCHORS = {4: (77, 84), 5: (85, 102), 6: (103, 150), 10: (173, 196),
           20: (695, 732), 23: (777, 788)}

SYNTHETIC = [
    ["Содержание", "Предисловие к русскому изданию", "12", "Предисловие", "16"],
    ["4", "Торговые диапазоны",
     "Есть обычный дурак, который все и всегда делает не так, и есть."],
    ["78"],
    ["80", "ЧАСТЬ 1. АНАЛИЗ ГРАФИКОВ", "Если установился торговый диапазон, то"],
    ["ГЛАВА 4. ТОРГОВЫЕ ДИАПАЗОНЫ", "81", "после пробоя, заданное число дней"],
    ["5", "Поддержка", "и сопротивление", "На узком рынке, где ценам негде."],
]


def check(label: str, got, want) -> str | None:
    return None if got == want else f"{label}: получено {got!r}, ожидалось {want!r}"


def self_test_logic() -> list[str]:
    """Проверки, которым PDF не нужен."""
    problems: list[str] = []

    found = from_title_text(SYNTHETIC)
    problems.append(check("титулы в синтетике",
                          [(c["n"], c["physical_start"]) for c in found],
                          [(4, 2), (5, 6)]))
    problems.append(check("название гл. 5 из двух строк",
                          next((c["title"] for c in found if c["n"] == 5), None),
                          "Поддержка и сопротивление"))
    problems.append(check("эпиграф не попал в название гл. 4",
                          next((c["title"] for c in found if c["n"] == 4), None),
                          "Торговые диапазоны"))

    # OCR рвёт цифры: «ГЛАВА 2 1 .» — это глава 21, а не 2.
    ocr = from_running_headers([["ГЛАВА 2 1 . ИЗМЕРЕНИЕ РЕЗУЛЬТАТИВНОСТИ", "749"]])
    problems.append(check("OCR-разрыв номера в колонтитуле",
                          [c["n"] for c in ocr], [21]))

    toc = from_toc([["5. Поддержка и сопротивление", "85",
                     "Торговые диапазоны", "85"],
                    ["20. Тестирование и оптимизация торговых систем 695"]])
    problems.append(check("оглавление: номер на следующей строке",
                          toc.get(5), 85))
    problems.append(check("оглавление: номер в конце строки", toc.get(20), 695))
    problems.append(check("оглавление: печатная страница не стала главой",
                          85 in toc, False))

    # Маркер границы обрезает главу: гл. 6 не должна забрать титул гл. 7.
    # Последняя глава тянется до конца книги — границы за ней нет.
    chapters = [{"n": 6, "physical_start": 103}, {"n": 8, "physical_start": 157},
                {"n": 9, "physical_start": 165}]
    ends = add_ends(chapters, [103, 151, 157, 165], 805)
    problems.append(check("маркер границы обрезает главу",
                          [c["physical_end"] for c in ends], [150, 164, 805]))

    mixed = [{"n": 2, "physical_start": 749}, {"n": 3, "physical_start": 44}]
    flagged = flag_non_monotonic(mixed)
    problems.append(check("нарушенный порядок глав помечен",
                          [c["confidence"] for c in mixed], ["low", "low"]))
    problems.append(check("нарушенный порядок не стал границей", len(flagged), 1))

    return [p for p in problems if p]


def self_test_pdf(pdf_path: Path) -> list[str]:
    """Якоря по настоящей книге."""
    doc = load_pdf(pdf_path)
    chapters, source, _ = detect(doc, pdf_path, 0)
    by_n = {c["n"]: c for c in chapters}
    problems = [check("источник границ", source, "title-font")]
    for number, (start, end) in ANCHORS.items():
        ch = by_n.get(number)
        if not ch:
            problems.append(f"гл. {number} не найдена вовсе")
            continue
        problems.append(check(f"гл. {number} начало",
                              ch["physical_start"], start))
        problems.append(check(f"гл. {number} конец", ch["physical_end"], end))
        problems.append(check(f"гл. {number} confidence",
                              ch.get("confidence"), "high"))
    toc = from_toc(all_lines(doc))
    deltas = {toc[n] - by_n[n]["physical_start"] for n in toc if n in by_n}
    problems.append(check("offset по оглавлению", deltas, {0}))
    return [p for p in problems if p]


def self_test(pdf_path: Path) -> int:
    problems = self_test_logic()
    print(f"  {'ok  ' if not problems else 'FAIL'} логика детектора "
          f"({len(SYNTHETIC)} синтетических страниц)")

    if not pdf_path.exists():
        print(f"  ПРОПУЩЕНО  якоря границ: нет {pdf_path.name}")
        print("\nБез книги якоря ничего не гарантируют — прогони на машине с PDF.")
        return 1 if problems else 0

    pdf_problems = self_test_pdf(pdf_path)
    print(f"  {'ok  ' if not pdf_problems else 'FAIL'} якоря границ "
          f"({len(ANCHORS)} глав)")
    problems += pdf_problems

    for line in problems:
        print(f"    ✗ {line}")
    print(f"\nself-test: {'ok' if not problems else f'{len(problems)} проблем'}")
    return 1 if problems else 0


# ── Точка входа ──────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", default=DEFAULT_PDF, help="путь к PDF от корня репозитория")
    ap.add_argument("--page-offset", type=int, default=0,
                    help="печатная = физическая + offset (для этой книги 0)")
    ap.add_argument("--detect-offset", type=int, metavar="PHYS",
                    help="показать текст физической страницы PHYS, чтобы "
                         "увидеть её печатный номер, и выйти")
    ap.add_argument("--audit", action="store_true",
                    help="отчёт по knowledge/queue/chapters.yaml: границы, "
                         "уверенность, сколько в диапазоне текста")
    ap.add_argument("--self-test", action="store_true",
                    help="проверить детектор на синтетике и на якорях книги")
    args = ap.parse_args()

    pdf_path = (ROOT / args.pdf).resolve()

    if args.self_test:
        return self_test(pdf_path)

    doc = load_pdf(pdf_path)
    print(f"PDF: {pdf_path.name}, страниц {doc.page_count}")

    if args.audit:
        return audit(doc)

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

    chapters, source, notes = detect(doc, pdf_path, args.page_offset)
    dump(chapters, args.pdf, args.page_offset, source)

    print(f"\nНайдено глав: {len(chapters)} (источник: {source})")
    print(f"Черновик: {DRAFT.relative_to(ROOT)}")
    for ch in chapters:
        conf = ch.get("confidence", "medium")
        mark = {"high": "  ", "medium": " ?", "low": " ⚠"}.get(conf, " ⚠")
        print(f"{mark} гл. {ch['n']:>2}  физ. {ch['physical_start']:>3}–{ch['physical_end']:<3}"
              f"  {conf:<6}  {ch.get('title', '')[:45]}")

    for line in notes:
        print(f"\n⚠ {line}")
    suspect = [c["n"] for c in chapters if c.get("confidence") != "high"]
    if suspect:
        print(f"\n⚠ Проверить руками: главы {suspect}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
