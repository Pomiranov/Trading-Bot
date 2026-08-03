"""Долг №52: дневной гейт не имеет права показывать внутридневному бару его
собственную сессию.

ПРЕДМЕТ. `BacktestEngine._downtrend_gate` при не-D1 таймфрейме ресемплирует данные
в дневные и раздаёт значения обратно через `series.reindex(index, method="ffill")`.
`resample("1D")` подписывает дневной бар НАЧАЛОМ дня, а его `close` — это закрытие
последнего внутридневного бара ТОГО ЖЕ дня. Значит бар 04:00 получал значение,
посчитанное по цене 20:00 того же дня, — до 16 часов будущего.

ИНВАРИАНТ, который здесь проверяется: для внутридневного бара времени `t` дня `D`
значение гейта равно значению дневной серии на сессии `D−1`, а не `D`.

РЕШЕНИЕ ПО §6 = вариант A, принято человеком 2026-08-03: внутридневной вызывающий
видит последнюю ЗАКРЫТУЮ дневную сессию. Для дневного контура правильный ответ
ДРУГОЙ — сессия `D` включительно, потому что бар решения и есть дневной бар этой
сессии. Поэтому сдвиг обязан быть УСЛОВНЫМ, и `test_d1_gate_is_not_shifted` его
условность и проверяет: без неё починка одного заглядывания завела бы вторую
ошибку в дневном контуре.

ПОЧЕМУ ТЕСТ НАЧИНАЕТСЯ С ПРОВЕРКИ САМОЙ СИНТЕТИКИ. Если дневной признак не
переворачивается ровно между 04.01 и 05.01, то главное утверждение выполняется
тривиально (обе сессии дали бы одно и то же), и тест зеленел бы, ничего не проверяя.
`test_synthetic_flips_exactly_on_the_target_session` закрывает эту дыру.
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bot"))

from backtest.engine import BacktestEngine                  # noqa: E402
from signals.indicators import structural_downtrend_series   # noqa: E402

# Параметры фильтра — те же, что в боевом rules_osc_range.yaml
PARAMS = dict(sma_short=50, sma_long=200, lower_low_lookback=120, lower_low_window=20)

DAYS = 500
LAST_DAY = "2026-01-05"          # сессия из примера, записанного в теле долга №52
PREV_DAY = "2026-01-04"
BAR_0400 = pd.Timestamp("2026-01-05 04:00")
BAR_2000 = pd.Timestamp("2026-01-05 20:00")

D1_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _daily_close(d: int) -> float:
    """Путь цены, подобранный так, чтобы третье условие фильтра перевернулось
    РОВНО на последнем дне.

    Плато 105 держится ВЫШЕ минимума окна 120-дневной давности (≈102), поэтому
    04.01 фильтр молчит; закрытие 99 последнего дня уходит НИЖЕ этого минимума,
    и 05.01 фильтр включается. Первые два условия (`close < SMA200`,
    `SMA50 < SMA200`) выполнены на обеих сессиях — то есть переворот вызван
    ровно одним условием, а не смесью.
    """
    if d < 250:
        return 200.0
    if d < 400:
        return 200.0 - (d - 250) * 100.0 / 150.0
    if d < DAYS - 1:
        return 105.0
    return 99.0


def _intraday() -> pd.DataFrame:
    """H4-ряд: четыре бара в сутки, 04:00 / 08:00 / 12:00 / 20:00.

    Бары ДО вечернего несут закрытие ПРЕДЫДУЩЕГО дня, вечерний — закрытие своего.
    Разделение намеренное: если бар 04:00 получает значение, посчитанное по 99,
    он получил число, которого в 04:00 ещё не существовало.
    """
    days = pd.date_range(end=LAST_DAY, periods=DAYS, freq="D")
    rows, idx = [], []
    for d, day in enumerate(days):
        c_today = _daily_close(d)
        c_prev = _daily_close(d - 1) if d else c_today
        for hh, close in ((4, c_prev), (8, c_prev), (12, c_prev), (20, c_today)):
            idx.append(day + pd.Timedelta(hours=hh))
            rows.append({"open": close, "high": close * 1.001,
                         "low": close * 0.999, "close": close, "volume": 1000})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx, name="datetime"))


class _Rules:
    """Минимальная заглушка правил: движку от неё нужен только конфиг фильтра.

    Штатный `StubRules` (`test_forward_catchup.py`) атрибута
    `structural_downtrend_filter` НЕ имеет, поэтому `_downtrend_gate` на нём
    возвращает `None` и гейта не считает вовсе — на таком стабе долг №52
    непроверяем.
    """
    structural_downtrend_filter = dict(enabled=True, apply_to="long", **PARAMS)


class DowntrendGateCausality(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.h4 = _intraday()
        cls.d1 = cls.h4.resample("1D").agg(D1_AGG).dropna(subset=["close"])
        cls.daily = structural_downtrend_series(cls.d1, **PARAMS)

    # ── 0. Синтетика обязана быть НЕтривиальной ───────────────────────────

    def test_synthetic_flips_exactly_on_the_target_session(self):
        """Без переворота между 04.01 и 05.01 главный тест зеленел бы вхолостую."""
        self.assertFalse(bool(self.daily.loc[pd.Timestamp(PREV_DAY)]),
                         "дневной признак 04.01 обязан быть False")
        self.assertTrue(bool(self.daily.loc[pd.Timestamp(LAST_DAY)]),
                        "дневной признак 05.01 обязан быть True")
        # и закрытия те, что в примере долга
        self.assertEqual(float(self.d1.loc[pd.Timestamp(LAST_DAY), "close"]), 99.0)
        self.assertEqual(float(self.h4.loc[BAR_0400, "close"]), 105.0)
        self.assertEqual(float(self.h4.loc[BAR_2000, "close"]), 99.0)

    # ── 1. Главное утверждение долга №52 ─────────────────────────────────

    def test_intraday_bar_takes_previous_session_not_its_own(self):
        """Бар 05.01 04:00 обязан получить признак сессии 04.01, а не 05.01.

        До починки здесь True: значение посчитано по закрытию 20:00 того же дня,
        то есть на 16 часов вперёд.
        """
        gate = BacktestEngine(rules_engine=_Rules(),
                              timeframe="H4")._downtrend_gate(self.h4, self.h4.index)
        self.assertEqual(
            bool(gate.loc[BAR_0400]), bool(self.daily.loc[pd.Timestamp(PREV_DAY)]),
            "бар 04:00 получил признак СВОЕЙ сессии — заглядывание на 16 часов")
        self.assertFalse(bool(gate.loc[BAR_0400]))

    def test_no_intraday_bar_sees_its_own_session(self):
        """Тот же инвариант ПРЕДИКАТОМ по всем барам, а не на одном примере.

        Один бар мог бы совпасть случайно; проверка по всему ряду этого не
        допускает. Бары первой сессии исключены: у неё нет предшественника.
        """
        gate = BacktestEngine(rules_engine=_Rules(),
                              timeframe="H4")._downtrend_gate(self.h4, self.h4.index)
        labels = list(self.daily.index)
        pos = {ts: i for i, ts in enumerate(labels)}
        checked = mismatched = 0
        for ts in self.h4.index:
            i = pos[ts.normalize()]
            if i == 0:
                continue
            checked += 1
            if bool(gate.loc[ts]) != bool(self.daily.iloc[i - 1]):
                mismatched += 1
        self.assertGreater(checked, 1000, "проверено подозрительно мало баров")
        self.assertEqual(mismatched, 0,
                         f"{mismatched} из {checked} баров видят свою сессию")

    # ── 2. Дневной контур НЕ должен сдвинуться ───────────────────────────

    def test_d1_gate_is_not_shifted(self):
        """При timeframe='D1' гейт равен НЕсдвинутой серии.

        Проверяет условность сдвига. По таблице §6 у дневного контура бар решения
        и есть дневной бар сессии `D`, поэтому `D` включительно — верный ответ, и
        безусловный `.shift(1)` завёл бы здесь вторую ошибку. Тест обязан быть
        зелёным и ДО починки, и ПОСЛЕ: это доказательство no-op, а не приёмка.
        """
        gate = BacktestEngine(rules_engine=_Rules(),
                              timeframe="D1")._downtrend_gate(self.d1, self.d1.index)
        self.assertEqual(len(gate), len(self.daily))
        self.assertEqual(int((gate.values != self.daily.values).sum()), 0,
                         "дневной гейт сдвинулся — правка протекла в D1")

    # ── 3. Край серии не заводит второй неоднозначности ──────────────────

    def test_shifted_in_gap_falls_inside_warmup(self):
        """После сдвига первый дневной бар остаётся без предшественника.

        `fillna(False)` даст «лонги разрешены», и это НЕ новое смешение: позиция
        попадает внутрь уже существующей зоны прогрева. Сравнение с `SMA(200)`
        при `NaN` даёт `False`, поэтому первые `sma_long` значений серии уже
        `False` до всякого сдвига — сдвиг удлиняет прогрев с N до N+1 бара.

        Проверяется числом: если бы `True` встретился раньше 200-го бара,
        неоднозначность была бы новой и её пришлось бы записать как таковую.
        """
        warmup = self.daily.iloc[:PARAMS["sma_long"]]
        self.assertEqual(int(warmup.sum()), 0,
                         "внутри прогрева есть True — сдвиг создал бы НОВОЕ "
                         "смешение прогрева с «нет даунтренда»")
        self.assertTrue(bool(self.daily.iloc[PARAMS["sma_long"]:].any()),
                        "серия целиком False — тест ничего не проверяет")


if __name__ == "__main__":
    unittest.main()
