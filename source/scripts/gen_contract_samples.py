"""Generate the contract sample suite: valid records and one mutation per contract.

Every negative sample is a documented mutation of a valid record, and the
expected error class is written next to it (keyword or invariant id plus the
instance path).  Verification asserts the class of the rejection, not the exact
wording, so a message change cannot silently weaken the suite.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c2m_craft.core.contracts import SchemaStore, format_issues  # noqa: E402
from c2m_craft.commerce import settlement as settlement_mod  # noqa: E402
from c2m_craft.service import Service  # noqa: E402

POSITIVE_DIR = ROOT / "samples" / "contracts" / "positive"
NEGATIVE_DIR = ROOT / "samples" / "contracts" / "negative"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")


def run() -> int:
    store = SchemaStore(ROOT)
    service = Service(ROOT, ROOT / "var" / "samples", reset=True)

    # -- two assessments and the review queue ---------------------------
    assessment_a = service.assess_at(service.concept("DC-0001"), "WS-JW-A", queue_review=False)
    assessment_b = service.assess_at(service.concept("DC-0003"), "WS-JW-A")
    assessment_c = service.assess_at(service.concept("DC-0002"), "WS-JW-B")
    queue_ids = [item["queue_id"] for item in service.reviews.items]
    review_pending = service.reviews.get(queue_ids[0])
    decision = service.decide_review(
        queue_ids[1],
        "conditionally_manufacturable",
        "The reviewer accepts the thin wall only as a museum sample with a resin backing plate, "
        "re-inspection after casting, and no load-bearing use.",
    )
    review_overridden = decision["review"]
    assessment_c = decision["assessment"] or assessment_c

    # -- happy path order to settlement ---------------------------------
    order = service.create_order("DC-0001", model="designer_presale")
    order_id = order["order_id"]
    commerce = service.commerce
    commerce.transition(order_id, "presale_opened", actor={"kind": "designer", "id": "designer-01"})
    commerce.transition(order_id, "payment_received", actor={"kind": "buyer", "id": "buyer-01"})
    commerce.transition(order_id, "work_order_issued", actor={"kind": "system", "id": "system"})
    commerce.transition(order_id, "dispatched", actor={"kind": "factory", "id": "workshop-01"})
    commerce.transition(order_id, "production_started", actor={"kind": "factory", "id": "workshop-01"})
    commerce.transition(order_id, "qc_passed", actor={"kind": "artisan", "id": "ART-JW-01"})
    commerce.transition(order_id, "shipped", actor={"kind": "factory", "id": "workshop-01"})
    commerce.transition(order_id, "settled", actor={"kind": "system", "id": "system"})
    settled_order = service.order(order_id)
    work_order = commerce.work_orders[settled_order["items"][0]["work_order_id"]]
    settlement = commerce.settlement_for(order_id)

    # -- refund path -----------------------------------------------------
    refund_order = service.create_order("DC-0005", model="designer_presale")
    refund_id = refund_order["order_id"]
    commerce.transition(refund_id, "presale_opened", actor={"kind": "designer", "id": "designer-01"})
    commerce.transition(refund_id, "payment_received", actor={"kind": "buyer", "id": "buyer-02"})
    commerce.request_refund(refund_id, "The collector moved the commission to another quarter.")
    commerce.decide_refund(refund_id, approve=True)
    commerce.execute_refund(refund_id)
    refunded_order = service.order(refund_id)

    # -- positive samples ------------------------------------------------
    positives: dict[str, tuple[str, dict]] = {
        "assessment-dc0001-ws-jw-a.json": ("manufacturability_assessment", assessment_a),
        "assessment-dc0003-ws-jw-a.json": ("manufacturability_assessment", assessment_b),
        "assessment-dc0002-ws-jw-b.json": ("manufacturability_assessment", assessment_c),
        "order-ORD-0001.json": ("c2m_order", settled_order),
        "work-order-WO-0001.json": ("craft_work_order", work_order),
        "settlement-ST-0001.json": ("settlement", settlement),
        "order-ORD-0002.json": ("c2m_order", refunded_order),
        "artisan-review-AR-0001.json": ("artisan_review", review_pending),
        "artisan-review-AR-0002.json": ("artisan_review", review_overridden),
    }
    enterprise_profile = {
        "profile_id": "EP-0001",
        "enterprise": {
            "name": "Harbour Jewellery Works (synthetic)",
            "industry": "jewelry",
            "size": "medium",
            "region": "East Asian coastal belt",
        },
        "components": [
            {
                "component_id": "kb_craft",
                "kind": "knowledge_base",
                "enabled": True,
                "config": {"collections": ["craft_rules", "licensing"], "language": "zh"},
            },
            {
                "component_id": "agent_quote",
                "kind": "agent",
                "enabled": True,
                "config": {"tools": ["rules.explain", "library.search"], "max_turns": 6},
            },
            {
                "component_id": "wf_dispatch",
                "kind": "workflow",
                "enabled": True,
                "config": {"trigger": "order.paid", "steps": ["assess", "issue_work_order", "notify"]},
            },
            {
                "component_id": "crm_leads",
                "kind": "crm",
                "enabled": False,
                "config": {"mode": "pilot"},
            },
        ],
        "locale": {"primary": "zh", "secondary": ["en"]},
        "channels": {"site": True, "seo": True, "crm": False},
        "sla": {"first_response_hours": 4, "delivery_days": 21},
        "fde": {
            "fde_id": "FDE-01",
            "handbook_ref": "docs/fde-handbook.md (M3)",
            "go_live_checklist": [
                "interview notes signed off by the client",
                "craft rules reviewed by the workshop craftsperson",
                "licence list attached to every asset",
                "order ledger reconciliation signed by finance",
            ],
        },
        "created_at": "2026-10-20T00:00:00Z",
    }
    ip_license = {
        "license_id": "IPL-0001",
        "characters": [
            {
                "name": {"zh": "千里眼", "en": "Far-sighted guardian"},
                "role": "lead",
                "traits": ["sees distant ships", "keeps watch at the harbour mouth"],
            },
            {
                "name": {"zh": "顺风耳", "en": "Far-hearing guardian"},
                "role": "support",
                "traits": ["hears the wind change", "listens for returning crews"],
            },
        ],
        "usage": {
            "derivative_categories": ["jewelry_pendant", "apparel_collab", "cultural_gift"],
            "territory": ["CN"],
            "term_months": 24,
            "exclusivity": False,
            "royalty_rate_bp": 800,
        },
        "quality_spec": {
            "material_standard": "18K gold or 925 silver, nickel free, hallmarked",
            "packaging": "recycled board box with authenticity label and review record reference",
            "inspection_points": [
                "surface finish matches the approved sample",
                "authenticity label attached",
                "no traditional prototype claimed as exclusive",
            ],
        },
        "contract_template_ref": "templates/ip-license-template.md (M4)",
        "content_review": {
            "status": "approved",
            "reviewer": "CR-IP-01",
            "authenticity_label": "original dual-character design derived from maritime folk belief",
        },
        "traditional_prototype_refs": [
            {"name": "Mazu temple guardian statues", "exclusive_claimed": False},
            {"name": "traditional maritime festival costumes", "exclusive_claimed": False},
        ],
        "created_at": "2026-09-30T00:00:00Z",
    }
    # M3/M4 refresh the enterprise profile and IP licence samples from the runtime,
    # so the committed sample matches the populated profile and the signed document set.
    enterprise_profile = store.json_load(
        ROOT / "config" / "enterprise" / "profiles" / "EP-0001.json"
    )
    ip_license = service.ip.license
    positives["enterprise-profile-EP-0001.json"] = ("enterprise_profile", enterprise_profile)
    positives["ip-license-IPL-0001.json"] = ("ip_license", ip_license)

    # -- milestone 2 records --------------------------------------------
    built = service.build_customization(
        "DC-0001",
        [
            {"group_id": "alloy", "option_id": "alloy_22k"},
            {"group_id": "engraving", "option_id": "engraving_light"},
        ],
    )
    choice = built["choice"]
    edition = service.editions.create(
        concept_id="DC-0001",
        size=8,
        artist={"artist_id": "ARTIST-01", "name": "Studio Lin (synthetic)", "royalty_rate_bp": 800},
        workshop_id="WS-JW-A",
        created_at=service.clock.now,
    )
    issued = service.editions.issue(
        edition["edition_id"],
        number=1,
        order_id="ORD-9999",
        owner={"owner_id": "OWNER-C1", "display_name": "Collector One"},
        at=service.clock.now,
    )
    edition = issued["edition"]
    collector = service.editions.transfer(
        issued["record"]["record_id"],
        owner_id="OWNER-C2",
        display_name="Collector Two",
        at=service.clock.now,
        note="private sale with certificate hand-over",
    )
    schedule = service.schedules()[0]

    qc_order = service.create_order("DC-0001")
    for event, actor in (("presale_opened", "designer"), ("payment_received", "buyer"),
                         ("work_order_issued", "system")):
        service.commerce.transition(qc_order["order_id"], event, actor={"kind": actor, "id": actor})
    qc = service.record_qc(
        qc_order["order_id"],
        "QC-01",
        verdict="pass",
        defects=[],
        inspector="ART-JW-01",
    )

    royalty_settlement = settlement_mod.build(
        store,
        settled_order,
        service.settings.split_policy(),
        settlement_id="ST-0002",
        created_at=service.settings.as_of,
        royalty_assets=[
            {"asset_id": "PA-JW-0001", "licensor": "Regional Crafts Archive (synthetic)", "rate_bp": 300},
            {"asset_id": "PA-JW-0002", "licensor": "self", "rate_bp": 0},
        ],
    )
    positives["customization-choice-CUS-0001.json"] = ("customization_choice", choice)
    positives["edition-ED-0001.json"] = ("edition", edition)
    positives["collector-record-COL-0001.json"] = ("collector_record", collector)
    positives["production-schedule-SCH-0001.json"] = ("production_schedule", schedule)
    positives["qc-record-QCR-0001.json"] = ("qc_record", qc)

    written = []
    for filename, (contract_id, payload) in positives.items():
        issues = store.validate(contract_id, payload, ctx={"as_of": "2026-10-23T00:00:00Z"})
        if issues:
            raise SystemExit(f"{filename} invalid: {format_issues(issues)}")
        write_json(POSITIVE_DIR / filename, payload)
        written.append(filename)

    # -- negative samples: one mutation each -----------------------------
    def mutate(source: dict) -> dict:
        return copy.deepcopy(source)

    negatives: list[tuple[str, str, dict, dict]] = []

    pattern = store.json_load(ROOT / "samples" / "library" / "assets.json")["assets"][0]
    heritage = store.json_load(ROOT / "samples" / "library" / "assets.json")["assets"][2]

    case = mutate(pattern)
    case["license"].pop("source_type")
    negatives.append(
        ("pattern-asset-missing-source.json", "pattern_asset", case,
         {"keyword": "required", "path_prefix": "$.license"})
    )

    case = mutate(pattern)
    case["license"]["usage_scope"] = []
    negatives.append(
        ("pattern-asset-empty-scope.json", "pattern_asset", case,
         {"invariant": "INV-LIC-02", "path_prefix": "$"})
    )

    case = mutate(heritage)
    case["license"]["exclusive"] = True
    negatives.append(
        ("pattern-asset-exclusive-heritage.json", "pattern_asset", case,
         {"invariant": "INV-LIC-03", "path_prefix": "$"})
    )

    case = mutate(pattern)
    case["license"]["valid_from"] = "2029-01-01T00:00:00Z"
    negatives.append(
        ("pattern-asset-inverted-window.json", "pattern_asset", case,
         {"invariant": "INV-LIC-04", "path_prefix": "$"})
    )

    case = mutate(pattern)
    case["palette"] = ["gold"]
    negatives.append(
        ("pattern-asset-bad-hex.json", "pattern_asset", case,
         {"keyword": "pattern", "path_prefix": "$.palette[0]"})
    )

    concept = store.json_load(ROOT / "samples" / "concepts" / "DC-0001.json")
    case = mutate(concept)
    case["seed"] = "NOT-A-SEED"
    negatives.append(
        ("design-concept-bad-seed.json", "design_concept", case,
         {"keyword": "pattern", "path_prefix": "$.seed"})
    )

    case = mutate(concept)
    case.pop("craft_facts")
    negatives.append(
        ("design-concept-missing-facts.json", "design_concept", case,
         {"keyword": "required", "path_prefix": "$"})
    )

    case = mutate(settled_order)
    case["amounts"]["platform_fee_cents"] = -1
    negatives.append(
        ("order-negative-amount.json", "c2m_order", case,
         {"keyword": "minimum", "path_prefix": "$.amounts.platform_fee_cents"})
    )

    case = mutate(settled_order)
    case["amounts"]["designer_share_cents"] += 100
    negatives.append(
        ("order-share-mismatch.json", "c2m_order", case,
         {"invariant": "INV-ORDER-01", "path_prefix": "$"})
    )

    case = mutate(settled_order)
    case["dispute"] = {
        "status": "resolved_rework",
        "reason": "The enamel colour is two shades off the approved sample.",
        "resolution_note": None,
        "opened_at": case["created_at"],
        "resolved_at": case["updated_at"],
        "qc_record_ids": ["QCR-0001"],
    }
    negatives.append(
        ("order-dispute-resolved-without-note.json", "c2m_order", case,
         {"invariant": "INV-DISPUTE-01", "path_prefix": "$"})
    )

    case = mutate(settlement)
    case["split_policy"]["lines"][0]["rate_bp"] = 1000
    negatives.append(
        ("settlement-rate-mismatch.json", "settlement", case,
         {"invariant": "INV-MONEY-01", "path_prefix": "$"})
    )

    case = mutate(review_pending)
    case["status"] = "overridden"
    case["decision"] = {
        "verdict": "conditionally_manufacturable",
        "reason": "ok",
        "decided_at": "2026-10-23T00:00:00Z",
    }
    negatives.append(
        ("review-override-no-reason.json", "artisan_review", case,
         {"invariant": "INV-REVIEW-01", "path_prefix": "$"})
    )

    case = mutate(review_pending)
    case["status"] = "confirmed"
    case["decision"] = {
        "verdict": "not_manufacturable",
        "reason": "confirmed as assessed but with a different verdict",
        "decided_at": "2026-10-23T00:00:00Z",
    }
    negatives.append(
        ("review-confirmed-contradiction.json", "artisan_review", case,
         {"invariant": "INV-REVIEW-01", "path_prefix": "$"})
    )

    case = mutate(ip_license)
    case["traditional_prototype_refs"][0]["exclusive_claimed"] = True
    negatives.append(
        ("ip-license-exclusive-heritage.json", "ip_license", case,
         {"invariant": "INV-IP-01", "path_prefix": "$"})
    )

    case = mutate(work_order)
    case["bom"] = []
    negatives.append(
        ("work-order-empty-bom.json", "craft_work_order", case,
         {"keyword": "minItems", "path_prefix": "$.bom"})
    )

    case = mutate(choice)
    case["amounts"]["delta_cents"] += 100
    negatives.append(
        ("customization-choice-delta-mismatch.json", "customization_choice", case,
         {"invariant": "INV-CUSTOM-01", "path_prefix": "$"})
    )

    case = mutate(edition)
    case["numbering"]["issued"].append(dict(case["numbering"]["issued"][0]))
    negatives.append(
        ("edition-duplicate-number.json", "edition", case,
         {"invariant": "INV-EDITION-01", "path_prefix": "$"})
    )

    case = mutate(collector)
    case["provenance"][1]["from"] = "OWNER-OTHER"
    negatives.append(
        ("collector-chain-break.json", "collector_record", case,
         {"invariant": "INV-EDITION-02", "path_prefix": "$"})
    )

    case = mutate(qc)
    case["verdict"] = "pass"
    case["defects"] = [
        {"code": "setting_loose", "severity": "critical", "count": 1, "note": "stone moves in the bezel"}
    ]
    negatives.append(
        ("qc-pass-with-critical.json", "qc_record", case,
         {"invariant": "INV-QC-01", "path_prefix": "$"})
    )

    case = mutate(royalty_settlement)
    case["royalty_lines"][0]["amount_cents"] += 50
    negatives.append(
        ("settlement-royalty-mismatch.json", "settlement", case,
         {"invariant": "INV-ROYALTY-01", "path_prefix": "$"})
    )

    expected: dict[str, dict] = {}
    for filename, contract_id, payload, expectation in negatives:
        issues = store.validate(contract_id, payload, ctx={"as_of": "2026-10-23T00:00:00Z"})
        if not issues:
            raise SystemExit(f"{filename} was accepted by the contract")
        matched = any(
            (issue.invariant == expectation.get("invariant") if expectation.get("invariant")
             else issue.keyword == expectation.get("keyword"))
            and issue.path.startswith(expectation["path_prefix"])
            for issue in issues
        )
        if not matched:
            raise SystemExit(
                f"{filename}: expected {expectation} but got {format_issues(issues)}"
            )
        write_json(NEGATIVE_DIR / filename, payload)
        expected[filename] = {
            "contract": contract_id,
            **expectation,
            "error_count": len(issues),
        }

    merged = store.json_load(NEGATIVE_DIR / "expected.json").get("samples", {})
    merged.update(expected)
    write_json(
        NEGATIVE_DIR / "expected.json",
        {"version": "1.0.0", "samples": dict(sorted(merged.items()))},
    )

    print(f"[gen_contract_samples] positives: {len(positives)}, negatives: {len(negatives)}")
    print(f"[gen_contract_samples] work order {work_order['work_order_id']}, "
          f"settlement {settlement['settlement_id']}, ledger events {len(service.ledger.events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
