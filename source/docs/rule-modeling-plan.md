# Manufacturability rule modelling plan

This is the technical highlight of the brief: **can this concept be made, where
can it not be made, and what should change** - answered by rules and equipment
envelopes expressed as data, with a craftsperson in the loop and a lint that lets
a non-programmer edit the rules without breaking them.

## 1. Why rules as data

The client supplies verbal craft rules and will proofread them after award. If
those rules lived in Python, every proofreading round would need a programmer and
a release. Instead each rule is one JSON object in a rule file:

```
config/craft_rules/jewelry.json     17 rules, 17 facts
config/craft_rules/hardwood.json    15 rules, 16 facts
config/craft_rules/rule_file.schema.json   the structure a craftsperson edits
config/equipment/WS-JW-A.json       capability envelope, equipment, QC checkpoints
config/equipment/WS-JW-B.json
config/equipment/WS-HW-A.json
config/equipment/WS-HW-B.json
```

Adding an industry means adding one rule file plus one industry profile; the
engine code does not change. That claim is verified: the same concept assessed at
two workshops of the same industry, or under two different industries, produces
different verdicts without touching code.

## 2. Fact model

A concept does not carry pixels here, it carries the parameters a craftsperson
would actually ask for. Facts are declared per industry inside the rule file,
which is also the schema the lint validates against.

### Jewelry (17 facts)

| Fact | Type | Unit | Meaning |
|---|---|---|---|
| `min_wall_thickness_mm` | number | mm | thinnest cast wall |
| `max_dimension_mm` | number | mm | largest outside dimension |
| `stone_count` | integer | - | number of stones |
| `stone_size_mm` | number | mm | largest stone diameter |
| `setting_type` | string | - | none, prong, bezel, pave, channel |
| `prong_count` | integer | - | prong count |
| `prong_thickness_mm` | number | mm | prong root thickness |
| `undercut` | boolean | - | undercut present |
| `hollow_cast` | boolean | - | hollow casting |
| `enamel` | boolean | - | enamel present |
| `enamel_firing_c` | number | C | enamel firing temperature |
| `engraving_depth_mm` | number | mm | chasing depth |
| `surface_finish` | string | - | polished, brushed, sandblasted, mirror |
| `ring_size_mm` | number | mm | ring inner circumference, 0 for non-rings |
| `alloy` | string | - | 18k_gold, 22k_gold, 925_silver, pt950 |
| `chain_link_mm` | number | mm | chain gauge, 0 for no chain |
| `recessed_area` | boolean | - | deep recess present |

### Hardwood (16 facts)

`species` (walnut, oak, elm, pine, teak), `joint_types` (array of mortise_tenon,
dovetail, screw, dowel), `tolerance_mm`, `span_mm`, `load_kg`, `carve_depth_mm`,
`wood_moisture_pct`, `panel_thickness_mm`, `finish` (oil, wax, lacquer,
high_gloss, matte), `humidity_zone` (dry, temperate, coastal, tropical),
`curve_radius_mm` (0 means flat), `undercut`, `hardware_included`, `leg_count`,
`cantilever`, `outdoor`.

`max_dimension_mm` and `max_dimension_mm`-style geometry facts are derived from
`form.dimensions_mm` when the concept omits them, so a designer does not have to
repeat what the model already knows.

## 3. Rule DSL

```json
{
  "id": "JW-CAST-001",
  "industry": "jewelry",
  "process": "casting",
  "severity": "blocker",
  "title": {"zh": "壁厚低于可铸下限", "en": "Wall below the castable limit"},
  "when": {"all": [{"fact": "min_wall_thickness_mm", "op": "lt", "value": 0.55}]},
  "verdict": "not_manufacturable",
  "reason": {
    "zh": "最小壁厚 {min_wall_thickness_mm} mm 低于手工铸造的 0.55 mm 下限，熔液会在薄壁处提前凝固。",
    "en": "A {min_wall_thickness_mm} mm wall is below the 0.55 mm manual-casting limit; the melt freezes before the cavity fills."
  },
  "fixes": [{"text": {"zh": "把最薄处加到 0.8 mm 以上。", "en": "Thicken the thinnest section to 0.8 mm."},
             "suggested_change": {"min_wall_thickness_mm": 0.8}}],
  "evidence": {"source_type": "synthetic_baseline", "artisan_ref": "JW-ARTISAN-01",
               "captured_at": "2026-10-10T00:00:00Z", "reviewed_by": "pending",
               "confidence": "high", "client_confirmation_required": true},
  "review": {"tier": "artisan", "trigger": "on_fail"},
  "version": "1.0.0",
  "references": ["docs/rule-modeling-plan.md#casting"]
}
```

