# Requirement decomposition matrix

Generated from `docs/requirements.json` by `python -m c2m_craft requirements render`.

- Items: 54 · covered 39 · partial 1 · planned 9 · excluded 5
- M1 items implemented: 21/21

| ID | Module | Milestone | Status | Requirement | Contracts | Artifacts | Verify | AC | Quote |
|---|---|---|---|---|---|---|---|---|---|
| A1.1 | A | M1 | covered | Text or reference image to form and pattern concept candidates | design_concept | c2m_craft/creative/workstation.py, static/app.js, config/creative/lexicon.json | C | J1 |  |
| A1.2 | A | M3 | covered | Style transfer | design_concept | c2m_craft/creative/workstation.py, config/creative/styles.json, static/app.js, verify/records/model_calls.md | C | J1 |  |
| A1.3 | A | M1 | covered | Palette and series expansion | design_concept | c2m_craft/creative/series.py, config/creative/series.json, config/creative/palettes.json | C | J1 |  |
| A1.4 | A | M1 | covered | Pattern and material effect preview | design_concept | static/app.js, c2m_craft/creative/workstation.py | C | J1 |  |
| A2.1 | A | M1 | covered | Mandatory licensing source and usage scope with positive and negative cases | pattern_asset | c2m_craft/library/assets.py, contracts/pattern-asset.schema.json, samples/library/rejected.json | B | J2 |  |
| A2.2 | A | M2 | partial | Multimodal search over the asset library | pattern_asset | c2m_craft/library/assets.py, out/library_snapshot.json, static/app.js | B | J2 |  |
| A3.1 | A | M1 | covered | Designer original pre-sale transaction | c2m_order | c2m_craft/commerce/orders.py, samples/contracts/positive/order-ORD-0001.json | D | J4 |  |
| A3.2 | A | M2 | covered | Consumer participatory customisation | c2m_order, customization_choice | contracts/customization-choice.schema.json, config/commerce/customization.json, c2m_craft/commerce/customization.py, out/customization_report.json | I | J4 |  |
| A3.3 | A | M2 | covered | Artist and manufacturer collaboration with limited edition numbering | c2m_order, ip_license, edition, collector_record | contracts/edition.schema.json, contracts/collector-record.schema.json, c2m_craft/commerce/editions.py, out/edition_archive.json | I | J4 |  |
| A4.1 | A | M1 | covered | Order to work order to dispatch to QC to shipment to revenue sharing | c2m_order, craft_work_order, settlement | c2m_craft/commerce/orders.py, c2m_craft/commerce/dispatch.py, c2m_craft/commerce/settlement.py | D | J4 |  |
| A4.2 | A | M2 | covered | Delivery timeline commitment for custom items | craft_work_order, production_schedule, c2m_order | config/commerce/capacity.json, c2m_craft/commerce/capacity.py, out/capacity_plan.json | I | J4 |  |
| A4.3 | A | M2 | covered | Refund and dispute handling | c2m_order, settlement | c2m_craft/commerce/orders.py, config/commerce/pricing.json, out/quality_report.json | D | J4 |  |
| A4.4 | A | M2 | covered | Quality standards | qc_record, craft_work_order | config/commerce/quality.json, contracts/qc-record.schema.json, c2m_craft/commerce/quality.py, out/quality_report.json | I | J4 |  |
| A5.1 | A | M1 | covered | Jewelry craft rules: setting, casting, chasing | manufacturability_assessment | config/craft_rules/jewelry.json, c2m_craft/craft/rules.py | C | J3 |  |
| A5.2 | A | M1 | covered | Hardwood rules: joinery, carving, surface, plus equipment capability | manufacturability_assessment | config/craft_rules/hardwood.json, config/equipment/WS-HW-A.json, config/equipment/WS-HW-B.json | C | J3 |  |
| A5.3 | A | M1 | covered | Verdict: can it be made, where it cannot, what to change | manufacturability_assessment | c2m_craft/craft/assessment.py, samples/concepts/expected.json | C | J3 |  |
| A5.4 | A | M1 | covered | Two-tier process: AI preliminary verdict plus craftsperson review | artisan_review, manufacturability_assessment | c2m_craft/craft/review.py, contracts/artisan-review.schema.json, static/app.js | C | J3 |  |
| A5.5 | A | M1 | covered | Rules maintainable by non-programmers | - | c2m_craft/craft/lint.py, config/craft_rules/rule_file.schema.json, docs/rule-authoring-form.md | A | J3, J9 |  |
| B1 | B | M3 | covered | Componentised enterprise AI service layer | service_component, enterprise_profile | c2m_craft/enterprise/registry.py, c2m_craft/enterprise/runtime.py, config/enterprise/components.json, out/enterprise_report.json | J | J5 |  |
| B2 | B | M1 | covered | Industry switching by configuration, not duplicated code | enterprise_profile, service_component | config/enterprise/profiles/EP-0001.json, config/enterprise/profiles/EP-0002.json, c2m_craft/enterprise/runtime.py, out/enterprise_report.json | J | J5 |  |
| B3 | B | M3 | covered | Multilingual site, SEO, content, foreign-trade leads, CRM, inquiry follow-up | growth_site, inquiry_lead, enterprise_profile | config/growth/site.json, config/growth/copy.json, config/growth/crm.json, c2m_craft/enterprise/growth/, out/growth_report.json, out/site/en/index.html | J | J6 |  |
| B4 | B | M3 | covered | FDE on-site delivery handbook | enterprise_profile | docs/fde-handbook.md, config/enterprise/fde-checklist.json, out/enterprise_report.json | J | J5 |  |
| B5 | B | M1 | covered | One-enterprise-one-profile sample | enterprise_profile | samples/contracts/positive/enterprise-profile-EP-0001.json, config/enterprise/profiles/EP-0001.json | J | J5 |  |
| C5 | C | M1 | covered | Licensing contract templates | ip_license, content_review | config/ip/licensing.json, c2m_craft/ip/licensing.py, out/licensing_pack.json, docs/licensing-templates.md | K | J7 |  |
| C6 | C | M4 | covered | Derivative licensing and quality specification | merch_spec, ip_license | config/ip/licensing.json, c2m_craft/ip/licensing.py, out/licensing_pack.json, docs/licensing-templates.md | K | J7 |  |
| C7 | C | M1 | covered | No exclusive claim over traditional prototypes or religious site names | ip_license, pattern_asset | c2m_craft/core/invariants.py, samples/library/assets.json | B | J10 |  |
| C1 | C | M4 | covered | Dual guardian character settings | character_bible, content_review | config/ip/characters.json, c2m_craft/ip/bible.py, out/character_bible.json, docs/character-bible.md | K | J7 |  |
| C2 | C | M4 | covered | Character design manual and visual asset library | character_bible, visual_asset | config/ip/visuals.json, c2m_craft/ip/visuals.py, out/ip_asset_library.json | K | J7 |  |
| C3 | C | M4 | covered | Short-drama workflow from script to final cut | short_drama, content_review | config/ip/drama.json, c2m_craft/ip/drama.py, out/short_drama_package.json, docs/short-drama-workflow.md | K | J7 |  |
| C4 | C | M4 | covered | One sample reel | short_drama, content_review | out/sample_reel.html, out/content_review.json, verify/records/ui_smoke.log | K | J7 |  |
| D1 | D | M4 | covered | Optional global design co-creation competition operations package | - | docs/competition-ops-pack.md | K | - |  |
| E1 | E | M1 | covered | Runnable repository with one-click launch | - | README.md, start.ps1, start.sh, c2m_craft/__main__.py | F | J0, J1 |  |
| E2 | E | M1 | covered | Craft rules, equipment capability and licensing fields stored as data | pattern_asset | config/craft_rules/jewelry.json, config/equipment/WS-JW-A.json, contracts/pattern-asset.schema.json | A | J2, J3 |  |
| E3 | E | M1 | covered | Per-module verification records: commands, inputs, expected outputs | - | verify/run_verification.py, verify/records/tests_output.txt, verify/records/verification_output.txt, out/hash_manifest.json | F | J0, J9 |  |
| E4 | E | M1 | covered | Licensed or self-produced assets with content review and authenticity labelling | pattern_asset, ip_license, visual_asset, content_review | samples/library/assets.json, contracts/ip-license.schema.json, c2m_craft/ip/reviews.py, out/content_review.json | K | J10 |  |
| E5 | E | M1 | covered | Synthetic samples with interfaces defined against real field schemas | common | samples/concepts/DC-0001.json, config/site.json | G | J10 |  |
| F1 | F | M1 | excluded | Policy application materials | - | - | H | - |  |
| F2 | F | M1 | excluded | Fiscal funding estimates | - | - | H | - |  |
| F3 | F | M1 | excluded | Real medical diagnosis or treatment | - | - | H | - |  |
| F4 | F | M1 | excluded | Offline space construction | - | - | H | - |  |
| F5 | F | M1 | excluded | Licensed businesses requiring a locally qualified entity | - | - | H | - |  |
| G1 | G | M2 | planned | Business process interview material for the six industries | - | - | H | - |  |
| G2 | G | M2 | planned | Verbal craft rules with proofreading | - | - | H | - |  |
| G3 | G | M2 | planned | Pattern asset licensing list | pattern_asset | - | H | - |  |
| G4 | G | M2 | planned | Craft constraint samples from one jewelry and one woodworking enterprise | - | - | H | - |  |
| G5 | G | M2 | planned | Acceptance reviewer from the client | - | - | H | - |  |
| H1 | H | M2 | planned | Quote broken down by module A, B, C and D | - | - | H | - |  |
| H2 | H | M2 | planned | Quote broken down by milestone | - | - | H | - |  |
| H3 | H | M2 | planned | Stack, open-source reuse and delivery timeline | - | - | H | - |  |
| H4 | H | M2 | planned | Model and compute cost basis | - | - | H | - |  |
| I1 | I | M1 | covered | M1: architecture and data contracts, rule modelling plan, clickable workstation prototype | common, design_concept, manufacturability_assessment | ARCHITECTURE.md, docs/data-contracts.md, docs/rule-modeling-plan.md, static/index.html | H | J0, J1, J2, J3, J4, J8, J9, J10 |  |
| I2 | I | M2 | covered | M2: C2M pre-sale and manufacturing coordination pipeline plus pattern licensing library | c2m_order, pattern_asset, customization_choice, edition, collector_record, qc_record, production_schedule, settlement | out/capacity_plan.json, out/customization_report.json, out/edition_archive.json, out/quality_report.json, out/settlement_report.md | I | J4, J2 |  |
| I3 | I | M3 | covered | M3: enterprise AI service layer with two industry components plus the growth stack | enterprise_profile, service_component, growth_site, inquiry_lead | out/enterprise_report.json, out/growth_report.json, docs/fde-handbook.md, docs/growth-playbook.md | J | J5, J6 |  |
| I4 | I | M4 | covered | M4: IP pipeline with one sample reel plus full verification records and delivery documentation | character_bible, visual_asset, short_drama, content_review, ip_license, merch_spec | out/character_bible.json, out/ip_asset_library.json, out/short_drama_package.json, out/sample_reel.html, out/licensing_pack.json, out/content_review.json | K | J7 |  |

