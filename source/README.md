# C2M craft co-creation prototype (M1 to M4)

A runnable Phase 1 foundation for the regional specialty industry brief: 23 data
contracts, a manufacturability rule engine driven entirely by configuration, a
clickable prototype where a design brief becomes a concept, the concept gets a
verdict, and the verdict gates participatory customisation, a pre-sale order, a
craft work order, quality control, shipment and a revenue-sharing settlement with
per-asset royalties. On top of that spine, M3 adds the componentised enterprise
service layer with the growth stack (multilingual site, SEO audit, inquiry to CRM
loop) and M4 adds the cultural IP pipeline (two guardians, visual asset library,
short drama with a sample reel, licensing pack and content reviews).

- Python 3.11+ standard library only. No dependency install, no build step, no
  database, no network call.
- Deterministic: two runs of the demo produce byte-identical artifacts.
- Honest about scope: the concept generator is an offline curated vocabulary and
  the UI says so; a real model is reached only through the optional sidecar.

## Quick start

Three commands, from this directory:

```
python -m c2m_craft demo
python tests/test_runner.py
python verify/run_verification.py
```

Then open the prototype:

```
python -m c2m_craft serve
```

It prints `http://127.0.0.1:8412` and binds loopback only. On Windows the
convenience launcher is `.\start.ps1`; on macOS or Linux use `sh start.sh`.

Environment check first if you like:

```
python -m c2m_craft selftest
```

## What the prototype shows

Seven tabs, eight workflows, all backed by the real code rather than a mock:

| Tab | What you can do |
|---|---|
| Creative workstation | type a brief (or drop a reference image for a palette), generate four candidates, expand one into a three-SKU series, send a candidate to the manufacturability assessment, and render an AI effect shot through the optional model sidecar |
| Pattern library | search by text, tag, palette or industry, or narrow by motif family, symmetry and line weight; inspect licence source, scope and window; submit a new asset and watch a missing licensing field get rejected with its field path |
| Pre-sale orders | create an order, customise a concept with priced options and preview the verdict before ordering, open a limited edition and issue a numbered certificate, advance it through every state, request, approve and execute a refund, open a dispute that cites its quality records and resolve it |
| Factory dispatch | read the capacity board and its promises, inspect the work order: bill of materials, process route with equipment, craft constraints, quality checkpoints and promised delivery, then read the quality records with their defect taxonomy |
| Contracts and rules | the contract registry with its invariants, the rule catalogue with an explain view, and the artisan review queue where a verdict can be confirmed or overridden |
| Enterprise | switch industry between two populated profiles on one component registry, read the assembly plan and its blockers, read the FDE go-live readiness, open the generated pages in English, Chinese and German, submit an inquiry and move the lead through the CRM pipeline |
| IP studio | read the two-guardian character bible, browse 22 vector visual assets, walk the short drama storyboard and edit decision list, open the sample reel, and read the licence document set, the four merchandise specifications and the content reviews |

Every preview is drawn procedurally from palettes, motifs and vector recipes, so
the repository carries no image assets.

## Commands