A rule is a **defect detector**: when `when` matches the facts, the rule fails,
contributes its verdict and offers fixes. Operators:

| Operator | Applies to | Semantics |
|---|---|---|
| `lt`, `lte`, `gt`, `gte` | number, integer | ordered comparison |
| `eq`, `ne` | any | equality |
| `in`, `not_in` | enum strings | membership |
| `contains_any` | arrays | at least one member matches |
| `missing`, `present` | any | presence test (no value needed) |

Conditions compose with `all`, `any` and `not`. `applies_when` is an optional
precondition used by capability checks (for example the ring-size limits only
apply when `ring_size_mm > 0`).

`reason` and fix text are bilingual templates; `{fact}` placeholders are filled
with the concept's values in both languages, so a craftsman reading the Chinese
and an engineer reading the English see the same numbers. A placeholder that does
not name a declared fact is a lint error.

## 4. Equipment capability

Each workshop file declares an envelope and the QC checkpoints it can run:

| Workshop | Key limits | Lead time |
|---|---|---|
| WS-JW-A | wall 0.6 mm, casting envelope 45 mm, alloys 18k/22k/925/pt950, ring 44-62 mm, enamel kiln 820 C | 21 days |
| WS-JW-B | wall 0.9 mm, casting envelope 30 mm, alloys 18k/925, ring 48-58 mm, enamel furnace 750 C | 16 days |
| WS-HW-A | carve depth 12 mm, span 1200 mm, kiln moisture 14% | 35 days |
| WS-HW-B | carve depth 8 mm, span 900 mm, kiln moisture 12% | 24 days |

Capability checks use the same condition vocabulary and carry their own reason
and fix, which is what makes "it can be made, just not here" expressible:
`DC-0003` is conditionally manufacturable at WS-JW-A and impossible at WS-JW-B
because of the 0.9 mm wall limit; `DC-0004` fails only at WS-JW-B because its
800 C enamel exceeds that furnace.

## 5. Two-tier assessment

Tier one is deterministic:

1. derive facts and validate them against the industry fact schema;
2. if a required fact is missing, return `not_assessable` with the missing list
   instead of guessing;
3. evaluate every workshop capability check and every industry rule;
4. reduce: any failed blocker means `not_manufacturable`, otherwise any failed
   cost or quality rule means `conditionally_manufacturable`, otherwise
   `manufacturable`;
5. collect the failed rule ids as blockers and every fix, rendered bilingually.

Tier two is the craftsperson. A rule may declare `review.trigger = on_fail` or
`always`. When such a rule fails, the assessment enters the review queue with the
failed rule ids, the auto verdict, the assigned artisan and an SLA. The queue
item is a contract (`artisan_review`): a confirmation must keep the verdict, and
an override needs a written reason of at least eight characters and must actually
change the verdict. Both tiers stay in the record, so a later reader can see what
the engine said and what the human decided.

## 6. Rule catalogue

### Jewelry

| Rule | Process | Severity | Trigger |
|---|---|---|---|
| JW-CAST-001 | casting | blocker | wall below 0.55 mm |
| JW-CAST-002 | casting | cost | hollow casting with a wall under 0.8 mm |
| JW-SET-001 | setting | blocker | stone above 8 mm with no declared setting |
| JW-SET-002 | setting | blocker | prong root under 0.5 mm |
| JW-SET-003 | setting | blocker | pave with stones under 1.2 mm |
| JW-SET-004 | setting | cost | more than 40 stones per piece |
| JW-SET-005 | setting | blocker | fewer than three prongs on a stone above 4 mm |
| JW-CHASE-001 | chasing | cost | engraving deeper than 0.35 mm in one pass |
| JW-CHASE-002 | chasing | cost | undercut needs a split mould |
| JW-SURF-001 | surface | cost | mirror polish over a recessed area |
| JW-SURF-002 | surface | cost | enamel fired above 780 C |
| JW-FORM-001 | forming | cost | ring size below the standard mandrel |
| JW-FORM-002 | forming | blocker | chain link under 1.0 mm |
| JW-MAT-001 | material | cost | pt950 under 1.0 mm wall |
| JW-MAT-002 | material | cost | 22k prongs under 0.8 mm |
| JW-ASM-001 | assembly | blocker | channel setting on a wall under 1.0 mm |
| JW-ASM-002 | assembly | blocker | hollow body with enamel |

### Hardwood

