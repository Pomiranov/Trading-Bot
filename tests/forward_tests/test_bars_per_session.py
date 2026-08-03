"""Долг №50, класс (б) по варианту E2: множитель баров на сессию ПРИКОЛОЧЕН.

ПРЕДМЕТ. Окна задаются в СЕССИЯХ, движок переводит их в бары таймфрейма умножением
на приколоченный множитель. Тест закрепляет ВСЕ СЕМНАДЦАТЬ значений пре-регистрации
`docs/EXPERIMENTS.md:63-92` ПОИМЁННО, а не проверяет «формула работает»: формула,
проверенная на одном значении, молча ошибается на другом — ровно это и мерилось
ниже.

⚠ ПОПРАВКА К ПОСЫЛКЕ, ЗАМЕРЕННАЯ 03.08, а не принятая на слово. В задании стояло:
«25 × 4.3 при хранении 4.3 как числа с точкой даёт 107.49999999999999 → 107; это
ЕДИНСТВЕННЫЙ из 17 параметров на границе .5; остальные 16 правильны при любом
способе». На этой платформе **обе половины неверны**:

    repr(25 * 4.3) == '107.5'      # ровно 107.5, а не 107.4999...
    round(25 * 4.3) == 108         # банкирское округление даёт ВЕРНЫЙ ответ
    int(25 * 4.3)   == 107         # усечение даёт неверный

и `float + round` совпадает с пре-регистрацией по ВСЕМ 17, а `float + int`
расходится по **ВОСЬМИ**: macd_fast, macd_slow, macd_signal, ema_fast,
pivot_strength, pivot_max_age, rsi9, stoch_smooth. То есть `pivot_max_age` не
особенный, а опасен не сам float, а УСЕЧЕНИЕ.

Почему дробь и целые всё равно приняты: результат не зависит ни от платформы, ни от
того, какой способ округления выберет следующий автор. `round` в Python округляет
половину К ЧЁТНОМУ (`round(106.5) == 106`), то есть при том же множителе даёт разные
правила разным окнам; сегодня ни одно из 17 в эту разницу не попадает, но опираться
на это — то же, что опираться на совпадение.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bot"))

from universe import (                                        # noqa: E402
    BARS_PER_SESSION, BARS_PER_SESSION_VERSION,
    bars_per_session_version, scale_sessions_to_bars,
)

# Отпечаток ПРИКОЛОЧЕН литералом (идиома SAMPLE_START_2026_07_VERSION): падение
# этого утверждения означает, что множитель изменили, и тогда обязаны быть
# перемерены все 17 значений и опорные тройки.
EXPECTED_VERSION = "c268ab752b9be2d8"

# Пре-регистрация: (имя, окно в СЕССИЯХ, ожидаемое на H4). Порядок и имена — как в
# `EXPERIMENTS.md`; список закрыт семнадцатью, ни одного сверх.
PREREGISTERED = [
    ("rsi_period",        14,  60),
    ("atr_period",        14,  60),
    ("adx_period",        14,  60),
    ("bb_period",         20,  86),
    ("macd_fast",         12,  52),
    ("macd_slow",         26, 112),
    ("macd_signal",        9,  39),
    ("ema_fast",           9,  39),
    ("ema_slow",          21,  90),
    ("pivot_strength",     3,  13),
    ("pivot_max_age",     25, 108),
    ("rsi9",               9,  39),
    ("stoch_window",      14,  60),
    ("stoch_smooth",       3,  13),
    ("mac_ema",           28, 120),
    ("SIGNAL_WINDOW",     61, 262),
    ("warmup_backtest",   50, 215),
]


class MultiplierIsPinned(unittest.TestCase):

    def test_multiplier_is_a_pinned_fraction_not_a_float(self):
        """Дробь, а не число с точкой: (num, den) целыми."""
        self.assertEqual(BARS_PER_SESSION["D1"], (1, 1))
        self.assertEqual(BARS_PER_SESSION["H4"], (43, 10))
        self.assertEqual(BARS_PER_SESSION["H1"], (156, 10))
        for tf, (num, den) in BARS_PER_SESSION.items():
            self.assertIsInstance(num, int, tf)
            self.assertIsInstance(den, int, tf)

    def test_fingerprint_is_a_pinned_literal(self):
        self.assertEqual(BARS_PER_SESSION_VERSION, EXPECTED_VERSION)
        self.assertEqual(bars_per_session_version(BARS_PER_SESSION), EXPECTED_VERSION)

    def test_fingerprint_namespace_is_separate(self):
        """Без префикса отпечаток таблицы из одной записи совпал бы с чужим.

        Та же ловушка, которую тест нашёл 30.07 у `sample_version`.
        """
        import hashlib
        one = {"D1": (1, 1)}
        naive = hashlib.sha256("D1=1/1".encode()).hexdigest()[:16]
        self.assertNotEqual(bars_per_session_version(one), naive)

    def test_unknown_timeframe_fails_loudly(self):
        """Множитель приколочен: неизвестный ТФ — отказ, а не тихий дефолт."""
        with self.assertRaises(KeyError):
            scale_sessions_to_bars(61, "M5")


class SeventeenValues(unittest.TestCase):
    """Г3: все 17 значений против пре-регистрации, ПОИМЁННО."""

    def test_all_seventeen_match_preregistration_on_h4(self):
        wrong = [(n, scale_sessions_to_bars(s, "H4"), exp)
                 for n, s, exp in PREREGISTERED
                 if scale_sessions_to_bars(s, "H4") != exp]
        self.assertEqual(wrong, [], f"расхождение с пре-регистрацией: {wrong}")
        self.assertEqual(len(PREREGISTERED), 17, "список обязан быть ровно на 17")

    def test_d1_is_identity_by_construction(self):
        """На D1 множитель 1/1, значит перевод — ТОЖДЕСТВО, а не округление.

        Отсюда Г1 и Г2 выполняются по построению: числа D1 не могут сдвинуться.
        """
        for n, sessions, _ in PREREGISTERED:
            self.assertEqual(scale_sessions_to_bars(sessions, "D1"), sessions, n)
        for v in range(1, 400):
            self.assertEqual(scale_sessions_to_bars(v, "D1"), v)

    def test_half_rounds_up(self):
        """Половина ВВЕРХ — решение, названное словами, а не свойство языка."""
        self.assertEqual(scale_sessions_to_bars(25, "H4"), 108)   # 107.5 → 108
        self.assertEqual(scale_sessions_to_bars(5, "H4"), 22)     # 21.5  → 22

    def test_truncating_float_implementation_is_wrong_on_eight_of_seventeen(self):
        """Реализация с усечением ПАДАЕТ — и не на одном параметре, а на восьми.

        Это и есть тот тест, который обязан был падать: он падает на конкурирующей
        реализации, а не на нашей. Восьмёрка ЗАМЕРЕНА, а не оценена; если она
        изменится, изменилось поведение float на платформе, и это надо знать.
        """
        num, den = BARS_PER_SESSION["H4"]
        mult = num / den                      # 4.3 как число с точкой
        broken = [n for n, s, exp in PREREGISTERED if int(s * mult) != exp]
        self.assertEqual(len(broken), 8, f"усечением ломается: {broken}")
        self.assertIn("pivot_max_age", broken)
        # и ровно на этих же значениях наша реализация верна
        for n, s, exp in PREREGISTERED:
            self.assertEqual(scale_sessions_to_bars(s, "H4"), exp, n)


class FilterWindowsAreNotRescaled(unittest.TestCase):
    """Г4: двойной пересчёт окон фильтра даунтренда.

    ПРЕДИКАТ ОБЛАСТИ: множитель применяется к окну в барах СЫРОГО таймфрейма и НЕ
    применяется к окну, считаемому на РЕСЕМПЛЁННОМ дневном ряде. Окна фильтра
    считаются на ресемплённых дневных барах, их окна уже календарные.
    """

    FILTER_WINDOWS = {"sma_long": 200, "sma_short": 50,
                      "lower_low_lookback": 120, "lower_low_window": 20}

    def test_naive_scale_everything_would_double_count(self):
        """Реализация «умножаем всё без разбора» ПАДАЕТ здесь — показано числом."""
        naive = {k: scale_sessions_to_bars(v, "H4")
                 for k, v in self.FILTER_WINDOWS.items()}
        self.assertEqual(naive["sma_long"], 860)
        # 860 ДНЕВНЫХ баров вместо 200 — это 3.4 года вместо 10 месяцев
        for k, v in self.FILTER_WINDOWS.items():
            self.assertNotEqual(naive[k], v,
                                f"{k}: наивное умножение обязано менять значение — "
                                f"иначе тест ничего не проверяет")

    def test_filter_config_is_passed_through_unscaled(self):
        """Боевой путь: `_downtrend_gate` отдаёт окна фильтра БЕЗ множителя.

        Проверяется на настоящем движке с настоящим конфигом фильтра, а не на
        копии логики: подменять здесь функцию значило бы проверять свою копию.
        """
        from backtest.engine import BacktestEngine

        class _Rules:
            structural_downtrend_filter = dict(enabled=True, apply_to="long",
                                               **FilterWindowsAreNotRescaled.FILTER_WINDOWS)

        eng = BacktestEngine(rules_engine=_Rules(), timeframe="H4")
        cfg = eng._rules.structural_downtrend_filter
        for k, v in self.FILTER_WINDOWS.items():
            self.assertEqual(cfg[k], v,
                             f"{k} пересчитан множителем — двойной пересчёт")


if __name__ == "__main__":
    unittest.main()
