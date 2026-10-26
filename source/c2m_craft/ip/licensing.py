"""Licensing package: signed document set, merchandise specifications and review links.

The licence record carries the two guardians, the usage block, the quality
specification, the signed document set (with a checksum per document) and the
merchandise specifications.  Invariants prove that every licensed derivative
category has a signed document and that heritage stays non-exclusive.
"""

from __future__ import annotations

from ..core import canonical
from ..core.errors import ValidationFailed

DOCUMENT_FIELDS = (
    "document_id",
    "kind",
    "status",
    "derivative_categories",
    "signatories",
    "file_ref",
)


def _document_checksum(document: dict) -> str:
    return canonical.content_hash({field: document[field] for field in DOCUMENT_FIELDS})


def build_merch_specs(store, settings, reviews: dict[str, dict]) -> list[dict]:
    config = settings.json("config/ip/licensing.json")
    index = {
        (review["subject"]["kind"], review["subject"]["ref"]): review_id
        for review_id, review in reviews.items()
    }
    specs = []
    for spec in config["merch_specs"]:
        review_id = index.get(("merch_spec", spec["spec_id"]))
        if review_id is None:
            raise ValidationFailed(f"merch spec {spec['spec_id']} has no content review")
        record = dict(spec)
        record["license_id"] = config["license_id"]
        record["content_review_ref"] = review_id
        record["created_at"] = config["created_at"]
        store.assert_valid("merch_spec", record)
        specs.append(record)
    return specs


def build_license(
    store, settings, bible: dict, reviews: dict[str, dict], merch_specs: list[dict]
) -> dict:
    config = settings.json("config/ip/licensing.json")
    review_id = {
        (review["subject"]["kind"], review["subject"]["ref"]): review_id
        for review_id, review in reviews.items()
    }.get(("licence_document", config["license_id"]))
    if review_id is None:
        raise ValidationFailed("the licence package has no content review")
    review = reviews[review_id]
    documents = []
    for document in config["documents"]:
        record = {field: document[field] for field in DOCUMENT_FIELDS}
        record["checksum"] = _document_checksum(record)
        documents.append(record)
    characters = [
        {
            "name": character["name"],
            "role": character["role"],
            "traits": list(character["motifs"][:3]),
        }
        for character in bible["canon"]["characters"]
    ]
    record = {
        "license_id": config["license_id"],
        "characters": characters,
        "usage": config["usage"],
        "quality_spec": config["quality_spec"],
        "contract_template_ref": config["contract_template_ref"],
        "content_review": {
            "status": "approved",
            "reviewer": str(review["reviewer"]["name"])[:40],
            "authenticity_label": str(review["authenticity"]["label"])[:120],
        },
        "traditional_prototype_refs": config["traditional_prototype_refs"],
        "documents": documents,
        "merch_spec_refs": [spec["spec_id"] for spec in merch_specs],
        "created_at": config["created_at"],
    }
    store.assert_valid("ip_license", record)
    return record


def document_summary(license_record: dict) -> dict:
    documents = license_record["documents"]
    signed = [document for document in documents if document["status"] == "signed"]
    covered = sorted(
        {
            category
            for document in signed
            for category in document["derivative_categories"]
        }
    )
    return {
        "documents": len(documents),
        "signed": len(signed),
        "draft": sum(1 for document in documents if document["status"] == "draft"),
        "categories_covered": covered,
        "categories_licensed": sorted(license_record["usage"]["derivative_categories"]),
        "royalty_rate_bp": license_record["usage"]["royalty_rate_bp"],
        "term_months": license_record["usage"]["term_months"],
        "exclusivity": license_record["usage"]["exclusivity"],
    }


def merch_summary(specs: list[dict]) -> dict:
    categories = sorted({spec["category"] for spec in specs})
    return {
        "specs": len(specs),
        "categories": categories,
        "aql": sorted({float(spec["quality"]["sampling"]["aql"]) for spec in specs}),
        "royalty_rates_bp": sorted({spec["rights"]["royalty_rate_bp"] for spec in specs}),
    }
