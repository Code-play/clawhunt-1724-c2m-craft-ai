"""Character visual asset library described as deterministic drawing recipes.

A visual asset is not a binary file: it is a list of vector layers with palette
tokens resolved from the character record.  The browser (and the sample reel) can
therefore draw the asset from data, the library ships inside the repository
without images, and the checksum over the recipe proves two builds are identical.
"""

from __future__ import annotations

from ..core.invariants import visual_asset_checksum

REVIEWER = "Content review desk"


def _tint(palette: list[str], index: int) -> str:
    return palette[index % len(palette)]


def _mirror(geometry: list[float], width: int = 768) -> list[float]:
    return [
        width - value if index % 2 == 0 else value for index, value in enumerate(geometry)
    ]


def _layer(
    layer_id: str,
    shape: str,
    fill: str,
    stroke: str,
    stroke_width: float,
    geometry: list[float],
    *,
    mirror: bool = False,
    opacity_bp: int = 10000,
) -> dict:
    if mirror:
        if shape in ("circle", "ellipse"):
            geometry = [768 - geometry[0], *geometry[1:]]
        else:
            geometry = _mirror(geometry)
    return {
        "layer_id": layer_id,
        "shape": shape,
        "fill": fill,
        "stroke": stroke,
        "stroke_width": stroke_width,
        "opacity_bp": opacity_bp,
        "geometry": [float(value) for value in geometry],
        "closed": shape != "line",
    }


def _figure_layers(character: dict, palette: list[str], variant: dict, tokens: dict) -> list[dict]:
    mirror = bool(variant.get("mirror"))
    face = bool(variant.get("face", True))
    eye_offset = int(variant.get("eye_offset", 0))
    mouth_offset = int(variant.get("mouth_offset", 0))
    accent_x = int(variant.get("accent_x", 0))
    ink = tokens["ink"]
    paper = tokens["paper"]
    layers = [
        _layer("paper", "rect", paper, paper, 0, [0, 0, 768, 1024]),
        _layer("ground", "rect", _tint(palette, 2), paper, 0, [0, 880, 768, 144]),
        _layer(
            "cloak",
            "polygon",
            _tint(palette, 0),
            _tint(palette, 4),
            6,
            [384, 226, 648, 900, 120, 900],
            mirror=mirror,
        ),
        _layer(
            "shoulders",
            "ellipse",
            _tint(palette, 1),
            _tint(palette, 4),
            4,
            [384, 336, 226, 72],
            mirror=mirror,
        ),
        _layer(
            "head",
            "circle",
            _tint(palette, 2),
            _tint(palette, 4),
            4,
            [384, 168, 80],
            mirror=mirror,
        ),
        _layer(
            "motif_band",
            "rect",
            _tint(palette, 3),
            _tint(palette, 4),
            3,
            [176 + accent_x, 604, 416, 56],
            mirror=mirror,
        ),
        _layer("hem", "rect", _tint(palette, 4), ink, 2, [128, 856, 512, 44], mirror=mirror),
        _layer(
            "sleeve",
            "path",
            _tint(palette, 0),
            _tint(palette, 4),
            4,
            [150, 372, 126, 700, 232, 664, 296, 420],
            mirror=mirror,
        ),
    ]
    if face:
        radius = 12 + abs(eye_offset) // 3
        layers.extend(
            [
                _layer(
                    "eye_left",
                    "circle",
                    ink,
                    ink,
                    0,
                    [348, 154 + eye_offset, radius],
                    mirror=mirror,
                ),
                _layer(
                    "eye_right",
                    "circle",
                    ink,
                    ink,
                    0,
                    [420, 154 + eye_offset, radius],
                    mirror=mirror,
                ),
                _layer(
                    "mouth",
                    "line",
                    ink,
                    ink,
                    4,
                    [356, 214 + mouth_offset, 412, 214 + mouth_offset],
                    mirror=mirror,
                ),
            ]
        )
    else:
        layers.append(
            _layer("profile", "line", ink, ink, 3, [384, 86, 384, 862], mirror=mirror, opacity_bp=2500)
        )
    return layers


def _object_layers(character: dict, palette: list[str], variant: dict, tokens: dict) -> list[dict]:
    seed = int(variant.get("motif_seed", 1))
    ink = tokens["ink"]
    paper = tokens["paper"]
    zigzag = []
    for index in range(6):
        x = 232 + index * 60
        y = 460 + (28 if index % 2 == 0 else -28) + seed * 6
        zigzag.extend([x, y])
    return [
        _layer("paper", "rect", paper, paper, 0, [0, 0, 768, 1024]),
        _layer("shadow", "ellipse", _tint(palette, 4), paper, 0, [384, 884, 210, 40], opacity_bp=3500),
        _layer("body", "rect", _tint(palette, 0), _tint(palette, 4), 6, [224, 340, 320, 440]),
        _layer("inset", "rect", _tint(palette, 2), ink, 2, [256, 384, 256, 140]),
        _layer("motif", "path", _tint(palette, 3), ink, 4, zigzag),
        _layer("grip", "line", ink, ink, 10, [384, 300, 384, 344]),
        _layer("base", "rect", _tint(palette, 1), ink, 3, [264, 780, 240, 40]),
    ]


