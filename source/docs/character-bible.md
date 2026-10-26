# Character Bible: The Two Guardians of the Craft Village
Canonical reference for bible IPB-0001. Source data lives in
`config/ip/characters.json` and is rendered to `out/character_bible.json` by
`python -m c2m_craft demo`. This document is the human-readable companion; the JSON
record is the machine-readable one. If they disagree, the JSON record and the
invariant win, and this document is corrected.

All characters, places and organisations are synthetic. Heritage techniques are
cited as shared regional practice, never claimed as private property.
## World
Working title: The Two Guardians of the Craft Village.

Premise: A craft village lives by two promises: the forest gives the wood, the kiln
gives the colour. Two guardians keep the promises, and when one of them stops
listening the village loses half of what it knows.

Setting: A craft village between a mountain range and a bay. By day the woodworking
and jewellery workshops share one street; by night the kiln fire and the mountain
wind take turns watching over the village. Two guardians are said to keep it: one
of timber and grain, one of kiln fire and glaze. Era: timeless, so the setting
supports short drama, merchandise, exhibition and social formats without a period
claim.

Three world rules:

1. A guardian may borrow a motif from the village, but may never claim a
   traditional prototype as private property.
2. Every piece made under a guardian's name carries the name of the craftsperson
   who finished it.
3. When a guardian takes, the guardian must also teach; craft knowledge never
   leaves the village without a student.

Rule 1 is enforced by the licensing invariants, rule 2 appears in merchandise
labelling, and rule 3 drives the final beat of the short drama.

Conflict: the kiln guardian has let the fire grow cold to protect the forest, and
the wood guardian reads that silence as betrayal; the village loses its glaze and
the two stop speaking. Resolution theme: the two crafts are one practice: the wood
needs the fire to finish it, and the fire needs the wood to be worth burning. The
conflict is a misunderstanding between two people who want the same thing, not a
villain story. Neither guardian is wrong; each is incomplete without the other.

| Id | Name | Element | Role | Archetype | Review |
|---|---|---|---|---|---|
| CHR-MU | A-Mu | wood | guardian of grain and timber | patient steward who measures twice | CRV-0001 |
| CHR-HUO | A-Huo | fire | guardian of kiln fire and glaze | restless maker who listens to the kiln | CRV-0002 |

## A-Mu (CHR-MU)
Silhouette: a tall hooded figure with square shoulders, a long apron of carved
panels and a hem that widens like a tree root. The shape is vertical and stable; in
a wide shot A-Mu reads as a column, not a person in a costume.

Palette: `#3F5B43` deep green for the forest and apron base; `#8C6A3F` warm timber
brown for panels and grain lines; `#E7D8B8` pale linen for the measure cord and
highlights; `#C9A227` brass for the try square and metal accents; `#1F2A44`
near-navy for outline and shadow.

Motifs: mortise-and-tenon lattice, rice ear, cloud scroll.

Taboos: never cuts a living tree for a commission; never signs a piece that a
craftsperson did not finish.

Props: brass try square, linen measure cord.

Voice: warm register, measured pace. Signature line: "Measure twice, and let the
wood keep the second measure."

Personality axes (basis points): warmth 7800, order 8800, energy 4200, candour
6100. High order and low energy explain why A-Mu waits and why the waiting looks
like stubbornness to A-Huo. Relationship: sibling to CHR-HUO; raised in the same
workshop street, they disagree like two hands of the same craft.

Arc beats:

1. The silent kiln. A-Mu finds the kiln cold for the first time in living memory
   and assumes the fire guardian has abandoned the village.
2. The unfinished panel. A-Mu refuses to finish a commissioned panel because the
   grain needs fire to set the inlay; the buyer walks away.
3. The shared bench. A-Mu walks to the kiln with a half-carved panel, and the two
   guardians build one bench where wood and fire are finished together.

Licence-safe sourcing: `self_produced`. Authenticity label: "Original character,
self-produced concept data, AI-assisted draft reviewed by a human content
reviewer." Content review CRV-0001.
## A-Huo (CHR-HUO)
Silhouette: a compact figure wrapped in a cracked-glaze mantle, with one sleeve
wider than the other and a small flame-shaped collar. Asymmetry is the identifier;
A-Huo should never look symmetrical in a still frame.

Palette: `#8E3B2F` deep oxide red for the mantle body; `#D9822B` ember orange for
the flame wave and rim light; `#F2C14E` kiln yellow for the hottest highlight;
`#2B2B2B` charcoal for cracks and shadow; `#E7D8B8` pale linen as the shared neutral
with A-Mu.

