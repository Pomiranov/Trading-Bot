"""Привязка сделки к набору правил (долг №30).

Предмет. `trades.signal_rules` был пуст во всех 7 532 строках, отпечатка набора
правил не существовало вовсе, а `osc_range_moex_d1_fwd` держал confidence 0.6574
при НУЛЕ собственных сделок — скопировано с `osc_range_moex_d1` при засеве.
Значит ни одна строка `belief_system` не была привязана к набору, её породившему.

Здесь проверяется:
  - отпечаток различает две версии ОДНОГО правила с разными параметрами. Кейс
    взят в форме дефекта A3 (`indicators.ema_slow` 21 против 50): именно он
    показывает, почему хешировать выборку секций нельзя;
  - отпечаток НЕ меняется от перестановки ключей и правки комментариев;
  - форвард пишет непустые `signal_rules`, `rules_version` и origin='forward';
  - предикат обучающей выборки исключает и 'unknown', и бэктест;
  - засев НЕ копирует confidence.
"""

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

from config import config
from learning.sample import RULES_VERSION_UNKNOWN, TRAINING_SAMPLE_SQL
from signals.rules_engine import (
    RULES_VERSION_LEN, RULES_VERSION_UNKNOWN as RV_ENGINE, RulesEngine,
)
from tests.forward_tests.test_forward_catchup import (
    FakeDB, StubRules, _bars, _make_runner, _run_sync, _smooth,
)


