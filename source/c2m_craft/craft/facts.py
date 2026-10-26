"""Fact model for the manufacturability engine.

A concept does not carry pixels here; it carries the parameters a craftsperson
would actually ask for (wall thickness, stone size, species, span).  Facts are
declared per industry in the rule file, so adding an industry means adding a
fact schema, not editing code.
"""

from __future__ import annotations

from typing import Any

TYPE_CHECKS = {
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "string": lambda value: isinstance(value, str),
    "boolean": lambda value: isinstance(value, bool),
    "array": lambda value: isinstance(value, list),
}


def derive(concept: dict) -> dict:
    """Copy declared facts and derive the ones that follow from geometry."""
    facts: dict[str, Any] = dict(concept.get("craft_facts") or {})
    dimensions = ((concept.get("form") or {}).get("dimensions_mm") or {})
    if "max_dimension_mm" not in facts and dimensions:
        values = [float(value) for value in dimensions.values() if isinstance(value, (int, float))]
        if values:
            facts["max_dimension_mm"] = round(max(values), 2)
    return facts


def check(facts: dict, facts_schema: dict) -> dict:
    """Validate facts against the industry fact schema."""
    errors: list[str] = []
    unknown = sorted(set(facts) - set(facts_schema))
    if unknown:
        errors.append(f"unknown facts: {', '.join(unknown)}")

    missing: list[str] = []
    for name, spec in sorted(facts_schema.items()):
        if spec.get("required") and name not in facts:
            missing.append(name)

    for name, value in sorted(facts.items()):
        spec = facts_schema.get(name)
        if not spec:
            continue
        expected = spec.get("type", "number")
        checker = TYPE_CHECKS.get(expected)
        if checker and not checker(value):
            errors.append(f"{name} must be {expected}, got {type(value).__name__}")
            continue
        if expected in ("number", "integer"):
            low, high = spec.get("min"), spec.get("max")
            if low is not None and value < low:
                errors.append(f"{name}={value} below minimum {low}")
            if high is not None and value > high:
                errors.append(f"{name}={value} above maximum {high}")
        allowed = spec.get("enum")
        if allowed:
            if expected == "array":
                bad = [item for item in value if item not in allowed]
                if bad:
                    errors.append(f"{name} contains values outside {allowed}: {bad}")
            elif value not in allowed:
                errors.append(f"{name}={value!r} not in {allowed}")

    return {"ok": not errors and not missing, "errors": errors, "missing": missing}


def required_facts(facts_schema: dict) -> list[str]:
    return sorted(name for name, spec in facts_schema.items() if spec.get("required"))


def describe(facts_schema: dict, language: str = "en") -> list[dict]:
    """Human-readable fact catalogue, used by the spec endpoint and docs."""
    rows = []
    for name, spec in sorted(facts_schema.items()):
        description = spec.get("description") or {}
        rows.append(
            {
                "fact": name,
                "type": spec.get("type"),
                "required": bool(spec.get("required")),
                "unit": spec.get("unit"),
                "min": spec.get("min"),
                "max": spec.get("max"),
                "enum": spec.get("enum"),
                "description": description.get(language) or description.get("en") or "",
            }
        )
    return rows
