"""Acceptance assertions for milestone M1.

Usage::

    python verify/run_verification.py

The script is deliberately independent of the implementation's own verdicts: it
recomputes hashes, payout sums, ledger links and the assessment expectation table
from the committed artifacts, compares the API documentation with the live route
table, runs the demo twice and compares the manifests byte for byte, and drives
the HTTP server over a real socket on an ephemeral port.

Records written to ``verify/records/``:

    tests_output.txt        raw output of the test run
    verification_output.txt full transcript of this script, group by group
    commands.md             commands, exit codes and expected last lines
    ui_smoke.log            the HTTP walkthrough
    artifact_hashes.txt     the determinism manifest

The last line is always ``N/N assertions passed``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c2m_craft import requirements as requirements_mod  # noqa: E402
from c2m_craft.core.canonical import content_hash  # noqa: E402
from c2m_craft.core.contracts import SchemaStore, format_issues  # noqa: E402
from c2m_craft.core.errors import Conflict, ContractError, ValidationFailed  # noqa: E402
from c2m_craft.core.invariants import known_ids  # noqa: E402
from c2m_craft.craft import lint as lint_mod  # noqa: E402
from c2m_craft.service import Service  # noqa: E402

RECORDS = ROOT / "verify" / "records"
OUT = ROOT / "out"
PY = sys.executable
STORE = SchemaStore(ROOT)
SETTINGS = Service(ROOT, Path(tempfile.mkdtemp(prefix="c2m_verify_boot_")) / "boot", reset=True).settings

TRANSCRIPT: list[str] = []
FAILURES: list[str] = []
COUNTS = {"total": 0, "passed": 0}
GROUP_COUNTS: dict[str, dict] = {}


def group(name: str) -> None:
    GROUP_COUNTS.setdefault(name, {"total": 0, "passed": 0})
    line = f"\n== group {name} =="
    print(line)
    TRANSCRIPT.append(line)


def check(group_name: str, label: str, condition: bool, detail: str = "") -> None:
    COUNTS["total"] += 1
    GROUP_COUNTS.setdefault(group_name, {"total": 0, "passed": 0})
    GROUP_COUNTS[group_name]["total"] += 1
    if condition:
        COUNTS["passed"] += 1
        GROUP_COUNTS[group_name]["passed"] += 1
        line = f"[{group_name}{GROUP_COUNTS[group_name]['total']:02d}] ok   {label}"
    else:
        FAILURES.append(f"{group_name}: {label} {detail}".strip())
        line = f"[{group_name}{GROUP_COUNTS[group_name]['total']:02d}] FAIL {label}  {detail}".rstrip()
    print(line)
    TRANSCRIPT.append(line)


def sample(relative: str) -> dict:
    return SchemaStore.json_load(ROOT / relative)


def concept(concept_id: str) -> dict:
    return sample(f"samples/concepts/{concept_id}.json")


# -- independent helpers --------------------------------------------------
def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def largest_remainder(total: int, rates: list[int]) -> list[int]:
    """Reimplementation of the split rule, deliberately not importing the library."""
    shares = [total * rate // 10000 for rate in rates]
    remainder = total - sum(shares)
    order = sorted(range(len(rates)), key=lambda index: (-(total * rates[index] % 10000), index))
    for index in order[:remainder]:
        shares[index] += 1
    return shares


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_get(base: str, path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(base + path, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def http_post(base: str, path: str, body: dict) -> tuple[int, str]:
    request = urllib.request.Request(
        base + path, data=json.dumps(body).encode("utf-8"), method="POST"
    )
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


# -- A. contracts ---------------------------------------------------------
def group_a() -> None:
    group("A")
    check("A", "twenty-three contracts registered", len(STORE.contract_ids) == 23, str(STORE.contract_ids))
    check("A", "the registry is version 2.0.0 or later", STORE.registry["version"] >= "2.0.0",
          str(STORE.registry["version"]))
    missing = [entry["id"] for entry in STORE.registry["contracts"] if entry["urn"] not in STORE.schemas]
    check("A", "every registry urn is loaded", not missing, str(missing))

    refs: list = []

    def walk(node, key):
        if isinstance(node, dict):
            if "$ref" in node:
                refs.append((key, node["$ref"]))
            for value in node.values():
                walk(value, key)
        elif isinstance(node, list):
            for value in node:
                walk(value, key)

    for key, schema in STORE.schemas.items():
        walk(schema, key)
    broken = []
    for key, ref in refs:
        try:
            STORE.resolve(ref, key)
        except Exception as exc:  # noqa: BLE001
            broken.append(f"{key}->{ref}: {exc}")
    check("A", "all schema references resolve", not broken, "; ".join(broken[:3]))
    check("A", "reference count is substantial", len(refs) >= 50, f"{len(refs)} references")

    positives = 0
    bad_positives = []
    for asset in sample("samples/library/assets.json")["assets"]:
        positives += 1
        issues = STORE.validate("pattern_asset", asset, ctx={"as_of": SETTINGS.as_of})
        if issues:
            bad_positives.append(f"{asset['asset_id']}: {issues[0].message}")
    for path in sorted((ROOT / "samples" / "concepts").glob("DC-*.json")):
        positives += 1
        issues = STORE.validate("design_concept", sample(str(path.relative_to(ROOT))))
        if issues:
            bad_positives.append(f"{path.name}: {issues[0].message}")
    from c2m_craft.demo import contract_for

    for path in sorted((ROOT / "samples" / "contracts" / "positive").glob("*.json")):
        positives += 1
        issues = STORE.validate(contract_for(path.name), sample(str(path.relative_to(ROOT))),
                                ctx={"as_of": SETTINGS.as_of})
        if issues:
            bad_positives.append(f"{path.name}: {issues[0].message}")
    check("A", "all positive samples validate", not bad_positives, "; ".join(bad_positives[:3]))
    check("A", "positive sample count at least 42", positives >= 42, f"{positives}")

    negative_dir = ROOT / "samples" / "contracts" / "negative"
    expected = sample("samples/contracts/negative/expected.json")["samples"]
    rejected = 0
    wrong_class = []
    for filename, expectation in sorted(expected.items()):
        payload = SchemaStore.json_load(negative_dir / filename)
        issues = STORE.validate(expectation["contract"], payload, ctx={"as_of": SETTINGS.as_of})
        if not issues:
            wrong_class.append(f"{filename}: accepted")
            continue
        rejected += 1
        matched = any(
            (issue.invariant == expectation.get("invariant") if expectation.get("invariant")
             else issue.keyword == expectation.get("keyword"))
            and issue.path.startswith(expectation["path_prefix"])
            for issue in issues
        )
        if not matched:
            wrong_class.append(f"{filename}: {format_issues(issues)}")
    check("A", "every negative sample is rejected", rejected == len(expected), f"{rejected}/{len(expected)}")
    check("A", "negative rejection class matches expectation", not wrong_class, "; ".join(wrong_class[:3]))
    check("A", "negative sample count at least 31", len(expected) >= 31, str(len(expected)))

    declared_invariants = {
        item for entry in STORE.registry["contracts"] for item in entry.get("invariants", [])
    }
    check("A", "declared invariants equal implemented ones", sorted(declared_invariants) == sorted(known_ids()),
          f"{sorted(declared_invariants)} vs {sorted(known_ids())}")
    bad_versions = [
        entry["id"] for entry in STORE.registry["contracts"]
        if not re.match(r"^\d+\.\d+\.\d+$", str(entry["version"]))
    ]
    check("A", "contract versions are semantic", not bad_versions, str(bad_versions))
    on_disk = {path.name for path in (ROOT / "contracts").glob("*.schema.json")}
    registered = {entry["file"] for entry in STORE.registry["contracts"]}
    check("A", "registry covers every schema file", on_disk == registered,
          f"extra {sorted(on_disk - registered)} missing {sorted(registered - on_disk)}")

    event = {
        "event_id": "EVT-0001-0001", "order_id": "ORD-0001", "seq": 1,
        "at": "2026-10-23T00:00:00Z", "type": "order_created",
        "from_status": "none", "to_status": "draft",
        "actor": {"kind": "buyer", "id": "buyer-01"}, "payload": {},
        "prev_hash": "0" * 64, "hash": "a" * 64,
    }
    issues = STORE.validate_pointer("urn:c2m:contract:c2m-order", "/$defs/order_event", event)
    check("A", "ledger event definition validates a well formed row", not issues, format_issues(issues))


# -- B. licensing gate ----------------------------------------------------
def group_b() -> None:
    group("B")
    service = Service(ROOT, Path(tempfile.mkdtemp(prefix="c2m_verify_b_")) / "run", reset=True)
    base = sample("samples/library/assets.json")["assets"][0]

    def reject(payload, *, require_active_window: bool = False) -> list:
        try:
            service.ingest_asset(payload)
        except ContractError as exc:
            return exc.details
        except Conflict:
            return [{"code": "duplicate"}]
        return []

    missing_source = json.loads(json.dumps(base))
    missing_source["license"].pop("source_type")
    details = reject(missing_source)
    check("B", "missing licensing source is rejected", bool(details), str(details)[:160])

    empty_scope = json.loads(json.dumps(base))
    empty_scope["license"]["usage_scope"] = []
    details = reject(empty_scope)
    check("B", "empty usage scope is rejected", any(item.get("invariant") == "INV-LIC-02" for item in details),
          str(details)[:160])

    heritage = sample("samples/library/assets.json")["assets"][2]
    exclusive = json.loads(json.dumps(heritage))
    exclusive["license"]["exclusive"] = True
    details = reject(exclusive)
    check("B", "exclusive claim on heritage is rejected",
          any(item.get("invariant") == "INV-LIC-03" for item in details), str(details)[:160])

    inverted = json.loads(json.dumps(base))
    inverted["license"]["valid_from"] = "2029-01-01T00:00:00Z"
    details = reject(inverted)
    check("B", "inverted licence window is rejected",
          any(item.get("invariant") == "INV-LIC-04" for item in details), str(details)[:160])

    issues = STORE.validate("pattern_asset", sample("samples/library/assets.json")["assets"][6],
                            ctx={"as_of": SETTINGS.as_of, "require_active_window": True})
    check("B", "expired licence window is rejected for a transaction",
          any(issue.invariant == "INV-LIC-04" for issue in issues), format_issues(issues)[:160])

    site_exclusive = json.loads(json.dumps(heritage))
    site_exclusive["license"]["exclusive"] = True
    site_exclusive["traditional_prototype"] = False
    site_exclusive["religious_site_names"] = ["Mazu temple (synthetic name)"]
    issues = STORE.validate("pattern_asset", site_exclusive)
    check("B", "religious site exclusivity is rejected",
          any(issue.invariant == "INV-LIC-03" for issue in issues), format_issues(issues)[:160])

    bad_colour = json.loads(json.dumps(base))
    bad_colour["palette"] = ["gold"]
    issues = STORE.validate("pattern_asset", bad_colour)
    check("B", "invalid palette colour is rejected",
          any(issue.keyword == "pattern" and issue.path.startswith("$.palette") for issue in issues),
          format_issues(issues)[:160])

    valid = {
        "asset_id": "PA-JW-0850",
        "title": {"zh": "验证纹样", "en": "Verification pattern"},
        "industries": ["jewelry"],
        "medium": "pattern",
        "tags": ["verify"],
        "palette": ["#C9A227"],
        "preview": {"motif_style": "fret", "texture": "matte", "gradient_angle_deg": 30},
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
    accepted = service.ingest_asset(valid)
    check("B", "a fully licensed asset is accepted", accepted["asset_id"] == "PA-JW-0850", accepted["asset_id"])
    check("B", "the accepted asset appears in the library", len(service.library.assets) == 9,
          str(len(service.library.assets)))
    details = reject(json.loads(json.dumps(valid)))
    check("B", "a duplicate asset is refused", bool(details), str(details)[:160])

    state = service.library.license_state(service.library.get("PA-HW-0003"))
    check("B", "expired asset reports an invalid licence state", not state["ok"], str(state["reasons"])[:160])

    cases = sample("samples/library/rejected.json")["cases"]
    rejected_cases = 0
    for case in cases:
        if reject(case["payload"]):
            rejected_cases += 1
    check("B", "all committed rejection payloads are refused", rejected_cases == len(cases),
          f"{rejected_cases}/{len(cases)}")


# -- C. manufacturability -------------------------------------------------
def group_c() -> None:
    group("C")
    expected = sample("samples/concepts/expected.json")
    from c2m_craft.craft.rules import load_ruleset

    rulesets = {
        industry: load_ruleset(SETTINGS.rules_path(industry))
        for industry in SETTINGS.industry_ids()
    }
    check("C", "jewelry rule count", len(rulesets["jewelry"].rules) >= 14, str(len(rulesets["jewelry"].rules)))
    check("C", "hardwood rule count", len(rulesets["hardwood"].rules) >= 14, str(len(rulesets["hardwood"].rules)))
    total_rules = sum(len(ruleset.rules) for ruleset in rulesets.values())
    check("C", "total rule count", total_rules >= 30, str(total_rules))

    lint_result = lint_mod.lint_all(STORE, SETTINGS)
    check("C", "rule lint passes", lint_result["ok"], str(lint_result["totals"]))
    errors = [row for row in lint_result["findings"] if row["severity"] == "error"]
    check("C", "rule lint has no errors", not errors, str(errors[:2]))
    warns = [row for row in lint_result["findings"] if row["severity"] == "warn"]
    check("C", "rule lint has no warnings", not warns, str(warns[:2]))

    service = Service(ROOT, Path(tempfile.mkdtemp(prefix="c2m_verify_c_")) / "run", reset=True)
    matrix = {}
    mismatches = []
    blocker_misses = []
    contract_failures = []
    for concept_id in sorted(expected["concepts"]):
        spec = expected["concepts"][concept_id]
        payload = concept(concept_id)
        for workshop_id in sorted(spec["workshops"]):
            assessment = service.assess_at(payload, workshop_id, queue_review=False)
            want = spec["workshops"][workshop_id]
            matrix[(concept_id, workshop_id)] = assessment
            if assessment["auto"]["verdict"] != want["verdict"]:
                mismatches.append(f"{concept_id}/{workshop_id}")
            for rule_id in want["must_fail"]:
                if rule_id not in assessment["blockers"]:
                    blocker_misses.append(f"{concept_id}/{workshop_id}:{rule_id}")
            issues = STORE.validate("manufacturability_assessment", assessment)
            if issues:
                contract_failures.append(f"{concept_id}/{workshop_id}: {issues[0].message}")

    check("C", "all twenty verdicts match the hand-written table", not mismatches, str(mismatches))
    check("C", "all expected blocking rules are present", not blocker_misses, str(blocker_misses))
    check("C", "every assessment validates against its contract", not contract_failures, str(contract_failures[:2]))
    check("C", "assessment count is twenty", len(matrix) == 20, str(len(matrix)))

    counterexamples = expected["counterexamples"]
    check("C", "three counterexamples are declared", len(counterexamples) == 3, str(counterexamples))
    no_blockers = [cid for cid in counterexamples
                   if not any(key[0] == cid and value["blockers"] for key, value in matrix.items())]
    check("C", "each counterexample has at least one blocker", not no_blockers, str(no_blockers))
    no_fixes = [cid for cid in counterexamples
                if not all(value["fixes"] for key, value in matrix.items() if key[0] == cid)]
    check("C", "each counterexample has fix suggestions", not no_fixes, str(no_fixes))
    bad_fix = [
        f"{key[0]}/{key[1]}" for key, value in matrix.items()
        if value["blockers"] and not all(fix["suggested_change"] for fix in value["fixes"])
    ]
    check("C", "every fix carries a machine readable change", not bad_fix, str(bad_fix[:3]))
    bilingual = [
        f"{key[0]}/{key[1]}" for key, value in matrix.items()
        if any(not (fix["text"]["zh"] and fix["text"]["en"]) for fix in value["fixes"])
    ]
    check("C", "every fix is bilingual", not bilingual, str(bilingual[:3]))

    plan = (ROOT / "docs" / "rule-modeling-plan.md").read_text(encoding="utf-8")
    undocumented = [rule["id"] for ruleset in rulesets.values() for rule in ruleset.rules
                    if rule["id"] not in plan]
    check("C", "every rule id appears in the shipped rule documentation", not undocumented, str(undocumented[:5]))

    left = matrix[("DC-0003", "WS-JW-A")]
    right = matrix[("DC-0003", "WS-JW-B")]
    check("C", "workshop capability changes the verdict",
          left["auto"]["verdict"] != right["auto"]["verdict"],
          f"{left['auto']['verdict']} vs {right['auto']['verdict']}")
    check("C", "the narrower workshop cites its capability rule",
          any(rule.startswith("CAP-JW-B") for rule in right["blockers"]), str(right["blockers"]))

    wood = matrix[("DC-0009", "WS-HW-A")]
    metal = matrix[("DC-0010", "WS-JW-A")]
    check("C", "the same motif assessed in two industries differs",
          wood["industry"] == "hardwood" and metal["industry"] == "jewelry"
          and wood["auto"]["verdict"] == "manufacturable"
          and metal["auto"]["verdict"] == "conditionally_manufacturable",
          f"{wood['auto']['verdict']} vs {metal['auto']['verdict']}")

    missing_fact = concept("DC-0001")
    missing_fact["craft_facts"].pop("stone_size_mm")
    result = service.assess_at(missing_fact, "WS-JW-A", queue_review=False)
    check("C", "a concept with missing facts is not assessable",
          result["final_verdict"] == "not_assessable" and "stone_size_mm" in result["missing_facts"],
          result["final_verdict"])

    review = service.assess_at(concept("DC-0003"), "WS-JW-A")
    check("C", "flagged failures request a craftsperson", review["artisan"]["required"],
          str(review["artisan"]))
    queue_id = review["artisan"]["queue_id"]
    try:
        service.decide_review(queue_id, "manufacturable", "short")
        short_reason_refused = False
    except ValidationFailed:
        short_reason_refused = True
    check("C", "an override with a short reason is refused", short_reason_refused)
    decided = service.decide_review(
        queue_id, "manufacturable",
        "The reviewer accepts the hollow casting with an internal support and a post-cast inspection.",
    )
    check("C", "an override with a reason is recorded",
          decided["review"]["status"] == "overridden", decided["review"]["status"])
    check("C", "the override changes the effective verdict",
          decided["assessment"]["final_verdict"] == "manufacturable",
          decided["assessment"]["final_verdict"])

    confirmation = service.assess_at(concept("DC-0002"), "WS-JW-A")
    confirmed = service.decide_review(confirmation["artisan"]["queue_id"], "not_manufacturable", "")
    check("C", "a confirmation keeps the verdict",
          confirmed["review"]["status"] == "confirmed"
          and confirmed["assessment"]["final_verdict"] == "not_manufacturable",
          confirmed["review"]["status"])


# -- D. order pipeline ----------------------------------------------------
def group_d() -> None:
    group("D")
    service = Service(ROOT, Path(tempfile.mkdtemp(prefix="c2m_verify_d_")) / "run", reset=True)
    commerce = service.commerce

    order = service.create_order("DC-0001")
    amounts = order["amounts"]
    check("D", "order total equals subtotal plus customisation fee",
          amounts["total_cents"] == amounts["subtotal_cents"] + amounts["customization_fee_cents"],
          str(amounts))
    shares = (amounts["designer_share_cents"] + amounts["factory_share_cents"]
              + amounts["ip_share_cents"] + amounts["platform_fee_cents"])
    check("D", "revenue shares sum to the total", shares == amounts["total_cents"], f"{shares} vs {amounts['total_cents']}")
    check("D", "deposit follows the configured rate",
          amounts["deposit_cents"] == amounts["total_cents"] * 3000 // 10000,
          str(amounts["deposit_cents"]))
    issues = STORE.validate("c2m_order", order, ctx={"allowed_statuses": commerce.main.states})
    check("D", "a new order validates against its contract", not issues, format_issues(issues)[:160])

    try:
        commerce.transition(order["order_id"], "settled", actor={"kind": "system", "id": "system"})
        refused = False
    except Conflict:
        refused = True
    check("D", "an illegal transition is refused", refused)

    steps = [
        ("presale_opened", "designer"),
        ("payment_received", "buyer"),
        ("work_order_issued", "system"),
        ("dispatched", "factory"),
        ("production_started", "factory"),
        ("qc_passed", "artisan"),
        ("shipped", "factory"),
        ("settled", "system"),
    ]
    for event, actor in steps:
        commerce.transition(order["order_id"], event, actor={"kind": actor, "id": actor})
    settled = service.order(order["order_id"])
    check("D", "the happy path reaches settlement", settled["status"] == "settled", settled["status"])
    settlement = commerce.settlement_for(order["order_id"])
    check("D", "a settlement exists for the settled order", settlement is not None, "missing")
    check("D", "settlement payouts sum to the settled total",
          sum(line["amount_cents"] for line in settlement["payout_lines"]) == settlement["total_cents"],
          str(settlement["total_cents"]))
    check("D", "settlement rates sum to 10000 basis points",
          sum(line["rate_bp"] for line in settlement["payout_lines"]) == 10000,
          str([line["rate_bp"] for line in settlement["payout_lines"]]))
    check("D", "settlement reconciliation delta is zero",
          settlement["reconciliation"]["delta_cents"] == 0, str(settlement["reconciliation"]))
    independent = largest_remainder(
        settled["amounts"]["total_cents"],
        [line["rate_bp"] for line in settlement["split_policy"]["lines"]],
    )
    check("D", "payout amounts match an independent recomputation",
          sorted(independent) == sorted(line["amount_cents"] for line in settlement["payout_lines"]),
          f"{independent} vs {[line['amount_cents'] for line in settlement['payout_lines']]}")

    work_order_id = settled["items"][0]["work_order_id"]
    work_order = commerce.work_orders[work_order_id]
    check("D", "a work order was issued", bool(work_order["work_order_id"]), work_order_id)
    check("D", "the work order has a bill of materials", bool(work_order["bom"]), str(len(work_order["bom"])))
    check("D", "the work order has a process route", len(work_order["process_steps"]) >= 3,
          str(len(work_order["process_steps"])))
    check("D", "the work order has quality checkpoints", bool(work_order["qc_checkpoints"]),
          str(len(work_order["qc_checkpoints"])))
    check("D", "the promised delivery is after creation",
          work_order["promised_delivery_at"] > work_order["created_at"],
          f"{work_order['created_at']} -> {work_order['promised_delivery_at']}")
    check("D", "the work order validates against its contract",
          not STORE.validate("craft_work_order", work_order), "invalid")

    ledger = service.ledger.verify()
    check("D", "the ledger chain verifies", ledger["ok"], str(ledger["problems"][:2]))
    check("D", "the settled order has nine ledger events",
          len(service.order_events(order["order_id"])) == 9,
          str(len(service.order_events(order["order_id"]))))

    blocked = service.create_order("DC-0001")
    original = service.concept("DC-0001")
    broken = json.loads(json.dumps(original))
    broken["craft_facts"]["min_wall_thickness_mm"] = 0.3
    service.concepts["DC-0001"] = broken
    service.commerce.concepts["DC-0001"] = broken
    try:
        service.commerce.transition(blocked["order_id"], "presale_opened",
                                    actor={"kind": "designer", "id": "designer-01"})
        service.commerce.transition(blocked["order_id"], "payment_received",
                                    actor={"kind": "buyer", "id": "buyer-01"})
        service.commerce.transition(blocked["order_id"], "work_order_issued",
                                    actor={"kind": "system", "id": "system"})
        refused = False
    except Conflict:
        refused = True
    check("D", "a concept that fails the rules cannot receive a work order", refused)
    try:
        service.create_order("DC-0002")
        blocked_at_creation = False
    except Conflict:
        blocked_at_creation = True
    check("D", "a non-manufacturable concept cannot even be quoted", blocked_at_creation)
    service.concepts["DC-0001"] = original
    service.commerce.concepts["DC-0001"] = original

    qc_order = service.create_order("DC-0005")
    for event, actor in (("presale_opened", "designer"), ("payment_received", "buyer"),
                         ("work_order_issued", "system"), ("dispatched", "factory"),
                         ("production_started", "factory")):
        commerce.transition(qc_order["order_id"], event, actor={"kind": actor, "id": actor})
    commerce.transition(qc_order["order_id"], "qc_failed", actor={"kind": "artisan", "id": "ART-HW-01"})
    check("D", "a quality failure returns the order to qc_failed",
          service.order(qc_order["order_id"])["status"] == "qc_failed",
          service.order(qc_order["order_id"])["status"])
    commerce.transition(qc_order["order_id"], "rework_started", actor={"kind": "factory", "id": "workshop-01"})
    check("D", "rework moves the order back into production",
          service.order(qc_order["order_id"])["status"] == "in_production",
          service.order(qc_order["order_id"])["status"])

    refund_order = service.create_order("DC-0001")
    for event, actor in (("presale_opened", "designer"), ("payment_received", "buyer")):
        commerce.transition(refund_order["order_id"], event, actor={"kind": actor, "id": actor})
    commerce.request_refund(refund_order["order_id"], "The commission moved to another quarter.")
    check("D", "a refund after payment is for the full amount",
          service.order(refund_order["order_id"])["refund"]["amount_cents"]
          == service.order(refund_order["order_id"])["amounts"]["total_cents"],
          str(service.order(refund_order["order_id"])["refund"]))
    commerce.decide_refund(refund_order["order_id"], approve=True)
    commerce.execute_refund(refund_order["order_id"])
    check("D", "an executed refund closes the order as refunded",
          service.order(refund_order["order_id"])["status"] == "refunded",
          service.order(refund_order["order_id"])["status"])

    partial_order = service.create_order("DC-0001")
    for event, actor in (("presale_opened", "designer"), ("payment_received", "buyer"),
                         ("work_order_issued", "system"), ("dispatched", "factory")):
        commerce.transition(partial_order["order_id"], event, actor={"kind": actor, "id": actor})
    commerce.request_refund(partial_order["order_id"], "Colour is two shades off.")
    expected_partial = service.order(partial_order["order_id"])["amounts"]["total_cents"] * 5000 // 10000
    check("D", "a refund after dispatch is capped at half",
          service.order(partial_order["order_id"])["refund"]["amount_cents"] == expected_partial,
          str(service.order(partial_order["order_id"])["refund"]["amount_cents"]))

    dispute_order = service.create_order("DC-0004")
    for event, actor in (("presale_opened", "designer"), ("payment_received", "buyer"),
                         ("work_order_issued", "system"), ("dispatched", "factory")):
        commerce.transition(dispute_order["order_id"], event, actor={"kind": actor, "id": actor})
    commerce.open_dispute(dispute_order["order_id"], "Enamel shade differs from the approved sample.")
    check("D", "a dispute puts the order on hold",
          service.order(dispute_order["order_id"])["status"] == "disputed",
          service.order(dispute_order["order_id"])["status"])
    result = commerce.resolve_dispute(dispute_order["order_id"], "split",
                                      "Buyer keeps the piece at half price.")
    check("D", "a split dispute settles the order",
          service.order(dispute_order["order_id"])["status"] == "settled",
          service.order(dispute_order["order_id"])["status"])
    net = service.order(dispute_order["order_id"])["amounts"]["total_cents"] * 5000 // 10000
    check("D", "the split settlement only pays out the net amount",
          result["settlement"]["total_cents"] == net, f"{result['settlement']['total_cents']} vs {net}")
    check("D", "the split settlement records the refund",
          bool(result["settlement"]["refunds"]), "no refund row")

    board = commerce.board()
    check("D", "the dispatch board lists every order", len(board) == len(commerce.orders), str(len(board)))
    trace = [json.loads(line) for line in
             (OUT / "order_trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    check("D", "the committed order trace has ledger events", len(trace) >= 20, str(len(trace)))
    check("D", "the committed order trace covers three order ids",
          len({row["order_id"] for row in trace}) >= 3, str({row["order_id"] for row in trace}))


# -- E. tests -------------------------------------------------------------
def group_e(tests_output: str, tests_code: int) -> None:
    group("E")
    lines = [line for line in tests_output.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    match = re.search(r"(\d+)/(\d+) tests passed", last)
    check("E", "the test command exits zero", tests_code == 0, f"exit {tests_code}")
    check("E", "the test run prints a summary line", match is not None, last[:120])
    if match:
        passed, total = int(match.group(1)), int(match.group(2))
        check("E", "all tests pass", passed == total, f"{passed}/{total}")
        check("E", "the suite has at least one hundred tests", total >= 100, str(total))
    else:
        check("E", "all tests pass", False, "no summary")
        check("E", "the suite has at least one hundred tests", False, "no summary")
    names = "\n".join(line.split("ok")[-1] for line in lines if " ok " in line)
    check("E", "licensing validation is tested", "licens" in names or "library" in names, "")
    check("E", "manufacturability is tested", "assess" in names or "rules_" in names, "")
    check("E", "the order state machine is tested", "commerce_" in names, "")
    check("E", "revenue sharing is tested", "settlement_" in names, "")
    check("E", "the HTTP layer is tested", "http_" in names, "")


# -- F. documentation -----------------------------------------------------
def group_f() -> None:
    group("F")
    from c2m_craft.web.server import route_table

    api_doc = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    documented = []
    for row in route_table():
        path = row["path"]
        for pattern, replacement in (
            (r"\(\?P<rule_id>\[A-Za-z0-9_-\]\+\)", "{rule_id}"),
            (r"\(\?P<asset_id>PA-\[A-Z\]\{2\}-\[0-9\]\{4\}\)", "{asset_id}"),
            (r"\(\?P<concept_id>DC-\[0-9\]\{4\}\)", "{concept_id}"),
            (r"\(\?P<queue_id>AR-\[0-9\]\{4\}\)", "{queue_id}"),
            (r"\(\?P<order_id>ORD-\[0-9\]\{4\}\)", "{order_id}"),
            (r"\(\?P<edition_id>ED-\[0-9\]\{4\}\)", "{edition_id}"),
            (r"\(\?P<record_id>COL-\[0-9\]\{4\}\)", "{record_id}"),
            (r"\(\?P<inquiry_id>INQ-\[0-9\]\{4\}\)", "{inquiry_id}"),
        ):
            path = re.sub(pattern, replacement, path)
        path = path.lstrip("^").rstrip("$")
        documented.append((row["method"], path))
    missing = [f"{method} {path}" for method, path in documented if path not in api_doc]
    check("F", "every route appears in docs/api.md", not missing, str(missing[:4]))
    check("F", "the documented route count matches the live table",
          api_doc.count("| `/api/") >= len(route_table()), f"{api_doc.count('| `/api/')} vs {len(route_table())}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required_commands = [
        "python -m c2m_craft demo",
        "python -m c2m_craft serve",
        "python tests/test_runner.py",
        "python verify/run_verification.py",
        "python -m c2m_craft selftest",
    ]
    missing_commands = [command for command in required_commands if command not in readme]
    check("F", "the README lists the five entry commands", not missing_commands, str(missing_commands))

    from c2m_craft.cli import build_parser

    parser = build_parser()
    subcommands = set()
    for action in parser._actions:  # noqa: SLF001 - argparse exposes choices here
        if hasattr(action, "choices") and isinstance(getattr(action, "choices"), dict):
            subcommands |= set(action.choices)
    mentioned = set(re.findall(r"python -m c2m_craft ([a-z]+)", readme))
    unknown = sorted(mentioned - subcommands)
    check("F", "every command named in the README exists", not unknown, str(unknown))
    check("F", "the README documents at least ten commands", len(mentioned) >= 10, str(len(mentioned)))

    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    check("F", "the UI wires the optional model sidecar",
          "SIDECAR_URL" in app_js and 'data-action="ws-render"' in app_js, "")
    check("F", "the UI wires the text model",
          'data-action="ws-copy"' in app_js and "/generate_text" in app_js, "")
    check("F", "the README documents the model call record",
          "generate_text" in readme and "--report" in readme, "")
    index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    check("F", "the UI shows the model mode chip",
          "refreshModelStatus" in app_js and 'id="model-status"' in index_html, "")
    check("F", "the README documents the sidecar commands",
          "sidecar.py --port 8413" in readme and "selftest.py" in readme, "")
    package_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "c2m_craft").rglob("*.py")
    )
    check("F", "no sidecar address leaks into the offline package",
          "127.0.0.1:8413" not in package_text, "")
    check("F", "the UI wires the enterprise tab",
          'data-tab="enterprise"' in index_html and "refreshEnterprise" in app_js, "")
    check("F", "the UI wires the IP studio tab",
          'data-tab="ipstudio"' in index_html and "refreshIp" in app_js, "")
    check("F", "the UI draws visual assets from their recipes", "assetSvg" in app_js, "")
    check("F", "the UI renders the CRM pipeline", "crm-advance" in app_js and "refreshCrm" in app_js, "")
    readme_m3 = "Milestone 3: enterprise service layer" in readme and "Milestone 4: cultural IP pipeline" in readme
    check("F", "the README documents milestones 3 and 4", readme_m3, "")
    check("F", "the README lists the M3/M4 sample generator",
          "scripts/gen_m3_m4_samples.py" in readme, "")

    solution = (ROOT / "SOLUTION.md").read_text(encoding="utf-8")
    check("F", "the solution keeps the repository placeholder", "REPO_LINK_HERE" in solution)
    check("F", "the solution keeps the archive placeholder", "ZIP_LINK_HERE" in solution)
    injected = solution.replace(
        "REPO_LINK_HERE",
        "- 交付物仓库（含可浏览源码树 source/ 与打包文件）：https://github.com/Code-play/clawhunt-1724-c2m-craft-ai",
    ).replace(
        "ZIP_LINK_HERE",
        "- 打包下载（zip）：https://github.com/Code-play/clawhunt-1724-c2m-craft-ai/raw/main/1724-c2m-craft-ai.zip",
    )
    check("F", "the injected solution stays under the 10000 character limit", len(injected) <= 10000, str(len(injected)))
    check("F", "the injected solution is substantial", len(injected) >= 8000, str(len(injected)))

    delivery = (ROOT / "DELIVERY.md").read_text(encoding="utf-8")
    missing_ac = [f"J{index}" for index in range(11) if f"| {index} |" not in delivery and f"J{index}" not in delivery]
    check("F", "the delivery note covers every acceptance criterion", not missing_ac, str(missing_ac))

    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    missing_modules = [name for name in ("core", "craft", "creative", "library", "commerce", "web")
                       if f"{name}/" not in architecture]
    check("F", "the architecture note maps every module", not missing_modules, str(missing_modules))

    for relative in ("README.md", "DELIVERY.md", "SOLUTION.md", "ARCHITECTURE.md",
                     "docs/data-contracts.md", "docs/rule-modeling-plan.md",
                     "docs/rule-authoring-form.md", "docs/requirements-matrix.md",
                     "docs/requirements-matrix.zh.md", "docs/fde-handbook.md",
                     "docs/growth-playbook.md", "docs/character-bible.md",
                     "docs/short-drama-workflow.md", "docs/licensing-templates.md",
                     "docs/competition-ops-pack.md"):
        check("F", f"documentation exists: {relative}", (ROOT / relative).is_file(), relative)


# -- G. compliance and determinism ---------------------------------------
def group_g(first_manifest: dict, second_manifest: dict, demo_ok: bool) -> None:
    group("G")
    check("G", "the demo command exits zero", demo_ok, "non-zero exit")
    check("G", "two demo runs produce the same manifest", first_manifest == second_manifest,
          "manifests differ")
    files = first_manifest.get("files", {})
    check("G", "the manifest lists thirty-two artifacts plus itself", len(files) == 32, str(len(files)))
    mismatched = [name for name, digest in files.items()
                  if sha_file(OUT / name) != digest]
    check("G", "every manifest hash matches the committed artifact", not mismatched, str(mismatched[:3]))

    artifacts = sorted(path.name for path in OUT.glob("*") if path.is_file())
    check("G", "the output directory holds twenty-two artifacts", len(artifacts) == 22, str(artifacts))
    site_files = sorted(path.relative_to(OUT).as_posix() for path in (OUT / "site").rglob("*") if path.is_file())
    check("G", "the generated site holds nine pages and two crawler files", len(site_files) == 11, str(len(site_files)))
    check("G", "the generated pages cover three languages",
          all(f"site/{language}/index.html" in site_files for language in ("en", "zh", "de")), str(site_files[:3]))
    bad_json = []
    for name in artifacts:
        if name.endswith(".json"):
            try:
                json.loads((OUT / name).read_text(encoding="utf-8"))
            except ValueError:
                bad_json.append(name)
    check("G", "every generated JSON artifact parses", not bad_json, str(bad_json))

    trace = [json.loads(line) for line in
             (OUT / "order_trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    broken = []
    previous = "0" * 64
    per_order: dict[str, int] = {}
    for index, row in enumerate(trace):
        body = {key: row[key] for key in (
            "event_id", "order_id", "seq", "at", "type", "from_status", "to_status",
            "actor", "payload", "prev_hash",
        )}
        if sha(canonical(body)) != row["hash"]:
            broken.append(f"row {index}: hash")
        if row["prev_hash"] != previous:
            broken.append(f"row {index}: link")
        per_order[row["order_id"]] = per_order.get(row["order_id"], 0) + 1
        if row["seq"] != per_order[row["order_id"]]:
            broken.append(f"row {index}: seq")
        previous = row["hash"]
    check("G", "the committed ledger verifies independently", not broken, str(broken[:3]))

    settled = [row for row in trace if row["type"] == "settled"]
    check("G", "the trace contains settled events", bool(settled), str(len(settled)))
    payout_problems = []
    for row in settled:
        payouts = row["payload"].get("payouts")
        if not payouts:
            payout_problems.append(f"{row['event_id']}: no payout snapshot")
            continue
        if sum(payouts) != row["payload"].get("settled_cents"):
            payout_problems.append(f"{row['event_id']}: {sum(payouts)} != {row['payload'].get('settled_cents')}")
    check("G", "settled events carry payouts that sum to the settled amount", not payout_problems,
          str(payout_problems[:3]))

    report = json.loads((OUT / "assessment_results.json").read_text(encoding="utf-8"))
    facts_problems = []
    for assessment in report["assessments"]:
        if sha(canonical(assessment["facts"])) != assessment["reproducibility"]["facts_hash"]:
            facts_problems.append(assessment["assessment_id"])
    check("G", "assessment facts hashes recompute independently", not facts_problems, str(facts_problems[:3]))
    check("G", "the assessment report still agrees with the expectation table",
          report["agreement"]["auto_matched"] == report["agreement"]["total"],
          f"{report['agreement']}")

    codes = [json.loads(line)["type"] for line in
             (OUT / "order_trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    check("G", "the trace covers refunds", "refunded" in codes, str(sorted(set(codes))))
    check("G", "the trace covers disputes", any(code.startswith("dispute_") for code in codes),
          str(sorted(set(codes))))

    stdlib = set(sys.stdlib_module_names)
    third_party = []
    clock_calls = []
    network = []
    for path in sorted((ROOT / "c2m_craft").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                names = []
            for name in names:
                top = name.split(".")[0]
                if top not in stdlib and top != "c2m_craft":
                    third_party.append(f"{path.name}: {name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("now", "utcnow", "today") and getattr(node.func.value, "id", "") in (
                    "datetime", "date",
                ):
                    clock_calls.append(f"{path.name}:{node.lineno}")
                if node.func.attr == "time" and getattr(node.func.value, "id", "") == "time":
                    clock_calls.append(f"{path.name}:{node.lineno}")
    check("G", "the package imports only the standard library", not third_party, str(third_party[:3]))
    check("G", "the package never reads the wall clock", not clock_calls, str(clock_calls[:3]))
    for path in sorted((ROOT / "c2m_craft").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for module in ("import requests", "import httpx", "import aiohttp", "import socket"):
            if re.search(rf"^\s*{re.escape(module)}\b", text, re.M):
                network.append(f"{path.name}: {module}")
    check("G", "the package has no network client", not network, str(network[:3]))

    site = sample("config/site.json")
    check("G", "the delivery is marked as synthetic",
          site.get("data_provenance") == "synthetic_baseline" and site.get("client_materials_received") is False,
          str(site.get("data_provenance")))


# -- H. requirements ------------------------------------------------------
def group_h() -> None:
    group("H")
    result = requirements_mod.check(ROOT)
    check("H", "the requirement matrix is closed", result["ok"], str(result["problems"][:3]))
    stats = result["stats"]
    check("H", "the brief is decomposed into at least fifty items", stats["items"] >= 50, str(stats["items"]))
    check("H", "every M1 item is implemented",
          stats["m1_items"] == stats["m1_implemented"], f"{stats['m1_implemented']}/{stats['m1_items']}")
    check("H", "entities are covered, partial and planned as expected",
          stats["status_counts"]["covered"] >= 39 and stats["status_counts"]["planned"] >= 9,
          str(stats["status_counts"]))
    late = [item for item in requirements_mod.load(ROOT)["items"]
            if item["milestone"] in ("M3", "M4") and item["status"] != "covered"]
    check("H", "every M3 and M4 item is covered", not late, str([item["id"] for item in late]))
    data = requirements_mod.load(ROOT)
    acceptance_ids = sorted((row["id"] for row in data["acceptance"]), key=lambda value: int(value[1:]))
    check("H", "all eleven acceptance criteria are declared",
          acceptance_ids == [f"J{index}" for index in range(11)], str(acceptance_ids))
    referenced = {ac for item in data["items"] for ac in item.get("ac_refs", [])}
    check("H", "every acceptance criterion is referenced by an item",
          set(acceptance_ids) <= referenced, str(sorted(set(acceptance_ids) - referenced)))
    mismatched = [ac_id for ac_id, entry in result["acceptance"].items()
                  if entry["computed"] != entry["declared"]]
    check("H", "declared and computed acceptance coverage agree", not mismatched, str(mismatched))
    matrix = (ROOT / "docs" / "requirements-matrix.md").read_text(encoding="utf-8")
    rows = matrix.count("\n| ") - matrix.count("\n| ---") - matrix.count("\n| ID") - matrix.count("\n| AC") - 1
    check("H", "the rendered matrix has one row per item", rows >= stats["items"], f"{rows} vs {stats['items']}")
    check("H", "the Chinese matrix is rendered", (ROOT / "docs" / "requirements-matrix.zh.md").is_file())
    contract_refs = {ref for item in data["items"] for ref in item.get("contract_refs", [])}
    unknown_contracts = sorted(contract_refs - set(STORE.contract_ids))
    check("H", "every contract referenced by a requirement exists", not unknown_contracts, str(unknown_contracts))
    groups = set(data["verify_groups"])
    declared_groups = {item.get("verify_group") for item in data["items"]}
    check("H", "every item points at a declared verification group",
          declared_groups <= groups, str(sorted(declared_groups - groups)))


# -- HTTP smoke -----------------------------------------------------------
def http_smoke() -> str:
    lines: list[str] = []
    port = free_port()
    process = subprocess.Popen(
        [PY, "-m", "c2m_craft", "serve", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    base = f"http://127.0.0.1:{port}"
    ready = False
    try:
        for _ in range(60):
            try:
                status, _ = http_get(base, "/api/health")
                if status == 200:
                    ready = True
                    break
            except (urllib.error.URLError, ConnectionError):
                pass
            import time

            time.sleep(0.1)
        if not ready:
            lines.append("server did not become ready")
            return "\n".join(lines)
        lines.append(f"server ready on {base}")

        get_paths = [
            "/api/health", "/api/spec", "/api/i18n", "/api/industries", "/api/rules",
            "/api/rules/JW-CAST-001", "/api/library/search?q=interlace",
            "/api/library/PA-JW-0001", "/api/concepts", "/api/concepts/DC-0001",
            "/api/assessments", "/api/reviews/queue", "/api/orders", "/api/dispatch/board",
            "/api/enterprise", "/api/enterprise/switch", "/api/growth/site",
            "/api/growth/crm", "/api/ip",
        ]
        for path in get_paths:
            status, body = http_get(base, path)
            lines.append(f"GET {path} -> {status} ({(body or '')[:60]})")
            check("G", f"smoke: GET {path} succeeds", status == 200, str(status))

        status, body = http_get(base, "/")
        lines.append(f"GET / -> {status}")
        check("G", "smoke: the prototype page is served", status == 200 and "app.js" in body, str(status))

        status, body = http_post(base, "/api/workstation/generate", {
            "text": "a coastal pendant series for duty free retail",
            "industry": "jewelry", "count": 2, "style_id": "coastal_minimal",
        })
        lines.append(f"POST /api/workstation/generate -> {status}")
        check("G", "smoke: concept generation works over HTTP", status == 200, str(status))

        status, body = http_post(base, "/api/assess", {"concept_id": "DC-0002", "workshop_id": "WS-JW-A"})
        lines.append(f"POST /api/assess -> {status}")
        payload = json.loads(body)
        check("G", "smoke: assessment returns a blocked verdict",
              status == 200 and payload["data"]["assessment"]["final_verdict"] == "not_manufacturable",
              str(status))

        status, body = http_post(base, "/api/library/ingest", {"asset_id": "PA-JW-0999"})
        lines.append(f"POST /api/library/ingest (invalid) -> {status}")
        check("G", "smoke: the licensing gate answers 422 over HTTP", status == 422, str(status))

        status, body = http_post(base, "/api/growth/inquiry", {
            "language": "en",
            "contact": {"name": "Verify Buyer", "email": "verify.buyer@example.com",
                        "company": "Verify Retail (synthetic)", "country": "DE", "channel": "site_form"},
            "message": "We need 200 pcs of the pendant for the spring season.",
            "intent": "bulk_quote", "product_interest": ["pendant"],
        })
        lines.append(f"POST /api/growth/inquiry -> {status}")
        inquiry = json.loads(body)["data"]["inquiry"] if status == 200 else {}
        check("G", "smoke: an inquiry becomes a scored lead",
              status == 200 and inquiry.get("lead", {}).get("score", 0) > 0, str(status))
        if inquiry:
            status, body = http_post(
                base, f"/api/growth/inquiries/{inquiry['inquiry_id']}/advance",
                {"stage": "contacted", "note": "called the buyer and confirmed the assortment"},
            )
            lines.append(f"POST /api/growth/inquiries/{inquiry['inquiry_id']}/advance -> {status}")
            check("G", "smoke: the lead moves one stage", status == 200
                  and json.loads(body)["data"]["inquiry"]["lead"]["stage"] == "contacted", str(status))

        for path, needle in (("/en", "hreflang"), ("/zh/collection", "<h1"),
                             ("/reel", "<svg"), ("/sitemap.xml", "<urlset")):
            status, body = http_get(base, path)
            lines.append(f"GET {path} -> {status}")
            check("G", f"smoke: GET {path} serves the generated artifact",
                  status == 200 and needle in body, str(status))

        status, body = http_post(base, "/api/orders", {"concept_id": "DC-0001"})
        lines.append(f"POST /api/orders -> {status}")
        order = json.loads(body)["data"]["order"]
        check("G", "smoke: an order can be created over HTTP", status == 200, str(status))
        for event, actor in (("presale_opened", "designer"), ("payment_received", "buyer")):
            status, body = http_post(base, f"/api/orders/{order['order_id']}/advance",
                                     {"event": event, "actor_kind": actor, "actor_id": actor})
            lines.append(f"POST /api/orders/{order['order_id']}/advance {event} -> {status}")
        status, body = http_post(base, f"/api/orders/{order['order_id']}/advance",
                                 {"event": "settled", "actor_kind": "system"})
        lines.append(f"POST /api/orders/{order['order_id']}/advance settled -> {status}")
        check("G", "smoke: an illegal transition answers 409", status == 409, str(status))

        status, body = http_get(base, f"/api/orders/{order['order_id']}")
        lines.append(f"GET /api/orders/{order['order_id']} -> {status}")
        check("G", "smoke: the order ledger is readable", status == 200
              and len(json.loads(body)["data"]["events"]) >= 3, str(status))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        lines.append("server stopped")
    return "\n".join(lines)


# -- main -----------------------------------------------------------------
def group_i() -> None:
    """Milestone 2: customisation, capacity, editions, royalties, quality."""
    capacity = json.loads((OUT / "capacity_plan.json").read_text(encoding="utf-8"))
    check("I", "four workshops publish a capacity schedule",
          len(capacity["schedules"]) == 4, str(len(capacity["schedules"])))
    over = [
        (schedule["workshop_id"], row["date"], row["booked_minutes"], row["capacity_minutes"])
        for schedule in capacity["schedules"] for row in schedule["utilization"]
        if row["booked_minutes"] > row["capacity_minutes"]
    ]
    check("I", "no day is booked beyond its capacity", not over, str(over[:2]))
    valid = not any(STORE.validate("production_schedule", schedule) for schedule in capacity["schedules"])
    check("I", "every schedule validates against the contract", valid)

    customization = json.loads((OUT / "customization_report.json").read_text(encoding="utf-8"))
    check("I", "the candidate option catalogue covers both industries",
          customization["counts"]["industries"] == 2, str(customization["counts"]))
    check("I", "the catalogue publishes options and conflicts",
          customization["counts"]["options"] >= 20 and customization["counts"]["conflicts"] >= 3,
          str(customization["counts"]))
    applied = customization["applied"]["choice"]
    catalogue = customization["catalog"][applied["industry"]]
    base = applied["amounts"]["base_unit_price_cents"]
    expected = base
    for selection in applied["selections"]:
        row = next(
            option
            for group in catalogue["groups"]
            for option in group["options"]
            if option["option_id"] == selection["option_id"]
        )
        expected += base * int(row["price_delta_bp"]) // 10000
    check("I", "customisation deltas recompute from the catalogue",
          expected == applied["amounts"]["unit_price_cents"],
          f"{expected} != {applied['amounts']['unit_price_cents']}")
    check("I", "the applied choice is bound to a derived concept",
          applied["status"] == "applied"
          and applied["result_concept_id"]
          and applied["result_concept_id"] != applied["base_concept_id"],
          str(applied["result_concept_id"]))
    check("I", "the customisation choice validates against the contract",
          not STORE.validate("customization_choice", applied))

    editions = json.loads((OUT / "edition_archive.json").read_text(encoding="utf-8"))
    edition = editions["edition_detail"]
    check("I", "the edition issues no more numbers than its size",
          len(edition["numbering"]["issued"]) <= edition["size"],
          f"{len(edition['numbering']['issued'])}/{edition['size']}")
    record = editions["certificate"]
    recomputed = content_hash(
        {
            "edition_id": record["edition_id"],
            "edition_number": record["edition_number"],
            "concept_id": edition["concept_id"],
            "certificate_id": record["certificate_id"],
        }
    )
    check("I", "the certificate hash recomputes from the piece identity",
          recomputed == record["certificate_hash"], recomputed)
    chain = record["provenance"]
    chained = (
        bool(chain)
        and chain[0]["from"] is None
        and all(chain[index]["from"] == chain[index - 1]["to"] for index in range(1, len(chain)))
        and chain[-1]["to"] == record["owner"]["owner_id"]
    )
    check("I", "the collector provenance chain is continuous", chained)
    check("I", "the collector record validates against the contract",
          not STORE.validate("collector_record", record))

    events = [
        json.loads(line)
        for line in (OUT / "order_trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    created = [event for event in events if event["type"] == "order_created"]
    promised = all(
        event["payload"]["promise"]["promised_delivery_at"] > event["at"] for event in created
    )
    check("I", "every order carries a promise later than the order time", promised,
          str(len(created)))
    royalty_events = [
        event for event in events if event["type"] == "settled" and event["payload"].get("royalty_lines")
    ]
    check("I", "a settlement carries per-asset royalty lines", len(royalty_events) == 1,
          str(len(royalty_events)))
    if royalty_events:
        payload = royalty_events[0]["payload"]
        allocated = sum(line["amount_cents"] for line in payload["royalty_lines"])
        check("I", "royalty lines sum to the IP share",
              allocated == payload["ip_share_cents"], f"{allocated} != {payload['ip_share_cents']}")
        check("I", "each royalty line keeps its asset rate",
              all(line["rate_bp"] >= 0 for line in payload["royalty_lines"]))

    quality = json.loads((OUT / "quality_report.json").read_text(encoding="utf-8"))
    check("I", "the quality report holds both a pass and a failure",
          quality["summary"]["passed"] >= 1 and quality["summary"]["failed"] >= 1,
          str(quality["summary"]))
    codes = {row["code"] for row in quality["taxonomy"]}
    offenders = [
        row["code"]
        for record in quality["records"]
        for row in record["defects"]
        if row["code"] not in codes
    ]
    check("I", "every recorded defect comes from the taxonomy", not offenders, str(offenders))
    consistent = all(
        record["verdict"] != "pass"
        or not any(
            row["severity"] in ("major", "critical") and row["count"] > 0
            for row in record["defects"]
        )
        for record in quality["records"]
    )
    check("I", "no pass carries a major or critical defect", consistent)
    measurements = all(
        bool(row["ok"]) == (row["limit_min"] <= row["value"] <= row["limit_max"])
        for record in quality["records"]
        for row in record["measurements"]
    )
    check("I", "measurement limits bracket their values", measurements)

    dispute_events = [event for event in events if event["type"] == "dispute_opened"]
    cited = dispute_events[-1]["payload"].get("qc_record_ids") if dispute_events else []
    known_records = {row["qc_id"] for row in quality["records"]}
    check("I", "the dispute cites a quality record that exists",
          bool(cited) and set(cited) <= known_records, str(cited))
    disputed_orders = [event for event in events if event["type"] == "dispute_resolved_split"]
    check("I", "the dispute resolves with a note and keeps its evidence",
          bool(disputed_orders) and bool(disputed_orders[-1]["payload"].get("note")) and bool(cited),
          str(len(disputed_orders)))


# -- J. milestone 3 --------------------------------------------------------
def group_j() -> None:
    """Milestone 3: enterprise service layer, FDE readiness and the growth stack."""
    group("J")
    enterprise = json.loads((OUT / "enterprise_report.json").read_text(encoding="utf-8"))
    registry = enterprise["registry"]
    check("J", "ten reusable components are registered",
          registry["counts"]["components"] == 10, str(registry["counts"]))
    components = registry["components"]
    invalid = []
    for component in components:
        issues = STORE.validate("service_component", component)
        if issues:
            invalid.append(f"{component['component_id']}: {format_issues(issues)}")
    check("J", "every registered component validates against its contract", not invalid,
          "; ".join(invalid[:3]))
    missing_config = [
        component["config_ref"] for component in components
        if not (ROOT / component["config_ref"]).exists()
    ]
    check("J", "every component configuration path exists", not missing_config,
          str(missing_config[:3]))
    component_ids = {component["component_id"] for component in components}
    bad_dependency = sorted(
        f"{component['component_id']}->{dependency}"
        for component in components
        for dependency in component["depends_on"]
        if dependency not in component_ids
    )
    check("J", "component dependencies are declared by id", not bad_dependency,
          str(bad_dependency[:3]))

    profiles = enterprise["profiles"]
    check("J", "two enterprise profiles are assembled", len(profiles) == 2, str(len(profiles)))
    ready = [profile["profile_id"] for profile in profiles if profile["assembly"]["status"] == "ready"]
    check("J", "both assemblies are ready", len(ready) == 2, str(ready))
    invalid_profiles = []
    for path in sorted((ROOT / "config" / "enterprise" / "profiles").glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        issues = STORE.validate("enterprise_profile", profile)
        if issues:
            invalid_profiles.append(f"{path.name}: {format_issues(issues)}")
    check("J", "every populated profile validates", not invalid_profiles,
          "; ".join(invalid_profiles[:3]))
    switch = enterprise["switch"]
    check("J", "the switch covers two industries on two profiles",
          switch["industries"] == ["hardwood", "jewelry"] and len(switch["rows"]) == 2,
          str(switch["industries"]))
    check("J", "the switch proves zero code changes",
          switch["proof"]["code_changes_between_industries"] == 0, str(switch["proof"]))
    check("J", "the profiles share at least fifteen capabilities",
          len(switch["capabilities_shared"]) >= 15, str(len(switch["capabilities_shared"])))
    fde = enterprise["fde"]["readiness"]["EP-0001"]
    check("J", "the FDE checklist has twelve items", fde["items_total"] == 12, str(fde["items_total"]))
    check("J", "readiness is derived from the checklist", fde["readiness_bp"] == 7500, str(fde["readiness_bp"]))
    check("J", "blocking items keep the deployment in pilot",
          fde["status"] == "pilot" and len(fde["blocking_open"]) == 2,
          f"{fde['status']} {len(fde['blocking_open'])}")
    boundaries = profiles[0].get("data_boundaries") or {}
    check("J", "the profile maps its data boundaries",
          len(boundaries.get("stores") or []) >= 4 and boundaries.get("cross_border") is True,
          str(len(boundaries.get("stores") or [])))
    deployment = profiles[0].get("deployment") or {}
    check("J", "the profile declares its deployment posture",
          deployment.get("mode") in {"on_prem", "private_cloud", "saas"}
          and deployment.get("auth_gate") is True, str(deployment.get("mode")))

    growth = json.loads((OUT / "growth_report.json").read_text(encoding="utf-8"))
    site = growth["site"]
    check("J", "the site generates nine pages", len(site["pages"]) == 9, str(len(site["pages"])))
    check("J", "the site covers three languages", site["languages"] == ["en", "zh", "de"], str(site["languages"]))
    site_issues = STORE.validate("growth_site", site)
    check("J", "the site validates against its contract", not site_issues, format_issues(site_issues)[:160])
    language_gap = [
        page["page_id"] for page in site["pages"]
        if {row["lang"] for row in page["hreflang"]} != set(site["languages"])
    ]
    check("J", "every page links every language", not language_gap, str(language_gap[:3]))
    path_gap = [
        page["path"] for page in site["pages"]
        if not page["path"].startswith("/" + page["language"]) or page["canonical_path"] != page["path"]
    ]
    check("J", "canonical paths follow the language", not path_gap, str(path_gap[:3]))
    check("J", "the SEO audit is clean",
          site["seo"]["score_bp"] == 10000 and site["seo"]["issues"] == [],
          str(site["seo"]["score_bp"]))
    negative = growth.get("negative_audit") or {}
    codes = [issue["code"] for issue in negative.get("issues") or []]
    check("J", "the auditor detects a stripped description",
          negative.get("score_bp", 10000) < 10000 and "description_length" in codes, str(codes))
    check("J", "the demo writes nine pages plus two crawler files",
          len(growth.get("site_files") or []) == 11, str(len(growth.get("site_files") or [])))
    sitemap = (OUT / "site" / "sitemap.xml").read_text(encoding="utf-8")
    check("J", "the sitemap lists every page", sitemap.count("<url>") == 9, str(sitemap.count("<url>")))
    robots = (OUT / "site" / "robots.txt").read_text(encoding="utf-8")
    check("J", "the robots file points at the sitemap", "Sitemap:" in robots and "Disallow: /api/" in robots)

    crm = growth["crm"]
    inquiries = crm["inquiries"]
    check("J", "the demo drives three inquiries", len(inquiries) == 3, str(len(inquiries)))
    check("J", "the pipeline has the six stages", len(crm["board"]["stages"]) == 6,
          str(len(crm["board"]["stages"])))
    stages = {record["lead"]["stage"] for record in inquiries}
    check("J", "the loop closes with won, contacted and lost leads",
          stages == {"won", "contacted", "lost"}, str(sorted(stages)))
    check("J", "one lead carries a quote", sum(1 for record in inquiries if record["quote"]) == 1)
    check("J", "the quoted value reconciles",
          crm["summary"]["quoted_value_cents"] == 240000, str(crm["summary"]["quoted_value_cents"]))
    invalid_leads = [
        record["inquiry_id"] for record in inquiries
        if STORE.validate("inquiry_lead", record)
    ]
    check("J", "every lead validates against its contract", not invalid_leads, str(invalid_leads[:3]))
    score_bad = []
    for record in inquiries:
        points = sum(row["points"] for row in record["lead"]["score_breakdown"])
        if record["lead"]["score"] != max(0, min(100, points)):
            score_bad.append(record["inquiry_id"])
    check("J", "lead scores recompute from their factors", not score_bad, str(score_bad[:3]))
    check("J", "no lead breaches its first response SLA",
          crm["board"]["sla_breaches"] == [], str(crm["board"]["sla_breaches"]))
    due_ok = all(
        [row["due_at"] for row in record["follow_ups"]] == sorted(row["due_at"] for row in record["follow_ups"])
        for record in inquiries
    )
    check("J", "follow-ups are scheduled in due order", due_ok)
    stage_event = {"qualified": "routed", "contacted": "contacted", "quoted": "quoted", "won": "won", "lost": "lost"}
    trace_ok = all(
        record["crm_events"][-1]["type"] == stage_event[record["lead"]["stage"]]
        for record in inquiries
    )
    check("J", "the last CRM event opens the current stage", trace_ok)


# -- K. milestone 4 --------------------------------------------------------
def group_k() -> None:
    """Milestone 4: cultural IP canon, visual library, short drama, reel and licensing."""
    group("K")
    bible = json.loads((OUT / "character_bible.json").read_text(encoding="utf-8"))
    bible_issues = STORE.validate("character_bible", bible)
    check("K", "the character bible validates", not bible_issues, format_issues(bible_issues)[:160])
    characters = bible["canon"]["characters"]
    check("K", "the bible holds two guardians", len(characters) == 2, str(len(characters)))
    check("K", "the guardians use distinct elements",
          len({character["element"] for character in characters}) == 2,
          str([character["element"] for character in characters]))
    check("K", "every guardian cites a content review",
          all(character["content_review_ref"].startswith("CRV-") for character in characters))
    check("K", "every guardian has a three beat arc",
          all(len(character["story_arc"]) == 3 for character in characters))
    check("K", "heritage references are never exclusive",
          all(row["exclusive_claimed"] is False for row in bible["heritage_refs"]),
          str(bible["heritage_refs"]))

    library = json.loads((OUT / "ip_asset_library.json").read_text(encoding="utf-8"))
    assets = library["assets"]
    check("K", "the visual library holds twenty-two assets", len(assets) == 22, str(len(assets)))
    kinds = {asset["kind"] for asset in assets}
    check("K", "the library covers every asset kind",
          kinds == {"turnaround", "expression", "prop", "costume", "scene"}, str(sorted(kinds)))
    invalid_assets = [
        asset["asset_id"] for asset in assets if STORE.validate("visual_asset", asset)
    ]
    check("K", "every asset validates against its contract", not invalid_assets, str(invalid_assets[:3]))
    bad_checksums = []
    for asset in assets:
        expected = sha(
            canonical(
                {
                    "asset_id": asset["asset_id"],
                    "character_id": asset["character_id"],
                    "kind": asset["kind"],
                    "view_or_name": asset["view_or_name"],
                    "recipe": asset["recipe"],
                    "resolution": asset["resolution"],
                }
            )
        )
        if expected != asset["checksum"]:
            bad_checksums.append(asset["asset_id"])
    check("K", "every asset checksum recomputes from its recipe", not bad_checksums, str(bad_checksums[:3]))
    geometry_bad = []
    for asset in assets:
        for layer in asset["recipe"]["layers"]:
            size = len(layer["geometry"])
            if layer["shape"] == "circle" and size != 3:
                geometry_bad.append(f"{asset['asset_id']}:{layer['layer_id']}")
            if layer["shape"] == "ellipse" and size != 4:
                geometry_bad.append(f"{asset['asset_id']}:{layer['layer_id']}")
            if layer["shape"] in ("polygon", "path", "line") and size % 2:
                geometry_bad.append(f"{asset['asset_id']}:{layer['layer_id']}")
    check("K", "every drawing layer carries valid geometry", not geometry_bad, str(geometry_bad[:3]))
    check("K", "every asset is labelled and approved",
          all(asset["source"]["authenticity_label"] and asset["review"]["status"] == "approved"
              for asset in assets))

    drama = json.loads((OUT / "short_drama_package.json").read_text(encoding="utf-8"))
    drama_issues = STORE.validate("short_drama", drama)
    check("K", "the short drama validates", not drama_issues, format_issues(drama_issues)[:160])
    scenes = drama["script"]["scenes"]
    beats = sum(len(scene["beats"]) for scene in scenes)
    check("K", "the drama has five scenes and ten beats", len(scenes) == 5 and beats == 10,
          f"{len(scenes)} scenes, {beats} beats")
    frames = drama["storyboard"]["frames"]
    check("K", "the storyboard has one frame per beat", len(frames) == beats, str(len(frames)))
    check("K", "the cut is sixty-seven seconds", drama["cut"]["total_seconds"] == 67,
          str(drama["cut"]["total_seconds"]))
    edl = drama["cut"]["edl"]
    timecode_ok = edl[0]["in_tc"] == "00:00:00"
    for index in range(1, len(edl)):
        timecode_ok = timecode_ok and edl[index]["in_tc"] == edl[index - 1]["out_tc"]
    timecode_ok = timecode_ok and edl[-1]["out_tc"] == "00:01:07"
    check("K", "the edit decision list has continuous timecodes", timecode_ok, str(edl[-1]))
    subtitles = drama["subtitles"]["lines"]
    check("K", "the subtitle track has twelve lines", len(subtitles) == 12, str(len(subtitles)))
    previous_end = "00:00:00"
    subtitle_ok = True
    for line in subtitles:
        subtitle_ok = subtitle_ok and line["in_tc"] >= previous_end and line["out_tc"] > line["in_tc"]
        previous_end = line["out_tc"]
    check("K", "subtitles never overlap and stay inside the cut",
          subtitle_ok and previous_end <= "00:01:07", previous_end)
    check("K", "the drama review is approved with a review reference",
          drama["review"]["status"] == "approved" and drama["review"]["content_review_ref"].startswith("CRV-"))

    pack = json.loads((OUT / "licensing_pack.json").read_text(encoding="utf-8"))
    license_record = pack["license"]
    license_issues = STORE.validate("ip_license", license_record)
    check("K", "the licence package validates", not license_issues, format_issues(license_issues)[:160])
    documents = license_record["documents"]
    signed = [document for document in documents if document["status"] == "signed"]
    check("K", "the licence set holds five documents, four signed",
          len(documents) == 5 and len(signed) == 4, f"{len(documents)}/{len(signed)}")
    signing_bad = [
        document["document_id"] for document in signed
        if not {"licensor", "licensee"} <= {row["party"] for row in document["signatories"]}
    ]
    check("K", "every signed document has both parties", not signing_bad, str(signing_bad[:3]))
    categories = set(license_record["usage"]["derivative_categories"])
    covered = {
        category for document in signed for category in document["derivative_categories"]
    }
    check("K", "every derivative category has a signed document",
          categories - covered == set(), str(sorted(categories - covered)))
    checksum_bad = [
        document["document_id"] for document in documents
        if not re.match(r"^[a-f0-9]{64}$", document["checksum"])
    ]
    check("K", "every licence document carries a checksum", not checksum_bad, str(checksum_bad[:3]))
    specs = pack["merch_specs"]
    check("K", "four merchandise specifications are delivered", len(specs) == 4, str(len(specs)))
    spec_invalid = [spec["spec_id"] for spec in specs if STORE.validate("merch_spec", spec)]
    check("K", "every merchandise specification validates", not spec_invalid, str(spec_invalid[:3]))
    check("K", "the specifications cover the four derivative categories",
          {spec["category"] for spec in specs} ==
          {"jewelry_pendant", "apparel_collab", "wood_carving_collectible", "cultural_gift"},
          str(sorted(spec["category"] for spec in specs)))
    labelled = []
    for spec in specs:
        labels = " ".join(spec["quality"]["inspection_points"] + spec["packaging"]["label_requirements"]).lower()
        if "authenticity" not in labels:
            labelled.append(spec["spec_id"])
    check("K", "every specification carries the authenticity label", not labelled, str(labelled[:3]))

    reviews = json.loads((OUT / "content_review.json").read_text(encoding="utf-8"))["reviews"]
    check("K", "nine content reviews are recorded", len(reviews) == 9, str(len(reviews)))
    review_invalid = [review["review_id"] for review in reviews if STORE.validate("content_review", review)]
    check("K", "every content review validates", not review_invalid, str(review_invalid[:3]))
    check("K", "every review carries the AIGC authenticity block",
          all(review["authenticity"]["ai_generated"] and review["authenticity"]["disclosure_required"]
              for review in reviews))
    check("K", "approved reviews carry no failed checklist item",
          all(review["verdict"] != "approved"
              or all(item["verdict"] != "fail" for item in review["checklist"])
              for review in reviews))

    reel = (OUT / "sample_reel.html").read_text(encoding="utf-8")
    check("K", "the sample reel holds one frame per storyboard frame", reel.count("<svg") == 10,
          str(reel.count("<svg")))
    check("K", "the reel is self contained",
          "<img" not in reel and 'src="http' not in reel and 'href="http' not in reel,
          "external asset found")
    check("K", "the reel carries the authenticity label", "AI-assisted" in reel)
    check("K", "the reel shows the cut timecodes", "00:00:00" in reel and "00:01:07" in reel)
    check("K", "the reel stays a reasonable artifact size", len(reel.encode("utf-8")) < 200000,
          str(len(reel.encode("utf-8"))))


def main() -> int:
    RECORDS.mkdir(parents=True, exist_ok=True)
    # Records are overwritten at the end of this run; they are deliberately not
    # deleted first, because the demo's coverage report reads the artifact tree and
    # a missing record would make two consecutive demo runs disagree.

    print("[verify] running the demo")
    demo = subprocess.run([PY, "-m", "c2m_craft", "demo"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", timeout=600)
    first_manifest_text = (OUT / "hash_manifest.json").read_text(encoding="utf-8") if demo.returncode == 0 else ""
    first_manifest = json.loads(first_manifest_text) if first_manifest_text else {}
    TRANSCRIPT.append(f"[verify] demo exit {demo.returncode}")

    print("[verify] running the tests")
    tests = subprocess.run([PY, "tests/test_runner.py"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", timeout=900)
    (RECORDS / "tests_output.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8", newline="\n")
    TRANSCRIPT.append(f"[verify] tests exit {tests.returncode}")

    print("[verify] re-running the demo for determinism")
    demo2 = subprocess.run([PY, "-m", "c2m_craft", "demo"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", timeout=600)
    second_manifest_text = (OUT / "hash_manifest.json").read_text(encoding="utf-8") if demo2.returncode == 0 else ""
    second_manifest = json.loads(second_manifest_text) if second_manifest_text else {}
    TRANSCRIPT.append(f"[verify] second demo exit {demo2.returncode}")

    group_a()
    group_b()
    group_c()
    group_d()
    group_e(tests.stdout, tests.returncode)
    group_f()
    group_g(first_manifest, second_manifest, demo.returncode == 0 and demo2.returncode == 0)
    group_h()
    group_i()
    group_j()
    group_k()

    print("[verify] driving the HTTP server")
    smoke = http_smoke()
    (RECORDS / "ui_smoke.log").write_text(smoke + "\n", encoding="utf-8", newline="\n")
    TRANSCRIPT.append("\n== http smoke ==\n" + smoke)

    manifest = json.loads((OUT / "hash_manifest.json").read_text(encoding="utf-8"))
    hash_lines = [f"{name}  {digest}" for name, digest in sorted(manifest["files"].items())]
    (RECORDS / "artifact_hashes.txt").write_text(
        "\n".join(hash_lines) + f"\nmanifest  {sha_file(OUT / 'hash_manifest.json')}\n",
        encoding="utf-8",
        newline="\n",
    )

    commands = [
        ("python -m c2m_craft demo", demo.returncode,
         "artifacts written: 33"),
        ("python tests/test_runner.py", tests.returncode,
         "N/N tests passed"),
        ("python -m c2m_craft demo (second run)", demo2.returncode,
         "identical hash manifest"),
        ("python verify/run_verification.py", 0, "N/N assertions passed"),
    ]
    command_lines = ["# Verification commands", "",
                     "| Command | Exit | Expected last line |", "|---|---|---|"]
    for command, code, expected in commands:
        command_lines.append(f"| `{command}` | {code} | {expected} |")
    command_lines.extend([
        "",
        "Generated at the logical as-of time recorded in `out/hash_manifest.json`; no wall clock is read.",
        "",
        "Group results:",
        "",
        "| Group | Assertions | Passed |",
        "|---|---|---|",
    ])
    for name in sorted(GROUP_COUNTS):
        command_lines.append(
            f"| {name} | {GROUP_COUNTS[name]['total']} | {GROUP_COUNTS[name]['passed']} |"
        )
    command_lines.append("")
    (RECORDS / "commands.md").write_text("\n".join(command_lines), encoding="utf-8", newline="\n")

    summary_lines = ["# Verification transcript", "",
                     f"- assertions: {COUNTS['total']}",
                     f"- passed: {COUNTS['passed']}",
                     f"- failed: {len(FAILURES)}",
                     ""]
    summary_lines.extend(TRANSCRIPT)
    if FAILURES:
        summary_lines.extend(["", "## Failures", ""])
        summary_lines.extend(f"- {failure}" for failure in FAILURES)
    (RECORDS / "verification_output.txt").write_text(
        "\n".join(summary_lines), encoding="utf-8", newline="\n"
    )

    print()
    for name in sorted(GROUP_COUNTS):
        stats = GROUP_COUNTS[name]
        print(f"[group {name}] {stats['passed']}/{stats['total']} assertions passed")
    print(f"{COUNTS['passed']}/{COUNTS['total']} assertions passed")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
