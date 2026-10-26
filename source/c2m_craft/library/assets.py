"""Licensed pattern and form library.

Ingestion is gated: an asset that does not declare where it came from and what
it may be used for is rejected with the exact field path.  Search is a simple
weighted match over text, tags and palette; the M1 prototype calls this
"multimodal" only in the narrow sense of text plus palette plus form and says so
in the documentation.
"""

from __future__ import annotations

from pathlib import Path

from ..core.contracts import SchemaStore
from ..core.errors import Conflict, ContractError, NotFound

DESCRIPTOR_FAMILIES = {
    "fret": "geometric",
    "interlace": "floral",
    "wave": "wave",
    "granule": "organic",
    "openwork": "floral",
    "inlay": "inlay",
    "relief": "relief",
}

DESCRIPTOR_DEFAULTS = {
    "geometric": {"symmetry": "translational", "density_bp": 4200, "line_weight": "medium", "edge_complexity": 6},
    "floral": {"symmetry": "bilateral", "density_bp": 6200, "line_weight": "fine", "edge_complexity": 8},
    "wave": {"symmetry": "translational", "density_bp": 3800, "line_weight": "medium", "edge_complexity": 5},
    "organic": {"symmetry": "radial", "density_bp": 5200, "line_weight": "medium", "edge_complexity": 6},
    "inlay": {"symmetry": "translational", "density_bp": 3000, "line_weight": "bold", "edge_complexity": 4},
    "relief": {"symmetry": "bilateral", "density_bp": 7000, "line_weight": "bold", "edge_complexity": 9},
}


