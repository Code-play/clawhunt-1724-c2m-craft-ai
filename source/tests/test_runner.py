"""Unit and integration tests: one command, no dependencies.

Run from the delivery root:

    python tests/test_runner.py

The last line is always ``N/N tests passed``.  Every test is a plain function
decorated with ``@test``; the runner reports the failing one with its assertion
message, so a red run points at a single behaviour.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c2m_craft import requirements as requirements_mod  # noqa: E402
from c2m_craft.commerce import dispatch as dispatch_mod  # noqa: E402
from c2m_craft.commerce import settlement as settlement_mod  # noqa: E402
from c2m_craft.core import canonical, money  # noqa: E402
from c2m_craft.core.contracts import SchemaStore, format_issues  # noqa: E402
from c2m_craft.core.errors import Conflict, ContractError, NotFound, ValidationFailed  # noqa: E402
from c2m_craft.core.invariants import known_ids, visual_asset_checksum  # noqa: E402
from c2m_craft.enterprise.growth import GrowthStack  # noqa: E402
from c2m_craft.enterprise.registry import ComponentRegistry  # noqa: E402
from c2m_craft.enterprise.runtime import EnterpriseRuntime, Profiles  # noqa: E402
from c2m_craft.ip import IpPipeline  # noqa: E402
from c2m_craft.craft import facts as facts_mod  # noqa: E402
from c2m_craft.craft import lint as lint_mod  # noqa: E402
from c2m_craft.craft.assessment import assess  # noqa: E402
from c2m_craft.craft.rules import (  # noqa: E402
    condition_facts,
    evaluate_condition,
    explain,
    load_ruleset,
    render_i18n,
)
from c2m_craft.creative.workstation import ConceptRequest, nearest_palette  # noqa: E402
from c2m_craft.service import Service  # noqa: E402
from c2m_craft.web.server import route_table, start_in_thread  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="c2m_tests_"))
TESTS: list = []
STORE = SchemaStore(ROOT)
SETTINGS = Service(ROOT, TMP / "boot", reset=True).settings
RULESETS = {
    industry: load_ruleset(SETTINGS.rules_path(industry)) for industry in SETTINGS.industry_ids()
}


def test(func):
    TESTS.append(func)
    return func


def new_service(name: str) -> Service:
    return Service(ROOT, TMP / name, reset=True)


def eq(left, right, label: str) -> None:
    if left != right:
        raise AssertionError(f"{label}: {left!r} != {right!r}")


def ok(condition, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def concept(concept_id: str = "DC-0001") -> dict:
    return SchemaStore.json_load(ROOT / "samples" / "concepts" / f"{concept_id}.json")


def sample(relative: str) -> dict:
    return SchemaStore.json_load(ROOT / relative)


# -- contracts ------------------------------------------------------------
@test
def contracts_registry_lists_all() -> None:
    eq(len(STORE.contract_ids), 23, "contract count")
    eq(STORE.contract_ids[0], "common", "first contract is common")
    eq(STORE.registry["version"], "2.0.0", "registry version")


@test
def contracts_every_urn_is_loaded() -> None:
    missing = [entry["id"] for entry in STORE.registry["contracts"] if entry["urn"] not in STORE.schemas]
    eq(missing, [], "unloaded contracts")


@test
def contracts_every_file_exists() -> None:
    missing = [entry["file"] for entry in STORE.registry["contracts"] if not (ROOT / "contracts" / entry["file"]).is_file()]
    eq(missing, [], "missing schema files")


@test
def contracts_references_resolve() -> None:
    def walk(node, key, found):
        if isinstance(node, dict):
            if "$ref" in node:
                found.append((key, node["$ref"]))
            for value in node.values():
                walk(value, key, found)
        elif isinstance(node, list):
            for value in node:
                walk(value, key, found)

    found: list = []
    for key, schema in STORE.schemas.items():
        walk(schema, key, found)
    broken = []
    for key, ref in found:
        try:
            STORE.resolve(ref, key)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{key} -> {ref}: {exc}")
    eq(broken, [], "unresolvable references")
    ok(len(found) >= 50, f"expected many references, found {len(found)}")


@test
def contracts_common_defs_are_complete() -> None:
    defs = STORE.schemas["urn:c2m:contract:common"]["$defs"]
    for name in ("i18n_text", "money", "timestamp", "actor", "hex_color", "rate_bp", "slug", "industry"):
        ok(name in defs, f"common.$defs.{name}")


@test
def contracts_invariants_are_implemented() -> None:
    registered = {item for entry in STORE.registry["contracts"] for item in entry.get("invariants", [])}
    eq(sorted(registered), sorted(known_ids()), "invariant registry")


@test
def contracts_accept_library_assets() -> None:
    assets = sample("samples/library/assets.json")["assets"]
    for asset in assets:
        issues = STORE.validate("pattern_asset", asset, ctx={"as_of": SETTINGS.as_of})
        eq([issue.as_dict() for issue in issues], [], f"asset {asset['asset_id']}")


@test
def contracts_accept_concepts() -> None:
    for path in sorted((ROOT / "samples" / "concepts").glob("DC-*.json")):
        payload = SchemaStore.json_load(path)
        eq([i.as_dict() for i in STORE.validate("design_concept", payload)], [], path.name)


@test
def contracts_accept_positive_samples() -> None:
    from c2m_craft.demo import contract_for

    for path in sorted((ROOT / "samples" / "contracts" / "positive").glob("*.json")):
        payload = SchemaStore.json_load(path)
        issues = STORE.validate(contract_for(path.name), payload, ctx={"as_of": SETTINGS.as_of})
        eq([i.as_dict() for i in issues], [], path.name)


@test
def contracts_reject_missing_licensing_source() -> None:
    payload = copy.deepcopy(sample("samples/library/assets.json")["assets"][0])
    payload["license"].pop("source_type")
    issues = STORE.validate("pattern_asset", payload)
    ok(any(issue.keyword == "required" and issue.path == "$.license" for issue in issues),
       format_issues(issues))


@test
def contracts_reject_empty_usage_scope() -> None:
    payload = copy.deepcopy(sample("samples/library/assets.json")["assets"][0])
    payload["license"]["usage_scope"] = []
    issues = STORE.validate("pattern_asset", payload)
    ok(any(issue.invariant == "INV-LIC-02" for issue in issues), format_issues(issues))


@test
def contracts_reject_exclusive_heritage() -> None:
    payload = copy.deepcopy(sample("samples/library/assets.json")["assets"][2])
    payload["license"]["exclusive"] = True
    issues = STORE.validate("pattern_asset", payload)
    ok(any(issue.invariant == "INV-LIC-03" for issue in issues), format_issues(issues))


@test
def contracts_reject_inverted_window() -> None:
    payload = copy.deepcopy(sample("samples/library/assets.json")["assets"][0])
    payload["license"]["valid_from"] = "2029-01-01T00:00:00Z"
    issues = STORE.validate("pattern_asset", payload)
    ok(any(issue.invariant == "INV-LIC-04" for issue in issues), format_issues(issues))


@test
def contracts_reject_expired_window_when_active_required() -> None:
    payload = copy.deepcopy(sample("samples/library/assets.json")["assets"][6])
    issues = STORE.validate(
        "pattern_asset", payload, ctx={"as_of": SETTINGS.as_of, "require_active_window": True}
    )
    ok(any(issue.invariant == "INV-LIC-04" for issue in issues), format_issues(issues))


@test
def contracts_reject_bad_palette_hex() -> None:
    payload = copy.deepcopy(sample("samples/library/assets.json")["assets"][0])
    payload["palette"] = ["gold"]
    issues = STORE.validate("pattern_asset", payload)
    ok(any(issue.keyword == "pattern" and issue.path == "$.palette[0]" for issue in issues),
       format_issues(issues))


@test
def contracts_reject_order_share_mismatch() -> None:
    payload = copy.deepcopy(sample("samples/contracts/positive/order-ORD-0001.json"))
    payload["amounts"]["designer_share_cents"] += 100
    issues = STORE.validate("c2m_order", payload, ctx={"allowed_statuses": ["settled"]})
    ok(any(issue.invariant == "INV-ORDER-01" for issue in issues), format_issues(issues))


@test
def contracts_reject_settlement_rate_mismatch() -> None:
    payload = copy.deepcopy(sample("samples/contracts/positive/settlement-ST-0001.json"))
    payload["split_policy"]["lines"][0]["rate_bp"] = 1000
    issues = STORE.validate("settlement", payload)
    ok(any(issue.invariant == "INV-MONEY-01" for issue in issues), format_issues(issues))


@test
def contracts_reject_override_without_reason() -> None:
    payload = copy.deepcopy(sample("samples/contracts/positive/artisan-review-AR-0001.json"))
    payload["status"] = "overridden"
    payload["decision"] = {"verdict": "manufacturable", "reason": "ok", "decided_at": "2026-10-23T00:00:00Z"}
    issues = STORE.validate("artisan_review", payload)
    ok(any(issue.invariant == "INV-REVIEW-01" for issue in issues), format_issues(issues))


@test
def contracts_reject_ip_exclusive_heritage() -> None:
    payload = copy.deepcopy(sample("samples/contracts/positive/ip-license-IPL-0001.json"))
    payload["traditional_prototype_refs"][0]["exclusive_claimed"] = True
    issues = STORE.validate("ip_license", payload)
    ok(any(issue.invariant == "INV-IP-01" for issue in issues), format_issues(issues))


@test
def contracts_order_event_pointer_validates() -> None:
    event = {
        "event_id": "EVT-0001-0001",
        "order_id": "ORD-0001",
        "seq": 1,
        "at": "2026-10-23T00:00:00Z",
        "type": "order_created",
        "from_status": "none",
        "to_status": "draft",
        "actor": {"kind": "buyer", "id": "buyer-01"},
        "payload": {},
        "prev_hash": "0" * 64,
        "hash": "a" * 64,
    }
    issues = STORE.validate_pointer("urn:c2m:contract:c2m-order", "/$defs/order_event", event)
    eq([i.as_dict() for i in issues], [], "order event")


@test
def contracts_order_event_pointer_rejects_bad_hash() -> None:
    event = {
        "event_id": "EVT-0001-0001",
        "order_id": "ORD-0001",
        "seq": 1,
        "at": "2026-10-23T00:00:00Z",
        "type": "order_created",
        "from_status": "none",
        "to_status": "draft",
        "actor": {"kind": "buyer", "id": "buyer-01"},
        "payload": {},
        "prev_hash": "0" * 64,
        "hash": "not-a-hash",
    }
    issues = STORE.validate_pointer("urn:c2m:contract:c2m-order", "/$defs/order_event", event)
    ok(any(issue.path == "$.hash" for issue in issues), format_issues(issues))


# -- rule engine ----------------------------------------------------------
@test
def rules_counts_per_industry() -> None:
    eq(len(RULESETS["jewelry"].rules), 17, "jewelry rules")
    eq(len(RULESETS["hardwood"].rules), 15, "hardwood rules")


@test
def rules_lint_is_clean() -> None:
    result = lint_mod.lint_all(STORE, SETTINGS)
    errors = [row for row in result["findings"] if row["severity"] == "error"]
    eq(errors, [], "lint errors")
    ok(result["ok"], "lint ok")


@test
def rules_lint_flags_unknown_fact() -> None:
    data = json.loads(json.dumps(RULESETS["jewelry"].rules[0]))
    data["when"] = {"all": [{"fact": "unobtainium_pct", "op": "gt", "value": 1}]}
    path = TMP / "rules_unknown.json"
    path.write_text(json.dumps(_rule_file([data])), encoding="utf-8")
    result = lint_mod.lint_ruleset(STORE, path)
    ok(any(row["code"] == "UNKNOWN_FACT" for row in result["findings"]), "unknown fact finding")


@test
def rules_lint_flags_duplicate_id() -> None:
    first = json.loads(json.dumps(RULESETS["jewelry"].rules[0]))
    second = json.loads(json.dumps(RULESETS["jewelry"].rules[0]))
    path = TMP / "rules_dup.json"
    path.write_text(json.dumps(_rule_file([first, second])), encoding="utf-8")
    result = lint_mod.lint_ruleset(STORE, path)
    ok(any(row["code"] == "DUP_ID" for row in result["findings"]), "duplicate id finding")


@test
def rules_lint_flags_type_mismatch() -> None:
    data = json.loads(json.dumps(RULESETS["jewelry"].rules[0]))
    data["when"] = {"all": [{"fact": "alloy", "op": "lt", "value": 1}]}
    path = TMP / "rules_type.json"
    path.write_text(json.dumps(_rule_file([data])), encoding="utf-8")
    result = lint_mod.lint_ruleset(STORE, path)
    ok(any(row["code"] == "TYPE_MISMATCH" for row in result["findings"]), "type mismatch finding")


@test
def rules_lint_flags_unknown_placeholder() -> None:
    data = json.loads(json.dumps(RULESETS["jewelry"].rules[0]))
    data["reason"] = {"zh": "壁厚 {not_a_fact}", "en": "wall {not_a_fact}"}
    path = TMP / "rules_placeholder.json"
    path.write_text(json.dumps(_rule_file([data])), encoding="utf-8")
    result = lint_mod.lint_ruleset(STORE, path)
    ok(any(row["code"] == "PLACEHOLDER_UNKNOWN" for row in result["findings"]), "placeholder finding")


@test
def rules_lint_flags_unused_fact() -> None:
    data = json.loads(json.dumps(RULESETS["jewelry"].rules[0]))
    path = TMP / "rules_unused.json"
    payload = _rule_file([data])
    payload["facts_schema"]["mystery_mm"] = {"type": "number", "required": False}
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = lint_mod.lint_ruleset(STORE, path)
    ok(any(row["code"] == "UNUSED_FACT" for row in result["findings"]), "unused fact finding")


@test
def rules_facts_are_all_referenced() -> None:
    for industry, ruleset in RULESETS.items():
        used: set = set()
        for rule in ruleset.rules:
            used |= condition_facts(rule["when"])
            if rule.get("applies_when"):
                used |= condition_facts(rule["applies_when"])
        for workshop_id in SETTINGS.workshop_ids(industry):
            for check in SETTINGS.workshop(workshop_id).get("capability_checks", []):
                used.add(str(check["fact"]))
                applies = check.get("applies_when") or {}
                if isinstance(applies, dict) and applies.get("fact"):
                    used.add(str(applies["fact"]))
        unused = sorted(set(ruleset.facts_schema) - used)
        eq(unused, [], f"{industry} unused facts")


@test
def rules_operator_semantics() -> None:
    facts = {"wall": 0.3, "alloy": "18k_gold", "joints": ["screw"], "flag": True}
    ok(evaluate_condition({"fact": "wall", "op": "lt", "value": 0.5}, facts), "lt")
    ok(not evaluate_condition({"fact": "wall", "op": "gt", "value": 0.5}, facts), "gt")
    ok(evaluate_condition({"fact": "wall", "op": "eq", "value": 0.3}, facts), "eq")
    ok(evaluate_condition({"fact": "alloy", "op": "in", "value": ["18k_gold"]}, facts), "in")
    ok(evaluate_condition({"fact": "alloy", "op": "not_in", "value": ["925_silver"]}, facts), "not_in")
    ok(evaluate_condition({"fact": "joints", "op": "contains_any", "value": ["screw"]}, facts), "contains_any")
    ok(evaluate_condition({"not": {"fact": "flag", "op": "eq", "value": False}}, facts), "not")
    ok(evaluate_condition({"any": [{"fact": "wall", "op": "gt", "value": 9}, {"fact": "flag", "op": "eq", "value": True}]}, facts), "any")
    ok(not evaluate_condition({"fact": "missing_fact", "op": "lt", "value": 1}, facts), "missing fact is false")


@test
def rules_render_i18n_fills_placeholders() -> None:
    rendered = render_i18n({"zh": "壁厚 {wall_mm}", "en": "wall {wall_mm}"}, {"wall_mm": 0.4})
    eq(rendered["en"], "wall 0.4", "en rendering")
    eq(rendered["zh"], "壁厚 0.4", "zh rendering")


@test
def rules_explain_returns_facts_and_fixes() -> None:
    payload = explain(RULESETS["jewelry"], "JW-CAST-001")
    eq(payload["rule_id"], "JW-CAST-001", "rule id")
    ok(payload["facts"] == ["min_wall_thickness_mm"], "facts")
    ok(payload["fixes"], "fixes present")


@test
def rules_evidence_is_flagged_for_client_confirmation() -> None:
    for industry, ruleset in RULESETS.items():
        for rule in ruleset.rules:
            evidence = rule["evidence"]
            eq(evidence["source_type"], "synthetic_baseline", f"{rule['id']} source type")
            ok(evidence["client_confirmation_required"], f"{rule['id']} confirmation flag")


@test
def rules_equipment_lint_flags_unknown_fact() -> None:
    workshop = json.loads(json.dumps(SETTINGS.workshop("WS-JW-A")))
    workshop["capability_checks"][0]["fact"] = "not_a_fact"
    path = TMP / "workshop_bad.json"
    path.write_text(json.dumps(workshop), encoding="utf-8")
    findings = lint_mod.lint_equipment(STORE, path, RULESETS["jewelry"].facts_schema)
    ok(any(row["code"] == "UNKNOWN_FACT" for row in findings), "equipment unknown fact")


@test
def rules_versions_are_semver() -> None:
    import re

    pattern = re.compile(r"^\d+\.\d+\.\d+$")
    for ruleset in RULESETS.values():
        ok(pattern.match(ruleset.version), f"{ruleset.industry} version")
        eq(ruleset.as_of, SETTINGS.as_of, f"{ruleset.industry} as_of")


def _rule_file(rules: list[dict]) -> dict:
    return {
        "industry": "jewelry",
        "version": "1.0.0",
        "as_of": SETTINGS.as_of,
        "facts_schema": json.loads(json.dumps(RULESETS["jewelry"].facts_schema)),
        "rules": rules,
    }


# -- assessment -----------------------------------------------------------
@test
def assess_clean_concept_is_manufacturable() -> None:
    workshop = SETTINGS.workshop("WS-JW-A")
    result = assess(concept("DC-0001"), workshop, RULESETS["jewelry"],
                    assessment_id="MA-9001", created_at=SETTINGS.as_of)
    eq(result["final_verdict"], "manufacturable", "verdict")
    eq(result["blockers"], [], "blockers")


@test
def assess_thin_wall_is_blocked_with_fixes() -> None:
    workshop = SETTINGS.workshop("WS-JW-A")
    result = assess(concept("DC-0002"), workshop, RULESETS["jewelry"],
                    assessment_id="MA-9002", created_at=SETTINGS.as_of)
    eq(result["final_verdict"], "not_manufacturable", "verdict")
    ok("JW-CAST-001" in result["blockers"], "wall blocker")
    ok(len(result["fixes"]) >= 2, "fix suggestions")
    ok(all(fix["text"]["en"] for fix in result["fixes"]), "fixes are bilingual")


@test
def assess_workshop_capability_changes_the_verdict() -> None:
    left = assess(concept("DC-0003"), SETTINGS.workshop("WS-JW-A"), RULESETS["jewelry"],
                  assessment_id="MA-9003", created_at=SETTINGS.as_of)
    right = assess(concept("DC-0003"), SETTINGS.workshop("WS-JW-B"), RULESETS["jewelry"],
                   assessment_id="MA-9004", created_at=SETTINGS.as_of)
    eq(left["final_verdict"], "conditionally_manufacturable", "workshop A")
    eq(right["final_verdict"], "not_manufacturable", "workshop B")
    ok("CAP-JW-B-01" in right["blockers"], "capability blocker")


@test
def assess_enamel_kiln_limit() -> None:
    result = assess(concept("DC-0004"), SETTINGS.workshop("WS-JW-B"), RULESETS["jewelry"],
                    assessment_id="MA-9005", created_at=SETTINGS.as_of)
    ok("CAP-JW-B-06" in result["blockers"], "kiln blocker")


@test
def assess_hardwood_rules_apply() -> None:
    result = assess(concept("DC-0006"), SETTINGS.workshop("WS-HW-A"), RULESETS["hardwood"],
                    assessment_id="MA-9006", created_at=SETTINGS.as_of)
    eq(result["final_verdict"], "not_manufacturable", "verdict")
    for rule_id in ("HW-JOIN-003", "HW-FORM-001"):
        ok(rule_id in result["blockers"], f"{rule_id} blocker")


@test
def assess_outdoor_pine_is_blocked() -> None:
    result = assess(concept("DC-0008"), SETTINGS.workshop("WS-HW-A"), RULESETS["hardwood"],
                    assessment_id="MA-9007", created_at=SETTINGS.as_of)
    ok("HW-SURF-002" in result["blockers"], "outdoor species blocker")
    ok("HW-JOIN-002" in result["blockers"], "screw-only blocker")


@test
def assess_missing_facts_is_not_assessable() -> None:
    payload = concept("DC-0001")
    payload["craft_facts"].pop("stone_size_mm")
    result = assess(payload, SETTINGS.workshop("WS-JW-A"), RULESETS["jewelry"],
                    assessment_id="MA-9008", created_at=SETTINGS.as_of)
    eq(result["final_verdict"], "not_assessable", "verdict")
    ok("stone_size_mm" in result["missing_facts"], "missing fact listed")


@test
def assess_requires_artisan_review_for_flagged_rule() -> None:
    result = assess(concept("DC-0003"), SETTINGS.workshop("WS-JW-A"), RULESETS["jewelry"],
                    assessment_id="MA-9009", created_at=SETTINGS.as_of, queue_id="AR-9001")
    ok(result["artisan"]["required"], "review required")
    eq(result["artisan"]["queue_id"], "AR-9001", "queue id")
    eq(result["artisan"]["status"], "pending", "status")


@test
def assess_record_matches_the_contract() -> None:
    result = assess(concept("DC-0002"), SETTINGS.workshop("WS-JW-A"), RULESETS["jewelry"],
                    assessment_id="MA-9010", created_at=SETTINGS.as_of)
    eq([i.as_dict() for i in STORE.validate("manufacturability_assessment", result)], [], "contract")


@test
def assess_is_reproducible() -> None:
    first = assess(concept("DC-0007"), SETTINGS.workshop("WS-HW-A"), RULESETS["hardwood"],
                   assessment_id="MA-9011", created_at=SETTINGS.as_of)
    second = assess(concept("DC-0007"), SETTINGS.workshop("WS-HW-A"), RULESETS["hardwood"],
                    assessment_id="MA-9011", created_at=SETTINGS.as_of)
    eq(first, second, "same inputs, same record")
    eq(first["reproducibility"]["facts_hash"], second["reproducibility"]["facts_hash"], "facts hash")


@test
def assess_all_twenty_cases_match_expectations() -> None:
    expected = sample("samples/concepts/expected.json")
    mismatches = []
    for concept_id, spec in expected["concepts"].items():
        payload = concept(concept_id)
        for workshop_id, want in spec["workshops"].items():
            result = assess(payload, SETTINGS.workshop(workshop_id), RULESETS[spec["industry"]],
                            assessment_id="MA-9100", created_at=SETTINGS.as_of)
            if result["auto"]["verdict"] != want["verdict"]:
                mismatches.append(f"{concept_id}/{workshop_id}: {result['auto']['verdict']} != {want['verdict']}")
            for rule_id in want["must_fail"]:
                if rule_id not in result["blockers"]:
                    mismatches.append(f"{concept_id}/{workshop_id}: missing blocker {rule_id}")
    eq(mismatches, [], "expectation table")


@test
def assess_counterexamples_have_blockers_and_fixes() -> None:
    for concept_id in sample("samples/concepts/expected.json")["counterexamples"]:
        payload = concept(concept_id)
        workshop = SETTINGS.workshop(SETTINGS.industry(payload["industry"])["default_workshop"])
        result = assess(payload, workshop, RULESETS[payload["industry"]],
                        assessment_id="MA-9101", created_at=SETTINGS.as_of)
        eq(result["final_verdict"], "not_manufacturable", f"{concept_id} verdict")
        ok(result["blockers"], f"{concept_id} blockers")
        ok(result["fixes"], f"{concept_id} fixes")
        ok(all(fix["text"]["zh"] for fix in result["fixes"]), f"{concept_id} bilingual fixes")


@test
def assess_facts_model_rejects_unknown_fact() -> None:
    result = facts_mod.check({"nonsense_mm": 1}, RULESETS["jewelry"].facts_schema)
    ok(not result["ok"], "unknown fact rejected")
    ok(result["errors"], "error message present")


# -- review queue ---------------------------------------------------------
@test
def review_create_is_pending() -> None:
    service = new_service("review_create")
    result = service.assess_at(concept("DC-0003"), "WS-JW-A")
    queue_id = result["artisan"]["queue_id"]
    item = service.reviews.get(queue_id)
    eq(item["status"], "pending", "status")
    eq(item["concept_id"], "DC-0003", "concept")
    eq([i.as_dict() for i in STORE.validate("artisan_review", item)], [], "contract")


@test
def review_confirm_keeps_the_verdict() -> None:
    service = new_service("review_confirm")
    result = service.assess_at(concept("DC-0003"), "WS-JW-A")
    decision = service.decide_review(result["artisan"]["queue_id"], "conditionally_manufacturable", "")
    eq(decision["review"]["status"], "confirmed", "status")
    eq(decision["assessment"]["final_verdict"], "conditionally_manufacturable", "verdict")


@test
def review_override_needs_a_reason() -> None:
    service = new_service("review_override_short")
    result = service.assess_at(concept("DC-0003"), "WS-JW-A")
    try:
        service.decide_review(result["artisan"]["queue_id"], "manufacturable", "ok")
    except ValidationFailed:
        return
    raise AssertionError("a short override reason was accepted")


@test
def review_override_changes_the_verdict() -> None:
    service = new_service("review_override")
    result = service.assess_at(concept("DC-0003"), "WS-JW-A")
    decision = service.decide_review(
        result["artisan"]["queue_id"],
        "manufacturable",
        "The reviewer accepts the hollow casting with an internal support and a post-cast inspection.",
    )
    eq(decision["review"]["status"], "overridden", "status")
    eq(decision["assessment"]["final_verdict"], "manufacturable", "verdict")
    ok(decision["assessment"]["artisan"]["notes"], "notes stored")


@test
def review_confirm_with_different_verdict_is_refused() -> None:
    service = new_service("review_confirm_bad")
    result = service.assess_at(concept("DC-0003"), "WS-JW-A")
    try:
        service.decide_review(result["artisan"]["queue_id"], "manufacturable", "")
    except ValidationFailed:
        return
    raise AssertionError("a silent override was accepted")


@test
def review_cannot_be_decided_twice() -> None:
    service = new_service("review_twice")
    result = service.assess_at(concept("DC-0003"), "WS-JW-A")
    queue_id = result["artisan"]["queue_id"]
    service.decide_review(queue_id, "conditionally_manufacturable", "")
    try:
        service.decide_review(queue_id, "manufacturable", "Second attempt with a long enough reason.")
    except Conflict:
        return
    raise AssertionError("a decided review was decided again")


@test
def review_queue_lists_pending_items() -> None:
    service = new_service("review_queue")
    service.assess_at(concept("DC-0003"), "WS-JW-A")
    service.assess_at(concept("DC-0002"), "WS-JW-B")
    eq(len(service.reviews.pending()), 2, "pending count")


# -- creative -------------------------------------------------------------
@test
def creative_generates_requested_count() -> None:
    service = new_service("creative_count")
    rows = service.generate("a coastal pendant series", "jewelry", count=4)
    eq(len(rows), 4, "count")
    for row in rows:
        eq([i.as_dict() for i in STORE.validate("design_concept", row)], [], row["concept_id"])


@test
def creative_is_deterministic() -> None:
    left = new_service("creative_left").generate("coastal heritage", "jewelry", count=2)
    right = new_service("creative_right").generate("coastal heritage", "jewelry", count=2)
    strip = lambda rows: [{k: v for k, v in row.items() if k != "concept_id"} for row in rows]  # noqa: E731
    eq(strip(left), strip(right), "same brief, same concepts")


@test
def creative_different_brief_differs() -> None:
    service = new_service("creative_diff")
    left = service.generate("coastal heritage", "jewelry", count=2)
    right = service.generate("courtly ornament", "jewelry", count=2)
    ok(left[0]["seed"] != right[0]["seed"], "seeds differ")


@test
def creative_concepts_use_industry_vocabulary() -> None:
    service = new_service("creative_vocab")
    rows = service.generate("carved console", "hardwood", count=2)
    for row in rows:
        ok(row["industry"] == "hardwood", "industry")
        ok(all(motif.startswith("MOT-HW") for motif in row["motif_ids"]), "hardwood motifs")
        ok("species" in row["craft_facts"], "species fact")


@test
def creative_series_expands_three_skus() -> None:
    service = new_service("creative_series")
    concept_row = service.generate("a fret ring", "jewelry", count=1)[0]
    skus = service.expand_series(concept_row["concept_id"])
    eq(len(skus), 3, "sku count")
    eq([sku["series"]["sku_index"] for sku in skus], [1, 2, 3], "sku indexes")
    eq(len({sku["series"]["series_id"] for sku in skus}), 1, "single series id")


@test
def creative_series_scales_dimensions() -> None:
    service = new_service("creative_series_scale")
    concept_row = service.generate("a fret ring", "jewelry", count=1)[0]
    skus = service.expand_series(concept_row["concept_id"])
    small, standard, large = (sku["form"]["dimensions_mm"]["x"] for sku in skus)
    ok(small < standard < large, f"dimensions grow: {small}, {standard}, {large}")


@test
def creative_series_rotates_palette() -> None:
    service = new_service("creative_series_palette")
    concept_row = service.generate("a fret ring", "jewelry", count=1)[0]
    skus = service.expand_series(concept_row["concept_id"])
    ok(skus[0]["palette"] != skus[1]["palette"], "palette rotates")


@test
def creative_reference_palette_maps_to_curated_palette() -> None:
    palettes = SETTINGS.palettes()["palettes"]
    mapped = nearest_palette(palettes, ["#C9A227", "#1F2A44", "#F2EFE9"])
    eq(mapped["palette_id"], "coastal_brass", "nearest palette")


@test
def creative_reference_palette_is_recorded() -> None:
    service = new_service("creative_reference")
    rows = service.generate("a ring", "jewelry", count=1, reference_palette=["#C9A227", "#1F2A44"])
    eq(rows[0]["source"], "reference_image", "source")
    ok(rows[0]["palette"], "palette present")


@test
def creative_rejects_empty_prompt() -> None:
    service = new_service("creative_empty")
    try:
        service.generate("   ", "jewelry", count=1)
    except ValueError:
        return
    raise AssertionError("an empty prompt was accepted")


@test
def creative_request_validation_limits_count() -> None:
    try:
        ConceptRequest(text="x", industry="jewelry", count=99).validate()
    except ValueError:
        return
    raise AssertionError("count above the limit was accepted")


@test
def creative_generator_is_marked_deterministic() -> None:
    service = new_service("creative_flag")
    row = service.generate("a ring", "jewelry", count=1)[0]
    eq(row["generator"]["adapter"], "offline_lexicon", "adapter")
    ok(row["generator"]["deterministic"], "deterministic flag")


# -- library --------------------------------------------------------------
@test
def library_loads_eight_assets() -> None:
    service = new_service("library_load")
    eq(len(service.library.assets), 8, "asset count")


@test
def library_search_by_text() -> None:
    service = new_service("library_text")
    hits = service.library.search(query="interlace")
    ok(hits, "hits present")
    ok(all("interlace" in hit["asset"]["title"]["en"].lower() or "interlace" in hit["asset"]["tags"] for hit in hits), "text match")


@test
def library_search_by_tag() -> None:
    service = new_service("library_tag")
    hits = service.library.search(query="", tags=["coastal"])
    ok(hits, "tag hits")
    ok(all("coastal" in hit["asset"]["tags"] for hit in hits), "tag filter")


@test
def library_search_by_palette() -> None:
    service = new_service("library_palette")
    hits = service.library.search(query="", palette=["#C9A227", "#1F2A44"])
    ok(hits, "palette hits")
    ok(hits[0]["score"] > 0, "palette scoring")


@test
def library_search_by_industry() -> None:
    service = new_service("library_industry")
    hits = service.library.search(query="", industry="hardwood")
    ok(hits, "industry hits")
    ok(all("hardwood" in hit["asset"]["industries"] for hit in hits), "industry filter")


@test
def library_license_state_accepts_active_asset() -> None:
    service = new_service("library_active")
    state = service.library.license_state(service.library.get("PA-JW-0001"), usage="commercial_product")
    ok(state["ok"], str(state))
    ok(state["usage_scope"], "scope listed")


@test
def library_license_state_flags_expired_asset() -> None:
    service = new_service("library_expired")
    state = service.library.license_state(service.library.get("PA-HW-0003"))
    ok(not state["ok"], str(state))
    ok(any("does not cover" in reason for reason in state["reasons"]), state["reasons"])


@test
def library_license_state_flags_missing_usage() -> None:
    service = new_service("library_usage")
    state = service.library.license_state(service.library.get("PA-JW-0003"), usage="advertising")
    ok(not state["ok"], str(state))


@test
def library_ingest_accepts_valid_asset() -> None:
    service = new_service("library_ingest_ok")
    payload = {
        "asset_id": "PA-JW-0801",
        "title": {"zh": "测试纹样", "en": "Test pattern"},
        "industries": ["jewelry"],
        "medium": "pattern",
        "tags": ["test"],
        "palette": ["#C9A227"],
        "preview": {"motif_style": "fret", "texture": "matte", "gradient_angle_deg": 10},
        "license": {
            "source_type": "self_produced",
            "usage_scope": ["internal_demo"],
            "territory": ["CN"],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2030-01-01T00:00:00Z",
            "royalty_rate_bp": 0,
            "attribution_required": False,
            "exclusive": False,
        },
        "traditional_prototype": False,
        "religious_site_names": [],
        "review": {"status": "auto_checked"},
        "created_at": "2026-10-22T00:00:00Z",
    }
    service.ingest_asset(payload)
    eq(len(service.library.assets), 9, "asset appended")
    eq(service.library.get("PA-JW-0801")["asset_id"], "PA-JW-0801", "lookup")


@test
def library_ingest_rejects_missing_source() -> None:
    service = new_service("library_ingest_bad")
    payload = copy.deepcopy(service.library.get("PA-JW-0001"))
    payload["license"].pop("source_type")
    try:
        service.ingest_asset(payload)
    except ContractError as exc:
        ok(any(item["path"] == "$.license" for item in exc.details), str(exc.details))
        return
    raise AssertionError("missing licensing source was accepted")


@test
def library_ingest_rejects_duplicate() -> None:
    service = new_service("library_ingest_dup")
    payload = copy.deepcopy(service.library.get("PA-JW-0001"))
    try:
        service.ingest_asset(payload)
    except Conflict:
        return
    raise AssertionError("duplicate asset was accepted")


@test
def library_ingest_rejects_empty_scope() -> None:
    service = new_service("library_ingest_scope")
    payload = copy.deepcopy(service.library.get("PA-JW-0001"))
    payload["license"]["usage_scope"] = []
    try:
        service.ingest_asset(payload)
    except ContractError as exc:
        ok(any(item.get("invariant") == "INV-LIC-02" for item in exc.details), str(exc.details))
        return
    raise AssertionError("empty usage scope was accepted")


# -- commerce -------------------------------------------------------------
def _new_order(service: Service, concept_id: str = "DC-0001") -> dict:
    order = service.create_order(concept_id)
    service.commerce.transition(order["order_id"], "presale_opened",
                                actor={"kind": "designer", "id": "designer-01"})
    service.commerce.transition(order["order_id"], "payment_received",
                                actor={"kind": "buyer", "id": "buyer-01"})
    return order


@test
def commerce_order_amounts_reconcile() -> None:
    service = new_service("commerce_amounts")
    order = service.create_order("DC-0001")
    amounts = order["amounts"]
    eq(amounts["total_cents"], amounts["subtotal_cents"] + amounts["customization_fee_cents"], "total")
    shares = (
        amounts["designer_share_cents"]
        + amounts["factory_share_cents"]
        + amounts["ip_share_cents"]
        + amounts["platform_fee_cents"]
    )
    eq(shares, amounts["total_cents"], "shares")


@test
def commerce_order_matches_contract() -> None:
    service = new_service("commerce_contract")
    order = service.create_order("DC-0001")
    eq([i.as_dict() for i in STORE.validate("c2m_order", order, ctx={"allowed_statuses": service.commerce.main.states})], [], "contract")


@test
def commerce_illegal_transition_is_refused() -> None:
    service = new_service("commerce_illegal")
    order = service.create_order("DC-0001")
    try:
        service.commerce.transition(order["order_id"], "shipped", actor={"kind": "factory", "id": "workshop-01"})
    except Conflict:
        return
    raise AssertionError("shipped from draft was accepted")


@test
def commerce_happy_path_settles() -> None:
    service = new_service("commerce_happy")
    order = _new_order(service, "DC-0001")
    order_id = order["order_id"]
    for event, actor in (
        ("work_order_issued", "system"),
        ("dispatched", "factory"),
        ("production_started", "factory"),
        ("qc_passed", "artisan"),
        ("shipped", "factory"),
        ("settled", "system"),
    ):
        service.commerce.transition(order_id, event, actor={"kind": actor, "id": actor})
    final = service.order(order_id)
    eq(final["status"], "settled", "status")
    settlement = service.commerce.settlement_for(order_id)
    ok(settlement is not None, "settlement exists")
    eq(settlement["total_cents"], final["amounts"]["total_cents"], "settlement total")


@test
def commerce_ledger_chain_verifies() -> None:
    service = new_service("commerce_ledger")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    result = service.ledger.verify()
    ok(result["ok"], str(result["problems"]))
    eq(result["events"], len(service.ledger.events), "event count")


@test
def commerce_work_order_is_issued_for_manufacturable_concept() -> None:
    service = new_service("commerce_wo")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    work_order = service.commerce.work_orders[service.order(order["order_id"])["items"][0]["work_order_id"]]
    eq(work_order["workshop_id"], "WS-JW-A", "workshop")
    ok(work_order["bom"], "bom")
    ok(work_order["process_steps"], "route")
    ok(work_order["qc_checkpoints"], "qc")
    eq([i.as_dict() for i in STORE.validate("craft_work_order", work_order)], [], "contract")


@test
def commerce_work_order_is_refused_when_rules_change() -> None:
    service = new_service("commerce_blocked")
    order = _new_order(service, "DC-0001")
    # A late measurement or a tightened rule can make an accepted concept unmakeable.
    service.commerce.concepts["DC-0001"]["craft_facts"]["min_wall_thickness_mm"] = 0.3
    try:
        service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    except Conflict as exc:
        ok("not manufacturable" in exc.message, exc.message)
        return
    raise AssertionError("a blocked concept received a work order")


@test
def commerce_qc_failure_then_rework() -> None:
    service = new_service("commerce_qc")
    order = _new_order(service, "DC-0001")
    order_id = order["order_id"]
    for event, actor in (("work_order_issued", "system"), ("dispatched", "factory"), ("production_started", "factory")):
        service.commerce.transition(order_id, event, actor={"kind": actor, "id": actor})
    service.commerce.transition(order_id, "qc_failed", actor={"kind": "artisan", "id": "ART-JW-01"})
    eq(service.order(order_id)["status"], "qc_failed", "failed state")
    service.commerce.transition(order_id, "rework_started", actor={"kind": "factory", "id": "workshop-01"})
    eq(service.order(order_id)["status"], "in_production", "rework state")


@test
def commerce_full_refund_after_payment() -> None:
    service = new_service("commerce_refund")
    order = _new_order(service, "DC-0001")
    order_id = order["order_id"]
    result = service.commerce.request_refund(order_id, "Schedule change")
    eq(result["order"]["refund"]["amount_cents"], result["order"]["amounts"]["total_cents"], "full refund")
    service.commerce.decide_refund(order_id, approve=True)
    service.commerce.execute_refund(order_id)
    eq(service.order(order_id)["status"], "refunded", "status")


@test
def commerce_partial_refund_after_dispatch() -> None:
    service = new_service("commerce_partial")
    order = _new_order(service, "DC-0001")
    order_id = order["order_id"]
    for event, actor in (("work_order_issued", "system"), ("dispatched", "factory")):
        service.commerce.transition(order_id, event, actor={"kind": actor, "id": actor})
    service.commerce.request_refund(order_id, "Colour mismatch")
    refund = service.order(order_id)["refund"]
    eq(refund["amount_cents"], money.apply_rate(service.order(order_id)["amounts"]["total_cents"], 5000), "half refund")


@test
def commerce_refund_rejected_path() -> None:
    service = new_service("commerce_reject")
    order = _new_order(service, "DC-0001")
    service.commerce.request_refund(order["order_id"], "Changed my mind")
    service.commerce.decide_refund(order["order_id"], approve=False)
    eq(service.order(order["order_id"])["refund"]["status"], "rejected", "status")


@test
def commerce_refund_cannot_be_requested_twice() -> None:
    service = new_service("commerce_refund_twice")
    order = _new_order(service, "DC-0001")
    service.commerce.request_refund(order["order_id"], "First")
    try:
        service.commerce.request_refund(order["order_id"], "Second")
    except Conflict:
        return
    raise AssertionError("a second refund request was accepted")


@test
def commerce_dispute_rework_resolution() -> None:
    service = new_service("commerce_dispute_rework")
    order = _new_order(service, "DC-0001")
    order_id = order["order_id"]
    service.commerce.transition(order_id, "work_order_issued", actor={"kind": "system", "id": "system"})
    service.commerce.transition(order_id, "dispatched", actor={"kind": "factory", "id": "workshop-01"})
    service.commerce.open_dispute(order_id, "Surface marks")
    eq(service.order(order_id)["status"], "disputed", "disputed state")
    service.commerce.resolve_dispute(order_id, "rework", "Workshop will refinish and re-inspect.")
    eq(service.order(order_id)["status"], "in_production", "rework state")


@test
def commerce_dispute_refund_resolution() -> None:
    service = new_service("commerce_dispute_refund")
    order = _new_order(service, "DC-0001")
    order_id = order["order_id"]
    service.commerce.open_dispute(order_id, "Never delivered")
    service.commerce.resolve_dispute(order_id, "refund", "Platform refunds the buyer in full.")
    eq(service.order(order_id)["status"], "refunded", "refunded state")
    eq(service.order(order_id)["refund"]["status"], "refunded", "refund sub-state")


@test
def commerce_dispute_split_creates_settlement() -> None:
    service = new_service("commerce_dispute_split")
    order = _new_order(service, "DC-0004")
    order_id = order["order_id"]
    for event, actor in (("work_order_issued", "system"), ("dispatched", "factory")):
        service.commerce.transition(order_id, event, actor={"kind": actor, "id": actor})
    service.commerce.open_dispute(order_id, "Enamel shade differs")
    result = service.commerce.resolve_dispute(order_id, "split", "Half refund, piece retained.")
    eq(service.order(order_id)["status"], "settled", "settled state")
    settlement = result["settlement"]
    ok(settlement is not None, "settlement created")
    total = service.order(order_id)["amounts"]["total_cents"]
    eq(settlement["total_cents"], total - money.apply_rate(total, 5000), "net total")
    eq([i.as_dict() for i in STORE.validate("settlement", settlement)], [], "contract")


@test
def commerce_board_lists_orders() -> None:
    service = new_service("commerce_board")
    _new_order(service, "DC-0001")
    _new_order(service, "DC-0005")
    board = service.commerce.board()
    eq(len(board), 2, "board rows")
    ok(all("order_id" in row and "status" in row for row in board), "columns")


@test
def commerce_available_events_follow_state() -> None:
    service = new_service("commerce_available")
    order = service.create_order("DC-0001")
    events = [row["event"] for row in service.commerce.available_events(order["order_id"])]
    eq(events, ["presale_opened"], "draft events")
    service.commerce.transition(order["order_id"], "presale_opened", actor={"kind": "designer", "id": "designer-01"})
    events = [row["event"] for row in service.commerce.available_events(order["order_id"])]
    eq(events, ["payment_received"], "presale events")


@test
def commerce_events_have_hashes_and_sequences() -> None:
    service = new_service("commerce_events")
    order = _new_order(service, "DC-0001")
    events = service.order_events(order["order_id"])
    eq([event["seq"] for event in events], list(range(1, len(events) + 1)), "sequence")
    for event in events:
        eq(len(event["hash"]), 64, "hash length")
        eq([i.as_dict() for i in STORE.validate_pointer("urn:c2m:contract:c2m-order", "/$defs/order_event", event)], [], "event contract")


# -- settlement -----------------------------------------------------------
@test
def settlement_split_sums_to_total() -> None:
    shares = money.split_amounts(18750, [1500, 6000, 1000, 1500])
    eq(sum(shares), 18750, "sum")


@test
def settlement_largest_remainder_assigns_leftovers() -> None:
    shares = money.split_amounts(10001, [3333, 3333, 3334])
    eq(sum(shares), 10001, "sum")
    ok(len(set(shares)) <= 3, "distributed")


@test
def settlement_rejects_rates_not_summing_to_10000() -> None:
    try:
        money.split_amounts(100, [5000, 4000])
    except ValueError:
        return
    raise AssertionError("rates summing to 9000 were accepted")


@test
def settlement_build_posts_and_reconciles() -> None:
    service = new_service("settlement_build")
    order = _new_order(service, "DC-0001")
    settlement = settlement_mod.build(
        STORE,
        service.order(order["order_id"]),
        SETTINGS.split_policy(),
        settlement_id="ST-9001",
        created_at=SETTINGS.as_of,
    )
    eq(settlement["reconciliation"]["delta_cents"], 0, "delta")
    eq(settlement["remainder_cents"], 0, "remainder for round amounts")
    settlement_mod.post(settlement)
    eq(settlement["status"], "posted", "status")
    eq([i.as_dict() for i in STORE.validate("settlement", settlement)], [], "contract")


@test
def settlement_records_refunds_before_posting() -> None:
    service = new_service("settlement_refund")
    order = _new_order(service, "DC-0001")
    entry = settlement_mod.refund_entry(5000, "partial", "dispatched", SETTINGS.as_of)
    settlement = settlement_mod.build(
        STORE,
        service.order(order["order_id"]),
        SETTINGS.split_policy(),
        settlement_id="ST-9002",
        created_at=SETTINGS.as_of,
        net_total_cents=service.order(order["order_id"])["amounts"]["total_cents"] - 5000,
        refunds=[entry],
    )
    eq(len(settlement["refunds"]), 1, "refund recorded")
    eq(settlement["total_cents"], service.order(order["order_id"])["amounts"]["total_cents"] - 5000, "net")


@test
def settlement_describe_lists_parties() -> None:
    service = new_service("settlement_describe")
    order = _new_order(service, "DC-0001")
    settlement = settlement_mod.build(
        STORE,
        service.order(order["order_id"]),
        SETTINGS.split_policy(),
        settlement_id="ST-9003",
        created_at=SETTINGS.as_of,
    )
    text = settlement_mod.describe(settlement)
    ok("designer" in text and "factory" in text, text)


# -- dispatch -------------------------------------------------------------
@test
def dispatch_cost_estimate_computes_material() -> None:
    service = new_service("dispatch_cost")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    work_order = service.commerce.work_orders[service.order(order["order_id"])["items"][0]["work_order_id"]]
    estimate = dispatch_mod.cost_estimate(work_order)
    ok(estimate["material_cents"] > 0, "material cost")
    ok(estimate["labour_minutes"] > 0, "labour minutes")


@test
def dispatch_work_order_carries_constraints() -> None:
    service = new_service("dispatch_constraints")
    order = _new_order(service, "DC-0004")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    work_order = service.commerce.work_orders[service.order(order["order_id"])["items"][0]["work_order_id"]]
    constraints = work_order["process_steps"][0]["constraints"]
    ok(constraints, "constraints present")
    ok(any("JW-" in item for item in constraints), "rule ids referenced")


@test
def dispatch_promised_delivery_uses_lead_time() -> None:
    service = new_service("dispatch_promise")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    work_order = service.commerce.work_orders[service.order(order["order_id"])["items"][0]["work_order_id"]]
    ok(work_order["promised_delivery_at"] > work_order["created_at"], "promise after creation")


# -- HTTP API -------------------------------------------------------------
HTTP = {}


def http_call(method: str, path: str, body=None):
    import urllib.error
    import urllib.request

    if "base" not in HTTP:
        service = new_service("http")
        server, thread, base = start_in_thread(service)
        HTTP.update({"service": service, "server": server, "thread": thread, "base": base})
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(HTTP["base"] + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@test
def http_health_endpoint() -> None:
    status, payload = http_call("GET", "/api/health")
    eq(status, 200, "status")
    eq(payload["data"]["status"], "ok", "body")


@test
def http_spec_lists_every_route() -> None:
    status, payload = http_call("GET", "/api/spec")
    eq(status, 200, "status")
    eq(len(payload["data"]["routes"]), len(route_table()), "route count")


@test
def http_generate_endpoint() -> None:
    status, payload = http_call(
        "POST", "/api/workstation/generate",
        {"text": "a coastal ring", "industry": "jewelry", "count": 2, "style_id": "coastal_minimal"},
    )
    eq(status, 200, "status")
    eq(len(payload["data"]["concepts"]), 2, "concept count")


@test
def http_assess_endpoint() -> None:
    status, payload = http_call("POST", "/api/assess", {"concept_id": "DC-0001", "workshop_id": "WS-JW-A"})
    eq(status, 200, "status")
    eq(payload["data"]["assessment"]["final_verdict"], "manufacturable", "verdict")


@test
def http_ingest_rejects_invalid_payload_with_422() -> None:
    status, payload = http_call("POST", "/api/library/ingest", {"asset_id": "PA-JW-0999"})
    eq(status, 422, "status")
    eq(payload["error"]["code"], "contract_violation", "code")
    ok(payload["error"]["details"], "details present")


@test
def http_order_flow() -> None:
    status, payload = http_call("POST", "/api/orders", {"concept_id": "DC-0001"})
    eq(status, 200, "create")
    order_id = payload["data"]["order"]["order_id"]
    status, payload = http_call(
        "POST", f"/api/orders/{order_id}/advance",
        {"event": "presale_opened", "actor_kind": "designer", "actor_id": "designer-01"},
    )
    eq(status, 200, "advance")
    eq(payload["data"]["order"]["status"], "presale_open", "status")
    status, payload = http_call("GET", f"/api/orders/{order_id}")
    eq(status, 200, "read")
    ok(len(payload["data"]["events"]) >= 2, "events")


@test
def http_illegal_transition_returns_409() -> None:
    status, payload = http_call(
        "POST", "/api/orders/ORD-0001/advance", {"event": "settled", "actor_kind": "system"}
    )
    eq(status, 409, "status")
    eq(payload["error"]["code"], "conflict", "code")


@test
def http_unknown_route_returns_404() -> None:
    status, payload = http_call("GET", "/api/does-not-exist")
    eq(status, 404, "status")
    eq(payload["error"]["code"], "not_found", "code")


@test
def http_static_index_is_served() -> None:
    import urllib.request

    if "base" not in HTTP:
        http_call("GET", "/api/health")
    with urllib.request.urlopen(HTTP["base"] + "/", timeout=10) as response:
        body = response.read().decode("utf-8")
    ok("C2M craft co-creation prototype" in body, "title")
    for tab in ("workstation", "library", "presale", "dispatch", "contracts"):
        ok(f'data-tab="{tab}"' in body, f"tab {tab}")


@test
def http_ledger_endpoint() -> None:
    status, payload = http_call("GET", "/api/orders/ORD-0001/ledger")
    eq(status, 200, "status")
    ok(payload["data"]["events"], "events")


@test
def http_review_queue_endpoint() -> None:
    status, payload = http_call("GET", "/api/reviews/queue")
    eq(status, 200, "status")
    ok("items" in payload["data"], "items key")


# -- milestone 2: capacity, customisation, editions, royalties, quality ---
def _settle_order(service: Service, concept_id: str = "DC-0001", **kwargs) -> dict:
    order = _new_order(service, concept_id)
    for event, actor in (
        ("work_order_issued", "system"),
        ("dispatched", "factory"),
        ("production_started", "factory"),
        ("qc_passed", "artisan"),
        ("shipped", "factory"),
        ("settled", "system"),
    ):
        service.commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    for key, value in kwargs.items():
        setattr(service.order(order["order_id"]), key, value)
    return service.order(order["order_id"])


@test
def capacity_quote_returns_a_feasible_workshop() -> None:
    service = new_service("cap_quote")
    quote = service.quote("DC-0001")
    eq(quote["workshop_id"], "WS-JW-A", "workshop")
    ok(quote["promised_delivery_at"] > service.settings.as_of, quote["promised_delivery_at"])
    ok(quote["working_minutes"] > 0, "working minutes")


@test
def capacity_quote_refuses_an_unmakeable_concept() -> None:
    service = new_service("cap_blocked")
    try:
        service.quote("DC-0002")
    except Conflict as exc:
        ok("no workshop" in exc.message, exc.message)
        return
    raise AssertionError("a blocked concept received a quote")


@test
def capacity_quote_lists_alternatives() -> None:
    service = new_service("cap_alt")
    quote = service.quote("DC-0005")
    ok(quote["alternatives"], "alternatives present")


@test
def capacity_schedules_validate() -> None:
    service = new_service("cap_sched")
    schedules = service.schedules()
    eq(len(schedules), 4, "schedule count")
    for schedule in schedules:
        eq([i.as_dict() for i in STORE.validate("production_schedule", schedule)], [], schedule["schedule_id"])


@test
def capacity_order_carries_a_promise() -> None:
    service = new_service("cap_promise")
    order = service.create_order("DC-0001")
    promise = order["promise"]
    ok(promise["workshop_id"] in ("WS-JW-A", "WS-JW-B"), promise["workshop_id"])
    ok(promise["promised_delivery_at"] > order["created_at"], promise["promised_delivery_at"])
    ok(promise["slot_id"].startswith("SLOT-"), promise["slot_id"])
    eq([i.as_dict() for i in STORE.validate("c2m_order", order, ctx={"allowed_statuses": ["draft"]})], [], "contract")


@test
def capacity_load_pushes_later_promises_back() -> None:
    service = new_service("cap_load")
    first = service.create_order("DC-0001")["promise"]["promised_delivery_at"]
    for _ in range(8):
        service.create_order("DC-0001")
    later = service.create_order("DC-0001")["promise"]["promised_delivery_at"]
    ok(later >= first, f"{later} < {first}")


@test
def capacity_work_order_uses_the_promised_workshop() -> None:
    service = new_service("cap_wo")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    promise = service.order(order["order_id"])["promise"]
    work_order = service.commerce.work_orders[service.order(order["order_id"])["items"][0]["work_order_id"]]
    eq(work_order["workshop_id"], promise["workshop_id"], "work order workshop")
    eq(work_order["promised_delivery_at"], promise["promised_delivery_at"], "promised date")


@test
def customization_catalog_lists_groups() -> None:
    service = new_service("custom_catalog")
    catalog = service.catalog.describe("jewelry")
    eq(len(catalog["groups"]), 4, "jewelry groups")
    ok(catalog["conflicts"], "conflicts documented")


@test
def customization_resolves_price_deltas() -> None:
    service = new_service("custom_resolve")
    built = service.build_customization(
        "DC-0001",
        [
            {"group_id": "alloy", "option_id": "alloy_22k"},
            {"group_id": "engraving", "option_id": "engraving_light"},
        ],
        register=False,
    )
    choice = built["choice"]
    eq(choice["amounts"]["base_unit_price_cents"], 24000, "base")
    eq(choice["amounts"]["delta_cents"], 2880 + 1200, "delta")
    eq(choice["amounts"]["unit_price_cents"], 24000 + 2880 + 1200, "unit")
    eq(choice["status"], "feasible", "status")


@test
def customization_rejects_unknown_option() -> None:
    service = new_service("custom_unknown")
    try:
        service.build_customization("DC-0001", [{"group_id": "alloy", "option_id": "unobtainium"}], register=False)
    except ValidationFailed:
        return
    raise AssertionError("an unknown option was accepted")


@test
def customization_rejects_conflicting_options() -> None:
    service = new_service("custom_conflict")
    try:
        service.build_customization(
            "DC-0001",
            [
                {"group_id": "finish", "option_id": "finish_mirror"},
                {"group_id": "engraving", "option_id": "engraving_deep"},
            ],
            register=False,
        )
    except ValidationFailed as exc:
        ok("incompatible" in exc.message, exc.message)
        return
    raise AssertionError("a conflicting combination was accepted")


@test
def customization_derives_a_new_concept() -> None:
    service = new_service("custom_derive")
    built = service.build_customization("DC-0001", [{"group_id": "alloy", "option_id": "alloy_22k"}])
    derived = built["derived_concept"]
    eq(derived["derived_from"], "DC-0001", "lineage")
    eq(derived["craft_facts"]["alloy"], "22k_gold", "fact change")
    ok(derived["concept_id"] not in ("DC-0001",), derived["concept_id"])
    eq([i.as_dict() for i in STORE.validate("design_concept", derived)], [], "contract")


@test
def customization_blocks_an_unmakeable_base() -> None:
    service = new_service("custom_infeasible")
    built = service.build_customization("DC-0002", [{"group_id": "alloy", "option_id": "alloy_18k"}], register=False)
    eq(built["choice"]["feasibility"]["ok"], False, "feasible")
    ok(built["error"], "error text")
    ok(built["derived_concept"] is None, "no derived concept registered")


@test
def customization_order_applies_the_choice() -> None:
    service = new_service("custom_order")
    order = service.create_order(
        "DC-0001",
        selections=[{"group_id": "alloy", "option_id": "alloy_22k"}],
        model="participatory_customization",
    )
    item = order["items"][0]
    ok(item["customization_id"], "customization id")
    choice = service.commerce.customizations[item["customization_id"]]
    eq(choice["status"], "applied", "choice status")
    eq(item["concept_id"], choice["result_concept_id"], "derived concept")
    eq(order["amounts"]["subtotal_cents"], choice["amounts"]["unit_price_cents"], "price")


@test
def customization_lead_time_extends_the_promise() -> None:
    service = new_service("custom_lead")
    base = service.create_order("DC-0001")["promise"]["promised_delivery_at"]
    platin = service.create_order(
        "DC-0001", selections=[{"group_id": "alloy", "option_id": "alloy_platinum"}]
    )["promise"]["promised_delivery_at"]
    ok(platin > base, f"{platin} <= {base}")


@test
def edition_create_and_issue() -> None:
    service = new_service("edition_issue")
    edition = service.editions.create(
        concept_id="DC-0001",
        size=5,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A",
        created_at=service.settings.as_of,
    )
    result = service.editions.issue(
        edition["edition_id"],
        number=1,
        order_id="ORD-0001",
        owner={"owner_id": "OWNER-C1", "display_name": "Collector One"},
        at=service.settings.as_of,
    )
    record = result["record"]
    eq(len(record["certificate_hash"]), 64, "certificate hash")
    eq(record["edition_number"], 1, "number")
    eq(result["edition"]["numbering"]["issued"][0]["number"], 1, "issued list")


@test
def edition_cannot_over_issue() -> None:
    service = new_service("edition_over")
    edition = service.editions.create(
        concept_id="DC-0001",
        size=1,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A",
        created_at=service.settings.as_of,
    )
    service.editions.issue(
        edition["edition_id"], number=1, order_id="ORD-0001",
        owner={"owner_id": "OWNER-C1", "display_name": "Collector One"}, at=service.settings.as_of,
    )
    eq(service.editions.edition(edition["edition_id"])["status"], "closed", "closed")
    try:
        service.editions.reserve(edition["edition_id"], "ORD-0002")
    except Conflict:
        return
    raise AssertionError("a closed edition accepted a reservation")


@test
def edition_duplicate_number_is_refused() -> None:
    service = new_service("edition_dup")
    edition = service.editions.create(
        concept_id="DC-0001", size=3,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A", created_at=service.settings.as_of,
    )
    service.editions.issue(
        edition["edition_id"], number=1, order_id="ORD-0001",
        owner={"owner_id": "OWNER-C1", "display_name": "Collector One"}, at=service.settings.as_of,
    )
    try:
        service.editions.issue(
            edition["edition_id"], number=1, order_id="ORD-0002",
            owner={"owner_id": "OWNER-C2", "display_name": "Collector Two"}, at=service.settings.as_of,
        )
    except Conflict:
        return
    raise AssertionError("a duplicate number was issued")


@test
def edition_transfer_updates_the_chain() -> None:
    service = new_service("edition_transfer")
    edition = service.editions.create(
        concept_id="DC-0001", size=2,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A", created_at=service.settings.as_of,
    )
    issued = service.editions.issue(
        edition["edition_id"], number=1, order_id="ORD-0001",
        owner={"owner_id": "OWNER-C1", "display_name": "Collector One"}, at=service.settings.as_of,
    )
    record = service.editions.transfer(
        issued["record"]["record_id"], owner_id="OWNER-C2", display_name="Collector Two",
        at=service.settings.as_of, note="private sale",
    )
    eq(record["owner"]["owner_id"], "OWNER-C2", "owner")
    eq([entry["kind"] for entry in record["provenance"]], ["issue", "transfer"], "chain")
    eq([i.as_dict() for i in STORE.validate("collector_record", record)], [], "contract")
    try:
        service.editions.transfer(
            record["record_id"], owner_id="OWNER-C2", display_name="Collector Two", at=service.settings.as_of
        )
    except ValidationFailed:
        return
    raise AssertionError("a transfer to the same owner was accepted")


@test
def edition_reservation_tracks_available_numbers() -> None:
    service = new_service("edition_reserve")
    edition = service.editions.create(
        concept_id="DC-0001", size=2,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A", created_at=service.settings.as_of,
    )
    first = service.editions.reserve(edition["edition_id"], "ORD-0001")
    second = service.editions.reserve(edition["edition_id"], "ORD-0002")
    eq(first["number"], 1, "first number")
    eq(second["number"], 2, "second number")
    eq(service.editions.available_numbers(edition["edition_id"]), 0, "available")
    service.editions.release(edition["edition_id"], 1)
    eq(service.editions.available_numbers(edition["edition_id"]), 1, "after release")


@test
def edition_order_issues_a_certificate_on_settlement() -> None:
    service = new_service("edition_order")
    edition = service.editions.create(
        concept_id="DC-0001", size=3,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A", created_at=service.settings.as_of,
    )
    order = _new_order(service, "DC-0001")
    # attach the reservation the way create_order does, then settle
    reservation = service.editions.reserve(edition["edition_id"], order["order_id"])
    order["items"][0]["edition_id"] = edition["edition_id"]
    order["items"][0]["edition_number"] = reservation["number"]
    for event, actor in (
        ("work_order_issued", "system"), ("dispatched", "factory"),
        ("production_started", "factory"), ("qc_passed", "artisan"),
        ("shipped", "factory"), ("settled", "system"),
    ):
        service.commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    records = [row for row in service.editions.records.values() if row["edition_id"] == edition["edition_id"]]
    eq(len(records), 1, "collector record")
    eq(records[0]["edition_number"], 1, "issued number")


@test
def royalty_lines_split_the_ip_share() -> None:
    service = new_service("royalty_lines")
    order = _create_licensed_order(service)
    settlement = service.commerce.settlement_for(order["order_id"])
    lines = settlement["royalty_lines"]
    ok(lines, "royalty lines")
    ip_share = sum(
        line["amount_cents"] for line in settlement["payout_lines"] if line["party"] == "ip_licensor"
    )
    eq(sum(line["amount_cents"] for line in lines), ip_share, "sum")
    eq(lines[0]["asset_id"], "PA-JW-0001", "asset")
    eq(lines[0]["rate_bp"], 300, "rate")
    eq([i.as_dict() for i in STORE.validate("settlement", settlement)], [], "contract")


def _create_licensed_order(service: Service) -> dict:
    order = service.create_order("DC-0010", asset_license_ids=["PA-JW-0001"])
    for event, actor in (
        ("presale_opened", "designer"), ("payment_received", "buyer"),
        ("work_order_issued", "system"), ("dispatched", "factory"),
        ("production_started", "factory"), ("qc_passed", "artisan"),
        ("shipped", "factory"), ("settled", "system"),
    ):
        service.commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    return service.order(order["order_id"])


@test
def royalty_refuses_an_expired_licence() -> None:
    service = new_service("royalty_expired")
    try:
        service.create_order("DC-0010", asset_license_ids=["PA-HW-0003"])
    except Conflict as exc:
        ok("cannot be used" in exc.message, exc.message)
        return
    raise AssertionError("an expired licence was accepted on an order")


@test
def quality_record_passes_and_links_to_the_checkpoint() -> None:
    service = new_service("quality_pass")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    record = service.record_qc(
        order["order_id"], "QC-01", verdict="pass", defects=[],
        inspector="ART-JW-01", at=service.settings.as_of,
    )
    eq(record["verdict"], "pass", "verdict")
    ok(record["measurements"], "measurements derived")
    ok(all(row["ok"] for row in record["measurements"]), "measurements within limits")
    eq([i.as_dict() for i in STORE.validate("qc_record", record)], [], "contract")
    work_order = service.commerce.work_orders[service.order(order["order_id"])["items"][0]["work_order_id"]]
    eq(work_order["qc_checkpoints"][0]["status"], "passed", "checkpoint updated")


@test
def quality_failure_needs_a_major_defect() -> None:
    service = new_service("quality_minor")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    try:
        service.record_qc(
            order["order_id"], "QC-02", verdict="fail",
            defects=[{"code": "surface_scratch", "count": 1, "note": "minor scratch"}],
            inspector="ART-JW-01", at=service.settings.as_of,
        )
    except ContractError:
        return
    raise AssertionError("a failure with only a minor defect was stored")


@test
def quality_rejects_unknown_defect_codes() -> None:
    service = new_service("quality_unknown")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    try:
        service.record_qc(
            order["order_id"], "QC-01", verdict="rework",
            defects=[{"code": "not_a_defect", "count": 1, "note": "?"}],
            inspector="ART-JW-01", at=service.settings.as_of,
        )
    except ValidationFailed:
        return
    raise AssertionError("an unknown defect code was accepted")


@test
def quality_failure_and_rework_transitions() -> None:
    service = new_service("quality_flow")
    order = _new_order(service, "DC-0001")
    for event, actor in (("work_order_issued", "system"), ("dispatched", "factory"), ("production_started", "factory")):
        service.commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    service.record_qc(
        order["order_id"], "QC-02", verdict="rework",
        defects=[{"code": "setting_loose", "count": 1, "note": "stone moves 0.1 mm"}],
        inspector="ART-JW-01", at=service.settings.as_of,
    )
    service.commerce.transition(order["order_id"], "qc_failed", actor={"kind": "artisan", "id": "ART-JW-01"})
    eq(service.order(order["order_id"])["status"], "qc_failed", "failed")
    service.commerce.transition(order["order_id"], "rework_started", actor={"kind": "factory", "id": "workshop-01"})
    eq(service.order(order["order_id"])["status"], "in_production", "rework")


@test
def state_persist_is_atomic() -> None:
    service = new_service("state_atomic")
    service.persist()
    temp = Path(str(service.state_path) + ".tmp")
    ok(service.state_path.is_file(), "state file")
    ok(not temp.exists(), "temporary file cleaned up")
    data = json.loads(service.state_path.read_text(encoding="utf-8"))
    ok("counters" in data and "concepts" in data, "state shape")


@test
def state_file_corruption_is_tolerated() -> None:
    service = new_service("state_corrupt")
    service.state_path.write_text("{broken", encoding="utf-8")
    with contextlib.redirect_stderr(io.StringIO()):  # the warning is expected noise
        service.load_state()
    service.persist()
    data = json.loads(service.state_path.read_text(encoding="utf-8"))
    ok("counters" in data, "state rewritten after corruption")


@test
def state_concurrent_persist_stays_valid() -> None:
    service = new_service("state_concurrent")
    failures: list[str] = []

    def writer() -> None:
        try:
            service.persist()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=writer) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    eq(failures, [], "concurrent persists")
    data = json.loads(service.state_path.read_text(encoding="utf-8"))
    ok("counters" in data, "state still parses")


@test
def dispute_can_cite_a_quality_record() -> None:
    service = new_service("dispute_evidence")
    order = _new_order(service, "DC-0001")
    for event, actor in (("work_order_issued", "system"), ("dispatched", "factory")):
        service.commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    record = service.record_qc(
        order["order_id"], "QC-02", verdict="rework",
        defects=[{"code": "finish_defect", "count": 1, "note": "polish marks under the rim"}],
        inspector="ART-JW-01",
    )
    service.commerce.open_dispute(
        order["order_id"], "Finish is not what was approved.", qc_record_ids=[record["qc_id"]]
    )
    updated = service.order(order["order_id"])
    eq(updated["dispute"]["qc_record_ids"], [record["qc_id"]], "evidence")
    eq([i.as_dict() for i in STORE.validate("c2m_order", updated)], [], "contract")
    opened = [e for e in service.order_events(order["order_id"]) if e["type"] == "dispute_opened"]
    eq(opened[-1]["payload"]["qc_record_ids"], [record["qc_id"]], "ledger payload")


@test
def dispute_refuses_an_unknown_quality_record() -> None:
    service = new_service("dispute_unknown_qc")
    order = _new_order(service, "DC-0001")
    service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    try:
        service.commerce.open_dispute(
            order["order_id"], "Not what was agreed.", qc_record_ids=["QCR-9999"]
        )
    except NotFound:
        return
    raise AssertionError("an unknown quality record was accepted as evidence")


@test
def dispute_refuses_evidence_from_another_order() -> None:
    service = new_service("dispute_foreign_qc")
    first = _new_order(service, "DC-0001")
    second = _new_order(service, "DC-0005")
    for order in (first, second):
        service.commerce.transition(order["order_id"], "work_order_issued", actor={"kind": "system", "id": "system"})
    record = service.record_qc(
        first["order_id"], "QC-02", verdict="fail",
        defects=[{"code": "setting_loose", "count": 1, "note": "stone moves"}],
        inspector="ART-JW-01",
    )
    try:
        service.commerce.open_dispute(
            second["order_id"], "Not what was agreed.", qc_record_ids=[record["qc_id"]]
        )
    except ValidationFailed:
        return
    raise AssertionError("a record from another order was accepted")


@test
def dispute_resolution_keeps_the_cited_records() -> None:
    service = new_service("dispute_evidence_kept")
    order = _new_order(service, "DC-0001")
    for event, actor in (("work_order_issued", "system"), ("dispatched", "factory")):
        service.commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    record = service.record_qc(
        order["order_id"], "QC-03", verdict="rework",
        defects=[{"code": "surface_scratch", "count": 2, "note": "scuffs on the reverse"}],
        inspector="ART-JW-01",
    )
    service.commerce.open_dispute(
        order["order_id"], "Scuffed on arrival.", qc_record_ids=[record["qc_id"]]
    )
    service.commerce.resolve_dispute(order["order_id"], "rework", "The workshop re-polishes the surface.")
    updated = service.order(order["order_id"])
    eq(updated["dispute"]["qc_record_ids"], [record["qc_id"]], "evidence kept")
    eq(updated["dispute"]["status"], "resolved_rework", "status")


# -- HTTP API: milestone 2 ------------------------------------------------
@test
def http_customization_catalog_endpoint() -> None:
    status, payload = http_call("GET", "/api/customization/catalog?industry=jewelry")
    eq(status, 200, "status")
    eq(len(payload["data"]["groups"]), 4, "groups")


@test
def http_customization_preview_endpoint() -> None:
    status, payload = http_call(
        "POST", "/api/customization/preview",
        {"concept_id": "DC-0001", "selections": [{"group_id": "alloy", "option_id": "alloy_22k"}]},
    )
    eq(status, 200, "status")
    ok(payload["data"]["choice"]["feasibility"]["ok"], "feasible")


@test
def http_capacity_board_endpoint() -> None:
    status, payload = http_call("GET", "/api/capacity/board")
    eq(status, 200, "status")
    eq(len(payload["data"]["schedules"]), 4, "schedules")


@test
def http_edition_flow() -> None:
    status, payload = http_call(
        "POST", "/api/editions",
        {
            "concept_id": "DC-0001",
            "size": 2,
            "artist": {"artist_id": "ARTIST-77", "name": "Studio 77", "royalty_rate_bp": 500},
        },
    )
    eq(status, 200, "create")
    edition_id = payload["data"]["edition"]["edition_id"]
    status, payload = http_call(
        "POST", f"/api/editions/{edition_id}/issue",
        {"order_id": "ORD-0001", "owner": {"owner_id": "OWNER-H1", "display_name": "Collector H"}},
    )
    eq(status, 200, "issue")
    record_id = payload["data"]["record"]["record_id"]
    status, payload = http_call(
        "POST", f"/api/collectors/{record_id}/transfer",
        {"owner_id": "OWNER-H2", "display_name": "Collector H2", "note": "auction"},
    )
    eq(status, 200, "transfer")
    eq(payload["data"]["record"]["provenance"][-1]["to"], "OWNER-H2", "owner")


@test
def http_quality_endpoint() -> None:
    status, payload = http_call("GET", "/api/quality/records")
    eq(status, 200, "status")
    ok("summary" in payload["data"], "summary")


@test
def docs_ui_wires_the_model_sidecar() -> None:
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    ok("SIDECAR_URL" in app, "sidecar url in the UI")
    ok('data-action="ws-render"' in app, "render button in the UI")
    ok('data-action="ws-copy"' in app and "/generate_text" in app, "text model wired in the UI")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ok("sidecar.py --port 8413" in readme, "README documents the sidecar command")
    ok("generate_text" in readme and "--report" in readme, "README documents the text call and the report")
    index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    ok("refreshModelStatus" in app and 'id="model-status"' in index, "model mode chip wired")
    package = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "c2m_craft").rglob("*.py")
    )
    ok("127.0.0.1:8413" not in package and "SIDECAR_URL" not in package, "the package stays offline")


# -- documentation and requirements --------------------------------------
@test
def docs_api_matches_route_table() -> None:
    text = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    missing = []
    for row in route_table():
        path = row["path"].replace("(?P<rule_id>[A-Za-z0-9_-]+)", "{rule_id}")
        path = path.replace("(?P<asset_id>PA-[A-Z]{2}-[0-9]{4})", "{asset_id}")
        path = path.replace("(?P<concept_id>DC-[0-9]{4})", "{concept_id}")
        path = path.replace("(?P<queue_id>AR-[0-9]{4})", "{queue_id}")
        path = path.replace("(?P<order_id>ORD-[0-9]{4})", "{order_id}")
        path = path.replace("(?P<edition_id>ED-[0-9]{4})", "{edition_id}")
        path = path.replace("(?P<record_id>COL-[0-9]{4})", "{record_id}")
        path = path.replace("(?P<inquiry_id>INQ-[0-9]{4})", "{inquiry_id}")
        path = path.lstrip("^").rstrip("$")
        if path not in text:
            missing.append(path)
    eq(missing, [], "routes missing from docs/api.md")


@test
def docs_readme_lists_commands() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for command in ("python -m c2m_craft demo", "python -m c2m_craft serve",
                    "python tests/test_runner.py", "python verify/run_verification.py",
                    "python -m c2m_craft selftest"):
        ok(command in text, command)


@test
def docs_files_exist() -> None:
    for relative in (
        "README.md",
        "DELIVERY.md",
        "SOLUTION.md",
        "ARCHITECTURE.md",
        "docs/data-contracts.md",
        "docs/api.md",
        "docs/rule-modeling-plan.md",
        "docs/rule-authoring-form.md",
        "docs/requirements.json",
        "docs/requirements-matrix.md",
    ):
        ok((ROOT / relative).is_file(), relative)


@test
def docs_solution_keeps_placeholders() -> None:
    text = (ROOT / "SOLUTION.md").read_text(encoding="utf-8")
    ok("REPO_LINK_HERE" in text, "repo placeholder")
    ok("ZIP_LINK_HERE" in text, "zip placeholder")


@test
def requirements_check_passes() -> None:
    result = requirements_mod.check(ROOT)
    eq(result["problems"], [], "requirement problems")
    ok(result["ok"], "requirements ok")


@test
def requirements_cover_all_acceptance_criteria() -> None:
    data = requirements_mod.load(ROOT)
    ids = {row["id"] for row in data["acceptance"]}
    expected = {f"J{index}" for index in range(11)}
    eq(ids, expected, "acceptance ids")
    referenced = {ac for item in data["items"] for ac in item.get("ac_refs", [])}
    eq(sorted(ids - referenced), [], "unreferenced acceptance criteria")


@test
def requirements_m1_items_are_implemented() -> None:
    result = requirements_mod.check(ROOT)
    eq(result["stats"]["m1_items"], result["stats"]["m1_implemented"], "M1 items implemented")


@test
def acceptance_j3_points_at_the_engine() -> None:
    data = requirements_mod.load(ROOT)
    row = next(item for item in data["acceptance"] if item["id"] == "J3")
    ok("A5.3" in row["m1_items"], "J3 references A5.3")


# -- guarantees -----------------------------------------------------------
@test
def guarantee_no_wall_clock_in_package() -> None:
    from c2m_craft.selftest import run as selftest_run

    service = new_service("guarantee_clock")
    result = selftest_run(service)
    failed = [row for row in result["checks"] if not row["ok"]]
    eq(failed, [], "selftest failures")


@test
def guarantee_no_third_party_imports() -> None:
    stdlib = set(sys.stdlib_module_names)
    offenders = []
    for path in sorted((ROOT / "c2m_craft").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                if top not in stdlib and top != "c2m_craft":
                    offenders.append(f"{path.name}: {name}")
    eq(offenders, [], "third-party imports")


@test
def guarantee_ledger_detects_tampering() -> None:
    service = new_service("guarantee_tamper")
    _new_order(service, "DC-0001")
    service.ledger.events[0]["payload"]["amounts"]["total_cents"] += 1
    result = service.ledger.verify()
    ok(not result["ok"], "tampering detected")
    ok(any("hash mismatch" in problem for problem in result["problems"]), str(result["problems"]))


@test
def guarantee_demo_manifest_is_stable() -> None:
    from c2m_craft import demo

    demo.run(ROOT, quiet=True)
    first = (ROOT / "out" / "hash_manifest.json").read_text(encoding="utf-8")
    demo.run(ROOT, quiet=True)
    second = (ROOT / "out" / "hash_manifest.json").read_text(encoding="utf-8")
    eq(first, second, "manifest stable")


# -- milestone 3: enterprise service layer and growth stack -----------------
M34 = {}


def m34() -> Service:
    if "service" not in M34:
        M34["service"] = Service(ROOT, TMP / "m34", reset=True)
    return M34["service"]


def m34_enterprise() -> EnterpriseRuntime:
    if "enterprise" not in M34:
        registry = ComponentRegistry(STORE, m34().settings)
        plans = Profiles(STORE, m34().settings)
        M34["enterprise"] = EnterpriseRuntime(STORE, m34().settings, registry, plans)
    return M34["enterprise"]


def m34_ip() -> IpPipeline:
    if "ip" not in M34:
        M34["ip"] = IpPipeline(STORE, m34().settings)
    return M34["ip"]


def m34_site(*, audited: bool = True):
    growth = GrowthStack(STORE, m34().settings)
    site = growth.build("SITE-JW-01", at=SETTINGS.as_of)
    return (growth.audit(site, at=SETTINGS.as_of) if audited else site), growth


@test
def m3_contracts_are_registered() -> None:
    for contract_id in (
        "service_component",
        "growth_site",
        "inquiry_lead",
        "character_bible",
        "visual_asset",
        "short_drama",
        "content_review",
        "merch_spec",
    ):
        ok(contract_id in STORE.contract_ids, contract_id)


@test
def m3_invariant_count_grew() -> None:
    eq(len(known_ids()), 25, "invariant count")
    for invariant_id in ("INV-COMP-01", "INV-ENT-01", "INV-SEO-01", "INV-LEAD-01"):
        ok(invariant_id in known_ids(), invariant_id)


@test
def m3_sample_suite_counts() -> None:
    positives = list((ROOT / "samples" / "contracts" / "positive").glob("*.json"))
    expected = sample("samples/contracts/negative/expected.json")["samples"]
    eq(len(positives), 24, "positive samples")
    eq(len(expected), 31, "negative expectations")


@test
def m3_negative_samples_are_rejected() -> None:
    from c2m_craft.demo import contract_for

    expected = sample("samples/contracts/negative/expected.json")["samples"]
    wrong = []
    for filename, expectation in sorted(expected.items()):
        payload = sample(f"samples/contracts/negative/{filename}")
        issues = STORE.validate(expectation["contract"], payload, ctx={"as_of": SETTINGS.as_of})
        if not issues:
            wrong.append(f"{filename}: accepted")
            continue
        matched = any(
            (issue.invariant == expectation.get("invariant") if expectation.get("invariant")
             else issue.keyword == expectation.get("keyword"))
            and issue.path.startswith(expectation["path_prefix"])
            for issue in issues
        )
        if not matched:
            wrong.append(filename)
    eq(wrong, [], "negative classes")
    ok(contract_for("growth-site-SITE-JW-01.json") == "growth_site", "prefix mapping")


@test
def m3_enterprise_registry_loads() -> None:
    registry = ComponentRegistry(STORE, m34().settings)
    eq(len(registry.components), 10, "component count")
    ok("kb_craft" in registry.ids(), "kb_craft")
    eq(registry.kind_counts()["workflow"], 3, "workflow components")


@test
def m3_enterprise_registry_dependencies() -> None:
    registry = ComponentRegistry(STORE, m34().settings)
    closure = registry.dependency_closure("wf_dispatch")
    eq(closure, ["kb_craft", "agent_quote"], "dispatch closure")
    eq(registry.dependency_closure("kb_craft"), [], "root closure")


@test
def m3_enterprise_registry_config_paths_exist() -> None:
    registry = ComponentRegistry(STORE, m34().settings)
    missing = [path for path in registry.config_paths() if not (ROOT / path).exists()]
    eq(missing, [], "config paths")


@test
def m3_enterprise_component_self_dependency_rejected() -> None:
    component = copy.deepcopy(ComponentRegistry(STORE, m34().settings).components[0])
    component["depends_on"] = [component["component_id"]]
    issues = STORE.validate("service_component", component)
    ok(any(issue.invariant == "INV-COMP-01" for issue in issues), format_issues(issues))


@test
def m3_enterprise_profiles_load() -> None:
    plans = Profiles(STORE, m34().settings)
    eq(plans.ids(), ["EP-0001", "EP-0002"], "profile ids")
    eq(len(plans.for_industry("jewelry")), 1, "jewelry profiles")
    eq(len(plans.for_industry("hardwood")), 1, "hardwood profiles")


@test
def m3_enterprise_assemblies_are_ready() -> None:
    runtime = m34_enterprise()
    for profile_id in ("EP-0001", "EP-0002"):
        assembly = runtime.assemble(profile_id)
        eq(assembly["assembly"]["status"], "ready", f"{profile_id} status")
        eq(assembly["assembly"]["issues"], [], f"{profile_id} issues")
        ok(assembly["assembly"]["components_enabled"] >= 8, profile_id)


@test
def m3_enterprise_industry_switch_is_a_config_edit() -> None:
    matrix = m34_enterprise().switch_matrix()
    eq(matrix["industries"], ["hardwood", "jewelry"], "industries")
    eq(len(matrix["rows"]), 2, "rows")
    eq(matrix["proof"]["code_changes_between_industries"], 0, "code changes")
    eq(matrix["proof"]["registry_version"], "1.0.0", "registry version")


@test
def m3_enterprise_switch_shares_capabilities() -> None:
    matrix = m34_enterprise().switch_matrix()
    ok(len(matrix["capabilities_shared"]) >= 15, str(len(matrix["capabilities_shared"])))
    jewelry_specific = matrix["capabilities_industry_specific"]["jewelry"]
    ok("rules.explain" not in jewelry_specific, "shared capability is not listed as specific")


@test
def m3_enterprise_assembly_reports_unknown_component() -> None:
    runtime = m34_enterprise()
    profile = copy.deepcopy(runtime.profiles.get("EP-0001"))
    profile["components"].append(
        {"component_id": "ghost_component", "kind": "workflow", "enabled": True, "config": {}}
    )
    runtime.profiles.records["EP-TEST"] = profile
    try:
        assembly = runtime.assemble("EP-TEST")
        codes = [issue["code"] for issue in assembly["assembly"]["issues"]]
        ok("unknown_component" in codes, str(codes))
    finally:
        runtime.profiles.records.pop("EP-TEST", None)


@test
def m3_enterprise_fde_readiness() -> None:
    readiness = m34_enterprise().fde_readiness("EP-0001")
    eq(readiness["items_total"], 12, "checklist items")
    eq(readiness["readiness_bp"], 7500, "readiness")
    eq(len(readiness["blocking_open"]), 2, "blocking items")
    eq(readiness["status"], "pilot", "status")


@test
def m3_enterprise_report_summary() -> None:
    report = m34_enterprise().report()
    summary = report["summary"]
    eq(summary["components"], 10, "components")
    eq(summary["profiles"], 2, "profiles")
    eq(summary["assemblies_ready"], 2, "ready assemblies")
    eq(len(report["switch"]["rows"]), 2, "switch rows")


@test
def m3_enterprise_describe_shape() -> None:
    data = m34_enterprise().describe()
    eq(len(data["profiles"]), 2, "profiles")
    eq(len(data["registry"]["components"]), 10, "components")
    ok(data["fde"]["readiness_bp"] > 0, "fde readiness")


@test
def growth_site_generates_nine_pages() -> None:
    site, _ = m34_site(audited=False)
    eq(len(site["pages"]), 9, "pages")
    eq(site["languages"], ["en", "zh", "de"], "languages")
    eq(len({page["language"] for page in site["pages"]}), 3, "page languages")


@test
def growth_site_hreflang_is_complete() -> None:
    site, _ = m34_site(audited=False)
    for page in site["pages"]:
        eq(sorted(row["lang"] for row in page["hreflang"]), ["de", "en", "zh"], page["page_id"])


@test
def growth_site_paths_follow_the_language() -> None:
    site, _ = m34_site(audited=False)
    for page in site["pages"]:
        ok(page["path"].startswith("/" + page["language"]), page["path"])
        eq(page["canonical_path"], page["path"], page["page_id"])


@test
def growth_site_audit_is_clean() -> None:
    site, _ = m34_site()
    eq(site["seo"]["audited"], True, "audited")
    eq(site["seo"]["score_bp"], 10000, "score")
    eq(site["seo"]["issues"], [], "issues")
    ok(all(page["status"] == "reviewed" for page in site["pages"]), "reviewed pages")


@test
def growth_site_audit_detects_damage() -> None:
    _, growth = m34_site()
    site = growth.build("SITE-JW-01", at=SETTINGS.as_of)
    damaged = growth.negative_audit(site)
    ok(damaged["seo"]["score_bp"] < 10000, str(damaged["seo"]["score_bp"]))
    codes = [issue["code"] for issue in damaged["seo"]["issues"]]
    ok("description_length" in codes, str(codes))


@test
def growth_site_html_carries_seo_metadata() -> None:
    site, growth = m34_site()
    spec = growth.spec(site["site_id"])
    packs = growth.copy(site["site_id"])
    from c2m_craft.enterprise.growth import site as site_mod

    page = site["pages"][0]
    html = site_mod.page_html(spec, packs, page)
    ok("<title>" in html and 'rel="canonical"' in html, "head")
    ok('hreflang="zh"' in html and 'hreflang="de"' in html, "alternates")
    ok("application/ld+json" in html, "structured data")
    ok("<h1>" in html, "h1")
    ok(page["canonical_path"] in html, "canonical path")


@test
def growth_site_writes_pages_and_crawlers() -> None:
    site, growth = m34_site()
    target = TMP / "site_check"
    files = growth.write(site, target)
    eq(len(files), 11, "written files")
    ok((target / "sitemap.xml").is_file() and (target / "robots.txt").is_file(), "crawlers")
    sitemap = (target / "sitemap.xml").read_text(encoding="utf-8")
    eq(sitemap.count("<url>"), 9, "sitemap urls")
    ok("xhtml:link" in sitemap, "sitemap alternates")


@test
def growth_site_spec_and_copy_are_data() -> None:
    growth = GrowthStack(STORE, m34().settings)
    eq(growth.site_ids(), ["SITE-HW-01", "SITE-JW-01"], "configured sites")
    spec = growth.spec("SITE-JW-01")
    eq(spec["inquiry_form"]["endpoint"], "/api/growth/inquiry", "form endpoint")
    packs = growth.copy("SITE-JW-01")
    eq(sorted(packs), ["de", "en", "zh"], "copy languages")


# -- milestone 3: inquiry to CRM loop ---------------------------------------
def crm_intake(payload=None, *, at: str = "2026-10-23T01:00:00Z") -> dict:
    growth = GrowthStack(STORE, m34().settings)
    growth.crm._inquiry_n = 0
    growth.crm._follow_n = 0
    growth.crm._quote_n = 0
    defaults = {
        "site_id": "SITE-JW-01",
        "language": "en",
        "contact": {
            "name": "Anna Weber",
            "email": "anna.weber@nordlicht-retail.example",
            "company": "Nordlicht Retail (synthetic)",
            "country": "DE",
            "channel": "site_form",
        },
        "message": "We need 500 pcs of the coastal pendant for the winter season.",
        "intent": "bulk_quote",
        "product_interest": ["coastal pendant"],
    }
    if payload:
        defaults.update(payload)
    return growth.crm.intake(defaults, at=at)


@test
def crm_lead_score_is_deterministic() -> None:
    inquiry = crm_intake()
    points = sum(row["points"] for row in inquiry["lead"]["score_breakdown"])
    eq(inquiry["lead"]["score"], max(0, min(100, points)), "score")
    eq(inquiry["lead"]["stage"], "qualified", "stage")


@test
def crm_lead_scoring_matches_policy() -> None:
    inquiry = crm_intake()
    factors = {row["factor"] for row in inquiry["lead"]["score_breakdown"]}
    ok("intent_weight" in factors and "market_focus" in factors, str(factors))
    ok("company_present" in factors and "message_specificity" in factors, str(factors))


@test
def crm_routing_uses_intent() -> None:
    eq(crm_intake()["lead"]["owner"]["owner_id"], "OWNER-EXPORT-01", "bulk route")
    eq(
        crm_intake({"intent": "sample_request"})["lead"]["owner"]["owner_id"],
        "OWNER-STUDIO-01",
        "sample route",
    )
    eq(
        crm_intake({"intent": "information"})["lead"]["owner"]["owner_id"],
        "OWNER-GENERAL-01",
        "general route",
    )


@test
def crm_follow_ups_are_scheduled() -> None:
    inquiry = crm_intake()
    templates = [row["template_id"] for row in inquiry["follow_ups"]]
    ok("quote_follow_up" in templates and "call_back" in templates, str(templates))
    dues = [row["due_at"] for row in inquiry["follow_ups"]]
    eq(dues, sorted(dues), "due order")


@test
def crm_follow_ups_use_the_language() -> None:
    inquiry = crm_intake({"language": "zh", "intent": "sample_request"})
    ok(inquiry["follow_ups"], "follow ups")
    ok(inquiry["language"] == "zh", "language")


@test
def crm_intake_events_are_recorded() -> None:
    inquiry = crm_intake()
    types = [row["type"] for row in inquiry["crm_events"]]
    eq(types, ["received", "scored", "routed"], "events")


@test
def crm_advance_contacted_sets_first_response() -> None:
    inquiry = crm_intake()
    growth = GrowthStack(STORE, m34().settings)
    growth.crm.inquiries[inquiry["inquiry_id"]] = inquiry
    updated = growth.crm.advance(
        inquiry["inquiry_id"], "contacted", at="2026-10-23T03:00:00Z", note="called the buyer and confirmed the range"
    )
    eq(updated["lead"]["stage"], "contacted", "stage")
    eq(updated["lead"]["first_response_at"], "2026-10-23T03:00:00Z", "first response")


@test
def crm_advance_quoted_builds_quote() -> None:
    inquiry = crm_intake()
    growth = GrowthStack(STORE, m34().settings)
    growth.crm.inquiries[inquiry["inquiry_id"]] = inquiry
    growth.crm.advance(inquiry["inquiry_id"], "contacted", at="2026-10-23T03:00:00Z", note="called the buyer and confirmed the range")
    updated = growth.crm.advance(
        inquiry["inquiry_id"], "quoted", at="2026-10-23T04:00:00Z", note="sent the bulk quotation with the delivery window"
    )
    eq(updated["quote"]["amount_cents"], 240000, "quote amount")
    eq(updated["quote"]["incoterm"], "CIF", "incoterm by country")


@test
def crm_advance_won_requires_quote() -> None:
    inquiry = crm_intake()
    growth = GrowthStack(STORE, m34().settings)
    growth.crm.inquiries[inquiry["inquiry_id"]] = inquiry
    with_quote = growth.crm.advance(
        inquiry["inquiry_id"], "lost", at="2026-10-23T04:00:00Z", note="the buyer postponed the season order"
    )
    eq(with_quote["lead"]["stage"], "lost", "lost")


@test
def crm_illegal_transition_is_refused() -> None:
    inquiry = crm_intake()
    growth = GrowthStack(STORE, m34().settings)
    growth.crm.inquiries[inquiry["inquiry_id"]] = inquiry
    try:
        growth.crm.advance(inquiry["inquiry_id"], "won", at="2026-10-23T04:00:00Z", note="jump straight to won without a quote")
    except Conflict:
        return
    raise AssertionError("stage jump was accepted")


@test
def crm_advance_needs_a_note() -> None:
    inquiry = crm_intake()
    growth = GrowthStack(STORE, m34().settings)
    growth.crm.inquiries[inquiry["inquiry_id"]] = inquiry
    try:
        growth.crm.advance(inquiry["inquiry_id"], "contacted", at="2026-10-23T03:00:00Z", note="ok")
    except Conflict:
        return
    raise AssertionError("a short note was accepted")


@test
def crm_board_and_sla() -> None:
    growth = GrowthStack(STORE, m34().settings)
    growth.crm._inquiry_n = 0
    growth.crm._follow_n = 0
    growth.crm._quote_n = 0
    growth.crm.inquiries.clear()
    intake = growth.crm.intake(
        {
            "site_id": "SITE-JW-01",
            "language": "en",
            "contact": {"name": "Test Buyer", "email": "test@example.com", "country": "US", "channel": "site_form"},
            "message": "Looking for the catalogue and the licence summary.",
            "intent": "information",
            "product_interest": ["catalogue"],
        },
        at="2026-10-23T00:00:00Z",
    )
    board = growth.crm.board(now="2026-10-25T00:00:00Z")
    eq(len(board["stages"]), 6, "stages")
    eq(board["sla_breaches"], [intake["inquiry_id"]], "sla breach")
    ok(board["open_follow_ups"], "open follow ups")


@test
def crm_report_summary() -> None:
    growth = GrowthStack(STORE, m34().settings)
    growth.crm._inquiry_n = 0
    growth.crm._follow_n = 0
    growth.crm._quote_n = 0
    growth.crm.inquiries.clear()
    inquiry = crm_intake()
    growth.crm.inquiries[inquiry["inquiry_id"]] = inquiry
    growth.crm.advance(inquiry["inquiry_id"], "contacted", at="2026-10-23T03:00:00Z", note="called the buyer and confirmed the range")
    growth.crm.advance(inquiry["inquiry_id"], "quoted", at="2026-10-23T04:00:00Z", note="sent the bulk quotation with the delivery window")
    report = growth.crm.report(now="2026-10-23T06:00:00Z")
    eq(report["summary"]["inquiries"], 1, "inquiries")
    eq(report["summary"]["quoted"], 1, "quoted")
    eq(report["summary"]["quoted_value_cents"], 240000, "quoted value")
    eq(len(report["trace"]), 1, "trace")


@test
def crm_score_mismatch_is_rejected() -> None:
    inquiry = crm_intake()
    payload = copy.deepcopy(inquiry)
    payload["lead"]["score"] = min(100, payload["lead"]["score"] + 10)
    issues = STORE.validate("inquiry_lead", payload)
    ok(any(issue.invariant == "INV-LEAD-01" for issue in issues), format_issues(issues))


# -- milestone 4: cultural IP pipeline --------------------------------------
@test
def m4_contracts_are_registered() -> None:
    for contract_id in (
        "character_bible",
        "visual_asset",
        "short_drama",
        "content_review",
        "merch_spec",
    ):
        ok(contract_id in STORE.contract_ids, contract_id)
    eq(STORE.entry("ip_license")["version"], "1.1.0", "ip licence version")
    eq(STORE.entry("character_bible")["invariants"], ["INV-CHAR-01"], "character invariant")


@test
def ip_bible_has_two_distinct_guardians() -> None:
    bible = m34_ip().bible
    characters = bible["canon"]["characters"]
    eq(len(characters), 2, "characters")
    eq([row["character_id"] for row in characters], ["CHR-MU", "CHR-HUO"], "ids")
    eq({row["element"] for row in characters}, {"wood", "fire"}, "elements")


@test
def ip_bible_story_arc_and_heritage() -> None:
    bible = m34_ip().bible
    for character in bible["canon"]["characters"]:
        eq(len(character["story_arc"]), 3, character["character_id"])
        ok(len(character["motifs"]) >= 3, "motifs")
    eq([row["exclusive_claimed"] for row in bible["heritage_refs"]], [False, False, False], "heritage")


@test
def ip_assets_cover_the_library_plan() -> None:
    assets = m34_ip().assets
    eq(len(assets), 22, "assets")
    kinds = {asset["kind"] for asset in assets}
    eq(kinds, {"turnaround", "expression", "prop", "costume", "scene"}, "kinds")
    eq(sum(1 for asset in assets if asset["kind"] == "turnaround"), 6, "turnarounds")


@test
def ip_asset_checksums_recompute() -> None:
    for asset in m34_ip().assets:
        eq(visual_asset_checksum(asset), asset["checksum"], asset["asset_id"])


@test
def ip_asset_recipes_are_drawable() -> None:
    for asset in m34_ip().assets:
        for layer in asset["recipe"]["layers"]:
            geometry = layer["geometry"]
            if layer["shape"] == "circle":
                eq(len(geometry), 3, layer["layer_id"])
            elif layer["shape"] == "ellipse":
                eq(len(geometry), 4, layer["layer_id"])
            elif layer["shape"] in ("polygon", "path", "line"):
                eq(len(geometry) % 2, 0, layer["layer_id"])


@test
def ip_assets_are_labelled_and_reviewed() -> None:
    for asset in m34_ip().assets:
        ok(asset["source"]["authenticity_label"], asset["asset_id"])
        ok(asset["source"]["ai_assisted"], asset["asset_id"])
        eq(asset["review"]["status"], "approved", asset["asset_id"])


@test
def ip_asset_checksum_mismatch_is_rejected() -> None:
    asset = copy.deepcopy(m34_ip().asset("VA-MU-TURN-FRONT"))
    asset["recipe"]["layers"][0]["fill"] = "#FFFFFF"
    issues = STORE.validate("visual_asset", asset)
    ok(any(issue.invariant == "INV-ASSET-01" for issue in issues), format_issues(issues))


@test
def ip_drama_durations_agree() -> None:
    drama = m34_ip().drama
    total = 0
    for scene in drama["script"]["scenes"]:
        beats = sum(beat["duration_seconds"] for beat in scene["beats"])
        eq(beats, scene["duration_seconds"], scene["scene_id"])
        total += scene["duration_seconds"]
    eq(total, drama["cut"]["total_seconds"], "total")
    eq(total, 67, "reel length")


@test
def ip_drama_storyboard_matches_the_script() -> None:
    drama = m34_ip().drama
    frames = drama["storyboard"]["frames"]
    eq(len(frames), 10, "frames")
    eq(len(frames), sum(len(scene["beats"]) for scene in drama["script"]["scenes"]), "beat count")
    for frame in frames:
        ok(frame["shot"] in {"wide", "medium", "close", "insert", "pov"}, frame["shot"])
        ok(frame["camera"] in {"static", "pan", "push_in", "handheld", "orbit"}, frame["camera"])


@test
def ip_drama_edl_timecodes_are_continuous() -> None:
    drama = m34_ip().drama
    edl = drama["cut"]["edl"]
    eq(edl[0]["in_tc"], "00:00:00", "starts at zero")
    for index in range(1, len(edl)):
        eq(edl[index]["in_tc"], edl[index - 1]["out_tc"], f"row {index}")
    eq(edl[-1]["out_tc"], "00:01:07", "ends at the cut length")


@test
def ip_drama_subtitles_stay_in_the_cut() -> None:
    drama = m34_ip().drama
    lines = drama["subtitles"]["lines"]
    eq(len(lines), 12, "subtitle lines")
    previous_end = "00:00:00"
    for line in lines:
        ok(line["out_tc"] > line["in_tc"], line["in_tc"])
        ok(line["in_tc"] >= previous_end, "overlap")
        previous_end = line["out_tc"]
    ok(previous_end <= "00:01:07", "inside the cut")


@test
def ip_drama_review_is_approved() -> None:
    drama = m34_ip().drama
    eq(drama["review"]["status"], "approved", "status")
    ok(drama["review"]["content_review_ref"].startswith("CRV-"), "review ref")
    ok(drama["review"]["authenticity_label"], "label")


@test
def ip_licence_document_set() -> None:
    license_record = m34_ip().license
    documents = license_record["documents"]
    eq(len(documents), 5, "documents")
    signed = [row for row in documents if row["status"] == "signed"]
    eq(len(signed), 4, "signed")
    for document in documents:
        eq(len(document["checksum"]), 64, document["document_id"])
        parties = {row["party"] for row in document["signatories"]}
        if document["status"] == "signed":
            ok({"licensor", "licensee"} <= parties, document["document_id"])


@test
def ip_licensing_covers_every_derivative_category() -> None:
    license_record = m34_ip().license
    categories = set(license_record["usage"]["derivative_categories"])
    covered = {
        category
        for document in license_record["documents"]
        if document["status"] == "signed"
        for category in document["derivative_categories"]
    }
    eq(categories - covered, set(), "uncovered categories")
    ok(license_record["usage"]["exclusivity"] is False, "exclusivity")


@test
def ip_licence_document_checksums_recompute() -> None:
    from c2m_craft.core import canonical

    for document in m34_ip().license["documents"]:
        body = {
            field: document[field]
            for field in (
                "document_id",
                "kind",
                "status",
                "derivative_categories",
                "signatories",
                "file_ref",
            )
        }
        eq(canonical.content_hash(body), document["checksum"], document["document_id"])


@test
def ip_merch_specs_cover_four_categories() -> None:
    specs = m34_ip().merch_specs
    eq(len(specs), 4, "specs")
    eq(
        {spec["category"] for spec in specs},
        {"jewelry_pendant", "apparel_collab", "wood_carving_collectible", "cultural_gift"},
        "categories",
    )
    for spec in specs:
        ok(spec["content_review_ref"].startswith("CRV-"), spec["spec_id"])
        labels = " ".join(spec["quality"]["inspection_points"] + spec["packaging"]["label_requirements"]).lower()
        ok("authenticity" in labels, spec["spec_id"])


@test
def ip_merch_spec_labels_are_required() -> None:
    spec = copy.deepcopy(m34_ip().merch_specs[0])
    spec["packaging"]["label_requirements"] = ["licence number"]
    spec["quality"]["inspection_points"] = ["motif depth", "finish match"]
    issues = STORE.validate("merch_spec", spec)
    ok(any(issue.invariant == "INV-MERCH-01" for issue in issues), format_issues(issues))


@test
def ip_content_reviews_cover_every_subject() -> None:
    reviews = m34_ip().reviews
    eq(len(reviews), 9, "reviews")
    verdicts = {review["verdict"] for review in reviews.values()}
    eq(verdicts, {"approved"}, "verdicts")
    for review in reviews.values():
        ok(len(review["checklist"]) >= 5, review["review_id"])
        ok(review["authenticity"]["ai_generated"] and review["authenticity"]["disclosure_required"], "aigc")


@test
def ip_content_review_verdict_is_enforced() -> None:
    review = copy.deepcopy(m34_ip().reviews["CRV-0001"])
    review["checklist"][0]["verdict"] = "fail"
    review["checklist"][0]["note"] = "the heritage sentence over-claims ownership"
    issues = STORE.validate("content_review", review)
    ok(any(issue.invariant == "INV-CONTENT-01" for issue in issues), format_issues(issues))


@test
def ip_reel_is_self_contained() -> None:
    html = m34_ip().reel_html()
    ok(html.count("<svg") == 10, str(html.count("<svg")))
    ok("<title>" in html and "AI-assisted" in html, "head")
    ok("00:00:00" in html and "00:01:07" in html, "timecodes")
    ok("src=\"http" not in html and "href=\"http" not in html, "no external assets")
    ok("<img" not in html, "no binary assets")


@test
def ip_pipeline_report_summary() -> None:
    report = m34_ip().report()
    summary = report["summary"]
    eq(summary["characters"], 2, "characters")
    eq(summary["assets"], 22, "assets")
    eq(summary["frames"], 10, "frames")
    eq(summary["reel_seconds"], 67, "seconds")
    eq(summary["merch_specs"], 4, "specs")
    eq(summary["reviews"], 9, "reviews")


@test
def ip_describe_exposes_assets_and_reviews() -> None:
    data = m34_ip().describe()
    eq(len(data["assets"]), 22, "assets")
    eq(len(data["reviews"]), 9, "reviews")
    eq(data["reel"]["path"], "/reel", "reel path")


# -- milestone 3 and 4 HTTP ------------------------------------------------
@test
def http_enterprise_endpoint() -> None:
    status, payload = http_call("GET", "/api/enterprise")
    eq(status, 200, "status")
    eq(len(payload["data"]["profiles"]), 2, "profiles")
    eq(len(payload["data"]["registry"]["components"]), 10, "components")


@test
def http_enterprise_switch_endpoint() -> None:
    status, payload = http_call("GET", "/api/enterprise/switch")
    eq(status, 200, "status")
    eq(len(payload["data"]["rows"]), 2, "rows")


@test
def http_growth_site_endpoint() -> None:
    status, payload = http_call("GET", "/api/growth/site")
    eq(status, 200, "status")
    eq(len(payload["data"]["site"]["pages"]), 9, "pages")
    eq(payload["data"]["site"]["seo"]["score_bp"], 10000, "score")


@test
def http_inquiry_to_crm_loop() -> None:
    status, payload = http_call(
        "POST",
        "/api/growth/inquiry",
        {
            "language": "en",
            "contact": {
                "name": "Http Buyer",
                "email": "http.buyer@example.com",
                "company": "Http Retail (synthetic)",
                "country": "US",
                "channel": "site_form",
            },
            "message": "We need 120 pcs for the spring season and a sample first.",
            "intent": "bulk_quote",
            "product_interest": ["pendant"],
        },
    )
    eq(status, 200, "intake status")
    inquiry = payload["data"]["inquiry"]
    ok(inquiry["lead"]["score"] > 0, "score")
    status, payload = http_call(
        "POST",
        f"/api/growth/inquiries/{inquiry['inquiry_id']}/advance",
        {"stage": "contacted", "note": "called the buyer and confirmed the assortment"},
    )
    eq(status, 200, "advance status")
    eq(payload["data"]["inquiry"]["lead"]["stage"], "contacted", "stage")
    status, payload = http_call("GET", "/api/growth/crm")
    eq(status, 200, "board status")
    ok(any(row["stage"] == "contacted" for row in payload["data"]["stages"]), "board stages")


@test
def http_ip_endpoint() -> None:
    status, payload = http_call("GET", "/api/ip")
    eq(status, 200, "status")
    eq(len(payload["data"]["assets"]), 22, "assets")
    eq(payload["data"]["drama"]["cut"]["total_seconds"], 67, "seconds")


@test
def http_generated_site_and_reel_are_served() -> None:
    import urllib.request

    if "base" not in HTTP:
        http_call("GET", "/api/health")
    for path, needle in (("/en", "hreflang"), ("/zh/collection", "<h1>"), ("/reel", "<svg"), ("/sitemap.xml", "<urlset")):
        with urllib.request.urlopen(HTTP["base"] + path, timeout=10) as response:
            body = response.read().decode("utf-8")
        eq(response.status, 200, path)
        ok(needle in body, f"{path} body")


def main() -> int:
    failures = []
    for index, func in enumerate(TESTS, start=1):
        try:
            func()
        except Exception as exc:  # noqa: BLE001
            failures.append((index, func.__name__, f"{type(exc).__name__}: {exc}"))
            print(f"[{index:03d}] FAIL {func.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"[{index:03d}] ok   {func.__name__}")
    total = len(TESTS)
    passed = total - len(failures)
    print(f"{passed}/{total} tests passed")
    if HTTP.get("server"):
        HTTP["server"].shutdown()
        HTTP["server"].server_close()
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
