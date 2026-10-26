# Data contracts

Twenty-three contracts live in `contracts/`. `contracts/registry.json` is the index:
it binds each contract id to its `$id` urn, its file, a semantic version, the
invariants it enforces and the requirement ids it serves.

```
python -m c2m_craft contracts list      # what is registered
python -m c2m_craft contracts verify    # positives accepted, negatives rejected
```

## 1. Validation model

`c2m_craft/core/contracts.py` implements a JSON Schema 2020-12 subset:

| Supported | Not supported (on purpose) |
|---|---|
| `$ref` (local and cross-document by `$id` urn) | remote `$ref` |
| `type` (string or list), `required`, `properties`, `additionalProperties` | `format` assertions |
| `enum`, `const`, `pattern`, `minLength`, `maxLength` | `$dynamicRef`, `unevaluated*` |
| `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` | numeric `multipleOf` |
| `items`, `minItems`, `maxItems`, `uniqueItems` | tuple validation beyond prefix items |
| `minProperties`, `maxProperties`, `propertyNames` | content encodings |
| `allOf`, `anyOf`, `oneOf`, `not` | |
| `x-invariants` (custom) | |

Errors carry the instance path (`$.license.usage_scope`), the keyword and, for
semantic failures, the invariant id. The validator is exercised by both the
positive and the negative suite, so it cannot silently degrade into a no-op.

## 2. Invariants

Cross-field rules that JSON Schema cannot express are declared per contract as
`x-invariants` and implemented in `c2m_craft/core/invariants.py`.

| Id | Contract | Rule |
|---|---|---|
| `INV-LIC-01` | pattern_asset | `source_type=licensed` requires `licensor` and `license_id`; attribution requires a content review |
| `INV-LIC-02` | pattern_asset | usage scope must be non-empty and duplicate free |
| `INV-LIC-03` | pattern_asset | a traditional prototype, or an asset naming a religious site, cannot be exclusive |
| `INV-LIC-04` | pattern_asset | `valid_from < valid_to`; with `require_active_window`, the window must cover `as_of` |
| `INV-ORDER-01` | c2m_order | total = subtotal + customisation fee; the four revenue shares sum to the total; status is a known state |
| `INV-MONEY-01` | settlement | policy and payout rates sum to 10000 bp and agree per party; payouts sum to the total; reconciliation delta is zero |
| `INV-REVIEW-01` | artisan_review | an override needs a reason of at least 8 characters and must change the verdict; `confirmed` cannot contradict a different decision |
| `INV-IP-01` | ip_license | traditional prototypes must keep `exclusive_claimed=false`; no exclusivity while prototypes are referenced |
| `INV-CUSTOM-01` | customization_choice | each option group appears once; selection deltas sum to the declared delta; unit price = base + delta; `applied` needs a result concept; status and `feasibility.ok` agree |
| `INV-EDITION-01` | edition | issued and reserved numbers stay inside `1..size`, are unique and disjoint; a `closed` edition has issued all its numbers; every number has a distinct collector record; the artist royalty stays at or below 50 percent |
| `INV-EDITION-02` | collector_record | the provenance chain starts with an `issue` entry, each entry continues from the previous owner and the last entry points at the current owner |
| `INV-QC-01` | qc_record | a pass carries no major or critical defect; a failure carries at least one; rework carries at least one defect; every measurement's `ok` flag agrees with its limits |
| `INV-PROMISE-01` | c2m_order | the promised delivery, and every alternative, is later than the order creation time; the working time is positive |
| `INV-DISPUTE-01` | c2m_order | a dispute that never opened carries no reason, time or evidence; an open one carries a reason and an opening time; a resolved one carries a note and a resolution time; a quality record is cited at most once |
| `INV-ROYALTY-01` | settlement | royalty lines sum to the IP payout; each line stays within the IP share and its own basis; rates stay inside 0..10000 bp |
| `INV-COMP-01` | service_component | a component cannot depend on itself, a prototype cannot be enabled by default, a personal-data component needs a retention policy, a lead-storing component must declare personal data |
| `INV-ENT-01` | enterprise_profile | component ids are unique, enabled components satisfy the channels they must serve, the primary locale is not repeated, the FDE handbook reference and a four-item checklist exist, the CRM pipeline starts at `new`, growth serves the primary locale |
| `INV-SEO-01` | growth_site | every language has a page, every page links every language, canonical equals path, paths carry the language prefix, title and description respect the declared bounds, canonical paths are unique, an audited site carries a positive score |
| `INV-LEAD-01` | inquiry_lead | the score is the clamped sum of its factors, the SLA falls after submission, advanced stages carry a first response, quoted and won stages carry a quote, the last event opens the current stage, events and follow-ups are ordered |
| `INV-CHAR-01` | character_bible | two distinct characters, distinct elements and signature lines, one review each, at least three motifs, two props and three arc beats, an authenticity label, and no exclusive heritage claim |
| `INV-ASSET-01` | visual_asset | the checksum recomputes from identity and recipe, a licensed asset needs a reference, an AI-assisted asset needs a label, an approved asset needs a reviewer, layer geometry matches the shape |
| `INV-DRAMA-01` | short_drama | beat durations sum to the scene, scenes sum to the cut, frames sum to the cut and to their scene, the EDL covers every frame once in order with continuous timecodes, subtitles stay inside the cut without overlap, an approval carries no open issue |
| `INV-CONTENT-01` | content_review | an approval carries no failed item, an authenticity label and no heritage exclusivity; a rejection needs a failed item or a heritage conflict; failed items need a note; AI content must require disclosure |
| `INV-MERCH-01` | merch_spec | tolerances are positive, the AQL is a real inspection plan, characters and materials are unique, the packaging or inspection carries the authenticity label, the derivative royalty stays at or below 50 percent |
| `INV-IP-02` | ip_license | signed documents carry both parties, every licensed derivative category has a signed document, document ids are unique, and exclusivity is refused while traditional prototypes are referenced |

