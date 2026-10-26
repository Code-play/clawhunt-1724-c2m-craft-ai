"""Adapter implementations for the creative workstation.

Only the offline adapter ships in M1.  ``ExternalModelAdapter`` is a declared
placeholder with no transport code: wiring a real API in M2 must not change the
call sites, and no network import is allowed in this repository.
"""

from __future__ import annotations

from .workstation import ConceptModelAdapter, ConceptRequest, generate


class OfflineLexiconAdapter:
    """Hash-seeded, vocabulary-driven concept generator (deterministic)."""

    name = "offline_lexicon"
    version = "1.0.0"

    def __init__(self, lexicon: dict, palettes: list[dict], styles: list[dict]) -> None:
        self.lexicon = lexicon
        self.palettes = palettes
        self.styles = styles

    def generate(self, request: ConceptRequest, context: dict) -> list[dict]:
        return generate(
            request,
            lexicon=self.lexicon,
            palettes=self.palettes,
            styles=self.styles,
            created_at=str(context["created_at"]),
            next_id=int(context.get("next_id", 1)),
        )


class ExternalModelAdapter:
    """Declared boundary for M2. Deliberately unimplemented in M1."""

    name = "external_api"
    version = "0.0.0"

    def generate(self, request: ConceptRequest, context: dict) -> list[dict]:
        raise NotImplementedError(
            "M1 ships the offline vocabulary adapter only; M2 wires this boundary to a model API"
        )


def adapter_for(name: str, lexicon: dict, palettes: list[dict], styles: list[dict]):
    if name == "offline_lexicon":
        return OfflineLexiconAdapter(lexicon, palettes, styles)
    if name == "external_api":
        return ExternalModelAdapter()
    raise KeyError(f"unknown adapter {name}")


__all__ = [
    "ConceptModelAdapter",
    "ConceptRequest",
    "OfflineLexiconAdapter",
    "ExternalModelAdapter",
    "adapter_for",
]
