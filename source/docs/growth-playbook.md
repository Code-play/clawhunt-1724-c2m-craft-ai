# Growth Playbook: Multilingual Site and Inquiry Loop
Operating guide for the growth stack of SITE-JW-01, the synthetic jewellery site
for EP-0001: the generated pages, the SEO contract, the inquiry form, lead scoring,
routing, follow-ups, quotes and the CRM pipeline.

The stack is configuration, not code. Pages come from `config/growth/site.json`
and `config/growth/copy.json`; scoring and routing come from
`config/growth/crm.json`. Change the data, re-run the demo, and
`out/growth_report.json` changes with it.

| File | Role |
|---|---|
| `config/growth/site.json` | Pages, slugs, sections, languages, SEO bounds, inquiry form |
| `config/growth/copy.json` | Nav, footer, form labels, follow-up templates, page titles |
| `config/growth/crm.json` | Scoring, routing, follow-ups, quote policy, pipeline |
| `out/site` | Generated site: 9 pages, `sitemap.xml`, `robots.txt` |
| `out/growth_report.json` | Site record, SEO audit, negative audit, CRM board, trace |

The demo writes `out/site` from scratch. Never hand-edit a generated page; the next
run removes it.
## The Nine Pages
Three page ids times three languages. Language `en` is primary.

| Page id | Slug | Paths | Sections |
|---|---|---|---|
| `home` | empty | `/en`, `/zh`, `/de` | hero, value, inquiry |
| `collection` | `collection` | `/en/collection`, `/zh/collection`, `/de/collection` | range, craft, proof |
| `studio` | `studio` | `/en/studio`, `/zh/studio`, `/de/studio` | story, team, visit |

Files land under `out/site/en`, `out/site/zh` and `out/site/de` as `index.html`,
`collection.html` and `studio.html`, plus `out/site/sitemap.xml` and
`out/site/robots.txt`. The `site_files` array in `out/growth_report.json` lists 11
entries: 9 pages and 2 files. `python -m c2m_craft serve` binds `127.0.0.1:8412` and
serves the pages at `/en`, `/zh`, `/de` and their slugs, with the sitemap and robots
file at the root. The demo generates; the server serves what is on disk.
## SEO Contract
Bounds live in `config/growth/site.json` and are copied into every audit.

| Rule | Bound | Severity when broken |
|---|---|---|
| Title length | 12 to 70 characters | major |
| Meta description length | 45 to 200 characters | major |
| H1 length | 4 to 120 characters | minor |
| H1 count | exactly one per page | generator emits one |
| Canonical | `canonical_path` equals the page path | major |
| Hreflang | every page lists en, zh, de and each target links back | major if target missing, minor if not reciprocal |
| JSON-LD | `@context` and `@type` present, `inLanguage` matches the page | minor and info |
| Keywords | at least three | minor |
| Language coverage | every declared language has pages | major |
| Primary home | the primary language has a home page | major |

Score model: start at 10000 bp, subtract major 1500, minor 500, info 100, floor
zero. A page set is `reviewed` only when the score is at least 8000 and no major
issue remains. The generated site scores 10000 with zero issues and all 9 pages
reviewed. Structured data: `Organization` on home, `CollectionPage` on collection,
`AboutPage` on studio. Each page carries a canonical link, three hreflang
alternates and one parseable JSON-LD block.

The report also includes a negative audit: the same site with one page description
stripped, proving the auditor detects a fault instead of always returning a perfect
score. It reports `description_length` as a major issue on `home` and scores 8500.
That is the useful evidence in a client review: remove one required field and the
score drops by exactly one major penalty. If the negative audit ever scores 10000,
the auditor is broken and the positive score is worthless.
## Inquiry Form
Form id `FORM-JW-01`, endpoint `POST /api/growth/inquiry`, rendered on the home page
in all three languages.

| Field | Type | Required |
|---|---|---|
| `contact_name` | text | true |
| `email` | email | true |
| `company` | text | false |
| `country` | text | true |
| `intent` | select | true |
| `message` | textarea | true |

Intent options: `sample_request`, `bulk_quote`, `oem`, `partnership`,
`information`. Labels come from `config/growth/copy.json`; no field outside this
list is accepted.
## Lead Scoring
Deterministic, a pure function of the inquiry and `config/growth/crm.json`. Base is
10; the total is clamped to 0 through 100.

