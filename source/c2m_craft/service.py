"""Service container shared by the CLI, the HTTP server and the demo.

Holds the loaded contracts, configuration, rules, library, creative vocabulary
and the order book; wires the logical clock to the ledger; and resolves ids so
that every generated record is unique within a session.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path

from .commerce.orders import Commerce
from .commerce import customization as customization_mod
from .core import canonical
from .core.clock import LogicalClock
from .core.contracts import SchemaStore
from .core.errors import Conflict, NotFound, ValidationFailed
from .core.ledger import Ledger
from .core.settings import ROOT, Settings
from .craft.assessment import assess as assess_concept
from .craft.review import ReviewQueue
from .craft.rules import load_ruleset
from .creative.adapters import OfflineLexiconAdapter
from .creative.series import expand
from .creative.workstation import ConceptRequest
from .enterprise.growth import GrowthStack
from .enterprise.registry import ComponentRegistry
from .enterprise.runtime import EnterpriseRuntime, Profiles
from .ip import IpPipeline
from .library.assets import Library


class Service:
    def __init__(
        self,
        root: Path | str | None = None,
        workdir: Path | str | None = None,
        *,
        reset: bool = False,
    ) -> None:
        self.root = Path(root) if root else ROOT
        self.settings = Settings(self.root)
        self.store = SchemaStore(self.root)
        self.clock = LogicalClock(self.settings.as_of)
        self.workdir = Path(workdir) if workdir else self.root / "var" / "runtime"
        if reset and self.workdir.exists():
            shutil.rmtree(self.workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)

        self.rulesets = {
            industry: load_ruleset(self.settings.rules_path(industry))
            for industry in self.settings.industry_ids()
        }
        self.ledger = Ledger(self.workdir / "ledger.jsonl", self.clock)
        self.library = Library.from_file(
            self.store, self.settings, self.root / "samples" / "library" / "assets.json"
        )
        self.concepts: dict[str, dict] = {}
        self._load_concepts()
        self.commerce = Commerce(
            self.store,
            self.settings,
            self.clock,
            self.ledger,
            concepts=self.concepts,
            rulesets=self.rulesets,
        )
        self.reviews: ReviewQueue = self.commerce.reviews
        self.commerce.attach_library(self.library)
        self.catalog = self.commerce.catalog
        self.planner = self.commerce.planner
        self.editions = self.commerce.editions
        self.quality = self.commerce.quality
        self._concept_n = max((int(key.split("-")[1]) for key in self.concepts), default=0)
        self._asset_n = max(
            (int(asset["asset_id"].split("-")[-1]) for asset in self.library.assets), default=0
        )
        self.state_path = self.workdir / "state.json"
        self._state_lock = threading.Lock()
        self._enterprise: EnterpriseRuntime | None = None
        self._growth: GrowthStack | None = None
        self._ip: IpPipeline | None = None
        self._growth_site: dict | None = None
        if self.state_path.exists():
            self.load_state()

    # -- lazily built subsystems -----------------------------------------
    @property
    def enterprise(self) -> EnterpriseRuntime:
        if self._enterprise is None:
            registry = ComponentRegistry(self.store, self.settings)
            profiles = Profiles(self.store, self.settings)
            self._enterprise = EnterpriseRuntime(self.store, self.settings, registry, profiles)
        return self._enterprise

    @property
    def growth(self) -> GrowthStack:
        if self._growth is None:
            self._growth = GrowthStack(self.store, self.settings)
        return self._growth

    @property
    def ip(self) -> IpPipeline:
        if self._ip is None:
            self._ip = IpPipeline(self.store, self.settings)
        return self._ip

    # -- fixtures --------------------------------------------------------
    def _load_concepts(self) -> None:
        for path in sorted((self.root / "samples" / "concepts").glob("DC-*.json")):
            with open(path, "r", encoding="utf-8") as handle:
                concept = json.load(handle)
            self.concepts[str(concept["concept_id"])] = concept

    def concept(self, concept_id: str) -> dict:
        try:
            return self.concepts[concept_id]
        except KeyError as exc:
            raise NotFound(f"concept {concept_id} not found") from exc

    def expected_table(self) -> dict:
        return SchemaStore.json_load(self.root / "samples" / "concepts" / "expected.json")

    # -- creative --------------------------------------------------------
    def generate(
        self,
        text: str,
        industry: str,
        *,
        count: int = 4,
        style_id: str | None = None,
        reference_palette: list[str] | None = None,
    ) -> list[dict]:
        request = ConceptRequest(
            text=text,
            industry=industry,
            count=count,
            style_id=style_id,
            reference_palette=reference_palette,
        )
        adapter = OfflineLexiconAdapter(
            self.settings.lexicon(),
            self.settings.palettes()["palettes"],
            self.settings.styles()["styles"],
        )
        concepts = adapter.generate(
            request,
            {
                "created_at": self.clock.now,
                "next_id": self._concept_n + 1,
            },
        )
        for concept in concepts:
            self.store.assert_valid("design_concept", concept)
            self._concept_n += 1
            self.concepts[str(concept["concept_id"])] = concept
            self.commerce.concepts[str(concept["concept_id"])] = concept
        return concepts

    def expand_series(self, concept_id: str) -> list[dict]:
        concept = self.concept(concept_id)
        config = self.settings.series_config()
        skus = expand(concept, config, next_id=self._concept_n + 1)
        for sku in skus:
            sku.pop("_price_multiplier_bp", None)
            self.store.assert_valid("design_concept", sku)
            self._concept_n += 1
            self.concepts[str(sku["concept_id"])] = sku
            self.commerce.concepts[str(sku["concept_id"])] = sku
        return skus

    # -- assessment ------------------------------------------------------
    def workshops_for(self, industry: str) -> list[dict]:
        return [self.settings.workshop(workshop_id) for workshop_id in self.settings.workshop_ids(industry)]

    def default_workshop(self, industry: str) -> dict:
        return self.settings.workshop(str(self.settings.industry(industry)["default_workshop"]))

    def assess_at(
        self,
        concept: dict,
        workshop_id: str,
        *,
        queue_review: bool = True,
        at: str | None = None,
    ) -> dict:
        industry = str(concept["industry"])
        if industry not in self.rulesets:
            raise ValidationFailed(f"no rule set for industry {industry}")
        workshop = self.settings.workshop(workshop_id)
        if workshop.get("industry") != industry:
            raise ValidationFailed(
                f"workshop {workshop_id} does not serve industry {industry}"
            )
        assessment = assess_concept(
            concept,
            workshop,
            self.rulesets[industry],
            assessment_id=self.commerce.next_assessment_id(),
            created_at=at or self.clock.now,
            queue_id=None,
        )
        self.store.assert_valid(
            "manufacturability_assessment", assessment, ctx={"as_of": self.settings.as_of}
        )
        self.commerce.assessments[assessment["assessment_id"]] = assessment
        if queue_review and assessment["artisan"]["required"]:
            item = self.reviews.create(
                assessment,
                self.rulesets[industry],
                requested_at=at or self.clock.now,
                artisan=(
                    {"artisan_id": "ART-HW-01", "name": "Woodworking craft reviewer (synthetic)"}
                    if industry == "hardwood"
                    else {"artisan_id": "ART-JW-01", "name": "Jewelry craft reviewer (synthetic)"}
                ),
            )
            assessment["artisan"]["queue_id"] = item["queue_id"]
            assessment["artisan"]["status"] = "pending"
        return assessment

    def decide_review(self, queue_id: str, verdict: str, reason: str, *, at: str | None = None) -> dict:
        item = self.reviews.decide(queue_id, verdict, reason, decided_at=at or self.clock.now)
        assessment = self.commerce.assessments.get(item["assessment_id"])
        if assessment is not None:
            updated = self.reviews.apply(assessment, queue_id)
            self.commerce.assessments[item["assessment_id"]] = updated
            self.store.assert_valid(
                "manufacturability_assessment", updated, ctx={"as_of": self.settings.as_of}
            )
            return {"review": item, "assessment": updated}
        return {"review": item, "assessment": None}

    # -- library ---------------------------------------------------------
    def ingest_asset(self, payload: dict) -> dict:
        asset = self.library.ingest(payload)
        self._asset_n += 1
        return asset

    def search_library(self, **kwargs) -> list[dict]:
        return self.library.search(**kwargs)

    # -- commerce --------------------------------------------------------
    def create_order(self, concept_id: str, **kwargs) -> dict:
        selections = kwargs.pop("selections", None)
        edition_id = kwargs.pop("edition_id", None)
        concept = self.concept(concept_id)
        choice = None
        if selections:
            built = self.build_customization(concept_id, selections)
            if built["error"]:
                raise Conflict(built["error"])
            concept = built["derived_concept"]
            choice = built["choice"]
        order = self.commerce.create_order(
            concept,
            customization=choice,
            edition_id=edition_id,
            **kwargs,
        )
        if choice is not None:
            choice["status"] = "applied"
            choice["result_concept_id"] = concept["concept_id"]
            choice["confirmed_at"] = order["created_at"]
            self.store.assert_valid("customization_choice", choice)
            self.commerce.customizations[choice["customization_id"]] = choice
        return order

    def build_customization(
        self, concept_id: str, selections: list[dict], *, at: str | None = None, register: bool = True
    ) -> dict:
        """Resolve options, derive a concept and check that it can still be made."""
        concept = self.concept(concept_id)
        stamp = at or self.clock.now
        choice = customization_mod.resolve(
            self.settings,
            self.commerce.catalog,
            concept,
            selections,
            customization_id=self.commerce.next_customization_id(),
            created_at=stamp,
        )
        derived = customization_mod.apply_to_concept(
            concept,
            choice,
            concept_id=f"DC-{self._concept_n + 1:04d}",
            created_at=stamp,
        )
        self.store.assert_valid("design_concept", derived)
        quote = None
        error = None
        try:
            quote = self.commerce.planner.quote(
                derived,
                at=stamp,
                extra_lead_days=customization_mod.lead_time_delta(choice),
                work_orders=list(self.commerce.work_orders.values()),
            )
        except Conflict as exc:
            error = exc.message
        if quote:
            choice["status"] = "feasible"
            choice["feasibility"] = {"ok": True, "assessment_id": None, "blockers": []}
        else:
            choice["status"] = "infeasible"
            choice["feasibility"] = {"ok": False, "assessment_id": None, "blockers": [error or "infeasible"]}
        self.store.assert_valid("customization_choice", choice)
        if register and quote:
            self._concept_n += 1
            self.concepts[derived["concept_id"]] = derived
            self.commerce.concepts[derived["concept_id"]] = derived
            self.commerce.customizations[choice["customization_id"]] = choice
        return {
            "choice": choice,
            "derived_concept": derived if quote else None,
            "quote": quote,
            "error": error,
        }

    def quote(self, concept_id: str, **kwargs) -> dict:
        return self.commerce.quote_for(self.concept(concept_id), **kwargs)

    def schedules(self, at: str | None = None) -> list[dict]:
        return self.commerce.schedules(at=at)

    def record_qc(self, order_id: str, checkpoint_id: str, **kwargs) -> dict:
        record = self.commerce.record_qc(order_id, checkpoint_id, **kwargs)
        self.persist()
        return record

    def order(self, order_id: str) -> dict:
        return self.commerce.get(order_id)

    def order_events(self, order_id: str) -> list[dict]:
        return self.commerce.events(order_id)

    # -- enterprise service layer ---------------------------------------
    def enterprise_report(self) -> dict:
        return self.enterprise.report()

    def enterprise_switch(self) -> dict:
        return self.enterprise.switch_matrix()

    # -- growth stack ----------------------------------------------------
    def growth_site(self, *, fresh: bool = False, at: str | None = None) -> dict:
        if fresh or self._growth_site is None:
            stamp = at or self.clock.now
            record = self.growth.build("SITE-JW-01", at=stamp)
            record = self.growth.audit(record, at=stamp)
            self._growth_site = record
        return self._growth_site

    def growth_inquiry(self, payload: dict) -> dict:
        self.clock.advance(3)
        record = self.growth.intake(
            {**payload, "site_id": payload.get("site_id") or "SITE-JW-01"}, at=self.clock.now
        )
        return record

    def growth_advance(self, inquiry_id: str, stage: str, note: str) -> dict:
        self.clock.advance(5)
        return self.growth.advance(inquiry_id, stage, at=self.clock.now, note=note)

    def growth_crm(self) -> dict:
        return self.growth.crm.board(now=self.clock.now)

    # -- cultural IP pipeline -------------------------------------------
    def ip_report(self) -> dict:
        return self.ip.report()

    # -- persistence -----------------------------------------------------
    def _state(self) -> dict:
        state = {
            "version": "1.0.0",
            "clock_minutes": self.clock.offset_minutes,
            "counters": {
                "concept": self._concept_n,
                "asset": self._asset_n,
                "order": self.commerce._order_n,
                "work_order": self.commerce._wo_n,
                "settlement": self.commerce._st_n,
                "assessment": self.commerce._ma_n,
                "review": self.reviews._next,
                "customization": self.commerce._customization_n,
                "slot": self.commerce._slot_n,
                "schedule": self.commerce._schedule_n,
                "edition": self.commerce.editions._edition_n,
                "collector": self.commerce.editions._collector_n,
                "quality": self.commerce.quality._next,
            },
            "concepts": [self.concepts[key] for key in sorted(self.concepts)],
            "assets": list(self.library.assets),
            "orders": [self.commerce.orders[key] for key in sorted(self.commerce.orders)],
            "work_orders": [self.commerce.work_orders[key] for key in sorted(self.commerce.work_orders)],
            "settlements": [self.commerce.settlements[key] for key in sorted(self.commerce.settlements)],
            "assessments": [self.commerce.assessments[key] for key in sorted(self.commerce.assessments)],
            "reviews": list(self.reviews.items),
            "customizations": [
                self.commerce.customizations[key] for key in sorted(self.commerce.customizations)
            ],
            "quality_records": list(self.commerce.quality.records),
            "editions": [
                self.commerce.editions.editions[key] for key in sorted(self.commerce.editions.editions)
            ],
            "collector_records": [
                self.commerce.editions.records[key] for key in sorted(self.commerce.editions.records)
            ],
        }
        if self._growth is not None:
            crm = self._growth.crm
            state["crm"] = {
                "inquiry_n": crm._inquiry_n,
                "follow_n": crm._follow_n,
                "quote_n": crm._quote_n,
                "inquiries": [
                    crm.inquiries[key] for key in sorted(crm.inquiries)
                ],
            }
        return state

    def persist(self) -> None:
        """Write the state atomically: a killed or concurrent writer cannot corrupt it."""
        temp = Path(f"{self.state_path}.{os.getpid()}.{threading.get_ident()}.tmp")
        with self._state_lock:
            canonical.dump_json(temp, self._state())
            os.replace(temp, self.state_path)

    def load_state(self) -> None:
        try:
            data = canonical.read_json(self.state_path)
        except (OSError, ValueError) as exc:
            print(f"[state] unreadable state file ignored: {exc}", file=sys.stderr)
            return
        self.clock.restore(float(data.get("clock_minutes", 0)))
        counters = data.get("counters", {})
        self._concept_n = int(counters.get("concept", self._concept_n))
        self._asset_n = int(counters.get("asset", self._asset_n))
        self.commerce._order_n = int(counters.get("order", self.commerce._order_n))
        self.commerce._wo_n = int(counters.get("work_order", self.commerce._wo_n))
        self.commerce._st_n = int(counters.get("settlement", self.commerce._st_n))
        self.commerce._ma_n = int(counters.get("assessment", self.commerce._ma_n))
        self.reviews._next = int(counters.get("review", self.reviews._next))
        self.commerce._customization_n = int(counters.get("customization", 0))
        self.commerce._slot_n = int(counters.get("slot", 0))
        self.commerce._schedule_n = int(counters.get("schedule", 0))
        self.commerce.editions._edition_n = int(counters.get("edition", 1))
        self.commerce.editions._collector_n = int(counters.get("collector", 1))
        self.commerce.quality._next = int(counters.get("quality", 1))

        for concept in data.get("concepts", []):
            self.concepts[str(concept["concept_id"])] = concept
            self.commerce.concepts[str(concept["concept_id"])] = concept
        if data.get("assets"):
            self.library.assets = list(data["assets"])
            self.library.by_id = {str(asset["asset_id"]): asset for asset in self.library.assets}
        for order in data.get("orders", []):
            self.commerce.orders[str(order["order_id"])] = order
        for work_order in data.get("work_orders", []):
            self.commerce.work_orders[str(work_order["work_order_id"])] = work_order
        for settlement in data.get("settlements", []):
            self.commerce.settlements[str(settlement["settlement_id"])] = settlement
        for assessment in data.get("assessments", []):
            self.commerce.assessments[str(assessment["assessment_id"])] = assessment
        self.reviews.items = list(data.get("reviews", []))
        for choice in data.get("customizations", []):
            self.commerce.customizations[str(choice["customization_id"])] = choice
        self.commerce.quality.records = list(data.get("quality_records", []))
        for edition in data.get("editions", []):
            self.commerce.editions.editions[str(edition["edition_id"])] = edition
        for record in data.get("collector_records", []):
            self.commerce.editions.records[str(record["record_id"])] = record
        crm_state = data.get("crm") or {}
        if crm_state:
            crm = self.growth.crm
            crm._inquiry_n = int(crm_state.get("inquiry_n", 0))
            crm._follow_n = int(crm_state.get("follow_n", 0))
            crm._quote_n = int(crm_state.get("quote_n", 0))
            for inquiry in crm_state.get("inquiries", []):
                crm.inquiries[str(inquiry["inquiry_id"])] = inquiry

    # -- introspection ---------------------------------------------------
    def spec(self) -> dict:
        return {
            "version": self.settings.site["version"],
            "as_of": self.settings.as_of,
            "currency": self.settings.currency,
            "languages": self.settings.site["languages"],
            "data_provenance": self.settings.site["data_provenance"],
            "client_materials_received": self.settings.site["client_materials_received"],
            "contracts": [
                {
                    "id": entry["id"],
                    "urn": entry["urn"],
                    "file": entry["file"],
                    "version": entry["version"],
                    "invariants": entry.get("invariants", []),
                    "requirements": entry.get("requirements", []),
                }
                for entry in self.store.registry["contracts"]
            ],
            "industries": [
                {
                    "industry": industry,
                    "title": self.settings.industry(industry)["title"],
                    "workshops": [
                        {
                            "workshop_id": workshop["workshop_id"],
                            "name": workshop["name"],
                            "lead_time_days": workshop["lead_time_days"],
                            "capability_checks": len(workshop["capability_checks"]),
                        }
                        for workshop in self.workshops_for(industry)
                    ],
                    "rules": len(self.rulesets[industry].rules),
                    "facts": len(self.rulesets[industry].facts_schema),
                    "rule_version": self.rulesets[industry].version,
                }
                for industry in sorted(self.rulesets)
            ],
            "counts": {
                "concepts": len(self.concepts),
                "library_assets": len(self.library.assets),
                "orders": len(self.commerce.orders),
                "assessments": len(self.commerce.assessments),
                "reviews": len(self.reviews.items),
            },
            "enterprise": {
                "components": len(self.enterprise.registry.components),
                "profiles": len(self.enterprise.profiles.ids()),
                "industries": len(self.enterprise.industries),
            },
            "growth": {
                "sites": len(self.growth.sites),
                "languages": self.growth.spec("SITE-JW-01")["languages"],
                "crm_stages": list(self.growth.crm.policy["pipeline"]["stages"]),
            },
            "ip": {
                "characters": len(self.ip.bible["canon"]["characters"]),
                "assets": len(self.ip.assets),
                "reel_seconds": self.ip.drama["cut"]["total_seconds"],
                "merch_specs": len(self.ip.merch_specs),
            },
            "limits": self.settings.site["limits"],
            "offline": True,
            "generator": {
                "adapter": "offline_lexicon",
                "version": "1.0.0",
                "deterministic": True,
                "note": "The creative workstation is an offline vocabulary adapter; the optional model sidecar renders real images and copy without entering the package.",
            },
        }
