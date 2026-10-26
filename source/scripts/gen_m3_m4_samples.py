"""Generate the contract samples for the M3 email and growth contracts and the M4 IP contracts.

Run from the delivery root:

    python scripts/gen_m3_m4_samples.py

Every positive sample is taken from the runtime, so a fixture that drifts from the
engine fails loudly.  Every negative sample is a documented mutation and carries
the expected rejection class (invariant id plus instance path), the same format the
M1/M2 suite uses.  The expectations are merged into the existing expected.json.
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
from c2m_craft.service import Service  # noqa: E402

POSITIVE_DIR = ROOT / "samples" / "contracts" / "positive"
NEGATIVE_DIR = ROOT / "samples" / "contracts" / "negative"
AS_OF = "2026-10-23T00:00:00Z"


def write_json(path: Path, value) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")


def run() -> int:
    store = SchemaStore(ROOT)
    service = Service(ROOT, ROOT / "var" / "samples_m34", reset=True)
    ip = service.ip
    component = service.enterprise.registry.components[0]
    site = service.growth_site()
    inquiry = service.growth.crm.intake(
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
            "message": "We need 500 pcs of the coastal pendant for the winter season.",
            "intent": "bulk_quote",
            "product_interest": ["coastal pendant"],
        },
        at=AS_OF,
    )

    positives: dict[str, tuple[str, dict]] = {
        "service-component-kb-craft.json": ("service_component", component),
        "enterprise-profile-EP-0001.json": (
            "enterprise_profile",
            store.json_load(ROOT / "config" / "enterprise" / "profiles" / "EP-0001.json"),
        ),
        "growth-site-SITE-JW-01.json": ("growth_site", site),
        "inquiry-lead-INQ-0001.json": ("inquiry_lead", inquiry),
        "character-bible-IPB-0001.json": ("character_bible", ip.bible),
        "visual-asset-VA-MU-TURN-FRONT.json": ("visual_asset", ip.asset("VA-MU-TURN-FRONT")),
        "short-drama-SDR-0001.json": ("short_drama", ip.drama),
        "content-review-CRV-0001.json": ("content_review", ip.reviews["CRV-0001"]),
        "merch-spec-MS-0001.json": ("merch_spec", ip.merch_specs[0]),
        "ip-license-IPL-0001.json": ("ip_license", ip.license),
    }
    written = []
    for filename, (contract_id, payload) in sorted(positives.items()):
        issues = store.validate(contract_id, payload, ctx={"as_of": AS_OF})
        if issues:
            raise SystemExit(f"{filename} invalid: {format_issues(issues)}")
        write_json(POSITIVE_DIR / filename, payload)
        written.append(filename)

    def mutate(payload: dict) -> dict:
        return copy.deepcopy(payload)

    negatives: list[tuple[str, str, dict, dict]] = []

    case = mutate(component)
    case["depends_on"] = [case["component_id"]]
    negatives.append(
        ("service-component-self-dependency.json", "service_component", case,
         {"invariant": "INV-COMP-01", "path_prefix": "$"})
    )

    case = mutate(positives["enterprise-profile-EP-0001.json"][1])
    for entry in case["components"]:
        if entry["component_id"] == "crm_leads":
            entry["enabled"] = False
    negatives.append(
        ("enterprise-profile-crm-channel-missing.json", "enterprise_profile", case,
         {"invariant": "INV-ENT-01", "path_prefix": "$"})
    )

    case = mutate(site)
    case["pages"][0]["hreflang"] = case["pages"][0]["hreflang"][:-1]
    negatives.append(
        ("growth-site-hreflang-gap.json", "growth_site", case,
         {"invariant": "INV-SEO-01", "path_prefix": "$"})
    )

    case = mutate(site)
    case["pages"][0]["title"] = "Short title"
    negatives.append(
        ("growth-site-title-too-short.json", "growth_site", case,
         {"invariant": "INV-SEO-01", "path_prefix": "$"})
    )

    case = mutate(inquiry)
    case["lead"]["score"] = min(100, int(case["lead"]["score"]) + 10)
    negatives.append(
        ("inquiry-lead-score-mismatch.json", "inquiry_lead", case,
         {"invariant": "INV-LEAD-01", "path_prefix": "$"})
    )

    case = mutate(ip.bible)
    case["heritage_refs"][0]["exclusive_claimed"] = True
    negatives.append(
        ("character-bible-heritage-exclusive.json", "character_bible", case,
         {"invariant": "INV-CHAR-01", "path_prefix": "$"})
    )

    case = mutate(ip.asset("VA-MU-TURN-FRONT"))
    case["recipe"]["layers"][0]["fill"] = "#FFFFFF"
    negatives.append(
        ("visual-asset-checksum-mismatch.json", "visual_asset", case,
         {"invariant": "INV-ASSET-01", "path_prefix": "$"})
    )

    case = mutate(ip.drama)
    last = case["cut"]["edl"][-1]
    last["in_tc"] = "00:00:59"
    negatives.append(
        ("short-drama-timecode-gap.json", "short_drama", case,
         {"invariant": "INV-DRAMA-01", "path_prefix": "$"})
    )

    case = mutate(ip.reviews["CRV-0001"])
    case["checklist"][0]["verdict"] = "fail"
    case["checklist"][0]["note"] = "the heritage sentence over-claims ownership"
    negatives.append(
        ("content-review-approved-with-fail.json", "content_review", case,
         {"invariant": "INV-CONTENT-01", "path_prefix": "$"})
    )

    case = mutate(ip.merch_specs[0])
    case["packaging"]["label_requirements"] = ["licence number"]
    case["quality"]["inspection_points"] = ["motif depth matches the render", "packaging matches"]
    negatives.append(
        ("merch-spec-missing-authenticity-label.json", "merch_spec", case,
         {"invariant": "INV-MERCH-01", "path_prefix": "$"})
    )

    case = mutate(ip.license)
    for document in case["documents"]:
        document["status"] = "draft"
    negatives.append(
        ("ip-license-draft-only-coverage.json", "ip_license", case,
         {"invariant": "INV-IP-02", "path_prefix": "$"})
    )

    expected = store.json_load(NEGATIVE_DIR / "expected.json")["samples"]
    for filename, contract_id, payload, expectation in negatives:
        issues = store.validate(contract_id, payload, ctx={"as_of": AS_OF})
        if not issues:
            raise SystemExit(f"{filename} was accepted by the contract")
        matched = any(
            (issue.invariant == expectation.get("invariant") if expectation.get("invariant")
             else issue.keyword == expectation.get("keyword"))
            and issue.path.startswith(expectation["path_prefix"])
            for issue in issues
        )
        if not matched:
            raise SystemExit(f"{filename}: expected {expectation} but got {format_issues(issues)}")
        write_json(NEGATIVE_DIR / filename, payload)
        expected[filename] = {
            "contract": contract_id,
            **expectation,
            "error_count": len(issues),
        }

    write_json(
        NEGATIVE_DIR / "expected.json",
        {"version": "1.0.0", "samples": dict(sorted(expected.items()))},
    )
    print(
        f"[gen_m3_m4_samples] positives: {len(positives)}, negatives: {len(negatives)}, "
        f"expected total: {len(expected)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
