"""Pre-sale order lifecycle: amounts, transitions, refunds, disputes, settlement.

The order is the spine of the C2M flow: pre-sale ordering, craft work order,
dispatch, quality control, shipment and revenue sharing all hang off one record
whose every state change is appended to the hash-chained ledger.  Refund and
dispute are sub-states, so a settlement cannot be corrupted by a late refund.
"""

from __future__ import annotations

from ..core import money
from ..core.clock import add_days
from ..core.contracts import SchemaStore
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..craft.assessment import assess
from ..craft.review import ReviewQueue
from ..craft.rules import RuleSet
from . import capacity as capacity_mod
from . import customization as customization_mod
from . import dispatch as dispatch_mod
from . import editions as editions_mod
from . import quality as quality_mod
from . import settlement as settlement_mod
from .state import StateMachine

ACTIVE_STATES = (
    "paid",
    "work_order_issued",
    "dispatched",
    "in_production",
    "qc_failed",
    "qc_passed",
    "shipped",
)


def _artisan_for(industry: str) -> dict:
    if industry == "hardwood":
        return {"artisan_id": "ART-HW-01", "name": "Woodworking craft reviewer (synthetic)"}
    return {"artisan_id": "ART-JW-01", "name": "Jewelry craft reviewer (synthetic)"}


