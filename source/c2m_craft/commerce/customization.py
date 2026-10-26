"""Participatory customisation: catalogue, price resolution, derived concept.

An option only changes facts. That is deliberate: the manufacturability gate runs
again on the derived concept, so adding a 9 mm stone cannot bypass the setting
rules, and the buyer sees a verdict rather than a surprise at production time.
"""

from __future__ import annotations

import copy
from typing import Iterable

from ..core.canonical import content_hash
from ..core.errors import ValidationFailed

OPTION_FIELDS = ("option_id", "label", "price_delta_bp", "lead_time_delta_days", "fact_changes")


def signed_rate(amount_cents: int, rate_bp: int) -> int:
    """Apply a signed basis-point delta, rounding towards negative infinity."""
    return int(amount_cents) * int(rate_bp) // 10000


class CustomizationCatalog:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.data = settings.json("config/commerce/customization.json")

    def for_industry(self, industry: str) -> dict:
        try:
            return self.data["industries"][industry]
        except KeyError as exc:
            raise ValidationFailed(f"no customisation catalogue for industry {industry}") from exc

    def option(self, industry: str, group_id: str, option_id: str) -> dict:
        for group in self.for_industry(industry)["groups"]:
            if group["group_id"] != group_id:
                continue
            for option in group["options"]:
                if option["option_id"] == option_id:
                    return option
        raise ValidationFailed(f"unknown option {group_id}/{option_id}")

    def describe(self, industry: str) -> dict:
        catalogue = self.for_industry(industry)
        return {
            "industry": industry,
            "groups": [
                {
                    "group_id": group["group_id"],
                    "label": group["label"],
                    "options": [
                        {
                            "option_id": option["option_id"],
                            "label": option["label"],
                            "price_delta_bp": int(option["price_delta_bp"]),
                            "lead_time_delta_days": int(option["lead_time_delta_days"]),
                            "fact_changes": dict(option["fact_changes"]),
                        }
                        for option in group["options"]
                    ],
                }
                for group in catalogue["groups"]
            ],
            "conflicts": [
                {
                    "a": conflict["a"],
                    "b": conflict["b"],
                    "reason": conflict["reason"],
                }
                for conflict in catalogue.get("conflicts", [])
            ],
        }


def find_conflicts(catalogue: dict, selections: Iterable[dict]) -> list[dict]:
    chosen = {(item["group_id"], item["option_id"]) for item in selections}
    problems = []
    for conflict in catalogue.get("conflicts", []):
        first = (conflict["a"]["group_id"], conflict["a"]["option_id"])
        second = (conflict["b"]["group_id"], conflict["b"]["option_id"])
        if first in chosen and second in chosen:
            problems.append(conflict["reason"])
    return problems


def resolve(
    settings,
    catalogue: CustomizationCatalog,
    concept: dict,
    selections: list[dict],
    *,
    customization_id: str,
    created_at: str,
) -> dict:
    """Validate the selection and resolve every delta to integer cents."""
    if not selections:
        raise ValidationFailed("at least one option must be selected")
    industry = str(concept["industry"])
    catalogue_data = catalogue.for_industry(industry)
    base_price = settings.base_price(industry, str(concept["form"]["category"]))

    resolved: list[dict] = []
    seen_groups: set[str] = set()
    for item in selections:
        group_id = str(item.get("group_id") or "")
        option_id = str(item.get("option_id") or "")
        if group_id in seen_groups:
            raise ValidationFailed(f"option group {group_id} was chosen twice")
        seen_groups.add(group_id)
        option = catalogue.option(industry, group_id, option_id)
        delta = signed_rate(base_price, int(option["price_delta_bp"]))
        resolved.append(
            {
                "group_id": group_id,
                "option_id": option_id,
                "label": dict(option["label"]),
                "price_delta_cents": delta,
                "lead_time_delta_days": int(option["lead_time_delta_days"]),
                "fact_changes": dict(option["fact_changes"]),
            }
        )

    conflicts = find_conflicts(catalogue_data, resolved)
    if conflicts:
        raise ValidationFailed("incompatible options: " + " | ".join(reason["en"] for reason in conflicts))

    delta_total = sum(item["price_delta_cents"] for item in resolved)
    return {
        "customization_id": customization_id,
        "base_concept_id": str(concept["concept_id"]),
        "result_concept_id": None,
        "industry": industry,
        "selections": resolved,
        "amounts": {
            "base_unit_price_cents": base_price,
            "delta_cents": delta_total,
            "unit_price_cents": base_price + delta_total,
        },
        "status": "draft",
        "feasibility": {"ok": False, "assessment_id": None, "blockers": []},
        "created_at": created_at,
        "confirmed_at": None,
    }


def apply_to_concept(concept: dict, choice: dict, *, concept_id: str, created_at: str) -> dict:
    """Build the derived concept: facts change, identity does not."""
    derived = copy.deepcopy(concept)
    derived["concept_id"] = concept_id
    derived["derived_from"] = str(concept["concept_id"])
    derived["customization_id"] = str(choice["customization_id"])
    derived["created_at"] = created_at
    facts = dict(derived.get("craft_facts") or {})
    for selection in choice["selections"]:
        for name, value in selection["fact_changes"].items():
            facts[name] = value
    derived["craft_facts"] = facts
    material = dict(derived.get("material") or {})
    if "alloy" in facts:
        material["name"] = str(facts["alloy"])
    if "species" in facts:
        material["name"] = str(facts["species"])
    if facts.get("surface_finish"):
        material["finish"] = str(facts["surface_finish"])
    elif facts.get("finish"):
        material["finish"] = str(facts["finish"])
    derived["material"] = material
    derived["seed"] = content_hash(
        {"base": concept.get("seed"), "selections": [item["option_id"] for item in choice["selections"]]}
    )[:16]
    labels = [item["label"] for item in choice["selections"]]
    suffix = {"zh": "·".join(label["zh"] for label in labels), "en": ", ".join(label["en"] for label in labels)}
    derived["title"] = {
        "zh": f"{concept['title']['zh']}（{suffix['zh']}）",
        "en": f"{concept['title']['en']} ({suffix['en']})",
    }
    derived["source"] = "hybrid"
    return derived


def lead_time_delta(choice: dict) -> int:
    if not choice.get("selections"):
        return 0
    return max(int(item.get("lead_time_delta_days", 0)) for item in choice["selections"])
