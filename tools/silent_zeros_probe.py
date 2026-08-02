"""Предикат по AST: где нехватка/отсутствие данных даёт РАЗРЕШИТЕЛЬНЫЙ ответ.

Образец класса — mask.fillna(False) в structural_downtrend_series: «истории мало»
неотличимо от «даунтренда нет», и оба дают False, то есть «не блокировать».

Предикат находит КЛАСС конструкции механически. Направление («разрешительный» или
«запретительный») зависит от смысла функции и назначается разбором — предикат его
не угадывает и не скрывает, что не угадывает.

Ничего не пишет в проект. Запускается из scratchpad.
"""
import ast
import sys
from pathlib import Path

# ── Что считаем «пустым/умолчательным» значением ──────────────────────────────

def permissive_const(node):
    """Текст значения, если узел — константа-умолчание. Иначе None."""
    if isinstance(node, ast.Constant):
        v = node.value
        if v is False:
            return "False"
        if v is None:
            return "None"
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
            return repr(v)
        if v == "":
            return "''"
        return None
    if isinstance(node, ast.Dict) and not node.keys:
        return "{}"
    if isinstance(node, (ast.List, ast.Set)) and not node.elts:
        return "[]"
    if isinstance(node, ast.Tuple) and not node.elts:
        return "()"
    return None


# Признаки «речь про нехватку данных», а не про обычную ветку
SCARCITY = ("len(", ".empty", "isna", "isnull", "is none", "is not none",
            "notna", "== 0", "< ", "<= ", "not ", "size", "shape", "count",
            "exists", "any(", "all(")


class Finder(ast.NodeVisitor):
    def __init__(self, path, src):
        self.path, self.lines = path, src.splitlines()
        self.hits, self.stack = [], []

    def _fn(self):
        return self.stack[-1] if self.stack else "<модуль>"

    def _src(self, node):
        i = node.lineno - 1
        return self.lines[i].strip() if 0 <= i < len(self.lines) else ""

    def add(self, node, kind, detail):
        self.hits.append({"file": self.path, "line": node.lineno, "fn": self._fn(),
                          "kind": kind, "detail": detail, "src": self._src(node)})

    def visit_FunctionDef(self, node):
        self.stack.append(node.name); self.generic_visit(node); self.stack.pop()
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        f = node.func
        # 1. .fillna(<умолчание>)
        if isinstance(f, ast.Attribute) and f.attr == "fillna" and node.args:
            c = permissive_const(node.args[0])
            if c is not None:
                self.add(node, "fillna", f".fillna({c})")
        # 2. .get(k, <умолчание>)
        if isinstance(f, ast.Attribute) and f.attr == "get" and len(node.args) >= 2:
            c = permissive_const(node.args[1])
            if c is not None:
                self.add(node, "dict.get", f".get(..., {c})")
        # 3. getattr(o, a, <умолчание>)
        if isinstance(f, ast.Name) and f.id == "getattr" and len(node.args) >= 3:
            c = permissive_const(node.args[2])
            if c is not None:
                self.add(node, "getattr", f"getattr(..., {c})")
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # 4. x or {} / x or 0 / x or False
        if isinstance(node.op, ast.Or):
            c = permissive_const(node.values[-1])
            if c is not None:
                self.add(node, "or-умолчание", f"... or {c}")
        self.generic_visit(node)

    def visit_If(self, node):
        # 5. охранный возврат по признаку нехватки данных
        test = ast.unparse(node.test).lower()
        if any(m in test for m in SCARCITY):
            for st in node.body:
                if isinstance(st, ast.Return) and st.value is not None:
                    c = permissive_const(st.value)
                    if c is not None:
                        self.add(st, "охрана→умолчание",
                                 f"if {ast.unparse(node.test)[:60]} → return {c}")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        # 6. except → умолчание / молчаливый проход
        for st in node.body:
            if isinstance(st, ast.Return) and st.value is not None:
                c = permissive_const(st.value)
                if c is not None:
                    self.add(st, "except→умолчание", f"except → return {c}")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.add(node, "except→pass", "except → pass")
        self.generic_visit(node)


def scan(path: Path, rel: str):
    src = path.read_text(encoding="utf-8", errors="replace")
    fnd = Finder(rel, src)
    fnd.visit(ast.parse(src, filename=str(path)))
    return fnd.hits


# ── Замыкание живого пути: что реально импортирует run_forward_d1.py ──────────

def live_closure(root: Path, entry: Path):
    """Файлы проекта, достижимые импортом из entry. Корни sys.path — как у прогона."""
    bases = [root / "bot", root]
    seen, out, stack = set(), set(), [entry]
    while stack:
        cur = stack.pop()
        if cur in seen or not cur.exists():
            continue
        seen.add(cur); out.add(cur)
        try:
            tree = ast.parse(cur.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        mods = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods.append(n.module)
        for m in mods:
            rel = Path(*m.split("."))
            for b in bases:
                for cand in (b / rel.with_suffix(".py"), b / rel / "__init__.py"):
                    if cand.exists():
                        stack.append(cand)
    return out


def main(root_str):
    root = Path(root_str)
    entry = root / "bot" / "run_forward_d1.py"
    live = live_closure(root, entry)

    AREAS = {
        "движок правил":   ["bot/signals/rules_engine.py"],
        "индикаторы":      ["bot/signals/indicators.py"],
        "сайзинг и риск":  ["bot/risk/"],
        "движок бэктеста": ["bot/backtest/engine.py"],
        "живой прогон":    ["bot/run_forward_d1.py"],
        "загрузка данных": ["bot/data/loader.py"],
        "прочее signals":  ["bot/signals/"],
    }
    files = sorted({p for p in (root / "bot").rglob("*.py")
                    if "__pycache__" not in str(p)})
    all_hits = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        for h in scan(p, rel):
            h["live"] = p in live
            all_hits.append(h)

    def area_of(rel):
        for name, pats in AREAS.items():
            if any(rel.startswith(x) or rel == x for x in pats):
                return name
        return "вне области решения"

    AREAS["вне области решения"] = []

    print(f"Просканировано файлов: {len(files)}")
    print(f"Живой путь (замыкание импортов от run_forward_d1.py): {len(live)} файлов")
    print(f"Всего срабатываний предиката: {len(all_hits)}\n")

    for name in AREAS:
        sel = [h for h in all_hits if area_of(h["file"]) == name]
        if not sel:
            continue
        print(f"===== {name}: {len(sel)} =====")
        for h in sorted(sel, key=lambda x: (x["file"], x["line"])):
            mark = "ЖИВОЙ" if h["live"] else "  —  "
            print(f"  [{mark}] {h['file']}:{h['line']}  {h['fn']}()  «{h['kind']}»  {h['detail']}")
            print(f"           {h['src'][:110]}")
        print()

    print("===== СВОДКА ПО ВИДАМ =====")
    kinds = {}
    for h in all_hits:
        kinds.setdefault(h["kind"], [0, 0])
        kinds[h["kind"]][0] += 1
        kinds[h["kind"]][1] += 1 if h["live"] else 0
    for k, (n, nl) in sorted(kinds.items(), key=lambda kv: -kv[1][0]):
        print(f"  {k:<20} всего {n:>3}, из них на живом пути {nl:>3}")


if __name__ == "__main__":
    main(sys.argv[1])
