# ADR 0003 - two-tier craft review

## Status
Accepted for M1.

## Context
The client's craft knowledge is verbal and will be proofread by named
craftspeople after award. A rule engine that silently decides "not manufacturable"
would either be ignored or, worse, trusted. A purely manual workflow would not be
runnable software.

## Decision
Separate the deterministic decision from the human confirmation:

- the engine evaluates rules and workshop capability checks and records every
  evaluation with the fact values that triggered it;
- a rule can request a human (`review.trigger = on_fail` or `always`); the
  assessment then enters a queue with the failed rule ids, the auto verdict and
  an SLA;
- a craftsperson either confirms the auto verdict or overrides it; an override
  needs a written reason of at least eight characters and must actually change
  the verdict, which is enforced both in the service and in the contract
  invariant;
- `final_verdict` is the effective verdict and both tiers stay in the record.

## Consequences
The prototype can be run by a non-expert without pretending the rules are
authoritative, and the client can audit exactly which rule and which number
caused a verdict. The cost is an extra queue and two more states to test, which
M1 covers with positive and negative cases.

## Alternatives rejected
- "Engine is advisory only": the work order gate would have no meaning.
- "Human is always required": the demo would not run offline, and the 20-case
  expectation table would be untestable.
