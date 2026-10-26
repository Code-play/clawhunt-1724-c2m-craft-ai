# Architecture

## 1. Scope

The repository delivers four milestones on one code base:

1. **M1** - architecture and data contracts, the manufacturability rule modelling
   plan, the clickable workstation prototype, and the C2M order spine.
2. **M2** - participatory customisation, limited editions and the collector archive,
   the capacity calendar and delivery promises, descriptor search, per-asset
   royalties and quality records.
3. **M3** - the componentised enterprise AI service layer for two industries, the
   FDE handbook and a populated profile, and the growth stack: multilingual site
   generation, SEO audit and the inquiry-to-CRM closed loop.
4. **M4** - the cultural IP pipeline: dual guardian bible, visual asset library
   described as vector recipes, short drama from script to final cut with one sample
   reel, licensing document set, merchandise specifications and content reviews.

A model-integration increment adds real Qwen image and copy calls through an
optional sidecar process (section 10) while the repository itself stays offline and
reproducible.

## 2. Module map

```
c2m_craft/
  core/       contracts, invariants, logical clock, money, canonical JSON, ledger
  craft/      facts, rule engine, lint, two-tier assessment, artisan review
  creative/   offline concept adapter, workstation, series expansion
  library/    licensed assets, ingestion gate, descriptor search, licence terms
  commerce/   order state machines, capacity planner, customisation catalogue,
              editions and collector records, quality records, dispatch synthesis,
              settlement with royalty allocation
  enterprise/ component registry, profile assembly, FDE readiness and the growth
              stack (site generator, SEO auditor, inquiry-to-CRM loop)
  ip/         character bible, visual asset recipes, short drama, sample reel,
              licensing pack and content reviews
  web/        standard-library HTTP server and JSON API
  service.py  wiring: configuration, rulesets, library, commerce, enterprise, IP
  demo.py     regenerates every artifact under out/
  requirements.py  requirement matrix check and render
  selftest.py environment and offline-guarantee checks
  cli.py      command line entry point
```

Dependency rule: `core` imports nothing from the other packages; `craft`,
`creative`, `library`, `commerce`, `enterprise` and `ip` depend only on `core`; `web`
depends on the service container. This is what lets the B and C modules (enterprise
service layer, cultural IP pipeline) land in M3/M4 without touching the kernel.

## 3. Request flow

```
browser tab
   |
   v
HTTP JSON API (web/server.py)
   |
   v
Service (service.py)  --- configuration ---> config/*.json
   |                        contracts   ---> contracts/*.schema.json
   |                        rules       ---> config/craft_rules/*.json
   |                        workshops   ---> config/equipment/*.json
   v
creative.workstation  --concept-->  craft.assessment --verdict-->  commerce.orders
                                                                        |
                                                      dispatch.build --> work order
                                                                        |
                                                       settlement.build -> payout lines
                                                                        |
                                                        core.ledger -> hash chain

enterprise.registry --select--> enterprise profile --assemble--> capability envelope
                                       |
                                       +--> growth.site  -> out/site pages + sitemap
                                       +--> growth.seo   -> audit and score
                                       +--> growth.crm   -> inquiry -> lead -> quote

ip.bible --> ip.visuals (vector recipes + checksum) --+
      |                                               +--> ip.drama -> EDL + subtitles
      +--> ip.reviews -> authenticity block           |        |
                                                      |        +--> ip.reel -> out/sample_reel.html
      ip.licensing -> signed document set + merch specs + coverage invariant
```

Every state change appends one event to the ledger. The ledger is append-only on
disk (`var/<run>/ledger.jsonl`) and each row hashes its sequence number, the
previous row hash and its own body, so an edited, deleted or reordered row is
detected by recomputation rather than by trust.

## 4. Determinism

The delivery is reproducible on purpose, because the brief requires that re-running
verification yields the same conclusions.

- **No wall clock.** `core/clock.py` provides a `LogicalClock` rooted at
  `config/site.json -> as_of`. Each mutation advances it by an explicit number of
  minutes. Nothing in the package calls `datetime.now`, `date.today` or `time.time`;
  `selftest` proves this by AST scan.
- **No network.** There is no HTTP client anywhere in the package. The model
  boundary (`creative/adapters.py`) is a protocol with an offline implementation,
  and the real model lives in a separate process.
