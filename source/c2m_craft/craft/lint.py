"""Rule lint: the safety net that lets a non-programmer edit rule files.

The lint checks structure, referential integrity, type sanity and coverage, and
it also checks the workshop capability files against the same fact schema, so a
renamed fact cannot silently turn a rule into a no-op.
"""

from __future__ import annotations

from pathlib import Path

from ..core.contracts import SchemaStore
from . import facts as facts_mod
from .rules import RuleSet, condition_facts, iter_conditions, placeholders

NUMERIC_OPS = {"lt", "lte", "gt", "gte"}
ENUM_OPS = {"in", "not_in", "contains_any"}


def _finding(code: str, severity: str, subject: str, message: str) -> dict:
    return {"code": code, "severity": severity, "subject": subject, "message": message}


def _rule_schema_key(store: SchemaStore) -> str:
    cache = getattr(store, "_rule_schema_key", None)
    if cache:
        return cache
    path = store.root / "config" / "craft_rules" / "rule_file.schema.json"
    key = store.register_file(path)
    store._rule_schema_key = key  # type: ignore[attr-defined]
    return key


def lint_ruleset(
    store: SchemaStore,
    ruleset_path: Path | str,
    as_of: str | None = None,
    also_used: set[str] | None = None,
) -> dict:
    path = Path(ruleset_path)
    data = store.json_load(path)
    findings: list[dict] = []

    key = _rule_schema_key(store)
    for issue in store.validate_key(key, data):
        findings.append(
            _finding("SCHEMA", "error", str(path.name), f"{issue.path}: {issue.message}")
        )

    facts_schema = data.get("facts_schema") or {}
    rules = data.get("rules") or []
    factset = set(facts_schema)

    seen: dict[str, int] = {}
    for index, rule in enumerate(rules):
        rule_id = str(rule.get("id", f"<index {index}>"))
        seen[rule_id] = seen.get(rule_id, 0) + 1
    for rule_id, count in sorted(seen.items()):
        if count > 1:
            findings.append(_finding("DUP_ID", "error", rule_id, f"declared {count} times"))

    used_facts: set[str] = set()
    for rule in rules:
        rule_id = str(rule.get("id"))
        for predicate in iter_conditions(rule):
            name = str(predicate.get("fact"))
            used_facts.add(name)
            spec = facts_schema.get(name)
            if spec is None:
                findings.append(
                    _finding("UNKNOWN_FACT", "error", rule_id, f"uses undeclared fact {name}")
                )
                continue
            op = str(predicate.get("op"))
            ftype = spec.get("type")
            if op in NUMERIC_OPS and ftype not in ("number", "integer"):
                findings.append(
                    _finding(
                        "TYPE_MISMATCH",
                        "error",
                        rule_id,
                        f"{op} on a {ftype} fact cannot be ordered",
                    )
                )
            if op in ENUM_OPS and not spec.get("enum"):
                findings.append(
                    _finding(
                        "TYPE_MISMATCH",
                        "error",
                        rule_id,
                        f"{op} needs an enum fact, {name} has none",
                    )
                )
            if op in ("missing", "present") and predicate.get("value") is not None:
                findings.append(
                    _finding("VALUE_IGNORED", "warn", rule_id, f"{op} ignores its value")
                )
            if op not in NUMERIC_OPS | ENUM_OPS | {"eq", "ne", "missing", "present"}:
                findings.append(
                    _finding("UNKNOWN_OP", "error", rule_id, f"unsupported operator {op}")
                )

        for template in (rule.get("reason"), *[fix.get("text") for fix in rule.get("fixes", [])]):
            for name in placeholders(template or {}):
                if name not in factset:
                    findings.append(
                        _finding(
                            "PLACEHOLDER_UNKNOWN",
                            "error",
                            rule_id,
                            f"message placeholder {{{name}}} is not a declared fact",
                        )
                    )

        for fix in rule.get("fixes", []):
            for name in (fix.get("suggested_change") or {}):
                if name not in factset:
                    findings.append(
                        _finding(
                            "FIX_UNKNOWN_FACT",
                            "error",
                            rule_id,
                            f"suggested_change names undeclared fact {name}",
                        )
                    )

        review = rule.get("review") or {}
        if rule.get("severity") == "blocker" and review.get("tier") == "auto" and review.get(
            "trigger"
        ) == "never":
            findings.append(
                _finding(
                    "REVIEW_GAP",
                    "warn",
                    rule_id,
                    "a blocker is never reviewed by a craftsperson",
                )
            )

        evidence = rule.get("evidence") or {}
        if evidence.get("client_confirmation_required") and evidence.get("reviewed_by") == "pending":
            findings.append(
                _finding(
                    "EVIDENCE_PENDING",
                    "info",
                    rule_id,
                    "synthetic baseline awaiting client craftsperson confirmation",
                )
            )

        if not rule.get("references"):
            findings.append(
                _finding("NO_REFERENCE", "warn", rule_id, "no documentation reference")
            )

        if as_of and rule.get("evidence", {}).get("captured_at", "") > as_of:
            findings.append(
                _finding("FUTURE_EVIDENCE", "warn", rule_id, "evidence is dated after as_of")
            )

    # shadowed rules: identical condition and identical verdict
    signatures: dict[str, list[str]] = {}
    for rule in rules:
        signature = f"{sorted(condition_facts(rule['when']))}|{rule['when']}|{rule['verdict']}"
        signatures.setdefault(signature, []).append(str(rule["id"]))
    for signature, ids in signatures.items():
        if len(ids) > 1:
            findings.append(
                _finding("SHADOWED", "warn", ", ".join(ids), "identical condition and verdict")
            )

    errors = sum(1 for item in findings if item["severity"] == "error")
    warnings = sum(1 for item in findings if item["severity"] == "warn")
    infos = sum(1 for item in findings if item["severity"] == "info")
    referenced = set(used_facts) | set(also_used or ())
    for name in sorted(factset - referenced):
        findings.append(
            _finding(
                "UNUSED_FACT",
                "warn",
                name,
                "declared but referenced by neither a rule nor a capability check",
            )
        )
        warnings += 1
    required = facts_mod.required_facts(facts_schema)
    covered = [name for name in required if name in referenced]
    stats = {
        "industry": data.get("industry"),
        "version": data.get("version"),
        "rules": len(rules),
        "facts": len(facts_schema),
        "facts_used": len(referenced),
        "required_facts": len(required),
        "coverage_bp": (len(covered) * 10000) // max(len(required), 1),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }
    return {
        "ok": errors == 0,
        "path": str(path),
        "findings": findings,
        "stats": stats,
        "used_facts": sorted(used_facts),
        "data": data,
    }


def lint_equipment(
    store: SchemaStore,
    workshop_path: Path | str,
    facts_schema: dict,
    used_facts: set[str] | None = None,
) -> list[dict]:
    workshop = store.json_load(Path(workshop_path))
    findings: list[dict] = []
    workshop_id = str(workshop.get("workshop_id"))

    seen: set[str] = set()
    for check in workshop.get("capability_checks", []):
        check_id = str(check.get("capability_id"))
        if check_id in seen:
            findings.append(_finding("DUP_CAPABILITY", "error", workshop_id, check_id))
        seen.add(check_id)
        name = str(check.get("fact"))
        if used_facts is not None:
            used_facts.add(name)
            applies = check.get("applies_when") or {}
            if isinstance(applies, dict) and applies.get("fact"):
                used_facts.add(str(applies["fact"]))
        spec = facts_schema.get(name)
        if spec is None:
            findings.append(
                _finding(
                    "UNKNOWN_FACT",
                    "error",
                    f"{workshop_id}/{check_id}",
                    f"capability check uses undeclared fact {name}",
                )
            )
            continue
        if str(check.get("op")) in NUMERIC_OPS and spec.get("type") not in ("number", "integer"):
            findings.append(
                _finding(
                    "TYPE_MISMATCH",
                    "error",
                    f"{workshop_id}/{check_id}",
                    f"ordered comparison on {spec.get('type')} fact {name}",
                )
            )
    equipment_ids = set()
    for item in workshop.get("equipment", []):
        equipment_id = str(item.get("equipment_id"))
        if equipment_id in equipment_ids:
            findings.append(_finding("DUP_EQUIPMENT", "error", workshop_id, equipment_id))
        equipment_ids.add(equipment_id)
    for checkpoint in workshop.get("qc_checkpoints", []):
        if not checkpoint.get("pass_criteria"):
            findings.append(
                _finding(
                    "QC_NO_CRITERIA",
                    "error",
                    workshop_id,
                    str(checkpoint.get("checkpoint_id")),
                )
            )
    return findings


def lint_all(store: SchemaStore, settings) -> dict:
    per_industry: dict[str, dict] = {}
    findings: list[dict] = []
    all_ids: dict[str, str] = {}

    for industry in settings.industry_ids():
        equipment_facts: set[str] = set()
        workshop_paths = [
            settings.path(f"config/equipment/{workshop_id}.json")
            for workshop_id in settings.workshop_ids(industry)
        ]
        for path in workshop_paths:
            workshop = store.json_load(path)
            for check in workshop.get("capability_checks", []):
                equipment_facts.add(str(check["fact"]))
                applies = check.get("applies_when") or {}
                if isinstance(applies, dict) and applies.get("fact"):
                    equipment_facts.add(str(applies["fact"]))

        result = lint_ruleset(
            store,
            settings.rules_path(industry),
            as_of=settings.as_of,
            also_used=equipment_facts,
        )
        per_industry[industry] = result["stats"]
        findings.extend(result["findings"])
        for rule in result["data"]["rules"]:
            rule_id = str(rule["id"])
            if rule_id in all_ids:
                findings.append(
                    _finding(
                        "CROSS_DUP_ID",
                        "error",
                        rule_id,
                        f"used by both {all_ids[rule_id]} and {industry}",
                    )
                )
            all_ids[rule_id] = industry
        facts_schema = result["data"]["facts_schema"]
        industry_used: set[str] = set(result.get("used_facts", [])) | equipment_facts
        for path in workshop_paths:
            findings.extend(lint_equipment(store, path, facts_schema, industry_used))
        per_industry[industry]["facts_used_all"] = len(industry_used)

    errors = sum(1 for item in findings if item["severity"] == "error")
    warnings = sum(1 for item in findings if item["severity"] == "warn")
    infos = sum(1 for item in findings if item["severity"] == "info")
    return {
        "ok": errors == 0,
        "findings": findings,
        "industries": per_industry,
        "totals": {
            "rules": sum(item["rules"] for item in per_industry.values()),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
        },
    }
