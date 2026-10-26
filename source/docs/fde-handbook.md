# FDE On-Site Delivery Handbook <a id="on-site-delivery"></a>
Forward-deployed engineering (FDE) method for putting the C2M craft service into
one enterprise, on site, with the client's own craftsperson, export desk and
finance team in the room. The worked example is EP-0001, Harbour Jewellery Works
(synthetic), a medium jewellery enterprise on the East Asian coastal belt.

Every number here is read from the repository; nothing describes a future feature.
Delivery is FDE-JW-01 on profile EP-0001: `on_prem` in CN, auth gate enabled, nightly
logical backup with 14 day retention and quarterly restore drill, SLA of 4 hours first
response and 21 days delivery, zh primary and en secondary with de also rendered,
checklist version 1.0.0.

The delivery command is `python -m c2m_craft demo`. It rewrites every artifact under
`out/` and produces `out/enterprise_report.json`, which renders readiness from
`config/enterprise/fde-checklist.json` for both configured profiles. Today it says
12 items, 9 done, 3 open, `readiness_bp` 7500, `status` `pilot`. Two open items are
blocking, so the report refuses to present the profile as live. Readiness is
derived, not typed: a deployment cannot claim go-live while a blocking item is
open, because the open set is recomputed on every run.
## Scope
In scope: six-industry interview notes, craft rule proofreading, the data boundary
map, one populated profile assembled from the ten components in
`config/enterprise/components.json`, the multilingual site and SEO audit, the
inquiry to CRM loop, three training tiers and a formal handover.

Out of scope: new craft rules, workshops or industries (data additions with their
own authoring form); legal advice (this handbook records what the profile declares,
counsel signs it); live payment capture and real customer data (all people and
companies in the repository are synthetic).

Client-visible artefacts: `out/enterprise_report.json` for readiness and open items;
`out/growth_report.json` for the nine pages, SEO score, negative audit and CRM board,
with `site_files` listing the files under `out/site`; `out/library_snapshot.json` for
licensed patterns; `out/settlement_report.md` for finance; `out/contract_report.json`
for acceptance.
## Phase 1: discover <a id="discover"></a>
Goal: replace assumptions with signed facts. Three items, all blocking, all done.

| Item id | Title | Owner | Evidence | Status | Blocking |
|---|---|---|---|---|---|
| `interview_signed` | Interview notes for the industries signed off by the client | FDE | `docs/fde-handbook.md#discover` | done | true |
| `rules_reviewed` | Craft rules proofread by the craftsperson | FDE + artisan | `docs/rule-authoring-form.md` | done | true |
| `data_boundary_map` | Data boundary map and cross-border list confirmed | FDE + legal | `docs/fde-handbook.md#data-boundary-map` | done | true |

Method: interview the owner, the export desk and one craftsperson separately,
because their definitions of "makeable" rarely match. Walk the rule files with the
craftsperson and mark every rule they would override in practice. Draw the data map
before configuration, because a profile cannot be populated honestly without
knowing where personal data lands. Collect signatures on the notes, not on a
summary written afterwards. Exit criterion: all three items done, and the client
can restate the boundary map without reading it.
## Phase 2: configure
Goal: turn signed facts into one profile. Site acceptance is the only non-blocking
item, because a site can be re-reviewed after go-live without breaking an order.

| Item id | Title | Owner | Evidence | Status | Blocking |
|---|---|---|---|---|---|
| `profile_populated` | Enterprise profile fully populated from the component registry | FDE | `config/enterprise/profiles/EP-0001.json` | done | true |
| `site_reviewed` | Multilingual pages and the SEO audit accepted by the client | FDE + marketing | `out/growth_report.json` | done | false |
| `licence_list` | Pattern licence list and expiry reminders in place | FDE | `out/library_snapshot.json` | done | true |

Method: enable only what the client will operate; EP-0001 enables all ten
components, including `ip_studio` and `ip_licensing`. Fill every component config
from the registry entry without inventing keys; the report marks a component `ok`
only when its boundary and dependencies hold. Generate the site from
`config/growth/site.json` and `config/growth/copy.json`, then run the SEO audit;
copy edits are data edits, never code edits. Attach a licence record to every
pattern before the library is shown; a pattern without source, scope and review
state does not enter. Demo the industry switch with `GET /api/enterprise/switch`
so the client sees what is shared and what is industry specific. Exit criterion:
profile populated, licence list complete, and the client has opened one generated
page in each of en, zh and de.
## Phase 3: pilot
Goal: rehearse the commercial loop with the people who will run it. Two of three
items are done; training is open and blocking.

| Item id | Title | Owner | Evidence | Status | Blocking |
|---|---|---|---|---|---|
| `crm_rehearsed` | Inquiry to CRM loop rehearsed with the export desk | FDE | `out/growth_report.json` | done | true |
| `operator_training` | Operator and administrator training tiers delivered | FDE | `docs/fde-handbook.md#training-tiers` | open | true |
| `order_reconciliation` | Order ledger reconciled and signed by finance | FDE + finance | `out/settlement_report.md` | done | true |

Pilot script: submit a real-shaped inquiry in the client's language through the
generated form or `POST /api/growth/inquiry`; read `GET /api/growth/crm` with the
export desk and confirm score, owner and due time; advance the lead stage by stage
with a note of at least 12 characters, and let the loop refuse a disallowed stage;
reconcile the quoted value and settlement lines with finance and have finance sign;
freeze the evidence in the report, not in a slide deck. Exit criterion: the export
desk runs the loop unaided, finance has signed, and the training tiers are
delivered with attendance recorded.
## Data Boundary Map
Source: `data_boundaries` in `config/enterprise/profiles/EP-0001.json`. All five
stores declare region CN.