- **Seeded generation.** Concept seeds are `sha256(prompt|industry|style|palette|index)`
  and all randomness comes from `random.Random(seed)`.
- **Canonical serialisation.** JSON is written with `sort_keys=True`,
  `ensure_ascii=False` and LF endings. `out/hash_manifest.json` records the SHA-256
  of the other 32 artifacts, including the generated site; two consecutive demo runs
  must produce the same manifest.
- **Recipes instead of binaries.** Visual assets are vector layer lists, the reel is
  HTML with inline SVG, and the site pages are strings. Nothing generated embeds a
  timestamp or a random id.

## 5. Clickable prototype

`python -m c2m_craft serve` binds `127.0.0.1:8412` only. `static/` holds one HTML
page, one stylesheet and one script; there is no build step, no CDN and no external
font. The concept preview is drawn procedurally from the palette and motif style
(CSS gradients), the IP assets are drawn from their recipes in SVG, so the
repository carries no binary assets.

Tabs and the workflows they carry:

| Tab | Workflow | Backing code |
|---|---|---|
| Creative workstation | brief or reference image to concepts, series and verdict | `creative/*`, `craft/*` |
| Pattern library | descriptor search and licensed ingestion with rejection paths | `library/assets.py` |
| Pre-sale orders | order, customisation, edition, refund, dispute and settlement | `commerce/orders.py`, `commerce/customization.py`, `commerce/editions.py` |
| Factory dispatch | capacity board, work order, BOM, process route, QC records | `commerce/capacity.py`, `commerce/dispatch.py`, `commerce/quality.py` |
| Contracts and rules | contract registry, rule catalogue, review queue | `core/contracts.py`, `craft/lint.py` |
| Enterprise | industry switch, assembly plan, FDE readiness, generated site, inquiry and CRM pipeline | `enterprise/*` |
| IP studio | character bible, visual library, storyboard, reel, licence set, reviews | `ip/*` |

The API route table is exported at `GET /api/spec`; `docs/api.md` is compared
against it by the verification script, so the guide cannot drift from the code. The
generated site is served read-only at `/{language}` and `/{language}/{page}`, and the
reel at `/reel`; those page routes sit outside the JSON API table on purpose.

## 6. Data contracts

Twenty-three contracts, versioned in `contracts/registry.json` at 2.0.0:

`common`, `pattern_asset`, `design_concept`, `manufacturability_assessment`,
`craft_work_order`, `c2m_order` (with the ledger event as `$defs`), `settlement`,
`artisan_review`, `enterprise_profile`, `ip_license`, and the five M2 additions
`customization_choice`, `edition`, `collector_record`, `qc_record` and
`production_schedule`.

M3 adds `service_component`, `growth_site` and `inquiry_lead`, and bumps
`enterprise_profile` to 1.1.0 with data boundaries, deployment posture and the growth
stack. M4 adds `character_bible`, `visual_asset`, `short_drama`, `content_review` and
`merch_spec`, and bumps `ip_license` to 1.1.0 with the signed document set and the
merchandise specification references.

The validator is a hand-written JSON Schema 2020-12 subset (see
`docs/data-contracts.md` for the exact keyword list). Cross-field rules live in
`x-invariants` and are implemented in `core/invariants.py`; 25 invariants are
registered and each one has at least one committed negative sample.

## 7. Milestone 2 mechanics

**Capacity and promises.** Each workshop profile declares a daily capacity in
working minutes and a set of ISO working days. Committed work orders book their
minutes backwards from their promised date, filling the remaining capacity per day;
a new order fills forwards from the quote date. The promised date is the first
working day with enough room, pushed past the configured lead time; the order stores
the workshop, the slot, the working minutes and every alternative that was rejected.

**Customisation.** The catalogue lives in `config/commerce/customization.json`. A
selection resolves to fact changes and a signed basis-point price delta; the engine
derives a new concept, runs the manufacturability gate again and only then prices
the order. Conflicting options are refused with the catalogue reason.

**Editions.** A number is reserved when an order referencing the edition is created
and issued when that order settles. The certificate hash covers the edition, number,
concept and certificate id, so transfers append to the provenance chain without
invalidating the certificate.

