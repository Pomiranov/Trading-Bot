"""Путь к правилам и громкий отказ RulesEngine (долг №24).

Предмет. Во всех семи скриптах bot/backtest/ путь к правилам собирался как
parent.parent (= bot/), тогда как knowledge/ лежит в КОРНЕ. RulesEngine на
несуществующем файле писал logger.error и продолжал с нулём правил, поэтому
прогон не падал — он выдавал 0 сделок. Ноль сделок читается как «правило не
сработало», то есть как правдоподобный отрицательный результат, и так две недели
(с merge-коммита b2b02c4, 2026-07-14) молчали шесть скриптов.

Здесь проверяется:
  - путь берётся из config.rules_dir и больше нигде не собирается вручную;
  - отсутствие файла и пустой набор дают РАЗНЫЕ исключения, и в тексте есть
    абсолютный путь;
  - файл только с filters остаётся законным (среди будущих кандидатов такие
    будут) — «пусто» считается по всем используемым секциям, а не по «rules»;
  - синглтон rules_engine ленивый: импорт модуля его не строит. Это инвариант
    изоляции форварда, а не оптимизация — run_forward_d1 импортирует этот модуль,
    и исключение на импорте убило бы ночной прогон вместе с обработкой выходов.
"""

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bot"))

from config import config
from signals.rules_engine import RulesEngine

# Скрипты долга №24 и файл правил, который каждый должен брать.
#
# Было СЕМЬ, стало ШЕСТЬ: `run_ab_backtest.py` удалён 30.07 (долги №37/№28) как
# перекрытый `run_ab_tf_backtest.py --learn` — те же две стратегии A/B, 12 бумаг
# вместо 4, три таймфрейма включая 1h, приколоченное окно из БД вместо
# скользящего `date.today() - 200 дней` с MOEX ISS.
#
# Тест падает ЗАКОННО при добавлении или удалении измерительного скрипта: он
# читает файлы с диска, и отсутствующий даёт FileNotFoundError. Тогда правится
# этот словарь — сознательно, а не подгонкой (правило 2 §8 PROJECT_STATE).
SCRIPTS = {
    "run_osc_oos_debug.py":  "rules_osc_range.yaml",
    "run_ab_tf_backtest.py": "rules_osc_range.yaml",
    "run_ab_swing_stop.py":  "rules.yaml",
    "run_ab_trend_fix.py":   "rules.yaml",
    "run_wrd_backtest.py":   "rules_wrd_moex.yaml",
    "run_ab_wrd_sar.py":     "rules_wrd_moex.yaml",
}


class TestRulesPathSingleSource(unittest.TestCase):

    def test_config_rules_dir_points_at_repo_root(self):
        self.assertEqual(config.rules_dir, _ROOT / "knowledge" / "rules")
        self.assertTrue(config.rules_dir.is_dir(), f"нет каталога {config.rules_dir}")

    def test_no_script_builds_the_path_by_hand(self):
        """Регрессия на сам дефект: ручная сборка пути не должна вернуться."""
        offenders = []
        for name in SCRIPTS:
            text = (_ROOT / "bot" / "backtest" / name).read_text(encoding="utf-8")
            if 'parent.parent / "knowledge"' in text:
                offenders.append(name)
            if "config.rules_dir" not in text:
                offenders.append(f"{name} (не берёт config.rules_dir)")
        self.assertEqual(offenders, [], f"путь собран вручную: {offenders}")

    def test_every_referenced_rules_file_exists(self):
        for name, yml in SCRIPTS.items():
            self.assertTrue((config.rules_dir / yml).exists(),
                            f"{name} ссылается на отсутствующий {yml}")

    def test_debug_script_constant_resolves(self):
        from backtest import run_osc_oos_debug as dbg
        self.assertEqual(dbg.DEFAULT_RULES, config.rules_dir / "rules_osc_range.yaml")
        self.assertTrue(dbg.DEFAULT_RULES.exists())

    def test_forward_uses_the_same_source(self):
        import run_forward_d1 as fwd
        self.assertEqual(fwd.RULES_FILE, config.rules_dir / "rules_osc_range.yaml")


