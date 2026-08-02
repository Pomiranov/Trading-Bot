"""ПОДСАДКА для правила 12 §8. Двенадцать заведомо ПОЛОЖИТЕЛЬНЫХ случаев
и шесть отрицательных контролей. Предикат обязан поймать 12/12 и не поймать
ни одного контроля.

Файл нигде не импортируется и никуда не ставится — он существует, чтобы
показать предикат СРАБАТЫВАЮЩИМ, а не только давшим ноль.
"""
import pandas as pd


# ───────────────── ПОЛОЖИТЕЛЬНЫЕ 1–12 ─────────────────

def p01_fillna_false(df):
    return (df["close"] < df["sma"]).fillna(False)            # +1 fillna

def p02_fillna_zero(df):
    return df["atr"].fillna(0)                                 # +2 fillna

def p03_dict_get_false(cfg):
    return cfg.get("enabled", False)                           # +3 dict.get

def p04_dict_get_empty(cfg):
    return cfg.get("params", {})                               # +4 dict.get

def p05_getattr_false(rules):
    return getattr(rules, "downtrend_filter", False)           # +5 getattr

def p06_getattr_zero(pos):
    return getattr(pos, "size", 0)                             # +6 getattr

def p07_or_empty(cfg):
    return (cfg or {})                                         # +7 or-умолчание

def p08_or_zero(x):
    return (x or 0)                                            # +8 or-умолчание

def p09_guard_len(df, need=200):
    if len(df) < need:
        return False                                           # +9 охрана→умолчание
    return True

def p10_guard_empty(df):
    if df.empty:
        return 0                                               # +10 охрана→умолчание
    return df["close"].iloc[-1]

def p11_except_return(raw):
    try:
        return float(raw)
    except ValueError:
        return 0                                               # +11 except→умолчание

def p12_except_pass(store, key):
    try:
        store.flush(key)
    except OSError:
        pass                                                   # +12 except→pass


# ───────────────── ОТРИЦАТЕЛЬНЫЕ КОНТРОЛИ ─────────────────

def n01_fillna_true(df):
    return (df["close"] < df["sma"]).fillna(True)              # запретительное — не ловим

def n02_get_required(cfg):
    return cfg["threshold"]                                     # нет умолчания вовсе

def n03_guard_raises(df, need=200):
    if len(df) < need:
        raise ValueError("истории не хватает")                  # fail-loud — не ловим
    return True

def n04_except_raises(raw):
    try:
        return float(raw)
    except ValueError:
        raise                                                    # пробрасывает — не ловим

def n05_get_nonempty_default(cfg):
    return cfg.get("mode", "strict")                             # умолчание НЕ пустое

def n06_or_nonempty(x):
    return (x or "strict")                                       # умолчание НЕ пустое