class Commerce:
    def __init__(
        self,
        store: SchemaStore,
        settings,
        clock,
        ledger,
        *,
        concepts: dict[str, dict] | None = None,
        rulesets: dict[str, RuleSet] | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.clock = clock
        self.ledger = ledger
        self.concepts: dict[str, dict] = dict(concepts or {})
        self.rulesets: dict[str, RuleSet] = dict(rulesets or {})
        self.orders: dict[str, dict] = {}
        self.work_orders: dict[str, dict] = {}
        self.settlements: dict[str, dict] = {}
        self.assessments: dict[str, dict] = {}

        machines = settings.state_machine()
        self.main = StateMachine(machines["main"])
        self.refund_machine = StateMachine(machines["refund"])
        self.dispute_machine = StateMachine(machines["dispute"])

        self.reviews = ReviewQueue(store)
        self.catalog = customization_mod.CustomizationCatalog(settings)
        self.planner = capacity_mod.CapacityPlanner(settings, store, self.rulesets)
        self.quality = quality_mod.QualityBook(store, settings)
        self.editions = editions_mod.EditionBook(store, settings, self.concepts)
        self.customizations: dict[str, dict] = {}
        self.library = None
        self._order_n = 0
        self._wo_n = 0
        self._st_n = 0
        self._ma_n = 0
        self._customization_n = 0
        self._slot_n = 0
        self._schedule_n = 0

    def attach_library(self, library) -> None:
        """Give the order book access to licensed assets for royalty allocation."""
        self.library = library

    # -- ids and time ----------------------------------------------------
    def _stamp(self, at: str | None = None) -> str:
        if at:
            return at
        stamp = self.clock.now
        self.clock.advance(1)
        return stamp

    def next_order_id(self) -> str:
        self._order_n += 1
        return f"ORD-{self._order_n:04d}"

    def next_work_order_id(self) -> str:
        self._wo_n += 1
        return f"WO-{self._wo_n:04d}"

    def next_settlement_id(self) -> str:
        self._st_n += 1
        return f"ST-{self._st_n:04d}"

    def next_assessment_id(self) -> str:
        self._ma_n += 1
        return f"MA-{self._ma_n:04d}"

    def next_customization_id(self) -> str:
        self._customization_n += 1
        return f"CUS-{self._customization_n:04d}"

    def next_slot_id(self) -> str:
        self._slot_n += 1
        return f"SLOT-{self._slot_n:04d}"

    # -- pricing ---------------------------------------------------------
    def price(self, concept: dict, quantity: int = 1, *, unit_price_cents: int | None = None) -> dict:
        industry = str(concept["industry"])
        category = str(concept["form"]["category"])
        unit = int(unit_price_cents) if unit_price_cents is not None else self.settings.base_price(industry, category)
        subtotal = unit * int(quantity)
        pricing = self.settings.pricing()
        fee = money.apply_rate(subtotal, int(pricing["customization_fee_bp"]))
        total = subtotal + fee
        deposit = money.apply_rate(total, int(pricing["deposit_bp"]))
        shares = money.shares_by_party(total, pricing["split_policy"]["lines"])
        by_party = {line["party"]: int(line["amount_cents"]) for line in shares}
        return {
            "subtotal_cents": subtotal,
            "customization_fee_cents": fee,
            "deposit_cents": deposit,
            "total_cents": total,
            "platform_fee_cents": by_party["platform"],
            "designer_share_cents": by_party["designer"],
            "factory_share_cents": by_party["factory"],
            "ip_share_cents": by_party["ip_licensor"],
        }

    # -- creation --------------------------------------------------------
    def create_order(
        self,
        concept: dict,
        *,
        model: str = "designer_presale",
        buyer: dict | None = None,
        quantity: int = 1,
        customizations: list[str] | None = None,
        asset_license_ids: list[str] | None = None,
        customization: dict | None = None,
        edition_id: str | None = None,
        workshop_id: str | None = None,
        at: str | None = None,
    ) -> dict:
        stamp = self._stamp(at)
        order_id = self.next_order_id()
        if concept["industry"] not in self.rulesets:
            raise ValidationFailed(f"no rule set loaded for industry {concept['industry']}")
        buyer_block = dict(buyer or {"id": "buyer-01", "locale": "en"})
        self.concepts[str(concept["concept_id"])] = concept

        unit_price = None
        extra_lead_days = 0
        if customization is not None:
            self.store.assert_valid(
                "customization_choice", customization, ctx={"as_of": self.settings.as_of}
            )
            unit_price = int(customization["amounts"]["unit_price_cents"])
            extra_lead_days = customization_mod.lead_time_delta(customization)
        amounts = self.price(concept, quantity, unit_price_cents=unit_price)

        licensed_assets = list(
            asset_license_ids if asset_license_ids is not None else concept.get("asset_refs", [])
        )
        if licensed_assets and self.library is not None:
            for asset_id in licensed_assets:
                asset = self.library.get(asset_id)
                terms = self.library.licence_terms(asset, usage="commercial_product")
                if not terms["ok"]:
                    raise Conflict(
                        f"asset {asset_id} cannot be used in this order: " + "; ".join(terms["reasons"])
                    )

        promise = self.planner.quote(
            concept,
            at=stamp,
            quantity=quantity,
            extra_lead_days=extra_lead_days,
            candidates=[workshop_id] if workshop_id else None,
            work_orders=list(self.work_orders.values()),
        )

        edition_number = None
        if edition_id:
            reservation = self.editions.reserve(edition_id, order_id)
            edition_number = int(reservation["number"])

        order = {
            "order_id": order_id,
            "model": model,
            "status": "draft",
            "buyer": buyer_block,
            "items": [
                {
                    "item_id": "ITM-0001",
                    "concept_id": concept["concept_id"],
                    "title": dict(concept["title"]),
                    "quantity": int(quantity),
                    "unit_price_cents": amounts["subtotal_cents"] // max(int(quantity), 1),
                    "asset_license_ids": licensed_assets,
                    "work_order_id": None,
                    "customizations": list(customizations or []),
                    "customization_id": customization["customization_id"] if customization else None,
                    "edition_id": edition_id,
                    "edition_number": edition_number,
                }
            ],
            "amounts": amounts,
            "currency": "USD",
            "deadline_at": add_days(stamp, float(self.settings.pricing()["quote_validity_days"])),
            "promise": {
                "workshop_id": promise["workshop_id"],
                "promised_delivery_at": promise["promised_delivery_at"],
                "slot_id": self.next_slot_id(),
                "working_minutes": int(promise["working_minutes"]),
                "alternatives": list(promise["alternatives"]),
            },
            "refund": {
                "status": "none",
                "amount_cents": 0,
                "reason": None,
                "requested_at": None,
                "decided_at": None,
            },
            "dispute": {
                "status": "none",
                "reason": None,
                "resolution_note": None,
                "opened_at": None,
                "resolved_at": None,
                "qc_record_ids": [],
            },
            "created_at": stamp,
            "updated_at": stamp,
        }
        self._validate(order)
        self.orders[order_id] = order
        self._log(
            order, "order_created", "none", "draft",
            {"kind": "buyer", "id": buyer_block["id"]},
            {
                "amounts": amounts,
                "concept_id": concept["concept_id"],
                "promise": order["promise"],
                **({"customization_id": customization["customization_id"]} if customization else {}),
                **({"edition_id": edition_id, "edition_number": edition_number} if edition_id else {}),
            },
            stamp,
        )
        return order

    # -- transition helpers ---------------------------------------------
    def _validate(self, order: dict) -> None:
        self.store.assert_valid(
            "c2m_order", order, ctx={"allowed_statuses": self.main.states}
        )

    def _log(
        self,
        order: dict,
        event_type: str,
        from_status: str,
        to_status: str,
        actor: dict,
        payload: dict,
        at: str,
    ) -> dict:
        order["updated_at"] = at
        return self.ledger.append(
            event_type=event_type,
            order_id=order["order_id"],
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            payload=payload,
            at=at,
        )

    def get(self, order_id: str) -> dict:
        try:
            return self.orders[order_id]
        except KeyError as exc:
            raise NotFound(f"order {order_id} not found") from exc

    def available_events(self, order_id: str) -> list[dict]:
        return self.main.available(self.get(order_id)["status"])

    def events(self, order_id: str) -> list[dict]:
        self.get(order_id)
        return self.ledger.by_order(order_id)

    # -- main pipeline ---------------------------------------------------
    def transition(
        self,
        order_id: str,
        event: str,
        *,
        actor: dict | None = None,
        payload: dict | None = None,
        at: str | None = None,
    ) -> dict:
        order = self.get(order_id)
        actor = dict(actor or {"kind": "system", "id": "system"})
        stamp = self._stamp(at)
        target = self.main.target(order["status"], event, actor["kind"])
        previous = order["status"]
        created_work_order = None
        created_settlement = None
        event_payload = dict(payload or {})

        if event == "payment_received":
            event_payload.setdefault("amount_cents", order["amounts"]["total_cents"])
            event_payload.setdefault("deposit_cents", order["amounts"]["deposit_cents"])
        elif event == "work_order_issued":
            created_work_order = self._issue_work_order(order, stamp)
            order["items"][0]["work_order_id"] = created_work_order["work_order_id"]
            event_payload["work_order_id"] = created_work_order["work_order_id"]
        elif event in ("qc_passed", "qc_failed"):
            status = "passed" if event == "qc_passed" else "failed"
            self._mark_qc(order, status)
            event_payload.setdefault("checkpoint_status", status)
        elif event == "settled":
            created_settlement = self._settle(order, stamp)
            event_payload["settlement_id"] = created_settlement["settlement_id"]
            event_payload["settled_cents"] = created_settlement["total_cents"]
            event_payload["payouts"] = [
                line["amount_cents"] for line in created_settlement["payout_lines"]
            ]
            if created_settlement["refunds"]:
                event_payload["refunded_cents"] = sum(
                    entry["amount_cents"] for entry in created_settlement["refunds"]
                )
            if created_settlement.get("royalty_lines"):
                event_payload["royalty_lines"] = created_settlement["royalty_lines"]
                event_payload["ip_share_cents"] = sum(
                    line["amount_cents"]
                    for line in created_settlement["payout_lines"]
                    if line["party"] == "ip_licensor"
                )
            edition = self._issue_edition(order, stamp)
            if edition:
                event_payload["edition"] = edition

        order["status"] = target
        self._validate(order)
        record = self._log(order, event, previous, target, actor, event_payload, stamp)
        return {
            "order": order,
            "event": record,
            "work_order": created_work_order,
            "settlement": created_settlement,
        }

    def _issue_work_order(self, order: dict, stamp: str) -> dict:
        item = order["items"][0]
        concept = self.concepts.get(item["concept_id"])
        if concept is None:
            raise NotFound(f"concept {item['concept_id']} is not registered in this session")
        industry = str(concept["industry"])
        promise = order.get("promise") or {}
        workshop_id = str(
            promise.get("workshop_id") or self.settings.industry(industry)["default_workshop"]
        )
        workshop = self.settings.workshop(workshop_id)
        ruleset = self.rulesets[industry]
        assessment_id = self.next_assessment_id()
        assessment = assess(
            concept,
            workshop,
            ruleset,
            assessment_id=assessment_id,
            created_at=stamp,
            queue_id=None,
        )
        self.store.assert_valid(
            "manufacturability_assessment", assessment, ctx={"as_of": self.settings.as_of}
        )
        self.assessments[assessment_id] = assessment
        if assessment["final_verdict"] == "not_manufacturable":
            raise Conflict(
                f"concept {concept['concept_id']} is not manufacturable at {workshop_id}: "
                + ", ".join(assessment["blockers"])
            )
        if assessment["artisan"]["required"]:
            review = self.reviews.create(
                assessment,
                ruleset,
                requested_at=stamp,
                artisan=_artisan_for(industry),
            )
            assessment["artisan"]["queue_id"] = review["queue_id"]
            assessment["artisan"]["status"] = "pending"
        work_order_id = self.next_work_order_id()
        work_order = dispatch_mod.build(
            self.store,
            order,
            concept,
            workshop,
            self.settings.industry(industry),
            assessment,
            work_order_id=work_order_id,
            created_at=stamp,
        )
        if promise.get("promised_delivery_at"):
            work_order["promised_delivery_at"] = str(promise["promised_delivery_at"])
        if promise.get("slot_id") and work_order["process_steps"]:
            work_order["process_steps"][0]["constraints"].append(
                f"capacity slot {promise['slot_id']} reserved at {workshop_id} "
                f"for {promise.get('working_minutes')} minutes"
            )
        self.store.assert_valid("craft_work_order", work_order)
        self.work_orders[work_order_id] = work_order
        return work_order

    def _mark_qc(self, order: dict, status: str) -> None:
        work_order_id = order["items"][0].get("work_order_id")
        if not work_order_id:
            raise Conflict("no work order to inspect")
        work_order = self.work_orders[work_order_id]
        checkpoints = work_order["qc_checkpoints"]
        if status == "passed":
            for checkpoint in checkpoints:
                checkpoint["status"] = "passed"
            work_order["status"] = "completed"
            return
        pending = next((item for item in checkpoints if item["status"] == "pending"), None)
        if pending is None:
            raise Conflict("all quality checkpoints are already decided")
        pending["status"] = "failed"

    def _settle(self, order: dict, stamp: str) -> dict:
        refunds = []
        net_total = int(order["amounts"]["total_cents"])
        if order["refund"]["status"] == "refunded" and order["refund"]["amount_cents"]:
            refunds.append(
                settlement_mod.refund_entry(
                    int(order["refund"]["amount_cents"]),
                    "partial" if int(order["refund"]["amount_cents"]) < net_total else "full",
                    "pre-settlement",
                    stamp,
                )
            )
            net_total -= int(order["refund"]["amount_cents"])
        settlement = settlement_mod.build(
            self.store,
            order,
            self.settings.split_policy(),
            settlement_id=self.next_settlement_id(),
            created_at=stamp,
            net_total_cents=net_total,
            refunds=refunds,
            royalty_assets=self._royalty_assets(order),
        )
        settlement_mod.post(settlement)
        self.settlements[settlement["settlement_id"]] = settlement
        return settlement

    def _royalty_assets(self, order: dict) -> list[dict]:
        """Resolve the licensed assets used by an order into royalty weights."""
        if self.library is None:
            return []
        rows = []
        seen: set[str] = set()
        for asset_id in order["items"][0].get("asset_license_ids") or []:
            if asset_id in seen:
                continue
            seen.add(asset_id)
            try:
                asset = self.library.get(asset_id)
            except NotFound:
                continue
            terms = self.library.licence_terms(asset, usage="commercial_product")
            if not terms["ok"]:
                raise Conflict(
                    f"asset {asset_id} can no longer be used: " + "; ".join(terms["reasons"])
                )
            rows.append(
                {
                    "asset_id": asset_id,
                    "licensor": terms["licensor"],
                    "rate_bp": int(terms["royalty_rate_bp"]),
                }
            )
        return rows

    def _issue_edition(self, order: dict, stamp: str) -> dict | None:
        item = order["items"][0]
        edition_id = item.get("edition_id")
        number = item.get("edition_number")
        if not edition_id or not number:
            return None
        buyer_id = str(order["buyer"]["id"])
        owner_id = "OWNER-" + "".join(ch for ch in buyer_id.upper() if ch.isalnum() or ch == "-")
        result = self.editions.issue(
            str(edition_id),
            number=int(number),
            order_id=str(order["order_id"]),
            owner={"owner_id": owner_id[:30], "display_name": f"Collector {buyer_id}"},
            at=stamp,
        )
        record = result["record"]
        return {
            "edition_id": record["edition_id"],
            "edition_number": record["edition_number"],
            "collector_record_id": record["record_id"],
            "certificate_id": record["certificate_id"],
            "certificate_hash": record["certificate_hash"],
        }

    # -- quality ---------------------------------------------------------
    def record_qc(
        self,
        order_id: str,
        checkpoint_id: str,
        *,
        verdict: str,
        defects: list[dict],
        inspector: str,
        at: str | None = None,
    ) -> dict:
        order = self.get(order_id)
        work_order_id = order["items"][0].get("work_order_id")
        if not work_order_id:
            raise Conflict("this order has no work order to inspect")
        work_order = self.work_orders[work_order_id]
        concept = self.concepts.get(str(work_order["concept_id"]))
        if concept is None:
            raise NotFound(f"concept {work_order['concept_id']} is not registered")
        stamp = self._stamp(at)
        record = self.quality.record(
            work_order,
            concept,
            checkpoint_id,
            verdict=verdict,
            defects=defects,
            inspector=inspector,
            at=stamp,
        )
        for checkpoint in work_order["qc_checkpoints"]:
            if checkpoint["checkpoint_id"] == checkpoint_id:
                checkpoint["status"] = "passed" if verdict == "pass" else "failed"
        return record

    # -- capacity --------------------------------------------------------
    def quote_for(
        self, concept: dict, *, at: str | None = None, quantity: int = 1, extra_lead_days: int = 0
    ) -> dict:
        return self.planner.quote(
            concept,
            at=at or self.clock.now,
            quantity=quantity,
            extra_lead_days=extra_lead_days,
            work_orders=list(self.work_orders.values()),
        )

    def schedules(self, *, at: str | None = None) -> list[dict]:
        stamp = at or self.clock.now
        rows = []
        for workshop_id in sorted(self.settings.workshop_ids()):
            self._schedule_n += 1
            rows.append(
                self.planner.schedule(
                    workshop_id,
                    list(self.work_orders.values()),
                    at=stamp,
                    schedule_id=f"SCH-{self._schedule_n:04d}",
                )
            )
        return rows

    # -- refunds ---------------------------------------------------------
    def refund_amount(self, order: dict) -> int:
        policy = self.settings.pricing()["refund_policy"]
        total = int(order["amounts"]["total_cents"])
        if order["status"] in policy["full_refund_states"]:
            return total
        if order["status"] in policy["partial_refund_states"]:
            return money.apply_rate(total, int(policy["partial_refund_bp"]))
        raise Conflict(f"a refund is not available in state {order['status']!r}")

    def request_refund(
        self, order_id: str, reason: str, *, actor: dict | None = None, at: str | None = None
    ) -> dict:
        order = self.get(order_id)
        actor = dict(actor or {"kind": "buyer", "id": order["buyer"]["id"]})
        stamp = self._stamp(at)
        target = self.refund_machine.target(order["refund"]["status"], "refund_requested", actor["kind"])
        amount = self.refund_amount(order)
        previous_status = order["status"]
        order["refund"] = {
            "status": target,
            "amount_cents": amount,
            "reason": reason,
            "requested_at": stamp,
            "decided_at": None,
        }
        self._validate(order)
        record = self._log(
            order, "refund_requested", previous_status, previous_status, actor,
            {"amount_cents": amount, "reason": reason}, stamp,
        )
        return {"order": order, "event": record}

    def decide_refund(
        self, order_id: str, approve: bool, *, actor: dict | None = None, at: str | None = None
    ) -> dict:
        order = self.get(order_id)
        actor = dict(actor or {"kind": "platform", "id": "ops-01"})
        stamp = self._stamp(at)
        event = "refund_approved" if approve else "refund_rejected"
        target = self.refund_machine.target(order["refund"]["status"], event, actor["kind"])
        previous_status = order["status"]
        order["refund"]["status"] = target
        order["refund"]["decided_at"] = stamp
        self._validate(order)
        record = self._log(
            order, event, previous_status, previous_status, actor,
            {"amount_cents": order["refund"]["amount_cents"]}, stamp,
        )
        return {"order": order, "event": record}

    def execute_refund(
        self, order_id: str, *, actor: dict | None = None, at: str | None = None
    ) -> dict:
        order = self.get(order_id)
        actor = dict(actor or {"kind": "system", "id": "system"})
        stamp = self._stamp(at)
        target = self.main.target(order["status"], "refunded", actor["kind"])
        self.refund_machine.target(order["refund"]["status"], "refunded", actor["kind"])
        previous_status = order["status"]
        amount = int(order["refund"]["amount_cents"])
        order["status"] = target
        order["refund"]["status"] = "refunded"
        order["refund"]["decided_at"] = stamp
        self._validate(order)
        record = self._log(
            order, "refunded", previous_status, target, actor,
            {"amount_cents": amount, "reason": order["refund"]["reason"]}, stamp,
        )
        return {"order": order, "event": record, "amount_cents": amount}

    # -- disputes --------------------------------------------------------
    def _quality_evidence(self, order: dict, qc_record_ids: list[str]) -> list[str]:
        """A dispute may only cite inspections recorded against its own work order."""
        work_order_id = order["items"][0].get("work_order_id")
        cited: list[str] = []
        seen: set[str] = set()
        for raw in qc_record_ids:
            qc_id = str(raw)
            if qc_id in seen:
                raise ValidationFailed(f"quality record {qc_id} is cited twice")
            seen.add(qc_id)
            record = next((row for row in self.quality.records if row["qc_id"] == qc_id), None)
            if record is None:
                raise NotFound(f"quality record {qc_id} not found")
            if not work_order_id or record["work_order_id"] != work_order_id:
                raise ValidationFailed(f"quality record {qc_id} belongs to another order")
            cited.append(qc_id)
        return cited

    def open_dispute(
        self,
        order_id: str,
        reason: str,
        *,
        qc_record_ids: list[str] | None = None,
        actor: dict | None = None,
        at: str | None = None,
    ) -> dict:
        order = self.get(order_id)
        actor = dict(actor or {"kind": "buyer", "id": order["buyer"]["id"]})
        stamp = self._stamp(at)
        cited = self._quality_evidence(order, list(qc_record_ids or []))
        target = self.main.target(order["status"], "dispute_opened", actor["kind"])
        sub_target = self.dispute_machine.target(order["dispute"]["status"], "dispute_opened", actor["kind"])
        previous_status = order["status"]
        order["status"] = target
        order["dispute"] = {
            "status": sub_target,
            "reason": reason,
            "resolution_note": None,
            "opened_at": stamp,
            "resolved_at": None,
            "qc_record_ids": cited,
        }
        self._validate(order)
        record = self._log(
            order,
            "dispute_opened",
            previous_status,
            target,
            actor,
            {"reason": reason, "qc_record_ids": cited},
            stamp,
        )
        return {"order": order, "event": record}

    def resolve_dispute(
        self,
        order_id: str,
        resolution: str,
        note: str,
        *,
        actor: dict | None = None,
        at: str | None = None,
    ) -> dict:
        if resolution not in ("rework", "refund", "split"):
            raise ValidationFailed("resolution must be rework, refund or split")
        order = self.get(order_id)
        actor = dict(actor or {"kind": "platform", "id": "ops-01"})
        stamp = self._stamp(at)
        event = f"dispute_resolved_{resolution}"
        target = self.main.target(order["status"], event, actor["kind"])
        sub_target = self.dispute_machine.target(order["dispute"]["status"], event, actor["kind"])
        previous_status = order["status"]
        payload: dict = {"resolution": resolution, "note": note}

        if resolution == "refund":
            amount = int(order["amounts"]["total_cents"])
            order["refund"] = {
                "status": "refunded",
                "amount_cents": amount,
                "reason": note,
                "requested_at": order["dispute"].get("opened_at"),
                "decided_at": stamp,
            }
            payload["refund_cents"] = amount
        elif resolution == "split":
            amount = money.apply_rate(int(order["amounts"]["total_cents"]), 5000)
            order["refund"] = {
                "status": "refunded",
                "amount_cents": amount,
                "reason": note,
                "requested_at": order["dispute"].get("opened_at"),
                "decided_at": stamp,
            }
            payload["refund_cents"] = amount

        order["status"] = target
        order["dispute"]["status"] = sub_target
        order["dispute"]["resolution_note"] = note
        order["dispute"]["resolved_at"] = stamp

        settlement = None
        if target == "settled":
            settlement = self._settle(order, stamp)
            payload["settlement_id"] = settlement["settlement_id"]
            payload["settled_cents"] = settlement["total_cents"]
            payload["payouts"] = [line["amount_cents"] for line in settlement["payout_lines"]]
            if settlement.get("royalty_lines"):
                payload["royalty_lines"] = settlement["royalty_lines"]
                payload["ip_share_cents"] = sum(
                    line["amount_cents"]
                    for line in settlement["payout_lines"]
                    if line["party"] == "ip_licensor"
                )
            edition = self._issue_edition(order, stamp)
            if edition:
                payload["edition"] = edition

        self._validate(order)
        record = self._log(order, event, previous_status, target, actor, payload, stamp)
        return {"order": order, "event": record, "settlement": settlement}

    # -- read helpers ----------------------------------------------------
    def board(self) -> list[dict]:
        rows = []
        for order in self.orders.values():
            item = order["items"][0]
            work_order = self.work_orders.get(item.get("work_order_id") or "")
            rows.append(
                {
                    "order_id": order["order_id"],
                    "status": order["status"],
                    "concept_id": item["concept_id"],
                    "title": item["title"],
                    "workshop_id": (work_order or {}).get("workshop_id"),
                    "total_cents": order["amounts"]["total_cents"],
                    "deposit_cents": order["amounts"]["deposit_cents"],
                    "promised_delivery_at": (work_order or {}).get("promised_delivery_at")
                    or (order.get("promise") or {}).get("promised_delivery_at"),
                    "promise_alternatives": len((order.get("promise") or {}).get("alternatives") or []),
                    "refund_status": order["refund"]["status"],
                    "dispute_status": order["dispute"]["status"],
                    "edition_id": item.get("edition_id"),
                    "customization_id": item.get("customization_id"),
                }
            )
        rows.sort(key=lambda row: row["order_id"])
        return rows

    def settlement_for(self, order_id: str) -> dict | None:
        for settlement in self.settlements.values():
            if settlement["order_id"] == order_id:
                return settlement
        return None
