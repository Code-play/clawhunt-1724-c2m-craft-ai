# ADR 0004 - industry switch by configuration

## Status
Accepted for M1.

## Context
The brief requires reusable components for at least two industries with
"industry switching via configuration rather than duplicating code", and the
client's six clusters must not become six forks.

## Decision
An industry is a directory of data, not a branch in code:

```
config/industries/jewelry.json      price profile, categories, BOM rules, process route
config/craft_rules/jewelry.json     facts schema plus rules
config/equipment/WS-JW-*.json       capability envelopes for that industry
```

The service loads every industry found on disk, builds one rule set per file, and
the HTTP layer exposes them without knowing which ones exist. Adding footwear or
medical means adding files. Revenue shares, deposit rates and refund policy live
in `config/commerce/pricing.json` for the same reason.

M1 proves the switch with evidence rather than a claim: the same design brief is
generated under jewelry and under hardwood, and the same concept is assessed at
two workshops and under two industries, yielding different verdicts and different
reasons with no code change.

## Consequences
Two industries in M1, four more in M3, with the same engine. The risk is
configuration drift, so the lint validates rule files and capability checks
against the same fact schema, and the demo fails if a rule references a fact that
does not exist.

## Alternatives rejected
- "Class per industry": the second industry would duplicate the engine.
- "One merged fact schema for all industries": the assessment would carry
  meaningless facts and the reasons would be vague.
