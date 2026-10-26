"""Deterministic rule engine.

A rule is a defect detector: if its condition matches the facts, the rule fails
and contributes its verdict plus a fix.  Conditions are plain data, so a
craftsperson can add a rule without touching Python.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

FACT_NAME = re.compile(r"\{([a-z][a-z0-9_]*)\}")

TRIGGERS = ("never", "on_fail", "always")


@dataclass
class RuleSet:
    industry: str
    version: str
    as_of: str
    facts_schema: dict
    rules: list[dict] = field(default_factory=list)

    @property
    def by_id(self) -> dict[str, dict]:
        return {str(rule["id"]): rule for rule in self.rules}

    def get(self, rule_id: str) -> dict:
        try:
            return self.by_id[rule_id]
        except KeyError as exc:
            raise KeyError(f"unknown rule {rule_id}") from exc

    def stats(self) -> dict:
        severities: dict[str, int] = {}
        for rule in self.rules:
            severities[rule["severity"]] = severities.get(rule["severity"], 0) + 1
        return {
            "industry": self.industry,
            "version": self.version,
            "rules": len(self.rules),
            "by_severity": severities,
            "facts": len(self.facts_schema),
            "required_facts": sum(1 for spec in self.facts_schema.values() if spec.get("required")),
        }


def load_ruleset(path: Path | str) -> RuleSet:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return RuleSet(
        industry=str(data["industry"]),
        version=str(data["version"]),
        as_of=str(data["as_of"]),
        facts_schema=dict(data["facts_schema"]),
        rules=list(data["rules"]),
    )


# -- condition evaluation -------------------------------------------------
def _leaf(predicate: dict, facts: dict) -> bool:
    name = str(predicate["fact"])
    op = str(predicate["op"])
    present = name in facts
    if op == "missing":
        return not present
    if op == "present":
        return present
    if not present:
        return False
    value = facts[name]
    target = predicate.get("value")
    if op == "lt":
        return value < target
    if op == "lte":
        return value <= target
    if op == "gt":
        return value > target
    if op == "gte":
        return value >= target
    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    if op == "in":
        return value in (target or [])
    if op == "not_in":
        return value not in (target or [])
    if op == "contains_any":
        if isinstance(value, list):
            return any(item in (target or []) for item in value)
        return value in (target or [])
    raise ValueError(f"unsupported operator: {op}")


def evaluate_condition(condition: Any, facts: dict) -> bool:
    if not isinstance(condition, dict):
        raise TypeError("condition must be an object")
    if "all" in condition:
        return all(evaluate_condition(item, facts) for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(item, facts) for item in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], facts)
    return _leaf(condition, facts)


def condition_facts(condition: Any) -> set[str]:
    names: set[str] = set()
    if not isinstance(condition, dict):
        return names
    if "all" in condition:
        for item in condition["all"]:
            names |= condition_facts(item)
    elif "any" in condition:
        for item in condition["any"]:
            names |= condition_facts(item)
    elif "not" in condition:
        names |= condition_facts(condition["not"])
    elif "fact" in condition:
        names.add(str(condition["fact"]))
    return names


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return text or "0"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def render_i18n(template: dict, facts: dict) -> dict:
    """Fill ``{fact}`` placeholders in both languages."""

    def fill(text: str) -> str:
        def replace(match: re.Match) -> str:
            name = match.group(1)
            return _format_value(facts.get(name, match.group(0)))

        return FACT_NAME.sub(replace, text)

    return {"zh": fill(str(template.get("zh", ""))), "en": fill(str(template.get("en", "")))}


def placeholders(template: dict) -> set[str]:
    names: set[str] = set()
    for language in ("zh", "en"):
        names |= set(FACT_NAME.findall(str(template.get(language, ""))))
    return names


# -- rule evaluation ------------------------------------------------------
def evaluate_rule(rule: dict, facts: dict) -> dict:
    used = sorted(condition_facts(rule["when"]))
    applicable = True
    applies_when = rule.get("applies_when")
    if applies_when:
        applicable = evaluate_condition(applies_when, facts)
        used = sorted(set(used) | condition_facts(applies_when))
    missing = [name for name in used if name not in facts]
    if not applicable or missing:
        status = "na"
    else:
        status = "fail" if evaluate_condition(rule["when"], facts) else "pass"
    return {
        "rule_id": str(rule["id"]),
        "source": str(rule.get("source", "rule")),
        "status": status,
        "severity": str(rule["severity"]),
        "reason": render_i18n(rule["reason"], facts) if status == "fail" else {
            "zh": str(rule.get("title", {}).get("zh", "")),
            "en": str(rule.get("title", {}).get("en", "")),
        },
        "facts_used": used,
    }


def evaluate_capability(check: dict, facts: dict) -> dict:
    condition = {"fact": check["fact"], "op": check["op"], "value": check.get("value")}
    used = sorted(condition_facts(condition))
    applicable = True
    applies_when = check.get("applies_when")
    if applies_when:
        applicable = evaluate_condition(applies_when, facts)
        used = sorted(set(used) | condition_facts(applies_when))
    missing = [name for name in used if name not in facts]
    if not applicable or missing:
        status = "na"
    else:
        status = "fail" if evaluate_condition(condition, facts) else "pass"
    return {
        "rule_id": str(check["capability_id"]),
        "source": "capability",
        "status": status,
        "severity": str(check["severity"]),
        "reason": render_i18n(check["reason"], facts) if status == "fail" else {
            "zh": str(check.get("title", {}).get("zh", "")),
            "en": str(check.get("title", {}).get("en", "")),
        },
        "facts_used": used,
    }


def iter_conditions(rule: dict) -> Iterator[dict]:
    """Yield every leaf condition of a rule (used by lint)."""
    def walk(node: Any) -> Iterator[dict]:
        if not isinstance(node, dict):
            return
        if "all" in node:
            for item in node["all"]:
                yield from walk(item)
        elif "any" in node:
            for item in node["any"]:
                yield from walk(item)
        elif "not" in node:
            yield from walk(node["not"])
        elif "fact" in node:
            yield node

    yield from walk(rule.get("when"))
    if rule.get("applies_when"):
        yield from walk(rule["applies_when"])


def explain(ruleset: RuleSet, rule_id: str) -> dict:
    rule = ruleset.get(rule_id)
    return {
        "rule_id": rule_id,
        "industry": ruleset.industry,
        "process": rule["process"],
        "severity": rule["severity"],
        "title": rule["title"],
        "condition": rule["when"],
        "facts": sorted(condition_facts(rule["when"])),
        "verdict": rule["verdict"],
        "reason": rule["reason"],
        "fixes": rule["fixes"],
        "evidence": rule["evidence"],
        "review": rule["review"],
        "references": rule.get("references", []),
        "version": rule["version"],
    }
