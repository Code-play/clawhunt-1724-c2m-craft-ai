"""Manufacturability assessment: the two-tier verdict.

Tier one is deterministic and reproducible: evaluate the workshop capability
envelope plus the industry rules against the declared facts, then reduce the
result to a verdict with reasons and fixes.  Tier two is the craftsperson: a
rule may ask for a human review, and the assessment record keeps both the auto
verdict and the human disposition.
"""

from __future__ import annotations

from typing import Iterable

from ..core.canonical import content_hash
from . import facts as facts_mod
from .rules import RuleSet, evaluate_capability, evaluate_rule, render_i18n

VERDICTS = ("manufacturable", "conditionally_manufacturable", "not_manufacturable")


def _reduce(evaluations: Iterable[dict]) -> tuple[str, list[str], list[dict]]:
    blockers: list[str] = []
    conditional = False
    for item in evaluations:
        if item["status"] != "fail":
            continue
        if item["severity"] == "blocker":
            blockers.append(item["rule_id"])
        else:
            conditional = True
    blockers = sorted(set(blockers))
    if blockers:
        return "not_manufacturable", blockers, []
    if conditional:
        return "conditionally_manufacturable", [], []
    return "manufacturable", [], []


def _fixes_from(evaluations: Iterable[dict], ruleset: RuleSet, workshop: dict, facts: dict) -> list[dict]:
    rule_index = ruleset.by_id
    cap_index = {str(item["capability_id"]): item for item in workshop.get("capability_checks", [])}
    fixes: list[dict] = []
    seen: set[str] = set()
    for item in evaluations:
        if item["status"] != "fail":
            continue
        rule_id = item["rule_id"]
        source = rule_index.get(rule_id) or cap_index.get(rule_id)
        if not source:
            continue
        for fix in source.get("fixes", []):
            key = f"{rule_id}|{fix.get('text', {}).get('en', '')}"
            if key in seen:
                continue
            seen.add(key)
            fixes.append(
                {
                    "rule_id": rule_id,
                    "text": render_i18n(fix["text"], facts),
                    "suggested_change": dict(fix.get("suggested_change") or {}),
                }
            )
    return fixes


def assess(
    concept: dict,
    workshop: dict,
    ruleset: RuleSet,
    *,
    assessment_id: str,
    created_at: str,
    queue_id: str | None = None,
    reviewer: str | None = None,
) -> dict:
    facts = facts_mod.derive(concept)
    check = facts_mod.check(facts, ruleset.facts_schema)

    evaluations: list[dict] = []
    for capability in workshop.get("capability_checks", []):
        evaluations.append(evaluate_capability(capability, facts))
    for rule in ruleset.rules:
        evaluations.append(evaluate_rule(rule, facts))

    verdict, blockers, _ = _reduce(evaluations)
    if check["missing"]:
        verdict = "not_assessable"

    failed = [item for item in evaluations if item["status"] == "fail"]
    fixes = _fixes_from(failed, ruleset, workshop, facts)

    review_ids: list[str] = []
    for item in failed:
        if item["source"] != "rule":
            continue
        rule = ruleset.get(item["rule_id"])
        trigger = str((rule.get("review") or {}).get("trigger", "never"))
        if trigger in ("on_fail", "always"):
            review_ids.append(item["rule_id"])

    required = bool(review_ids)
    artisan = {
        "required": required,
        "queue_id": queue_id if required else None,
        "status": "pending" if required else "not_required",
        "reviewer": reviewer if required else None,
        "decision_verdict": None,
        "notes": None,
        "decided_at": None,
    }

    assessment = {
        "assessment_id": assessment_id,
        "concept_id": str(concept["concept_id"]),
        "industry": str(concept["industry"]),
        "workshop_id": str(workshop["workshop_id"]),
        "facts": facts,
        "rule_evaluations": evaluations,
        "auto": {
            "verdict": verdict if verdict in VERDICTS else "not_manufacturable",
            "evaluated_rules": sum(1 for item in evaluations if item["status"] != "na"),
            "blocking_rules": blockers,
        },
        "artisan": artisan,
        "blockers": blockers,
        "fixes": fixes,
        "missing_facts": list(check["missing"]),
        "final_verdict": verdict,
        "reproducibility": {
            "rules_version": ruleset.version,
            "facts_hash": content_hash(facts),
        },
        "created_at": created_at,
    }
    return assessment


def review_reasons(assessment: dict, ruleset: RuleSet) -> list[dict]:
    """Return the failed rules that asked for an artisan review."""
    reasons = []
    for item in assessment.get("rule_evaluations", []):
        if item["status"] != "fail":
            continue
        rule = ruleset.by_id.get(item["rule_id"])
        if not rule:
            continue
        if str((rule.get("review") or {}).get("trigger", "never")) in ("on_fail", "always"):
            reasons.append({"rule_id": item["rule_id"], "reason": item["reason"]})
    return reasons


def apply_review(assessment: dict, review_item: dict) -> dict:
    """Fold an artisan decision into an assessment (override or confirmation)."""
    updated = dict(assessment)
    artisan = dict(assessment.get("artisan") or {})
    decision = review_item.get("decision") or {}
    artisan["queue_id"] = review_item.get("queue_id")
    artisan["status"] = review_item.get("status", "pending")
    artisan["reviewer"] = (review_item.get("reviewer") or {}).get("artisan_id")
    artisan["decision_verdict"] = decision.get("verdict")
    artisan["notes"] = decision.get("reason")
    artisan["decided_at"] = decision.get("decided_at")
    updated["artisan"] = artisan
    if decision.get("verdict"):
        updated["final_verdict"] = decision["verdict"]
    return updated


def summarize(assessment: dict, language: str = "en") -> str:
    verdict = str(assessment.get("final_verdict"))
    if verdict == "not_assessable":
        missing = ", ".join(assessment.get("missing_facts", []))
        return f"not assessable: missing facts {missing}"
    lines = [f"{verdict} at {assessment.get('workshop_id')}"]
    for blocker in assessment.get("blockers", []):
        lines.append(f"  blocker: {blocker}")
    for fix in assessment.get("fixes", []):
        lines.append(f"  fix: {fix['text'].get(language, fix['text'].get('en', ''))}")
    return "\n".join(lines)
