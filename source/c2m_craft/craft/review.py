"""Artisan review queue (the human tier).

The queue is a plain list of contract-validated records.  An override changes
the verdict and therefore must carry a written reason; that rule lives in the
contract invariant and is enforced here as well.
"""

from __future__ import annotations

from ..core.contracts import SchemaStore
from ..core.errors import Conflict, NotFound, ValidationFailed
from .assessment import apply_review, review_reasons
from .rules import RuleSet


class ReviewQueue:
    def __init__(self, store: SchemaStore, *, default_artisan: dict | None = None) -> None:
        self.store = store
        self.items: list[dict] = []
        self._next = 1
        self.default_artisan = default_artisan or {
            "artisan_id": "ART-JW-01",
            "name": "Craft reviewer (synthetic)",
        }

    def allocate_id(self) -> str:
        queue_id = f"AR-{self._next:04d}"
        self._next += 1
        return queue_id

    def create(
        self,
        assessment: dict,
        ruleset: RuleSet,
        *,
        requested_at: str,
        artisan: dict | None = None,
        sla_hours: int = 24,
    ) -> dict:
        failed = review_reasons(assessment, ruleset)
        if not failed:
            raise ValidationFailed("this assessment needs no artisan review")
        queue_id = assessment.get("artisan", {}).get("queue_id") or self.allocate_id()
        item = {
            "queue_id": queue_id,
            "assessment_id": assessment["assessment_id"],
            "concept_id": assessment["concept_id"],
            "rule_ids": sorted({entry["rule_id"] for entry in failed}),
            "requested_at": requested_at,
            "status": "pending",
            "auto_verdict": assessment["auto"]["verdict"],
            "reviewer": dict(artisan or self.default_artisan),
            "decision": None,
            "sla_hours": int(sla_hours),
        }
        self.store.assert_valid("artisan_review", item)
        self.items.append(item)
        return item

    def get(self, queue_id: str) -> dict:
        for item in self.items:
            if item["queue_id"] == queue_id:
                return item
        raise NotFound(f"review item {queue_id} not found")

    def pending(self) -> list[dict]:
        return [item for item in self.items if item["status"] == "pending"]

    def decide(self, queue_id: str, verdict: str, reason: str, *, decided_at: str) -> dict:
        item = self.get(queue_id)
        if item["status"] != "pending":
            raise Conflict(f"review item {queue_id} is already {item['status']}")
        text = (reason or "").strip()
        if verdict != item["auto_verdict"] and len(text) < 8:
            raise ValidationFailed(
                "an override needs a written reason of at least 8 characters"
            )
        item["decision"] = {"verdict": verdict, "reason": text or "confirmed as assessed", "decided_at": decided_at}
        item["status"] = "confirmed" if verdict == item["auto_verdict"] else "overridden"
        self.store.assert_valid("artisan_review", item)
        return item

    def apply(self, assessment: dict, queue_id: str) -> dict:
        return apply_review(assessment, self.get(queue_id))
