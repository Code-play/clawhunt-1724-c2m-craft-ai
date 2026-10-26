"""Deterministic capacity planning and delivery promises.

The same planner answers three questions: what does this order need, when can a
workshop finish it, and which workshop should get it. Existing work orders book
their minutes backwards from their promised date, a new order fills the remaining
capacity forwards, and the promise is the first working day with enough room.

Nothing here reads the wall clock: the starting point and the ready time come from
configuration and the logical clock.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from ..core.clock import fmt_ts, parse_ts
from ..core.errors import Conflict
from ..craft.assessment import assess

HOURS_PER_DAY = 1440


class CapacityPlanner:
    def __init__(self, settings, store, rulesets) -> None:
        self.settings = settings
        self.store = store
        self.rulesets = rulesets
        self.config = settings.json("config/commerce/capacity.json")
        self.horizon_days = int(self.config.get("horizon_days", 60))
        self.ready_time = str(self.config.get("ready_time", "18:00:00"))
        self.lead_time_days = int(self.config.get("request_lead_time_days", 10))

    # -- workshop profiles ----------------------------------------------
    def profile(self, workshop_id: str) -> dict:
        return dict(
            self.config["workshops"].get(
                workshop_id,
                {"capacity_per_day_minutes": 420, "working_days": [1, 2, 3, 4, 5], "setup_minutes": 30},
            )
        )

    def working_days(self, workshop_id: str) -> set[int]:
        return {int(day) for day in self.profile(workshop_id).get("working_days", [1, 2, 3, 4, 5])}

    def _is_working(self, day: date, workshop_id: str) -> bool:
        return day.isoweekday() in self.working_days(workshop_id)

    def _next_working(self, day: date, workshop_id: str) -> date:
        cursor = day
        for _ in range(14):
            if self._is_working(cursor, workshop_id):
                return cursor
            cursor += timedelta(days=1)
        return cursor

    # -- demand ----------------------------------------------------------
    def work_minutes(self, work_order: dict) -> int:
        minutes = sum(int(step.get("est_minutes", 0)) for step in work_order.get("process_steps", []))
        setup = int(self.profile(str(work_order.get("workshop_id"))).get("setup_minutes", 30))
        return max(minutes + setup, 1)

    def demand_minutes(self, concept: dict, quantity: int = 1) -> int:
        industry = self.settings.industry(str(concept["industry"]))
        facts = dict(concept.get("craft_facts") or {})
        total = 0
        for step in industry.get("process_route", []):
            driver = step.get("driver")
            value = float(facts.get(driver, 0) or 0) if driver else 0.0
            total += int(round(float(step["est_minutes"]) + float(step["driver_rate"]) * value))
        return max(total * max(int(quantity), 1), 1)

    # -- booking ---------------------------------------------------------
    def _booked(
        self,
        workshop_id: str,
        work_orders: Iterable[dict],
        start_day: date,
        days: int,
    ) -> dict[date, int]:
        capacity = int(self.profile(workshop_id)["capacity_per_day_minutes"])
        booked: dict[date, int] = {}
        ordered = sorted(
            (order for order in work_orders if order.get("workshop_id") == workshop_id),
            key=lambda order: (str(order.get("promised_delivery_at", "")), str(order.get("work_order_id", ""))),
        )
        for work_order in ordered:
            promise = str(work_order.get("promised_delivery_at") or "")
            if not promise:
                continue
            remaining = self.work_minutes(work_order)
            cursor = parse_ts(promise).date()
            guard = 0
            while remaining > 0 and guard < days + self.horizon_days:
                guard += 1
                if cursor < start_day:
                    break
                if self._is_working(cursor, workshop_id):
                    free = capacity - booked.get(cursor, 0)
                    if free > 0:
                        take = min(free, remaining)
                        booked[cursor] = booked.get(cursor, 0) + take
                        remaining -= take
                cursor -= timedelta(days=1)
        return booked

    def _finish_day(
        self,
        workshop_id: str,
        minutes: int,
        booked: dict[date, int],
        start_day: date,
    ) -> tuple[date, dict[date, int]]:
        capacity = int(self.profile(workshop_id)["capacity_per_day_minutes"])
        remaining = minutes
        cursor = self._next_working(start_day, workshop_id)
        guard = 0
        while remaining > 0 and guard < self.horizon_days * 2:
            guard += 1
            if self._is_working(cursor, workshop_id):
                free = capacity - booked.get(cursor, 0)
                if free > 0:
                    take = min(free, remaining)
                    booked[cursor] = booked.get(cursor, 0) + take
                    remaining -= take
            if remaining > 0:
                cursor += timedelta(days=1)
        return cursor, booked

    def _ready_at(self, day: date) -> str:
        hour, minute, second = (int(part) for part in self.ready_time.split(":"))
        moment = datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=timezone.utc)
        return fmt_ts(moment)

    # -- quoting ---------------------------------------------------------
    def quote(
        self,
        concept: dict,
        *,
        at: str,
        quantity: int = 1,
        extra_lead_days: int = 0,
        candidates: list[str] | None = None,
        work_orders: Iterable[dict] | None = None,
    ) -> dict:
        """Pick the fastest feasible workshop and return the promise."""
        industry = str(concept["industry"])
        ruleset = self.rulesets[industry]
        workshop_ids = candidates or self.settings.workshop_ids(industry)
        work_orders = list(work_orders or [])
        start_day = parse_ts(at).date()
        earliest = start_day + timedelta(days=self.lead_time_days + int(extra_lead_days))
        demand = self.demand_minutes(concept, quantity)

        quotes: list[dict] = []
        blocked: list[str] = []
        for workshop_id in workshop_ids:
            workshop = self.settings.workshop(workshop_id)
            if workshop.get("industry") != industry:
                continue
            verdict = assess(
                concept,
                workshop,
                ruleset,
                assessment_id="MA-CAP",
                created_at=at,
            )
            if verdict["final_verdict"] == "not_manufacturable":
                blocked.append(f"{workshop_id}: {', '.join(verdict['blockers'])}")
                continue
            booked = self._booked(workshop_id, work_orders, start_day, self.horizon_days)
            finish_day, booked = self._finish_day(workshop_id, demand, booked, start_day)
            promised_day = max(finish_day, self._next_working(earliest, workshop_id))
            quotes.append(
                {
                    "workshop_id": workshop_id,
                    "promised_delivery_at": self._ready_at(promised_day),
                    "working_minutes": demand,
                    "verdict": verdict["final_verdict"],
                    "finish_day": promised_day.isoformat(),
                    "capacity_per_day_minutes": int(self.profile(workshop_id)["capacity_per_day_minutes"]),
                }
            )

        if not quotes:
            raise Conflict(
                "no workshop can make this concept: " + ("; ".join(blocked) or "no candidate workshop")
            )

        quotes.sort(
            key=lambda row: (
                row["promised_delivery_at"],
                row["verdict"] != "manufacturable",
                row["workshop_id"],
            )
        )
        chosen = quotes[0]
        alternatives = [
            {
                "workshop_id": row["workshop_id"],
                "promised_delivery_at": row["promised_delivery_at"],
            }
            for row in quotes[1:]
        ]
        return {
            "workshop_id": chosen["workshop_id"],
            "promised_delivery_at": chosen["promised_delivery_at"],
            "working_minutes": chosen["working_minutes"],
            "verdict": chosen["verdict"],
            "alternatives": alternatives,
        }

    # -- schedules -------------------------------------------------------
    def schedule(
        self,
        workshop_id: str,
        work_orders: Iterable[dict],
        *,
        at: str,
        schedule_id: str,
        horizon_days: int | None = None,
    ) -> dict:
        profile = self.profile(workshop_id)
        capacity = int(profile["capacity_per_day_minutes"])
        start_day = parse_ts(at).date()
        days = int(horizon_days or self.horizon_days)
        booked = self._booked(workshop_id, work_orders, start_day, days)

        slots = []
        for index, work_order in enumerate(
            sorted(
                (order for order in work_orders if order.get("workshop_id") == workshop_id),
                key=lambda order: (
                    str(order.get("promised_delivery_at", "")),
                    str(order.get("work_order_id", "")),
                ),
            ),
            start=1,
        ):
            promised = str(work_order.get("promised_delivery_at") or "")
            minutes = self.work_minutes(work_order)
            end_day = parse_ts(promised).date() if promised else start_day
            begin_day = end_day
            remaining = minutes
            guard = 0
            while remaining > 0 and guard < self.horizon_days * 2:
                guard += 1
                begin_day = begin_day - timedelta(days=1)
                if begin_day < start_day:
                    begin_day = start_day
                    break
            process = str((work_order.get("process_steps") or [{}])[0].get("process", "production"))
            slots.append(
                {
                    "slot_id": f"SLOT-{index:04d}",
                    "order_id": str(work_order["order_id"]),
                    "work_order_id": str(work_order["work_order_id"]),
                    "start": self._ready_at(begin_day),
                    "end": self._ready_at(end_day),
                    "minutes": minutes,
                    "process": process,
                }
            )

        utilization = []
        for offset in range(min(days, 14)):
            day = start_day + timedelta(days=offset)
            if not self._is_working(day, workshop_id):
                continue
            utilization.append(
                {
                    "date": day.isoformat(),
                    "booked_minutes": int(booked.get(day, 0)),
                    "capacity_minutes": capacity,
                }
            )

        schedule = {
            "schedule_id": schedule_id,
            "workshop_id": workshop_id,
            "horizon": {
                "from": self._ready_at(start_day),
                "to": self._ready_at(start_day + timedelta(days=days)),
            },
            "capacity_per_day_minutes": capacity,
            "slots": slots,
            "utilization": utilization,
            "generated_at": at,
        }
        self.store.assert_valid("production_schedule", schedule)
        return schedule