| Command | Purpose |
|---|---|
| `python -m c2m_craft demo` | regenerate every artifact under `out/` |
| `python -m c2m_craft serve` | start the prototype on 127.0.0.1:8412 |
| `python -m c2m_craft selftest` | check the offline and determinism guarantees |
| `python -m c2m_craft spec` | print the runtime specification as JSON |
| `python -m c2m_craft contracts list` | list the registered contracts |
| `python -m c2m_craft contracts verify` | validate the positive and negative sample suite |
| `python -m c2m_craft rules lint` | validate rule files, capability checks and coverage |
| `python -m c2m_craft rules explain --rule-id JW-CAST-001` | explain one rule |
| `python -m c2m_craft rules coverage` | facts and rule counts per industry |
| `python -m c2m_craft assess --concept DC-0002 --workshop WS-JW-A` | run one assessment from the CLI |
| `python -m c2m_craft library search --q interlace` | search the library |
| `python -m c2m_craft library ingest --input <file.json>` | ingest an asset with the licensing gate |
| `python -m c2m_craft order create --concept DC-0001` | create an order |
| `python -m c2m_craft order advance --id ORD-0001 --event payment_received --actor buyer` | advance it |
| `python -m c2m_craft order show --id ORD-0001` | show order, events and settlement |
| `python -m c2m_craft customization catalog --industry jewelry` | list the option catalogue with price deltas and conflicts |
| `python -m c2m_craft customization preview --concept DC-0001 --select alloy:alloy_22k` | resolve options, derive the concept and quote it |
| `python -m c2m_craft capacity board` | show the four workshop schedules |
| `python -m c2m_craft capacity quote --concept DC-0001` | ask for a delivery promise and its alternatives |
| `python -m c2m_craft edition create --concept DC-0001 --size 5` | open a limited edition |
| `python -m c2m_craft edition issue --edition ED-0001 --order ORD-0001 --owner OWNER-C1` | issue the next numbered certificate |
| `python -m c2m_craft edition transfer --record COL-0001 --owner OWNER-C2 --owner-name Collector Two` | append an ownership transfer |
| `python -m c2m_craft quality record --order ORD-0001 --checkpoint QC-01 --verdict pass` | record an inspection |
| `python ../model-sidecar/sidecar.py --port 8413 --stub` | start the model sidecar in placeholder mode (no key needed) |
| `python ../model-sidecar/sidecar.py --port 8413` | start the model sidecar in live mode (reads the local key file) |
| `python ../model-sidecar/selftest.py` | run the sidecar's offline selftest |
| `python ../model-sidecar/sidecar.py --report cache/compliance_report.md` | export the model call record as markdown |
| `python ../model-sidecar/live_check.py` | verify the live endpoint end to end (needs a key) |
| `python -m c2m_craft requirements check` | verify the requirement matrix is closed |
| `python -m c2m_craft requirements render` | regenerate the bilingual matrix |
| `python tests/test_runner.py` | run the test suite (last line `N/N tests passed`) |
| `python verify/run_verification.py` | run the acceptance assertions and write records |
| `python scripts/gen_m3_m4_samples.py` | regenerate the M3 and M4 contract samples |

Exit codes: `0` ok, `2` rejected (a contract or state-machine refusal, which is a
normal business result), `3` usage or environment error.

## Repository layout

```
contracts/        23 JSON Schema contracts plus the registry
config/           industries, craft rules, workshop capability, creative vocabulary,
                  commerce policy, enterprise component registry and profiles,
                  growth site copy and CRM policy, cultural IP canon and licensing,
                  UI strings
samples/          ten concept inputs, the expected verdict table, licensed assets,
                  rejection payloads, contract positive and negative suites
c2m_craft/        the implementation: core, craft, creative, library, commerce,
                  enterprise (service layer and growth), ip (cultural IP), web
static/           one HTML page, one stylesheet, one script; no build step
tests/            one command, self-counting test runner
verify/           acceptance assertions and the records they write
docs/             architecture decisions, data contracts, API, rule modelling plan,
                  FDE handbook, growth playbook, character bible, drama workflow,
                  licensing templates, competition pack, requirement matrix
scripts/          deterministic fixture generators
out/              artifacts generated by the demo, including the generated site
var/              working state (gitignored, safe to delete)
```

## Milestone 3: enterprise service layer and growth stack

The service layer is assembled from ten reusable components declared in
`config/enterprise/components.json`. Each component declares its industries,
capabilities, contracts, dependencies and data boundary. An enterprise profile
(`config/enterprise/profiles/EP-0001.json` for jewellery, `EP-0002.json` for
hardwood) selects components; the runtime resolves each selection, checks the
industry, the configuration path, the contracts and the dependencies, and reports
exactly what would block go-live. Comparing the two profiles on one registry is
the proof that switching industry is a configuration edit, not a fork.

The growth stack generates nine pages in three languages from data
(`config/growth/site.json` plus `config/growth/copy.json`), audits them against the
declared SEO bounds (title and description length, one H1, canonical, reciprocal
hreflang, parseable structured data) and scores the site. An inquiry submitted from
a page becomes a lead with deterministic scoring, an SLA clock, an owner, follow-up
tasks and a quote draft; the pipeline stages are a function of the CRM events.
`docs/fde-handbook.md` and `docs/growth-playbook.md` document the on-site method
and the runbook.