## Acceptance criteria

| AC | Criterion | Coverage | M1 items | Evidence |
|---|---|---|---|---|
| J0 | Both bidding and delivery include a runnable repository, documentation-only proposals are rejected | covered | E1, E3, I1 | I1, E1, E3 |
| J1 | Four main workflows are fully navigable end to end after one-command launch | covered | A1.1, A1.4, A2.1, A4.1 | A1.1, A1.4, A2.1, A4.1 |
| J2 | Asset ingestion rejects missing licensing source or usage scope, with positive and negative cases | covered | A2.1 | A2.1, C7, E2 |
| J3 | At least ten concept inputs including three counterexamples, ten out of ten agree with the documented rules | covered | A5.1, A5.2, A5.3, A5.4, A5.5 | A5.1, A5.2, A5.3, A5.4 |
| J4 | One custom order completes order, work order, dispatch, QC, shipment, revenue sharing with traceable amounts and refund paths | covered | A3.1, A3.2, A3.3, A4.1, A4.2, A4.3, A4.4 | A3.1, A3.2, A3.3, A4.1, A4.2, A4.3, A4.4 |
| J5 | Reusable components for at least two industries, industry switching by configuration, FDE manual and a populated profile | covered | B1, B2, B4, B5, I3 | B1, B2, B4, B5, I3 |
| J6 | Multilingual site generation, SEO metadata and inquiry-to-CRM closed loop, each with an end-to-end test | covered | B3, I3 | B3, I3 |
| J7 | Dual-character manual, visual asset library, one complete short-drama workflow with a sample clip, licensing templates and merchandise specs | covered | C1, C2, C3, C4, C5, C6, E4, I4 | C1, C2, C3, C4, C5, C6, E4, I4 |
| J8 | Unit tests for licensing validation, manufacturability, order state machine and revenue sharing, passing with one command | covered | E3, I1 | E3 |
| J9 | Every command and interface mentioned in the documentation actually exists | covered | E3, A5.5 | E3, A5.5 |
| J10 | Synthetic or anonymised samples only, no real confidential data, no exclusive claim on traditional or religious heritage | covered | C7, E5 | C7, E4, E5 |

Verification groups: 

- A: contracts and registry
- B: licensing ingestion gate
- C: manufacturability assessment
- D: C2M order pipeline
- E: four core unit-test areas
- F: documentation and implementation consistency
- G: compliance, determinism and offline guarantees
- H: requirement coverage
- I: milestone 2: customisation, capacity, editions, royalties, quality
- J: milestone 3: enterprise service layer, FDE handbook and growth stack
- K: milestone 4: cultural IP character bible, short drama, sample reel and licensing
