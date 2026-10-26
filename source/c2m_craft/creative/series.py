"""Series expansion: one concept becomes three SKUs.

Dimensions and the facts that follow from them scale together, the palette
rotates, and the price multiplier is expressed in basis points so prices stay
integer cents.
"""

from __future__ import annotations

from ..core.money import apply_rate

DIMENSION_FACTS = ("max_dimension_mm", "span_mm", "panel_thickness_mm", "min_wall_thickness_mm")


def _rotate(colors: list[dict], step: int) -> list[dict]:
    if not colors:
        return colors
    step = step % len(colors)
    return [{"hex": item["hex"], "weight": item["weight"]} for item in colors[step:] + colors[:step]]


def expand(concept: dict, config: dict, *, next_id: int) -> list[dict]:
    series_id = f"series_{concept['concept_id'].lower().replace('-', '_')}"
    rotation = int(config.get("palette_rotation", 1))
    skus = []
    for index, size in enumerate(config["sizes"]):
        sku = dict(concept)
        sku["concept_id"] = f"DC-{next_id + index:04d}"
        factor = float(size["dimension_factor"])
        dimensions = {
            axis: round(float(value) * factor, 2)
            for axis, value in concept["form"]["dimensions_mm"].items()
        }
        facts = dict(concept.get("craft_facts") or {})
        for name in DIMENSION_FACTS:
            if name in facts and isinstance(facts[name], (int, float)):
                facts[name] = round(float(facts[name]) * factor, 2)
        label = size["label"]["en"]
        sku.update(
            {
                "title": {
                    "zh": f"{concept['title']['zh']}·{size['label']['zh']}",
                    "en": f"{concept['title']['en']} ({label})",
                },
                "form": {
                    "category": concept["form"]["category"],
                    "dimensions_mm": dimensions,
                    "variant": concept["form"]["variant"],
                },
                "craft_facts": facts,
                "palette": _rotate(concept["palette"], rotation * (index + 1)),
                "series": {"series_id": series_id, "sku_index": int(size["sku_index"])},
            }
        )
        sku["_price_multiplier_bp"] = int(size["price_multiplier_bp"])
        skus.append(sku)
    return skus


def sku_price(base_cents: int, multiplier_bp: int) -> int:
    return apply_rate(base_cents, multiplier_bp)
