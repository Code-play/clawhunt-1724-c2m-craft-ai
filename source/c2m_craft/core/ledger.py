"""Append-only, hash-chained event ledger.

Every order transition writes one row.  Each row hashes the sequence number, the
previous row hash and the row body, so editing, deleting or reordering a row is
detectable without a database.  The verification script recomputes the chain
independently instead of trusting this module's verdict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import canonical

GENESIS = "0" * 64
BODY_FIELDS = (
    "event_id",
    "order_id",
    "seq",
    "at",
    "type",
    "from_status",
    "to_status",
    "actor",
    "payload",
    "prev_hash",
)


class Ledger:
    def __init__(self, path: Path | str | None = None, clock=None) -> None:
        self.path = Path(path) if path else None
        self.clock = clock
        self.events: list[dict] = []
        if self.path and self.path.exists():
            self.events = canonical.read_jsonl(self.path)

    @property
    def head(self) -> str:
        return str(self.events[-1]["hash"]) if self.events else GENESIS

    def append(
        self,
        *,
        event_type: str,
        order_id: str,
        from_status: str,
        to_status: str,
        actor: dict,
        payload: dict | None = None,
        at: str | None = None,
    ) -> dict:
        order_number = order_id.split("-")[-1]
        seq = sum(1 for event in self.events if event["order_id"] == order_id) + 1
        body = {
            "event_id": f"EVT-{order_number}-{seq:04d}",
            "order_id": order_id,
            "seq": seq,
            "at": at or (self.clock.now if self.clock else ""),
            "type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "actor": dict(actor),
            "payload": dict(payload or {}),
            "prev_hash": self.head,
        }
        digest = canonical.content_hash(body)
        record = dict(body)
        record["hash"] = digest
        self.events.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            canonical.append_jsonl(self.path, record)
        return record

    def by_order(self, order_id: str) -> list[dict]:
        return [event for event in self.events if event["order_id"] == order_id]

    def verify(self) -> dict:
        problems: list[str] = []
        previous = GENESIS
        expected_seq = 1
        per_order_seq: dict[str, int] = {}
        for index, event in enumerate(self.events):
            missing = [field for field in BODY_FIELDS if field not in event]
            if missing:
                problems.append(f"row {index}: missing {missing}")
                continue
            if "hash" not in event:
                problems.append(f"row {index}: missing hash")
                continue
            body = {field: event[field] for field in BODY_FIELDS}
            recomputed = canonical.content_hash(body)
            if recomputed != event["hash"]:
                problems.append(f"row {index}: hash mismatch")
            if event["prev_hash"] != previous:
                problems.append(f"row {index}: prev_hash does not chain")
            order_id = event["order_id"]
            per_order_seq[order_id] = per_order_seq.get(order_id, 0) + 1
            if event["seq"] != per_order_seq[order_id]:
                problems.append(f"row {index}: seq {event['seq']} out of order for {order_id}")
            previous = event["hash"]
            expected_seq += 1
        return {
            "ok": not problems,
            "events": len(self.events),
            "orders": len(per_order_seq),
            "head": self.head,
            "problems": problems,
        }

    def snapshot(self) -> list[dict]:
        return list(self.events)

    def export(self) -> list[dict[str, Any]]:
        return [dict(event) for event in self.events]
