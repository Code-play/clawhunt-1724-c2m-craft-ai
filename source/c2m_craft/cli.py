"""Command line interface.

Exit codes: 0 success, 2 rejected (a validation or state-machine refusal, which
is a normal business result), 3 usage or environment error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core.errors import CraftError
from .core.settings import ROOT
from .service import Service


def emit(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1))


def build_service(args) -> Service:
    workdir = Path(args.workdir) if getattr(args, "workdir", None) else ROOT / "var" / "cli"
    return Service(ROOT, workdir, reset=bool(getattr(args, "reset", False)))


def cmd_demo(args) -> int:
    from . import demo

    summary = demo.run(ROOT)
    emit(summary)
    return 0


def cmd_serve(args) -> int:
    from .web.server import serve

    service = Service(ROOT, ROOT / "var" / "runtime")
    serve(service, args.host, args.port)
    return 0


def cmd_selftest(args) -> int:
    from .selftest import run as selftest_run

    service = build_service(args)
    result = selftest_run(service)
    service.persist()
    emit(result)
    return 0 if result["ok"] else 2


def cmd_contracts(args) -> int:
    service = build_service(args)
    store = service.store
    if args.action == "list":
        emit(
            {
                "contracts": [
                    {
                        "id": entry["id"],
                        "urn": entry["urn"],
                        "file": entry["file"],
                        "version": entry["version"],
                        "invariants": entry.get("invariants", []),
                        "requirements": entry.get("requirements", []),
                    }
                    for entry in store.registry["contracts"]
                ]
            }
        )
        return 0
    problems = []
    for entry in store.registry["contracts"]:
        if entry["urn"] not in store.schemas:
            problems.append(f"{entry['id']}: schema not loaded")
        for dep in entry.get("deps", []):
            if dep not in store.contract_ids:
                problems.append(f"{entry['id']}: unknown dependency {dep}")
    positives = 0
    for path in sorted((ROOT / "samples" / "contracts" / "positive").glob("*.json")):
        from .demo import contract_for

        payload = store.json_load(path)
        issues = store.validate(contract_for(path.name), payload, ctx={"as_of": service.settings.as_of})
        if issues:
            problems.append(f"{path.name}: {issues[0].path} {issues[0].message}")
        positives += 1
    negatives = store.json_load(ROOT / "samples" / "contracts" / "negative" / "expected.json")["samples"]
    rejected = 0
    for filename, expectation in sorted(negatives.items()):
        payload = store.json_load(ROOT / "samples" / "contracts" / "negative" / filename)
        issues = store.validate(expectation["contract"], payload, ctx={"as_of": service.settings.as_of})
        if not issues:
            problems.append(f"{filename}: negative sample was accepted")
        else:
            rejected += 1
    emit(
        {
            "ok": not problems,
            "contracts": len(store.registry["contracts"]),
            "positives": positives,
            "negatives_rejected": rejected,
            "problems": problems,
        }
    )
    return 0 if not problems else 2


def cmd_rules(args) -> int:
    service = build_service(args)
    from .craft import lint as lint_mod
    from .craft.rules import explain

    if args.action == "lint":
        result = lint_mod.lint_all(service.store, service.settings)
        emit(result)
        return 0 if result["ok"] else 2
    if args.action == "coverage":
        emit(
            {
                "industries": {
                    industry: service.rulesets[industry].stats()
                    for industry in sorted(service.rulesets)
                },
                "facts": {
                    industry: [
                        {
                            "fact": name,
                            "required": bool(spec.get("required")),
                            "type": spec.get("type"),
                        }
                        for name, spec in sorted(service.rulesets[industry].facts_schema.items())
                    ]
                    for industry in sorted(service.rulesets)
                },
            }
        )
        return 0
    industry = args.industry or "jewelry"
    if industry not in service.rulesets:
        print(f"unknown industry {industry!r}", file=sys.stderr)
        return 3
    try:
        emit(explain(service.rulesets[industry], args.rule_id))
    except KeyError:
        print(f"unknown rule {args.rule_id!r}", file=sys.stderr)
        return 3
    return 0


def cmd_assess(args) -> int:
    service = build_service(args)
    concept = service.concept(args.concept)
    workshop = args.workshop or service.default_workshop(concept["industry"])["workshop_id"]
    assessment = service.assess_at(concept, workshop, queue_review=not args.no_review)
    service.persist()
    emit(assessment)
    return 0


def cmd_library(args) -> int:
    service = build_service(args)
    if args.action == "search":
        hits = service.search_library(
            query=args.q or "",
            tags=[item for item in (args.tags or "").split(",") if item],
            palette=[item for item in (args.palette or "").split(",") if item],
            industry=args.industry,
        )
        emit({"results": hits, "count": len(hits)})
        return 0
    if not args.input:
        print("--input is required for ingest", file=sys.stderr)
        return 3
    from .core.contracts import SchemaStore

    payload = SchemaStore.json_load(Path(args.input))
    asset = service.ingest_asset(payload)
    service.persist()
    emit({"asset": asset, "license": service.library.license_state(asset)})
    return 0


def cmd_order(args) -> int:
    service = build_service(args)
    commerce = service.commerce
    if args.action == "create":
        order = service.create_order(
            args.concept,
            model=args.model,
            quantity=args.quantity,
        )
        service.persist()
        emit(order)
        return 0
    if args.action == "list":
        emit({"orders": [service.order(key) for key in sorted(commerce.orders)]})
        return 0
    if not args.id:
        print("--id is required", file=sys.stderr)
        return 3
    if args.action == "show":
        emit(
            {
                "order": service.order(args.id),
                "events": service.order_events(args.id),
                "available_events": commerce.available_events(args.id),
                "settlement": commerce.settlement_for(args.id),
            }
        )
        return 0
    if args.action == "advance":
        if not args.event:
            print("--event is required", file=sys.stderr)
            return 3
        actor_kind = args.actor or "system"
        result = commerce.transition(args.id, args.event, actor={"kind": actor_kind, "id": actor_kind})
        service.persist()
        emit(result)
        return 0
    if args.action == "refund":
        if args.refund_action == "request":
            result = commerce.request_refund(args.id, args.reason or "customer request")
        elif args.refund_action == "approve":
            result = commerce.decide_refund(args.id, approve=True)
        elif args.refund_action == "reject":
            result = commerce.decide_refund(args.id, approve=False)
        elif args.refund_action == "execute":
            result = commerce.execute_refund(args.id)
        else:
            print("--refund-action must be request, approve, reject or execute", file=sys.stderr)
            return 3
        service.persist()
        emit(result)
        return 0
    if args.action == "dispute":
        if args.dispute_action == "open":
            result = commerce.open_dispute(args.id, args.reason or "quality dispute")
        elif args.dispute_action == "resolve":
            result = commerce.resolve_dispute(
                args.id, args.resolution or "split", args.note or "resolved by the platform"
            )
        else:
            print("--dispute-action must be open or resolve", file=sys.stderr)
            return 3
        service.persist()
        emit(result)
        return 0
    print(f"unknown action {args.action!r}", file=sys.stderr)
    return 3


def cmd_customization(args) -> int:
    service = build_service(args)
    if args.action == "catalog":
        emit(service.catalog.describe(args.industry))
        return 0
    selections = []
    for pair in (args.select or "").split(","):
        group_id, _, option_id = pair.partition(":")
        if group_id and option_id:
            selections.append({"group_id": group_id.strip(), "option_id": option_id.strip()})
    if not selections:
        print("--select needs group:option pairs", file=sys.stderr)
        return 3
    built = service.build_customization(args.concept, selections, register=False)
    service.persist()
    emit(built)
    return 0 if built["choice"]["feasibility"]["ok"] else 2


def cmd_capacity(args) -> int:
    service = build_service(args)
    if args.action == "board":
        emit(
            {
                "schedules": service.schedules(),
                "capacity": service.settings.json("config/commerce/capacity.json"),
            }
        )
        return 0
    emit(service.quote(args.concept, quantity=args.quantity))
    return 0


def cmd_edition(args) -> int:
    service = build_service(args)
    if args.action == "list":
        emit(
            {
                "editions": [
                    service.editions.editions[key] for key in sorted(service.editions.editions)
                ],
                "records": service.editions.archive(),
            }
        )
        return 0
    if args.action == "create":
        concept = service.concept(args.concept)
        workshop_id = args.workshop or service.default_workshop(concept["industry"])["workshop_id"]
        edition = service.editions.create(
            concept_id=args.concept,
            size=args.size,
            artist={
                "artist_id": args.artist_id,
                "name": args.artist_name,
                "royalty_rate_bp": args.royalty,
            },
            workshop_id=workshop_id,
            created_at=service.clock.now,
        )
        service.persist()
        emit(edition)
        return 0
    if args.action == "issue":
        if not args.edition or not args.order:
            print("--edition and --order are required", file=sys.stderr)
            return 3
        result = service.editions.issue(
            args.edition,
            number=int(args.number or 0) or service.editions.reserve(args.edition, args.order)["number"],
            order_id=args.order,
            owner={"owner_id": args.owner, "display_name": args.owner_name},
            at=service.clock.now,
        )
        service.persist()
        emit(result)
        return 0
    if args.action == "transfer":
        if not args.record:
            print("--record is required", file=sys.stderr)
            return 3
        record = service.editions.transfer(
            args.record,
            owner_id=args.owner,
            display_name=args.owner_name,
            at=service.clock.now,
            note=args.note or "ownership transferred",
        )
        service.persist()
        emit(record)
        return 0
    print(f"unknown action {args.action!r}", file=sys.stderr)
    return 3


def cmd_quality(args) -> int:
    service = build_service(args)
    if args.action == "list":
        emit({"records": service.quality.records, "summary": service.quality.summary()})
        return 0
    defects = []
    for item in (args.defect or "").split(","):
        if not item.strip():
            continue
        code, _, count = item.partition(":")
        defects.append(
            {"code": code.strip(), "count": int(count or 1), "note": args.note or code.strip()}
        )
    record = service.record_qc(
        args.order,
        args.checkpoint,
        verdict=args.verdict,
        defects=defects,
        inspector=args.inspector or "ART-JW-01",
    )
    emit(record)
    return 0


def cmd_requirements(args) -> int:
    from . import requirements as requirements_mod

    if args.action == "render":
        emit(requirements_mod.render(ROOT))
        return 0
    result = requirements_mod.check(ROOT)
    emit({"ok": result["ok"], "problems": result["problems"], "stats": result["stats"], "acceptance": result["acceptance"]})
    return 0 if result["ok"] else 2


def cmd_spec(args) -> int:
    service = build_service(args)
    emit(service.spec())
    return 0


def cmd_setup(args) -> int:
    service = build_service(args)
    service.persist()
    emit({"ok": True, "workdir": str(service.workdir), "state": str(service.state_path)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="c2m_craft",
        description="C2M craft co-creation prototype: contracts, craft rules, orders and a clickable workstation.",
    )
    parser.add_argument("--workdir", help="directory for working state (default var/cli)")
    parser.add_argument("--reset", action="store_true", help="clear the working state first")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("demo", help="regenerate every out/ artifact")
    sub.add_parser("selftest", help="check the offline, deterministic guarantees")
    sub.add_parser("spec", help="print the runtime specification")

    serve = sub.add_parser("serve", help="start the clickable prototype on loopback")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8412)

    contracts = sub.add_parser("contracts", help="list or verify the data contracts")
    contracts.add_argument("action", choices=["list", "verify"])

    rules = sub.add_parser("rules", help="lint, inspect or explain craft rules")
    rules.add_argument("action", choices=["lint", "coverage", "explain"])
    rules.add_argument("--rule-id", default="")
    rules.add_argument("--industry", default="")

    assess = sub.add_parser("assess", help="run the two-tier assessment for one concept")
    assess.add_argument("--concept", required=True)
    assess.add_argument("--workshop", default="")
    assess.add_argument("--no-review", action="store_true")

    library = sub.add_parser("library", help="search or ingest pattern assets")
    library.add_argument("action", choices=["search", "ingest"])
    library.add_argument("--q", default="")
    library.add_argument("--tags", default="")
    library.add_argument("--palette", default="")
    library.add_argument("--industry", default="")
    library.add_argument("--input", default="")

    order = sub.add_parser("order", help="create, inspect or advance an order")
    order.add_argument("action", choices=["create", "show", "list", "advance", "refund", "dispute"])
    order.add_argument("--id", default="")
    order.add_argument("--concept", default="")
    order.add_argument("--model", default="designer_presale")
    order.add_argument("--quantity", type=int, default=1)
    order.add_argument("--event", default="")
    order.add_argument("--actor", default="system")
    order.add_argument("--refund-action", default="")
    order.add_argument("--dispute-action", default="")
    order.add_argument("--resolution", default="split")
    order.add_argument("--reason", default="")
    order.add_argument("--note", default="")

    req = sub.add_parser("requirements", help="render or check the requirement matrix")
    req.add_argument("action", choices=["render", "check"])

    customization = sub.add_parser("customization", help="option catalogue and price preview")
    customization.add_argument("action", choices=["catalog", "preview"])
    customization.add_argument("--concept", default="")
    customization.add_argument("--select", default="")
    customization.add_argument("--industry", default="jewelry")

    capacity = sub.add_parser("capacity", help="capacity board and delivery quotes")
    capacity.add_argument("action", choices=["board", "quote"])
    capacity.add_argument("--concept", default="")
    capacity.add_argument("--quantity", type=int, default=1)

    edition = sub.add_parser("edition", help="limited editions and the collector archive")
    edition.add_argument("action", choices=["list", "create", "issue", "transfer"])
    edition.add_argument("--concept", default="")
    edition.add_argument("--size", type=int, default=8)
    edition.add_argument("--workshop", default="")
    edition.add_argument("--artist-id", default="ARTIST-01")
    edition.add_argument("--artist-name", default="Studio Lin")
    edition.add_argument("--royalty", type=int, default=800)
    edition.add_argument("--edition", default="")
    edition.add_argument("--record", default="")
    edition.add_argument("--order", default="")
    edition.add_argument("--number", type=int, default=0)
    edition.add_argument("--owner", default="OWNER-GUEST")
    edition.add_argument("--owner-name", default="Guest collector")
    edition.add_argument("--note", default="")

    quality = sub.add_parser("quality", help="quality records")
    quality.add_argument("action", choices=["list", "record"])
    quality.add_argument("--order", default="")
    quality.add_argument("--checkpoint", default="QC-01")
    quality.add_argument("--verdict", choices=["pass", "fail", "rework"], default="pass")
    quality.add_argument("--defect", default="")
    quality.add_argument("--note", default="")
    quality.add_argument("--inspector", default="ART-JW-01")

    sub.add_parser("setup", help="create the working state file")
    return parser


COMMANDS = {
    "demo": cmd_demo,
    "serve": cmd_serve,
    "selftest": cmd_selftest,
    "spec": cmd_spec,
    "contracts": cmd_contracts,
    "rules": cmd_rules,
    "assess": cmd_assess,
    "library": cmd_library,
    "order": cmd_order,
    "customization": cmd_customization,
    "capacity": cmd_capacity,
    "edition": cmd_edition,
    "quality": cmd_quality,
    "requirements": cmd_requirements,
    "setup": cmd_setup,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS[args.command]
    try:
        return int(handler(args))
    except CraftError as exc:
        print(json.dumps({"ok": False, "error": exc.as_dict()}, ensure_ascii=False, indent=1))
        return 2
    except FileNotFoundError as exc:
        print(f"missing file: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