| Rule | Process | Severity | Trigger |
|---|---|---|---|
| HW-JOIN-001 | joinery | cost | mortise tolerance above 0.3 mm |
| HW-JOIN-002 | joinery | blocker | screw-only structure above 40 kg |
| HW-JOIN-003 | joinery | blocker | span above 900 mm on a panel under 18 mm |
| HW-JOIN-004 | joinery | blocker | mortise joint with moisture above 12% |
| HW-JOIN-005 | joinery | blocker | dovetail in a panel under 14 mm |
| HW-CARVE-001 | carving | cost | undercut deeper than 8 mm |
| HW-CARVE-002 | carving | cost | tight radius with deep carving |
| HW-SURF-001 | surface | cost | high gloss in a coastal climate |
| HW-SURF-002 | surface | blocker | pine used outdoors |
| HW-SURF-003 | surface | cost | lacquer outdoors |
| HW-FORM-001 | forming | blocker | cantilever span above 1200 mm |
| HW-FORM-002 | forming | cost | panel under 16 mm |
| HW-MAT-001 | material | cost | pine above 60 kg |
| HW-MAT-002 | material | blocker | above 120 kg on fewer than four legs |
| HW-SAFE-001 | assembly | cost | load-rated hardware missing above 60 kg |

Every rule carries `references` pointing at a section of this document, and the
verification script asserts that each rule id can be found in this file. That is
how the acceptance criterion "ten out of ten agree with the manual craft rules
documented in the repository" is made checkable rather than asserted.

## 7. Worked example: DC-0002 at WS-JW-A

Concept: 0.3 mm wall pendant, single 8.5 mm stone, no declared setting.

| Step | Result |
|---|---|
| facts | wall 0.3, stone 8.5, setting none, dimension 40 |
| capability CAP-JW-A-01 | fail: wall 0.3 < 0.6 -> blocker |
| rule JW-CAST-001 | fail: wall 0.3 < 0.55 -> blocker |
| rule JW-SET-001 | fail: stone 8.5 > 8 and setting none -> blocker |
| other rules | pass or not applicable |
| verdict | not_manufacturable, three blockers |
| fixes | raise the wall to 0.8 mm; add a bezel; re-orient or split the casting |
| review | required because JW-CAST-001 and JW-SET-001 are `on_fail` rules |

At WS-JW-B the same concept fails four checks because the second workshop also
cannot cast 40 mm or wall 0.9 mm. The verdict is the same; the reasons are not.

## 8. Non-programmer maintenance workflow

1. Copy one row of `docs/rule-authoring-form.md` and fill it in.
2. Add the object to `config/craft_rules/<industry>.json`.
3. Run `python -m c2m_craft rules lint`. It rejects unknown facts, type
   mismatches, unknown placeholders, duplicate ids, shadowed rules, rules whose
   suggested change names a fact that does not exist, blockers that never reach a
   craftsperson, and facts that no rule or capability check uses.
4. Run `python -m c2m_craft rules explain --rule-id <id>` to see how the engine
   reads the rule.
5. Re-run `python -m c2m_craft demo` and compare `out/assessment_matrix.md`
   against `samples/concepts/expected.json`; a rule change that flips a verdict
   shows up as a red expectation until the expectation table is updated on
   purpose.

The same lint runs inside `verify/run_verification.py`, so a broken rule file
cannot ship.

## 9. Evidence and client confirmation

The client supplies verbal craft rules and proofreading after award. Until then
every rule is marked:

```
"evidence": {"source_type": "synthetic_baseline", "reviewed_by": "pending",
             "client_confirmation_required": true}
```

The lint reports these as `EVIDENCE_PENDING` (informational, 32 occurrences), so
the gap is visible rather than buried. When the interviewed rules arrive, the
field changes to `artisan_verbal`, `reviewed_by` gets the craftsperson's id, and
`client_confirmation_required` becomes false. No code changes; the verdict
mapping stays the same.

Rule semantics in M1 are plausible industry practice written down so the engine
can be exercised end to end. They are not the client's confirmed rules, and the
delivery says so in the README, the UI and DELIVERY.md.

## 10. Coverage

- 32 rules across two industries, 33 fact declarations, all referenced by at
  least one rule or capability check (the lint fails on an unused fact).
- 24 capability checks across four workshops.
- 10 concept inputs, of which 3 are deliberate counterexamples, assessed against
  two workshops each: 20 verdicts, all matching the hand-written expectation
  table committed before the engine ran.
- Every failed rule yields a bilingual reason and at least one fix with a
  machine-readable `suggested_change`, so the same data can drive an "apply the
  fix and re-assess" loop in M2 without a new rule format.
