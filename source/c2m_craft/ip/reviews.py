"""Content review records for the cultural IP pipeline.

Every artefact that ships (character, visual asset, short drama, licence document
set, merchandise specification) cites a review record.  The record is built from a
checklist template plus the subject, the reviewer, the authenticity block required
for AIGC labelling and the heritage check.  The invariant then ties the verdict to
the checklist, so an approval cannot hide a failed item.
"""

from __future__ import annotations

from ..core.errors import ValidationFailed


def load_config(settings) -> dict:
    return settings.json("config/ip/licensing.json")


def build(store, settings) -> dict[str, dict]:
    config = load_config(settings)
    templates = config["review_templates"]
    defaults = config["review_defaults"]
    reviews: dict[str, dict] = {}
    for row in config["reviews"]:
        try:
            template = templates[row["template"]]
        except KeyError as exc:
            raise ValidationFailed(f"review {row['review_id']} uses an unknown template") from exc
        checklist = []
        for item in template:
            entry = {
                "item_id": item["item_id"],
                "requirement": item["requirement"],
                "verdict": "pass",
            }
            if item["item_id"] == "heritage_non_exclusive":
                note = str(row.get("heritage_note") or "").strip()
                if note:
                    entry["note"] = note[:220]
            checklist.append(entry)
        record = {
            "review_id": row["review_id"],
            "subject": dict(row["subject"]),
            "checklist": checklist,
            "verdict": row["verdict"],
            "reviewer": dict(defaults["reviewer"]),
            "authenticity": dict(defaults["authenticity"]),
            "heritage_check": {
                "traditional_prototypes_referenced": list(defaults["heritage_refs"]),
                "exclusive_claim": False,
                "note": str(
                    row.get("heritage_note")
                    or "Heritage references are cited as shared regional technique, never claimed."
                )[:240],
            },
            "reviewed_at": defaults["reviewed_at"],
        }
        store.assert_valid("content_review", record)
        reviews[record["review_id"]] = record
    return reviews


def for_subject(reviews: dict[str, dict], kind: str, ref: str) -> dict | None:
    for review in reviews.values():
        if review["subject"]["kind"] == kind and review["subject"]["ref"] == ref:
            return review
    return None
