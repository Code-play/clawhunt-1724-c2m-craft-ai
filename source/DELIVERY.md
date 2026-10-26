# Delivery note - milestones M1 to M4

| | |
|---|---|
| Brief | Regional Specialty Industry AI Empowerment, Phase 1 (#1724) |
| Milestones | M1 - architecture and data contracts, manufacturability rule modelling plan, clickable workstation prototype. M2 - participatory customisation, limited editions and collector archive, capacity calendar and delivery promises, descriptor search, per-asset royalties, quality records. M3 - componentised enterprise AI service layer for two industries, FDE handbook and a populated profile, multilingual site with SEO and the inquiry-to-CRM loop. M4 - dual-guardian cultural IP bible, visual asset library, short drama with one sample reel, licensing templates and merchandise specifications |
| Logical as-of | 2026-10-23T00:00:00Z (`config/site.json`) |
| Runtime | Python 3.11+ standard library, offline, no build step |
| Entry points | `python -m c2m_craft demo` / `serve` / `selftest` / `requirements` |

## 1. Milestone mapping

| Brief line | Where it is delivered |
|---|---|
| architecture and data contracts | `contracts/` (23 schemas + registry 2.0.0), `c2m_craft/core/`, `ARCHITECTURE.md`, `docs/data-contracts.md`, six ADRs |
| manufacturability rule modelling plan | `config/craft_rules/`, `config/equipment/`, `c2m_craft/craft/`, `docs/rule-modeling-plan.md`, `docs/rule-authoring-form.md` |
| clickable workstation prototype | `static/`, `c2m_craft/web/server.py`, `python -m c2m_craft serve` |
| consumer participatory customisation | `config/commerce/customization.json`, `c2m_craft/commerce/customization.py`, `contracts/customization-choice.schema.json`, `out/customization_report.json` |
| limited edition and collector archive | `c2m_craft/commerce/editions.py`, `contracts/edition.schema.json`, `contracts/collector-record.schema.json`, `out/edition_archive.json` |
| capacity calendar and delivery promises | `config/commerce/capacity.json`, `c2m_craft/commerce/capacity.py`, `contracts/production-schedule.schema.json`, `out/capacity_plan.json` |
| quality standards and records | `config/commerce/quality.json`, `c2m_craft/commerce/quality.py`, `contracts/qc-record.schema.json`, `out/quality_report.json` |
| real model integration (A.1 creative capability) | `model-sidecar/sidecar.py` next to the delivery root, `static/app.js` (AI render and AI copy buttons), `config/model-keys.env` (local only), `model-sidecar/selftest.py` |
| enterprise service layer with two industry components | `config/enterprise/components.json`, `config/enterprise/profiles/`, `c2m_craft/enterprise/`, `out/enterprise_report.json` |
| FDE handbook and a populated profile | `docs/fde-handbook.md`, `config/enterprise/fde-checklist.json`, `config/enterprise/profiles/EP-0001.json` |
| multilingual site, SEO, inquiry to CRM | `config/growth/`, `c2m_craft/enterprise/growth/`, `out/growth_report.json`, `out/site/`, `docs/growth-playbook.md` |
| dual guardian character settings | `config/ip/characters.json`, `contracts/character-bible.schema.json`, `out/character_bible.json`, `docs/character-bible.md` |
| character design manual and visual asset library | `config/ip/visuals.json`, `c2m_craft/ip/visuals.py`, `out/ip_asset_library.json` |
| short drama workflow and one sample reel | `config/ip/drama.json`, `c2m_craft/ip/drama.py`, `c2m_craft/ip/reel.py`, `out/short_drama_package.json`, `out/sample_reel.html`, `docs/short-drama-workflow.md` |
| licensing templates and merchandise specifications | `config/ip/licensing.json`, `c2m_craft/ip/licensing.py`, `contracts/ip-license.schema.json`, `contracts/merch-spec.schema.json`, `out/licensing_pack.json`, `docs/licensing-templates.md` |
| content review and authenticity labelling | `contracts/content-review.schema.json`, `c2m_craft/ip/reviews.py`, `out/content_review.json` |
| each milestone has a runnable artifact and verification records | `out/` (33 generated artifacts), `tests/test_runner.py`, `verify/run_verification.py`, `verify/records/` |

## 2. Run on a clean machine

Prerequisite: Python 3.11 or newer. Nothing else.

```
python -m c2m_craft demo
python tests/test_runner.py
python verify/run_verification.py
python -m c2m_craft serve
```

Expected:

| Command | Last line / result |
|---|---|
| `demo` | `[demo] artifacts written: 33 -> .../out` and `out/hash_manifest.json` lists 32 hashes |
| `tests/test_runner.py` | `236/236 tests passed` with no `FAIL` lines |
| `verify/run_verification.py` | `289/289 assertions passed`, records written to `verify/records/` |
| `selftest` | `13/13` checks pass, `ok` true |
| `serve` | `[serve] C2M craft prototype on http://127.0.0.1:8412 (loopback only)` |

Then open `http://127.0.0.1:8412`: seven tabs, all clickable with the seeded
scenario data. A five-minute path: generate concepts in tab 1 and render an AI
effect shot, assess a candidate, customise a concept and create the order in tab 3,
advance it to settlement, read the capacity board and quality records in tab 4, then
switch industry in the Enterprise tab, open the generated English, Chinese and
German pages, submit an inquiry and move the lead through the CRM, and finish in the
IP studio with the character bible, the asset library and the sample reel.

Windows: `.\start.ps1`. macOS/Linux: `sh start.sh`.

## 3. Acceptance criteria coverage

The brief lists eleven acceptance criteria. All are covered now.

| AC | Criterion | Status | Evidence |
|---|---|---|---|
| 0 | Deliverables first: runnable repository plus one-command launch, no document-only proposal | covered | `README.md`, `start.ps1`, `start.sh`, this note |
| 1 | Four main workflows navigable end to end from a clean start | covered | seven tabs, 43 API routes, browser walkthrough in section 2 |
| 2 | Pattern ingestion validates licensing source and usage scope, with positive and negative cases | covered | `contracts/pattern-asset.schema.json` (4 invariants), six rejection payloads in `samples/library/rejected.json`, gate in `c2m_craft/library/assets.py` |
| 3 | Ten concept inputs including three non-manufacturable counterexamples, agreeing with the documented rules and reproducible | covered | `samples/concepts/` (10 inputs, 3 counterexamples), `samples/concepts/expected.json`, 32 rules in `docs/rule-modeling-plan.md` |
| 4 | One custom order completes order, work order, dispatch, QC, shipment, revenue sharing, with refund and dispute paths | covered | `c2m_craft/commerce/`, seven scenarios in `out/order_trace.jsonl`, `out/settlement_report.md`, `out/quality_report.json` |
| 5 | Enterprise service layer with two industry components, industry switch by configuration, FDE manual, populated profile | covered | `c2m_craft/enterprise/`, `config/enterprise/`, ten components and two ready profiles in `out/enterprise_report.json`, `docs/fde-handbook.md` |
| 6 | Multilingual site, SEO metadata, inquiry-to-CRM loop, one end-to-end test each | covered | `out/growth_report.json` (nine pages, audit 10000 bp, negative audit 8500 bp, three leads), `out/site/`, verification group J |
| 7 | IP pipeline with dual characters, asset library, one short-drama workflow and sample clip, licensing templates and merchandise specifications | covered | `out/character_bible.json`, `out/ip_asset_library.json` (22 assets), `out/short_drama_package.json` (5 scenes, 10 frames, 67 s), `out/sample_reel.html`, `out/licensing_pack.json` (5 documents, 4 merchandise specs), `docs/character-bible.md`, `docs/short-drama-workflow.md`, `docs/licensing-templates.md` |
| 8 | Unit tests for licensing validation, manufacturability, order state machine and revenue sharing, passing with one command | covered | `tests/test_runner.py` groups for each of the four areas, extended with the M2, M3 and M4 areas |
| 9 | Documentation mentions only commands and interfaces that exist | covered | `verify/run_verification.py` group F compares `docs/api.md` with `/api/spec` and runs every command named in the README |
| 10 | Synthetic or anonymised samples, no real confidential data, no exclusive claim on traditional or religious heritage | covered | `config/site.json` provenance flags, synthetic samples, `INV-LIC-03`, `INV-IP-01` and `INV-CHAR-01` plus rejection cases |

Criterion 8 is the only one the brief numbers as a test requirement: the suite runs
the four named areas plus the enterprise and growth loop and the IP pipeline
timecode and checksum invariants in one command.

## 4. Requirement decomposition

`docs/requirements.json` is the machine-readable decomposition of the brief: 54
items across modules A (craft co-creation and C2M), B (enterprise service layer), C
(IP pipeline), D (optional competition package), E (delivery hard requirements), F
(exclusions), G (client-provided inputs), H (quote structure), I (milestones) and J
(the acceptance criteria). Each item carries a milestone, a status, the contracts and
artifacts that implement it, the verification group that proves it and the
acceptance criteria it serves.

- 39 items are implemented and covered, 1 is partial (multimodal search: descriptor
  based, not an image embedding), 9 are planned (five client-provided inputs and four
  commercial quote items) and 5 are explicitly excluded by the brief. Every M1, M2,
  M3 and M4 item is implemented.
- `python -m c2m_craft requirements check` fails if an item loses its artifact, if a
  contract or acceptance id stops resolving, or if any acceptance criterion is left
  unreferenced.
- `docs/requirements-matrix.md` and the Chinese mirror are generated from that file;
  the quote column is intentionally empty, for the commercial owner to fill.

## 5. Evidence inventory

Generated by `python -m c2m_craft demo` into `out/`:

| Artifact | Content |
|---|---|
| `contract_report.json` | 42 positive records accepted, 31 negative records rejected with the expected class and path |
| `rules_report.json` | lint result, 32-rule catalogue, fact coverage per industry |
| `workstation_catalog.json` | two briefs, eight generated concepts, three series SKUs, adapter limitation |
| `library_snapshot.json` | eight licenced assets with licence state and search descriptors, four searches, six rejection cases, one accepted ingest |
| `assessment_results.json` | twenty assessments, agreement 20/20, two review decisions, three counterexamples |
| `assessment_matrix.md` | the matrix a reviewer reads |
| `capacity_plan.json` | four workshop schedules, committed slots, daily utilisation and the promise model |
| `customization_report.json` | option catalogue, a preview with derived concept and quote, an applied choice on a settled order |
| `edition_archive.json` | the edition, its issued numbers, the certificate and the transfer chain |
| `quality_report.json` | defect taxonomy, sampling plans, three inspections with measurements |
| `order_trace.jsonl` | every ledger event across seven order scenarios, hash chained |
| `settlement_report.md` | payout lines, royalty lines, delivery promises, reconciliation, refund and dispute cases |
| `coverage_report.md` | requirement coverage by milestone and acceptance criterion |
| `enterprise_report.json` | component registry, two assembled profiles, industry switch, FDE readiness and blocking items |
| `growth_report.json` | nine generated pages, SEO audit, negative audit, three inquiry-to-CRM traces and the pipeline board |
| `character_bible.json` | the two guardians, world rules, heritage references and usage plan |
| `ip_asset_library.json` | 22 vector assets with checksums and review state |
| `short_drama_package.json` | five scenes, ten beats, storyboard, edit decision list, subtitles and review |
| `sample_reel.html` | the self-contained 67 second animatic |
| `licensing_pack.json` | signed document set, four merchandise specifications, summary counts |
| `content_review.json` | nine review records with the authenticity and heritage blocks |
| `site/` | nine generated pages, `sitemap.xml` and `robots.txt` |
| `hash_manifest.json` | SHA-256 of the other 32 artifacts |

Written by `verify/run_verification.py` into `verify/records/`:

- `tests_output.txt` - the test run, unedited
- `verification_output.txt` - every assertion with its group and result
- `commands.md` - the commands run, their exit codes and expected last lines
- `ui_smoke.log` - the HTTP route walkthrough on an ephemeral port
- `artifact_hashes.txt` - hashes recorded by the verification run
- `model_calls.md` - the model call compliance record (see section 5.1)

### Model integration status

| Path | Wired | Offline proof | Live proof |
|---|---|---|---|
| image render (`/generate` to `/files/<name>`) | `static/app.js` button, `model-sidecar/sidecar.py` | 71 sidecar checks, browser run on a 1024x1024 placeholder, UI shows the mode chip | **verified live** 2026-10-24: real qwen-image-3.0 render through the UI, `live_check.py` 15/15 |
| bilingual copy (`/generate_text`) | same button set, chat completions path | same 71 checks plus fake-upstream HTTP coverage | **verified live** 2026-10-24: live qwen3.7-flash bilingual copy through the UI |
| compliance record (`/report`, `--report`) | `verify/records/model_calls.md` | earlier rows were `stub` and said so | current record: `live=4, stub=2`, every row labelled `AI-generated` |

The mode chip on the workstation shows `stub` / `replay` / `live` so nobody can
mistake a placeholder run for a real model call.

## 6. Inventory

| Item | Count |
|---|---|
| Data contracts | 23 |
| Cross-field invariants | 25 |
| Positive contract samples (plus 8 assets and 10 concepts) | 24 (42 total) |
| Negative contract samples | 31 |
| Industries | 2 (jewelry, hardwood) |
| Fact declarations | 33 |
| Craft rules | 32 |
| Workshop capability envelopes | 4 |
| Capability checks | 24 |
| Customisation groups / options | 7 / 22 |
| Concept inputs (3 counterexamples) | 10 |
| Assessment verdicts compared to the expectation table | 20 |
| Order scenarios | 7 plus one refused order |
| Enterprise components | 10 |
| Enterprise profiles | 2 (one per industry) |
| FDE checklist items | 12 (9 done, 2 blocking open) |
| Growth site pages | 9 (three languages) |
| HTTP routes | 43 API routes plus 3 static and 5 generated page routes |
| Tests | 236 |
| Verification assertions | 289 |
| Visual assets | 22 |
| Short drama scenes / beats / frames / seconds | 5 / 10 / 10 / 67 |
| Licence documents / merchandise specs / content reviews | 5 / 4 / 9 |
| Model sidecar offline checks | 71 |
| Live model checks (live_check.py) | 15 |

## 7. Environment

- Python 3.11 or newer; developed and verified on CPython 3.13.9.
- No third-party package is imported at runtime or in the tests. `selftest` proves
  this by AST scan against `sys.stdlib_module_names`.
- No network access is used or required. The only socket is the loopback HTTP
  server, bound to 127.0.0.1, and it is the prototype itself.
- Working state lives under `var/`, which is gitignored and safe to delete; deleting
  it only resets the interactive session, never the committed fixtures.

## 8. Data provenance and compliance

- All workshop, licence, customer, enterprise, lead and cultural IP data is
  synthetic or anonymised. `config/site.json` records
  `data_provenance: synthetic_baseline` and `client_materials_received: false`.
- Every rule carries an evidence block. In M1 they are `synthetic_baseline` with
  `client_confirmation_required: true` and `reviewed_by: pending`, and the lint
  reports those items as informational findings so the gap is visible.
- No traditional cultural prototype or religious site name is claimed as exclusive:
  the constraint is enforced by invariants on the pattern asset, IP licence and
  character bible contracts and demonstrated by rejection cases.
- Reference images never leave the browser: only an extracted six-colour palette is
  posted to the server.
- Every AI-generated artefact (render, copy, character, visual asset, drama, licence
  and merchandise review) carries an explicit `AI-generated` label in its record and
  in the UI; the offline demo calls no model.
- The M2 customisation catalogue, the M3 component and CRM policy and the M4 IP canon
  are configuration files: replacing them is a data edit, not a code change.

## 9. Assumptions and known limitations

1. Rule semantics are plausible industry practice drafted for the prototype, not the
   client's confirmed rules. Replacing them is a data edit plus
   `python -m c2m_craft rules lint`.
2. The creative workstation is an offline vocabulary adapter by default. Real image
   rendering and bilingual copy go through the optional model sidecar, verified live
   against Qwen on 2026-10-24; the offline demo never calls it. Style is expressed
   through concept parameters plus a text prompt; image-to-image transfer from a
   reference photo is not exposed yet.
3. Pricing, deposits, revenue shares, royalty rates and quote amounts are
   configuration values chosen to demonstrate the arithmetic, not commercial terms.
4. The order book and the CRM are single-process in-memory stores persisted to
   `var/`; a database is out of scope while the deliverable is a clickable prototype.
5. Authentication is intentionally absent because the prototype binds loopback only;
   any network exposure must add the deployment auth gate first. Every populated
   profile already declares `auth_gate: true` as a go-live condition.
6. Search over the licensing library is descriptor based (motif family, symmetry,
   density, line weight, edge complexity) and fully deterministic; a visual embedding
   model is deliberately out of scope while the build is offline.
7. The capacity model plans per workshop day, not per machine or per operator shift;
   it is a promise model, not a finite-capacity optimiser.
8. The sample reel is a self-contained HTML animatic generated from the drama
   package, not an encoded video: it needs no codec and commits no binary asset. A
   production renderer can consume the same edit decision list and subtitles.
9. A container image is still deferred; the enterprise layer brought configuration,
   not new dependencies.

## 10. What remains

- Client-provided inputs G1 to G5: interview material for the six industries, the
  verbal craft rules to proofread, the real pattern licence list, craft constraint
  samples from one jewelry and one woodworking enterprise, and the named acceptance
  reviewer.
- Commercial inputs H1 to H4: the per-module and per-milestone quote, stack and
  timeline commitment, and the model and compute cost basis.
- Two blocking FDE items before any go-live: the operator and administrator training
  tiers, and the backup and restore drill. Both are recorded in
  `out/enterprise_report.json` with owner and evidence.
- Production hardening, in the order the report implies: database-backed state, the
  deployment auth gate, a video renderer over the drama package, and image-to-image
  style transfer.

## 11. Handover checklist

- [ ] `python -m c2m_craft selftest` reports 13/13 checks
- [ ] `python -m c2m_craft demo` regenerates `out/` and the manifest is unchanged
- [ ] `python tests/test_runner.py` ends with `236/236 tests passed`
- [ ] `python verify/run_verification.py` ends with `289/289 assertions passed` and writes records
- [ ] `python -m c2m_craft serve` opens the seven tabs and the seeded walkthrough completes
- [ ] the generated pages open at `/en`, `/zh`, `/de` and the reel at `/reel`
- [ ] `docs/requirements-matrix.md` is regenerated after any scope change
- [ ] client craft rules replace the synthetic baseline, and `rules lint` stays green
- [ ] the customisation catalogue, the quality taxonomy and the M4 IP canon are
      reviewed against client practice before production use
- [ ] the two blocking FDE items are closed and the readiness report turns `go_live_ready`