## 3. The contracts

### common
Value objects referenced everywhere: bilingual text (`{zh, en}`), money
(`amount_cents` integer plus currency), RFC 3339 timestamps, actors, hex colours,
basis points, slugs, semver, SHA-256 hex and the industry enum. Amounts are
always integer cents; there are no floats in the money path.

### pattern_asset
The licensing gate. Required: `asset_id`, `title`, `industries`, `medium`,
`license`, `traditional_prototype`, `religious_site_names`, `review`,
`created_at`. `license.source_type` and `license.usage_scope` are required by the
schema; the cross-field rules above catch the cases the schema cannot. An asset
that cannot say where it came from and what it may be used for is rejected at
ingestion with the field path. Since registry 1.1.0 an optional `descriptor`
(motif family, symmetry, density in basis points, line weight, edge complexity)
makes search deterministic offline; when it is absent the library derives one
from `preview.motif_style`.

### design_concept
A generated candidate: source prompt, deterministic `seed`, palette, form
parameters, material, style parameters, the `craft_facts` bag that the assessment
consumes, a preview descriptor and the generator descriptor (adapter, version,
`deterministic: true`). Two identical requests produce identical concepts apart
from the allocated id. Optional `derived_from` and `customization_id` record the
lineage of a concept produced by participatory customisation.

### manufacturability_assessment
The output of the two-tier engine. `rule_evaluations` keeps every rule and
capability check with its status, severity and the fact values that triggered
it. `auto` carries the engine verdict and blocking rules, `artisan` carries the
review disposition (`not_required`, `pending`, `confirmed`, `overridden`),
`final_verdict` is the effective verdict, and `reproducibility` pins the rules
version and the facts hash so a reviewer can recompute the decision.

### craft_work_order
The manufacturing instruction: BOM lines driven by concept facts, process route
with equipment assignment, the craft constraints inherited from the assessment,
quality checkpoints with pass criteria, and the promised delivery date derived
from the workshop lead time. A work order cannot exist without a passing
assessment.

### c2m_order and the ledger event
Order amounts, the four sub-states (status, refund, dispute) and the items. An
item may carry `customization_id`, `edition_id` and `edition_number`, and the
order carries a `promise` block: the chosen workshop, the promised delivery, the
capacity slot, the working minutes and the alternative workshops with their
promises. The dispute sub-state can cite quality records (`qc_record_ids`); the
order book refuses a citation to an unknown record or to another order's record,
and `INV-DISPUTE-01` keeps the sub-state, its reason and its resolution coherent.
The `$defs/order_event` definition is the ledger row: sequence number,
timestamps, actor, payload, previous hash and hash. Ledger rows are validated
against this definition in the tests and in the verification script.

### settlement
The revenue split. `split_policy.lines` carries rates in basis points that must
sum to 10000; `payout_lines` carries the integer-cent result; `remainder_cents`
records how many cents the largest-remainder rule distributed; `reconciliation`
pins the delta to zero. Refunds applied before posting are recorded in
`refunds`, so a split settlement shows both the original total and the net.
Optional `royalty_lines` allocate the IP share across the licensed assets used by
the order, weighted by each asset's rate, with the largest remainder going to the
last line so the sum matches the IP payout exactly.

