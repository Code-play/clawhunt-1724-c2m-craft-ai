"""Work-order synthesis: concept plus workshop plus rules becomes an instruction.

The bill of materials and the process route are computed from the industry
configuration with the concept facts as drivers, the equipment ids come from the
chosen workshop, the quality checkpoints come from the workshop as well, and the
craft constraints carry the rule ids that failed the assessment.
"""

from __future__ import annotations

from ..core.clock import add_days
from ..core.contracts import SchemaStore


def build(
    store: SchemaStore,
    order: dict,
    concept: dict,
    workshop: dict,
    industry_config: dict,
    assessment: dict,
    *,
    work_order_id: str,
    created_at: str,
) -> dict:
    facts = dict(concept.get("craft_facts") or {})
    industry = str(concept["industry"])

    bom = []
    for index, line in enumerate(industry_config.get("bom", []), start=1):
        driver = line.get("driver")
        driver_value = float(facts.get(driver, 0) or 0) if driver else 0.0
        quantity = round(float(line["base"]) + float(line["driver_rate"]) * driver_value, 3)
        bom.append(
            {
                "line_id": f"BOM-{index:03d}",
                "material": str(line["material"]),
                "spec": str(line["spec"]),
                "quantity": quantity,
                "unit": str(line["unit"]),
                "unit_cost_cents": int(line["unit_cost_cents"]),
            }
        )

    equipment_by_process = {
        str(item["process"]): str(item["equipment_id"]) for item in workshop.get("equipment", [])
    }
    constraints = []
    for rule_id in assessment.get("blockers", []):
        constraints.append(f"{rule_id}: blocked, resolved by the accepted fix before dispatch")
    for item in assessment.get("rule_evaluations", []):
        if item["status"] == "fail" and item["severity"] != "blocker":
            constraints.append(f"{item['rule_id']}: conditional, quoted as extra labour")
    if assessment.get("artisan", {}).get("required"):
        constraints.append(
            f"artisan review {assessment['artisan'].get('queue_id')} must confirm before shipment"
        )

    steps = []
    for index, step in enumerate(industry_config.get("process_route", []), start=1):
        driver = step.get("driver")
        driver_value = float(facts.get(driver, 0) or 0) if driver else 0.0
        minutes = int(round(float(step["est_minutes"]) + float(step["driver_rate"]) * driver_value))
        steps.append(
            {
                "step_id": f"OP-{index:02d}",
                "name": dict(step["name"]),
                "process": str(step["process"]),
                "equipment_id": equipment_by_process.get(str(step["process"]), "EQ-GENERIC-01"),
                "est_minutes": max(minutes, 1),
                "constraints": list(constraints),
            }
        )

    qc = [
        {
            "checkpoint_id": str(item["checkpoint_id"]),
            "name": dict(item["name"]),
            "method": str(item["method"]),
            "pass_criteria": str(item["pass_criteria"]),
            "status": "pending",
        }
        for item in workshop.get("qc_checkpoints", [])
    ]

    promised = add_days(created_at, float(workshop.get("lead_time_days", 21)))
    work_order = {
        "work_order_id": work_order_id,
        "order_id": order["order_id"],
        "concept_id": concept["concept_id"],
        "industry": industry,
        "workshop_id": workshop["workshop_id"],
        "bom": bom,
        "process_steps": steps,
        "qc_checkpoints": qc,
        "promised_delivery_at": promised,
        "status": "issued",
        "created_at": created_at,
    }
    store.assert_valid("craft_work_order", work_order)
    return work_order


def cost_estimate(work_order: dict) -> dict:
    material = sum(
        round(line["quantity"] * line["unit_cost_cents"]) for line in work_order["bom"]
    )
    minutes = sum(step["est_minutes"] for step in work_order["process_steps"])
    return {
        "material_cents": int(material),
        "labour_minutes": int(minutes),
        "lead_time_days": (
            None
            if not work_order.get("promised_delivery_at")
            else work_order["promised_delivery_at"]
        ),
    }
