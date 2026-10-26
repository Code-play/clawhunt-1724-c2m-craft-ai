# C2M craft co-creation platform - Milestones M1 to M4

Order: Regional Specialty Industry AI Empowerment, Phase 1 (brief #1724).
Delivered: M1 - architecture and data contracts, manufacturability rule modelling
plan, clickable workstation prototype. M2 - participatory customisation, limited
editions and collector archive, capacity calendar and delivery promises, descriptor
search, per-asset royalties, quality records. M3 - componentised enterprise AI
service layer for two industries, FDE handbook and one populated profile,
multilingual site with SEO and the inquiry-to-CRM loop. M4 - dual-guardian cultural
IP bible, visual asset library, short drama with one sample reel, licensing
templates and derived merchandise specifications.

仓库地址：
- 交付物仓库（含可浏览源码树 source/ 与打包文件）：https://github.com/Code-play/clawhunt-1724-c2m-craft-ai

打包下载：
- 打包下载（zip）：https://github.com/Code-play/clawhunt-1724-c2m-craft-ai/raw/main/1724-c2m-craft-ai.zip

## 1. What is in this delivery

Four milestones, one runnable repository, no proposal document and no mock:

1. **Architecture and data contracts.** 23 versioned JSON Schema contracts and a
   registry, 25 cross-field invariants, a schema-subset validator on the standard
   library, and 42 valid plus 31 deliberately broken sample records. Every broken
   record is a committed mutation with its expected error class and instance path.

2. **Manufacturability rule modelling.** Two industries (gold jewelry, hardwood
   furniture), 32 rules, 33 facts, four workshop capability envelopes, 24
   capability checks - all JSON data. A deterministic engine turns a concept plus a
   workshop into a verdict, its blocking rules, a bilingual reason and a
   machine-readable fix; a second tier routes flagged failures to a craftsperson
   whose override needs a written reason.

3. **A clickable prototype.** Seven tabs walking eight workflows end to end on the
   standard library, no build step, no external asset: workstation, pattern library,
   pre-sale orders, factory dispatch, contracts and rules, enterprise, IP studio.
   Real image and text generation is available through an optional sidecar,
   verified live against Qwen; the offline demo never calls a model.

4. **The order spine.** Seven order scenarios on one hash-chained ledger: order,
   customisation, work order, dispatch, QC, shipment, settlement, refund and
   dispute. Every amount reconciles in integer cents; every transition is an event.

5. **Milestone 2 depth.** Seven option groups and 22 priced options re-gated by the
   manufacturability engine; limited editions with certificate hashes and an
   append-only ownership chain; a working-day capacity calendar that books backwards
   and fills forwards; a defect taxonomy with sampling plans; per-asset royalty
   lines that reconcile with the IP share.

6. **Milestone 3: enterprise service layer and growth stack.** Ten reusable
   components with declared industries, capabilities, contracts, dependencies and
   data boundaries. Two populated enterprise profiles (jewelry, hardwood) are
   assembled by one code path from one registry, which proves industry switching is
   configuration. An FDE handbook and a twelve-item go-live checklist drive derived
   readiness (9/12 done, 7500 bp, pilot, two blocking items). The growth stack
   generates nine pages in English, Chinese and German from data, audits them
   against declared SEO bounds (score 10000 bp, zero issues) and proves detection
   with a negative audit, then closes the inquiry-to-CRM loop with deterministic
   scoring, SLA, owner routing, follow-up tasks, a quote draft and pipeline events.

7. **Milestone 4: cultural IP pipeline.** Two original guardians (A-Mu, wood; A-Huo,
   fire) with world rules, motifs, taboos, props, voice and a three-beat arc. 22
   visual assets (turnarounds, expressions, props, costume, scenes) described as
   vector recipes with checksums that recompute. A five-scene, ten-beat short drama
   whose storyboard, continuous edit decision list and twelve subtitle lines are
   computed from the beat durations, rendered as one self-contained 67-second
   animatic. A signed licence document set, four merchandise specifications with
   quality plans, nine content reviews with the AI-assisted authenticity block, and
   invariants that refuse uncovered derivative categories or a failed checklist
   item inside an approval.

## 2. Run it

```
python -m c2m_craft demo               # 33 artifacts under out/, byte-identical on rerun
python tests/test_runner.py            # 236 tests, last line N/N tests passed
python verify/run_verification.py      # 289 assertions in groups A-K, writes records
python -m c2m_craft serve              # http://127.0.0.1:8412, loopback only
```

The demo also writes the generated site under `out/site/`, served at `/en`, `/zh`,
`/de`, and the sample reel at `/reel`. `python -m c2m_craft selftest` checks the
offline and determinism guarantees; `python -m c2m_craft requirements check` proves
the requirement matrix is closed.

## 3. Architecture

```
c2m_craft/core        contracts, invariants, logical clock, money, ledger
c2m_craft/craft       facts, rule engine, lint, two-tier assessment
c2m_craft/creative    offline concept adapter, series expansion
c2m_craft/library     licensed assets, ingestion gate, descriptor search
c2m_craft/commerce    orders, dispatch, capacity, customisation, editions,
                      quality, settlement, persisted state
c2m_craft/enterprise   component registry, profile assembly, growth stack
c2m_craft/ip           character bible, visual recipes, drama, reel, licensing
c2m_craft/web          standard-library HTTP server and JSON API
```

Dependency rule: core imports nothing from the other packages; the rest depend only
on core, and web depends on the service container. Determinism is enforced, not
claimed: a configured logical clock instead of the wall clock, hash-seeded
generation, canonical JSON, vector recipes instead of images, and a hash manifest
over every artifact. The package contains no network client and no third-party
import; verification re-derives hashes, payout sums, ledger links, asset checksums,
drama timecodes and the SEO audit itself instead of trusting the library.

## 4. Evidence

`out/` holds 33 artifacts: contract, rule, workstation, library, assessment,
capacity, customisation, edition, quality, enterprise and growth reports, the
character bible, the visual asset library, the short drama package, the licensing
pack, the content review records, the self-contained sample reel, the generated
site, the coverage report and the hash manifest. `verify/records/` keeps the test
output, the assertion transcript, the commands, the HTTP smoke log and the artifact
hashes. `docs/` holds the data contracts, API guide, rule plan and authoring form,
the FDE handbook, the growth playbook, the character bible, the short drama
workflow, the licensing templates, the optional competition pack, four ADRs and the
bilingual requirement matrix.

Detail a reviewer can recompute: 10 components assembled into 2 ready profiles;
9 site pages in 3 languages with reciprocal hreflang and a 10000 bp audit; 3 CRM
leads ending won, contacted and lost with a 240000 cent quote; 22 vector assets
whose SHA-256 recipe checksums are recomputed by verification; 10 storyboard frames
whose timecodes chain from 00:00:00 to 00:01:07; 5 licence documents with 4 signed
and both parties present; 9 content reviews whose approvals carry no failed item.
A negative sample exists for every one of the 31 rejected contracts, and the eight
new M3/M4 negatives were generated from the running engine, not hand-written.

## 5. Acceptance coverage

All eleven criteria are covered: runnable repository (0), four end-to-end
workflows (1), licensing gate with negative cases (2), ten concept inputs including
three counterexamples agreeing 10/10 with the documented rules (3), one custom
order through every stage with refund and dispute (4), two-industry service layer
with configuration switching, FDE manual and populated profile (5), multilingual
site, SEO metadata and inquiry-to-CRM closed loop (6), dual-character manual, visual
asset library, one short drama with a sample clip, licensing templates and
merchandise specifications (7), the four required unit-test areas plus the rest
passing with one command (8), documentation mentioning only commands and
interfaces that exist (9), and synthetic or anonymised samples with no exclusive
claim on traditional or religious heritage (10).

## 6. Compliance and honest limits

All data is synthetic or anonymised and marked as such in `config/site.json`.
Cultural heritage is cited, never claimed exclusively; an invariant enforces it and
two rejection samples prove it. Every AI-generated image, copy draft, character,
asset and drama carries an explicit `AI-generated` label; the offline demo uses no
model, and the optional sidecar keeps the key and the network outside the package.
Known limits: image-to-image transfer from a reference photo is not exposed;
library search is deterministic metadata, not an image embedding; the capacity model
plans per workshop day, not per machine; live model mode needs a key and the
sidecar process. Remaining client inputs are the six-industry interview material,
the client's own craft rules, the pattern licence list and the acceptance reviewer;
pricing and the commercial quote remain the bid owner's decision.