| Factor | Match | Points |
|---|---|---|
| `base` | every inquiry | 10 |
| `intent_weight` | `bulk_quote` 25, `oem` 22, `partnership` 18, `sample_request` 12, `information` 4, other 2 | as listed |
| `market_focus` | DE 15, FR 15, NL 15, IT 12, ES 12, US 12, GB 12, JP 10, AE 10, CN 8, other 5 | as listed |
| `company_present` | company is present | 8 |
| `message_specificity` | message mentions a quantity unit such as pcs, pieces, units, sets or stueck | 10 |
| `individual_buyer` | no company on the inquiry | -5 |

Worked examples: INQ-0001, DE bulk quote with company and a quantity marker, 10 +
25 + 15 + 8 + 10 = 68; INQ-0002, CN sample request with no company and a quantity
marker, 10 + 12 + 8 + 10 - 5 = 35; INQ-0003, US information request with company,
10 + 4 + 12 + 8 = 34. Every score carries a `score_breakdown`, so a sales manager
can challenge a number factor by factor instead of arguing about the total.
## SLA and Routing
SLA is 4 hours from submission. `sla_due_at` is set at intake; the first response
time is recorded when the lead moves to `contacted`. An open lead past its due time
appears in `sla_breaches`; the demo reports zero.

| Route id | Intents | Owner |
|---|---|---|
| `route_export_bulk` | `bulk_quote`, `oem` | Export desk (OWNER-EXPORT-01) |
| `route_studio_sample` | `sample_request` | Studio desk (OWNER-STUDIO-01) |
| `route_default` | `partnership`, `information` | General desk (OWNER-GENERAL-01) |

Routing is by intent only. Country, score and company never change the owner. If a
lead is misrouted, fix the intent or the route table; do not patch the lead.
## Follow-Up Templates
Follow-ups are created at intake from the intent, with due times offset from the
submission time.

| Template id | Offset | Channel | Intents | Subject |
|---|---|---|---|---|
| `ack_sample` | 2 hours | email | sample_request | Your sample request reached the studio |
| `information_reply` | 6 hours | email | sample_request, information | More information from the studio |
| `quote_follow_up` | 24 hours | email | bulk_quote, oem, partnership | Follow-up on your quotation |
| `call_back` | 72 hours | phone | bulk_quote, oem | A short call about your order |

Bodies live under `follow_ups` in `config/growth/copy.json`. A body is a starting
point, not a script: the owner adds market, quantity and finish. Five follow-ups are
open in the current demo run.
## Quote Rules
A quote is created only when a lead moves to `quoted`. Currency is USD; validity is
14 days; base amounts by intent are sample_request 18000 cents, bulk_quote 240000,
oem 360000, partnership 120000, information 0. Incoterm is US DDP, DE, FR and NL
CIF, and FOB everywhere else. A quote is a draft attached to the lead and does not
create an order. The demo's only quote is QTE-0001 for INQ-0001 at 240000 cents,
CIF, valid until 14 days after issue.
## Pipeline
Stages in order: `new`, `qualified`, `contacted`, `quoted`, `won`, `lost`. Intake
creates a lead directly in `qualified`, because scoring and routing already
happened.

| From | Allowed to |
|---|---|
| `new` | `qualified`, `lost` |
| `qualified` | `contacted`, `lost` |
| `contacted` | `quoted`, `lost` |
| `quoted` | `won`, `lost` |
| `won` | none |
| `lost` | none |

Each transition needs a note of at least 12 characters. `won` and `lost` are
terminal. Stage events are `routed`, `contacted`, `quoted`, `won` and `lost`; every
step appends to `crm_events`, which is why the trace can be replayed.
## Running the Loop
1. `python -m c2m_craft demo` regenerates `out/site` and `out/growth_report.json`.
2. `python -m c2m_craft serve` starts the service on loopback.
3. `GET /api/growth/site` returns the site record, SEO audit and page list.
4. `GET /api/growth/crm` returns policy, inquiries, board, trace and summary.
5. `POST /api/growth/inquiry` creates an inquiry from site_id, language, contact,
   message, intent and optional product_interest.
6. `POST /api/growth/inquiries/{inquiry_id}/advance` moves one lead with a target
   stage and a note; the transition table and note length are enforced.

Operating rhythm: daily, read the SLA board, clear due follow-ups and answer every
inquiry in the language it arrived in. Weekly, review quote validity, win and loss
notes, and leads that sat too long in one stage. Monthly, re-run the demo, confirm
the SEO score and negative audit, and check that every page is still `reviewed`.
Quarterly, sample closed leads against their `crm_events` trace and confirm the
notes are good enough for someone else to take over.
