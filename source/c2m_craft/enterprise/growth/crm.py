"""Inquiry to CRM closed loop.

An inquiry arrives from the multilingual site, becomes a lead with a deterministic
score and an owner, gets its follow-up tasks and (when the desk answers) a quote
draft.  Every step appends a CRM event; the stage is a function of those events,
which is what the invariant checks and what the end-to-end test asserts.
"""

from __future__ import annotations

from ...core.clock import add_days, add_minutes
from ...core.errors import Conflict, NotFound
from ...core.invariants import MAX_REASON_MIN


def _clamped(value: int) -> int:
    return max(0, min(100, value))


class CrmLoop:
    def __init__(self, store, settings) -> None:
        self.store = store
        self.settings = settings
        self.policy = settings.json("config/growth/crm.json")
        self.inquiries: dict[str, dict] = {}
        self._inquiry_n = 0
        self._follow_n = 0
        self._quote_n = 0

    # -- scoring ---------------------------------------------------------
    def _factor_points(self, factor: dict, contact: dict, intent: str, message: str):
        match = factor["match"]
        if match == "intent":
            table = factor["points"]
            if intent not in table:
                return None
            return int(table[intent]), f"intent={intent}"
        if match == "country":
            table = factor["points"]
            country = str(contact.get("country", ""))
            if country in table:
                return int(table[country]), f"country={country}"
            return int(factor.get("default_points", 0)), f"country={country} (not a focus market)"
        if match == "company":
            if contact.get("company"):
                return int(factor["points"]), f"company={contact['company']}"
            return None
        if match == "not_company":
            if not contact.get("company"):
                return int(factor["points"]), "no company on the inquiry"
            return None
        if match == "mentions_quantity":
            lowered = message.lower()
            for marker in self.policy["scoring"]["message_quantity_markers"]:
                if marker.lower() in lowered:
                    return int(factor["points"]), f"message mentions {marker}"
            return None
        return None

    def score(self, contact: dict, intent: str, message: str) -> tuple[int, list[dict]]:
        base = int(self.policy["scoring"]["base_points"])
        breakdown = [{"factor": "base", "points": base, "evidence": "qualified inquiry baseline"}]
        for factor in self.policy["scoring"]["factors"]:
            resolved = self._factor_points(factor, contact, intent, message)
            if resolved is None:
                continue
            points, evidence = resolved
            breakdown.append(
                {"factor": factor["factor"], "points": points, "evidence": evidence}
            )
        total = _clamped(sum(row["points"] for row in breakdown))
        return total, breakdown

    def _route(self, intent: str) -> dict:
        for rule in self.policy["routing"]:
            if intent in rule["when_intent"]:
                return dict(rule["owner"])
        return dict(self.policy["routing"][-1]["owner"])

    def _follow_ups(self, intent: str, submitted_at: str) -> list[dict]:
        rows = []
        for template in self.policy["follow_ups"]:
            if intent not in template["when_intent"]:
                continue
            self._follow_n += 1
            rows.append(
                {
                    "follow_up_id": f"FU-{self._follow_n:04d}",
                    "due_at": add_minutes(submitted_at, float(template["offset_hours"]) * 60),
                    "channel": template["channel"],
                    "template_id": template["template_id"],
                    "status": "scheduled",
                    "done_at": None,
                }
            )
        rows.sort(key=lambda row: row["due_at"])
        return rows

    # -- intake ----------------------------------------------------------
    def intake(self, payload: dict, *, at: str) -> dict:
        site_id = str(payload["site_id"])
        language = str(payload.get("language") or "en")
        contact = payload["contact"]
        message = str(payload["message"])
        intent = str(payload["intent"])
        self._inquiry_n += 1
        score, breakdown = self.score(contact, intent, message)
        owner = self._route(intent)
        sla_hours = float(self.policy["sla_hours"])
        record = {
            "inquiry_id": f"INQ-{self._inquiry_n:04d}",
            "site_id": site_id,
            "language": language,
            "submitted_at": at,
            "contact": {
                key: contact[key]
                for key in ("name", "email", "company", "country", "channel")
                if contact.get(key) is not None
            },
            "message": message,
            "intent": intent,
            "product_interest": list(payload.get("product_interest") or ["custom jewellery"]),
            "lead": {
                "lead_id": f"LEAD-{self._inquiry_n:04d}",
                "stage": "qualified",
                "score": score,
                "score_breakdown": breakdown,
                "owner": owner,
                "sla_due_at": add_minutes(at, sla_hours * 60),
                "first_response_at": None,
            },
            "follow_ups": self._follow_ups(intent, at),
            "quote": None,
            "crm_events": [
                {"at": at, "type": "received", "actor": "site", "note": f"inquiry received from {site_id}"},
                {
                    "at": add_minutes(at, 1),
                    "type": "scored",
                    "actor": "crm_scorer",
                    "note": f"score {score} from {len(breakdown)} factors",
                },
                {
                    "at": add_minutes(at, 2),
                    "type": "routed",
                    "actor": "crm_router",
                    "note": f"routed to {owner['owner_id']}",
                },
            ],
            "created_at": at,
        }
        self.store.assert_valid("inquiry_lead", record)
        self.inquiries[record["inquiry_id"]] = record
        return record

    # -- pipeline --------------------------------------------------------
    def _event_type(self, stage: str) -> str:
        return str(self.policy["pipeline"]["stage_events"][stage])

    def _quote(self, record: dict, at: str) -> dict:
        self._quote_n += 1
        intent = str(record["intent"])
        amount = int(self.policy["quote"]["base_amount_cents"].get(intent, 0))
        country = str(record["contact"].get("country", ""))
        incoterm = self.policy["quote"]["incoterm_by_country"].get(
            country, self.policy["quote"]["default_incoterm"]
        )
        return {
            "quote_id": f"QTE-{self._quote_n:04d}",
            "amount_cents": amount,
            "currency": "USD",
            "valid_until": add_days(at, float(self.policy["quote"]["valid_days"])),
            "incoterm": incoterm,
        }

    def advance(self, inquiry_id: str, stage: str, *, at: str, note: str) -> dict:
        record = self.get(inquiry_id)
        current = str(record["lead"]["stage"])
        allowed = self.policy["pipeline"]["allowed_transitions"].get(current, [])
        if stage not in allowed:
            raise Conflict(f"stage {current} cannot move to {stage}")
        if len(str(note).strip()) < MIN_EVENT_NOTE:
            raise Conflict("a pipeline step needs a written note")
        event_type = self._event_type(stage)
        if stage == "contacted" and not record["lead"]["first_response_at"]:
            record["lead"]["first_response_at"] = at
        if stage == "quoted":
            record["quote"] = self._quote(record, at)
        record["lead"]["stage"] = stage
        record["crm_events"].append(
            {"at": at, "type": event_type, "actor": "export_desk", "note": str(note).strip()}
        )
        self.store.assert_valid("inquiry_lead", record)
        self.inquiries[inquiry_id] = record
        return record

    def get(self, inquiry_id: str) -> dict:
        try:
            return self.inquiries[inquiry_id]
        except KeyError as exc:
            raise NotFound(f"inquiry {inquiry_id} not found") from exc

    # -- views -----------------------------------------------------------
    def board(self, *, now: str) -> dict:
        stages = list(self.policy["pipeline"]["stages"])
        columns = {stage: [] for stage in stages}
        breaches = []
        for record in self.inquiries.values():
            stage = str(record["lead"]["stage"])
            lead = record["lead"]
            columns.setdefault(stage, []).append(
                {
                    "inquiry_id": record["inquiry_id"],
                    "lead_id": lead["lead_id"],
                    "language": record["language"],
                    "intent": record["intent"],
                    "score": lead["score"],
                    "owner": lead["owner"]["name"],
                    "sla_due_at": lead["sla_due_at"],
                    "first_response_at": lead["first_response_at"],
                    "quote": record.get("quote"),
                }
            )
            if not lead["first_response_at"] and str(lead["sla_due_at"]) < now:
                breaches.append(record["inquiry_id"])
        return {
            "stages": [
                {
                    "stage": stage,
                    "count": len(columns.get(stage, [])),
                    "leads": sorted(columns.get(stage, []), key=lambda row: row["lead_id"]),
                }
                for stage in stages
            ],
            "sla_breaches": sorted(breaches),
            "open_follow_ups": sorted(
                (
                    {
                        "inquiry_id": record["inquiry_id"],
                        "follow_up_id": row["follow_up_id"],
                        "due_at": row["due_at"],
                        "channel": row["channel"],
                        "template_id": row["template_id"],
                        "language": record["language"],
                    }
                    for record in self.inquiries.values()
                    for row in record["follow_ups"]
                    if row["status"] == "scheduled"
                ),
                key=lambda row: (row["due_at"], row["inquiry_id"]),
            ),
        }

    def report(self, *, now: str) -> dict:
        records = [self.inquiries[key] for key in sorted(self.inquiries)]
        board = self.board(now=now)
        stage_counts = {row["stage"]: row["count"] for row in board["stages"]}
        quoted = [record["quote"] for record in records if record.get("quote")]
        trace = [
            {
                "inquiry_id": record["inquiry_id"],
                "language": record["language"],
                "intent": record["intent"],
                "score": record["lead"]["score"],
                "stage": record["lead"]["stage"],
                "owner": record["lead"]["owner"],
                "steps": [
                    {"at": event["at"], "type": event["type"], "note": event["note"]}
                    for event in record["crm_events"]
                ],
            }
            for record in records
        ]
        return {
            "version": "1.0.0",
            "policy": {
                "sla_hours": self.policy["sla_hours"],
                "stages": list(self.policy["pipeline"]["stages"]),
                "scoring_factors": [factor["factor"] for factor in self.policy["scoring"]["factors"]],
            },
            "inquiries": records,
            "board": board,
            "trace": trace,
            "summary": {
                "inquiries": len(records),
                "stage_counts": stage_counts,
                "quoted": len(quoted),
                "quoted_value_cents": sum(int(quote["amount_cents"]) for quote in quoted),
                "sla_breaches": len(board["sla_breaches"]),
                "follow_ups_open": len(board["open_follow_ups"]),
            },
        }


MIN_EVENT_NOTE = 12