| Store id | Kind | Region | Personal data |
|---|---|---|---|
| `store_craft_rules` | craft_rules | CN | false |
| `store_orders` | orders | CN | true |
| `store_library` | library | CN | false |
| `store_crm` | crm | CN | true |
| `store_content` | content | CN | false |

Cross-border position: the profile declares `cross_border: true`, and the DPA
reference is `docs/fde-handbook.md#data-boundary-map`, this section. Personal data
exists only in `store_orders` and `store_crm`; craft rules, the pattern library and
content carry none. A transfer happens when someone outside CN reads those two
stores, or when inquiries from de, en or zh markets are worked by a desk outside
CN. Both are expected in the export loop. The DPA must be signed and on file before
go-live and must name the export desk as a recipient; this handbook records the
requirement, it does not replace the agreement. CRM retention is 730 days from the
`crm_leads` component config; orders follow the ledger policy. Neither store may be
copied to a laptop for a demo. The inquiry form posts to `/api/growth/inquiry` and
accepts only the FORM-JW-01 fields, so the transfer surface is known and small.

FDE rules: never restore a CN backup into a non-CN environment; never paste inquiry
records into chat, tickets or slides; route raw-lead export requests through the
DPA owner and provide an aggregate instead.
## Go-Live
| Gate | State for EP-0001 | Meaning |
|---|---|---|
| `auth_gate_enabled` | done | Deployment auth gate and access audit enabled |
| `backup_restore_drill` | open | Backup restore has not been drilled and recorded |
| `handover_signed` | open, non-blocking | Handover note and open issue list not yet signed |

Because `backup_restore_drill` and `operator_training` are open and blocking, EP-0001
stays at `status` `pilot` with `readiness_bp` 7500. Close them; do not argue with it.

Runbook: re-run the demo and confirm `blocking_open` is empty; confirm the auth gate
is enabled and access is audited (the prototype binds loopback, and network
exposure is a deployment decision that needs the gate first); run the backup,
restore it into an isolated environment and record the restore; re-check the site
score and the CRM SLA board, where zero breaches is expected and any breach needs a
written reason; have the client sign the handover note and the open issue list.
## Training Tiers
Training is complete only when each tier has a named attendee and a signed
attendance record.

| Tier | Audience | What they must be able to do | Evidence of completion |
|---|---|---|---|
| T1 operator | Export desk, studio desk, workshop coordinator | Work the CRM board, advance a stage with a note, read a quote draft, submit a site inquiry, read the SEO page list | Attends T1 and completes one supervised inquiry to quote |
| T2 administrator | Operations lead, IT liaison | Switch industry, enable or disable a component, read the enterprise report, run the demo, restore a backup, manage users and the auth gate | Attends T2 and performs a restore in the drill environment |
| T3 developer | Client engineering or integrator | Read the contract registry, add a rule file, add a site page as data, extend an invariant, run tests and verification | Attends T3 and lands one data-only change with tests passing |

T1 covers the nine pages, form fields, scoring and routing, the SLA clock,
follow-ups, quote validity and pipeline transitions, and does not touch configuration
files. T2 covers the component registry, profile assembly, industry switch, readiness
semantics, the demo, backup and restore, and the access audit; it teaches why a
blocking item cannot be waived. T3 covers contract first seams, `config/craft_rules`,
the validator schema subset, invariant registration, negative samples, and the rule
that the demo stays byte-identical across two runs.

Anti-patterns: training on a slide deck instead of the running service; teaching only
the happy path, when the value is in the refusal paths (an unmakeable detail, a
disallowed stage move, a pattern without a licence); signing off T1 without supervision.
## Escalation
| Severity | Example | First responder | Escalates to | Target |
|---|---|---|---|---|
| S1 | Data boundary breach or auth gate failure | FDE on site | FDE lead and client legal | Immediate stop, written incident note |
| S2 | Go-live blocked by a failed restore or missing training | FDE | Delivery manager and client ops | Same working day |
| S3 | Site page or SEO audit rejected by client | FDE | Marketing owner | Next working day |
| S4 | Copy, label or wording change | Export desk | FDE | Next review slot |

Responsibility follows the phase owner: the FDE is responsible, the client owner is
accountable, and craft, legal, finance and ops are consulted where touched.
## Handover
Handover is a document set, not a meeting. `handover_signed` stays open until the
client signs both the note and the open issue list; it is non-blocking, so an
otherwise ready deployment can go live with a tracked handover gap.

Pack: the signed checklist with all twelve item ids and final status; the final
`out/enterprise_report.json` plus the hash manifest proving reproducibility; the data
boundary map and signed DPA reference; the populated profile with a change log; the
T1 to T3 attendance record with named attendees; the backup and restore drill record;
the open issue list with owner, severity and review date; and the operating cadence,
naming who reads the SLA board, reviews the SEO score and owns licence expiry.

Acceptance questions: can the client run the demo alone; explain why readiness is
7500 bp and what closes it; name the two stores holding personal data; advance a lead
to quote unaided; and name an owner for every open issue. When all five are yes, sign
the note, attach the open issue list, and move to support.