### customization_choice
One buyer's option selections: the base concept, the resolved selections with
their labels, fact changes and integer price deltas, the amounts (base, delta,
unit price), the feasibility gate and the derived concept. An option can only
change facts; the derived concept is assessed again before anything is ordered,
so a selection cannot smuggle in an unmakeable design.

### edition and collector_record
An edition fixes a size and a numbering policy. Numbers are reserved when an order
is placed and issued when it settles; `INV-EDITION-01` makes over-issuing and
duplicate serials impossible. The collector record holds the certificate hash and
the ordered ownership chain. The hash covers the piece identity (edition, number,
concept, certificate id) rather than the owner, so a transfer appends to the chain
and leaves the certificate valid.

### qc_record
The inspection: sampling plan, measurements with derived limits, defects with a
severity from the published taxonomy, the verdict, the inspector and the time.
`INV-QC-01` is what makes a pass with a critical defect impossible to store, so a
dispute cites a record rather than a sentence.

### production_schedule
The capacity plan behind a promise: the horizon, the daily capacity, the slots
already committed and the utilisation per day. It is generated from the logical
clock and the committed work orders, so the same state always yields the same
schedule.

### enterprise_profile
The B-layer seam: one enterprise, one profile. Components are declared with a
kind (knowledge base, agent, workflow, scenario showcase, CRM, growth, commerce,
analytics), an enabled flag and a configuration object; the industry enum switches
the profile rather than the code. Version 1.1.0 adds the populated-profile blocks:
`data_boundaries` (stores, regions, personal data, cross-border and the DPA
reference), `deployment` (mode, region, auth gate, backup policy) and `growth`
(site id, languages, CRM pipeline). The FDE handbook reference and go-live checklist
remain required, so a deployment cannot be declared done without them.

### service_component
One registry entry: component id, bilingual name, kind, industries, capabilities,
configuration path, contracts it reads, dependencies, default enablement, data
boundary (stores, personal data, retention, cross-border), maturity and a bilingual
summary. The registry file validates every entry against it, so a new component is
data, not code.

### growth_site
The generated multilingual site: brand, languages, primary language, one record per
page and language with title, meta description, H1, canonical path, hreflang
alternates, keywords, JSON-LD, sections and status, plus the SEO audit (audited,
score in basis points, issues with severity, checked time and the rules) and the
inquiry form that feeds the CRM.

### inquiry_lead
One inquiry and the closed loop around it: contact, message, intent, product
interest, the lead (stage, deterministic score with its factor breakdown, owner,
SLA deadline, first response), follow-up tasks with due times and templates, an
optional quote draft and the ordered CRM events. Stage is a function of the events.

### character_bible
The dual guardian canon: version, bilingual title, world (premise, bilingual
setting, era, three or more rules, conflict, resolution theme) and exactly two
characters with element, archetype, personality axes, silhouette, palette, motifs,
taboos, props, voice, relationship, three arc beats, licence-safe sourcing, an
authenticity label and a content review reference, plus the non-exclusive heritage
references and the usage plan.

### visual_asset
One asset of the character library: identity, character, kind (turnaround,
expression, prop, costume, scene), view or name, a drawing recipe (background plus
layers with shape, fill, stroke, width, opacity and geometry), resolution, source
(sourcing class, optional licence reference, AI flag, authenticity label, model
references), review state and a SHA-256 checksum over identity and recipe.

### short_drama
Script to final cut: bilingual title, bible reference, logline, genre, scenes with
heading, characters, beat-level durations and bilingual dialogue, a storyboard of
timed frames with shot, camera and visual cue, the cut (total seconds, EDL with
timecodes and transitions, tracks), the subtitle track and the review block.

### content_review
The review record every cultural IP artefact cites: subject kind and reference, a
checklist with item verdicts and notes, the verdict, the reviewer and role, the
authenticity block (AI flag, label, model references, disclosure flag) and the
heritage check (prototypes referenced, exclusivity claim, note).

### merch_spec
One derivative category: bilingual title, characters, licence reference, bill of
materials with sourcing classes, quality (tolerances, finish, testing, inspection
points, AQL sampling), packaging with label requirements, rights (royalty, territory,
term, exclusivity) and the content review reference.

### artisan_review
One queue item per assessment that asked for a human. It keeps the failed rule
ids, the auto verdict, the assigned craftsperson, the SLA and the decision.
`INV-REVIEW-01` is what stops a silent override.

### enterprise_profile
The B-layer seam: one enterprise, one profile. Components are declared with a
kind (knowledge base, agent, workflow, scenario showcase, CRM, analytics), an
enabled flag and a configuration object; the industry enum switches the profile
rather than the code. The FDE handbook reference and go-live checklist are part
of the profile, so a deployment cannot be declared done without them.

