"""Seed the hypotheses table from knowledge/rules YAML files.

Each YAML rule becomes an observation-stage hypothesis so the learning
engine can evaluate whether the rule actually works in live sandbox data.
Uses INSERT ... ON CONFLICT DO NOTHING so re-runs are idempotent and
existing live-trained hypotheses are never overwritten.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

_STRATEGY_MAP = {
    "rules.yaml":           "default_moex",
    "rules_osc_range.yaml": "osc_range_moex",
    "rules_wrd_moex.yaml":  "breakout_moex",
}


def _load_rules(path: Path) -> list[dict]:
    try:
        import yaml  # type: ignore
    except ImportError:
        logger.warning("PyYAML not installed — knowledge seeding skipped")
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("rules", []) if isinstance(data, dict) else []
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return []


def _rule_to_hypothesis(rule: dict, strategy_id: str, source_file: str) -> dict[str, Any]:
    name = rule.get("name", "unknown")
    description = rule.get("description") or name
    action = rule.get("action", "BUY").upper()
    conditions = {
        "rule_name":   name,
        "action":      action,
        "weight":      float(rule.get("weight", 1.0)),
        "strategy_id": strategy_id,
        "source_file": source_file,
        "checks":      rule.get("conditions", []),
    }
    return {
        "description": description,
        "market":      "stocks",
        "conditions":  conditions,
        "stage":       "observation",
    }


def seed_knowledge_hypotheses(engine) -> int:
    """Insert one hypothesis per knowledge rule; return count of rows inserted."""
    from sqlalchemy import text

    rule_files = [
        _KNOWLEDGE_DIR / "rules.yaml",
        *(_KNOWLEDGE_DIR / "rules").glob("*.yaml"),
    ]

    hypotheses: list[dict] = []
    seen_names: set[str] = set()

    for path in rule_files:
        if not path.exists():
            continue
        strategy_id = _STRATEGY_MAP.get(path.name, "default_moex")
        for rule in _load_rules(path):
            name = rule.get("name", "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            hypotheses.append(_rule_to_hypothesis(rule, strategy_id, path.name))

    if not hypotheses:
        logger.info("KnowledgeSeeder: no rules found — seeding skipped")
        return 0

    inserted = 0
    with engine.begin() as conn:
        for hyp in hypotheses:
            result = conn.execute(
                text("""
                    INSERT INTO hypotheses (description, market, stage, conditions)
                    VALUES (:desc, :market, :stage, :cond::jsonb)
                    ON CONFLICT (description) DO NOTHING
                """),
                {
                    "desc":   hyp["description"],
                    "market": hyp["market"],
                    "stage":  hyp["stage"],
                    "cond":   json.dumps(hyp["conditions"], ensure_ascii=False),
                },
            )
            inserted += result.rowcount

    logger.info("KnowledgeSeeder: seeded %d / %d hypothesis(es)", inserted, len(hypotheses))
    return inserted
