"""Dual guardian character bible.

The bible is the canon the rest of the IP pipeline hangs from: the visual asset
library draws its palettes and motifs, the short drama casts its characters and
the licence package names them.  It is built from ``config/ip/characters.json`` and
must cite one content review per guardian.
"""

from __future__ import annotations

from ..core.errors import ValidationFailed

CHARACTER_FIELDS = (
    "character_id",
    "name",
    "role",
    "element",
    "archetype",
    "personality",
    "silhouette",
    "palette",
    "motifs",
    "taboos",
    "props",
    "voice",
    "relationships",
    "story_arc",
    "licence_safe_sourcing",
    "authenticity_label",
    "content_review_ref",
)


def build(store, settings, reviews: dict[str, dict]) -> dict:
    config = settings.json("config/ip/characters.json")
    characters = []
    for character in config["characters"]:
        missing = [field for field in CHARACTER_FIELDS if field not in character]
        if missing:
            raise ValidationFailed(f"character {character.get('character_id')} lacks {missing}")
        if character["content_review_ref"] not in reviews:
            raise ValidationFailed(
                f"character {character['character_id']} cites an unknown content review"
            )
        characters.append({field: character[field] for field in CHARACTER_FIELDS})
    record = {
        "bible_id": config["bible_id"],
        "version": config["version"],
        "title": config["title"],
        "world": config["world"],
        "canon": {"characters": characters},
        "heritage_refs": config["heritage_refs"],
        "usage_plan": config["usage_plan"],
        "created_at": config["created_at"],
    }
    store.assert_valid("character_bible", record)
    return record


def character(record: dict, character_id: str) -> dict:
    for item in record["canon"]["characters"]:
        if item["character_id"] == character_id:
            return item
    raise KeyError(f"unknown character {character_id}")
