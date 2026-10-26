# API

Base URL: `http://127.0.0.1:8412`. Loopback only, GET and POST, JSON in and
JSON out. Success responses are `{"ok": true, "data": ...}`; failures are
`{"ok": false, "error": {"code", "message", "details"}}` with 400 (bad request),
404 (not found), 409 (state conflict), 422 (contract violation) or 500.

The table below is compared against the live route table by
`verify/run_verification.py` (group F) and by `tests/test_runner.py`, using
`GET /api/spec -> routes`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness, logical as-of and version |
| GET | `/api/spec` | runtime specification: contracts, industries, counts, route table |
| GET | `/api/i18n` | UI strings for both languages |
| GET | `/api/industries` | industry profiles, workshops and creative styles |
| GET | `/api/rules` | rule catalogue, optionally filtered by `industry` |
| GET | `/api/rules/{rule_id}` | one rule explained: condition, facts, fixes, evidence |
| GET | `/api/library/search` | search by `q`, `tags`, `palette`, `industry`, `family`, `symmetry`, `weight`, `density`, `limit` |
| GET | `/api/library/{asset_id}` | one asset with its licence state and search descriptor |
| POST | `/api/library/ingest` | validate and store a new asset |
| GET | `/api/concepts` | concept list |
| GET | `/api/concepts/{concept_id}` | one concept |
| POST | `/api/workstation/generate` | generate concept candidates |
| POST | `/api/workstation/series` | expand one concept into three SKUs |
| POST | `/api/assess` | run the two-tier assessment |
| GET | `/api/assessments` | assessments created in this session |
| GET | `/api/reviews/queue` | artisan review queue |
| POST | `/api/reviews/{queue_id}/decide` | confirm or override with a reason |
| POST | `/api/orders` | create a pre-sale order |
| GET | `/api/orders` | list orders |
| GET | `/api/orders/{order_id}` | order, events, available transitions, settlement |
| GET | `/api/orders/{order_id}/ledger` | ledger events for one order |
| POST | `/api/orders/{order_id}/advance` | advance one legal state transition |
| POST | `/api/orders/{order_id}/refund` | request, approve, reject or execute a refund |
| POST | `/api/orders/{order_id}/dispute` | open or resolve a dispute |
| GET | `/api/dispatch/board` | dispatch board and work orders |
| GET | `/api/settlement/{order_id}` | settlement for a settled order, including royalty lines |
| GET | `/api/customization/catalog` | option groups, price deltas and conflicts for one industry |
| POST | `/api/customization/preview` | resolve options, derive the concept and gate it |
| GET | `/api/capacity/board` | capacity schedules for every workshop |
| GET | `/api/capacity/quote` | delivery promise and alternatives for a concept |
| GET | `/api/editions` | editions and the collector archive |
| POST | `/api/editions` | open a limited edition |
| POST | `/api/editions/{edition_id}/issue` | issue a numbered certificate |
| POST | `/api/collectors/{record_id}/transfer` | append an ownership transfer |
| GET | `/api/quality/records` | inspection records and their summary |
| POST | `/api/quality/records` | record an inspection against a work order |
| GET | `/api/enterprise` | component registry, both enterprise profiles, industry switch and FDE readiness |
| GET | `/api/enterprise/switch` | the industry switch matrix: two profiles on one registry, no code change |
| GET | `/api/growth/site` | the generated multilingual site with its per-page SEO metadata (add `fresh=1` to rebuild) |
| GET | `/api/growth/crm` | the CRM pipeline board, open follow-ups and SLA breaches |
| POST | `/api/growth/inquiry` | intake an inquiry: score, route, schedule follow-ups, create the lead |
| POST | `/api/growth/inquiries/{inquiry_id}/advance` | move a lead one stage with a written note |
| GET | `/api/ip` | cultural IP package: character bible, asset library, short drama, licence set and reviews |

## Examples

Generate concepts:

```
curl -s -X POST http://127.0.0.1:8412/api/workstation/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"a coastal heritage pendant series","industry":"jewelry","count":4,"style_id":"coastal_minimal"}'
```

Expected: `data.concepts` has four entries, each `DC-00xx`, with a `seed` and a
`craft_facts` bag. Sending the same body again returns the same concepts with
fresh ids.

Assess a concept at a specific workshop:

```
curl -s -X POST http://127.0.0.1:8412/api/assess \
  -H "Content-Type: application/json" \
  -d '{"concept_id":"DC-0002","workshop_id":"WS-JW-A"}'
```

Expected: `data.assessment.final_verdict` is `not_manufacturable`,
`data.assessment.blockers` contains `JW-CAST-001` and `JW-SET-001`, and every
blocker has at least one fix with a `suggested_change`.

Ingest an asset without a licensing source:

```
curl -s -X POST http://127.0.0.1:8412/api/library/ingest \
  -H "Content-Type: application/json" \
  -d '{"asset_id":"PA-JW-0911","title":{"zh":"缺来源","en":"Missing source"},"industries":["jewelry"],"medium":"pattern","license":{"usage_scope":["commercial_product"]},"traditional_prototype":false,"religious_site_names":[],"review":{"status":"auto_checked"},"created_at":"2026-10-22T00:00:00Z"}'
```

Expected: HTTP 422 with `error.code = contract_violation` and a detail entry
`{"path": "$.license", "keyword": "required"}`.

Walk an order:

```
curl -s -X POST http://127.0.0.1:8412/api/orders -d '{"concept_id":"DC-0001"}'
curl -s -X POST http://127.0.0.1:8412/api/orders/ORD-0001/advance \
  -d '{"event":"presale_opened","actor_kind":"designer","actor_id":"designer-01"}'
curl -s -X POST http://127.0.0.1:8412/api/orders/ORD-0001/advance \
  -d '{"event":"payment_received","actor_kind":"buyer","actor_id":"buyer-01"}'
curl -s -X POST http://127.0.0.1:8412/api/orders/ORD-0001/advance \
  -d '{"event":"work_order_issued","actor_kind":"system","actor_id":"system"}'
curl -s http://127.0.0.1:8412/api/orders/ORD-0001
```

Expected: the order reaches `work_order_issued`, a work order appears in
`/api/dispatch/board`, and `events` grows by one per call, each with a 64
character hash. Advancing an event that is not legal in the current state returns
409 `conflict` and writes nothing.

Refund and dispute:

```
curl -s -X POST http://127.0.0.1:8412/api/orders/ORD-0001/refund \
  -d '{"action":"request","reason":"Schedule moved"}'
curl -s -X POST http://127.0.0.1:8412/api/orders/ORD-0001/refund -d '{"action":"approve"}'
curl -s -X POST http://127.0.0.1:8412/api/orders/ORD-0001/refund -d '{"action":"execute"}'
```

For a dispute, `{"action":"open","reason":"...","qc_record_ids":["QCR-0001"]}`
then `{"action":"resolve","resolution":"rework|refund|split","note":"..."}`. The
optional `qc_record_ids` list cites inspections recorded against this order's own
work order; an unknown record, or one from another order, returns 404 or 422. A
split creates a settlement whose total is the order total minus the agreed refund
and whose payout lines still sum to that net total.

## Customisation, capacity, editions and quality

Customisation preview returns the resolved choice, the derived concept and the
capacity quote together, so the buyer sees price and verdict before ordering:

```
curl -s -X POST http://127.0.0.1:8412/api/customization/preview \
  -d '{"concept_id":"DC-0001","selections":[{"group_id":"alloy","option_id":"alloy_22k"}]}'
```

The body answers with `choice.amounts` (base, delta, unit price in cents),
`derived_concept` (the concept the options would produce) and `quote` (workshop,
promise and alternatives). An incompatible pair returns 422 with the reason from
the catalogue; a combination that fails the rules returns `feasibility.ok=false`
with the blockers. `POST /api/orders` accepts the same `selections` array and
stores the applied choice on the order item as `customization_id`.

Capacity and promises:

```
curl -s http://127.0.0.1:8412/api/capacity/board
curl -s 'http://127.0.0.1:8412/api/capacity/quote?concept_id=DC-0001&quantity=2'
```

Editions and the collector archive:

```
curl -s -X POST http://127.0.0.1:8412/api/editions \
  -d '{"concept_id":"DC-0001","size":5,"artist":{"artist_id":"ARTIST-01","name":"Studio Lin","royalty_rate_bp":800}}'
curl -s -X POST http://127.0.0.1:8412/api/editions/ED-0001/issue \
  -d '{"order_id":"ORD-0009","owner":{"owner_id":"OWNER-C1","display_name":"Collector One"}}'
curl -s -X POST http://127.0.0.1:8412/api/collectors/COL-0001/transfer \
  -d '{"owner_id":"OWNER-C2","display_name":"Collector Two","note":"private sale"}'
```

An edition never issues more numbers than its size; the certificate hash covers
the piece identity, so a transfer appends to the provenance chain instead of
invalidating the certificate.

Quality records:

```
curl -s -X POST http://127.0.0.1:8412/api/quality/records \
  -d '{"order_id":"ORD-0006","checkpoint_id":"QC-02","verdict":"fail","defects":[{"code":"setting_loose","count":1}],"inspector":"ART-JW-01"}'
```

A verdict of `pass` cannot carry a major or critical defect, and `fail` needs one;
both are contract invariants, so an inconsistent inspection returns 422. Opening a
dispute with `qc_record_ids` stores the citation on the order and in the ledger
payload, so the resolution can point at the inspection that justified it.

## Static routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | the prototype page |
| GET | `/static/{file}` | stylesheet and script (no directory traversal) |
| GET | `/favicon.ico` | 204, no asset |
| GET | `/{language}` and `/{language}/{page}` | the generated growth site pages (`en`, `zh`, `de`) when `out/site/` exists |
| GET | `/sitemap.xml`, `/robots.txt` | generated crawler files for the growth site |
| GET | `/reel` | the generated sample reel (`out/sample_reel.html`) |

## Errors

| Status | Code | When |
|---|---|---|
| 400 | `bad_json`, `bad_body`, `bad_request` | malformed body, wrong field type, missing prompt |
| 404 | `not_found` | unknown route, concept, asset, order or settlement |
| 409 | `conflict` | illegal transition, duplicate asset, decided review, refund in the wrong state |
| 422 | `contract_violation` | contract or invariant rejection, with field paths |
| 422 | `insufficient_facts` | the concept cannot be assessed at all |
| 405 | `method_not_allowed` | anything other than GET or POST |

`GET /api/spec` is the machine-readable source of truth for this document.
## Model sidecar (separate process)

The AI effect shot is not part of this API. It is served by `model-sidecar/`
(listening on `127.0.0.1:8413` by default), which owns the model key and exposes
`GET /health`, `GET /records`, `POST /generate`, `POST /generate_text`, `GET /report` and `GET /files/<name>`. The
browser calls it directly, which keeps every network client out of the delivery
package and keeps `python -m c2m_craft demo` reproducible. See
`model-sidecar/README.md` for the request and record shapes.