class TestFailLoud(unittest.TestCase):

    def test_missing_file_raises_filenotfound_with_absolute_path(self):
        missing = config.rules_dir / "нет-такого-файла.yaml"
        with self.assertRaises(FileNotFoundError) as ctx:
            RulesEngine(rules_file=missing)
        msg = str(ctx.exception)
        self.assertIn(str(missing.resolve()), msg,
                      "в сообщении обязан быть АБСОЛЮТНЫЙ путь, иначе следующий "
                      "будет отлаживать тот же дефект заново")

    def test_empty_ruleset_raises_valueerror_not_filenotfound(self):
        """Разные типы, чтобы вызывающий мог ловить осознанно."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.yaml"
            p.write_text("settings:\n  min_buy_score: 2.0\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                RulesEngine(rules_file=p)
            self.assertNotIsInstance(ctx.exception, FileNotFoundError)
            self.assertIn(str(p.resolve()), str(ctx.exception))

    def test_candidate_schema_is_rejected(self):
        """16 черновиков knowledge/rules/candidates — другая схема (id/status/
        params). Раньше они молча грузились как «ноль правил»."""
        cands = sorted((config.rules_dir / "candidates").glob("*.yaml"))
        self.assertTrue(cands, "предусловие: черновики на месте")
        with self.assertRaises(ValueError):
            RulesEngine(rules_file=cands[0])

    def test_filters_only_file_is_legal(self):
        """Пусто считается по ВСЕМ секциям: файл только с filters — законный
        сценарий, и среди будущих кандидатов такие будут."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "filters_only.yaml"
            p.write_text(
                "filters:\n"
                "  structural_downtrend:\n"
                "    enabled: true\n"
                "    sma_short: 50\n"
                "    sma_long: 200\n",
                encoding="utf-8")
            eng = RulesEngine(rules_file=p)          # не должно бросить
            self.assertEqual(eng._rules, [])
            self.assertTrue(eng.structural_downtrend_filter)

    def test_live_rule_files_load_as_before(self):
        expected = {"rules.yaml": 12, "rules_osc_range.yaml": 6, "rules_wrd_moex.yaml": 2}
        for name, count in expected.items():
            eng = RulesEngine(rules_file=config.rules_dir / name)
            self.assertEqual(len(eng._rules), count, f"{name}: правил стало другое число")


class TestLazySingleton(unittest.TestCase):
    """Инвариант изоляции форварда, а не оптимизация.

    run_forward_d1 импортирует signals.rules_engine. Если экземпляр строится на
    импорте, fail-loud превращает проблему конфига в падение ночного прогона —
    вместе с обработкой ВЫХОДОВ по уже лежащим в БД барам, то есть в незакрытые
    стопы. Поэтому важно, что импорт модуля экземпляр не создаёт.
    """

    def test_importing_the_class_does_not_build_the_instance(self):
        import subprocess
        code = (
            "import sys; sys.path.insert(0, r'%s')\n"
            "from signals.rules_engine import RulesEngine\n"
            "import signals.rules_engine as m\n"
            "print('BUILT' if m._rules_engine_singleton is not None else 'LAZY')\n"
            % (_ROOT / "bot")
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, cwd=str(_ROOT))
        self.assertIn("LAZY", out.stdout, out.stderr)

    def test_importing_the_forward_does_not_build_the_instance(self):
        import subprocess
        code = (
            "import sys; sys.path.insert(0, r'%s')\n"
            "import run_forward_d1\n"
            "import signals.rules_engine as m\n"
            "print('BUILT' if m._rules_engine_singleton is not None else 'LAZY')\n"
            % (_ROOT / "bot")
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, cwd=str(_ROOT))
        self.assertIn("LAZY", out.stdout, out.stderr)

    def test_accessing_the_instance_builds_and_caches_it(self):
        import signals.rules_engine as m
        first = m.rules_engine
        self.assertIsInstance(first, RulesEngine)
        self.assertIs(m.rules_engine, first, "экземпляр обязан кэшироваться")

    def test_unknown_attribute_still_raises_attributeerror(self):
        import signals.rules_engine as m
        with self.assertRaises(AttributeError):
            m.нет_такого_атрибута

    def test_unused_backtest_singleton_is_gone(self):
        import backtest.engine as be
        self.assertFalse(hasattr(be, "backtest_engine"),
                         "синглтон удалён: импортёров не было, а конструирование "
                         "на импорте — лишняя точка отказа")


if __name__ == "__main__":
    unittest.main()
