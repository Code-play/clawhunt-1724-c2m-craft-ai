"""Configuration access.

All configuration is data: industry profiles, craft rules, workshop capability
envelopes, creative vocabulary, pricing and the order state machines.  Nothing
in the code hard-codes a workshop, an alloy or a price, which is what makes
"switch industry by configuration" true rather than a slogan.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Settings:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else ROOT
        self._cache: dict[str, dict] = {}
        self.site = self.json("config/site.json")

    # -- generic ---------------------------------------------------------
    def path(self, relative: str) -> Path:
        return self.root / relative

    def json(self, relative: str) -> dict:
        if relative not in self._cache:
            path = self.path(relative)
            with open(path, "r", encoding="utf-8") as handle:
                self._cache[relative] = json.load(handle)
        return self._cache[relative]

    # -- site ------------------------------------------------------------
    @property
    def as_of(self) -> str:
        return str(self.site["as_of"])

    @property
    def currency(self) -> str:
        return str(self.site.get("currency", "USD"))

    # -- industries ------------------------------------------------------
    def industry_ids(self) -> list[str]:
        return sorted(path.stem for path in self.path("config/industries").glob("*.json"))

    def industry(self, industry: str) -> dict:
        return self.json(f"config/industries/{industry}.json")

    def rules_path(self, industry: str) -> Path:
        return self.path(f"config/craft_rules/{industry}.json")

    # -- workshops -------------------------------------------------------
    def workshop_ids(self, industry: str | None = None) -> list[str]:
        ids = []
        for path in sorted(self.path("config/equipment").glob("*.json")):
            data = self.json(f"config/equipment/{path.name}")
            if industry is None or data.get("industry") == industry:
                ids.append(str(data["workshop_id"]))
        return ids

    def workshop(self, workshop_id: str) -> dict:
        return self.json(f"config/equipment/{workshop_id}.json")

    # -- creative vocabulary --------------------------------------------
    def lexicon(self) -> dict:
        return self.json("config/creative/lexicon.json")

    def palettes(self) -> dict:
        return self.json("config/creative/palettes.json")

    def styles(self) -> dict:
        return self.json("config/creative/styles.json")

    def series_config(self) -> dict:
        return self.json("config/creative/series.json")

    # -- commerce --------------------------------------------------------
    def pricing(self) -> dict:
        return self.json("config/commerce/pricing.json")

    def state_machine(self) -> dict:
        return self.json("config/commerce/state_machine.json")

    def split_policy(self) -> dict:
        return dict(self.pricing()["split_policy"])

    def base_price(self, industry: str, category: str) -> int:
        prices = self.pricing()["base_prices_cents"]
        return int(prices[industry][category])
