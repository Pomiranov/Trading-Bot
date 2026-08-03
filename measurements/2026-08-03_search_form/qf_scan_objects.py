#!/usr/bin/env python3
"""Поиск значения по ВСЕМ объектам базы git. Область — ПРЕДИКАТ, не перечень ref-ов.

ЗАЧЕМ ПРЕДИКАТ. `git rev-list --all` перечисляет объекты, достижимые из ссылок, и
недостижимые в него не попадают по построению — ровно та дыра, которую формы 2 и 3
коммита 0e9e078 заводились закрывать. `git cat-file --batch-all-objects`
перечисляет базу объектов: упакованные и россыпью, достижимые и недостижимые,
висячие и живые только через reflog.

ЧЕГО ФОРМА НЕ ДЕЛАЕТ. Она не печатает ни искомое значение, ни найденную строку.
Значение попадает внутрь ТОЛЬКО через переменную окружения QF_NEEDLE и на диск не
пишется. В аргументах командной строки значения нет намеренно: аргументы видны в
списке процессов.

КОДЫ ВОЗВРАТА — различают три исхода, а не два:
    0  просмотр состоялся, совпадений НЕТ
    1  просмотр состоялся, совпадения ЕСТЬ
    3  ОТКАЗ ФОРМЫ (не задано значение, не репозиторий, ноль объектов, сбой git)
Ноль совпадений при нуле просмотренных объектов есть ОТКАЗ, а не чистый
репозиторий, и различает их сама форма — код 3, а не 0.
"""
import os
import subprocess
import sys

FAIL = 3


def die(msg: str) -> None:
    print(f"ОТКАЗ ФОРМЫ: {msg}", file=sys.stderr)
    sys.exit(FAIL)


def git(repo, *args, binary=False):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    return p.returncode, (p.stdout if binary else p.stdout.decode("utf-8", "replace")), \
        p.stderr.decode("utf-8", "replace")


def main() -> None:
    needle = os.environ.get("QF_NEEDLE", "")
    if not needle:
        die("переменная окружения QF_NEEDLE пуста или не задана")
    nb = needle.encode()

    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    label = sys.argv[2] if len(sys.argv) > 2 else repo

    rc, _, err = git(repo, "rev-parse", "--git-dir")
    if rc != 0:
        die(f"{repo} не репозиторий git ({err.strip()})")

    # ── Область: ПЕРЕЧЕНЬ ВСЕХ ОБЪЕКТОВ БАЗЫ ──────────────────────────────
    rc, out, err = git(repo, "cat-file", "--batch-all-objects",
                       "--batch-check=%(objectname) %(objecttype)")
    if rc != 0:
        die(f"git cat-file --batch-all-objects вернул {rc}: {err.strip()}")

    objs = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            objs.append((parts[0], parts[1]))
    total = len(objs)
    if total == 0:
        die("просмотрено 0 объектов — это отказ формы, а не чистый репозиторий")

    # Для сверки области: сколько объектов достижимо из --all и из --all --reflog
    _, ra, _ = git(repo, "rev-list", "--objects", "--all")
    reach_all = len([l for l in ra.splitlines() if l.strip()])
    _, rr, _ = git(repo, "rev-list", "--objects", "--all", "--reflog")
    reach_reflog = len([l for l in rr.splitlines() if l.strip()])

    # ── Один процесс git cat-file --batch на всю базу ──────────────────────
    searchable = [(s, t) for s, t in objs if t in ("blob", "commit", "tag")]
    req = "".join(f"{s}\n" for s, _ in searchable).encode()
    p = subprocess.run(["git", "-C", repo, "cat-file", "--batch"],
                       input=req, capture_output=True)
    if p.returncode != 0:
        die(f"git cat-file --batch вернул {p.returncode}: "
            f"{p.stderr.decode('utf-8', 'replace').strip()}")

    buf, pos, hits, scanned = p.stdout, 0, [], 0
    while pos < len(buf):
        nl = buf.find(b"\n", pos)
        if nl < 0:
            die("поток --batch оборвался на заголовке объекта")
        header = buf[pos:nl].split()
        pos = nl + 1
        if len(header) == 2 and header[1] == b"missing":
            continue
        if len(header) != 3:
            die(f"нераспознанный заголовок --batch: {header!r}")
        sha, otype, size = header[0].decode(), header[1].decode(), int(header[2])
        body = buf[pos:pos + size]
        pos += size + 1                      # +1 — завершающий \n
        scanned += 1
        if nb in body:
            hits.append((otype, sha, body.count(nb)))

    if scanned != len(searchable):
        die(f"просмотрено {scanned} объектов из {len(searchable)} затребованных — "
            f"поток неполный")

    # ── Отчёт. Ни значения, ни найденных строк ────────────────────────────
    print(f"репозиторий            : {label}")
    print(f"объектов в базе (предикат cat-file --batch-all-objects): {total}")
    print(f"  из них просмотрено (blob/commit/tag)                 : {scanned}")
    print(f"  деревьев пропущено (в них содержимого нет)           : {total - scanned}")
    print(f"объектов достижимо из --all                            : {reach_all}")
    print(f"объектов достижимо из --all --reflog                   : {reach_reflog}")
    print(f"ОБЪЕКТОВ ВНЕ ОБЛАСТИ --all                             : {total - reach_all}")
    print(f"СОВПАДЕНИЙ (объектов)                                  : {len(hits)}")

    for otype, sha, n in hits:
        # где лежит объект: путь ищется по достижимым; недостижимый пути не имеет
        where = "недостижим из --all — пути нет"
        rc2, o2, _ = git(repo, "rev-list", "--objects", "--all")
        for line in o2.splitlines():
            if line.startswith(sha) and " " in line:
                where = "путь: " + line.split(" ", 1)[1]
                break
        rc3, o3, _ = git(repo, "log", "--all", "--format=%H", "--find-object", sha)
        commits = [c for c in o3.splitlines() if c.strip()]
        cinfo = ("коммиты: " + ", ".join(c[:12] for c in commits)) if commits \
            else "коммитов из --all не найдено"
        print(f"  HIT {otype:6} {sha}  вхождений={n}  {where}  {cinfo}")

    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