### ip_license
The C-layer seam: characters, derivative categories, territory, term, royalty
rate, quality specification, contract template reference, content review and the
traditional prototype references. Version 1.1.0 adds the signed `documents` (kind,
status, derivative categories, signatories with signed times, file reference and a
SHA-256 checksum) and the `merch_spec_refs`. The two invariants are the compliance
guarantee: heritage is referenced, never owned, and every licensed derivative
category has a signed document.

## 4. Sample suite

```
samples/library/assets.json                  8 valid assets
samples/concepts/DC-0001..0010.json         10 valid concepts
samples/contracts/positive/*.json           24 valid records of the other types
samples/contracts/negative/*.json           31 invalid records
samples/contracts/negative/expected.json    expected error class and path per negative
```

Each negative sample is a documented mutation of a valid record and the expected
error class is committed next to it:

| Negative sample | Contract | Expected |
|---|---|---|
| pattern-asset-missing-source | pattern_asset | `required` at `$.license` |
| pattern-asset-empty-scope | pattern_asset | `INV-LIC-02` |
| pattern-asset-exclusive-heritage | pattern_asset | `INV-LIC-03` |
| pattern-asset-inverted-window | pattern_asset | `INV-LIC-04` |
| pattern-asset-bad-hex | pattern_asset | `pattern` at `$.palette[0]` |
| design-concept-bad-seed | design_concept | `pattern` at `$.seed` |
| design-concept-missing-facts | design_concept | `required` at `$` |
| order-negative-amount | c2m_order | `minimum` at `$.amounts.platform_fee_cents` |
| order-share-mismatch | c2m_order | `INV-ORDER-01` |
| settlement-rate-mismatch | settlement | `INV-MONEY-01` |
| review-override-no-reason | artisan_review | `INV-REVIEW-01` |
| review-confirmed-contradiction | artisan_review | `INV-REVIEW-01` |
| ip-license-exclusive-heritage | ip_license | `INV-IP-01` |
| work-order-empty-bom | craft_work_order | `minItems` at `$.bom` |
| customization-choice-delta-mismatch | customization_choice | `INV-CUSTOM-01` |
| edition-duplicate-number | edition | `INV-EDITION-01` |
| collector-chain-break | collector_record | `INV-EDITION-02` |
| qc-pass-with-critical | qc_record | `INV-QC-01` |
| settlement-royalty-mismatch | settlement | `INV-ROYALTY-01` |
| order-dispute-resolved-without-note | c2m_order | `INV-DISPUTE-01` |
| service-component-self-dependency | service_component | `INV-COMP-01` |
| enterprise-profile-crm-channel-missing | enterprise_profile | `INV-ENT-01` |
| growth-site-hreflang-gap | growth_site | `INV-SEO-01` |
| growth-site-title-too-short | growth_site | `INV-SEO-01` |
| inquiry-lead-score-mismatch | inquiry_lead | `INV-LEAD-01` |
| character-bible-heritage-exclusive | character_bible | `INV-CHAR-01` |
| visual-asset-checksum-mismatch | visual_asset | `INV-ASSET-01` |
| short-drama-timecode-gap | short_drama | `INV-DRAMA-01` |
| content-review-approved-with-fail | content_review | `INV-CONTENT-01` |
| merch-spec-missing-authenticity-label | merch_spec | `INV-MERCH-01` |
| ip-license-draft-only-coverage | ip_license | `INV-IP-02` |

Verification asserts the class of the rejection (keyword or invariant id) and the
path prefix, not the exact message, so wording changes cannot weaken the suite.

## 5. Versioning

Each registry entry has a semantic version and a status. A breaking change means
a new major version and a migration note in this file; the ledger keeps the
contract version it was written with, which is why the assessment record stores
`rules_version` and `facts_hash` next to the verdict.

Registry 1.2.0 kept the fifteen M1/M2 contracts and bumped `c2m_order` to 1.2.0: the
dispute sub-state gains optional `qc_record_ids` and the `INV-DISPUTE-01`
invariant, so the M1 refund/dispute paths and the M2 order samples stay valid.

Registry 2.0.0 adds the eight M3/M4 contracts (`service_component`, `growth_site`,
`inquiry_lead`, `character_bible`, `visual_asset`, `short_drama`, `content_review`
and `merch_spec`) and bumps `enterprise_profile` and `ip_license` to 1.1.0. The two
bumps are additive: older M1 records remain valid, while the populated profile and
the signed document set add the fields the runtime and the invariants use. The
M1/M2 contracts are unchanged since 1.2.0.
