"""Generate the deterministic fixtures: 10 concepts, the expected verdict table,
the licensed asset library and the rejection payloads.

Run from the delivery root:

    python scripts/gen_samples.py

The generator validates every fixture against the contracts before writing, so a
fixture that drifts from the schema fails loudly instead of shipping.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from c2m_craft.core.contracts import SchemaStore  # noqa: E402

CREATED_AT = "2026-10-15T00:00:00Z"
PALETTE_WEIGHTS = [55, 20, 12, 6, 4, 3]
STYLE_CYCLE = ["coastal_minimal", "heritage_ornate", "kiln_earth", "court_contrast", "workshop_raw"]


def seed_for(concept_id: str, prompt_en: str) -> str:
    return hashlib.sha256(f"{concept_id}:{prompt_en}".encode("utf-8")).hexdigest()[:16]


def load(relative: str):
    with open(ROOT / relative, "r", encoding="utf-8") as handle:
        return json.load(handle)


PALETTES = {entry["palette_id"]: entry for entry in load("config/creative/palettes.json")["palettes"]}
LEXICON = load("config/creative/lexicon.json")


def form_for(industry: str, category: str) -> dict:
    for entry in LEXICON["forms"]:
        if entry["industry"] == industry and entry["category"] == category:
            return entry
    raise KeyError(f"no form template {industry}/{category}")


# concept_id, industry, category, motif, palette, title, prompt, facts overrides, style
CONCEPTS = [
    (
        "DC-0001", "jewelry", "ring", ["MOT-JW-01"], "coastal_brass",
        {"zh": "海雾缠枝戒", "en": "Sea mist interlace ring"},
        {"zh": "沿海产业带的缠枝纹素圈戒指，18K 金，日常佩戴。",
         "en": "An interlace-vine band ring for daily wear in 18K gold, made for the coastal industrial belt."},
        {},
        "coastal_minimal",
    ),
    (
        "DC-0002", "jewelry", "pendant", ["MOT-JW-04"], "court_vermilion",
        {"zh": "薄壁大石吊坠", "en": "Thin-wall large-stone pendant"},
        {"zh": "0.3 mm 薄壁、8.5 mm 单石、无镶口的吊坠概念。",
         "en": "A 0.3 mm wall pendant with a single 8.5 mm stone and no declared setting."},
        {
            "min_wall_thickness_mm": 0.3,
            "max_dimension_mm": 40,
            "stone_count": 1,
            "stone_size_mm": 8.5,
            "setting_type": "none",
            "prong_count": 0,
            "prong_thickness_mm": 0,
            "surface_finish": "polished",
            "engraving_depth_mm": 0,
            "recessed_area": False,
            "alloy": "18k_gold",
        },
        "heritage_ornate",
    ),
    (
        "DC-0003", "jewelry", "pendant", ["MOT-JW-02"], "harbour_ink",
        {"zh": "薄壁空心倒扣吊坠", "en": "Thin hollow pendant with undercut"},
        {"zh": "0.7 mm 壁厚的空心铸造吊坠，带倒扣纹样。",
         "en": "A hollow-cast pendant with a 0.7 mm wall and an undercut pattern."},
        {
            "min_wall_thickness_mm": 0.7,
            "max_dimension_mm": 42,
            "stone_count": 0,
            "stone_size_mm": 0,
            "setting_type": "none",
            "prong_count": 0,
            "prong_thickness_mm": 0,
            "hollow_cast": True,
            "undercut": True,
            "engraving_depth_mm": 0.3,
            "surface_finish": "polished",
            "ring_size_mm": 0,
            "alloy": "18k_gold",
            "chain_link_mm": 0,
            "recessed_area": True,
        },
        "kiln_earth",
    ),
    (
        "DC-0004", "jewelry", "brooch", ["MOT-JW-05"], "pine_shadow",
        {"zh": "深錾珐琅胸针", "en": "Deep-chased enamel brooch"},
        {"zh": "0.45 mm 錾刻配 800 摄氏度烧成珐琅的银胸针。",
         "en": "A silver brooch with 0.45 mm chasing and enamel fired at 800 C."},
        {
            "min_wall_thickness_mm": 1.4,
            "max_dimension_mm": 38,
            "stone_count": 6,
            "stone_size_mm": 1.5,
            "setting_type": "pave",
            "prong_count": 0,
            "prong_thickness_mm": 0,
            "enamel": True,
            "enamel_firing_c": 800,
            "engraving_depth_mm": 0.45,
            "surface_finish": "polished",
            "ring_size_mm": 0,
            "alloy": "925_silver",
            "chain_link_mm": 0,
            "recessed_area": False,
        },
        "court_contrast",
    ),
    (
        "DC-0005", "hardwood", "chair", ["MOT-HW-01"], "kiln_amber",
        {"zh": "胡桃木回纹扶手椅", "en": "Walnut fret armchair"},
        {"zh": "榫卯结构、胡桃木、设计载荷 110 kg 的扶手椅。",
         "en": "A mortise-and-tenon walnut armchair rated for 110 kg."},
        {},
        "heritage_ornate",
    ),
    (
        "DC-0006", "hardwood", "table", ["MOT-HW-03"], "lacquer_black",
        {"zh": "三毫米悬臂板", "en": "Three-millimetre cantilever shelf"},
        {"zh": "1500 mm 悬臂、3 mm 板厚的展示板概念。",
         "en": "A display shelf with a 1500 mm cantilever and a 3 mm panel."},
        {
            "species": "oak",
            "joint_types": ["screw"],
            "tolerance_mm": 0.5,
            "span_mm": 1500,
            "load_kg": 30,
            "carve_depth_mm": 0,
            "wood_moisture_pct": 9,
            "panel_thickness_mm": 3,
            "finish": "lacquer",
            "humidity_zone": "dry",
            "curve_radius_mm": 0,
            "undercut": False,
            "hardware_included": False,
            "leg_count": 2,
            "cantilever": True,
            "outdoor": False,
        },
        "workshop_raw",
    ),
    (
        "DC-0007", "hardwood", "cabinet", ["MOT-HW-05"], "oyster_cream",
        {"zh": "沿海高光深雕柜", "en": "Coastal high-gloss carved cabinet"},
        {"zh": "沿海环境、高光涂装、10 mm 雕深的榆木柜。",
         "en": "An elm cabinet for a coastal climate with a high-gloss finish and 10 mm carving."},
        {
            "species": "elm",
            "joint_types": ["dovetail"],
            "tolerance_mm": 0.2,
            "span_mm": 600,
            "load_kg": 20,
            "carve_depth_mm": 10,
            "wood_moisture_pct": 10,
            "panel_thickness_mm": 25,
            "finish": "high_gloss",
            "humidity_zone": "coastal",
            "curve_radius_mm": 50,
            "undercut": False,
            "hardware_included": True,
            "leg_count": 4,
            "cantilever": False,
            "outdoor": False,
        },
        "kiln_earth",
    ),
    (
        "DC-0008", "hardwood", "chair", ["MOT-HW-02"], "lacquer_black",
        {"zh": "户外松木螺丝椅", "en": "Outdoor pine screw-only chair"},
        {"zh": "松木、仅螺丝固定、70 kg 载荷的户外椅。",
         "en": "An outdoor pine chair fixed with screws only, rated for 70 kg."},
        {
            "species": "pine",
            "joint_types": ["screw"],
            "tolerance_mm": 0.4,
            "span_mm": 900,
            "load_kg": 70,
            "carve_depth_mm": 0,
            "wood_moisture_pct": 14,
            "panel_thickness_mm": 20,
            "finish": "lacquer",
            "humidity_zone": "coastal",
            "curve_radius_mm": 0,
            "undercut": False,
            "hardware_included": False,
            "leg_count": 4,
            "cantilever": False,
            "outdoor": True,
        },
        "workshop_raw",
    ),
    (
        "DC-0009", "hardwood", "cabinet", ["MOT-HW-04"], "coastal_brass",
        {"zh": "木质嵌坠概念", "en": "Wooden pendant concept"},
        {"zh": "同一纹样的木作版本：胡桃木小坠，雕深 6 mm，曲率 18 mm。",
         "en": "The same motif in timber: a small walnut pendant, 6 mm carving, 18 mm radius."},
        {
            "species": "walnut",
            "joint_types": ["dowel"],
            "tolerance_mm": 0.15,
            "span_mm": 45,
            "load_kg": 2,
            "carve_depth_mm": 6,
            "wood_moisture_pct": 9,
            "panel_thickness_mm": 20,
            "finish": "wax",
            "humidity_zone": "temperate",
            "curve_radius_mm": 18,
            "undercut": True,
            "hardware_included": True,
            "leg_count": 0,
            "cantilever": False,
            "outdoor": False,
        },
        "coastal_minimal",
    ),
    (
        "DC-0010", "jewelry", "pendant", ["MOT-HW-04"], "river_silver",
        {"zh": "木质嵌坠的金属版本", "en": "The pendant in metal"},
        {"zh": "同一纹样的金属版本：0.8 mm 壁厚、镜面、深凹面。",
         "en": "The same motif in metal: 0.8 mm wall, mirror finish, recessed field."},
        {
            "min_wall_thickness_mm": 0.8,
            "max_dimension_mm": 30,
            "stone_count": 3,
            "stone_size_mm": 2.0,
            "setting_type": "bezel",
            "prong_count": 0,
            "prong_thickness_mm": 0,
            "engraving_depth_mm": 0.2,
            "surface_finish": "mirror",
            "ring_size_mm": 0,
            "alloy": "18k_gold",
            "chain_link_mm": 0,
            "recessed_area": True,
        },
        "coastal_minimal",
    ),
]

# Hand-written expectations, committed before the engine is run.
EXPECTED = {
    "DC-0001": {"WS-JW-A": ("manufacturable", []), "WS-JW-B": ("manufacturable", [])},
    "DC-0002": {
        "WS-JW-A": ("not_manufacturable", ["CAP-JW-A-01", "JW-CAST-001", "JW-SET-001"]),
        "WS-JW-B": ("not_manufacturable", ["CAP-JW-B-01", "CAP-JW-B-02"]),
    },
    "DC-0003": {"WS-JW-A": ("conditionally_manufacturable", []), "WS-JW-B": ("not_manufacturable", ["CAP-JW-B-01"])},
    "DC-0004": {"WS-JW-A": ("conditionally_manufacturable", []), "WS-JW-B": ("not_manufacturable", ["CAP-JW-B-06"])},
    "DC-0005": {"WS-HW-A": ("manufacturable", []), "WS-HW-B": ("manufacturable", [])},
    "DC-0006": {
        "WS-HW-A": ("not_manufacturable", ["CAP-HW-A-02", "HW-JOIN-003", "HW-FORM-001"]),
        "WS-HW-B": ("not_manufacturable", ["CAP-HW-B-02", "HW-JOIN-003", "HW-FORM-001"]),
    },
    "DC-0007": {"WS-HW-A": ("conditionally_manufacturable", []), "WS-HW-B": ("not_manufacturable", ["CAP-HW-B-01"])},
    "DC-0008": {
        "WS-HW-A": ("not_manufacturable", ["HW-JOIN-002", "HW-SURF-002"]),
        "WS-HW-B": ("not_manufacturable", ["CAP-HW-B-03", "HW-JOIN-002", "HW-SURF-002"]),
    },
    "DC-0009": {"WS-HW-A": ("manufacturable", []), "WS-HW-B": ("manufacturable", [])},
    "DC-0010": {"WS-JW-A": ("conditionally_manufacturable", []), "WS-JW-B": ("not_manufacturable", ["CAP-JW-B-01"])},
}

COUNTEREXAMPLES = ["DC-0002", "DC-0006", "DC-0008"]


def build_concept(entry) -> dict:
    concept_id, industry, category, motifs, palette_id, title, prompt, overrides, style_id = entry
    template = form_for(industry, category)
    facts = dict(template["craft_facts"])
    facts.update(overrides)
    dimensions = dict(template["dimensions_mm"])
    if "max_dimension_mm" in facts:
        dimensions = {axis: round(float(value) * (facts["max_dimension_mm"] / max(template["dimensions_mm"].values())), 2)
                      for axis, value in dimensions.items()}
    palette_entry = PALETTES[palette_id]
    palette = [
        {"hex": color, "weight": PALETTE_WEIGHTS[index]}
        for index, color in enumerate(palette_entry["colors"][: len(PALETTE_WEIGHTS)])
    ]
    material_name = facts.get("alloy") or facts.get("species")
    finish = facts.get("surface_finish") or facts.get("finish") or "matte"
    style = next((item for item in load("config/creative/styles.json")["styles"] if item["style_id"] == style_id), None)
    return {
        "concept_id": concept_id,
        "title": title,
        "source": "text",
        "prompt": prompt,
        "seed": seed_for(concept_id, prompt["en"]),
        "industry": industry,
        "motif_ids": list(motifs),
        "palette": palette,
        "form": {
            "category": category,
            "dimensions_mm": dimensions,
            "variant": template["variant"],
        },
        "material": {"name": str(material_name), "finish": str(finish)},
        "style": {"style_id": style_id, "intensity": 60 + (len(concept_id) % 4) * 10},
        "craft_facts": facts,
        "preview": {
            "motif_style": next(
                item["pattern_style"] for item in LEXICON["motifs"] if item["motif_id"] in motifs
            ),
            "texture": (style or {}).get("texture", "matte"),
            "gradient_angle_deg": int((style or {}).get("gradient_angle_deg", 90)),
        },
        "asset_refs": [],
        "generator": {"adapter": "offline_lexicon", "version": "1.0.0", "deterministic": True},
        "created_by": "designer-01",
        "created_at": CREATED_AT,
    }


ASSETS = [
    {
        "asset_id": "PA-JW-0001",
        "title": {"zh": "缠枝授权纹样", "en": "Licensed interlace pattern"},
        "industries": ["jewelry"],
        "medium": "pattern",
        "tags": ["floral", "interlace", "licensed"],
        "palette": ["#C9A227", "#1F2A44", "#F2EFE9"],
        "preview": {"motif_style": "interlace", "texture": "polished", "gradient_angle_deg": 135},
        "license": {
            "source_type": "licensed",
            "licensor": "Regional Crafts Archive (synthetic)",
            "license_id": "LIC-SYN-0007",
            "usage_scope": ["commercial_product", "derivative_work"],
            "territory": ["CN", "global"],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2028-12-31T00:00:00Z",
            "royalty_rate_bp": 300,
            "attribution_required": True,
            "exclusive": False,
        },
        "traditional_prototype": False,
        "religious_site_names": [],
        "review": {"status": "content_reviewed", "reviewed_by": "CR-01", "reviewed_at": "2026-09-30T00:00:00Z", "authenticity_label": "derivative"},
        "created_at": "2026-09-30T00:00:00Z",
    },
    {
        "asset_id": "PA-JW-0002",
        "title": {"zh": "自研潮汐线", "en": "In-house tide line"},
        "industries": ["jewelry"],
        "medium": "form",
        "tags": ["wave", "minimal", "in-house"],
        "palette": ["#2E6F7E", "#D8DEE2", "#0F1A1F"],
        "preview": {"motif_style": "wave", "texture": "brushed", "gradient_angle_deg": 90},
        "license": {
            "source_type": "self_produced",
            "usage_scope": ["commercial_product", "advertising", "export"],
            "territory": ["global"],
            "valid_from": "2026-06-01T00:00:00Z",
            "valid_to": "2031-06-01T00:00:00Z",
            "royalty_rate_bp": 0,
            "attribution_required": False,
            "exclusive": True,
        },
        "traditional_prototype": False,
        "religious_site_names": [],
        "review": {"status": "artisan_reviewed", "reviewed_by": "ART-JW-01", "reviewed_at": "2026-06-10T00:00:00Z", "authenticity_label": "original_design"},
        "created_at": "2026-06-01T00:00:00Z",
    },
    {
        "asset_id": "PA-JW-0003",
        "title": {"zh": "传统云雷纹样", "en": "Traditional cloud-thunder motif"},
        "industries": ["jewelry", "carving", "heritage"],
        "medium": "pattern",
        "tags": ["traditional", "fret", "heritage"],
        "palette": ["#1F2A44", "#C9A227", "#E8E4DA"],
        "preview": {"motif_style": "fret", "texture": "carved", "gradient_angle_deg": 45},
        "license": {
            "source_type": "traditional_heritage",
            "licensor": "Public heritage registry (synthetic)",
            "license_id": "LIC-SYN-HER-01",
            "usage_scope": ["commercial_product", "derivative_work"],
            "territory": ["CN"],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2030-01-01T00:00:00Z",
            "royalty_rate_bp": 0,
            "attribution_required": True,
            "exclusive": False,
        },
        "traditional_prototype": True,
        "religious_site_names": [],
        "review": {"status": "content_reviewed", "reviewed_by": "CR-02", "reviewed_at": "2026-08-01T00:00:00Z", "authenticity_label": "traditional_reference"},
        "created_at": "2026-08-01T00:00:00Z",
    },
    {
        "asset_id": "PA-JW-0004",
        "title": {"zh": "庙宇纹样参考", "en": "Temple pattern reference"},
        "industries": ["jewelry", "heritage"],
        "medium": "pattern",
        "tags": ["temple", "reference", "non-exclusive"],
        "palette": ["#8C1C2B", "#C9A227", "#F6EDE3"],
        "preview": {"motif_style": "granule", "texture": "polished", "gradient_angle_deg": 20},
        "license": {
            "source_type": "public_domain",
            "usage_scope": ["internal_demo", "derivative_work"],
            "territory": ["CN"],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2036-01-01T00:00:00Z",
            "royalty_rate_bp": 0,
            "attribution_required": False,
            "exclusive": False,
        },
        "traditional_prototype": True,
        "religious_site_names": ["Mazu temple (synthetic name)"],
        "review": {"status": "content_reviewed", "reviewed_by": "CR-03", "reviewed_at": "2026-08-15T00:00:00Z", "authenticity_label": "traditional_reference"},
        "created_at": "2026-08-15T00:00:00Z",
    },
    {
        "asset_id": "PA-HW-0001",
        "title": {"zh": "授权回纹牙板", "en": "Licensed fret apron"},
        "industries": ["hardwood"],
        "medium": "form",
        "tags": ["fret", "apron", "joinery"],
        "palette": ["#5B3A22", "#C9A227", "#EADFCF"],
        "preview": {"motif_style": "fret", "texture": "carved", "gradient_angle_deg": 135},
        "license": {
            "source_type": "licensed",
            "licensor": "Woodcraft design studio (synthetic)",
            "license_id": "LIC-SYN-0011",
            "usage_scope": ["commercial_product"],
            "territory": ["CN", "EU"],
            "valid_from": "2025-06-01T00:00:00Z",
            "valid_to": "2027-06-01T00:00:00Z",
            "royalty_rate_bp": 450,
            "attribution_required": False,
            "exclusive": False,
        },
        "traditional_prototype": False,
        "religious_site_names": [],
        "review": {"status": "content_reviewed", "reviewed_by": "CR-04", "reviewed_at": "2026-07-01T00:00:00Z", "authenticity_label": "derivative"},
        "created_at": "2026-07-01T00:00:00Z",
    },
    {
        "asset_id": "PA-HW-0002",
        "title": {"zh": "公版缠枝挂落", "en": "Public-domain interlace spandrel"},
        "industries": ["hardwood"],
        "medium": "pattern",
        "tags": ["interlace", "spandrel", "public-domain"],
        "palette": ["#4A2E1B", "#A8794A", "#EFE6D6"],
        "preview": {"motif_style": "interlace", "texture": "carved", "gradient_angle_deg": 45},
        "license": {
            "source_type": "public_domain",
            "usage_scope": ["commercial_product", "advertising"],
            "territory": ["global"],
            "valid_from": "2020-01-01T00:00:00Z",
            "valid_to": "2040-01-01T00:00:00Z",
            "royalty_rate_bp": 0,
            "attribution_required": False,
            "exclusive": False,
        },
        "traditional_prototype": True,
        "religious_site_names": [],
        "review": {"status": "content_reviewed", "reviewed_by": "CR-05", "reviewed_at": "2026-06-20T00:00:00Z", "authenticity_label": "traditional_reference"},
        "created_at": "2026-06-20T00:00:00Z",
    },
    {
        "asset_id": "PA-HW-0003",
        "title": {"zh": "到期授权潮线嵌", "en": "Expired licensed tide inlay"},
        "industries": ["hardwood"],
        "medium": "material",
        "tags": ["inlay", "coastal", "expired"],
        "palette": ["#2E6F7E", "#D9C9A6", "#1B2A2E"],
        "preview": {"motif_style": "inlay", "texture": "polished", "gradient_angle_deg": 90},
        "license": {
            "source_type": "licensed",
            "licensor": "Inlay workshop (synthetic)",
            "license_id": "LIC-SYN-0021",
            "usage_scope": ["internal_demo"],
            "territory": ["CN"],
            "valid_from": "2025-01-01T00:00:00Z",
            "valid_to": "2026-09-30T00:00:00Z",
            "royalty_rate_bp": 200,
            "attribution_required": False,
            "exclusive": False,
        },
        "traditional_prototype": False,
        "religious_site_names": [],
        "review": {"status": "auto_checked", "reviewed_by": "CR-06", "reviewed_at": "2025-01-05T00:00:00Z", "authenticity_label": "derivative"},
        "created_at": "2025-01-01T00:00:00Z",
    },
    {
        "asset_id": "PA-HW-0004",
        "title": {"zh": "自研藤影雕花", "en": "In-house vine shadow carving"},
        "industries": ["hardwood", "carving"],
        "medium": "pattern",
        "tags": ["relief", "vine", "in-house"],
        "palette": ["#3E2A1A", "#8C6A45", "#E7DAC6"],
        "preview": {"motif_style": "relief", "texture": "carved", "gradient_angle_deg": 160},
        "license": {
            "source_type": "self_produced",
            "usage_scope": ["commercial_product", "derivative_work", "advertising"],
            "territory": ["global"],
            "valid_from": "2026-05-01T00:00:00Z",
            "valid_to": "2031-05-01T00:00:00Z",
            "royalty_rate_bp": 0,
            "attribution_required": False,
            "exclusive": True,
        },
        "traditional_prototype": False,
        "religious_site_names": [],
        "review": {"status": "artisan_reviewed", "reviewed_by": "ART-HW-01", "reviewed_at": "2026-05-05T00:00:00Z", "authenticity_label": "original_design"},
        "created_at": "2026-05-01T00:00:00Z",
    },
]

REJECTED = [
    {
        "name": "missing-source",
        "reason": "licensing source is mandatory",
        "payload": {
            "asset_id": "PA-JW-0901", "title": {"zh": "缺来源", "en": "Missing source"},
            "industries": ["jewelry"], "medium": "pattern",
            "license": {"usage_scope": ["commercial_product"]},
            "traditional_prototype": False, "religious_site_names": [],
            "review": {"status": "auto_checked"}, "created_at": "2026-10-01T00:00:00Z",
        },
    },
    {
        "name": "empty-usage-scope",
        "reason": "usage scope cannot be empty",
        "payload": {
            "asset_id": "PA-JW-0902", "title": {"zh": "空范围", "en": "Empty scope"},
            "industries": ["jewelry"], "medium": "pattern",
            "license": {"source_type": "self_produced", "usage_scope": []},
            "traditional_prototype": False, "religious_site_names": [],
            "review": {"status": "auto_checked"}, "created_at": "2026-10-01T00:00:00Z",
        },
    },
    {
        "name": "exclusive-heritage",
        "reason": "a traditional prototype cannot be exclusive",
        "payload": {
            "asset_id": "PA-JW-0903", "title": {"zh": "独占传统", "en": "Exclusive heritage"},
            "industries": ["heritage"], "medium": "pattern",
            "license": {
                "source_type": "traditional_heritage",
                "licensor": "Heritage registry (synthetic)",
                "license_id": "LIC-SYN-X1",
                "usage_scope": ["commercial_product"],
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2030-01-01T00:00:00Z",
                "exclusive": True,
            },
            "traditional_prototype": True, "religious_site_names": [],
            "review": {"status": "content_reviewed"}, "created_at": "2026-10-01T00:00:00Z",
        },
    },
    {
        "name": "expired-license",
        "reason": "the licence window has closed",
        "payload": {
            "asset_id": "PA-HW-0904", "title": {"zh": "过期授权", "en": "Expired licence"},
            "industries": ["hardwood"], "medium": "pattern",
            "license": {
                "source_type": "licensed",
                "licensor": "Studio (synthetic)",
                "license_id": "LIC-SYN-X2",
                "usage_scope": ["commercial_product"],
                "valid_from": "2025-01-01T00:00:00Z",
                "valid_to": "2026-09-30T00:00:00Z",
                "exclusive": False,
            },
            "traditional_prototype": False, "religious_site_names": [],
            "review": {"status": "auto_checked"}, "created_at": "2025-01-01T00:00:00Z",
        },
    },
    {
        "name": "religious-exclusive",
        "reason": "assets that reference religious sites cannot be exclusive",
        "payload": {
            "asset_id": "PA-JW-0905", "title": {"zh": "场所独占", "en": "Site exclusivity"},
            "industries": ["heritage"], "medium": "pattern",
            "license": {
                "source_type": "public_domain",
                "usage_scope": ["derivative_work"],
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_to": "2030-01-01T00:00:00Z",
                "exclusive": True,
            },
            "traditional_prototype": False,
            "religious_site_names": ["Mazu temple (synthetic name)"],
            "review": {"status": "auto_checked"}, "created_at": "2026-10-01T00:00:00Z",
        },
    },
    {
        "name": "bad-hex",
        "reason": "palette colours must be uppercase hex",
        "payload": {
            "asset_id": "PA-JW-0906", "title": {"zh": "色值错误", "en": "Bad colour"},
            "industries": ["jewelry"], "medium": "pattern",
            "palette": ["gold"],
            "license": {"source_type": "self_produced", "usage_scope": ["internal_demo"]},
            "traditional_prototype": False, "religious_site_names": [],
            "review": {"status": "auto_checked"}, "created_at": "2026-10-01T00:00:00Z",
        },
    },
]


def main() -> int:
    store = SchemaStore(ROOT)
    concepts_dir = ROOT / "samples" / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for entry in CONCEPTS:
        concept = build_concept(entry)
        issues = store.validate("design_concept", concept)
        if issues:
            raise SystemExit(f"{concept['concept_id']} invalid: {[i.as_dict() for i in issues]}")
        write_json(concepts_dir / f"{concept['concept_id']}.json", concept)
        written += 1

    expected = {
        "as_of": "2026-10-23T00:00:00Z",
        "note": "Expected verdicts were written by hand before running the engine; verification compares the engine output to this table.",
        "counterexamples": COUNTEREXAMPLES,
        "concepts": {},
    }
    for entry in CONCEPTS:
        concept_id, industry = entry[0], entry[1]
        workshops = {}
        for workshop_id, (verdict, must_fail) in EXPECTED[concept_id].items():
            workshops[workshop_id] = {"verdict": verdict, "must_fail": must_fail}
        expected["concepts"][concept_id] = {
            "industry": industry,
            "title": entry[5],
            "workshops": workshops,
        }
    write_json(concepts_dir / "expected.json", expected)

    for asset in ASSETS:
        issues = store.validate("pattern_asset", asset, ctx={"as_of": "2026-10-23T00:00:00Z", "require_active_window": False})
        if issues:
            raise SystemExit(f"{asset['asset_id']} invalid: {[i.as_dict() for i in issues]}")
    write_json(ROOT / "samples" / "library" / "assets.json", {"version": "1.0.0", "assets": ASSETS})

    rejection_rows = []
    for candidate in REJECTED:
        issues = store.validate(
            "pattern_asset",
            candidate["payload"],
            ctx={"as_of": "2026-10-23T00:00:00Z", "require_active_window": True},
        )
        if not issues:
            raise SystemExit(f"rejection candidate {candidate['name']} was accepted by the contract")
        rejection_rows.append(
            {
                "name": candidate["name"],
                "reason": candidate["reason"],
                "payload": candidate["payload"],
                "expected_error_count": len(issues),
                "expected_first_path": issues[0].path,
            }
        )
    write_json(ROOT / "samples" / "library" / "rejected.json", {"version": "1.0.0", "cases": rejection_rows})

    print(f"[gen_samples] wrote {written} concepts, {len(ASSETS)} assets, {len(rejection_rows)} rejection cases")
    print(f"[gen_samples] expected table covers {len(expected['concepts'])} concepts")
    return 0


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
