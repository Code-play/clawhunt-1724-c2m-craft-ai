"""Limited editions and the collector archive.

An edition has a fixed size and a numbering policy. Numbers are reserved when an
order is placed and issued when it settles, so an edition can be over-requested
but never over-issued. A certificate hash covers the piece identity (edition,
number, concept, certificate id) rather than the owner, which is what lets the
ownership chain move without invalidating the certificate.
"""

from __future__ import annotations

import copy

from ..core.canonical import content_hash
from ..core.errors import Conflict, NotFound, ValidationFailed


class EditionBook:
    def __init__(self, store, settings, concepts: dict) -> None:
        self.store = store
        self.settings = settings
        self.concepts = concepts
        self.editions: dict[str, dict] = {}
        self.records: dict[str, dict] = {}
        self._edition_n = 1
        self._collector_n = 1

    # -- ids -------------------------------------------------------------
    def allocate_edition_id(self) -> str:
        edition_id = f"ED-{self._edition_n:04d}"
        self._edition_n += 1
        return edition_id

    def allocate_collector_id(self) -> str:
        collector_id = f"COL-{self._collector_n:04d}"
        self._collector_n += 1
        return collector_id

    # -- editions --------------------------------------------------------
    def create(
        self,
        *,
        concept_id: str,
        size: int,
        artist: dict,
        workshop_id: str,
        created_at: str,
        title: dict | None = None,
        certificate_prefix: str = "CERT-ED",
    ) -> dict:
        concept = self.concepts.get(concept_id)
        if concept is None:
            raise NotFound(f"concept {concept_id} is not registered")
        if int(size) < 1:
            raise ValidationFailed("an edition needs a positive size")
        workshop = self.settings.workshop(workshop_id)
        edition = {
            "edition_id": self.allocate_edition_id(),
            "title": dict(title or concept["title"]),
            "artist": {
                "artist_id": str(artist.get("artist_id")),
                "name": str(artist.get("name")),
                "royalty_rate_bp": int(artist.get("royalty_rate_bp", 800)),
            },
            "manufacturer": {
                "workshop_id": workshop_id,
                "name": workshop["name"]["en"],
            },
            "concept_id": concept_id,
            "size": int(size),
            "numbering": {"policy": "sequential", "reserved": [], "issued": []},
            "certificate": {
                "template_ref": "docs/data-contracts.md#collector-record",
                "hash_algorithm": "sha256",
                "prefix": certificate_prefix,
            },
            "status": "open",
            "created_at": created_at,
        }
        self.store.assert_valid("edition", edition)
        self.editions[edition["edition_id"]] = edition
        return edition

    def edition(self, edition_id: str) -> dict:
        try:
            return self.editions[edition_id]
        except KeyError as exc:
            raise NotFound(f"edition {edition_id} not found") from exc

    def available_numbers(self, edition_id: str) -> int:
        edition = self.edition(edition_id)
        used = {row["number"] for row in edition["numbering"]["issued"]} | set(
            edition["numbering"]["reserved"]
        )
        return int(edition["size"]) - len(used)

    def reserve(self, edition_id: str, order_id: str) -> dict:
        edition = self.edition(edition_id)
        if edition["status"] != "open":
            raise Conflict(f"edition {edition_id} is {edition['status']}")
        used = {row["number"] for row in edition["numbering"]["issued"]} | set(
            edition["numbering"]["reserved"]
        )
        number = next((value for value in range(1, int(edition["size"]) + 1) if value not in used), None)
        if number is None:
            raise Conflict(f"edition {edition_id} is fully allocated")
        edition["numbering"]["reserved"].append(number)
        self.store.assert_valid("edition", edition)
        return {"edition": edition, "number": number, "order_id": order_id}

    def release(self, edition_id: str, number: int) -> None:
        edition = self.edition(edition_id)
        if number in edition["numbering"]["reserved"]:
            edition["numbering"]["reserved"].remove(number)

    def issue(
        self,
        edition_id: str,
        *,
        number: int,
        order_id: str,
        owner: dict,
        at: str,
        note: str = "issued with the settled order",
    ) -> dict:
        edition = self.edition(edition_id)
        if edition["status"] == "closed":
            raise Conflict(f"edition {edition_id} is closed")
        issued_numbers = {row["number"] for row in edition["numbering"]["issued"]}
        if number in issued_numbers:
            raise Conflict(f"number {number} of {edition_id} is already issued")
        if number < 1 or number > int(edition["size"]):
            raise ValidationFailed(f"number {number} is outside 1..{edition['size']}")
        number = int(number)
        if number in edition["numbering"]["reserved"]:
            edition["numbering"]["reserved"].remove(number)

        record_id = self.allocate_collector_id()
        certificate_id = f"{edition['certificate']['prefix']}-{edition_id.split('-')[-1]}-{number:04d}"
        certificate_hash = content_hash(
            {
                "edition_id": edition_id,
                "edition_number": number,
                "concept_id": edition["concept_id"],
                "certificate_id": certificate_id,
            }
        )
        owner_block = {
            "owner_id": str(owner.get("owner_id")),
            "display_name": str(owner.get("display_name")),
        }
        record = {
            "record_id": record_id,
            "edition_id": edition_id,
            "edition_number": number,
            "certificate_id": certificate_id,
            "certificate_hash": certificate_hash,
            "owner": owner_block,
            "provenance": [
                {
                    "at": at,
                    "from": None,
                    "to": owner_block["owner_id"],
                    "kind": "issue",
                    "note": note,
                }
            ],
            "created_at": at,
        }
        self.store.assert_valid("collector_record", record)
        self.records[record_id] = record

        edition["numbering"]["issued"].append(
            {
                "number": number,
                "collector_id": record_id,
                "order_id": str(order_id),
                "issued_at": at,
                "certificate_id": certificate_id,
            }
        )
        edition["numbering"]["issued"].sort(key=lambda row: row["number"])
        if len(edition["numbering"]["issued"]) == int(edition["size"]):
            edition["status"] = "closed"
        self.store.assert_valid("edition", edition)
        return {"edition": edition, "record": record}

    # -- collector archive ----------------------------------------------
    def record(self, record_id: str) -> dict:
        try:
            return self.records[record_id]
        except KeyError as exc:
            raise NotFound(f"collector record {record_id} not found") from exc

    def transfer(
        self,
        record_id: str,
        *,
        owner_id: str,
        display_name: str,
        at: str,
        note: str = "ownership transferred",
    ) -> dict:
        record = self.record(record_id)
        previous = record["owner"]["owner_id"]
        if owner_id == previous:
            raise ValidationFailed("the new owner must differ from the current owner")
        updated = copy.deepcopy(record)
        updated["owner"] = {"owner_id": owner_id, "display_name": display_name}
        updated["provenance"].append(
            {"at": at, "from": previous, "to": owner_id, "kind": "transfer", "note": note}
        )
        self.store.assert_valid("collector_record", updated)
        self.records[record_id] = updated
        return updated

    def archive(self) -> list[dict]:
        return [
            {
                "record_id": row["record_id"],
                "edition_id": row["edition_id"],
                "edition_number": row["edition_number"],
                "certificate_id": row["certificate_id"],
                "certificate_hash": row["certificate_hash"],
                "owner": row["owner"],
                "provenance_count": len(row["provenance"]),
            }
            for row in sorted(self.records.values(), key=lambda item: item["record_id"])
        ]