Motifs: crackle glaze, flame wave, peony roundel.

Taboos: never fires a glaze that copies a protected ritual object; never sells a
second firing without telling the buyer.

Props: glaze test tile, long bellows pipe.

Voice: crisp register, brisk pace. Signature line: "The kiln does not argue; it
answers in colour."

Personality axes (basis points): warmth 6400, order 4800, energy 9100, candour
8800. High energy and high candour explain why the silence is unbearable for A-Huo:
it cannot be answered with an argument. Relationship: sibling to CHR-MU; trusts the
wood guardian's patience but not the silence that came with it.

Arc beats:

1. The cold kiln. A-Huo let the fire die to keep the forest from being cut for a
   season, and cannot explain the choice without sounding like a refusal.
2. The crackled test. A single test tile survives the cold kiln with a crackle no
   one has seen; A-Huo realises the village glaze was waiting for this.
3. One bench. A-Huo carries the kiln fire to the wood bench and teaches the
   finishing step to the village apprentices, finishing A-Mu's half-carved panel.

Licence-safe sourcing: `self_produced`. Authenticity label: "Original character,
self-produced concept data, AI-assisted draft reviewed by a human content
reviewer." Content review CRV-0002.
## Relationship Dynamics
The pair works because they are opposed on the same axis, not because they are
opposites in every way. A-Mu is order without motion; A-Huo is motion without
order. Each character's taboo is a limit the other tests.

| Tension | A-Mu position | A-Huo position | Story use |
|---|---|---|---|
| Time | Wait for the right measure | Act while the kiln is hot | The pilot delay in the middle act |
| Material | Wood must keep its grain | Fire must leave a colour | The shared bench in the final act |
| Speech | Silence is patience | Silence is a refusal | The break at the end of act one |
| Credit | The finisher signs | The fire teaches | The apprenticeship beat |

Do not resolve this by making one character "learn to be more like the other". The
resolution is a third thing: one bench, two pairs of hands.
## Heritage References
Cited non-exclusively. The `exclusive_claimed` flag is false for every reference,
and the licensing invariants refuse an exclusive claim while these references are
present.

| Reference | Exclusive claimed | How it is used |
|---|---|---|
| Regional mortise-and-tenon joinery technique | false | A-Mu's lattice and silhouette construction |
| Local kiln-fire glaze technique | false | A-Huo's mantle and the crackle test |
| Peony roundel as a shared decorative motif | false | One A-Huo motif, never a sacred image |

Position: the bible borrows vocabulary, not ownership. The characters are original
combinations of silhouette, palette, motif and prop; the heritage techniques remain
shared practice. A reviewer who sees an origin claim, a sacred object reproduction
or an exclusivity grant must reject the record.
## Content Review
| Review | Subject | Verdict | Heritage note |
|---|---|---|---|
| CRV-0001 | CHR-MU | approved | Mortise-and-tenon joinery and the cloud scroll are cited as shared regional techniques, never claimed as private property. |
| CRV-0002 | CHR-HUO | approved | Kiln fire glaze and the peony roundel are cited as shared techniques; the crackle pattern is drawn from the synthetic test tile, not from a protected object. |

Reviewer: Content review desk. Both reviews were checked against the character
template items: heritage non-exclusive, original design, AI disclosure, canon
consistency, no ritual object and craft review.
## Visual Library and Usage
The visual library is `out/ip_asset_library.json`. Assets are deterministic drawing
recipes, not image files: each has a recipe, a palette drawn from the bible and a
checksum that recomputes. Examples include `VA-MU-TURN-FRONT`, `VA-HUO-TURN-SIDE`,
`VA-MU-EXPR-WARM` and `VA-SCENE-KILN-MOUTH`.

Usage plan: formats `short_drama`, `merchandise`, `exhibition`, `social`;
territories CN, EU, US. The short drama SDR-0001 is documented in
`docs/short-drama-workflow.md`; the licence set is documented in
`docs/licensing-templates.md`.

Do: keep the palette exact, because the hex values are the identity, not a mood
board; keep the silhouette rule, vertical and square for A-Mu, compact and
asymmetric for A-Huo; keep the taboos visible in behaviour, never explained in
dialogue; keep the two signature lines verbatim, because they are the earworms.

Do not: add a third guardian or a chosen-one subplot; give either guardian a
weapon, a throne or a temple; reproduce a ritual object, a sacred site or a
protected pattern; claim exclusivity over a heritage technique or a shared motif;
ship an asset without a review state and an authenticity label.
