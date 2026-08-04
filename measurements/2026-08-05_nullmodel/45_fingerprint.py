"""Отпечаток загруженного массива свечей (пункт 1.3).

ЗАЧЕМ. Контроль "после серии" удалён как тождество: load_candles_db зовётся один
раз, и оба прежних контроля читали ТОТ ЖЕ объект памяти. Вместо него вводится
отпечаток загруженного массива: две серии становятся сравнимы по нему БЕЗ
повторного счёта, а свойство "данные те же" проверяется прямо, а не через равенство
двух пересчётов одной и той же памяти.
"""
import asyncio
import hashlib
import sys
from datetime import date

sys.path.insert(0, "bot")

from universe import SAMPLE_START_2026_07, MEASUREMENT_UNIVERSE_2026_07  # noqa: E402
from backtest.candles import load_candles_db                              # noqa: E402

data = asyncio.run(load_candles_db("1d", list(MEASUREMENT_UNIVERSE_2026_07),
                                  SAMPLE_START_2026_07, date(2026, 7, 29)))
rows = 0
tmin = tmax = None
h = hashlib.sha256()
per = []
for t in sorted(data):
    d = data[t]
    rows += len(d)
    a, b = d.index[0], d.index[-1]
    tmin = a if tmin is None or a < tmin else tmin
    tmax = b if tmax is None or b > tmax else tmax
    ph = hashlib.sha256()
    for c in ("open", "high", "low", "close", "volume"):
        blob = d[c].to_numpy().tobytes()
        h.update(t.encode()); h.update(blob)
        ph.update(blob)
    per.append((t, len(d), ph.hexdigest()[:12]))

print("OTPECHATOK ZAGRUZHENNOGO MASSIVA SVECHEY")
print(f"  strok vsego      : {rows}")
print(f"  tikerov          : {len(data)}")
print(f"  min metka        : {tmin}")
print(f"  max metka        : {tmax}")
print(f"  sha256[:16] vsego: {h.hexdigest()[:16]}")
print("  po bumagam (strok / sha256[:12]):")
for t, n, ph in per:
    print(f"    {t:6} {n:>4}  {ph}")