def _fp(data: dict) -> str:
    """Отпечаток словаря через настоящий RulesEngine (через временный файл)."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "r.yaml"
        p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return RulesEngine(rules_file=p).rules_version


class TestFingerprint(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = yaml.safe_load(
            (config.rules_dir / "rules.yaml").read_text(encoding="utf-8"))

    def test_a3_defect_form_gives_different_fingerprints(self):
        """ГЛАВНЫЙ кейс: различие ТОЛЬКО в indicators.ema_slow.

        Хеш по секциям rules/exit_rules/filters дал бы этим двум наборам
        ОДИНАКОВЫЙ отпечаток — а это ровно дефект trend_moex (EMA21 против EMA50
        под одним именем правила). Фикс A3 в run_ab_trend_fix.py:71 сделан именно
        как data["indicators"]["ema_slow"] = 50.
        """
        baseline = copy.deepcopy(self.base)
        baseline.pop("indicators", None)              # дефолт движка = EMA21
        a3 = copy.deepcopy(self.base)
        a3.setdefault("indicators", {})["ema_slow"] = 50

        self.assertNotEqual(_fp(baseline), _fp(a3),
                            "отпечаток обязан различать EMA21 и EMA50")

    def test_settings_change_moves_the_fingerprint(self):
        """Порог входа тоже меняет поведение — и тоже вне секции rules."""
        loose = copy.deepcopy(self.base)
        loose.setdefault("settings", {})["min_buy_score"] = 1.5
        self.assertNotEqual(_fp(self.base), _fp(loose))

    def test_key_order_does_not_matter(self):
        """Канонизация: значение имеет содержание набора, а не порядок строк."""
        shuffled = dict(reversed(list(self.base.items())))
        self.assertEqual(_fp(self.base), _fp(shuffled))

    def test_comments_do_not_matter(self):
        """Комментарии в rules_osc_range.yaml правятся при каждой записи
        измерений — от байтов файла хеш дёргался бы без изменения поведения."""
        path = config.rules_dir / "rules_osc_range.yaml"
        original = RulesEngine(rules_file=path).rules_version
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "commented.yaml"
            text = path.read_text(encoding="utf-8")
            p.write_text("# добавленный комментарий\n" + text + "\n# и в конце\n",
                         encoding="utf-8")
            self.assertEqual(RulesEngine(rules_file=p).rules_version, original)

    def test_shape_and_stability(self):
        v = RulesEngine(rules_file=config.rules_dir / "rules.yaml").rules_version
        self.assertEqual(len(v), RULES_VERSION_LEN)
        self.assertTrue(all(c in "0123456789abcdef" for c in v))
        self.assertNotEqual(v, RULES_VERSION_UNKNOWN)


class TestTrainingSamplePredicate(unittest.TestCase):

    def test_unknown_label_agrees_between_modules(self):
        """learning/sample.py дублирует метку намеренно — значения обязаны совпасть."""
        self.assertEqual(RULES_VERSION_UNKNOWN, RV_ENGINE)

    def test_predicate_excludes_unknown_and_backtest(self):
        self.assertIn("rules_version IS NOT NULL", TRAINING_SAMPLE_SQL)
        self.assertIn("<> 'unknown'", TRAINING_SAMPLE_SQL)
        self.assertIn("origin IN ('forward', 'live')", TRAINING_SAMPLE_SQL)
        self.assertNotIn("backtest", TRAINING_SAMPLE_SQL)

    def test_predicate_does_not_rely_on_is_sandbox(self):
        """is_sandbox различителем НЕ является: он про бумагу против реальных
        денег, и форвард тоже is_sandbox=true (проверено на 7 532 строках)."""
        self.assertNotIn("is_sandbox", TRAINING_SAMPLE_SQL)

    def test_every_consumer_uses_the_shared_predicate(self):
        """Предикат не должен расползтись копиями — их уже было три у 0.0003."""
        for rel in ("bot/learning/belief_updater.py", "bot/learning/hypothesis_engine.py"):
            text = (_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("from learning.sample import TRAINING_SAMPLE_SQL", text, rel)
            self.assertEqual(text.count("{TRAINING_SAMPLE_SQL}"),
                             text.count(".format(TRAINING_SAMPLE_SQL="),
                             f"{rel}: подстановка без .format() дала бы литерал в SQL")


class TestForwardWritesAttribution(unittest.TestCase):
    """Сделка форварда обязана нести все три поля."""

    def setUp(self):
        closes = _smooth(260)
        rows = _bars(closes)
        times = [r["time"] for r in rows]
        db = FakeDB(rows, state={"SBER": times[258]})
        self.stub = StubRules(buy_at=(closes[259],), rules_version="abcdef0123456789")
        runner, self.opened, _ = _make_runner(db, self.stub)
        _run_sync(runner, db)
        self.assertEqual(len(self.opened), 1, "предусловие: ровно один вход")

    def test_signal_rules_not_empty(self):
        self.assertIsNotNone(self.opened[0].signal_rules)

    def test_rules_version_comes_from_the_engine(self):
        self.assertEqual(self.opened[0].rules_version, "abcdef0123456789")

    def test_origin_is_forward(self):
        """origin, а не is_sandbox: форвард бумажный, но обучающий."""
        self.assertEqual(self.opened[0].origin, "forward")
        self.assertTrue(self.opened[0].is_sandbox)


class TestSeedDoesNotInheritConfidence(unittest.TestCase):
    """Засев наследует только описательные поля.

    Форвард держал 0.6574 при нуле сделок именно потому, что copy включал
    confidence; у main.py тот же приём был заряжен на 0.2887.
    """

    def test_insert_does_not_mention_confidence(self):
        text = (_ROOT / "bot" / "learning" / "belief_seed.py").read_text(encoding="utf-8")
        # В INSERT-списке колонок confidence быть не должно; в докстринге и
        # комментариях слово встречается, поэтому ищем именно колоночный список.
        self.assertNotIn("confidence, best_regime, best_timeframe", text)
        self.assertIn("INSERT INTO belief_system (strategy_id, strategy_name, market, description)",
                      text)

    def test_both_call_sites_use_the_helper(self):
        for rel in ("bot/run_forward_d1.py", "bot/main.py"):
            text = (_ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("from learning.belief_seed import seed_belief", text, rel)
            self.assertNotIn("INSERT INTO belief_system", text,
                             f"{rel}: осталась своя копия засева")


if __name__ == "__main__":
    unittest.main()
