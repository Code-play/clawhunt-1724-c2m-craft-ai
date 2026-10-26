# Rule authoring form

One row per rule. Fill the table, then translate it into one JSON object in
`config/craft_rules/<industry>.json`. A craftsperson can fill this without
reading code; the engineer turns it into JSON once and then never touches the
semantics again. Run `python -m c2m_craft rules lint` after every edit.

## The form

| # | Field | What to write | Example |
|---|---|---|---|
| 1 | Rule id | `<INDUSTRY>-<PROCESS>-<NNN>`, unique across both industries | `JW-CAST-003` |
| 2 | Process | One of the workshop processes (casting, setting, chasing, surface, forming, material, assembly, joinery, carving) | `casting` |
| 3 | Severity | `blocker` (cannot be made), `cost` (can be made at extra cost or risk), `quality` | `blocker` |
| 4 | Title, Chinese | Short defect name, at most 40 characters | `壁厚低于 0.55 mm` |
| 5 | Title, English | Short defect name, at most 40 characters | `Wall below 0.55 mm` |
| 6 | Condition | Fact, operator and value; combine with "all of", "any of", "not" | `min_wall_thickness_mm < 0.55` |
| 7 | Verdict | `not_manufacturable` for a blocker, `conditionally_manufacturable` for cost | `not_manufacturable` |
| 8 | Reason, Chinese | Why it fails, with `{fact}` placeholders for the numbers | `最小壁厚 {min_wall_thickness_mm} mm 低于手工铸造下限` |
| 9 | Reason, English | Same sentence in English, same placeholders | `A {min_wall_thickness_mm} mm wall is below the manual-casting limit` |
| 10 | Fix | What to change, plus the field and value to change it to | `raise the wall to 0.8 mm` -> `min_wall_thickness_mm = 0.8` |
| 11 | Evidence | Who said it, when, confidence, and whether the client must still confirm | `JW-ARTISAN-01, 2026-10-10, high, needs client confirmation` |
| 12 | Review | `artisan` + `on_fail` when a human must look at a failure; `auto` + `never` for routine cost rules | `artisan / on_fail` |

## Example row

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| JW-CAST-003 | casting | blocker | 石膏模未排气 | Vents missing in the mould | `hollow_cast = true` and `undercut = true` | not_manufacturable | 空心件带倒扣时石膏模无法排气，浇不足比例超过三成 | A hollow body with an undercut cannot vent; more than 30 percent short pours | 增加两个排气孔或改分模 -> `undercut = false` | JW-ARTISAN-01, 2026-10-12, medium, needs client confirmation | artisan / on_fail |

## Conditions cheat sheet

| Intent | Write |
|---|---|
| below a limit | `{fact} lt {value}` |
| at or below a limit | `{fact} lte {value}` |
| above a limit | `{fact} gt {value}` |
| exactly a named option | `{fact} eq "option"` |
| one of several options | `{fact} in ["a", "b"]` |
| an array contains one of | `{fact} contains_any ["a"]` |
| two conditions at once | `all: [condition, condition]` |
| either condition | `any: [condition, condition]` |
| absence | `not: condition` |
| the fact is not declared | `{fact} missing` |

## Rules for placeholders

- Only use `{fact_name}` for facts that exist in the industry fact schema.
  Anything else is a lint error, because the reason text would print a literal
  brace to the reader.
- Write the number formatting as a plain placeholder; the engine formats 0.30 as
  `0.3` and lists arrays with commas.
- Keep both languages saying the same thing. The lint cannot check translation
  quality, only presence.

## What the lint will reject

- an unknown fact name in the condition, in a placeholder or in a fix
- an ordered comparison (`lt`, `gt`) on a string or boolean fact
- a membership test (`in`, `contains_any`) on a fact with no enum
- a duplicate rule id, including across industries
- a blocker that is `auto` and `never` reviewed
- a shadowed rule (identical condition and verdict as another rule)
- a rule with no `references` entry
- a fact declared in the schema but used by nothing

## After changing a rule

1. `python -m c2m_craft rules lint`
2. `python -m c2m_craft rules explain --rule-id <id>`
3. `python -m c2m_craft demo`
4. Compare `out/assessment_matrix.md` with `samples/concepts/expected.json`. A
   flipped verdict is expected only when the expectation table is updated on
   purpose; the verification script will fail until the two agree again.
