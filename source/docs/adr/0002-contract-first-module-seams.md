# ADR 0002 - contract-first module seams

## Status
Accepted for M1.

## Context
Modules A (craft co-creation and C2M), B (enterprise service layer) and C
(cultural IP pipeline) are delivered in different milestones. If M1 encoded the
order shape inside the HTTP handlers, every later module would resend fields and
the ledger would drift.

## Decision
Data shapes are contracts before they are code. Ten JSON Schema documents live in
`contracts/`, registered in `contracts/registry.json` with a semantic version,
dependencies, invariants and the requirement ids they serve. Cross-field rules
are declared in the schema (`x-invariants`) and implemented once in
`core/invariants.py`. The HTTP layer validates before it stores; the demo
validates before it writes; the tests validate the samples and the negatives.

Module boundaries: `core` has no imports from `craft`, `creative`, `library`,
`commerce` or `web`; those four depend only on `core`; `web` depends on the
service container. The B and C modules land as new subpackages plus new
contracts, not as edits to the kernel.

## Consequences
Every stored record can be re-validated by a third party without running the
application, and every rejection names the instance path. The cost is a
hand-written validator (no `jsonschema` dependency) and a curated keyword subset;
that subset is listed in `docs/data-contracts.md` and exercised by fourteen
negative samples, so it cannot quietly become permissive.

## Alternatives rejected
- "Depend on `jsonschema`": violates the standard-library-only constraint and
  would make the clean-machine claim untrue.
- "Validate with dataclasses only": field paths and cross-field invariants would
  be lost, and the negative suite could not assert where the rejection happened.