class Library:
    def __init__(self, store: SchemaStore, settings, assets: list[dict]) -> None:
        self.store = store
        self.settings = settings
        self.assets = list(assets)
        self.by_id = {str(asset["asset_id"]): asset for asset in self.assets}

    @classmethod
    def from_file(cls, store: SchemaStore, settings, path: Path | str) -> "Library":
        data = SchemaStore.json_load(path)
        return cls(store, settings, list(data.get("assets", [])))

    # -- ingestion -------------------------------------------------------
    def ingest(self, payload: dict, *, require_active_window: bool = True) -> dict:
        issues = self.store.validate(
            "pattern_asset",
            payload,
            ctx={
                "as_of": self.settings.as_of,
                "require_active_window": require_active_window,
            },
        )
        if issues:
            raise ContractError("pattern_asset", [issue.as_dict() for issue in issues])
        asset_id = str(payload["asset_id"])
        if asset_id in self.by_id:
            raise Conflict(f"asset {asset_id} already exists")
        self.assets.append(payload)
        self.by_id[asset_id] = payload
        return payload

    # -- lookup ----------------------------------------------------------
    def get(self, asset_id: str) -> dict:
        try:
            return self.by_id[asset_id]
        except KeyError as exc:
            raise NotFound(f"asset {asset_id} not found") from exc

    def license_state(
        self, asset: dict, usage: str | None = None, *, as_of: str | None = None
    ) -> dict:
        moment = str(as_of or self.settings.as_of)
        license_block = asset.get("license") or {}
        reasons: list[str] = []
        start = str(license_block.get("valid_from", ""))
        end = str(license_block.get("valid_to", ""))
        if start and end and not (start <= moment <= end):
            reasons.append(f"licence window {start}..{end} does not cover {moment}")
        scopes = list(license_block.get("usage_scope") or [])
        if usage and usage not in scopes:
            reasons.append(f"usage {usage!r} is not granted (scope: {', '.join(scopes) or 'none'})")
        return {
            "asset_id": asset["asset_id"],
            "ok": not reasons,
            "reasons": reasons,
            "usage_scope": scopes,
            "window": {"from": start, "to": end},
            "source_type": license_block.get("source_type"),
            "attribution_required": bool(license_block.get("attribution_required")),
            "exclusive": bool(license_block.get("exclusive")),
        }

    # -- search ----------------------------------------------------------
    def descriptor(self, asset: dict) -> dict:
        """Explicit descriptor when present, otherwise derived from the motif style."""
        if asset.get("descriptor"):
            return dict(asset["descriptor"])
        style = str((asset.get("preview") or {}).get("motif_style", "fret"))
        family = DESCRIPTOR_FAMILIES.get(style, "geometric")
        defaults = DESCRIPTOR_DEFAULTS[family]
        return {
            "motif_family": family,
            "symmetry": defaults["symmetry"],
            "density_bp": defaults["density_bp"],
            "line_weight": defaults["line_weight"],
            "edge_complexity": defaults["edge_complexity"],
        }

    def search(
        self,
        *,
        query: str = "",
        tags: list[str] | None = None,
        palette: list[str] | None = None,
        industry: str | None = None,
        motif_family: str | None = None,
        symmetry: str | None = None,
        line_weight: str | None = None,
        density_bp: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        tokens = [token for token in str(query).lower().split() if token]
        wanted_tags = [tag.lower() for tag in (tags or [])]
        results = []
        for asset in self.assets:
            if industry and industry not in asset.get("industries", []):
                continue
            haystack = " ".join(
                [
                    asset["title"].get("zh", ""),
                    asset["title"].get("en", ""),
                    " ".join(asset.get("tags", [])),
                    str(asset.get("medium", "")),
                ]
            ).lower()
            matched: list[str] = []
            score = 0
            for token in tokens:
                if token in haystack:
                    score += 10
                    matched.append(token)
            for tag in wanted_tags:
                if tag in [item.lower() for item in asset.get("tags", [])]:
                    score += 5
                    if tag not in matched:
                        matched.append(tag)
            if tokens and not matched:
                continue
            if wanted_tags and not set(wanted_tags) & {item.lower() for item in asset.get("tags", [])}:
                continue
            if palette:
                score += _palette_bonus(asset.get("palette", []), palette)

            descriptor = self.descriptor(asset)
            if motif_family:
                if descriptor["motif_family"] == motif_family:
                    score += 4
                    matched.append(f"family:{motif_family}")
                else:
                    continue
            if symmetry:
                if descriptor["symmetry"] == symmetry:
                    score += 3
                    matched.append(f"symmetry:{symmetry}")
                else:
                    continue
            if line_weight:
                if descriptor["line_weight"] == line_weight:
                    score += 2
                    matched.append(f"weight:{line_weight}")
                else:
                    continue
            if density_bp is not None:
                closeness = max(0, 4 - abs(int(descriptor["density_bp"]) - int(density_bp)) // 1500)
                if closeness:
                    score += closeness
                    matched.append(f"density:{closeness}")
            results.append(
                {
                    "asset": asset,
                    "score": score,
                    "matched": matched,
                    "descriptor": descriptor,
                    "license": self.license_state(asset),
                }
            )
        results.sort(key=lambda row: (-row["score"], str(row["asset"]["asset_id"])))
        return results[: max(1, min(limit, 50))]

    def licence_terms(
        self, asset: dict, *, usage: str | None = None, territory: str | None = None
    ) -> dict:
        """The licensing terms an order has to satisfy before it can use the asset."""
        state = self.license_state(asset, usage=usage)
        reasons = list(state["reasons"])
        license_block = asset.get("license") or {}
        territories = list(license_block.get("territory") or [])
        if territory and territories and territory not in territories and "global" not in territories:
            reasons.append(f"territory {territory!r} is not licensed (granted: {', '.join(territories)})")
        return {
            "asset_id": asset["asset_id"],
            "ok": not reasons,
            "reasons": reasons,
            "royalty_rate_bp": int(license_block.get("royalty_rate_bp", 0)),
            "licensor": str(license_block.get("licensor") or license_block.get("source_type") or "self"),
            "attribution_required": bool(license_block.get("attribution_required")),
            "exclusive": bool(license_block.get("exclusive")),
        }


def _palette_bonus(asset_colors: list[str], reference: list[str]) -> int:
    if not asset_colors or not reference:
        return 0
    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    bonus = 0
    for color in reference:
        if not (len(color) == 7 and color.startswith("#")):
            continue
        target = rgb(color)
        best = min(
            (target[0] - other[0]) ** 2 + (target[1] - other[1]) ** 2 + (target[2] - other[2]) ** 2
            for other in (rgb(value) for value in asset_colors)
        )
        bonus += max(0, 8 - best // 4000)
    return bonus
