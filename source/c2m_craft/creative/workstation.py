"""Deterministic creative workstation.

The M1 prototype does not call an image model.  It assembles concepts from a
curated vocabulary with a hash-seeded generator, so the same brief plus the same
palette always yields byte-identical concepts.  The adapter boundary is where a
real model plugs in for M2; the interface is declared here and the limitation is
stated in the UI, the README and DELIVERY.md.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Protocol

from ..core.canonical import sha256_hex

PALETTE_WEIGHTS = [55, 20, 12, 6, 4, 3]
MAX_PROMPT = 400


@dataclass
class ConceptRequest:
    text: str
    industry: str
    count: int = 4
    style_id: str | None = None
    reference_palette: list[str] | None = None

    def validate(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("a prompt is required")
        if len(self.text) > MAX_PROMPT:
            raise ValueError(f"prompt is longer than {MAX_PROMPT} characters")
        if self.count < 1 or self.count > 6:
            raise ValueError("count must be between 1 and 6")


class ConceptModelAdapter(Protocol):
    """Boundary for a real generative model. M2 implements this against an API."""

    name: str
    version: str

    def generate(self, request: ConceptRequest, context: dict) -> list[dict]: ...


def prompt_seed(text: str, industry: str, style_id: str, palette_id: str, index: int) -> str:
    digest = hashlib.sha256(
        f"{text.strip().lower()}|{industry}|{style_id}|{palette_id}|{index}".encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _rng(seed: str) -> random.Random:
    return random.Random(int(seed, 16))


def nearest_palette(palettes: list[dict], colors: list[str]) -> dict:
    """Map reference colours to the closest curated palette."""
    def to_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    wanted = [to_rgb(color) for color in colors if len(color) == 7 and color.startswith("#")]
    best = palettes[0]
    best_score = None
    for palette in palettes:
        candidates = [to_rgb(color) for color in palette["colors"]]
        score = 0
        for target in wanted:
            score += min(
                (target[0] - c[0]) ** 2 + (target[1] - c[1]) ** 2 + (target[2] - c[2]) ** 2
                for c in candidates
            )
        if best_score is None or score < best_score:
            best, best_score = palette, score
    return best


def _palette_entries(palette: dict) -> list[dict]:
    return [
        {"hex": color, "weight": PALETTE_WEIGHTS[index]}
        for index, color in enumerate(palette["colors"][: len(PALETTE_WEIGHTS)])
    ]


def _title(lexicon: dict, language: str, prefix_index: int, motif: dict, category: str) -> str:
    prefix = lexicon["titles"][language]["prefix"][prefix_index % len(lexicon["titles"][language]["prefix"])]
    noun_pool = lexicon["titles"][language].get(category) or [category]
    noun = noun_pool[prefix_index % len(noun_pool)]
    motif_name = motif["title"][language]
    if language == "zh":
        return f"{prefix}{motif_name}{noun}"
    return f"{prefix} {motif_name.lower()} {noun}"


def generate(
    request: ConceptRequest,
    *,
    lexicon: dict,
    palettes: list[dict],
    styles: list[dict],
    created_at: str,
    next_id: int,
) -> list[dict]:
    request.validate()
    industry = request.industry
    pool = [motif for motif in lexicon["motifs"] if industry in motif["industries"]]
    forms = [form for form in lexicon["forms"] if form["industry"] == industry]
    if not pool or not forms:
        raise ValueError(f"no vocabulary for industry {industry}")

    style = next(
        (item for item in styles if item["style_id"] == request.style_id),
        styles[0],
    )
    if request.reference_palette:
        palette = nearest_palette(palettes, request.reference_palette)
    else:
        palette_index = int(sha256_hex(request.text)[:4], 16) % len(palettes)
        palette = palettes[palette_index]

    concepts = []
    for index in range(request.count):
        seed = prompt_seed(request.text, industry, style["style_id"], palette["palette_id"], index)
        rng = _rng(seed)
        motif = pool[(int(seed[:4], 16) + index) % len(pool)]
        form = forms[(int(seed[4:8], 16) + index) % len(forms)]

        factor = float(style["geometry_factor"]) * (0.95 + 0.1 * rng.random())
        dimensions = {
            axis: round(float(value) * factor, 2)
            for axis, value in form["dimensions_mm"].items()
        }
        facts = dict(form["craft_facts"])
        # Geometry-driven facts follow the scaled dimensions.
        for name in ("max_dimension_mm", "span_mm"):
            if name in facts:
                facts[name] = round(float(facts[name]) * factor, 2)
        if "min_wall_thickness_mm" in facts:
            facts["min_wall_thickness_mm"] = round(
                float(facts["min_wall_thickness_mm"]) * (1.0 + (factor - 1.0) * 0.5), 2
            )
        for name in ("engraving_depth_mm", "carve_depth_mm"):
            if name in facts:
                facts[name] = round(float(facts[name]) * float(style["detail_factor"]), 2)

        concept_id = f"DC-{next_id + index:04d}"
        concepts.append(
            {
                "concept_id": concept_id,
                "title": {
                    "zh": _title(lexicon, "zh", int(seed[8:12], 16), motif, form["category"]),
                    "en": _title(lexicon, "en", int(seed[8:12], 16), motif, form["category"]),
                },
                "source": "reference_image" if request.reference_palette else "text",
                "prompt": {"zh": request.text, "en": request.text},
                "seed": seed,
                "industry": industry,
                "motif_ids": [motif["motif_id"]],
                "palette": _palette_entries(palette),
                "form": {
                    "category": form["category"],
                    "dimensions_mm": dimensions,
                    "variant": form["variant"],
                },
                "material": {
                    "name": str(facts.get("alloy") or facts.get("species") or "mixed"),
                    "finish": str(facts.get("surface_finish") or facts.get("finish") or "matte"),
                },
                "style": {
                    "style_id": style["style_id"],
                    "intensity": 40 + int(seed[12:14], 16) % 60,
                },
                "craft_facts": facts,
                "preview": {
                    "motif_style": motif["pattern_style"],
                    "texture": style["texture"],
                    "gradient_angle_deg": int(style["gradient_angle_deg"]),
                },
                "asset_refs": [],
                "generator": {
                    "adapter": "offline_lexicon",
                    "version": "1.0.0",
                    "deterministic": True,
                },
                "created_by": "designer-01",
                "created_at": created_at,
            }
        )
    return concepts
