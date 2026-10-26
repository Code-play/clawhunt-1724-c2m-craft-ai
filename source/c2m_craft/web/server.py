"""Standard-library HTTP server for the clickable prototype.

Only loopback binding, GET and POST, JSON in and JSON out.  Static assets are
served from ``static/``; the API route table is exported by ``/api/spec`` so the
documentation check can compare the guide with the code.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from ..core.errors import CraftError, NotFound, ValidationFailed

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
GENERATED_DIR = Path(__file__).resolve().parents[2] / "out"
LANG_PAGE = re.compile(r"^/(zh|en|de|ja|ar)(?:/([a-z0-9-]+))?$")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}

Route = tuple[str, str, re.Pattern, Callable]


def route(method: str, pattern: str):
    regex = re.compile(pattern)

    def decorate(func: Callable) -> Route:
        return (method, pattern, regex, func)

    return decorate


# -- handlers -------------------------------------------------------------
@route("GET", r"^/api/health$")
def health(service, request) -> dict:
    return {"status": "ok", "as_of": service.settings.as_of, "version": service.settings.site["version"]}


@route("GET", r"^/api/spec$")
def spec(service, request) -> dict:
    payload = service.spec()
    payload["routes"] = [{"method": method, "path": pattern} for method, pattern, _, _ in ROUTES]
    return payload


@route("GET", r"^/api/i18n$")
def i18n(service, request) -> dict:
    language = request["query"].get("lang", [service.settings.site["default_language"]])[0]
    return {"language": language, "strings": service.settings.json("config/i18n/ui.json")}


@route("GET", r"^/api/industries$")
def industries(service, request) -> dict:
    rows = []
    for industry in service.settings.industry_ids():
        profile = service.settings.industry(industry)
        rows.append(
            {
                "industry": industry,
                "title": profile["title"],
                "categories": profile["categories"],
                "default_workshop": profile["default_workshop"],
                "workshops": [
                    {
                        "workshop_id": workshop["workshop_id"],
                        "name": workshop["name"],
                        "lead_time_days": workshop["lead_time_days"],
                    }
                    for workshop in service.workshops_for(industry)
                ],
            }
        )
    return {
        "industries": rows,
        "styles": [
            {
                "style_id": style["style_id"],
                "title": style["title"],
                "texture": style["texture"],
            }
            for style in service.settings.styles()["styles"]
        ],
    }


@route("GET", r"^/api/rules$")
def rules(service, request) -> dict:
    industry = request["query"].get("industry", [None])[0]
    rows = []
    for name in sorted(service.rulesets):
        if industry and name != industry:
            continue
        ruleset = service.rulesets[name]
        for rule in ruleset.rules:
            rows.append(
                {
                    "rule_id": rule["id"],
                    "industry": name,
                    "process": rule["process"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "review": rule["review"],
                    "has_fix": bool(rule["fixes"]),
                }
            )
    return {"rules": rows, "count": len(rows)}


@route("GET", r"^/api/rules/(?P<rule_id>[A-Za-z0-9_-]+)$")
def rule_detail(service, request) -> dict:
    from ..craft.rules import explain

    rule_id = request["path"]["rule_id"]
    for name in sorted(service.rulesets):
        try:
            return explain(service.rulesets[name], rule_id)
        except KeyError:
            continue
    raise NotFound(f"rule {rule_id} not found")


@route("GET", r"^/api/library/search$")
def library_search(service, request) -> dict:
    query = request["query"]
    industry = query.get("industry", [None])[0]
    palette = [item for item in (query.get("palette", [""])[0] or "").split(",") if item]
    tags = [item for item in (query.get("tags", [""])[0] or "").split(",") if item]
    density = query.get("density", [""])[0]
    hits = service.search_library(
        query=query.get("q", [""])[0],
        tags=tags,
        palette=palette,
        industry=industry or None,
        motif_family=query.get("family", [None])[0] or None,
        symmetry=query.get("symmetry", [None])[0] or None,
        line_weight=query.get("weight", [None])[0] or None,
        density_bp=int(density) if density else None,
        limit=int(query.get("limit", ["20"])[0]),
    )
    return {"results": hits, "count": len(hits)}


@route("GET", r"^/api/library/(?P<asset_id>PA-[A-Z]{2}-[0-9]{4})$")
def library_asset(service, request) -> dict:
    asset = service.library.get(request["path"]["asset_id"])
    return {"asset": asset, "license": service.library.license_state(asset)}


@route("POST", r"^/api/library/ingest$")
def library_ingest(service, request) -> dict:
    payload = request["body"]
    asset = service.ingest_asset(payload)
    return {"asset": asset, "license": service.library.license_state(asset)}


@route("GET", r"^/api/concepts$")
def concepts(service, request) -> dict:
    rows = [
        {
            "concept_id": concept["concept_id"],
            "title": concept["title"],
            "industry": concept["industry"],
            "category": concept["form"]["category"],
            "palette": concept["palette"],
            "preview": concept["preview"],
        }
        for concept in service.concepts.values()
    ]
    rows.sort(key=lambda row: row["concept_id"])
    return {"concepts": rows, "count": len(rows)}


@route("GET", r"^/api/concepts/(?P<concept_id>DC-[0-9]{4})$")
def concept_detail(service, request) -> dict:
    return {"concept": service.concept(request["path"]["concept_id"])}


@route("POST", r"^/api/workstation/generate$")
def workstation_generate(service, request) -> dict:
    body = request["body"]
    text = str(body.get("text") or "").strip()
    industry = str(body.get("industry") or "")
    if not text:
        raise ValidationFailed("text is required")
    if industry not in service.settings.industry_ids():
        raise ValidationFailed(f"unknown industry {industry!r}")
    count = int(body.get("count") or 4)
    palette = body.get("reference_palette") or None
    if palette is not None and not isinstance(palette, list):
        raise ValidationFailed("reference_palette must be a list of hex colours")
    created = service.generate(
        text,
        industry,
        count=count,
        style_id=body.get("style_id") or None,
        reference_palette=palette,
    )
    return {"concepts": created, "count": len(created)}


@route("POST", r"^/api/workstation/series$")
def workstation_series(service, request) -> dict:
    concept_id = str(request["body"].get("concept_id") or "")
    skus = service.expand_series(concept_id)
    return {"series": skus, "count": len(skus)}


@route("POST", r"^/api/assess$")
def assess(service, request) -> dict:
    body = request["body"]
    concept_id = body.get("concept_id")
    concept = body.get("concept")
    if concept_id:
        concept = service.concept(str(concept_id))
    if not isinstance(concept, dict):
        raise ValidationFailed("provide concept_id or a concept object")
    workshop_id = str(body.get("workshop_id") or service.default_workshop(concept["industry"])["workshop_id"])
    queue_review = body.get("queue_review", True)
    assessment = service.assess_at(concept, workshop_id, queue_review=bool(queue_review))
    return {"assessment": assessment}


@route("GET", r"^/api/assessments$")
def assessments(service, request) -> dict:
    rows = [service.commerce.assessments[key] for key in sorted(service.commerce.assessments)]
    return {"assessments": rows, "count": len(rows)}


@route("GET", r"^/api/reviews/queue$")
def review_queue(service, request) -> dict:
    return {
        "items": list(service.reviews.items),
        "pending": len(service.reviews.pending()),
    }


@route("POST", r"^/api/reviews/(?P<queue_id>AR-[0-9]{4})/decide$")
def review_decide(service, request) -> dict:
    body = request["body"]
    verdict = str(body.get("verdict") or "")
    reason = str(body.get("reason") or "")
    if not verdict:
        raise ValidationFailed("verdict is required")
    return service.decide_review(request["path"]["queue_id"], verdict, reason)


@route("POST", r"^/api/orders$")
def create_order(service, request) -> dict:
    body = request["body"]
    concept_id = str(body.get("concept_id") or "")
    order = service.create_order(
        concept_id,
        model=str(body.get("model") or "designer_presale"),
        buyer=body.get("buyer") or None,
        quantity=int(body.get("quantity") or 1),
        customizations=body.get("customizations") or None,
    )
    return {"order": order}


@route("GET", r"^/api/orders$")
def list_orders(service, request) -> dict:
    return {"orders": [service.order(order_id) for order_id in sorted(service.commerce.orders)]}


@route("GET", r"^/api/orders/(?P<order_id>ORD-[0-9]{4})$")
def order_detail(service, request) -> dict:
    order_id = request["path"]["order_id"]
    order = service.order(order_id)
    return {
        "order": order,
        "events": service.order_events(order_id),
        "available_events": service.commerce.available_events(order_id),
        "settlement": service.commerce.settlement_for(order_id),
    }


@route("GET", r"^/api/orders/(?P<order_id>ORD-[0-9]{4})/ledger$")
def order_ledger(service, request) -> dict:
    order_id = request["path"]["order_id"]
    return {"events": service.order_events(order_id), "order_id": order_id}


@route("POST", r"^/api/orders/(?P<order_id>ORD-[0-9]{4})/advance$")
def order_advance(service, request) -> dict:
    order_id = request["path"]["order_id"]
    body = request["body"]
    event = str(body.get("event") or "")
    actor_kind = str(body.get("actor_kind") or "system")
    actor_id = str(body.get("actor_id") or actor_kind)
    if not event:
        raise ValidationFailed("event is required")
    return service.commerce.transition(
        order_id, event, actor={"kind": actor_kind, "id": actor_id}, payload=body.get("payload") or None
    )


@route("POST", r"^/api/orders/(?P<order_id>ORD-[0-9]{4})/refund$")
def order_refund(service, request) -> dict:
    order_id = request["path"]["order_id"]
    body = request["body"]
    action = str(body.get("action") or "")
    if action == "request":
        reason = str(body.get("reason") or "").strip()
        if not reason:
            raise ValidationFailed("a refund request needs a reason")
        return service.commerce.request_refund(order_id, reason)
    if action == "approve":
        return service.commerce.decide_refund(order_id, approve=True)
    if action == "reject":
        return service.commerce.decide_refund(order_id, approve=False)
    if action == "execute":
        return service.commerce.execute_refund(order_id)
    raise ValidationFailed("action must be request, approve, reject or execute")


@route("POST", r"^/api/orders/(?P<order_id>ORD-[0-9]{4})/dispute$")
def order_dispute(service, request) -> dict:
    order_id = request["path"]["order_id"]
    body = request["body"]
    action = str(body.get("action") or "")
    if action == "open":
        reason = str(body.get("reason") or "").strip()
        if not reason:
            raise ValidationFailed("opening a dispute needs a reason")
        evidence = body.get("qc_record_ids") or []
        if not isinstance(evidence, list):
            raise ValidationFailed("qc_record_ids must be a list")
        return service.commerce.open_dispute(order_id, reason, qc_record_ids=evidence)
    if action == "resolve":
        resolution = str(body.get("resolution") or "")
        note = str(body.get("note") or "").strip()
        if not note:
            raise ValidationFailed("resolving a dispute needs a note")
        return service.commerce.resolve_dispute(order_id, resolution, note)
    raise ValidationFailed("action must be open or resolve")


@route("GET", r"^/api/dispatch/board$")
def dispatch_board(service, request) -> dict:
    return {
        "board": service.commerce.board(),
        "work_orders": [
            service.commerce.work_orders[key] for key in sorted(service.commerce.work_orders)
        ],
    }


@route("GET", r"^/api/settlement/(?P<order_id>ORD-[0-9]{4})$")
def settlement_detail(service, request) -> dict:
    settlement = service.commerce.settlement_for(request["path"]["order_id"])
    if not settlement:
        raise NotFound(f"order {request['path']['order_id']} has no settlement yet")
    return {"settlement": settlement}


# -- milestone 2: customisation, capacity, editions, quality --------------
@route("GET", r"^/api/customization/catalog$")
def customization_catalog(service, request) -> dict:
    industry = request["query"].get("industry", [service.settings.industry_ids()[0]])[0]
    if industry not in service.settings.industry_ids():
        raise ValidationFailed(f"unknown industry {industry!r}")
    return service.catalog.describe(industry)


@route("POST", r"^/api/customization/preview$")
def customization_preview(service, request) -> dict:
    body = request["body"]
    concept_id = str(body.get("concept_id") or "")
    selections = body.get("selections") or []
    if not isinstance(selections, list) or not selections:
        raise ValidationFailed("selections must be a non-empty list")
    return service.build_customization(concept_id, selections, register=False)


@route("GET", r"^/api/capacity/board$")
def capacity_board(service, request) -> dict:
    return {
        "schedules": service.schedules(),
        "capacity": service.settings.json("config/commerce/capacity.json"),
    }


@route("GET", r"^/api/capacity/quote$")
def capacity_quote(service, request) -> dict:
    query = request["query"]
    concept_id = query.get("concept_id", [""])[0]
    if not concept_id:
        raise ValidationFailed("concept_id is required")
    quantity = int(query.get("quantity", ["1"])[0])
    return service.quote(concept_id, quantity=quantity)


@route("GET", r"^/api/editions$")
def editions(service, request) -> dict:
    return {
        "editions": [
            service.editions.editions[key] for key in sorted(service.editions.editions)
        ],
        "records": service.editions.archive(),
    }


@route("POST", r"^/api/editions$")
def create_edition(service, request) -> dict:
    body = request["body"]
    concept_id = str(body.get("concept_id") or "")
    size = int(body.get("size") or 0)
    artist = body.get("artist") or {}
    workshop_id = str(body.get("workshop_id") or service.default_workshop(service.concept(concept_id)["industry"])["workshop_id"])
    edition = service.editions.create(
        concept_id=concept_id,
        size=size,
        artist=artist,
        workshop_id=workshop_id,
        created_at=service.clock.now,
    )
    service.persist()
    return {"edition": edition}


@route("POST", r"^/api/editions/(?P<edition_id>ED-[0-9]{4})/issue$")
def issue_edition(service, request) -> dict:
    body = request["body"]
    order_id = str(body.get("order_id") or "")
    owner = body.get("owner") or {}
    number = body.get("number")
    edition_id = request["path"]["edition_id"]
    if number is None:
        reservation = service.editions.reserve(edition_id, order_id)
        number = reservation["number"]
    result = service.editions.issue(
        edition_id,
        number=int(number),
        order_id=order_id,
        owner={
            "owner_id": str(owner.get("owner_id") or "OWNER-GUEST"),
            "display_name": str(owner.get("display_name") or "Guest collector"),
        },
        at=service.clock.now,
    )
    service.persist()
    return result


@route("POST", r"^/api/collectors/(?P<record_id>COL-[0-9]{4})/transfer$")
def transfer_collector(service, request) -> dict:
    body = request["body"]
    record = service.editions.transfer(
        request["path"]["record_id"],
        owner_id=str(body.get("owner_id") or ""),
        display_name=str(body.get("display_name") or ""),
        at=service.clock.now,
        note=str(body.get("note") or "ownership transferred"),
    )
    service.persist()
    return {"record": record}


@route("GET", r"^/api/quality/records$")
def quality_records(service, request) -> dict:
    work_order_id = request["query"].get("work_order_id", [""])[0]
    rows = (
        service.quality.for_work_order(work_order_id)
        if work_order_id
        else list(service.quality.records)
    )
    return {"records": rows, "summary": service.quality.summary()}


@route("POST", r"^/api/quality/records$")
def record_quality(service, request) -> dict:
    body = request["body"]
    return {
        "record": service.record_qc(
            str(body.get("order_id") or ""),
            str(body.get("checkpoint_id") or ""),
            verdict=str(body.get("verdict") or ""),
            defects=body.get("defects") or [],
            inspector=str(body.get("inspector") or "ART-JW-01"),
        )
    }


@route("GET", r"^/api/enterprise$")
def enterprise(service, request) -> dict:
    return service.enterprise.describe()


@route("GET", r"^/api/enterprise/switch$")
def enterprise_switch(service, request) -> dict:
    return service.enterprise_switch()


@route("GET", r"^/api/growth/site$")
def growth_site(service, request) -> dict:
    fresh = request["query"].get("fresh", [""])[0] == "1"
    return {"site": service.growth_site(fresh=fresh)}


@route("GET", r"^/api/growth/crm$")
def growth_crm(service, request) -> dict:
    return dict(service.growth_crm(), inquiries=[service.growth.crm.get(key) for key in sorted(service.growth.crm.inquiries)])


@route("POST", r"^/api/growth/inquiry$")
def growth_inquiry(service, request) -> dict:
    body = request["body"]
    payload = {
        "language": str(body.get("language") or "en"),
        "contact": body.get("contact") or {},
        "message": str(body.get("message") or ""),
        "intent": str(body.get("intent") or "information"),
        "product_interest": body.get("product_interest") or [],
    }
    return {"inquiry": service.growth_inquiry(payload)}


@route("POST", r"^/api/growth/inquiries/(?P<inquiry_id>INQ-[0-9]{4})/advance$")
def growth_advance(service, request) -> dict:
    body = request["body"]
    return {
        "inquiry": service.growth_advance(
            request["path"]["inquiry_id"],
            str(body.get("stage") or ""),
            str(body.get("note") or ""),
        )
    }


@route("GET", r"^/api/ip$")
def ip_pipeline(service, request) -> dict:
    return service.ip.describe()


ROUTES: list[Route] = [
    health,
    spec,
    i18n,
    industries,
    rules,
    rule_detail,
    library_search,
    library_asset,
    library_ingest,
    concepts,
    concept_detail,
    workstation_generate,
    workstation_series,
    assess,
    assessments,
    review_queue,
    review_decide,
    create_order,
    list_orders,
    order_detail,
    order_ledger,
    order_advance,
    order_refund,
    order_dispute,
    dispatch_board,
    settlement_detail,
    customization_catalog,
    customization_preview,
    capacity_board,
    capacity_quote,
    editions,
    create_edition,
    issue_edition,
    transfer_collector,
    quality_records,
    record_quality,
    enterprise,
    enterprise_switch,
    growth_site,
    growth_crm,
    growth_inquiry,
    growth_advance,
    ip_pipeline,
]


def route_table() -> list[dict]:
    return [{"method": method, "path": pattern} for method, pattern, _, _ in ROUTES]


class Handler(BaseHTTPRequestHandler):
    server_version = "c2m-craft/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep the console clean
        return

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._send_json(405, {"ok": False, "error": {"code": "method_not_allowed", "message": "only GET and POST"}})

    do_DELETE = do_PUT

    # -- internals -------------------------------------------------------
    def _dispatch(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/" or path.startswith("/static/") or path == "/favicon.ico":
            self._serve_static(path)
            return
        if self._serve_generated(path):
            return
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    self._send_json(400, {"ok": False, "error": {"code": "bad_json", "message": "request body is not valid JSON"}})
                    return
                if not isinstance(body, dict):
                    self._send_json(400, {"ok": False, "error": {"code": "bad_body", "message": "request body must be a JSON object"}})
                    return
        for candidate_method, pattern, regex, handler in ROUTES:
            if candidate_method != method:
                continue
            match = regex.match(path)
            if not match:
                continue
            request = {"path": match.groupdict(), "query": query, "body": body, "method": method}
            try:
                with self.server.lock:  # type: ignore[attr-defined]
                    payload = handler(self.server.service, request)  # type: ignore[attr-defined]
                    if method == "POST":
                        self.server.service.persist()  # type: ignore[attr-defined]
            except CraftError as exc:
                self._send_json(exc.http_status, {"ok": False, "error": exc.as_dict()})
                return
            except (ValueError, KeyError) as exc:
                self._send_json(400, {"ok": False, "error": {"code": "bad_request", "message": str(exc), "details": []}})
                return
            except Exception as exc:  # noqa: BLE001
                self._send_json(
                    500,
                    {"ok": False, "error": {"code": "internal_error", "message": f"{type(exc).__name__}: {exc}", "details": []}},
                )
                return
            self._send_json(200, {"ok": True, "data": payload})
            return
        self._send_json(404, {"ok": False, "error": {"code": "not_found", "message": f"no route for {method} {path}"}})

    def _serve_generated(self, path: str) -> bool:
        """Serve the generated growth site and the sample reel, when present."""
        if path == "/reel":
            candidate = GENERATED_DIR / "sample_reel.html"
            if candidate.is_file():
                self._send_file(candidate, "text/html; charset=utf-8")
                return True
            return False
        if path in ("/sitemap.xml", "/robots.txt"):
            candidate = GENERATED_DIR / "site" / path.lstrip("/")
            if not candidate.is_file():
                return False
            kind = "application/xml; charset=utf-8" if path.endswith(".xml") else "text/plain; charset=utf-8"
            self._send_file(candidate, kind)
            return True
        match = LANG_PAGE.match(path)
        if not match:
            return False
        language = match.group(1)
        slug = match.group(2) or "index"
        candidate = GENERATED_DIR / "site" / language / f"{slug}.html"
        if not candidate.is_file():
            return False
        self._send_file(candidate, "text/html; charset=utf-8")
        return True

    def _send_file(self, candidate: Path, content_type: str) -> None:
        content = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _serve_static(self, path: str) -> None:
        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        relative = "index.html" if path == "/" else path[len("/static/"):]
        candidate = (STATIC_DIR / relative).resolve()
        if not str(candidate).startswith(str(STATIC_DIR.resolve())) or not candidate.is_file():
            self._send_json(404, {"ok": False, "error": {"code": "not_found", "message": path}})
            return
        self._send_file(candidate, CONTENT_TYPES.get(candidate.suffix, "application/octet-stream"))

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CraftServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, service):
        super().__init__(address, Handler)
        self.service = service
        self.lock = threading.Lock()


def create_server(service, host: str = "127.0.0.1", port: int = 8412) -> CraftServer:
    return CraftServer((host, port), service)


def start_in_thread(service, host: str = "127.0.0.1", port: int = 0):
    server = create_server(service, host, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, actual_port = server.server_address[0], server.server_address[1]
    return server, thread, f"http://{host}:{actual_port}"


def serve(service, host: str = "127.0.0.1", port: int = 8412) -> None:
    server = create_server(service, host, port)
    print(f"[serve] C2M craft prototype on http://{host}:{port} (loopback only)")
    print("[serve] press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] stopped")
    finally:
        server.server_close()