def _costume_layers(character: dict, palette: list[str], variant: dict, tokens: dict) -> list[dict]:
    paper = tokens["paper"]
    ink = tokens["ink"]
    trim = _tint(palette, 3)
    layers = [
        _layer("paper", "rect", paper, paper, 0, [0, 0, 768, 1024]),
        _layer("robe", "polygon", _tint(palette, 0), ink, 6, [384, 180, 700, 940, 68, 940]),
        _layer("collar", "circle", _tint(palette, 1), ink, 4, [384, 200, 74]),
        _layer("hem_band", "rect", _tint(palette, 4), ink, 3, [100, 900, 568, 40]),
    ]
    bands = int(variant.get("trim_bands", 2))
    for index in range(min(bands, 3)):
        top = 420 + index * 120
        layers.append(_layer(f"trim_{index + 1}", "rect", trim, ink, 2, [140, top, 488, 28]))
    layers.append(_layer("crease", "line", ink, ink, 2, [384, 280, 384, 880], opacity_bp=3000))
    return layers


def _landscape_layers(character: dict, palette: list[str], variant: dict, tokens: dict) -> list[dict]:
    sky = variant["sky"]
    hill = variant["hill"]
    sun_x = int(variant["sun_x"])
    ink = tokens["ink"]
    return [
        _layer("sky", "rect", sky, sky, 0, [0, 0, 768, 1024]),
        _layer("sun", "circle", tokens["gold"], sky, 0, [sun_x, 238, 92], opacity_bp=8000),
        _layer("far_hill", "polygon", hill, ink, 3, [0, 620, 240, 470, 520, 640, 768, 520, 768, 1024, 0, 1024]),
        _layer("near_hill", "polygon", _tint(palette, 1), ink, 3, [0, 760, 300, 650, 620, 780, 768, 720, 768, 1024, 0, 1024]),
        _layer("ground", "rect", _tint(palette, 0), ink, 2, [0, 860, 768, 164]),
        _layer("path", "path", _tint(palette, 2), ink, 3, [300, 1024, 360, 860, 420, 860, 460, 1024]),
    ]


BLUEPRINTS = {
    "figure": _figure_layers,
    "object": _object_layers,
    "costume": _costume_layers,
    "landscape": _landscape_layers,
}

KIND_PREFIX = {
    "turnaround": "TURN",
    "expression": "EXPR",
    "prop": "PROP",
    "costume": "COSTUME",
}


def asset_id(character_id: str, kind: str, view_or_name: str) -> str:
    slug = character_id.replace("CHR-", "")
    if kind == "scene":
        return f"VA-SCENE-{view_or_name.upper().replace('_', '-')}"
    if kind == "costume":
        return f"VA-{slug}-COSTUME-{view_or_name.upper()}"
    return f"VA-{slug}-{KIND_PREFIX[kind]}-{view_or_name.upper()}"


def _asset(
    store,
    character: dict,
    kind: str,
    blueprint: str,
    variant: dict,
    palette: list[str],
    tokens: dict,
    config: dict,
) -> dict:
    layers = BLUEPRINTS[blueprint](character, palette, variant, tokens)
    record = {
        "asset_id": asset_id(character["character_id"], kind, variant["view_or_name"]),
        "character_id": character["character_id"],
        "kind": kind,
        "view_or_name": variant["view_or_name"],
        "recipe": {"background": tokens["paper"], "layers": layers},
        "resolution": {"width": int(config["canvas"]["width"]), "height": int(config["canvas"]["height"])},
        "source": {
            "sourcing": "self_produced",
            "ai_assisted": True,
            "authenticity_label": str(character["authenticity_label"])[:160],
            "model_refs": ["qwen-image-3.0 (offline stub in the repository)"],
        },
        "review": {
            "status": "approved",
            "reviewer": REVIEWER,
            "reviewed_at": config["review"]["reviewed_at"],
        },
        "checksum": "",
        "created_at": config["created_at"],
    }
    record["checksum"] = visual_asset_checksum(record)
    store.assert_valid("visual_asset", record)
    return record


def build(store, settings, bible: dict) -> list[dict]:
    config = settings.json("config/ip/visuals.json")
    tokens = config["palette_tokens"]
    assets: list[dict] = []
    for character in bible["canon"]["characters"]:
        palette = list(character["palette"])
        for kind in ("turnaround", "expression", "prop", "costume"):
            plan = config["kinds"][kind]
            for variant in plan["variants"]:
                assets.append(
                    _asset(
                        store,
                        character,
                        kind,
                        plan["blueprint"],
                        variant,
                        palette,
                        tokens,
                        config,
                    )
                )
    characters = bible["canon"]["characters"]
    for index, variant in enumerate(config["kinds"]["scene"]["variants"]):
        character = characters[index % len(characters)]
        assets.append(
            _asset(
                store,
                character,
                "scene",
                "landscape",
                variant,
                list(character["palette"]),
                tokens,
                config,
            )
        )
    return assets


def by_id(assets: list[dict], asset_id_value: str) -> dict:
    for asset in assets:
        if asset["asset_id"] == asset_id_value:
            return asset
    raise KeyError(f"unknown visual asset {asset_id_value}")


def summary(assets: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for asset in assets:
        counts[asset["kind"]] = counts.get(asset["kind"], 0) + 1
    return {
        "assets": len(assets),
        "by_kind": dict(sorted(counts.items())),
        "characters": sorted({asset["character_id"] for asset in assets}),
        "approved": sum(1 for asset in assets if asset["review"]["status"] == "approved"),
        "ai_assisted": sum(1 for asset in assets if asset["source"]["ai_assisted"]),
    }