**Royalties and quality.** At settlement the licence terms of every asset used by
the order weight a largest-remainder split of the IP payout. Inspections record
defects by taxonomy code with derived measurement limits; `INV-QC-01` refuses a pass
carrying a major or critical defect and a failure without one.

## 8. Milestone 3 mechanics

**Component registry and profile assembly.** `config/enterprise/components.json`
declares ten reusable components, each validated against `service_component`:
industries, capabilities, contracts, dependencies, configuration path, data boundary
and maturity. An enterprise profile selects components and adds locale, channels,
SLA, growth stack, data boundaries, deployment and the client go-live list. The
runtime resolves every selection, checks the industry, the configuration path, the
registered contracts and the enabled dependencies, and reports each blocker with its
component id. Assembly status is derived, never typed.

**Industry switch.** `config/enterprise/profiles/EP-0001.json` (jewellery) and
`EP-0002.json` (hardwood) are assembled by the same code from the same registry.
`GET /api/enterprise/switch` returns both rows, the shared capability set and the
industry-specific remainder, with a proof block that states the code change count is
zero.

**FDE readiness.** `config/enterprise/fde-checklist.json` holds twelve items across
four phases with owner, evidence, status and a blocking flag. The report recomputes
done, open and blocking items per profile, so a deployment cannot claim go-live while
a blocking item is open. `docs/fde-handbook.md` is the method behind the checklist.

**Multilingual site.** `config/growth/site.json` declares pages, sections, languages
and the SEO bounds; `config/growth/copy.json` holds every string in every language.
The generator emits one `growth_site` page record per page and language with its
canonical path, reciprocal hreflang alternates, keywords and JSON-LD, writes the
HTML, the sitemap and the robots file, and validates the whole record against the
contract before anything is written.

**SEO audit.** The auditor checks title and description length, a single H1,
canonical consistency, reciprocal hreflang, parseable structured data and keyword
density, then scores from 10000 bp with fixed penalties and marks pages reviewed only
above the threshold. A negative audit (one description stripped) is committed in the
report to prove detection.

**Inquiry to CRM.** An inquiry from the site becomes a lead with a deterministic
score (base plus weighted factors), an SLA deadline, an owner from the routing table,
follow-up tasks from the cadence templates and, once quoted, a quote draft. Each step
appends a CRM event and the stage is a function of those events, which `INV-LEAD-01`
checks. `docs/growth-playbook.md` is the operating runbook.

## 9. Milestone 4 mechanics

**Canon.** `config/ip/characters.json` holds the world rules and the two guardians
with element, archetype, personality axes, silhouette, palette, motifs, taboos,
props, voice, relationship, three arc beats, licence-safe sourcing, authenticity
label and a content review reference. `INV-CHAR-01` refuses a shared element, a
repeated signature line, a reused review or an exclusive heritage claim.

**Visual library.** `config/ip/visuals.json` declares the variants; the builder
emits layered vector recipes with palette tokens resolved per character. Each asset
stores a SHA-256 over its identity and recipe, so verification proves a build is
unchanged without an image file. `INV-ASSET-01` refuses a checksum that does not
recompute, an unlabelled AI-assisted asset, a licensed asset without a reference and
malformed layer geometry.

**Short drama.** Durations live in the beats; scene durations, storyboard frame
durations, edit decision list timecodes and subtitle windows are all derived from
them. `INV-DRAMA-01` refuses a beat sum that misses the scene duration, an EDL that
is not continuous or does not cover every frame once, a frame that cites an unknown
scene or an asset outside its scene, and overlapping subtitles.

**Sample reel.** `ip/reel.py` renders one self-contained HTML document: the frame
SVGs inline, a CSS timeline computed from the EDL and a subtitle band, with the
authenticity label and the review reference. No codec, no external request, no
binary asset, byte identical across builds.

**Licensing.** `config/ip/licensing.json` holds the usage block, the quality
specification, the signed document set and four merchandise specifications. Document
checksums cover their identity, the invariant `INV-IP-02` refuses a derivative
category without a signed document or a signed document without both parties, and
`INV-MERCH-01` refuses a specification without the authenticity label or a quality
plan. Every artefact cites a `content_review` record; `INV-CONTENT-01` refuses an
approval that hides a failed item and requires the AIGC disclosure block.