## Milestone 4: cultural IP pipeline

`config/ip/characters.json` holds the canon of two guardians, A-Mu (wood) and
A-Huo (fire), with world rules, motifs, taboos, props, voice and a three-beat arc.
`config/ip/visuals.json` turns that canon into 22 deterministically drawn assets
(turnarounds, expressions, props, costume, scenes), each with a checksum that
recomputes from its drawing recipe. `config/ip/drama.json` holds the short drama
"Waking the Kiln": five scenes, ten beats, a storyboard of ten timed frames, an
edit decision list with continuous timecodes produced from the beat durations, and
a subtitle track. `out/sample_reel.html` is a self-contained animatic rendered from
that package. `config/ip/licensing.json` holds the signed document set, four
merchandise specifications with quality plans, and nine content reviews that carry
the AI-assisted authenticity label. `docs/character-bible.md`,
`docs/short-drama-workflow.md` and `docs/licensing-templates.md` document the
pipeline; `docs/competition-ops-pack.md` is the optional competition package.

## Determinism and the offline stub

Everything is reproducible on purpose. The clock is a configured logical instant
(`config/site.json -> as_of`), concept generation is hash-seeded, visual assets are
vector recipes rather than images, JSON is written canonically, and
`out/hash_manifest.json` records the SHA-256 of the other 32 artifacts so two runs
can be compared byte for byte.

The creative workstation is an offline vocabulary adapter: it assembles concepts
from curated motifs, palettes, styles and form templates. It is not a diffusion
model. `c2m_craft/creative/adapters.py` declares the `ConceptModelAdapter`
boundary and an unimplemented `ExternalModelAdapter` so a later milestone can add a
real model without changing call sites. Library search is likewise deterministic:
motif family, symmetry, density, line weight and edge complexity, not an image
embedding.

## Model integration (optional live mode)

The AI effect shot and the bilingual product copy on a concept card are served by
a separate process, not by the repository: `model-sidecar/` sits next to the
delivery root and owns the model API key, calls the image and text models,
downloads the result and records provenance.
Keeping it outside `c2m_craft/` is deliberate: the package must stay free of
network clients so `python -m c2m_craft demo` remains byte-for-byte reproducible,
and the prototype keeps working when the sidecar is offline.

| Mode | When | Behaviour |
|---|---|---|
| `stub` | `sidecar.py --stub` | deterministic SVG placeholder, never calls a model |
| `live` | a key is present | calls the model; cache-first unless `fresh=true` |
| `replay` | no key | cache only, a miss returns 409 |

The key lives in `config/model-keys.env` (outside the delivery repository). The
sidecar asks for `watermark=false`, stores every image with its SHA-256, writes the
bilingual copy through the chat completions endpoint (`/generate_text`) and labels
every result `AI-generated`; the UI shows that label next to the picture and the
copy, and `GET /report` renders the call record as a compliance table.
See `model-sidecar/README.md` for endpoints, cache layout and compliance notes.

## Data provenance

All workshop, licence, customer, enterprise, lead and cultural IP data in this
repository is synthetic or anonymised. `config/site.json` records
`data_provenance: synthetic_baseline` and `client_materials_received: false`. Rule
evidence is marked `client_confirmation_required: true` and the lint reports those
32 items, so the gap between this baseline and the client's interviewed rules is
visible rather than hidden. Heritage references in the IP bible and licence set are
cited as shared regional techniques and can never be claimed exclusively; the
invariants enforce that and two rejection samples prove it.

## Verification

```
python tests/test_runner.py           # unit and integration tests
python verify/run_verification.py     # acceptance assertions, writes verify/records/
```

The verification script re-derives hashes, payout sums and ledger links itself
instead of trusting the library's verdict, recomputes every visual asset checksum,
re-derives the drama timecodes and the SEO audit, compares the API documentation
against the live route table, runs the demo twice, and checks that no wall clock or
HTTP client exists in the package. Groups A to I cover M1 and M2, group J covers
the enterprise service layer and the growth stack, and group K covers the cultural
IP pipeline. See `DELIVERY.md` for the acceptance-criteria mapping and
`docs/requirements-matrix.md` for the full requirement decomposition.
