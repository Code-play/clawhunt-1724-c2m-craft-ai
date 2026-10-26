"""Quality records: sampling plan, measurements, defects and verdict.

The QC record is the object a dispute cites. Limits are derived from the concept
facts with a configured tolerance, the defect taxonomy fixes each code's severity,
and the verdict is checked against the defects by a contract invariant so a pass
with a critical defect cannot be stored.
"""

from __future__ import annotations

from ..core.errors import ValidationFailed


class QualityBook:
    def __init__(self, store, settings) -> None:
        self.store = store
        self.settings = settings
        self.config = settings.json("config/commerce/quality.json")
        self.records: list[dict] = []
        self._next = 1

    def allocate_id(self) -> str:
        qc_id = f"QCR-{self._next:04d}"
        self._next += 1
        return qc_id

    def code(self, code: str) -> dict:
        for item in self.config["defect_codes"]:
            if item["code"] == code:
                return item
        raise ValidationFailed(f"unknown defect code {code!r}")

    def plan_for(self, checkpoint_id: str) -> dict:
        key = self.config.get("checkpoint_plans", {}).get(checkpoint_id, "default")
        plans = self.config["sampling_plans"]
        plan = dict(plans.get(key) or plans["default"])
        return plan

    def measurements(self, concept: dict, checkpoint_id: str) -> list[dict]:
        facts = dict(concept.get("craft_facts") or {})
        industry = str(concept.get("industry"))
        names = (
            ("min_wall_thickness_mm", "wall_mm")
            if industry == "jewelry"
            else ("panel_thickness_mm", "panel_mm")
        )
        selected = [names]
        if industry == "hardwood":
            selected.append(("wood_moisture_pct", "moisture_pct"))
        else:
            selected.append(("max_dimension_mm", "dimension_mm"))
        tolerance = int(self.config.get("measurement_tolerance_bp", 1000)) / 10000
        rows = []
        for fact, name in selected:
            if fact not in facts:
                continue
            value = float(facts[fact])
            low = round(value * (1 - tolerance), 3)
            high = round(value * (1 + tolerance), 3)
            rows.append(
                {
                    "name": name,
                    "value": round(value, 3),
                    "limit_min": low,
                    "limit_max": high,
                    "ok": low <= value <= high,
                }
            )
        return rows

    def record(
        self,
        work_order: dict,
        concept: dict,
        checkpoint_id: str,
        *,
        verdict: str,
        defects: list[dict],
        inspector: str,
        at: str,
    ) -> dict:
        resolved = []
        for defect in defects:
            code = self.code(str(defect.get("code") or ""))
            resolved.append(
                {
                    "code": code["code"],
                    "severity": code["severity"],
                    "count": int(defect.get("count", 0)),
                    "note": str(defect.get("note") or code["label"]["en"]),
                }
            )
        record = {
            "qc_id": self.allocate_id(),
            "work_order_id": str(work_order["work_order_id"]),
            "checkpoint_id": str(checkpoint_id),
            "sample_size": int(work_order.get("_sample_size", 5)),
            "defects": resolved,
            "measurements": self.measurements(concept, checkpoint_id),
            "verdict": verdict,
            "inspector": inspector,
            "sampling_plan": self.plan_for(checkpoint_id),
            "at": at,
        }
        self.store.assert_valid("qc_record", record)
        self.records.append(record)
        return record

    def for_work_order(self, work_order_id: str) -> list[dict]:
        return [row for row in self.records if row["work_order_id"] == work_order_id]

    def summary(self) -> dict:
        passed = sum(1 for row in self.records if row["verdict"] == "pass")
        return {
            "records": len(self.records),
            "passed": passed,
            "failed": sum(1 for row in self.records if row["verdict"] == "fail"),
            "rework": sum(1 for row in self.records if row["verdict"] == "rework"),
        }