## 10. Model integration boundary

Real model calls arrive through an **optional sidecar process**, not through the
repository. `model-sidecar/` sits next to the delivery root, owns the API key, calls
an OpenAI-compatible image endpoint, downloads the result immediately (upstream URLs
expire in 24 hours), records provenance and replays cached results.

```
browser (8412) --fetch--> sidecar (8413) --https--> Qwen / DashScope
                              |
                              +--> cache/<request-hash>.json + image bytes
```

Why it is not inside `c2m_craft/`: two guarantees would break. The package must
contain no network client (verification scans the AST for one), and the demo must
stay byte-for-byte reproducible. The sidecar has three modes - `stub` for wiring and
tests, `live` when a key is present, `replay` when it is not - and the UI degrades to
a clear message when the process is absent.

The request hash covers the request kind, model, prompt, options and cache origin
(stub versus live), so an identical request is served from cache, a stub placeholder
can never satisfy a live request, and `fresh=true` forces a new call. Every record
carries the model id, the prompt, the digest of the output, the mode and the
`AI-generated` label; the UI renders that label next to the picture and the copy.
`GET /report` renders the cache as a compliance table, with stub rows marked as
such. The API key never leaves the sidecar process and is never served by an
endpoint.

## 11. Extension points

| Extension | Where | What changes |
|---|---|---|
| New industry | `config/industries/<id>.json`, `config/craft_rules/<id>.json`, `config/equipment/*.json`, an enterprise profile | data only; no code |
| New rule | rule file (validated by `config/craft_rules/rule_file.schema.json`) | data only |
| New workshop | one file under `config/equipment/` | data only |
| New service component | `config/enterprise/components.json` plus its configuration path | data only; the registry validates it |
| New market or language | `config/growth/site.json`, `config/growth/copy.json`, the profile growth block | data only |
| New derivative category | `config/ip/licensing.json`, a merch spec, the licence usage block | data only; coverage invariant enforces it |
| New drama episode | `config/ip/drama.json` with a shot plan per beat | data only; timecodes recompute |
| Real image model | implement `ConceptModelAdapter` and register it in `adapters.adapter_for` | one module |
| New payment or settlement policy | `config/commerce/pricing.json` | data only |

## 12. Deployment

- Local: `python -m c2m_craft serve` (Python 3.11+, standard library only).
- Windows convenience: `start.ps1` (PowerShell 7).
- POSIX convenience: `sh start.sh`.
- Demo/CI: `python -m c2m_craft demo`, `python tests/test_runner.py`,
  `python verify/run_verification.py`.

No database, no container requirement, no external service. The generated site
lives under `out/site/` and is served read-only; nothing writes to `static/`. A
container image and database-backed state are deferred until the production
hardening step (see `DELIVERY.md` section 10), when the enterprise layer brings real
operational dependencies.

## 13. Security and privacy posture

- Loopback binding only, no authentication in the prototype. Every populated
  enterprise profile declares `auth_gate: true` as a go-live condition, and the FDE
  checklist keeps it blocking, so public exposure without the gate cannot be
  declared ready.
- All workshop, licence, customer, enterprise, lead and cultural IP data are
  synthetic and marked as such in `config/site.json`.
- No image ever leaves the browser: the reference image is quantised to six colours
  client-side and only the hex list is posted.
- Cultural heritage constraints are enforced in contracts, not in prose: a
  traditional prototype cannot be marked exclusive, assets that reference religious
  sites cannot be licensed exclusively, and the character bible and IP licence
  invariants keep every heritage citation non-exclusive.
- The model API key lives outside the delivery package, in the sidecar process only.

## 14. Non-goals in this milestone

The offline demo does not call a model: live rendering needs the sidecar process and
an API key. Image-to-image style transfer, model fine-tuning, the six-industry
service runtime beyond the two worked industries, an image embedding for library
search, a finite-capacity optimiser and any offline space construction remain outside
this delivery. Two honest limits stand: descriptor search is deterministic metadata
rather than an image embedding, and the capacity model plans per workshop day, not
per machine or operator shift. The sample reel is an animatic rendered from data, not
an encoded video file.
