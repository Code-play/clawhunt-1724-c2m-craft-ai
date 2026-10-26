"""One-command demonstration: regenerate every artifact under ``out/``.

The demo is the reproducibility proof.  It runs the contract suite, the rule
lint, the creative workstation, the library gate, twenty assessments (ten
concepts against two workshops each) with two review decisions, and three order
scenarios (a settled order, a refunded order and a dispute resolved by split
settlement).  A second run must produce byte-identical files, which is what
``out/hash_manifest.json`` exists to prove.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .core import canonical
from .core.errors import ContractError, Conflict
from .craft import lint as lint_mod
from .requirements import check as requirements_check, coverage_report
from .service import Service

CONTRACT_PREFIXES = {
    "assessment": "manufacturability_assessment",
    "order": "c2m_order",
    "work-order": "craft_work_order",
    "settlement": "settlement",
    "artisan-review": "artisan_review",
    "enterprise-profile": "enterprise_profile",
    "ip-license": "ip_license",
    "pattern-asset": "pattern_asset",
    "concept": "design_concept",
    "customization-choice": "customization_choice",
    "qc-record": "qc_record",
    "edition": "edition",
    "collector-record": "collector_record",
    "production-schedule": "production_schedule",
    "service-component": "service_component",
    "growth-site": "growth_site",
    "inquiry-lead": "inquiry_lead",
    "character-bible": "character_bible",
    "visual-asset": "visual_asset",
    "short-drama": "short_drama",
    "content-review": "content_review",
    "merch-spec": "merch_spec",
}


def contract_for(filename: str) -> str:
    for prefix in sorted(CONTRACT_PREFIXES, key=len, reverse=True):
        if filename.startswith(f"{prefix}-"):
            return CONTRACT_PREFIXES[prefix]
    raise KeyError(f"cannot infer the contract for {filename}")


def run(root: Path | str | None = None, *, quiet: bool = False) -> dict:
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    out = root / "out"
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(out.iterdir()):
        if path.is_file() and path.suffix in (".json", ".md", ".jsonl", ".html"):
            path.unlink()
    if (out / "site").exists():
        shutil.rmtree(out / "site")

    service = Service(root, root / "var" / "demo", reset=True)

    contracts = _contract_report(service, root)
    rules = _rules_report(service)
    workstation = _workstation(service)
    library = _library(service, root)
    assessments = _assessments(service)
    orders = _orders(service)
    capacity = _capacity_report(service)
    customizations = _customization_report(service, orders)
    editions = _edition_report(service, orders)
    quality = _quality_report(service)
    enterprise = service.enterprise_report()
    growth = _growth_report(service)
    ip = service.ip_report()

    artifacts: dict[str, object] = {}
    artifacts["contract_report.json"] = contracts
    artifacts["rules_report.json"] = rules
    artifacts["workstation_catalog.json"] = workstation
    artifacts["library_snapshot.json"] = library
    artifacts["assessment_results.json"] = assessments
    artifacts["capacity_plan.json"] = capacity
    artifacts["customization_report.json"] = customizations
    artifacts["edition_archive.json"] = editions
    artifacts["quality_report.json"] = quality
    artifacts["enterprise_report.json"] = enterprise
    artifacts["growth_report.json"] = growth
    artifacts["character_bible.json"] = ip["bible"]
    artifacts["ip_asset_library.json"] = {
        "version": ip["version"],
        "asset_summary": ip["asset_summary"],
        "assets": ip["assets"],
    }
    artifacts["short_drama_package.json"] = ip["drama"]
    artifacts["licensing_pack.json"] = {
        "version": ip["version"],
        "license": ip["license"],
        "license_summary": ip["license_summary"],
        "merch_specs": ip["merch_specs"],
        "merch_summary": ip["merch_summary"],
    }
    artifacts["content_review.json"] = {
        "version": ip["version"],
        "summary": {
            "reviews": len(ip["reviews"]),
            "approved": sum(1 for row in ip["reviews"] if row["verdict"] == "approved"),
            "subjects": sorted({row["subject"]["kind"] for row in ip["reviews"]}),
        },
        "reviews": ip["reviews"],
    }

    for name, payload in artifacts.items():
        canonical.dump_json(out / name, payload)

    canonical.write_text(out / "assessment_matrix.md", _assessment_markdown(assessments))
    canonical.write_text(out / "settlement_report.md", _settlement_markdown(orders))
    canonical.write_text(
        out / "coverage_report.md",
        coverage_report(root, later_artifacts=frozenset({"out/sample_reel.html", "out/hash_manifest.json"})),
    )
    canonical.write_text(out / "sample_reel.html", service.ip.reel_html())
    canonical.dump_jsonl(out / "order_trace.jsonl", orders["ledger"])

    files = sorted(
        [
            "assessment_matrix.md",
            "assessment_results.json",
            "capacity_plan.json",
            "character_bible.json",
            "content_review.json",
            "contract_report.json",
            "coverage_report.md",
            "customization_report.json",
            "edition_archive.json",
            "enterprise_report.json",
            "growth_report.json",
            "ip_asset_library.json",
            "library_snapshot.json",
            "licensing_pack.json",
            "order_trace.jsonl",
            "quality_report.json",
            "rules_report.json",
            "sample_reel.html",
            "settlement_report.md",
            "short_drama_package.json",
            "workstation_catalog.json",
        ]
        + list(growth["site_files"])
    )
    manifest = {
        "generated_by": "python -m c2m_craft demo",
        "as_of": service.settings.as_of,
        "files": {name: canonical.file_sha256(out / name) for name in files},
    }
    canonical.dump_json(out / "hash_manifest.json", manifest)

    summary = {
        "artifacts": len(files) + 1,
        "contracts": contracts["summary"],
        "rules": rules["lint"]["totals"],
        "assessments": assessments["agreement"],
        "orders": orders["summary"],
        "enterprise": enterprise["summary"],
        "growth": {
            "site_pages": len(growth["site"]["pages"]),
            "seo_bp": growth["site"]["seo"]["score_bp"],
            "inquiries": growth["crm"]["summary"]["inquiries"],
            "quoted_value_cents": growth["crm"]["summary"]["quoted_value_cents"],
        },
        "ip": ip["summary"],
        "coverage": {
            "ok": assessments["agreement"]["auto_matched"] == assessments["agreement"]["total"],
            "requirements": requirements_check(root)["stats"],
        },
    }
    if not quiet:
        print("[demo] contracts:", contracts["summary"])
        print("[demo] rules:", rules["lint"]["totals"])
        print("[demo] assessments:", assessments["agreement"])
        print("[demo] orders:", orders["summary"])
        print(
            "[demo] capacity:",
            {"schedules": len(capacity["schedules"]), "slots": sum(len(row["slots"]) for row in capacity["schedules"])},
        )
        print("[demo] customisation:", customizations["counts"])
        print("[demo] editions:", editions["counts"])
        print("[demo] quality:", quality["summary"])
        print("[demo] enterprise:", enterprise["summary"])
        print("[demo] growth:", summary["growth"])
        print("[demo] ip:", ip["summary"])
        print(f"[demo] artifacts written: {len(files) + 1} -> {out}")
    return summary


# -- 1. contracts ---------------------------------------------------------
def _contract_report(service: Service, root: Path) -> dict:
    store = service.store
    positives: list[dict] = []
    for asset in service.library.assets:
        issues = store.validate(
            "pattern_asset",
            asset,
            ctx={"as_of": service.settings.as_of, "require_active_window": False},
        )
        positives.append(
            {
                "contract": "pattern_asset",
                "id": asset["asset_id"],
                "source": "samples/library/assets.json",
                "ok": not issues,
                "errors": [issue.as_dict() for issue in issues],
            }
        )
    for concept_id in sorted(service.concepts):
        concept = service.concepts[concept_id]
        issues = store.validate("design_concept", concept)
        positives.append(
            {
                "contract": "design_concept",
                "id": concept_id,
                "source": f"samples/concepts/{concept_id}.json",
                "ok": not issues,
                "errors": [issue.as_dict() for issue in issues],
            }
        )
    positive_dir = root / "samples" / "contracts" / "positive"
    for path in sorted(positive_dir.glob("*.json")):
        contract_id = contract_for(path.name)
        payload = store.json_load(path)
        issues = store.validate(contract_id, payload, ctx={"as_of": service.settings.as_of})
        positives.append(
            {
                "contract": contract_id,
                "id": path.stem,
                "source": f"samples/contracts/positive/{path.name}",
                "ok": not issues,
                "errors": [issue.as_dict() for issue in issues],
            }
        )

    negative_dir = root / "samples" / "contracts" / "negative"
    expected = store.json_load(negative_dir / "expected.json")["samples"]
    negatives: list[dict] = []
    for filename, expectation in sorted(expected.items()):
        payload = store.json_load(negative_dir / filename)
        issues = store.validate(expectation["contract"], payload, ctx={"as_of": service.settings.as_of})
        matched = any(
            (
                issue.invariant == expectation.get("invariant")
                if expectation.get("invariant")
                else issue.keyword == expectation.get("keyword")
            )
            and issue.path.startswith(expectation["path_prefix"])
            for issue in issues
        )
        negatives.append(
            {
                "sample": filename,
                "contract": expectation["contract"],
                "expected": {
                    "keyword": expectation.get("keyword"),
                    "invariant": expectation.get("invariant"),
                    "path_prefix": expectation["path_prefix"],
                },
                "rejected": bool(issues),
                "matched_expected": bool(matched),
                "errors": [issue.as_dict() for issue in issues],
            }
        )

    ok = all(row["ok"] for row in positives) and all(
        row["rejected"] and row["matched_expected"] for row in negatives
    )
    return {
        "registry": {
            "version": service.store.registry["version"],
            "contracts": [
                {
                    "id": entry["id"],
                    "urn": entry["urn"],
                    "version": entry["version"],
                    "invariants": entry.get("invariants", []),
                    "requirements": entry.get("requirements", []),
                }
                for entry in service.store.registry["contracts"]
            ],
        },
        "positives": positives,
        "negatives": negatives,
        "summary": {
            "contracts": len(service.store.registry["contracts"]),
            "positives": len(positives),
            "negatives": len(negatives),
            "ok": ok,
        },
    }


# -- 2. rules -------------------------------------------------------------
def _rules_report(service: Service) -> dict:
    lint = lint_mod.lint_all(service.store, service.settings)
    catalog = []
    for industry in sorted(service.rulesets):
        ruleset = service.rulesets[industry]
        for rule in ruleset.rules:
            catalog.append(
                {
                    "rule_id": rule["id"],
                    "industry": industry,
                    "process": rule["process"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "review_tier": rule["review"]["tier"],
                    "review_trigger": rule["review"]["trigger"],
                    "source_type": rule["evidence"]["source_type"],
                    "confidence": rule["evidence"]["confidence"],
                    "references": rule.get("references", []),
                    "version": rule["version"],
                }
            )
    facts_used = {}
    for industry in sorted(service.rulesets):
        ruleset = service.rulesets[industry]
        used = set()
        for rule in ruleset.rules:
            used |= lint_mod.condition_facts(rule["when"])
            if rule.get("applies_when"):
                used |= lint_mod.condition_facts(rule["applies_when"])
        facts_used[industry] = {
            "declared": len(ruleset.facts_schema),
            "used_by_rules": len(used),
            "unused": sorted(set(ruleset.facts_schema) - used),
        }
    return {
        "lint": {
            "ok": lint["ok"],
            "findings": lint["findings"],
            "totals": lint["totals"],
            "industries": lint["industries"],
        },
        "catalog": catalog,
        "facts": facts_used,
        "rule_versions": {
            industry: {
                "version": service.rulesets[industry].version,
                "as_of": service.rulesets[industry].as_of,
            }
            for industry in sorted(service.rulesets)
        },
    }


# -- 3. workstation -------------------------------------------------------
def _workstation(service: Service) -> dict:
    briefs = [
        {
            "brief_id": "brief-jewelry",
            "text": "a coastal heritage pendant series for duty free retail, interlace and fret motifs",
            "industry": "jewelry",
            "style_id": "coastal_minimal",
            "count": 4,
        },
        {
            "brief_id": "brief-hardwood",
            "text": "a carved hardwood console for a boutique hotel lobby, tide and vine motifs",
            "industry": "hardwood",
            "style_id": "heritage_ornate",
            "count": 4,
        },
    ]
    concepts: list[dict] = []
    generated_by_brief: dict[str, list[str]] = {}
    for brief in briefs:
        created = service.generate(
            brief["text"], brief["industry"], count=brief["count"], style_id=brief["style_id"]
        )
        generated_by_brief[brief["brief_id"]] = [item["concept_id"] for item in created]
        concepts.extend(created)
    series = service.expand_series(concepts[0]["concept_id"])
    return {
        "adapter": {
            "name": "offline_lexicon",
            "version": "1.0.0",
            "deterministic": True,
            "limitation": "curated vocabulary and parameter-level transforms; a generative model plugs in at the ConceptModelAdapter boundary in M2",
        },
        "briefs": briefs,
        "generated_by_brief": generated_by_brief,
        "concepts": concepts,
        "series": series,
        "counts": {"concepts": len(concepts), "series_skus": len(series)},
    }


# -- 4. library -----------------------------------------------------------
def _library(service: Service, root: Path) -> dict:
    assets = []
    for asset in service.library.assets:
        assets.append(
            {
                "asset_id": asset["asset_id"],
                "title": asset["title"],
                "industries": asset["industries"],
                "medium": asset["medium"],
                "license": service.library.license_state(asset),
            }
        )
    queries = [
        {"query": "interlace", "tags": [], "palette": [], "industry": None},
        {"query": "", "tags": ["coastal"], "palette": [], "industry": None},
        {"query": "carved", "tags": [], "palette": ["#C9A227", "#1F2A44"], "industry": "hardwood"},
    ]
    searches = []
    for query in queries:
        hits = service.library.search(
            query=query["query"],
            tags=query["tags"],
            palette=query["palette"],
            industry=query["industry"],
            limit=5,
        )
        searches.append(
            {
                "query": query,
                "results": [
                    {
                        "asset_id": hit["asset"]["asset_id"],
                        "title": hit["asset"]["title"],
                        "score": hit["score"],
                        "matched": hit["matched"],
                        "license_ok": hit["license"]["ok"],
                    }
                    for hit in hits
                ],
            }
        )

    rejections = []
    for case in service.store.json_load(root / "samples" / "library" / "rejected.json")["cases"]:
        try:
            service.ingest_asset(case["payload"])
            rejected = False
            errors = []
        except ContractError as exc:
            rejected = True
            errors = exc.details
        rejections.append(
            {
                "name": case["name"],
                "reason": case["reason"],
                "rejected": rejected,
                "errors": errors,
            }
        )
    accepted = service.ingest_asset(
        {
            "asset_id": "PA-JW-0005",
            "title": {"zh": "注入测试纹样", "en": "Ingest smoke pattern"},
            "industries": ["jewelry"],
            "medium": "pattern",
            "tags": ["ingest", "smoke"],
            "palette": ["#C9A227", "#1F2A44"],
            "preview": {"motif_style": "fret", "texture": "polished", "gradient_angle_deg": 30},
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
    )
    return {
        "assets": assets,
        "counts": {"assets": len(assets), "searches": len(searches), "rejections": len(rejections)},
        "searches": searches,
        "rejections": rejections,
        "accepted_ingest": {
            "asset_id": accepted["asset_id"],
            "license": service.library.license_state(accepted),
        },
        "rejection_summary": {
            "rejected": sum(1 for row in rejections if row["rejected"]),
            "total": len(rejections),
        },
    }


# -- 5. assessments -------------------------------------------------------
def _assessments(service: Service) -> dict:
    expected = service.expected_table()
    rows: list[dict] = []
    matched = 0
    total = 0
    for concept_id in sorted(expected["concepts"]):
        concept = service.concept(concept_id)
        for workshop_id in sorted(expected["concepts"][concept_id]["workshops"]):
            want = expected["concepts"][concept_id]["workshops"][workshop_id]
            assessment = service.assess_at(concept, workshop_id)
            auto_ok = assessment["auto"]["verdict"] == want["verdict"]
            blockers_ok = all(rule in assessment["blockers"] for rule in want["must_fail"])
            matched += 1 if (auto_ok and blockers_ok) else 0
            total += 1
            rows.append(
                {
                    "concept_id": concept_id,
                    "workshop_id": workshop_id,
                    "industry": concept["industry"],
                    "expected_verdict": want["verdict"],
                    "expected_blockers": want["must_fail"],
                    "auto_verdict": assessment["auto"]["verdict"],
                    "match": bool(auto_ok and blockers_ok),
                    "assessment_id": assessment["assessment_id"],
                }
            )

    decisions = []
    for concept_id, workshop_id, verdict, reason in (
        (
            "DC-0002",
            "WS-JW-A",
            "not_manufacturable",
            "Confirmed: 0.3 mm wall plus an unset 8.5 mm stone cannot be produced at this workshop.",
        ),
        (
            "DC-0003",
            "WS-JW-B",
            "conditionally_manufacturable",
            "Workshop B will route the casting to the vacuum caster of workshop A inside the same order; "
            "the reviewer accepts the 0.7 mm wall with a core support and a re-inspection after casting.",
        ),
    ):
        row = next(
            item for item in rows if item["concept_id"] == concept_id and item["workshop_id"] == workshop_id
        )
        assessment = service.commerce.assessments[row["assessment_id"]]
        queue_id = (assessment.get("artisan") or {}).get("queue_id")
        if not queue_id:
            decisions.append({"concept_id": concept_id, "workshop_id": workshop_id, "queued": False})
            continue
        result = service.decide_review(queue_id, verdict, reason)
        updated = result["assessment"] or assessment
        row["final_verdict"] = updated["final_verdict"]
        row["review"] = {
            "queue_id": queue_id,
            "status": updated["artisan"]["status"],
            "reviewer": updated["artisan"]["reviewer"],
            "decision_verdict": updated["artisan"]["decision_verdict"],
            "notes": updated["artisan"]["notes"],
        }
        decisions.append(row["review"] | {"concept_id": concept_id, "workshop_id": workshop_id})

    counterexamples = []
    for concept_id in expected["counterexamples"]:
        for row in rows:
            if row["concept_id"] != concept_id:
                continue
            assessment = service.commerce.assessments[row["assessment_id"]]
            counterexamples.append(
                {
                    "concept_id": concept_id,
                    "workshop_id": row["workshop_id"],
                    "verdict": assessment["final_verdict"],
                    "blockers": assessment["blockers"],
                    "fix_count": len(assessment["fixes"]),
                    "missing_facts": assessment["missing_facts"],
                    "first_fix": assessment["fixes"][0]["text"] if assessment["fixes"] else None,
                }
            )

    return {
        "agreement": {"auto_matched": matched, "total": total},
        "rules": {
            industry: service.rulesets[industry].stats() for industry in sorted(service.rulesets)
        },
        "rows": rows,
        "decisions": decisions,
        "counterexamples": counterexamples,
        "assessments": [
            service.commerce.assessments[key]
            for key in sorted(service.commerce.assessments)
        ],
        "reviews": list(service.reviews.items),
    }


def _assessment_markdown(result: dict) -> str:
    lines = ["# Manufacturability matrix", ""]
    lines.append(
        "Ten concept inputs against two workshops each. The auto verdict comes from the deterministic "
        "engine; the final verdict folds in the craftsperson's decision where a review was requested."
    )
    lines.append("")
    lines.append(f"Agreement with the hand-written expectation table: {result['agreement']['auto_matched']}/{result['agreement']['total']}")
    lines.append("")
    lines.append("| Concept | Workshop | Auto | Final | Blockers | Fixes |")
    lines.append("|---|---|---|---|---|---|")
    for row in result["rows"]:
        assessment = next(
            item for item in result["assessments"] if item["assessment_id"] == row["assessment_id"]
        )
        fixes = str(len(assessment["fixes"]))
        lines.append(
            f"| {row['concept_id']} | {row['workshop_id']} | {row['auto_verdict']} | "
            f"{assessment['final_verdict']} | {', '.join(assessment['blockers']) or '-'} | {fixes} |"
        )
    lines.append("")
    lines.append("## Counterexamples")
    lines.append("")
    for case in result["counterexamples"]:
        lines.append(
            f"- {case['concept_id']} at {case['workshop_id']}: {case['verdict']}, blockers "
            f"{', '.join(case['blockers'])}, {case['fix_count']} fix suggestion(s)"
        )
    lines.append("")
    lines.append("## Artisan review decisions")
    lines.append("")
    for decision in result["decisions"]:
        if not decision.get("queue_id"):
            lines.append(f"- {decision['concept_id']} at {decision['workshop_id']}: no review was required")
            continue
        lines.append(
            f"- {decision['queue_id']} ({decision['concept_id']} at {decision['workshop_id']}): "
            f"{decision['status']} by {decision['reviewer']} -> {decision['decision_verdict']}"
        )
    lines.append("")
    return "\n".join(lines)


# -- 6. orders ------------------------------------------------------------
def _orders(service: Service) -> dict:
    commerce = service.commerce
    cases: list[dict] = []

    order = service.create_order("DC-0001", model="designer_presale")
    steps = [
        ("presale_opened", {"kind": "designer", "id": "designer-01"}),
        ("payment_received", {"kind": "buyer", "id": "buyer-01"}),
        ("work_order_issued", {"kind": "system", "id": "system"}),
        ("dispatched", {"kind": "factory", "id": "workshop-01"}),
        ("production_started", {"kind": "factory", "id": "workshop-01"}),
        ("qc_passed", {"kind": "artisan", "id": "ART-JW-01"}),
        ("shipped", {"kind": "factory", "id": "workshop-01"}),
        ("settled", {"kind": "system", "id": "system"}),
    ]
    for event, actor in steps:
        commerce.transition(order["order_id"], event, actor=actor)
    settled = service.order(order["order_id"])
    settlement = commerce.settlement_for(order["order_id"])
    cases.append(
        {
            "case": "designer pre-sale settled",
            "order_id": settled["order_id"],
            "final_status": settled["status"],
            "events": len(service.order_events(settled["order_id"])),
            "total_cents": settled["amounts"]["total_cents"],
            "settlement_id": settlement["settlement_id"],
        }
    )

    refund = service.create_order("DC-0005", model="designer_presale")
    commerce.transition(refund["order_id"], "presale_opened", actor={"kind": "designer", "id": "designer-01"})
    commerce.transition(refund["order_id"], "payment_received", actor={"kind": "buyer", "id": "buyer-02"})
    commerce.request_refund(refund["order_id"], "The collector moved the commission to another quarter.")
    commerce.decide_refund(refund["order_id"], approve=True)
    commerce.execute_refund(refund["order_id"])
    refunded = service.order(refund["order_id"])
    cases.append(
        {
            "case": "full refund after payment",
            "order_id": refunded["order_id"],
            "final_status": refunded["status"],
            "events": len(service.order_events(refunded["order_id"])),
            "refund_cents": refunded["refund"]["amount_cents"],
            "total_cents": refunded["amounts"]["total_cents"],
        }
    )

    disputed = service.create_order("DC-0004", model="designer_presale")
    for event, actor in (
        ("presale_opened", {"kind": "designer", "id": "designer-01"}),
        ("payment_received", {"kind": "buyer", "id": "buyer-03"}),
        ("work_order_issued", {"kind": "system", "id": "system"}),
        ("dispatched", {"kind": "factory", "id": "workshop-01"}),
    ):
        commerce.transition(disputed["order_id"], event, actor=actor)
    dispute_inspection = service.record_qc(
        disputed["order_id"],
        "QC-03",
        verdict="rework",
        defects=[{"code": "finish_defect", "count": 2, "note": "enamel fired two shades light"}],
        inspector="ART-JW-01",
    )
    commerce.open_dispute(
        disputed["order_id"],
        "The enamel colour is two shades off the approved sample.",
        qc_record_ids=[dispute_inspection["qc_id"]],
    )
    commerce.resolve_dispute(
        disputed["order_id"],
        "split",
        "Buyer keeps the piece at half price; the workshop absorbs the rework labour.",
    )
    resolved = service.order(disputed["order_id"])
    split_settlement = commerce.settlement_for(disputed["order_id"])
    cases.append(
        {
            "case": "dispute resolved by split settlement",
            "order_id": resolved["order_id"],
            "final_status": resolved["status"],
            "events": len(service.order_events(resolved["order_id"])),
            "refund_cents": resolved["refund"]["amount_cents"],
            "settlement_id": split_settlement["settlement_id"],
            "settled_cents": split_settlement["total_cents"],
            "qc_evidence": resolved["dispute"]["qc_record_ids"],
        }
    )

    blocked = False
    blocked_reason = ""
    try:
        service.create_order("DC-0002", model="designer_presale")
    except Conflict as exc:
        blocked = True
        blocked_reason = exc.message
    cases.append(
        {
            "case": "order refused for a non-manufacturable concept",
            "order_id": None,
            "blocked": blocked,
            "reason": blocked_reason,
        }
    )

    # -- M2: participatory customisation ---------------------------------
    selections = [
        {"group_id": "alloy", "option_id": "alloy_22k"},
        {"group_id": "engraving", "option_id": "engraving_light"},
    ]
    preview = service.build_customization("DC-0001", selections, register=False)
    custom_order = service.create_order(
        "DC-0001",
        model="participatory_customization",
        selections=selections,
        buyer={"id": "buyer-05", "locale": "en"},
    )
    custom_choice = commerce.customizations[custom_order["items"][0]["customization_id"]]
    for event, actor in steps:
        commerce.transition(custom_order["order_id"], event, actor=actor)
    custom_settled = service.order(custom_order["order_id"])
    cases.append(
        {
            "case": "participatory customisation settled",
            "order_id": custom_settled["order_id"],
            "final_status": custom_settled["status"],
            "events": len(service.order_events(custom_settled["order_id"])),
            "total_cents": custom_settled["amounts"]["total_cents"],
            "customization_id": custom_choice["customization_id"],
            "derived_concept": custom_settled["items"][0]["concept_id"],
            "delta_cents": custom_choice["amounts"]["delta_cents"],
            "settlement_id": commerce.settlement_for(custom_settled["order_id"])["settlement_id"],
        }
    )

    # -- M2: licensed asset with a royalty split -------------------------
    licensed_order = service.create_order(
        "DC-0010",
        buyer={"id": "buyer-06", "locale": "en"},
        asset_license_ids=["PA-JW-0001"],
    )
    for event, actor in steps:
        commerce.transition(licensed_order["order_id"], event, actor=actor)
    licensed_settled = service.order(licensed_order["order_id"])
    royalty_settlement = commerce.settlement_for(licensed_order["order_id"])
    cases.append(
        {
            "case": "licensed asset order with royalty split",
            "order_id": licensed_settled["order_id"],
            "final_status": licensed_settled["status"],
            "events": len(service.order_events(licensed_settled["order_id"])),
            "total_cents": licensed_settled["amounts"]["total_cents"],
            "settlement_id": royalty_settlement["settlement_id"],
            "royalty_lines": len(royalty_settlement.get("royalty_lines") or []),
        }
    )

    # -- M2: limited edition and collector archive -----------------------
    edition = service.editions.create(
        concept_id="DC-0009",
        size=5,
        artist={
            "artist_id": "ARTIST-01",
            "name": "Studio Lin (synthetic)",
            "royalty_rate_bp": 800,
        },
        workshop_id="WS-HW-A",
        created_at=service.clock.now,
    )
    edition_order = service.create_order(
        "DC-0009",
        model="artist_manufacturer",
        edition_id=edition["edition_id"],
        workshop_id="WS-HW-A",
        buyer={"id": "buyer-07", "locale": "en"},
    )
    for event, actor in steps:
        commerce.transition(edition_order["order_id"], event, actor=actor)
    edition_settled = service.order(edition_order["order_id"])
    issued_records = [
        row for row in service.editions.records.values() if row["edition_id"] == edition["edition_id"]
    ]
    transferred = service.editions.transfer(
        issued_records[0]["record_id"],
        owner_id="OWNER-C2",
        display_name="Collector Two",
        at=service.clock.now,
        note="private sale with the certificate handed over",
    )
    cases.append(
        {
            "case": "limited edition settled and archived",
            "order_id": edition_settled["order_id"],
            "final_status": edition_settled["status"],
            "events": len(service.order_events(edition_settled["order_id"])),
            "total_cents": edition_settled["amounts"]["total_cents"],
            "edition_id": edition["edition_id"],
            "edition_number": edition_settled["items"][0]["edition_number"],
            "certificate_id": transferred["certificate_id"],
        }
    )

    # -- M2: quality inspection with a defect ----------------------------
    qc_order = service.create_order("DC-0004", buyer={"id": "buyer-08", "locale": "en"})
    for event, actor in (
        ("presale_opened", {"kind": "designer", "id": "designer-01"}),
        ("payment_received", {"kind": "buyer", "id": "buyer-08"}),
        ("work_order_issued", {"kind": "system", "id": "system"}),
        ("dispatched", {"kind": "factory", "id": "workshop-01"}),
        ("production_started", {"kind": "factory", "id": "workshop-01"}),
    ):
        commerce.transition(qc_order["order_id"], event, actor=actor)
    inspection_pass = service.record_qc(
        qc_order["order_id"],
        "QC-01",
        verdict="pass",
        defects=[{"code": "surface_scratch", "count": 1, "note": "faint polish mark on the reverse"}],
        inspector="ART-JW-01",
    )
    inspection_fail = service.record_qc(
        qc_order["order_id"],
        "QC-02",
        verdict="fail",
        defects=[{"code": "setting_loose", "count": 1, "note": "stone moves 0.1 mm in the bezel"}],
        inspector="ART-JW-01",
    )
    commerce.transition(qc_order["order_id"], "qc_failed", actor={"kind": "artisan", "id": "ART-JW-01"})
    commerce.transition(qc_order["order_id"], "rework_started", actor={"kind": "factory", "id": "workshop-01"})
    cases.append(
        {
            "case": "quality inspection failed and returned for rework",
            "order_id": qc_order["order_id"],
            "final_status": service.order(qc_order["order_id"])["status"],
            "events": len(service.order_events(qc_order["order_id"])),
            "qc_records": [inspection_pass["qc_id"], inspection_fail["qc_id"]],
            "settlement_id": None,
        }
    )

    return {
        "cases": cases,
        "orders": [
            service.order(order_id) for order_id in sorted(commerce.orders)
        ],
        "work_orders": [
            commerce.work_orders[key] for key in sorted(commerce.work_orders)
        ],
        "settlements": [
            commerce.settlements[key] for key in sorted(commerce.settlements)
        ],
        "ledger": service.ledger.export(),
        "ledger_check": service.ledger.verify(),
        "customization": {
            "preview": preview,
            "applied": custom_choice,
            "order_id": custom_settled["order_id"],
        },
        "edition": {
            "edition": service.editions.edition(edition["edition_id"]),
            "record": transferred,
        },
        "summary": {
            "orders": len(commerce.orders),
            "work_orders": len(commerce.work_orders),
            "settlements": len(commerce.settlements),
            "ledger_events": len(service.ledger.events),
            "ledger_verified": service.ledger.verify()["ok"],
            "blocked_work_order": any(case.get("blocked") for case in cases),
            "customizations": len(commerce.customizations),
            "editions": len(service.editions.editions),
            "collector_records": len(service.editions.records),
            "quality_records": len(service.quality.records),
        },
    }


def _capacity_report(service: Service) -> dict:
    schedules = service.schedules(at=service.clock.now)
    summary = []
    for schedule in schedules:
        summary.append(
            {
                "workshop_id": schedule["workshop_id"],
                "capacity_per_day_minutes": schedule["capacity_per_day_minutes"],
                "slots": len(schedule["slots"]),
                "booked_minutes": sum(slot["minutes"] for slot in schedule["slots"]),
                "days_listed": len(schedule["utilization"]),
                "peak_utilization_bp": max(
                    (
                        (row["booked_minutes"] * 10000) // max(row["capacity_minutes"], 1)
                        for row in schedule["utilization"]
                    ),
                    default=0,
                ),
            }
        )
    return {
        "as_of": service.settings.as_of,
        "capacity": service.settings.json("config/commerce/capacity.json"),
        "schedules": schedules,
        "summary": summary,
    }


def _customization_report(service: Service, orders: dict) -> dict:
    catalog = {
        industry: service.catalog.describe(industry)
        for industry in service.settings.industry_ids()
    }
    preview = orders["customization"]["preview"]
    applied = orders["customization"]["applied"]
    return {
        "catalog": catalog,
        "preview": {
            "base_concept_id": preview["choice"]["base_concept_id"],
            "derived_concept_id": (preview["derived_concept"] or {}).get("concept_id"),
            "choice": preview["choice"],
            "quote": preview["quote"],
        },
        "applied": {
            "order_id": orders["customization"]["order_id"],
            "choice": applied,
        },
        "counts": {
            "industries": len(catalog),
            "groups": sum(len(catalog[industry]["groups"]) for industry in catalog),
            "options": sum(
                len(group["options"]) for industry in catalog for group in catalog[industry]["groups"]
            ),
            "conflicts": sum(len(catalog[industry]["conflicts"]) for industry in catalog),
            "choices_recorded": len(service.commerce.customizations),
        },
    }


def _edition_report(service: Service, orders: dict) -> dict:
    edition = orders["edition"]["edition"]
    record = orders["edition"]["record"]
    return {
        "editions": [
            {
                "edition_id": row["edition_id"],
                "title": row["title"],
                "artist": row["artist"],
                "manufacturer": row["manufacturer"],
                "concept_id": row["concept_id"],
                "size": row["size"],
                "status": row["status"],
                "issued": len(row["numbering"]["issued"]),
                "reserved": row["numbering"]["reserved"],
                "issued_numbers": [item["number"] for item in row["numbering"]["issued"]],
            }
            for _, row in sorted(service.editions.editions.items())
        ],
        "collector_records": service.editions.archive(),
        "certificate": record,
        "certificate_summary": {
            "record_id": record["record_id"],
            "certificate_id": record["certificate_id"],
            "certificate_hash": record["certificate_hash"],
            "edition_id": record["edition_id"],
            "edition_number": record["edition_number"],
            "owner": record["owner"],
            "provenance": record["provenance"],
        },
        "edition_detail": edition,
        "counts": {
            "editions": len(service.editions.editions),
            "collector_records": len(service.editions.records),
            "certificates": sum(len(row["numbering"]["issued"]) for row in service.editions.editions.values()),
        },
    }


def _quality_report(service: Service) -> dict:
    config = service.settings.json("config/commerce/quality.json")
    return {
        "taxonomy": config["defect_codes"],
        "sampling_plans": config["sampling_plans"],
        "records": service.quality.records,
        "summary": service.quality.summary(),
    }


def _settlement_markdown(orders: dict) -> str:
    lines = ["# Settlement and coordination report", ""]
    lines.append("## Order cases")
    lines.append("")
    lines.append("| Case | Order | Final status | Events | Amount (cents) |")
    lines.append("|---|---|---|---|---|")
    for case in orders["cases"]:
        amount = case.get("settled_cents") or case.get("total_cents") or 0
        lines.append(
            f"| {case['case']} | {case['order_id']} | {case.get('final_status', 'blocked')} | "
            f"{case.get('events', 0)} | {amount} |"
        )
    lines.append("")
    lines.append("## Payout lines")
    lines.append("")
    for settlement in orders["settlements"]:
        lines.append(
            f"### {settlement['settlement_id']} (order {settlement['order_id']}, total "
            f"{settlement['total_cents']} cents)"
        )
        lines.append("")
        lines.append("| Party | Party id | Rate (bp) | Amount (cents) |")
        lines.append("|---|---|---|---|")
        for line in settlement["payout_lines"]:
            lines.append(
                f"| {line['party']} | {line['party_id']} | {line['rate_bp']} | {line['amount_cents']} |"
            )
        lines.append("")
        lines.append(
            f"Remainder distributed by largest-remainder rounding: {settlement['remainder_cents']} cent(s). "
            f"Reconciliation: payouts {settlement['reconciliation']['sum_payouts_cents']} cents, "
            f"delta {settlement['reconciliation']['delta_cents']}."
        )
        lines.append("")
        if settlement["refunds"]:
            for refund in settlement["refunds"]:
                lines.append(
                    f"- Refund recorded before posting: {refund['amount_cents']} cents "
                    f"({refund['kind']}, milestone {refund['milestone']})"
                )
            lines.append("")
        if settlement.get("royalty_lines"):
            lines.append("Royalty allocation inside the IP share:")
            lines.append("")
            lines.append("| Asset | Licensor | Rate (bp) | Amount (cents) |")
            lines.append("|---|---|---|---|")
            for line in settlement["royalty_lines"]:
                lines.append(
                    f"| {line['asset_id']} | {line['licensor']} | {line['rate_bp']} | "
                    f"{line['amount_cents']} |"
                )
            lines.append("")
    lines.append("## Delivery promises")
    lines.append("")
    lines.append("| Order | Workshop | Promised | Working minutes | Alternatives |")
    lines.append("|---|---|---|---|---|")
    for order in orders["orders"]:
        promise = order.get("promise") or {}
        lines.append(
            f"| {order['order_id']} | {promise.get('workshop_id', '-')} | "
            f"{promise.get('promised_delivery_at', '-')} | "
            f"{promise.get('working_minutes', '-')} | {len(promise.get('alternatives') or [])} |"
        )
    lines.append("")
    ledger = orders["ledger_check"]
    lines.append("## Ledger")
    lines.append("")
    lines.append(
        f"- Events: {ledger['events']}, orders: {ledger['orders']}, verified: {ledger['ok']}"
    )
    lines.append(f"- Head: {ledger['head']}")
    lines.append("")
    return "\n".join(lines)


def _growth_report(service: Service) -> dict:
    """Generate the multilingual site, audit it, then drive three inquiries through the CRM."""
    out = service.root / "out"
    site = service.growth_site()
    site_files = service.growth.write(site, out / "site")
    negative = service.growth.negative_audit(site)
    crm = service.growth.crm

    def intake(payload: dict) -> dict:
        service.clock.advance(4)
        return crm.intake(payload, at=service.clock.now)

    def advance(record: dict, stage: str, note: str) -> dict:
        service.clock.advance(9)
        return crm.advance(record["inquiry_id"], stage, at=service.clock.now, note=note)

    bulk = intake(
        {
            "site_id": "SITE-JW-01",
            "language": "en",
            "contact": {
                "name": "Anna Weber",
                "email": "anna.weber@nordlicht-retail.example",
                "company": "Nordlicht Retail (synthetic)",
                "country": "DE",
                "channel": "site_form",
            },
            "message": "We need 500 pcs of the coastal pendant for the winter season, gift boxed for the German market.",
            "intent": "bulk_quote",
            "product_interest": ["coastal pendant", "limited edition"],
        }
    )
    advance(bulk, "contacted", "called the buyer and confirmed the assortment and the gift box")
    advance(bulk, "quoted", "sent the bulk quotation with the working-day delivery window")
    advance(bulk, "won", "buyer confirmed the pilot order by email")

    sample = intake(
        {
            "site_id": "SITE-JW-01",
            "language": "zh",
            "contact": {
                "name": "林晓",
                "email": "lin.xiao@harbour-buyer.example",
                "country": "CN",
                "channel": "site_form",
            },
            "message": "想先看两件样品，确认纹样授权与表面处理之后再谈批量。",
            "intent": "sample_request",
            "product_interest": ["双守纹样吊坠"],
        }
    )
    advance(sample, "contacted", "外贸同事已回信并约定寄样时间")

    info = intake(
        {
            "site_id": "SITE-JW-01",
            "language": "de",
            "contact": {
                "name": "Jonas Keller",
                "email": "jonas.keller@marktdesk.example",
                "company": "Marktdesk Studio (synthetic)",
                "country": "US",
                "channel": "trade_show",
            },
            "message": "We met at the trade show and would like the licensing deck before the next season.",
            "intent": "information",
            "product_interest": ["licensing deck"],
        }
    )
    advance(info, "lost", "the buyer only wanted the licensing deck and no order followed this season")

    report = service.growth.report(now=service.clock.now, site_record=site)
    report["site_files"] = site_files
    report["negative_audit"] = {
        "description": "the same site with one page description stripped, to prove the auditor detects it",
        "score_bp": negative["seo"]["score_bp"],
        "issues": [
            {"code": issue["code"], "severity": issue["severity"], "page_id": issue["page_id"]}
            for issue in negative["seo"]["issues"]
        ],
    }
    return report


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
